import io, os, re, csv, json
from collections import defaultdict

ASSETS = r'<UNITY_PROJECT>\Assets'
IN = r'<BUILD_DIR>\_probe\confirmed_defect_list.tsv'
OUT = r'<BUILD_DIR>\_probe\confirmed_defect_list.tsv'
OUTJ = r'<BUILD_DIR>\_probe\confirmed_defect_list.json'

rows = list(csv.DictReader(io.open(IN, encoding='utf-8'), delimiter='\t'))
guids = {r['guid'] for r in rows}

# Parse YAML documents once per referencing file, mapping guid -> [GameObject name, component kind]
# Image = class 114, RawImage = 114 too (both MonoBehaviour). Use m_Sprite / m_Texture to tell them apart.
files = set()
for r in rows:
    for tok in r['refs'].split(' | '):
        if tok:
            files.add(tok.split('#')[0])
print('referencing files: %d' % len(files))

doc_re = re.compile(r'--- !u!(\d+) &(\d+)(.*?)(?=\n--- !u!|\Z)', re.S)
go_re = re.compile(r'm_GameObject: \{fileID: (\d+)\}')
name_re = re.compile(r'\n  m_Name: (.*)')

guidref = defaultdict(list)
for rel in sorted(files):
    p = os.path.join(ASSETS, rel)
    try:
        txt = io.open(p, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    gos = {}
    for cls, fid, body in doc_re.findall(txt):
        if cls == '1':
            nm = name_re.search(body)
            gos[fid] = nm.group(1).strip() if nm else '?'
    for cls, fid, body in doc_re.findall(txt):
        if cls != '114':
            continue
        # An Image/RawImage uses m_Sprite / m_Texture.  TalkPanelUI stores its portrait in a
        # plain Sprite field named 'avater' inside an AvaterSprite struct, so that pattern
        # must be matched too or the dialogue portrait never resolves.
        sp = re.search(r'\b(?:m_Sprite|avater|sprite): \{fileID: -?\d+, guid: ([0-9a-f]{32})', body)
        tx = re.search(r'm_Texture: \{fileID: -?\d+, guid: ([0-9a-f]{32})', body)
        g = sp.group(1) if sp else (tx.group(1) if tx else None)
        if g is None or g not in guids:
            continue
        gm = go_re.search(body)
        go = gos.get(gm.group(1), '?') if gm else '?'
        if tx and not sp:
            kind, field = 'RawImage', 'm_Texture'
        elif re.search(r'm_Sprite: \{fileID: -?\d+, guid: ' + g, body):
            kind, field = 'Image', 'm_Sprite'
        else:
            kind, field = 'MonoBehaviour', 'AvaterSprite.avater'
        guidref[g].append((rel, go, kind, field))

print('GUIDs resolved to a GameObject + field: %d / %d' % (len(guidref), len(guids)))
for r in rows:
    hits = guidref.get(r['guid'], [])
    if not hits:
        continue
    r['refCount'] = str(len(hits))
    r['refs'] = ' | '.join('%s :: %s :: %s.%s' % (a, b, c, d) for a, b, c, d in hits[:6])

cols = list(rows[0].keys())
with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=cols, delimiter='\t')
    w.writeheader()
    for r in rows:
        w.writerow(r)
with io.open(OUTJ, 'w', encoding='utf-8') as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)

WANT = ('apartmentmanager', 'idol', 'player', 'censorbtnoff', 'censorbtnon',
        'setting_off', 'setting_on', 'censor_work_begin_btn_off', 'markdark')
print()
print('=== field-level identities ===')
for r in rows:
    if r['sprite'] in WANT or r['texture'] in WANT:
        print('  %-26s %-22s %s' % (r['texture'][:26], r['sprite'][:22], r['refs'][:230]))
print()
print('wrote', OUT)
