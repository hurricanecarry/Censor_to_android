import os, numpy as np
from PIL import Image

AB = r'<BUILD_DIR>\_probe\ab'
WIN = r'<EVIDENCE_DIR>\ref\windows_reference.png'
WINPATH = r'<EVIDENCE_DIR>\ref\windows_dialog_reference.png'

g1 = np.asarray(Image.open(os.path.join(AB, 'G1_shot.png')).convert('RGB')).astype(np.int16)
g2 = np.asarray(Image.open(os.path.join(AB, 'G2_shot.png')).convert('RGB')).astype(np.int16)
ph = np.asarray(Image.open(r'<EVIDENCE_DIR>\ref\phone_dialog.png').convert('RGB')).astype(np.int16)

def region_diff(a, b, box, tag):
    x0, y0, x1, y1 = box
    A = a[y0:y1, x0:x1]; B = b[y0:y1, x0:x1]
    d = np.abs(A - B).max(axis=2)
    n = int((d > 24).sum())
    print('  %-46s px=%d (%.3f%%)  meanAbs=%.2f' % (tag, n, 100.0 * n / d.size, np.abs(A - B).mean()))
    if n:
        ys, xs = np.nonzero(d > 24)
        print('        diff bbox (screen) x %d..%d  y %d..%d' % (x0 + xs.min(), x0 + xs.max(), y0 + ys.min(), y0 + ys.max()))

# portrait occupies screen x 812..1489, y 34..720 (from the on-device chain dump)
print('=== G1 (spritefix ON / FullRect) vs G2 (spritefix OFF / Tight) ===')
region_diff(g1, g2, (812, 34, 1489, 720), 'portrait region only')
region_diff(g1, g2, (183, 0, 1463, 720), 'whole game viewport')
region_diff(g1, g2, (812, 34, 1180, 460), 'portrait UPPER-LEFT quadrant')

print()
print('=== PHONE 17:19 vs G2 (both should be the pre-fix Tight state) ===')
region_diff(ph, g2, (812, 34, 1489, 720), 'portrait region only')

# where exactly do G1 and G2 differ inside the portrait?
A = g1[34:720, 812:1489]; B = g2[34:720, 812:1489]
d = np.abs(A - B).max(axis=2)
m = d > 24
print()
print('  G1 vs G2 portrait mismatch density (cell %% of 40x40), 17 cols x 17 rows')
H, W = m.shape
for j in range(17):
    y0, y1 = j * H // 17, (j + 1) * H // 17
    row = ''
    for i in range(17):
        x0, x1 = i * W // 17, (i + 1) * W // 17
        row += '%4d' % int(round(100.0 * m[y0:y1, x0:x1].mean()))
    print('   %s' % row)
