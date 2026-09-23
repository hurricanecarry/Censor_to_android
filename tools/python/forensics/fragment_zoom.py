"""fragment_zoom.py -- tight zoom on the fragment cluster (editor render) and the device frame."""
from PIL import Image, ImageDraw

ED = r'<BUILD_DIR>\_probe\ab\iso_high_1600x720.png'
DEV = r'<BUILD_DIR>\_probe\shots\b67_desktop.png'
OUT = r'<EVIDENCE_DIR>\img\fragment_zoom_editor_dev.png'

# editor render: the cluster sits around x 430..720, y 380..700 (PIL top-left coords)
ED_BOX = (420, 370, 730, 700)
# device screenshot: the same cluster is around x 470..760, y 240..600 (visually located earlier)
DEV_BOX = (460, 230, 770, 560)

Z = 3
tiles = []
for label, path, box in (('EDITOR high', ED, ED_BOX), ('DEVICE b67', DEV, DEV_BOX)):
    im = Image.open(path).convert('RGB').crop(box)
    im = im.resize((im.width * Z, im.height * Z), Image.NEAREST)
    tiles.append((label, im))

W = max(t.width for _, t in tiles)
H = max(t.height for _, t in tiles)
canvas = Image.new('RGB', (W * len(tiles) + 8 * (len(tiles) - 1), H + 18), (20, 20, 24))
d = ImageDraw.Draw(canvas)
x = 0
for label, im in tiles:
    canvas.paste(im, (x, 18))
    d.text((x + 4, 4), label, fill=(255, 220, 120))
    x += im.width + 8
canvas.save(OUT)
print('wrote %s %s' % (OUT, canvas.size))
