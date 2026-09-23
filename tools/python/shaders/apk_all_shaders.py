"""apk_all_shaders.py

The Android player data stores most assets as GUID-named serialized files directly under
assets/bin/Data/ (next to the .split chunks).  An earlier version only scanned the named files, so its
"26 shaders missing" result was not trustworthy. This scans EVERY data file in the APK
(splits reassembled, GUID-named files read in place) and lists every Shader name found.

ASCII-only output.
"""

import os, sys, zipfile, glob, collections

sys.path.insert(0, r'<PY_DEPS>')  # UnityPy 等第三方解码库目录
import UnityPy

APK = r'<BUILD_DIR>\_probe\CensorPort_P1_b67.apk'
TMP = r'<BUILD_DIR>\_cd\_apk_data'
OUT = r'<BUILD_DIR>\_cd\apk_shaders_full.tsv'


def names_from_file(path):
  out = []
  try:
    env = UnityPy.load(path)
  except Exception:
    return out
  for o in env.objects:
    if o.type.name != 'Shader':
      continue
    try:
      t = o.read_typetree()
    except Exception:
      out.append('<unreadable>')
      continue
    pf = t.get('m_ParsedForm') or {}
    out.append(pf.get('m_Name') or t.get('m_Name') or '<noname>')
  return out


def main():
  os.makedirs(TMP, exist_ok=True)
  z = zipfile.ZipFile(APK)
  entries = [n for n in z.namelist() if n.startswith('assets/bin/Data/')]
  splits = collections.defaultdict(list)
  plain = []
  for n in entries:
    base = os.path.basename(n)
    if '.split' in base:
      splits[base.split('.split')[0]].append(n)
    elif base.endswith('.resource') or base.endswith('.resS'):
      continue
    else:
      plain.append(n)

  found = collections.Counter()
  files_with = 0

  for stem, members in sorted(splits.items()):
    members.sort(key=lambda m: int(m.rsplit('.split', 1)[1]))
    out = os.path.join(TMP, stem)
    with open(out, 'wb') as fh:
      for m in members:
        fh.write(z.read(m))
    got = names_from_file(out)
    if got:
      files_with += 1
      print(' %-28s %d shaders' % (stem, len(got)))
    found.update(got)

  print('scanning %d single-asset files ...' % len(plain))
  for i, n in enumerate(plain):
    p = os.path.join(TMP, 'one.bin')
    with open(p, 'wb') as fh:
      fh.write(z.read(n))
    got = names_from_file(p)
    if got:
      files_with += 1
      print(' %-40s %s' % (os.path.basename(n), ', '.join(got[:6])))
    found.update(got)

  print()
  print('APK shader names: %d distinct, in %d files' % (len(found), files_with))
  for n in sorted(found):
    print('  %-58s x%d' % (n, found[n]))
  with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('shader\tcount\n')
    for n in sorted(found):
      fh.write('%s\t%d\n' % (n, found[n]))
  print('-> %s' % OUT)


if __name__ == '__main__':
  main()
