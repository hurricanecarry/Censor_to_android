import io, os, csv, re, shutil, json

PROJ = r'<UNITY_PROJECT>'
LIST = r'<BUILD_DIR>\_probe\meshtype_fix_list.tsv'
BK   = r'<BUILD_DIR>\_probe\meshtype_fix_backup'
REPORT = r'<BUILD_DIR>\_probe\meshtype_fix_report.tsv'

rows = list(csv.DictReader(io.open(LIST, encoding='utf-8'), delimiter='\t'))
paths = []
seen = set()
for r in rows:
    p = r['path']
    if p in seen:
        continue
    seen.add(p)
    paths.append((p, r))
print('list rows %d -> unique textures %d' % (len(rows), len(paths)))

os.makedirs(BK, exist_ok=True)
changed = []
skipped = []
for rel, r in paths:
    meta = os.path.join(PROJ, rel.replace('/', os.sep)) + '.meta'
    if not os.path.exists(meta):
        skipped.append((rel, 'meta missing'))
        continue
    txt = io.open(meta, encoding='utf-8', errors='replace').read()
    sm = re.search(r'(?m)^\s+spriteMode: (\d+)', txt)
    mt = re.search(r'(?m)^(\s+spriteMeshType: )(\d+)', txt)
    if mt is None:
        skipped.append((rel, 'no spriteMeshType'))
        continue
    if sm is None or sm.group(1) != '1':
        skipped.append((rel, 'spriteMode=%s (not Single) - left alone' % (sm.group(1) if sm else '?')))
        continue
    if mt.group(2) == '0':
        skipped.append((rel, 'already FullRect'))
        continue
    # back up once, preserving the ORIGINAL content
    dst = os.path.join(BK, os.path.relpath(meta, PROJ).replace(os.sep, '__'))
    if not os.path.exists(dst):
        shutil.copy2(meta, dst)
    new = txt[:mt.start(2)] + '0' + txt[mt.end(2):]
    io.open(meta, 'w', encoding='utf-8', newline='').write(new)
    changed.append((rel, r['cover'], r['sprite']))

print('changed: %d   skipped: %d' % (len(changed), len(skipped)))
from collections import Counter
print('skip reasons:', dict(Counter(s[1].split(' - ')[0] for s in skipped)))
print()
print('--- first 12 changed ---')
for c in changed[:12]:
    print('   cover=%-7s %-24s %s' % (c[1], c[2][:24], c[0]))
with io.open(REPORT, 'w', encoding='utf-8', newline='') as fh:
    fh.write('path\tcover\tsprite\tresult\n')
    for c in changed:
        fh.write('%s\t%s\t%s\tchanged 1->0\n' % (c[0], c[1], c[2]))
    for s in skipped:
        fh.write('%s\t\t\tSKIPPED %s\n' % (s[0], s[1]))
print()
print('backup dir entries:', len(os.listdir(BK)))
print('report:', REPORT)
