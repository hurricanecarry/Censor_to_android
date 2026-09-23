"""atlas_regions.py -- crop the regions behind the sphere from the CG atlas.

The isolation render says the "fragments" inside the sphere are drawn by cc_ass_l, cc_ass_r and
cc_hightlight_ass_1/2/4 (plus cc_ass_r2).  If the atlas regions themselves look smooth, the fault
is in the rendering (mesh/UV/alpha); if they look like fragments, the art is authored that way.

ASCII-only output.
"""

import os, io, re
from PIL import Image

ATLAS = r'<UNITY_PROJECT>\Assets\AssetBundles\rootpackage_assets_art_uipanels_wallpaparpanelui\TextAsset\cengceng.atlas.txt'
PNG = r'<UNITY_PROJECT>\Assets\AssetBundles\rootpackage_assets_art_uipanels_wallpaparpanelui\Texture2D\cengceng.png'
OUT = r'<EVIDENCE_DIR>\img\atlas_sphere_regions.png'

WANT = ['cc_ass_l', 'cc_ass_r', 'cc_ass_r2', 'cc_hightlight_ass_1', 'cc_hightlight_ass_2',
        'cc_hightlight_ass_3', 'cc_hightlight_ass_4', 'cc_boob', 'cc_hightlight_boob',
        'highlight_2_leg_knee', 'fff1', 'fff2', 'fff93']


def parse_regions(path):
    """The AssetRipper-exported atlas text uses:
           cengceng.png / size:.. / filter:.. / pma:true
           <regionName>            <- a bare line, no colon
           bounds:x,y,w,h
           rotate:90               <- optional
    """
    txt = io.open(path, encoding='utf-8', errors='replace').read().splitlines()
    regions = {}
    cur = None
    for line in txt:
        s = line.strip()
        if not s:
            continue
        m = re.match(r'^([A-Za-z0-9_]+):(.*)$', s)
        if m:
            if cur is not None:
                regions[cur][m.group(1)] = m.group(2).strip()
            continue
        if ':' not in s:
            cur = s
            regions[cur] = {}
    return regions


def main():
    regs = parse_regions(ATLAS)
    print('regions in atlas: %d' % len(regs))
    img = Image.open(PNG).convert('RGBA')
    W, H = img.size
    print('atlas image: %s' % (img.size,))
    tiles = []
    for name in WANT:
        r = regs.get(name)
        if not r:
            print('  %-24s NOT IN ATLAS' % name)
            continue
        xy = [int(v) for v in r.get('bounds', '0,0,0,0').split(',')]
        size = [xy[2], xy[3]]
        rotate = r.get('rotate', 'false')
        x, y, w, h = xy[0], xy[1], size[0], size[1]
        # atlas coordinates are bottom-left origin
        box = (x, H - y - h, x + w, H - y)
        crop = img.crop(box)
        print('  %-24s xy=%s size=%s rotate=%s -> crop %s' % (name, xy, size, rotate, crop.size))
        tiles.append((name, crop))

    if not tiles:
        return
    cell = 260
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new('RGBA', (cols * cell, rows * (cell + 16)), (20, 20, 24, 255))
    from PIL import ImageDraw
    d = ImageDraw.Draw(canvas)
    for i, (name, crop) in enumerate(tiles):
        c = crop.copy()
        c.thumbnail((cell - 8, cell - 8), Image.LANCZOS)
        # composite on a mid-grey so alpha is visible
        bgc = Image.new('RGBA', c.size, (60, 60, 70, 255))
        bgc.alpha_composite(c)
        cx = (i % cols) * cell
        cy = (i // cols) * (cell + 16)
        canvas.paste(bgc.convert('RGB'), (cx + 4, cy + 16))
        d.text((cx + 4, cy + 2), name, fill=(255, 220, 120))
    canvas.convert('RGB').save(OUT)
    print('-> %s  %s' % (OUT, canvas.size))


if __name__ == '__main__':
    main()
