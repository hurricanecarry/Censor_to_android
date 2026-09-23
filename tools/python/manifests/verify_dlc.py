"""verify_dlc.py

Verify the freshly built DLCPackage against the original's manifest.

1. the package index must declare DLCPackage included with real metadata and still declare
   RootPackage
2. the built manifest's ADDRESSES must be exactly the 37 addresses the original
   PackageManifest_DLCPackage_2026-08-18-969.bytes carried (this is what the game loads by)
3. the built bundles must carry the original five bundle names

ASCII-only output.
"""

import io, os, re, json

PROJ = r'<UNITY_PROJECT>'
DLC = os.path.join(PROJ, 'Assets', 'StreamingAssets', 'dynamic_assets', 'DLCPackage')
INDEX = os.path.join(PROJ, 'Assets', 'Resources', 'CensorPackageIndex.txt')
MAP = r'<BUILD_DIR>\_cd\r24_dlc_address_map.tsv'

ORIG_BUNDLES = ['dlcpackage_assets_art_dlc_extraprefabs', 'dlcpackage_assets_art_dlc_scenes_tvinside',
                'dlcpackage_assets_art_dlc_scenes_tvoutside', 'dlcpackage_assets_art_dlc_scenes_tvstationroom',
                'dlcpackage_assets_art_dlc_npcs_prefabs']


def main():
    print('=== 1. package index ===')
    idx = json.load(io.open(INDEX, encoding='utf-8'))
    print('generatedAt = %s' % idx.get('generatedAt'))
    problems = []
    for p in idx['packages']:
        print('   %-12s included=%-5s manifest=%-42s size=%-8s bundles=%-3s bytes=%s'
              % (p['name'], p['included'], p['manifestFileName'], p['manifestSize'],
                 p['bundleCount'], p['bundleTotalBytes']))
        if p['included']:
            if not p['manifestFileName'] or p['manifestSize'] <= 0 or not p['manifestSha256']:
                problems.append('entry %s fails PackageIndex.Validate' % p['name'])
    names = set(p['name'] for p in idx['packages'])
    if 'RootPackage' not in names:
        problems.append('RootPackage missing')
    if not [p for p in idx['packages'] if p['name'] == 'DLCPackage' and p['included']]:
        problems.append('DLCPackage not included')

    print()
    print('=== 2. addresses in the built DLC manifest ===')
    man = None
    for f in os.listdir(DLC):
        if f.startswith('PackageManifest_DLCPackage') and f.endswith('.bytes'):
            man = os.path.join(DLC, f)
    print('manifest: %s (%d B)' % (os.path.basename(man), os.path.getsize(man)))
    raw = open(man, 'rb').read()
    strs = [s.decode('ascii', 'replace') for s in re.findall(rb'[\x20-\x7e]{4,}', raw)]
    got = set()
    for i, s in enumerate(strs):
        if not s.startswith('Assets/'):
            continue
        a = strs[i - 1] if i > 0 else ''
        if a and len(a) > 1 and ord(a[-1]) == len(s):
            a = a[:-1]
        got.add(a)
    want = set()
    for l in io.open(MAP, encoding='utf-8').read().splitlines()[1:]:
        c = l.split('\t')
        if len(c) >= 3:
            want.add(c[0].strip())
    print('addresses in built manifest : %d' % len(got))
    print('addresses expected (map)    : %d' % len(want))
    missing = sorted(want - got)
    extra = sorted(got - want)
    print('missing: %d %s' % (len(missing), missing[:8]))
    print('extra  : %d %s' % (len(extra), extra[:8]))
    if missing:
        problems.append('%d addresses missing from the built manifest' % len(missing))

    print()
    print('=== 3. bundles ===')
    files = sorted(os.listdir(DLC))
    for f in files:
        print('   %-52s %d' % (f, os.path.getsize(os.path.join(DLC, f))))
    got_names = set(os.path.basename(s).split('.')[0] for s in strs if s.endswith('.bundle'))
    print('bundle names seen in manifest: %s' % sorted(got_names))
    for b in ORIG_BUNDLES:
        if b not in got_names and (b + '.bundle') not in got_names:
            problems.append('bundle name not in manifest: %s' % b)

    print()
    print('PROBLEMS: %d' % len(problems))
    for p in problems:
        print('   %s' % p)


if __name__ == '__main__':
    main()
