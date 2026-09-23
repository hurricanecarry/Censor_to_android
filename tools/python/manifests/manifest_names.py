# -*- coding: utf-8 -*-
"""
Check the LOGICAL structure of the rebuilt manifest, not byte equality.

Byte-level hash overlap with the shipped bundles is not a valid expectation:
the shipped game was built by Unity 2022.3.0f1 while this rebuild runs on
2022.3.62f3c1, and every asset was round-tripped through AssetRipper's YAML
export.  Both change serialized bytes, hence every bundle hash.

What IS meaningful and checkable without Unity: the manifest stores bundle names
as plain (length-prefixed) strings, so the original 63 names can be searched for
directly, and the dependency structure can be read.
"""

import io, os, csv, sys, re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXP = r"<UNITY_PROJECT>"
DATA = r"<EVIDENCE_DIR>\data"
BUILT = os.path.join(EXP, "Assets", "StreamingAssets", "dynamic_assets", "RootPackage")

man = [f for f in os.listdir(BUILT) if f.startswith("PackageManifest_") and f.endswith(".bytes")]
if not man:
    print("no manifest in " + BUILT)
    sys.exit(1)
p = os.path.join(BUILT, man[0])
raw = open(p, "rb").read()
print("manifest: %s  %d B" % (man[0], len(raw)))

print("\n=== 1) are the shipped 63 logical bundle names present? ===")
rows = list(csv.DictReader(io.open(os.path.join(DATA, "RootPackage_bundles.tsv"),
                                   encoding="utf-8"), delimiter="\t"))
names = [r["BundleName"] for r in rows]
found = [n for n in names if n.encode("utf-8") in raw]
missing = [n for n in names if n.encode("utf-8") not in raw]
print("  shipped bundle names: %d" % len(names))
print("  present in rebuilt manifest : %d" % len(found))
print("  missing                     : %d" % len(missing))
for n in missing[:12]:
    print("     %s" % n)

print("\n=== 2) are the 95 shipped addresses present? ===")
asr = list(csv.DictReader(io.open(os.path.join(DATA, "RootPackage_assets.tsv"),
                                  encoding="utf-8"), delimiter="\t"))
afound = [r["Address"] for r in asr if r["Address"].encode("utf-8") in raw]
amiss = [r["Address"] for r in asr if r["Address"].encode("utf-8") not in raw]
print("  shipped addresses: %d   present: %d   missing: %d"
      % (len(asr), len(afound), len(amiss)))
for a in amiss[:12]:
    print("     %s" % a)

print("\n=== 3) does the rebuilt manifest carry the shipped dependency (chaospic)? ===")
chaos = b"rootpackage_assets_art_uipanels_common_textures_chaospic.bundle"
mainpanel = b"rootpackage_assets_art_uipanels_mainpanel_mainpanel.bundle"
print("  chaospic bundle name present  : %s" % (chaos in raw))
print("  mainpanel bundle name present : %s" % (mainpanel in raw))

print("\n=== 4) manifest header / version fields ===")
print("  first 32 bytes: %r" % raw[:32])
for probe in (b"2.0.0", b"RootPackage", b"dynamic_assets", b"Android"):
    print("     contains %-16r : %s" % (probe, probe in raw))

print("\n=== 5) produced package dir contents ===")
for f in sorted(os.listdir(BUILT)):
    if not f.endswith(".bundle"):
        print("     [meta] %-46s %d B" % (f, os.path.getsize(os.path.join(BUILT, f))))
nb = len([f for f in os.listdir(BUILT) if f.endswith(".bundle")])
print("     bundles: %d   (shipped: 63)" % nb)
