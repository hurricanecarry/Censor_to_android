import zipfile, os, sys, io, glob
sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

APK = r'<BUILD_DIR>\_probe\CensorPort_P1_b45.apk'
PROJ = r'<UNITY_PROJECT>\Assets\StreamingAssets\dynamic_assets\RootPackage'
FMT = {4: 'RGBA32', 47: 'ETC2_RGBA8', 45: 'ETC2_RGB4', 12: 'DXT5', 10: 'DXT1'}

z = zipfile.ZipFile(APK)
names = [n for n in z.namelist() if 'RootPackage' in n and n.endswith('.bundle')]
print('APK bundle entries under RootPackage: %d' % len(names))

# project side: which bundle file holds cengceng, and its size
proj_map = {}
for b in glob.glob(os.path.join(PROJ, '*.bundle')):
    proj_map[os.path.basename(b)] = os.path.getsize(b)

hits = 0
for n in names:
    base = os.path.basename(n)
    size = z.getinfo(n).file_size
    # only inspect the ones we know carry cengceng, to keep this quick
    if base not in proj_map:
        print('  !! %s is in the APK but NOT in the project StreamingAssets' % base)
        continue
    if proj_map[base] != size:
        print('  !! %s size differs: apk=%d project=%d' % (base, size, proj_map[base]))
        hits += 1

print()
print('=== inspect the cengceng-bearing bundles straight out of the APK ===')
for n in names:
    base = os.path.basename(n)
    if base not in ('f0a626c05a06e1f266e03c9a889f0fdc.bundle', 'f642335cb67f3bd7cff73e643820c31b.bundle',
                    '08ddc7152ef698844bbbea8b87f08fc8.bundle', 'ede71b08c97f7450f8708d94c6a2cef3.bundle',
                    '571e9cafeed79eefef694782d13e94b6.bundle'):
        continue
    data = z.read(n)
    try:
        env = UnityPy.load(io.BytesIO(data))
    except Exception as e:
        print('  %s -> UnityPy failed: %s' % (base, e))
        continue
    for o in env.objects:
        if o.type.name != 'Texture2D':
            continue
        try:
            d = o.read()
        except Exception:
            continue
        if (d.m_Name or '') != 'cengceng':
            continue
        f = getattr(d, 'm_TextureFormat', '?')
        print('  %-44s apkEntrySize=%-9d %dx%d fmt=%-4s %s' % (base, z.getinfo(n).file_size,
                                                               d.m_Width, d.m_Height, f, FMT.get(f, f)))
