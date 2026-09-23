"""audit_effective.py -- 精确版批次审计（只比较有效值）。

前一版统计了键在文件中的所有出现，于是 Unity 新写入的平台副本被误判为值变化。
本脚本只比较有效值：

  A) the DEFAULT section (everything before "platformSettings:") key by key - this is what an
     Android build actually uses when no platform override is in effect; and
  B) the platformSettings blocks, where every block must report overridden: 0

ASCII-only output.
"""

import io, os, re, json, collections

BACKUP = r'<BUILD_DIR>\_probe\r23_pma_meta_backup'
PROJ = r'<UNITY_PROJECT>'
CHANGED = r'<BUILD_DIR>\_cd\r23_changed_paths.txt'
OUT = r'<BUILD_DIR>\_cd\r23_audit_effective.json'

BOOKKEEPING = {'serializedVersion', 'timeCreated', 'licenseType', 'userData',
               'assetBundleName', 'assetBundleVariant', 'spriteID', 'internalIDToNameTable',
               'm_ObjectHideFlags', 'm_Name'}


def default_section(text):
    i = text.find('platformSettings:')
    head = text if i < 0 else text[:i]
    d = collections.OrderedDict()
    for line in head.splitlines():
        m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$', line)
        if m:
            d[m.group(1)] = m.group(2)
    return d


def platform_blocks(text):
    """return list of (buildTarget, overridden) for each platform block"""
    out = []
    for m in re.finditer(r'-\s*serializedVersion:\s*\d+\s*\n\s*buildTarget:\s*(\S+)([\s\S]*?)(?=\n\s*-\s*serializedVersion:|\Z)', text):
        target = m.group(1)
        body = m.group(2)
        ov = re.search(r'^\s*overridden:\s*(\d+)\s*$', body, re.M)
        out.append((target, ov.group(1) if ov else '<none>'))
    return out


def main():
    paths = [l.strip() for l in io.open(CHANGED, encoding='utf-8').read().splitlines() if l.strip()]
    unexpected = []
    keydiff = collections.Counter()
    blocks_added = 0
    overriding = []
    alpha_ok = 0
    for p in paths:
        cur = io.open(os.path.join(PROJ, p.replace('/', os.sep) + '.meta'), encoding='utf-8', errors='replace').read()
        bak = io.open(os.path.join(BACKUP, p.replace('/', os.sep) + '.meta'), encoding='utf-8', errors='replace').read()

        a, b = default_section(bak), default_section(cur)
        for k in set(list(a.keys()) + list(b.keys())):
            if a.get(k) == b.get(k):
                continue
            keydiff[k] += 1
            if k not in BOOKKEEPING and k != 'alphaIsTransparency':
                unexpected.append(('default section key changed: %s  %s -> %s' % (k, a.get(k), b.get(k)), p))
        if b.get('alphaIsTransparency') == '0':
            alpha_ok += 1
        else:
            unexpected.append(('alphaIsTransparency not 0: %s' % b.get('alphaIsTransparency'), p))

        pb, pc = platform_blocks(bak), platform_blocks(cur)
        blocks_added += max(0, len(pc) - len(pb))
        for target, ov in pc:
            if ov != '0':
                overriding.append((p, target, ov))

    print('metas audited                 : %d' % len(paths))
    print('alphaIsTransparency now 0     : %d' % alpha_ok)
    print('default-section key diffs     : %s' % dict(keydiff))
    print('platform blocks added         : %d' % blocks_added)
    print('blocks with overridden != 0   : %d' % len(overriding))
    print('unexpected diffs              : %d' % len(unexpected))
    for x in unexpected[:15]:
        print('   %s :: %s' % x)

    json.dump({'audited': len(paths), 'alpha_ok': alpha_ok, 'default_key_diffs': dict(keydiff),
               'platform_blocks_added': blocks_added, 'overriding_blocks': overriding,
               'unexpected': [list(x) for x in unexpected]},
              io.open(OUT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('-> %s' % OUT)


if __name__ == '__main__':
    main()
