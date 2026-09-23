using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// GATE 2 for the shader-reference migration: prove the materials really resolve
/// to the intended real shader and that their saved values survived.
///
/// A guid swap is only correct if the material now points at the expected shader
/// AND the properties the material actually stored are readable on that shader.
/// ASCII-only on purpose.
/// </summary>
public static class ShaderSampleVerify
{
    private static readonly string OutPath = @"<BUILD_DIR>\_cd\_shader_sample_verify.txt";
    private static readonly StringBuilder Sb = new StringBuilder();
    private static int _fail;

    private class Sample
    {
        public string Path;
        public string ExpectedShader;
        public string Family;
    }

    private static readonly Sample[] Samples =
    {
        new Sample { Path = "Assets/Material/orange kid Atlas Material.mat",
                     ExpectedShader = "TextMeshPro/Distance Field", Family = "TMP" },
        new Sample { Path = "Assets/Material/Sprite-Lit-Default.mat",
                     ExpectedShader = "Universal Render Pipeline/2D/Sprite-Lit-Default",
                     Family = "URP-2D" },
    };

    // properties that must exist for the family's look to survive.
    // Urp2DKeys lists what URP 14's Sprite-Lit-Default.shader actually declares
    // (verified against the package source).  An earlier version of this list also
    // demanded _ShapeLightParam, which is a Light2D GLOBAL, not a material
    // property, and that wrong expectation is what made the first run report a
    // failure.  The shader deliberately keeps [HideInInspector] legacy properties
    // so materials can fall back gracefully.
    private static readonly string[] TmpKeys = { "_MainTex", "_FaceTex", "_FaceColor", "_OutlineColor", "_OutlineWidth" };
    private static readonly string[] Urp2DKeys = { "_MainTex", "_MaskTex", "_NormalMap", "_Color", "_AlphaTex" };

    public static void Run()
    {
        Sb.AppendLine("=== GATE 2: shader reference migration sample check ===");
        Sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
        foreach (Sample s in Samples) Check(s);
        Sb.AppendLine();
        Sb.AppendLine("=== RESULT: " + (_fail == 0 ? "PASS" : ("FAIL (" + _fail + ")")) + " ===");
        File.WriteAllText(OutPath, Sb.ToString(), new UTF8Encoding(false));
        Debug.Log("[ShaderSampleVerify] wrote " + OutPath + " fail=" + _fail);
    }

    private static void Check(Sample s)
    {
        Sb.AppendLine();
        Sb.AppendLine("--- " + s.Family + ": " + s.Path);
        Material m = AssetDatabase.LoadAssetAtPath<Material>(s.Path);
        if (m == null) { Sb.AppendLine("  LOAD FAILED"); _fail++; return; }

        Shader sh = m.shader;
        string got = sh == null ? "(null)" : sh.name;
        Sb.AppendLine("  shader name      : " + got);
        Sb.AppendLine("  expected         : " + s.ExpectedShader);
        bool nameOk = got == s.ExpectedShader;
        Sb.AppendLine("  match            : " + nameOk);
        if (!nameOk) _fail++;
        Sb.AppendLine("  shader asset path: " + (sh == null ? "-" : AssetDatabase.GetAssetPath(sh)));
        Sb.AppendLine("  isSupported      : " + (sh != null && sh.isSupported));
        Sb.AppendLine("  renderQueue      : " + m.renderQueue);
        Sb.AppendLine("  passCount        : " + m.passCount);
        string[] kws = m.shaderKeywords;
        Sb.AppendLine("  shaderKeywords   : " + (kws == null || kws.Length == 0 ? "(none)" : string.Join(", ", kws)));

        // texture slots the material actually stores
        string[] texNames = m.GetTexturePropertyNames();
        int nonNull = 0;
        var sbTex = new List<string>();
        foreach (string t in texNames)
        {
            Texture tex = m.GetTexture(t);
            if (tex != null) nonNull++;
            sbTex.Add(t + "=" + (tex == null ? "null" : tex.name));
        }
        Sb.AppendLine("  texture props    : " + texNames.Length + "   non-null: " + nonNull);
        foreach (string t in sbTex.Take(12)) Sb.AppendLine("      " + t);

        string[] keys = s.Family == "TMP" ? TmpKeys : Urp2DKeys;
        Sb.AppendLine("  required properties present?");
        foreach (string k in keys)
        {
            bool has = m.HasProperty(k);
            Sb.AppendLine("      " + (has ? "OK  " : "MISS") + "  " + k);
            if (!has) _fail++;
        }

        // read back a few values so we can see real data rather than defaults
        Sb.AppendLine("  sampled values:");
        foreach (string k in new[] { "_Color", "_FaceColor", "_OutlineWidth", "_MainColor" })
        {
            if (!m.HasProperty(k)) continue;
            if (m.HasProperty(k))
            {
                try { Sb.AppendLine("      " + k + " (color) = " + m.GetColor(k)); } catch { }
                try { Sb.AppendLine("      " + k + " (float) = " + m.GetFloat(k)); } catch { }
            }
        }
    }
}
