"""verify_apk_texels.py

Independent end-to-end check, run against the SHIPPED APK (not the build folder):

for every bundle inside assets/dynamic_assets/RootPackage of the APK, find the Texture2D named
`cengceng` and count pixels where alpha == 0 but RGB != 0.  Those are the pixels Unity's
TextureImporter.alphaIsTransparency dilation fills in; PMA blending reads RGB even at alpha 0, so
they are exactly what drew the coloured blocky fragments.

Expected after the fix: zero_alpha_nonzero_rgb == 0.
ASCII-only output.
"""

import os, sys, zipfile, collections

sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

TMP = r'<BUILD_DIR>\_cd\_apk_bundle_tmp'


def check(apk, want_name='cengceng'):
    os.makedirs(TMP, exist_ok=True)
    z = zipfile.ZipFile(apk)
    bundles = [n for n in z.namelist() if n.startswith('assets/dynamic_assets/RootPackage/') and n.endswith('.bundle')]
    print('%s : %d bundles in the APK' % (os.path.basename(apk), len(bundles)))
    hits = 0
    for n in bundles:
        p = os.path.join(TMP, 'b.bundle')
        with open(p, 'wb') as fh:
            fh.write(z.read(n))
        try:
            env = UnityPy.load(p)
        except Exception:
            continue
        for o in env.objects:
            if o.type.name != 'Texture2D':
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue
            if (t.get('m_Name') or '') != want_name:
                continue
            try:
                img = o.read().image
            except Exception as e:
                print('   %s : image read failed %s' % (os.path.basename(n), e))
                continue
            px = img.convert('RGBA').getdata()
            zero_a = 0
            zero_a_nonzero_rgb = 0
            for r, g, b, a in px:
                if a == 0:
                    zero_a += 1
                    if r or g or b:
                        zero_a_nonzero_rgb += 1
            print('   %-46s size=%s  zeroAlpha=%d  zeroAlpha_nonZeroRGB=%d'
                  % (os.path.basename(n), img.size, zero_a, zero_a_nonzero_rgb))
            hits += 1
            break
    if hits == 0:
        print('   no %s Texture2D found' % want_name)
    print()


if __name__ == '__main__':
    check(r'<BUILD_DIR>\_probe\CensorPort_P1_b69.apk')
    check(r'<BUILD_DIR>\_probe\CensorPort_P1_b67.apk')
