"""audit_by_container.py

Correct version of the post-rebuild audit.  An earlier version matched by texture NAME, but names such as "1"
or "chanhuishi" occur in several bundles, so before/after lists got mixed up.

This one matches by the AssetBundle container path (env.container: asset path -> object), which
identifies the exact asset, and compares

 BEFORE = the same asset path inside CensorPort_P1_b69.apk
 AFTER = the rebuilt Assets/StreamingAssets/dynamic_assets/RootPackage bundles

reporting per asset: transparent-pixel RGB count (must become 0) and the built texture
properties (must be unchanged).

ASCII-only output; writes _cd/r23_audit_container.json
"""

import os, sys, io, json, zipfile

sys.path.insert(0, r'<PY_DEPS>')  # UnityPy 等第三方解码库目录
import UnityPy

PROJ = r'<UNITY_PROJECT>'
REBUILT = os.path.join(PROJ, 'Assets', 'StreamingAssets', 'dynamic_assets', 'RootPackage')
APK = r'<BUILD_DIR>\_probe\CensorPort_P1_b69.apk'
REMAINING = r'<BUILD_DIR>\_cd\r23_remaining.json'
TMP = r'<BUILD_DIR>\_cd\_audit_tmp2'
OUT = r'<BUILD_DIR>\_cd\r23_audit_container.json'


def norm(p):
  # the AssetBundle container stores asset paths in lower case
  return p.split('#')[0].replace('\\', '/').strip().lower()


def props(t):
  ts = t.get('m_TextureSettings') or {}
  return (t.get('m_Width'), t.get('m_Height'), t.get('m_TextureFormat'), t.get('m_MipCount'),
      ts.get('m_FilterMode'), ts.get('m_WrapU'), ts.get('m_WrapV'), ts.get('m_Aniso'))


def collect(bundle_paths, want, with_pixels=True):
  out = {}
  for label, path in bundle_paths:
    try:
      env = UnityPy.load(path)
    except Exception:
      continue
    try:
      container = env.container
    except Exception:
      continue
    for cpath, obj in container.items():
      key = norm(cpath)
      if key not in want:
        continue
      if obj.type.name != 'Texture2D':
        continue
      try:
        t = obj.read_typetree()
      except Exception:
        continue
      rec = {'source': label, 'props': props(t)}
      if with_pixels:
        try:
          px = list(obj.read().image.convert('RGBA').getdata())
          rec['zero_alpha'] = sum(1 for r, g, b, a in px if a == 0)
          rec['zero_alpha_nonzero_rgb'] = sum(1 for r, g, b, a in px if a == 0 and (r or g or b))
        except Exception as e:
          rec['pixel_error'] = str(e)
      out.setdefault(key, []).append(rec)
  return out


def main():
  rem = json.load(io.open(REMAINING, encoding='utf-8'))
  want = set(norm(r['texture']) for r in rem)
  print('affected asset paths: %d' % len(want))

  print('scanning rebuilt bundles ...')
  after = collect([('rebuilt', os.path.join(REBUILT, f))
           for f in sorted(os.listdir(REBUILT)) if f.endswith('.bundle')], want)

  os.makedirs(TMP, exist_ok=True)
  z = zipfile.ZipFile(APK)
  members = [n for n in z.namelist()
        if n.startswith('assets/dynamic_assets/RootPackage/') and n.endswith('.bundle')]
  paths = []
  for i, n in enumerate(members):
    p = os.path.join(TMP, 'a%03d.bundle' % i)
    with open(p, 'wb') as fh:
      fh.write(z.read(n))
    paths.append(('b69', p))
  print('scanning %d bundles from b69.apk ...' % len(paths))
  before = collect(paths, want)

  fixed = 0
  problems = []
  rows = []
  for k in sorted(want):
    a = after.get(k)
    b = before.get(k)
    if not a:
      problems.append(('not found in rebuilt bundles', k))
      continue
    if not b:
      problems.append(('not found in b69', k))
      continue
    za_after = max((x.get('zero_alpha_nonzero_rgb', 0) for x in a), default=None)
    za_before = max((x.get('zero_alpha_nonzero_rgb', 0) for x in b), default=None)
    same_props = a[0]['props'] == b[0]['props']
    rows.append({'path': k, 'before_zan': za_before, 'after_zan': za_after,
           'props_same': same_props, 'before_props': b[0]['props'], 'after_props': a[0]['props']})
    if za_after not in (0, None):
      problems.append(('RGB still present in transparent pixels: %s -> %s' % (za_before, za_after), k))
    else:
      fixed += 1
    if not same_props:
      problems.append(('properties changed: %s -> %s' % (b[0]['props'], a[0]['props']), k))

  print()
  print('assets fixed (transparent RGB now 0): %d / %d' % (fixed, len(want)))
  print('problems: %d' % len(problems))
  for x in problems[:20]:
    print('  %s :: %s' % (x[0], x[1]))
  print()
  print('largest before->after drops:')
  for r in sorted(rows, key=lambda r: -(r['before_zan'] or 0))[:12]:
    print('  %-70s %8s -> %-8s propsSame=%s' % (os.path.basename(r['path']), r['before_zan'], r['after_zan'], r['props_same']))

  json.dump({'affected': len(want), 'fixed': fixed, 'problems': [list(x) for x in problems], 'rows': rows},
       io.open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
  print('-> %s' % OUT)


if __name__ == '__main__':
  main()
