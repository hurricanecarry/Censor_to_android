"""texture_pixel_diff.py

The sRGB question, decided by pixel data instead of by the flag.

Our project's imported cengceng PNG and the ORIGINAL Windows build's stored cengceng
texture are compared pixel by pixel.  Both the original and our export carry
m_ColorSpace = 0 (non-sRGB), so the serialized flag matches; the only way the editor A/B
(where sRGB=1 removed the mottling) can be a real improvement is if the PNG that
AssetRipper wrote holds different pixel values than the original texture - i.e. the sRGB
flag is compensating for a data-level export artefact.

Tests, in order of what they would mean:
    ours      == orig                -> the flag change is a pure deviation from the original
    ours      == srgb_to_linear(orig) -> AssetRipper encoded a decode step into the PNG,
                                        so sRGBTexture=1 is a legitimate compensation
    srgb_to_linear(ours) == orig      -> the opposite encode
ASCII-only output.
"""

import os, sys, glob
import numpy as np
from PIL import Image

sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

ORIG = r'<ORIGINAL_BUILD>\TC_Data\StreamingAssets\dynamic_assets\RootPackage'
OURS = r'<UNITY_PROJECT>\Assets\AssetBundles\rootpackage_assets_art_uipanels_wallpaparpanelui\Texture2D\cengceng.png'
OUTDIR = r'<BUILD_DIR>\_cd'


def srgb_to_linear(a):
    a = a.astype(np.float64) / 255.0
    out = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def linear_to_srgb(a):
    a = a.astype(np.float64) / 255.0
    out = np.where(a <= 0.0031308, a * 12.92, 1.055 * (a ** (1.0 / 2.4)) - 0.055)
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def first_orig_cengceng():
    for b in sorted(glob.glob(os.path.join(ORIG, '*.bundle'))):
        try:
            env = UnityPy.load(b)
        except Exception:
            continue
        for o in env.objects:
            if o.type.name != 'Texture2D':
                continue
            t = o.read_typetree()
            if (t.get('m_Name') or '') != 'cengceng':
                continue
            img = o.read().image
            print('original cengceng from %s : %s %s mode=%s' % (
                os.path.basename(b), img.size, t.get('m_ColorSpace'), img.mode))
            return img.convert('RGBA'), os.path.basename(b)
    raise SystemExit('original cengceng not found')


def stats(label, a, b):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    if d.ndim == 3:
        d = d.max(axis=2)
    n = d.size
    pct = 100.0 * (d > 0).sum() / n
    print('  %-34s differing=%6.3f%%  mean=%6.3f  max=%d  p99=%d'
          % (label, pct, d.mean(), d.max(), int(np.percentile(d, 99))))
    return pct


def main():
    orig, bundle = first_orig_cengceng()
    ours = Image.open(OURS).convert('RGBA')
    print('our png: %s mode=%s' % (ours.size, ours.mode))

    orig.save(os.path.join(OUTDIR, 'orig_cengceng_from_bundle.png'))
    ours.save(os.path.join(OUTDIR, 'ours_cengceng_png.png'))

    A = np.array(orig)
    B = np.array(ours)
    print('shape orig=%s ours=%s  identical bytes=%s' % (A.shape, B.shape, np.array_equal(A, B)))
    print('mean per channel orig=%s ours=%s' % (A.reshape(-1, 4).mean(0).round(3),
                                                B.reshape(-1, 4).mean(0).round(3)))
    print()
    print('=== pixel comparisons (max channel difference) ===')
    stats('ours vs orig', B, A)
    stats('ours vs srgb_to_linear(orig)', B, srgb_to_linear(A))
    stats('srgb_to_linear(ours) vs orig', srgb_to_linear(B), A)
    stats('ours vs linear_to_srgb(orig)', B, linear_to_srgb(A))
    stats('linear_to_srgb(ours) vs orig', linear_to_srgb(B), A)
    print()
    print('=== sample pixels (x=1024, the middle column) ===')
    for y in (256, 512, 768, 1024):
        print('   y=%-5d orig=%s ours=%s  srgb2lin(orig)=%s'
              % (y, A[y, 1024], B[y, 1024], srgb_to_linear(A[y:y + 1, 1024:1025])[0, 0]))
    print()
    print('=== saved: %s / %s ===' % (os.path.join(OUTDIR, 'orig_cengceng_from_bundle.png'),
                                      os.path.join(OUTDIR, 'ours_cengceng_png.png')))


if __name__ == '__main__':
    main()
