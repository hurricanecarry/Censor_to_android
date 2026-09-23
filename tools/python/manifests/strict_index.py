# -*- coding: utf-8 -*-
"""
L4: make AssetsManager consume the strict PackageIndex.

A missing asset, malformed JSON, duplicate package names or a
missing RootPackage must fail an acceptance build, not be folded into "optional
DLC simply absent".  Previously PackageIndex.Load() logged and returned null, so
every such condition looked exactly like "no DLC", which the DLC branch then
treated as normal.

New behaviour:
  * WindowsEditor -> warn and continue (explicitly marked editor path)
  * any player   -> throw, naming the concrete index defect
"""

import io, os, sys, csv, shutil, hashlib, datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXP = r"<UNITY_PROJECT>"
TARGET = os.path.join(EXP, "Assets", "Scripts", "Assembly-CSharp", "Censorer", "Manager", "AssetsManager.cs")
BACKUP_ROOT = r"<UNITY_PROJECT_ROOT>\_fix_backup"
OUT = r"<BUILD_DIR>\_cd"
FIX_ID = "L4_STRICT_PACKAGE_INDEX"

APPLY = "--apply" in sys.argv

OLD = ('\t\t\tglobal::Censorer.Manager.PackageIndex packageIndex = '
       'global::Censorer.Manager.PackageIndex.Load();\n')

NEW = (
    '\t\t\tbool isEditorPlatform = (global::UnityEngine.Application.platform == '
    'global::UnityEngine.RuntimePlatform.WindowsEditor);\n'
    '\t\t\tstring packageIndexError;\n'
    '\t\t\tglobal::Censorer.Manager.PackageIndex packageIndex = '
    'global::Censorer.Manager.PackageIndex.Load(out packageIndexError);\n'
    '\t\t\tif (packageIndex == null)\n'
    '\t\t\t{\n'
    '\t\t\t\tif (isEditorPlatform)\n'
    '\t\t\t\t{\n'
    '\t\t\t\t\tglobal::UnityEngine.Debug.LogWarning("[AssetsManager] " + packageIndexError'
    ' + " -- editor path continues with every optional package treated as not included.");\n'
    '\t\t\t\t}\n'
    '\t\t\t\telse\n'
    '\t\t\t\t{\n'
    '\t\t\t\t\tthrow new global::System.Exception("Package index is unusable: " + packageIndexError);\n'
    '\t\t\t\t}\n'
    '\t\t\t}\n')

raw = open(TARGET, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig" if bom else "utf-8")

print("=== locate the line to replace ===")
print("  occurrences of the old call: %d" % text.count(OLD))
if text.count(OLD) != 1:
    print("  !! expected exactly one occurrence -- refusing")
    sys.exit(2)

# the editor/platform test is computed later in the current code; make sure we are
# not introducing a duplicate identifier
if "isEditorPlatform" in text:
    print("  !! 'isEditorPlatform' already present -- refusing to shadow")
    sys.exit(2)

new_text = text.replace(OLD, NEW)
print("  replacement inserted, delta = %+d chars" % (len(new_text) - len(text)))

if not APPLY:
    print("\ndry-run. context after the edit:")
    i = new_text.find("isEditorPlatform")
    for line in new_text[max(0, i - 260):i + 620].split("\n"):
        print("   " + line)
    print("\nre-run with --apply")
    sys.exit(0)

bak = os.path.join(BACKUP_ROOT, FIX_ID, "AssetsManager.cs")
os.makedirs(os.path.dirname(bak), exist_ok=True)
shutil.copy2(TARGET, bak)
data = new_text.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
tmp = TARGET + ".l4tmp"
open(tmp, "wb").write(data)
os.replace(tmp, TARGET)

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
journ = os.path.join(OUT, "fix_journal_%s.tsv" % stamp)
with io.open(journ, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["fixId", "relpath", "sha256_before", "sha256_after", "size_before",
                "size_after", "backup_path", "note"])
    w.writerow([FIX_ID, "Assets/Scripts/Assembly-CSharp/Censorer/Manager/AssetsManager.cs",
                hashlib.sha256(raw).hexdigest(), hashlib.sha256(data).hexdigest(),
                len(raw), len(data), bak,
                "strict PackageIndex: player throws, editor warns"])
print("\n=== APPLIED ===")
print("  file    : %s" % TARGET)
print("  backup  : %s" % bak)
print("  journal : %s" % journ)
print("  size %d -> %d" % (len(raw), len(data)))
