#!/usr/bin/env python3
"""
Fetch real daily contribution counts from GitHub's GraphQL API.
Requires a GITHUB_TOKEN environment variable.
Writes data/contributions.json with the raw days plus derived stats.
"""
import datetime
import json
import os
import sys
import requests

USERNAME = os.environ.get("GH_PROFILE_USER", "Abhinav2896")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")


def fetch_days():
    if not TOKEN:
        print("Error: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    # Calculate exact rolling 365 days window up to today
    to_date = datetime.datetime.now(datetime.timezone.utc)
    from_date = to_date - datetime.timedelta(days=365)
    
    query = """
    query($userName: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $userName) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
        "userName": USERNAME,
        "from": from_date.isoformat(),
        "to": to_date.isoformat()
    }
    
    resp = requests.post(url, headers=headers, json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    
    if "errors" in data:
        print("GraphQL Errors:", json.dumps(data["errors"], indent=2), file=sys.stderr)
        sys.exit(1)
        
    calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append({
                "date": day["date"],
                "count": day["contributionCount"]
            })
            
    days.sort(key=lambda d: d["date"])
    return days


def compute_current_streak(days):
    idx = len(days) - 1
    if idx >= 0 and days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break the streak on it
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"]) if days else {"date": None, "count": 0}
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "best_day": best,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "monthly_totals": monthly_list,
        "days": days
    }


def main():
    print(f"fetching graphql data for {USERNAME}...")
    days = fetch_days()
    data = build_data(days)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"wrote {OUT_PATH}: {data['total_contributions']} contributions, "
          f"{len(days)} days ({days[0]['date']} to {days[-1]['date']})")


if __name__ == "__main__":
    main()
