"""allin1_check.py -- is our AllIn1SpriteShader a stub, and how many properties does it expose?"""
import re, os, sys, glob
sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

OURS = r'<UNITY_PROJECT>\Assets\Resources'
ORIG = r'<ORIGINAL_BUILD>\TC_Data\StreamingAssets\dynamic_assets\RootPackage'
FILES = ['allin1spriteshader.shader', 'allin1spriteshaderscaledtime.shader',
         'allin1spriteshaderuimask.shader', 'allin1spriteshaderuimaskscaledtime.shader',
         'allin1urp2drenderer.shader']

print('=== our AllIn1 shader files ===')
for fn in FILES:
    p = os.path.join(OURS, fn)
    if not os.path.exists(p):
        print('  MISSING %s' % fn)
        continue
    txt = open(p, encoding='utf-8', errors='replace').read()
    body = txt.split('Properties', 1)[1].split('SubShader', 1)[0] if 'Properties' in txt else ''
    props = re.findall(r'(_[A-Za-z0-9_]+)\s*\(', body)
    has_blend = bool(re.search(r'^\s*Blend\b', txt, re.M))
    opq = '"RenderType"="Opaque"' in txt.replace(' ', '')
    dummy = 'DummyShaderTextExporter' in txt
    print('  %-42s %6d B  props=%3d  Blend=%-5s RenderTypeOpaque=%-5s dummyMarker=%s'
          % (fn, os.path.getsize(p), len(props), has_blend, opq, dummy))

print()
print('=== original AllIn1 shaders in bundles ===')
want = {
    'AllIn1SpriteShader/AllIn1SpriteShader': None,
    'AllIn1SpriteShader/AllIn1SpriteShaderScaledTime': None,
    'AllIn1SpriteShader/AllIn1SpriteShaderUiMask': None,
    'AllIn1SpriteShader/AllIn1SpriteShaderUiMaskScaledTime': None,
    'AllIn1SpriteShader/AllIn1Urp2dRenderer': None,
}
for b in sorted(glob.glob(os.path.join(ORIG, '*.bundle'))):
    if all(v is not None for v in want.values()):
        break
    try:
        env = UnityPy.load(b)
    except Exception:
        continue
    for o in env.objects:
        if o.type.name != 'Shader':
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        pf = t.get('m_ParsedForm') or {}
        nm = pf.get('m_Name') or ''
        if nm in want and want[nm] is None:
            props = [x.get('m_Name') for x in ((pf.get('m_PropInfo') or {}).get('m_Props') or [])]
            want[nm] = (len(props), props)
for nm, v in want.items():
    if v is None:
        print('  %-50s NOT FOUND in bundles' % nm)
    else:
        print('  %-50s props=%3d  first: %s' % (nm, v[0], ', '.join([p for p in v[1][:12]])))
