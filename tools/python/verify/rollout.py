# -*- coding: utf-8 -*-
"""
Full rollout of the 68 confirmed reference pairs, plus the same byte-level gate
that the samples had to pass -- applied to EVERY changed file this time.

Expected arithmetic:
  total MIGRATE references in the project   : 6100
  already migrated by the sample run (2 files, 13 types) : 1270
  therefore this rollout must report        : 4830 replacements
and after it the project must contain ZERO remaining old identities.
"""

import io, os, sys, csv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = r"<BUILD_DIR>\_cd"
sys.path.insert(0, OUT)
import cd3_rewrite as R          # noqa: E402

RUN_ID = "rollout1"
EXPECTED = 6100
SAMPLE_DONE = 1270

print("=== 1) pre-rollout: how many old identities remain? ===")
mig = [(r["oldGuid"], int(r["oldLocalID"]), r["newGuid"], int(r["newLocalID"]),
        (r["namespace"] + "." + r["class"]).strip("."))
       for r in csv.DictReader(io.open(os.path.join(OUT, "script_identity_pairs.tsv"),
                                       encoding="utf-8"), delimiter="\t")
       if r["status"] == "MIGRATE"]


def scan_old():
    total = 0
    per = {}
    for dp, dn, fn in os.walk(os.path.join(R.EXPORT, "Assets")):
        for x in fn:
            if not x.endswith(R.ASSET_EXT):
                continue
            p = os.path.join(dp, x)
            try:
                text, _, _, _ = R.read_strict(p)
            except RuntimeError:
                continue
            if "m_Script:" not in text:
                continue
            n = 0
            for og, ofid, ng, nfid, full in mig:
                n += len(R.ref_re(og, ofid).findall(text))
            if n:
                per[os.path.relpath(p, R.EXPORT)] = n
                total += n
    return total, per


pre_total, pre_per = scan_old()
print("  remaining old refs: %d across %d files" % (pre_total, len(pre_per)))
print("  expected to remain after the sample run: %d" % (EXPECTED - SAMPLE_DONE))

print("\n=== 2) apply --all ===")
rc = R.do_apply(None, True, [], RUN_ID)
print("apply returned %d" % rc)
if rc != 0:
    sys.exit(rc)

print("\n=== 3) GATE 1 for every changed file ===")
journ = os.path.join(OUT, "rewrite_journal_%s.tsv" % RUN_ID)
rows = list(csv.DictReader(io.open(journ, encoding="utf-8"), delimiter="\t"))
print("journal rows: %d" % len(rows))

total_repl = 0
bad_lines = 0
bad_files = []
line_mismatch = []
nl_changed = []
for row in rows:
    cur = os.path.join(R.EXPORT, row["relpath"])
    bak = row["backup_path"]
    old = open(bak, "rb").read().decode("utf-8", errors="strict")
    new = open(cur, "rb").read().decode("utf-8", errors="strict")
    total_repl += int(row["replacements"])
    ol, nl = old.split("\n"), new.split("\n")
    if len(ol) != len(nl):
        line_mismatch.append(row["relpath"])
        continue
    if old.endswith("\n") != new.endswith("\n") or ("\r\n" in old) != ("\r\n" in new):
        nl_changed.append(row["relpath"])
    ch = [i for i in range(len(ol)) if ol[i] != nl[i]]
    n = sum(1 for i in ch if "m_Script:" not in nl[i])
    if n:
        bad_lines += n
        bad_files.append((row["relpath"], n))
    if len(ch) != int(row["replacements"]):
        bad_files.append((row["relpath"], -1))

print("  files changed                : %d" % len(rows))
print("  total replacements           : %d" % total_repl)
print("  expected replacements        : %d" % (EXPECTED - SAMPLE_DONE))
print("  arithmetic match             : %s" % (total_repl == EXPECTED - SAMPLE_DONE))
print("  lines changed NOT m_Script   : %d" % bad_lines)
print("  files with line-count change : %d %s" % (len(line_mismatch), line_mismatch[:3]))
print("  files with newline/BOM change: %d %s" % (len(nl_changed), nl_changed[:3]))
print("  inconsistent files           : %d %s" % (len(bad_files), bad_files[:5]))

print("\n=== 4) post-rollout: remaining old identities must be 0 ===")
post_total, post_per = scan_old()
print("  remaining old refs: %d across %d files" % (post_total, len(post_per)))
for k, v in list(post_per.items())[:10]:
    print("     %s  x%d" % (k, v))

print("\n=== 5) new identities present ===")
new_total = 0
for dp, dn, fn in os.walk(os.path.join(R.EXPORT, "Assets")):
    for x in fn:
        if not x.endswith(R.ASSET_EXT):
            continue
        p = os.path.join(dp, x)
        try:
            text, _, _, _ = R.read_strict(p)
        except RuntimeError:
            continue
        if "m_Script:" not in text:
            continue
        for og, ofid, ng, nfid, full in mig:
            new_total += text.count("m_Script: {fileID: %d, guid: %s, type: 3}" % (nfid, ng))
print("  migrated new identities found in project: %d" % new_total)
print("  (should be 6100 if every old reference now uses the new identity)")

ok = (total_repl == EXPECTED - SAMPLE_DONE and bad_lines == 0 and post_total == 0
      and not line_mismatch and not nl_changed and new_total == EXPECTED)
print("\n=== ROLLOUT RESULT: %s ===" % ("PASS" if ok else "FAIL"))
