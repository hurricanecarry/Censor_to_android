"""bundles_audit.py

Post-rebuild verification for the 117 PMA atlases, done on the BUILD OUTPUT and on the
previous shipped APK so the check is empirical rather than a YAML key diff:

  BEFORE = the same textures inside CensorPort_P1_b69.apk (alphaIsTransparency was still 1 there)
  AFTER  = the freshly rebuilt Assets/StreamingAssets/dynamic_assets/RootPackage bundles

For every affected texture name:
  * count pixels with alpha == 0 and RGB != 0   -> must drop to 0
  * compare width/height/format/mipCount/filterMode/wrapMode/aniso -> must be unchanged,
    i.e. the fix changed ONLY the transparent-pixel RGB

ASCII-only output; writes _cd/r23_bundle_audit.json
"""

import os, sys, io, json, zipfile, collections

sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

PROJ = r'<UNITY_PROJECT>'
REBUILT = os.path.join(PROJ, 'Assets', 'StreamingAssets', 'dynamic_assets', 'RootPackage')
APK = r'<BUILD_DIR>\_probe\CensorPort_P1_b69.apk'
REMAINING = r'<BUILD_DIR>\_cd\r23_remaining.json'
TMP = r'<BUILD_DIR>\_cd\_audit_bundle_tmp'
OUT = r'<BUILD_DIR>\_cd\r23_bundle_audit.json'


def props(t):
    ts = t.get('m_TextureSettings') or {}
    return (t.get('m_Width'), t.get('m_Height'), t.get('m_TextureFormat'), t.get('m_MipCount'),
            ts.get('m_FilterMode'), ts.get('m_WrapU'), ts.get('m_WrapV'), ts.get('m_Aniso'))


def scan(path_iter, names, want_pixels):
    res = {}
    for label, path in path_iter:
        try:
            env = UnityPy.load(path)
        except Exception:
            continue
        for o in env.objects:
            if o.type.name != 'Texture2D':
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue
            nm = t.get('m_Name') or ''
            if nm not in names:
                continue
            key = nm
            rec = res.setdefault(key, [])
            entry = {'source': label, 'props': props(t)}
            if want_pixels:
                try:
                    img = o.read().image
                    px = list(img.convert('RGBA').getdata())
                    za = sum(1 for r, g, b, a in px if a == 0)
                    zan = sum(1 for r, g, b, a in px if a == 0 and (r or g or b))
                    entry['zero_alpha'] = za
                    entry['zero_alpha_nonzero_rgb'] = zan
                except Exception as e:
                    entry['pixel_error'] = str(e)
            rec.append(entry)
    return res


def main():
    rem = json.load(io.open(REMAINING, encoding='utf-8'))
    names = set(os.path.basename(r['texture'])[:-len('.png')] for r in rem)
    print('affected texture names: %d' % len(names))

    print('scanning rebuilt bundles ...')
    after = scan((('rebuilt:' + os.path.basename(p), os.path.join(REBUILT, p))
                  for p in sorted(os.listdir(REBUILT)) if p.endswith('.bundle')), names, True)

    os.makedirs(TMP, exist_ok=True)
    z = zipfile.ZipFile(APK)
    apk_members = [n for n in z.namelist() if n.startswith('assets/dynamic_assets/RootPackage/') and n.endswith('.bundle')]
    paths = []
    for i, n in enumerate(apk_members):
        p = os.path.join(TMP, 'a%03d.bundle' % i)
        with open(p, 'wb') as fh:
            fh.write(z.read(n))
        paths.append(('b69:' + os.path.basename(n), p))
    print('scanning %d bundles from b69.apk ...' % len(paths))
    before = scan(iter(paths), names, True)

    problems = []
    fixed = 0
    for name in sorted(names):
        a = after.get(name, [])
        b = before.get(name, [])
        if not a:
            problems.append(('texture not found in rebuilt bundles', name))
            continue
        if not b:
            problems.append(('texture not found in b69 apk', name))
            continue
        za_after = [x.get('zero_alpha_nonzero_rgb') for x in a if 'zero_alpha_nonzero_rgb' in x]
        za_before = [x.get('zero_alpha_nonzero_rgb') for x in b if 'zero_alpha_nonzero_rgb' in x]
        if not za_after or max(za_after) != 0:
            problems.append(('still has RGB in transparent pixels: after=%s before=%s' % (za_after, za_before), name))
        else:
            fixed += 1
        # property comparison (use the first occurrence of each side, sorted for stability)
        pa = sorted(a[0]['props'], key=str)
        pbn = sorted(b[0]['props'], key=str)
        if pa != pbn:
            problems.append(('built texture properties changed: before=%s after=%s' % (b[0]['props'], a[0]['props']), name))

    print()
    print('textures verified as fixed : %d / %d' % (fixed, len(names)))
    print('problems                   : %d' % len(problems))
    for x in problems[:15]:
        print('   %s :: %s' % (x[0], x[1]))

    json.dump({'affected': len(names), 'fixed': fixed, 'problems': [list(x) for x in problems],
               'after_sample': {k: v for k, v in list(after.items())[:3]},
               'before_sample': {k: v for k, v in list(before.items())[:3]}},
              io.open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('-> %s' % OUT)


if __name__ == '__main__':
    main()
