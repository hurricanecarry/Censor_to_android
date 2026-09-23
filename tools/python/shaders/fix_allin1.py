"""fix_allin1.py

Replace the AllIn1SpriteShader stubs' render body with a CORRECT transparent sprite pass.

What is wrong today: AssetRipper's dummy exporter kept the full property block (180/184/185
properties, including `_MySrcMode`/`_MyDstMode` whose defaults are 5/10 = SrcAlpha/
OneMinusSrcAlpha) but replaced the code with `return _MainTex.Sample(..) * _Color;` under
`Tags { "RenderType"="Opaque" }` with no Blend statement.  The six materials that use it
therefore draw OPAQUE with no alpha whatsoever, and none of the 180 effects run.

What this does NOT do: reconstruct the 180 effects (glow, fade, outline, gradient, shine, blur,
chromatic aberration, distortion, overlay ...).  Those remain missing; this fix only makes the
six materials blend and tint the way their own material settings ask for, which removes the
"opaque box" class of error.  Stated explicitly so the delivery note does not overclaim.

Files patched:
  * Assets/AssetBundles/.../mainpanel/Shader/AllIn1SpriteShader_AllIn1SpriteShader.shader
  * Assets/AssetBundles/.../singnotespanel/Shader/AllIn1SpriteShader_AllIn1SpriteShader.shader
    (these two are the ones the six materials actually reference -> require a bundle rebuild)
  * Assets/Resources/allin1*.shader (5 files, ship in the player; no material references the
    URP variant)

ASCII-only output.
"""

import io, os, re, shutil, sys

PROJ = r'<UNITY_PROJECT>'
BACKUP = r'<BUILD_DIR>\_probe\allin1_fix_backup'

TARGETS = [
    'Assets/AssetBundles/rootpackage_assets_art_uipanels_mainpanel_mainpanel/Shader/AllIn1SpriteShader_AllIn1SpriteShader.shader',
    'Assets/AssetBundles/rootpackage_assets_art_uipanels_singnotespanel/Shader/AllIn1SpriteShader_AllIn1SpriteShader.shader',
    'Assets/Resources/allin1spriteshader.shader',
    'Assets/Resources/allin1spriteshaderscaledtime.shader',
    'Assets/Resources/allin1spriteshaderuimask.shader',
    'Assets/Resources/allin1spriteshaderuimaskscaledtime.shader',
    'Assets/Resources/allin1urp2drenderer.shader',
]

HEAD = '''	SubShader{
		Tags { "Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent" "PreviewType"="Plane" "CanUseSpriteAtlas"="True" }
		LOD 200
'''

STENCIL = '''
		Stencil
		{
			Ref [_Stencil]
			Comp [_StencilComp]
			Pass [_StencilOp]
			ReadMask [_StencilReadMask]
			WriteMask [_StencilWriteMask]
		}
'''

STATE_PLAIN = '''
		Cull Off
		Lighting Off
		ZWrite Off
		Blend [_MySrcMode] [_MyDstMode]
'''

STATE_UI = '''
		Cull Off
		Lighting Off
		ZWrite Off
		ZTest [unity_GUIZTestMode]
		Blend [_MySrcMode] [_MyDstMode]
		ColorMask [_ColorMask]
'''

PASS = '''
		Pass
		{
			HLSLPROGRAM
			#pragma vertex vert
			#pragma fragment frag
			#pragma shader_feature_local PREMULTIPLYALPHA_ON

			float4x4 unity_ObjectToWorld;
			float4x4 unity_MatrixVP;
			float4 _MainTex_ST;

			struct Vertex_Stage_Input
			{
				float4 pos : POSITION;
				float2 uv : TEXCOORD0;
			};

			struct Vertex_Stage_Output
			{
				float2 uv : TEXCOORD0;
				float4 pos : SV_POSITION;
			};

			Vertex_Stage_Output vert(Vertex_Stage_Input input)
			{
				Vertex_Stage_Output output;
				output.uv = (input.uv.xy * _MainTex_ST.xy) + _MainTex_ST.zw;
				output.pos = mul(unity_MatrixVP, mul(unity_ObjectToWorld, input.pos));
				return output;
			}

			Texture2D<float4> _MainTex;
			SamplerState sampler_MainTex;
			float4 _Color;
			float _Alpha;

			struct Fragment_Stage_Input
			{
				float2 uv : TEXCOORD0;
			};

			float4 frag(Fragment_Stage_Input input) : SV_TARGET
			{
				float4 c = _MainTex.Sample(sampler_MainTex, input.uv.xy) * _Color;
				c.a *= _Alpha;
				#ifdef PREMULTIPLYALPHA_ON
				c.rgb *= c.a;
				#endif
				return c;
			}

			ENDHLSL
		}
	}
'''


def patch(rel):
    src = os.path.join(PROJ, rel.replace('/', os.sep))
    txt = io.open(src, encoding='utf-8', errors='replace').read()
    props = txt.split('SubShader', 1)[0]
    is_ui = ('_StencilComp' in props) and ('_ColorMask' in props)
    lines = txt.splitlines()
    i = next((k for k, l in enumerate(lines) if l.strip().startswith('SubShader')), None)
    if i is None:
        return rel, 'NO SubShader'
    j = next((k for k, l in enumerate(lines) if l.strip().startswith('//CustomEditor')), None)
    if j is None or j < i:
        j = len(lines)
        # find the final closing brace of the Shader block
        while j > 0 and lines[j - 1].strip() == '':
            j -= 1
        j -= 1
    body = HEAD + (STENCIL if is_ui else '') + (STATE_UI if is_ui else STATE_PLAIN) + PASS
    new = lines[:i] + body.splitlines() + lines[j:]
    out = '\n'.join(new) + ('\n' if txt.endswith('\n') else '')
    io.open(src, 'w', encoding='utf-8', newline='').write(out)
    has_blend = bool(re.search(r'(?m)^\s*Blend\b', out))
    return rel, ('patched ui=%s size %d -> %d blend=%s' % (is_ui, len(txt), len(out), has_blend))


def main():
    if os.path.isdir(BACKUP):
        shutil.rmtree(BACKUP)
    for rel in TARGETS:
        src = os.path.join(PROJ, rel.replace('/', os.sep))
        if not os.path.exists(src):
            print('MISSING %s' % rel)
            continue
        dst = os.path.join(BACKUP, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        r, msg = patch(rel)
        print('%-110s %s' % (os.path.basename(rel), msg))
    print('backup: %s' % BACKUP)


if __name__ == '__main__':
    main()
