"""
Prepare a portrait photo for clean ASCII conversion:
  1. remove the background (rembg) so the subject is isolated
  2. boost LOCAL contrast (CLAHE) so a flatly-lit face gains highlights and
     shadows -- this is what turns a dark blob into a recognizable face
  3. composite the subject onto pure white so the background reads as blank
     (white -> spaces in the ascii ramp)

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.
Run once whenever the source photo changes; the ascii SVG itself is static.

    python scripts/prep_photo.py <input.jpg> [output.png]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import remove

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.jpg")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

# 1. cut out the subject
cut = remove(Image.open(INP).convert("RGBA"))
rgb = np.array(cut.convert("RGB"))
alpha = np.array(cut.split()[-1])                 # 0 = background

# 2. local-contrast the luminance (CLAHE)
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
clahe = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8))
gray = clahe.apply(gray)

# a touch of global lift so the face sits in the sparse end of the ramp
gray = cv2.convertScaleAbs(gray, alpha=1.05, beta=18)

# 3. paste onto white using the alpha mask (feathered a hair to avoid a halo)
mask = (alpha.astype(np.float32) / 255.0)
mask = cv2.GaussianBlur(mask, (0, 0), 1.0)
out = gray.astype(np.float32) * mask + 255.0 * (1.0 - mask)
out = np.clip(out, 0, 255).astype(np.uint8)

# 4. crop to the bounding box of the subject to remove dead space
ys, xs = np.where(alpha > 10)
if len(ys) > 0 and len(xs) > 0:
    min_y, max_y = np.min(ys), np.max(ys)
    min_x, max_x = np.min(xs), np.max(xs)
    # Add a small 5% padding around the bounding box
    pad_y = int((max_y - min_y) * 0.05)
    min_y = max(0, min_y - pad_y)
    max_y = min(out.shape[0], max_y + pad_y)
    # DO NOT crop X axis - this preserves the original photo's horizontal framing and shoulder proportions
    min_x = 0
    max_x = out.shape[1]
    out = out[min_y:max_y, min_x:max_x]

Image.fromarray(out, mode="L").save(OUT)
print("wrote", OUT, out.shape)
