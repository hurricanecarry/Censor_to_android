"""before_after.py

Quantify the fragment/noise level inside the sphere for three frames, and build the 3-way image.

Fragments show up as high local pixel-to-pixel variation, so the metric is the mean absolute
Laplacian (difference between a pixel and the average of its 4 neighbours) inside a box that
covers the sphere.  Lower = smoother.
"""

import os
import numpy as np
from PIL import Image, ImageDraw

WIN = r'<EVIDENCE_DIR>\img\win_desktop_wallpaper.png'
B67 = r'<BUILD_DIR>\_probe\shots\b67_desktop.png'
B69 = r'<BUILD_DIR>\_probe\shots\b69_s2.png'
OUT = r'<EVIDENCE_DIR>\img\b67_vs_b69_vs_windows.png'

BOX = (600, 200, 900, 600)      # sphere area in 1600x720 device pixels (PIL top-left origin)


def load1600(path, is_win):
    im = Image.open(path).convert('RGB')
    if is_win:
        w, h = im.size
        nh = int(w / (1600.0 / 720.0))
        top = max(0, (h - nh) // 2)
        im = im.crop((0, top, w, top + nh))
    return np.asarray(im.resize((1600, 720), Image.LANCZOS), dtype=np.float64)


def laplacian_energy(a, box):
    x0, y0, x1, y1 = box
    g = a[y0:y1, x0:x1].mean(axis=2)
    lap = np.abs(g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:])
    return lap.mean(), np.percentile(lap, 99)


def main():
    win = load1600(WIN, True)
    b67 = load1600(B67, False)
    b69 = load1600(B69, False)
    print('box = %s   (sphere area)' % (BOX,))
    for name, a in (('WINDOWS', win), ('b67 BEFORE', b67), ('b69 AFTER', b69)):
        m, p99 = laplacian_energy(a, BOX)
        print('  %-12s meanLaplacian=%6.3f  p99=%7.3f' % (name, m, p99))

    W, H = 760, 342
    tiles = []
    for name, a in (('WINDOWS (reference)', win), ('b67 BEFORE fix', b67), ('b69 AFTER fix', b69)):
        im = Image.fromarray(a.astype(np.uint8))
        tiles.append((name, im.resize((W, H), Image.LANCZOS)))
    canvas = Image.new('RGB', (W, (H + 16) * len(tiles)), (18, 18, 22))
    d = ImageDraw.Draw(canvas)
    y = 0
    for name, im in tiles:
        canvas.paste(im, (0, y + 16))
        d.text((4, y + 2), name, fill=(255, 220, 120))
        y += H + 16
    canvas.save(OUT)
    print('-> %s %s' % (OUT, canvas.size))


if __name__ == '__main__':
    main()
