"""spine_shader_state.py

The Spine shaders are NOT inside the AssetBundles - a bundle material may reference a shader
that lives in the player's global data.  So the earlier "shader state" scan found nothing.

This script therefore compares the two players' OWN data:
  ORIGINAL: TC_Data/*.assets, level*, globalgamemanagers.assets  (Windows player)
  OURS    : every *.shader file under Assets that is NOT under Assets/AssetBundles
            (those files ship in the APK's player data, not in a YooAsset bundle)

for the Spine / Custom / UI shader families, printing the render state that decides blending.
ASCII-only output.
"""

import os, glob, re, sys, collections

sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

ORIG_DATA = r'<ORIGINAL_BUILD>\TC_Data'
ASSETS = r'<UNITY_PROJECT>\Assets'

PREFIX = ('Spine/', 'Custom/SpriteLt', 'UI/Additive', 'MyShaders/', 'Shader Graphs/', 'AllIn1SpriteShader/')

STATE_KEYS = ('rtBlend0', 'rtBlend1', 'rtSeparateBlend', 'zwrite', 'ztest', 'cull', 'colorMask',
              'alphaToMask', 'lighting', 'fogMode', 'stencilRef', 'stencilComp', 'stencilOp')


def orig_player_shaders():
    found = {}
    files = []
    files += sorted(glob.glob(os.path.join(ORIG_DATA, '*.assets')))
    files += sorted(glob.glob(os.path.join(ORIG_DATA, 'level*')))
    files += sorted(glob.glob(os.path.join(ORIG_DATA, 'globalgamemanagers*')))
    print('scanning %d original player data files' % len(files))
    for f in files:
        try:
            env = UnityPy.load(f)
        except Exception as e:
            print('   load fail %s: %s' % (os.path.basename(f), e))
            continue
        for o in env.objects:
            if o.type.name != 'Shader':
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue
            nm = t.get('m_Name') or ''
            if not nm.startswith(PREFIX) or nm in found:
                continue
            pf = t.get('m_ParsedForm') or {}
            passes = []
            for ss in (pf.get('m_SubShaders') or []):
                for p in (ss.get('m_Passes') or []):
                    st = p.get('m_State') or {}
                    passes.append({'name': p.get('m_Name') or '',
                                   'state': dict((k, st[k]) for k in STATE_KEYS if k in st)})
            found[nm] = {'file': os.path.basename(f), 'passes': passes,
                         'keywords': list(pf.get('m_KeywordNames') or [])}
    return found


def our_shader_files():
    found = {}
    for f in glob.glob(os.path.join(ASSETS, '**', '*.shader'), recursive=True):
        if os.sep + 'AssetBundles' + os.sep in f:
            continue
        try:
            txt = open(f, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        m = re.search(r'^\s*Shader\s+"([^"]+)"', txt, re.M)
        if not m:
            continue
        nm = m.group(1)
        if not nm.startswith(PREFIX) or nm in found:
            continue
        state = []
        for line in txt.splitlines():
            s = line.strip()
            if re.match(r'^(Blend|BlendOp|ZWrite|ZTest|Cull|ColorMask|Offset|AlphaToMask|Lighting|Fog)\b', s):
                state.append(s)
        found[nm] = {'path': f.replace(ASSETS, 'Assets'), 'state': state[:16],
                     'bytes': os.path.getsize(f),
                     'keywords': re.findall(r'#pragma\s+multi_compile\w*\s+([^\n]+)', txt)[:6]}
    return found


def main():
    o = orig_player_shaders()
    u = our_shader_files()
    print()
    print('=== ORIGINAL player-data shaders in our families: %d ===' % len(o))
    for nm in sorted(o):
        e = o[nm]
        print('  %s   (%s)' % (nm, e['file']))
        for p in e['passes'][:3]:
            st = p['state']
            print('      pass %-10s blend=%s/%s sep=%s zwrite=%s ztest=%s cull=%s colorMask=%s a2m=%s'
                  % (p['name'], st.get('rtBlend0'), st.get('rtBlend1'), st.get('rtSeparateBlend'),
                     st.get('zwrite'), st.get('ztest'), st.get('cull'), st.get('colorMask'),
                     st.get('alphaToMask')))
    print()
    print('=== OUR shader files outside AssetBundles in the same families: %d ===' % len(u))
    for nm in sorted(u):
        e = u[nm]
        print('  %s   (%s, %d B)' % (nm, e['path'], e['bytes']))
        for s in e['state']:
            print('      %s' % s)
    print()
    print('=== name-level diff ===')
    only_o = sorted(set(o) - set(u))
    only_u = sorted(set(u) - set(o))
    both = sorted(set(o) & set(u))
    print('  both=%d  onlyOriginal=%d  onlyOurs=%d' % (len(both), len(only_o), len(only_u)))
    if only_o:
        print('  only original: %s' % ', '.join(only_o[:25]))
    if only_u:
        print('  only ours    : %s' % ', '.join(only_u[:25]))


if __name__ == '__main__':
    main()
