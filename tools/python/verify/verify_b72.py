"""verify_b72.py

Offline verification of b72:
  1. the baked QualitySettings.m_CurrentQuality must now be 5 (Ultra), matching the original
     Windows player, instead of 2 (Medium)
  2. the APK must carry the new RootPackage manifest and the DLCPackage (5 bundles)
  3. the COMPILED AllIn1SpriteShader inside the rebuilt bundle must now show a transparent
     subshader whose blend is bound to _MySrcMode/_MyDstMode - i.e. the patch reached the
     shipped bundle data, not just the source file

ASCII-only output.
"""

import io, os, sys, zipfile, json

sys.path.insert(0, r'<PY_DEPS>')   # UnityPy 等第三方解码库目录
import UnityPy

APK = r'<BUILD_DIR>\_probe\CensorPort_P1_b72.apk'
BUNDLES = r'<UNITY_PROJECT>\Assets\StreamingAssets\dynamic_assets\RootPackage'
TMP = r'<BUILD_DIR>\_cd\_b72_ggm.bin'


def main():
    z = zipfile.ZipFile(APK)

    print('=== 1. baked quality level ===')
    open(TMP, 'wb').write(z.read('assets/bin/Data/globalgamemanagers'))
    env = UnityPy.load(TMP)
    for o in env.objects:
        if o.type.name == 'QualitySettings':
            t = o.read_typetree()
            q = t.get('m_CurrentQuality')
            print('   QualitySettings.m_CurrentQuality = %s   (original Windows = 5, b71 = 2)  %s'
                  % (q, 'OK' if q == 5 else 'MISMATCH'))
        elif o.type.name == 'PlayerSettings':
            t = o.read_typetree()
            print('   m_ActiveColorSpace = %s' % t.get('m_ActiveColorSpace'))

    print()
    print('=== 2. manifests and bundles inside the APK ===')
    import hashlib
    for name in ('RootPackage', 'DLCPackage'):
        try:
            b = z.read('assets/dynamic_assets/%s/PackageManifest_%s_1.0.bytes' % (name, name))
            n = len([x for x in z.namelist()
                     if x.startswith('assets/dynamic_assets/%s/' % name) and x.endswith('.bundle')])
            print('   %-12s manifest %d B sha=%s   bundles=%d' % (name, len(b), hashlib.sha256(b).hexdigest()[:16], n))
        except KeyError:
            print('   %-12s MANIFEST MISSING' % name)

    print()
    print('=== 3. compiled AllIn1 state inside the rebuilt bundle ===')
    found = 0
    for f in sorted(os.listdir(BUNDLES)):
        if not f.endswith('.bundle'):
            continue
        env = UnityPy.load(os.path.join(BUNDLES, f))
        for o in env.objects:
            if o.type.name != 'Shader':
                continue
            t = o.read_typetree()
            pf = t.get('m_ParsedForm') or {}
            if (pf.get('m_Name') or '') != 'AllIn1SpriteShader/AllIn1SpriteShader':
                continue
            found += 1
            subs = pf.get('m_SubShaders') or []
            tags = subs[0].get('m_Tags') if subs else None
            st = (subs[0].get('m_Passes') or [{}])[0].get('m_State') or {}
            def bl(k):
                v = st.get(k)
                return '%s(%s)' % (v.get('name'), v.get('val')) if isinstance(v, dict) else str(v)
            print('   bundle %s' % f[:20])
            print('      subshader tags : %s' % str(tags)[:160])
            print('      rtBlend0=%s  rtBlend1=%s  zwrite=%s  cull=%s' % (bl('rtBlend0'), bl('rtBlend1'), st.get('zwrite'), st.get('cull')))
    if found == 0:
        print('   no AllIn1SpriteShader found in the rebuilt bundles')


if __name__ == '__main__':
    main()
