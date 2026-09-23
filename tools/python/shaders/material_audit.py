# -*- coding: utf-8 -*-
"""Project-wide material audit after the shader reference migration."""

import io, os, re, csv, sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXP = r"<UNITY_PROJECT>"
OUT = r"<BUILD_DIR>\_cd"
GUID_RE = re.compile(r"^guid:\s*([0-9a-f]{32})", re.M)
SH = re.compile(r"m_Shader:\s*\{fileID:\s*(-?\d+),\s*guid:\s*([0-9a-f]{32}),\s*type:\s*(\d+)\}")

print("=== index shader guids: real vs dummy ===")
shader_kind = {}
for dp, dn, fn in os.walk(os.path.join(EXP, "Assets")):
    for x in fn:
        if not x.endswith(".shader"):
            continue
        p = os.path.join(dp, x)
        g = ""
        mp = p + ".meta"
        if os.path.isfile(mp):
            m = GUID_RE.search(io.open(mp, encoding="utf-8", errors="ignore").read(400))
            if m:
                g = m.group(1)
        if not g:
            continue
        txt = io.open(p, encoding="utf-8", errors="ignore").read()
        shader_kind[g] = ("dummy" if "DummyShaderTextExporter" in txt else "real",
                          os.path.relpath(p, EXP))
print("  in-project shaders: %d" % len(shader_kind))
for k, v in Counter(v[0] for v in shader_kind.values()).most_common():
    print("     %-8s %d" % (k, v))

print("\n=== material audit ===")
refmap = {}
with io.open(os.path.join(OUT, "shader_refmap.tsv"), encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        refmap[r["dummy_guid"]] = r["target_guid"]

kindcount = Counter()
unresolved = defaultdict(int)
perfile = []
for dp, dn, fn in os.walk(os.path.join(EXP, "Assets")):
    for x in fn:
        if not x.endswith(".mat"):
            continue
        p = os.path.join(dp, x)
        txt = io.open(p, encoding="utf-8", errors="ignore").read()
        m = SH.search(txt)
        rel = os.path.relpath(p, EXP)
        if not m:
            kindcount["NO_SHADER_FIELD"] += 1
            perfile.append((rel, "NO_SHADER_FIELD", ""))
            continue
        g = m.group(2)
        k = shader_kind.get(g)
        if k:
            kindcount["REAL" if k[0] == "real" else "DUMMY"] += 1
            perfile.append((rel, k[0].upper(), k[1]))
        else:
            kindcount["GUID_NOT_IN_PROJECT"] += 1
            unresolved[g] += 1
            perfile.append((rel, "GUID_NOT_IN_PROJECT", g))

for k, v in kindcount.most_common():
    print("  %-22s %d" % (k, v))
if unresolved:
    print("  unresolved shader guids:")
    for g, n in sorted(unresolved.items(), key=lambda kv: -kv[1])[:10]:
        print("     %s x%d" % (g, n))
else:
    print("  unresolved shader guids: none")

with io.open(os.path.join(OUT, "material_audit.tsv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["materialPath", "shaderKind", "shaderPathOrGuid"])
    for row in perfile:
        w.writerow(row)
print("\nwrote material_audit.tsv (%d materials)" % len(perfile))

print("\n=== materials still on a DUMMY shader (these are the remaining blockers) ===")
dum = [(a, c) for a, b, c in perfile if b == "DUMMY"]
byname = Counter()
for a, c in dum:
    byname[c] += 1
for k, v in byname.most_common(20):
    print("   x%-4d %s" % (v, k))
print("   total materials on dummy shaders: %d" % len(dum))
