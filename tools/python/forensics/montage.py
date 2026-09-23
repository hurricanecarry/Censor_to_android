"""montage.py -- build a labelled comparison strip for the B-item material question.

Panels (all 1600x720 device renders except the Windows reference):
    win      : Windows reference (downscaled to the device size)
    b67      : the device desktop after the sRGB build
    base     : r22_baseA / geom_pa_base (b66 era, sRGB=0)
    tintdef  : the probe's "default material" render
    tintadd  : the probe's "additive material" render

ASCII-only output.
"""

import os
from PIL import Image, ImageDraw

SRC = r'<BUILD_DIR>\_probe\devpull'
WIN = r'<EVIDENCE_DIR>\img\win_desktop_wallpaper.png'
B67 = r'<BUILD_DIR>\_probe\shots\b67_desktop.png'
OUT = r'<EVIDENCE_DIR>\img\b67_material_montage.png'

W, H = 800, 360
panels = [
    ('WINDOWS (reference)', WIN, True),
    ('b67 device desktop (sRGB=1)', B67, False),
    ('b66 r22_baseA (sRGB=0)', os.path.join(SRC, 'r22_baseA.png'), False),
    ('b66 geom_tint_default', os.path.join(SRC, 'geom_tint_default.png'), False),
    ('b66 geom_tint_additive', os.path.join(SRC, 'geom_tint_additive.png'), False),
]

rows = []
for label, path, is_win in panels:
    if not os.path.exists(path):
        print('MISSING %s' % path)
        continue
    im = Image.open(path).convert('RGB')
    if is_win:
        # crop the Windows shot to the same 20:9 band the device shows, then scale
        w, h = im.size
        target_ratio = 1600.0 / 720.0
        new_h = int(w / target_ratio)
        top = max(0, (h - new_h) // 2)
        im = im.crop((0, top, w, top + new_h))
    im = im.resize((W, H), Image.LANCZOS)
    rows.append((label, im))

cols = 1
canvas = Image.new('RGB', (W, (H + 18) * len(rows)), (20, 20, 20))
d = ImageDraw.Draw(canvas)
y = 0
for label, im in rows:
    canvas.paste(im, (0, y + 18))
    d.text((4, y + 3), label, fill=(255, 220, 120))
    y += H + 18
canvas.save(OUT)
print('wrote %s  %s' % (OUT, canvas.size))
