"""fragment_compare.py -- 3-way zoom of the sphere area: Windows vs editor vs device."""
import os
from PIL import Image, ImageDraw

WIN = r'<EVIDENCE_DIR>\img\win_desktop_wallpaper.png'
ED = r'<BUILD_DIR>\_probe\ab\iso_high_1600x720.png'
DEV = r'<BUILD_DIR>\_probe\shots\b67_desktop.png'
OUT = r'<EVIDENCE_DIR>\img\sphere_three_way_zoom.png'

BOX = (380, 320, 800, 700)      # left sphere + fragment cluster, in 1600x720 PIL coords


def norm1600(path, is_win):
    im = Image.open(path).convert('RGB')
    if is_win:
        w, h = im.size
        nh = int(w / (1600.0 / 720.0))
        top = max(0, (h - nh) // 2)
        im = im.crop((0, top, w, top + nh))
    return im.resize((1600, 720), Image.LANCZOS)


def main():
    a = norm1600(WIN, True).crop(BOX)
    b = norm1600(ED, False).crop(BOX)
    c = norm1600(DEV, False).crop(BOX)
    z = 2
    a = a.resize((a.width * z, a.height * z), Image.NEAREST)
    b = b.resize((b.width * z, b.height * z), Image.NEAREST)
    c = c.resize((c.width * z, c.height * z), Image.NEAREST)
    W = a.width
    H = a.height
    canvas = Image.new('RGB', (W * 3 + 8, H + 18), (20, 20, 24))
    d = ImageDraw.Draw(canvas)
    for i, (lbl, im) in enumerate((('WINDOWS', a), ('EDITOR (high)', b), ('DEVICE b67', c))):
        canvas.paste(im, (i * (W + 4), 18))
        d.text((i * (W + 4) + 4, 4), lbl, fill=(255, 220, 120))
    canvas.save(OUT)
    print('wrote %s %s' % (OUT, canvas.size))


if __name__ == '__main__':
    main()
