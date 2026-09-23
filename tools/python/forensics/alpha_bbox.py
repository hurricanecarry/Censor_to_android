import sys, os, numpy as np
from PIL import Image
sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

OURS_PNG = r'<UNITY_PROJECT>\Assets\AssetBundles\rootpackage_assets_art_uipanels_talkpanel\Texture2D\apartmentmanager.png'
ORIG_BUNDLE = r'<ORIGINAL_BUILD>\TC_Data\StreamingAssets\dynamic_assets\RootPackage\7c173a16aaa77d77e50c23f32972240f.bundle'

def bbox(a, thr):
    m = a > thr
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)

def show(tag, arr):
    print('%s  size=%s' % (tag, arr.shape))
    for thr in (0, 8, 64, 128, 250):
        b = bbox(arr, thr)
        if b is None:
            print('   alpha>%-4d : (empty)' % thr); continue
        x0, y0, x1, y1 = b
        print('   alpha>%-4d : x %4d..%4d (w %4d)   y_top %4d..%4d (h %4d)' % (
            thr, x0, x1, x1 - x0, y0, y1, y1 - y0))

A = np.asarray(Image.open(OURS_PNG).convert('RGBA'))[:, :, 3]
print('=== our exported PNG (PIL row 0 = TOP) ===')
show('ours', A)

env = UnityPy.load(ORIG_BUNDLE)
found = False
for o in env.objects:
    if o.type.name != 'Texture2D':
        continue
    d = o.read()
    if d.m_Name != 'apartmentmanager':
        continue
    img = d.image
    B = np.asarray(img.convert('RGBA'))[:, :, 3]
    print()
    print('=== original bundle Texture2D apartmentmanager (UnityPy row 0 = ? ) ===')
    show('orig', B)
    found = True
    print()
    print('shape equal:', A.shape == B.shape)
    if A.shape == B.shape:
        diff = (A.astype(np.int16) - B.astype(np.int16))
        nz = np.abs(diff) > 0
        print('alpha differing pixels: %d (%.4f%%)' % (int(nz.sum()), 100.0 * nz.sum() / A.size))
        if nz.any():
            ys, xs = np.nonzero(nz)
            print('  diff bbox: x %d..%d  y %d..%d' % (xs.min(), xs.max(), ys.min(), ys.max()))
        # also compare flipped
        Bf = B[::-1, :]
        nzf = (np.abs(A.astype(np.int16) - Bf.astype(np.int16)) > 0)
        print('alpha differing pixels (ours vs FLIPPED orig): %d (%.4f%%)' % (
            int(nzf.sum()), 100.0 * nzf.sum() / A.size))
    break
if not found:
    print('apartmentmanager Texture2D not found in bundle')
