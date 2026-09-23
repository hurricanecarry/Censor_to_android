# -*- coding: utf-8 -*-
"""
Build the shader reference remap table and check property-name compatibility.

Mechanism being migrated:
    a material stores  m_Shader: {fileID: 4800000, guid: <dummy guid>, type: 3}
    and separately  m_SavedProperties  keyed by PROPERTY NAME.
Re-pointing the shader to the real one therefore only preserves the look if the
real shader declares the same property names.  The dummy shaders kept their
original Properties block, so this is directly checkable per pair -- which is what
this script does, instead of assuming the swap is safe.

Outputs
  shader_refmap.tsv          dummy guid -> real guid, with property diff summary
  shader_property_diff.tsv   per-pair list of missing / extra property names
"""

import io, os, re, csv, sys
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = r"<BUILD_DIR>\_cd"
EXP = r"<UNITY_PROJECT>"
PKG_ROOTS = [
    os.path.join(EXP, "Library", "PackageCache"),
    r"<UNITY_DIR>\UnityProject\CensorAndroidProbe\Library\PackageCache",
]
GUID_RE = re.compile(r"^guid:\s*([0-9a-f]{32})", re.M)
# a shader property line looks like:  _Name ("Label", Type) = default
PROP_RE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)*([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.M)


def guid_of(path):
    mp = path + ".meta"
    if not os.path.isfile(mp):
        return ""
    m = GUID_RE.search(io.open(mp, encoding="utf-8", errors="ignore").read(400))
    return m.group(1) if m else ""


def resolve_target(rel):
    """shader_mapping stores package paths relative to the PackageCache root."""
    rel = rel.replace("\\", os.sep).replace("/", os.sep)
    for root in PKG_ROOTS:
        cand = os.path.join(root, rel)
        if os.path.isfile(cand):
            return cand
    # project-relative fallback (TMP shaders live inside Assets/)
    cand = os.path.join(EXP, "Assets", rel)
    if os.path.isfile(cand):
        return cand
    return None


def props_of(path):
    """Property names declared in the shader's Properties block, plus the
    properties actually referenced in the code (uniform/TEXTURE2D/float etc.),
    because a shader can use properties it does not declare in the block."""
    try:
        txt = io.open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return set(), set()
    decl = set()
    m = re.search(r"\bProperties\s*\{(.*?)\n\s*\}", txt, re.S)
    if m:
        decl = set(PROP_RE.findall(m.group(1)))
    used = set(re.findall(r"\b_([A-Za-z][A-Za-z0-9_]*)\b", txt))
    used = {"_" + u for u in used}
    return decl, used


print("=== 1) load the P1 + restorable rows from shader_mapping.tsv ===")
rows = list(csv.DictReader(io.open(os.path.join(OUT, "shader_mapping.tsv"),
                                   encoding="utf-8"), delimiter="\t"))
todo = [r for r in rows if r["status"].startswith("RESTORE")]
print("  RESTORE rows in the whole table : %d" % len(todo))
print("  of which p1_needed == yes       : %d" % sum(1 for r in todo if r["p1_needed"] == "yes"))

print("\n=== 2) resolve every target shader ===")
out_rows = []
diff_rows = []
pairs = {}
unresolved = []
for r in todo:
    dummy = os.path.join(EXP, "Assets", r["dummy_path"].replace("\\", os.sep))
    if not os.path.isfile(dummy):
        unresolved.append((r["shader_name"], "dummy file missing: " + r["dummy_path"]))
        continue
    tgt = resolve_target(r["target_path"])
    if tgt is None:
        unresolved.append((r["shader_name"], "target not found: " + r["target_path"]))
        continue
    dg = r["dummy_guid"] or guid_of(dummy)
    tg = guid_of(tgt)
    if not tg:
        unresolved.append((r["shader_name"], "target has no .meta guid: " + tgt))
        continue
    ddecl, dused = props_of(dummy)
    tdecl, tused = props_of(tgt)
    # a material only needs the names it actually saved; those come from the
    # original shader's declarations, so compare declared-vs-declared and also
    # declared-vs-available (declared or code-referenced) in the target.
    missing = sorted(ddecl - tdecl)
    missing_hard = sorted(ddecl - (tdecl | tused))
    extra = sorted(tdecl - ddecl)
    out_rows.append({
        "shader_name": r["shader_name"],
        "family": r["family"],
        "p1_needed": r["p1_needed"],
        "dummy_path": r["dummy_path"],
        "dummy_guid": dg,
        "target_path": tgt.replace(EXP + os.sep, ""),
        "target_guid": tg,
        "dummy_props": len(ddecl),
        "target_props": len(tdecl),
        "missing_in_target": len(missing),
        "missing_not_even_used": len(missing_hard),
        "extra_in_target": len(extra),
        "status": ("COMPATIBLE" if not missing_hard else "PROPERTY_GAP"),
    })
    diff_rows.append({
        "shader_name": r["shader_name"],
        "dummy_guid": dg,
        "target_guid": tg,
        "missing_declared": " ".join(missing[:60]),
        "missing_and_unused": " ".join(missing_hard[:60]),
        "extra_in_target": " ".join(extra[:60]),
    })
    pairs[(dg, r["shader_name"])] = tg

print("  resolved pairs: %d   unresolved: %d" % (len(out_rows), len(unresolved)))
for n, why in unresolved[:10]:
    print("     UNRESOLVED %-50s %s" % (n, why))

print("\n=== 3) property compatibility summary ===")
compat = Counter()
for r in out_rows:
    compat[r["status"]] += 1
for k, v in compat.most_common():
    print("  %-18s %d" % (k, v))

gaps = [r for r in out_rows if r["status"] == "PROPERTY_GAP"]
if gaps:
    print("\n  pairs with properties the target shader neither declares nor uses:")
    for r in sorted(gaps, key=lambda r: -r["missing_not_even_used"]):
        print("    %-52s missing=%d" % (r["shader_name"], r["missing_not_even_used"]))

with io.open(os.path.join(OUT, "shader_refmap.tsv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()), delimiter="\t")
    w.writeheader()
    for r in out_rows:
        w.writerow(r)
with io.open(os.path.join(OUT, "shader_property_diff.tsv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(diff_rows[0].keys()), delimiter="\t")
    w.writeheader()
    for r in diff_rows:
        w.writerow(r)
print("\nwrote shader_refmap.tsv (%d rows) and shader_property_diff.tsv" % len(out_rows))

print("\n=== 4) distinct remap pairs (guid -> guid) ===")
uniq = {}
for r in out_rows:
    uniq.setdefault((r["dummy_guid"], r["target_guid"]), r)
print("  distinct (dummyGuid -> targetGuid) pairs: %d" % len(uniq))
print("  for %d dummy shader files and %d target files"
      % (len({r["dummy_guid"] for r in out_rows}), len({r["target_guid"] for r in out_rows})))

