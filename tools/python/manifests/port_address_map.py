# -*- coding: utf-8 -*-
"""
Generate the port-side address map and the bundle folder list.

The original YooAsset manifest gives 95 (Address, AssetPath, BundleName) triples.
The AssetRipper export relocated every asset to
    Assets/AssetBundles/<bundleName without .bundle>/<original path, directories lowercased>
so both the address and the bundle name have to be reconstructed for the rebuild:

  * the bundle name is recoverable from the folder directly under AssetBundles/
  * the address is NOT recoverable (UI_MainUI has no relation to MainUI.prefab),
    so it is carried in an explicit map file that a custom IAddressRule reads.

Outputs a TSV consumed by the editor-side rule, and prints the mapping so the
relocation rule itself is verifiable.
"""

import io, os, csv, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = r"<BUILD_DIR>\_cd"
EXP = r"<UNITY_PROJECT>"
DATA = r"<EVIDENCE_DIR>\data"
DEST = os.path.join(EXP, "Assets", "PortBuild")

print("=== load the original manifest tables ===")
assets = list(csv.DictReader(io.open(os.path.join(DATA, "RootPackage_assets.tsv"),
                                     encoding="utf-8"), delimiter="\t"))
bundles = list(csv.DictReader(io.open(os.path.join(DATA, "RootPackage_bundles.tsv"),
                                      encoding="utf-8"), delimiter="\t"))
print("  addresses: %d   bundles: %d" % (len(assets), len(bundles)))


def relocate(asset_path, bundle_name):
    """Assets/Art/UIPanels/MainUI.prefab + rootpackage_..._mainui.bundle
       -> Assets/AssetBundles/rootpackage_..._mainui/art/uipanels/MainUI.prefab"""
    assert asset_path.startswith("Assets/"), asset_path
    rel = asset_path[len("Assets/"):]
    parts = rel.split("/")
    dirs = [p.lower() for p in parts[:-1]]
    folder = bundle_name[:-len(".bundle")] if bundle_name.endswith(".bundle") else bundle_name
    return "/".join(["Assets", "AssetBundles", folder] + dirs + [parts[-1]])


print("\n=== relocate every addressed asset and check it exists ===")
rows = []
missing = []
for r in assets:
    exp_path = relocate(r["AssetPath"], r["BundleName"])
    full = os.path.join(EXP, exp_path.replace("/", os.sep))
    if not os.path.isfile(full):
        missing.append((r["Address"], exp_path))
        continue
    rows.append({"Address": r["Address"], "OriginalAssetPath": r["AssetPath"],
                 "ExportAssetPath": exp_path, "BundleName": r["BundleName"]})

print("  relocated and found : %d" % len(rows))
print("  NOT found           : %d" % len(missing))
for a, p in missing[:15]:
    print("     %s -> %s" % (a, p))

print("\n=== sample of the relocation rule (first 5) ===")
for r in rows[:5]:
    print("   %-26s %s" % (r["Address"], r["OriginalAssetPath"]))
    print("       -> %s" % r["ExportAssetPath"])
    print("       bundle %s" % r["BundleName"])

print("\n=== bundle folders under Assets/AssetBundles ===")
abroot = os.path.join(EXP, "Assets", "AssetBundles")
folders = sorted(d for d in os.listdir(abroot) if os.path.isdir(os.path.join(abroot, d)))
print("  folders on disk: %d" % len(folders))
manifest_folders = sorted({b["BundleName"][:-len(".bundle")] if b["BundleName"].endswith(".bundle")
                           else b["BundleName"] for b in bundles})
print("  folders declared in the manifest: %d" % len(manifest_folders))
only_disk = sorted(set(folders) - set(manifest_folders))
only_manifest = sorted(set(manifest_folders) - set(folders))
print("  on disk but not declared : %d %s" % (len(only_disk), only_disk[:5]))
print("  declared but not on disk : %d %s" % (len(only_manifest), only_manifest[:5]))

print("\n=== bundle names: manifest vs what PackRuleResult would produce ===")
def normalize(collect_path_like):
    return collect_path_like.replace("/", "_").replace(".", "_").replace(" ", "_").lower()

bad = 0
for b in bundles:
    orig = b["BundleName"]
    # PackCollector on the relocated folder would yield this
    folder = orig[:-len(".bundle")] if orig.endswith(".bundle") else orig
    builtin = "assets_assetbundles_" + folder + ".bundle"
    # our custom rule returns just the folder
    custom = folder + ".bundle"
    ok = (custom == orig)
    if not ok:
        bad += 1
    if b["BundleID"] in ("0", "5", "8", "42", "62"):
        print("   id=%-3s original=%-64s" % (b["BundleID"], orig))
        print("            builtin PackCollector -> %s" % builtin)
        print("            custom rule           -> %s   match=%s" % (custom, ok))
print("  bundles where the custom rule does NOT reproduce the original name: %d" % bad)

os.makedirs(DEST, exist_ok=True)
addr_path = os.path.join(DEST, "PortAddressMap.tsv")
with io.open(addr_path, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["Address", "OriginalAssetPath", "ExportAssetPath",
                                      "BundleName"], delimiter="\t")
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("\nwrote %s  (%d rows)" % (os.path.relpath(addr_path, EXP), len(rows)))

meta = os.path.join(DEST, "PortBuildInfo.txt")
with io.open(meta, "w", encoding="utf-8") as f:
    f.write("sourceManifest\t%s\n" % os.path.join(DATA, "RootPackage.json"))
    f.write("packageName\tRootPackage\n")
    f.write("yooFolder\tdynamic_assets\n")
    f.write("addressCount\t%d\n" % len(rows))
    f.write("bundleCount\t%d\n" % len(bundles))
    f.write("note\tAddresses are not derivable from paths; this map is authoritative for the rebuild.\n")
print("wrote %s" % os.path.relpath(meta, EXP))
