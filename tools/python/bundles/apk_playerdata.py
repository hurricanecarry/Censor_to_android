import sys, os, io, zipfile, time
sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

APK = r'<BUILD_DIR>\_probe\CensorPort_P1_b45.apk'
FMT = {1:'Alpha8',4:'RGBA32',5:'ARGB32',10:'DXT1',12:'DXT5',34:'ETC_RGB4',45:'ETC2_RGB4',
       47:'ETC2_RGBA8',48:'ASTC_4x4',49:'ASTC_5x5',50:'ASTC_6x6',51:'ASTC_8x8',63:'ASTC_12x12'}

t0 = time.time()
z = zipfile.ZipFile(APK)
entries = z.namelist()

# player-build serialized data lives under assets/bin/Data
data_entries = [n for n in entries if n.startswith('assets/bin/Data/') and not n.endswith('/')]
print('player data entries: %d' % len(data_entries))
for n in data_entries[:20]:
    print('   %-46s %d' % (n, z.getinfo(n).file_size))

print()
print('=== scanning the player data for any Texture2D named cengceng ===')
hits = 0
for n in data_entries:
    size = z.getinfo(n).file_size
    if size < 4096:
        continue
    try:
        blob = z.read(n)
    except Exception as e:
        print('  read fail %s %s' % (n, e))
        continue
    try:
        env = UnityPy.load(io.BytesIO(blob))
    except Exception:
        continue
    try:
        for o in env.objects:
            if o.type.name != 'Texture2D':
                continue
            try:
                d = o.read()
            except Exception:
                continue
            nm = getattr(d, 'm_Name', '') or ''
            if 'cengceng' in nm.lower():
                f = getattr(d, 'm_TextureFormat', '?')
                print('  HIT %-30s %-24s %dx%d fmt=%-4s %s' % (n.split('/')[-1], nm, d.m_Width, d.m_Height, f, FMT.get(f, f)))
                hits += 1
    except Exception as e:
        pass

print('  cengceng Texture2D found in player data: %d' % hits)
print('elapsed %.1f s' % (time.time() - t0))
