# -*- coding: utf-8 -*-
"""
Verify the Android bundle build properly, replacing a check that was vacuous.

The build report counted "Encrypted":true/false in the manifest text and found
neither, because PackageManifest_*.bytes is a BINARY manifest, not JSON.  A check
that finds nothing proves nothing, so this script replaces it with:

  1. what the produced manifest actually is (magic bytes / first printable run)
  2. whether every produced .bundle starts with the unencrypted UnityFS header
     -- YooAsset XORs bundle headers when a bundle is encrypted, so a plain
     'UnityFS' prefix is direct evidence that no encryption was applied
  3. what the SHIPPED game's bundle file names look like, to confirm whether
     FileNameStyle=HashName is the right choice
"""

import io, os, glob, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXP = r"<UNITY_PROJECT>"
BUILT = os.path.join(EXP, "Assets", "StreamingAssets", "dynamic_assets", "RootPackage")
ORIG_GAME = r"<ORIGINAL_BUILD>"

print("=== 1) what is PackageManifest_RootPackage_1.0.bytes ? ===")
man = glob.glob(os.path.join(BUILT, "PackageManifest_*.bytes"))
if not man:
    print("  not found in " + BUILT)
    sys.exit(1)
p = man[0]
raw = open(p, "rb").read()
print("  file  : %s" % os.path.basename(p))
print("  size  : %d B" % len(raw))
print("  first 16 bytes hex : %s" % raw[:16].hex())
print("  first 24 bytes repr: %r" % raw[:24])
try:
    txt = raw.decode("utf-8")
    print("  decodes as UTF-8 : yes")
    for key in ('"Encrypted"', "Encrypted", '"FileVersion"', "FileVersion"):
        print("     contains %-16s : %d" % (key, txt.count(key)))
except UnicodeDecodeError as e:
    print("  decodes as UTF-8 : NO (%s)" % str(e)[:70])
print("  => binary manifest" if raw[:1] != b"{" else "  => JSON manifest")

print("\n=== 2) bundle headers: UnityFS means NOT encrypted ===")
bundles = sorted(glob.glob(os.path.join(BUILT, "*.bundle")))
print("  bundles: %d" % len(bundles))
kinds = collections.Counter()
bad = []
for b in bundles:
    with open(b, "rb") as f:
        head = f.read(8)
    k = head[:8]
    kinds[k] += 1
    if not k.startswith(b"UnityFS"):
        bad.append((os.path.basename(b), head))
for k, n in kinds.most_common():
    print("     %-12r x%d" % (k, n))
print("  bundles NOT starting with UnityFS: %d" % len(bad))
for n, h in bad[:10]:
    print("     %s  head=%r" % (n, h))
if not bad:
    print("  => every bundle carries a plain UnityFS header, so encryption is OFF")

print("\n=== 3) the SHIPPED game's bundle file names (FileNameStyle evidence) ===")
cands = []
for sub in ("TC_Data", "TC_Data"):
    d = os.path.join(ORIG_GAME, sub, "StreamingAssets", "dynamic_assets")
    if os.path.isdir(d):
        cands.append(d)
print("  searched: %s" % cands)
for d in cands:
    for pkg in sorted(os.listdir(d)):
        full = os.path.join(d, pkg)
        if not os.path.isdir(full):
            print("  [file] %-40s %d B" % (pkg, os.path.getsize(full)))
            continue
        files = sorted(os.listdir(full))
        print("  [pkg ] %-20s %d files" % (pkg, len(files)))
        for f in files[:6]:
            print("        %-52s %d B" % (f, os.path.getsize(os.path.join(full, f))))
        nameish = [f for f in files if not f.endswith(".bytes") and "_" in f and not
                   all(c in "0123456789abcdef" for c in os.path.splitext(f)[0])]
        hashish = [f for f in files if f.endswith(".bundle") and
                   all(c in "0123456789abcdef" for c in os.path.splitext(f)[0])]
        print("        hash-style .bundle names: %d   bundle-name-style: %d" % (len(hashish), len(nameish)))

print("\n=== 4) produced vs shipped: counts ===")
print("  produced bundles            : %d" % len(bundles))
print("  shipped manifest BundleList : 63")
print("  difference                  : %d  (share bundles created by EnableSharePackRule)"
      % (len(bundles) - 63))
