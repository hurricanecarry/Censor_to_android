import sys, os, glob
from collections import Counter
sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

DIRS = [
    r'<ORIGINAL_BUILD>\TC_Data\StreamingAssets\dynamic_assets\RootPackage',
]
files = []
for d in DIRS:
    files += sorted(glob.glob(os.path.join(d, '*.bundle')))
print('original bundles: %d' % len(files))

raw = Counter()
mesh = Counter()
pack = Counter()
n = 0
eq = 0
ne = 0
for b in files:
    try:
        env = UnityPy.load(b)
    except Exception as e:
        print('  LOAD FAIL %s : %s' % (os.path.basename(b), e))
        continue
    for o in env.objects:
        if o.type.name != 'Sprite':
            continue
        try:
            d = o.read()
            rd = d.m_RD
            s = int(rd.settingsRaw)
        except Exception:
            continue
        n += 1
        raw[s] += 1
        mesh[(s >> 4) & 1] += 1          # bit 4
        pack[s & 3] += 1                 # bits 0-1
        r = d.m_Rect
        tr = rd.textureRect
        if (abs(r.width - tr.width) < 1 and abs(r.height - tr.height) < 1
                and abs(r.x - tr.x) < 1 and abs(r.y - tr.y) < 1):
            eq += 1
        else:
            ne += 1

print('sprites: %d' % n)
print()
print('settingsRaw value histogram:', dict(raw.most_common(8)))
print('bit 4 (meshType 0=FullRect 1=Tight):', dict(mesh))
print('bits 0-1 (packingMode):', dict(pack))
print()
print('m_Rect == textureRect : %d' % eq)
print('m_Rect != textureRect : %d' % ne)
