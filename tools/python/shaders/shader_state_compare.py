"""shader_state_compare.py

The one asset layer that was never compared: the RENDER STATE of the Spine shaders.

Materials, textures, keywords, component fields and geometry all match the original, yet the
same mesh blends differently on our side.  A shader whose Blend/ZWrite/Cull/ColorMask/Stencil
state differs from the original would do exactly that, and our shaders come from an
AssetRipper export (i.e. from decompiled text), not from the original binary.

Part 1 dumps the original Windows bundles' compiled Shader objects for the Spine shader names
       (m_ParsedForm -> m_SubShaders -> m_Passes -> m_State).
Part 2 prints the same state as written in OUR project's .shader source files.
ASCII-only output.
"""

import os, glob, re, sys, collections

sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

ORIG = r'<ORIGINAL_BUILD>\TC_Data\StreamingAssets\dynamic_assets\RootPackage'
OURS = r'<UNITY_PROJECT>\Assets\AssetBundles'

WANT = ('Spine/SkeletonGraphic', 'Spine/SkeletonGraphic Multiply', 'Spine/SkeletonGraphic Additive',
        'Spine/Blend Modes/Skeleton PMA Additive', 'Spine/Blend Modes/Skeleton PMA Multiply',
        'Custom/SpriteLt', 'Custom/SpriteLt_UI', 'Spine/Skeleton')

STATE_KEYS = ('rtBlend0', 'rtBlend1', 'rtBlend2', 'rtBlend3', 'rtSeparateBlend',
              'zwrite', 'ztest', 'cull', 'colorMask', 'stencilRef', 'stencilReadMask',
              'stencilWriteMask', 'stencilOp', 'stencilComp', 'stencilPass', 'stencilFail', 'stencilZFail',
              'lighting', 'fogMode', 'offsetFactor', 'offsetUnits', 'alphaToMask')


def walk_state(st):
    out = {}
    if not isinstance(st, dict):
        return out
    for k in STATE_KEYS:
        if k in st:
            out[k] = st[k]
    return out


def orig_shaders():
    found = {}
    for b in sorted(glob.glob(os.path.join(ORIG, '*.bundle'))):
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
            nm = t.get('m_Name') or ''
            if nm not in WANT or nm in found:
                continue
            pf = t.get('m_ParsedForm') or {}
            subs = []
            for ss in (pf.get('m_SubShaders') or []):
                passes = []
                for p in (ss.get('m_Passes') or []):
                    passes.append({
                        'name': (p.get('m_Name') or ''),
                        'state': walk_state(p.get('m_State')),
                        'hasInstancing': (p.get('m_State') or {}).get('m_InstancingVariant'),
                    })
                subs.append({'tags': ss.get('m_Tags'), 'passes': passes})
            found[nm] = {'bundle': os.path.basename(b), 'propCount': len(pf.get('m_PropInfo', {}).get('m_Props', []) if isinstance(pf.get('m_PropInfo'), dict) else []),
                         'subshaders': subs,
                         'keywords': (pf.get('m_KeywordNames') or [])[:0]}
    return found


def our_shader_files():
    files = {}
    for f in glob.glob(os.path.join(OURS, '**', '*.shader'), recursive=True):
        try:
            txt = open(f, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        m = re.search(r'^\s*Shader\s+"([^"]+)"', txt, re.M)
        if not m:
            continue
        nm = m.group(1)
        if nm in files:
            continue
        # first pass block state lines
        state = []
        for line in txt.splitlines():
            s = line.strip()
            if re.match(r'^(Blend|BlendOp|ZWrite|ZTest|Cull|ColorMask|Offset|AlphaToMask|Lighting|Fog)\b', s):
                state.append(s)
            if s.startswith('Pass') and state:
                break
        pragmas = [l.strip() for l in txt.splitlines() if l.strip().startswith('#pragma')][:14]
        files[nm] = {'path': f.replace(OURS, 'AssetBundles'), 'state': state[:14], 'pragmas': pragmas,
                     'bytes': os.path.getsize(f)}
    return files


def main():
    o = orig_shaders()
    u = our_shader_files()
    print('=== ORIGINAL compiled shaders found (%d) ===' % len(o))
    for nm in WANT:
        if nm not in o:
            print('  %-45s NOT FOUND in original bundles' % nm)
            continue
        e = o[nm]
        print('  %-45s bundle=%s' % (nm, e['bundle']))
        for i, ss in enumerate(e['subshaders']):
            for j, p in enumerate(ss['passes']):
                st = p['state']
                print('      sub%d pass%d %-14s blend=%s/%s zwrite=%s ztest=%s cull=%s colorMask=%s'
                      % (i, j, p['name'], st.get('rtBlend0'), st.get('rtBlend1'),
                         st.get('zwrite'), st.get('ztest'), st.get('cull'), st.get('colorMask')))
    print()
    print('=== OUR shader source files named the same (%d total shaders scanned) ===' % len(u))
    for nm in WANT:
        if nm not in u:
            print('  %-45s NO FILE with this Shader name' % nm)
            continue
        e = u[nm]
        print('  %-45s %s (%d B)' % (nm, e['path'], e['bytes']))
        for s in e['state']:
            print('       %s' % s)
        print('       #pragmas: %s' % ' | '.join(e['pragmas'][:8]))
    print()
    print('=== every Shader name we have (for cross-checking) ===')
    for nm in sorted(u):
        print('   %s' % nm)


if __name__ == '__main__':
    main()
