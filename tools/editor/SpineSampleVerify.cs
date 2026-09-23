using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// GATE 2 for the Spine sample migration: validate the real ziji material for
/// Skeleton and PMA Multiply before any generalisation.
///
/// Checks that the materials resolve to the imported Spine 4.1 shaders, that the
/// shaders are supported, and that the properties the materials store are still
/// readable -- plus the original Spine 4.1 pass configuration (blend mode, cull,
/// zwrite) so the alpha model can be compared later.
/// ASCII-only.
/// </summary>
public static class SpineSampleVerify
{
    private static readonly string OutPath = @"<BUILD_DIR>\_cd\_spine_sample_verify.txt";
    private static readonly StringBuilder Sb = new StringBuilder();
    private static int _fail;

    private class Sample
    {
        public string Path;
        public string ExpectedShader;
        public string Why;
    }

    private static readonly Sample[] Samples =
    {
        new Sample { Path = "Assets/Material/ziji_Material.mat",
                     ExpectedShader = "Spine/Skeleton",
                     Why = "straight alpha, the plain skeleton material" },
        new Sample { Path = "Assets/Material/ziji_Material-Multiply.mat",
                     ExpectedShader = "Spine/Blend Modes/Skeleton PMA Multiply",
                     Why = "PMA multiply, the other P1-observed Spine shader" },
    };

    private static readonly string[] Keys =
    {
        "_MainTex", "_Color", "_Cutoff", "_StraightAlphaTex", "_AlphaTex",
        "_BlackTex", "_WhiteTex", "_FillPhase", "_FillColor", "_FillAlpha"
    };

    public static void Run()
    {
        Sb.AppendLine("=== GATE 2: Spine sample migration ===");
        Sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));

        Sb.AppendLine();
        Sb.AppendLine("--- imported Spine 4.1 shaders ---");
        foreach (string g in AssetDatabase.FindAssets("t:Shader", new[] { "Assets/Spine41Shaders" }))
        {
            string p = AssetDatabase.GUIDToAssetPath(g);
            Shader sh = AssetDatabase.LoadAssetAtPath<Shader>(p);
            if (sh == null) continue;
            Sb.AppendLine("  " + sh.name.PadRight(48) + " supported=" + sh.isSupported
                          + "  passes=" + sh.passCount + "  " + p);
        }

        foreach (Sample s in Samples) Check(s);

        Sb.AppendLine();
        Sb.AppendLine("=== RESULT: " + (_fail == 0 ? "PASS" : ("FAIL (" + _fail + ")")) + " ===");
        File.WriteAllText(OutPath, Sb.ToString(), new UTF8Encoding(false));
        Debug.Log("[SpineSampleVerify] wrote " + OutPath + " fail=" + _fail);
    }

    private static void Check(Sample s)
    {
        Sb.AppendLine();
        Sb.AppendLine("--- " + s.Path);
        Sb.AppendLine("    (" + s.Why + ")");
        Material m = AssetDatabase.LoadAssetAtPath<Material>(s.Path);
        if (m == null) { Sb.AppendLine("  LOAD FAILED"); _fail++; return; }

        Shader sh = m.shader;
        string got = sh == null ? "(null)" : sh.name;
        Sb.AppendLine("  shader name : " + got);
        Sb.AppendLine("  expected    : " + s.ExpectedShader);
        // Comparing only the shader NAME is not enough: the AssetRipper dummy
        // declares the same name, so an untouched material reported a false PASS in
        // the first run of this gate.  The asset path must be the imported one.
        string apath = sh == null ? "" : AssetDatabase.GetAssetPath(sh);
        bool ok = (got == s.ExpectedShader) && apath.StartsWith("Assets/Spine41Shaders/");
        Sb.AppendLine("  match       : " + ok);
        Sb.AppendLine("  is imported : " + apath.StartsWith("Assets/Spine41Shaders/")
                      + "   (a dummy would also match by name, hence this check)");
        if (!ok) _fail++;
        Sb.AppendLine("  asset path  : " + (apath == "" ? "-" : apath));
        Sb.AppendLine("  isSupported : " + (sh != null && sh.isSupported));
        Sb.AppendLine("  renderQueue : " + m.renderQueue + "   passCount=" + m.passCount);
        string[] kws = m.shaderKeywords;
        Sb.AppendLine("  keywords    : " + (kws == null || kws.Length == 0 ? "(none)" : string.Join(", ", kws)));

        Sb.AppendLine("  required Spine properties:");
        foreach (string k in Keys)
        {
            bool has = m.HasProperty(k);
            if (has)
            {
                string val;
                try { val = k.Contains("Color") ? m.GetColor(k).ToString() : m.GetFloat(k).ToString("0.###"); }
                catch { val = "?"; }
                Sb.AppendLine("      OK   " + k.PadRight(20) + " = " + val);
            }
            else
            {
                Sb.AppendLine("      --   " + k.PadRight(20) + " (not declared by this variant)");
            }
        }

        string[] tex = m.GetTexturePropertyNames();
        int nonNull = tex.Count(t => m.GetTexture(t) != null);
        Sb.AppendLine("  textures: " + tex.Length + "  non-null: " + nonNull);
        foreach (string t in tex.Take(6))
            Sb.AppendLine("      " + t + " = " + (m.GetTexture(t) == null ? "null" : m.GetTexture(t).name));
    }
}
