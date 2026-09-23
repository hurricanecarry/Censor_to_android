"""dlc_address_map.py

Build the DLC half of the address map from the ORIGINAL DLCPackage manifest.

Why needed: the game calls AssetsManager.LoadSyncFromDLC("UI_WallPaper-anchor-qte1") etc., while
the exported asset is Assets/AssetBundles/dlcpackage_assets_art_dlc_extraprefabs/art/dlc/
extraprefabs/WallPaper-anchor-qte1.prefab.  Addresses cannot be derived from paths, so the
original manifest's (address, asset path) pairs are carried explicitly, exactly like the 95
RootPackage rows already in Assets/PortBuild/PortAddressMap.tsv.

The original manifest is YooAsset binary; its strings are stored as length-prefixed runs, so the
(address, path) pairs can be read by scanning printable strings: every "Assets/Art/DLC/..." string
is preceded by its address string.

ASCII-only output; writes _cd/r24_dlc_address_map.tsv
"""

import io, os, re, sys

MANIFEST = (r'<ORIGINAL_BUILD>\TC_Data'
            r'\StreamingAssets\dynamic_assets\DLCPackage\PackageManifest_DLCPackage_2026-08-18-969.bytes')
PROJ = r'<UNITY_PROJECT>'
OUT = r'<BUILD_DIR>\_cd\r24_dlc_address_map.tsv'
EXISTING = os.path.join(PROJ, 'Assets', 'PortBuild', 'PortAddressMap.tsv')

# bundle folder for each original DLC subtree
FOLDER_RULES = [
    ('Assets/Art/DLC/ExtraPrefabs/', 'dlcpackage_assets_art_dlc_extraprefabs', 'art/dlc/extraprefabs/'),
    ('Assets/Art/DLC/Scenes/TVInside/', 'dlcpackage_assets_art_dlc_scenes_tvinside', 'art/dlc/scenes/tvinside/'),
    ('Assets/Art/DLC/Scenes/TVOutside/', 'dlcpackage_assets_art_dlc_scenes_tvoutside', 'art/dlc/scenes/tvoutside/'),
    ('Assets/Art/DLC/Scenes/TVStationRoom/', 'dlcpackage_assets_art_dlc_scenes_tvstationroom', 'art/dlc/scenes/tvstationroom/'),
    ('Assets/Art/DLC/NPCs/Prefabs/', 'dlcpackage_assets_art_dlc_npcs_prefabs', 'art/dlc/npcs/prefabs/'),
]


def pairs():
    b = open(MANIFEST, 'rb').read()
    strs = [s.decode('ascii', 'replace') for s in re.findall(rb'[\x20-\x7e]{4,}', b)]
    out = []
    for i, s in enumerate(strs):
        if not s.startswith('Assets/Art/DLC/'):
            continue
        addr = strs[i - 1] if i > 0 else ''
        # The manifest stores each string as [length byte][bytes], so the byte that precedes the
        # path is its LENGTH and, when that value is printable, the string scan glues it onto the
        # end of the address.  Strip it only when it really equals len(path).
        if addr and len(addr) > 1 and ord(addr[-1]) == len(s):
            addr = addr[:-1]
        out.append((addr, s))
    return out


def main():
    ps = pairs()
    print('pairs found in the original DLC manifest: %d' % len(ps))
    rows = []
    for addr, orig in ps:
        matched = None
        for prefix, folder, sub in FOLDER_RULES:
            if orig.startswith(prefix):
                matched = (folder, sub + orig[len(prefix):])
                break
        if matched is None:
            print('  !! no folder rule for %s' % orig)
            continue
        folder, sub = matched
        export = 'Assets/AssetBundles/%s/%s' % (folder, sub)
        exists = os.path.exists(os.path.join(PROJ, export.replace('/', os.sep)))
        rows.append((addr, orig, export, folder + '.bundle', exists))
        print('  %-34s %-58s exists=%s' % (addr, export.replace('Assets/AssetBundles/', ''), exists))

    missing = [r for r in rows if not r[4]]
    print()
    print('rows: %d   missing on disk: %d' % (len(rows), len(missing)))
    for r in missing:
        print('   MISSING %s' % r[2])

    # collisions against the existing RootPackage map
    existing = {}
    if os.path.exists(EXISTING):
        lines = io.open(EXISTING, encoding='utf-8', errors='replace').read().splitlines()
        for l in lines[1:]:
            c = l.split('\t')
            if len(c) >= 3:
                existing[c[2].strip().replace('\\', '/')] = c[0].strip()
    print('existing map rows: %d' % len(existing))
    coll = [r for r in rows if r[2] in existing]
    print('collisions with existing map: %d' % len(coll))
    for c in coll:
        print('   %s (existing address %s)' % (c[2], existing[c[2]]))

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write('Address\tOriginalAssetPath\tExportAssetPath\tBundleName\n')
        for r in rows:
            f.write('%s\t%s\t%s\t%s\n' % r[:4])
    print('-> %s' % OUT)


if __name__ == '__main__':
    main()
