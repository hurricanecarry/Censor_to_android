# -*- coding: utf-8 -*-
"""
C/D-2 precise identity mapping.

Fixes the two defects found in script_identity_audit.py:
  (1) it treated "guid present in a .meta" as proof of resolution.  It never
      resolved the MonoScript to a System.Type.  Here every reference is joined
      to a Unity-resolved (guid, fileID) -> System.Type table.
  (2) it aggregated every fileID of one assembly into a single row, so 96 URP
      Core references collapsed into "Volume".  Here the unit is ONE
      (guid, fileID) pair == ONE distinct script identity == ONE type.

Inputs (produced by Unity via Assets/Editor/IdentityDump.cs):
  identity_source_dll.tsv  : source project that contains ONLY the game DLLs
  identity_target_pkg.tsv  : the probe project, which has the real UPM packages

Outputs:
  script_identity_pairs.tsv : old identity -> new identity, one row per pair
  dependency_providers.tsv  : assembly-level keep/replace decision + evidence
  meta_guid_conflicts.tsv   : duplicate GUIDs (never silently collapsed)
"""

import io, os, re, csv
from collections import Counter, defaultdict

ROOT = r"<UNITY_PROJECT>"
OUT = r"<BUILD_DIR>\_cd"
PACKAGE_JSON_ROOTS = [
    r"<UNITY_EDITOR>\2022.3.62f3c1\Editor\Data\Resources\PackageManager\BuiltInPackages",
    os.path.join(ROOT, "Packages"),
    r"<UNITY_DIR>\UnityProject\CensorAndroidProbe\Packages",
    r"<UNITY_DIR>\UnityProject\CensorAndroidProbe\Library\PackageCache",
]
ASSET_EXT = (".prefab", ".unity", ".asset")
REF_RE = re.compile(r"m_Script:\s*\{fileID:\s*(-?\d+),\s*guid:\s*([0-9a-f]{32}),\s*type:\s*3\}")
GUID_RE = re.compile(r"^guid:\s*([0-9a-f]{32})", re.M)
LOCALID_RE = re.compile(r"^\s*mainObjectFileID:\s*(-?\d+)", re.M)


def load_identity(path):
    """(guid, fileID) -> row ; and type -> [rows] for the reverse join."""
    by_pair, by_type = {}, defaultdict(list)
    if not os.path.exists(path):
        print("  MISSING: " + path)
        return by_pair, by_type
    with io.open(path, encoding="utf-8", errors="ignore") as f:
        rdr = csv.DictReader(f, delimiter="\t")
        for r in rdr:
            try:
                fid = int(r["localFileID"])
            except Exception:
                continue
            g = r["guid"].strip()
            if len(g) != 32:
                continue
            by_pair[(g, fid)] = r
            t = (r.get("fullTypeName") or "").strip()
            if t:
                by_type[t].append(r)
    return by_pair, by_type


print("=== 1) load Unity-resolved identity tables ===")
src_pair, src_type = load_identity(os.path.join(OUT, "identity_source_dll.tsv"))
tgt_pair, tgt_type = load_identity(os.path.join(OUT, "identity_target_pkg.tsv"))
print("  source (game DLLs)      : %d pairs / %d types" % (len(src_pair), len(src_type)))
print("  target (UPM packages)   : %d pairs / %d types" % (len(tgt_pair), len(tgt_type)))

# ---------------------------------------------------------------- package deps
print("\n=== 2) package dependency evidence (real package.json) ===")
pkg_meta = {}
for root in PACKAGE_JSON_ROOTS:
    if not os.path.isdir(root):
        continue
    for d in os.listdir(root):
        pj = os.path.join(root, d, "package.json")
        if not os.path.isfile(pj):
            continue
        try:
            txt = io.open(pj, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        nm = re.search(r'"name"\s*:\s*"([^"]+)"', txt)
        vr = re.search(r'"version"\s*:\s*"([^"]+)"', txt)
        if not nm:
            continue
        deps = re.findall(r'"([a-z0-9_.\-]+)"\s*:\s*"([^"]+)"', txt)
        blk = re.search(r'"dependencies"\s*:\s*\{(.*?)\}', txt, re.S)
        depmap = {}
        if blk:
            for k, v in re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', blk.group(1)):
                depmap[k] = v
        pkg_meta[nm.group(1)] = {
            "version": vr.group(1) if vr else "?",
            "path": os.path.join(root, d),
            "root": root,
            "deps": depmap,
        }
for k in sorted(pkg_meta):
    if re.match(r"com\.unity\.(render-pipelines|ugui|textmeshpro|shadergraph|scriptablebuildpipeline|timeline|cinemachine|searcher|burst|mathematics|2d)", k):
        print("  %-48s v%-10s deps=%s" % (k, pkg_meta[k]["version"], pkg_meta[k]["deps"]))

# which package provides which assembly (evidence = package script asset paths)
asm_provider = defaultdict(set)
asm_provider_path = {}
for r in tgt_pair.values():
    if r.get("origin") != "PACKAGE":
        continue
    a = (r.get("assembly") or "").strip()
    if not a:
        continue
    p = r.get("assetPath", "")
    m = re.match(r"Packages/([^/]+)/", p)
    if m:
        asm_provider[a].add(m.group(1))
        asm_provider_path.setdefault(a, p)

# ------------------------------------------------------- 3) export meta index
print("\n=== 3) index exported .meta guids (KEEP ALL, report conflicts) ===")
meta = defaultdict(list)
for dp, dn, fn in os.walk(os.path.join(ROOT, "Assets")):
    for x in fn:
        if not x.endswith(".meta"):
            continue
        p = os.path.join(dp, x)
        try:
            head = io.open(p, encoding="utf-8", errors="ignore").read(400)
        except Exception:
            continue
        m = GUID_RE.search(head)
        if m:
            meta[m.group(1)].append(p[:-5])
conflicts = {g: v for g, v in meta.items() if len(v) > 1}
print("  distinct guids: %d   conflicted guids: %d" % (len(meta), len(conflicts)))

with io.open(os.path.join(OUT, "meta_guid_conflicts.tsv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["guid", "count", "paths"])
    for g, v in sorted(conflicts.items(), key=lambda kv: -len(kv[1])):
        w.writerow([g, len(v), " | ".join(v)])
print("  wrote meta_guid_conflicts.tsv")

# ------------------------------------------------------------- 4) scan refs
print("\n=== 4) scan real export for m_Script references ===")
refs = Counter()
examples = defaultdict(list)
nfiles = 0
for dp, dn, fn in os.walk(os.path.join(ROOT, "Assets")):
    for x in fn:
        if not x.endswith(ASSET_EXT):
            continue
        p = os.path.join(dp, x)
        nfiles += 1
        try:
            txt = io.open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        rel = os.path.relpath(p, ROOT)
        if "m_Script:" not in txt:
            continue
        for m in REF_RE.finditer(txt):
            key = (m.group(2), int(m.group(1)))
            refs[key] += 1
            if len(examples[key]) < 3:
                examples[key].append(rel)
print("  scanned %d asset files; %d distinct (guid,fileID) pairs; %d total refs"
      % (nfiles, len(refs), sum(refs.values())))

# --------------------------------------------------- 5) build the pairs table
print("\n=== 5) build script_identity_pairs.tsv ===")
rows = []
for (g, fid), cnt in sorted(refs.items(), key=lambda kv: -kv[1]):
    s = src_pair.get((g, fid))
    old_path = meta.get(g, [""])[0]
    if s is None:
        # not a DLL-backed identity: either a decompiled .cs (fileID 11500000)
        # or a GUID that no export .meta declares (a genuinely dangling ref).
        if g in meta:
            status = "KEEP_SOURCE_CS"
            ev = "fileID=%d is a source-script form; guid present in export .meta" % fid
        else:
            status = "DANGLING_NO_META"
            ev = "guid not declared by any export .meta"
        rows.append({
            "oldGuid": g, "oldLocalID": fid, "occurrences": cnt,
            "exampleAsset": " | ".join(examples[(g, fid)]),
            "sourceAssembly": "", "namespace": "", "class": "",
            "identityEvidence": ev,
            "newGuid": "", "newLocalID": "", "targetPath": "",
            "status": status,
        })
        continue

    full = (s.get("fullTypeName") or "").strip()
    ns, _, cls = full.rpartition(".")
    cands = tgt_type.get(full, [])
    # a type may legitimately appear more than once (runtime + editor assembly);
    # pick the runtime one and record ALL candidates in the note.
    runtime = [c for c in cands if not c.get("assembly", "").endswith(".Editor")]
    chosen = (runtime or cands)[0] if cands else None
    cand_note = "candidates=%d[%s]" % (
        len(cands), "; ".join("%s@%s#%s" % (c.get("assembly"), c.get("guid"), c.get("localFileID")) for c in cands))

    if chosen is None:
        status = "NO_TARGET_IN_PACKAGES"
        ev = "Unity resolved old identity to %s; no package provides this type" % full
        rows.append({
            "oldGuid": g, "oldLocalID": fid, "occurrences": cnt,
            "exampleAsset": " | ".join(examples[(g, fid)]),
            "sourceAssembly": s.get("assembly", ""), "namespace": ns, "class": cls,
            "identityEvidence": ev, "newGuid": "", "newLocalID": "",
            "targetPath": "", "status": status,
        })
        continue

    if len(cands) > 1 and len(runtime) != 1:
        status = "UNKNOWN_MULTI_CANDIDATE"
    else:
        status = "MIGRATE"
    rows.append({
        "oldGuid": g, "oldLocalID": fid, "occurrences": cnt,
        "exampleAsset": " | ".join(examples[(g, fid)]),
        "sourceAssembly": s.get("assembly", ""), "namespace": ns, "class": cls,
        "identityEvidence": "Unity GetClass resolved %s in %s" % (full, s.get("assembly")),
        "newGuid": chosen.get("guid"), "newLocalID": chosen.get("localFileID"),
        "targetPath": chosen.get("assetPath"),
        "status": status,
    })
    if cand_note:
        rows[-1]["identityEvidence"] += "; " + cand_note

cols = ["oldGuid", "oldLocalID", "occurrences", "exampleAsset", "sourceAssembly",
        "namespace", "class", "identityEvidence", "newGuid", "newLocalID",
        "targetPath", "status"]
with io.open(os.path.join(OUT, "script_identity_pairs.tsv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
    w.writeheader()
    for r in rows:
        w.writerow(r)

st = Counter(r["status"] for r in rows)
print("  rows: %d" % len(rows))
for k, v in st.most_common():
    tot = sum(r["occurrences"] for r in rows if r["status"] == k)
    print("    %-26s pairs=%-5d refs=%d" % (k, v, tot))

# ------------------------------------------------- 6) dependency_providers.tsv
print("\n=== 6) build dependency_providers.tsv ===")
dll_asm = defaultdict(lambda: {"guid": "", "path": "", "types": 0})
for (g, fid), r in src_pair.items():
    a = (r.get("assembly") or "").strip()
    if not a:
        continue
    dll_asm[a]["guid"] = g
    dll_asm[a]["path"] = r.get("assetPath", "")
    dll_asm[a]["types"] += 1

refs_by_asm = Counter()
for r in rows:
    if r["sourceAssembly"]:
        refs_by_asm[r["sourceAssembly"]] += r["occurrences"]

dep_rows = []
for a in sorted(set(list(dll_asm.keys()) + list(asm_provider.keys()))):
    d = dll_asm.get(a)
    provs = sorted(asm_provider.get(a, []))
    # is any providing package inside the forced URP/TMP/uGUI closure?
    forced = [p for p in provs if p in
              ("com.unity.ugui", "com.unity.textmeshpro", "com.unity.render-pipelines.core",
               "com.unity.render-pipelines.universal", "com.unity.shadergraph",
               "com.unity.render-pipelines.universal-config", "com.unity.searcher")]
    if d and provs:
        decision = "REPLACE_WITH_PACKAGE"
        ev = ("dual provider: DLL %s AND package(s) %s; "
              "package wins because a package cannot coexist with a same-named DLL. "
              "Forced by dependency closure: %s"
              % (a, provs, ", ".join("%s->%s" % (p, pkg_meta.get(p, {}).get("deps", {}).get("com.unity.ugui", ""))
                                     for p in forced) or "n/a"))
    elif d and not provs:
        decision = "KEEP_DLL"
        ev = "no package provides this assembly in the current closure; keep the original DLL and its .meta GUID"
    elif provs and not d:
        decision = "PACKAGE_ONLY"
        ev = "package provides this assembly; the export has no DLL for it"
    else:
        decision = "UNKNOWN"
        ev = ""
    # resolve the package version/path evidence
    tgt_pkg = provs[0] if provs else ""
    dep_rows.append({
        "assemblyName": a,
        "currentDllPath": (d or {}).get("path", ""),
        "currentDllGuid": (d or {}).get("guid", ""),
        "targetPackage": tgt_pkg,
        "targetPackageVersion": pkg_meta.get(tgt_pkg, {}).get("version", ""),
        "targetResolvedPath": pkg_meta.get(tgt_pkg, {}).get("path", ""),
        "decision": decision,
        "decisionEvidence": ev,
        "affectedRefPairCount": sum(1 for r in rows if r["sourceAssembly"] == a),
        "affectedRefTotal": refs_by_asm.get(a, 0),
        "dllTypeCount": (d or {}).get("types", 0),
    })

dcols = ["assemblyName", "currentDllPath", "currentDllGuid", "targetPackage",
         "targetPackageVersion", "targetResolvedPath", "decision", "decisionEvidence",
         "affectedRefPairCount", "affectedRefTotal", "dllTypeCount"]
with io.open(os.path.join(OUT, "dependency_providers.tsv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=dcols, delimiter="\t")
    w.writeheader()
    for r in dep_rows:
        w.writerow(r)

dec = Counter(r["decision"] for r in dep_rows)
print("  assemblies: %d" % len(dep_rows))
for k, v in dec.most_common():
    print("    %-24s %d" % (k, v))
print("\n  assemblies to REPLACE_WITH_PACKAGE (refs, types):")
for r in sorted(dep_rows, key=lambda r: -r["affectedRefTotal"]):
    if r["decision"] == "REPLACE_WITH_PACKAGE":
        print("    %-46s refs=%-6d pairs=%-4d types=%-4d <- %s"
              % (r["assemblyName"], r["affectedRefTotal"], r["affectedRefPairCount"],
                 r["dllTypeCount"], r["targetPackage"]))
print("\nDONE")
