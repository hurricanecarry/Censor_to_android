using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Export the P1 dependency closure.
///
/// P1 roots, established from the real code and from the shipped YooAsset
/// manifest rather than guessed:
///   * Assets/Main.unity                            (the entry scene)
///   * UI_MainUI          -> UIManager.LoadUIs() AssetsManager.LoadSync("UI_MainUI")
///   * UI_StartGamePanel  -> GameRunner ... UIManager.Open&lt;StartGamePanelUI&gt;()
///   * UI_LoadingScenePanel, UI_MainPanel (the panel behind the main menu)
///   * the manifest closure of those bundles: UI_MainPanel depends on
///     rootpackage_assets_art_uipanels_common_textures_chaospic
///   * ALL of Assets/Resources/**   -- always shipped and loadable by name, so it
///     belongs to every closure regardless of serialized references
///   * the URP default materials referenced by Renderer2DData fields
///
/// For each root this records AssetDatabase.GetDependencies(root, true), then
/// reports every Shader and Material that ends up inside, so the P1 shader set is
/// decided by real references instead of by name heuristics.
///
/// ASCII-only on purpose.
/// </summary>
public static class P1Closure
{
    private static readonly string OutDir = @"<BUILD_DIR>\_cd";
    private static readonly string DepsPath = Path.Combine(OutDir, "_p1_deps.tsv");
    private static readonly string ShadersPath = Path.Combine(OutDir, "_p1_shaders.tsv");
    private static readonly string MatsPath = Path.Combine(OutDir, "_p1_materials.tsv");

    private static readonly string[] Roots =
    {
        "Assets/Main.unity",
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainui/art/uipanels/MainUI.prefab",
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_startgamepanel_startgamepanel/art/uipanels/startgamepanel/StartGamePanel.prefab",
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_loadingscenepanel_loadingscenepanel/art/uipanels/loadingscenepanel/LoadingScenePanel.prefab",
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainpanel_mainpanel/art/uipanels/mainpanel/MainPanel.prefab",
        "Assets/MonoBehaviour/Renderer2D.asset",
        "Assets/MonoBehaviour/UniversalRenderPipelineGlobalSettings.asset"
    };

    public static void Run()
    {
        var sb = new StringBuilder();
        sb.AppendLine("root\tdependency\ttype\tguid\tisDummyShader");

        var rootSet = new List<string>(Roots);
        // every asset under Resources is reachable by name at runtime
        foreach (string g in AssetDatabase.FindAssets("", new[] { "Assets/Resources" }))
        {
            string p = AssetDatabase.GUIDToAssetPath(g);
            if (!string.IsNullOrEmpty(p) && !p.EndsWith(".meta"))
                rootSet.Add(p);
        }
        // plus the whole P1 bundle folders, so nothing inside them is missed
        foreach (string dir in new[]
                 {
                     "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainui",
                     "Assets/AssetBundles/rootpackage_assets_art_uipanels_startgamepanel_startgamepanel",
                     "Assets/AssetBundles/rootpackage_assets_art_uipanels_loadingscenepanel_loadingscenepanel",
                     "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainpanel_mainpanel",
                     "Assets/AssetBundles/rootpackage_assets_art_uipanels_common_textures_chaospic"
                 })
        {
            foreach (string g in AssetDatabase.FindAssets("", new[] { dir }))
            {
                string p = AssetDatabase.GUIDToAssetPath(g);
                if (!string.IsNullOrEmpty(p) && !p.EndsWith(".meta"))
                    rootSet.Add(p);
            }
        }

        Debug.Log("[P1Closure] roots (after expanding Resources and P1 bundles): " + rootSet.Count);

        var depOf = new Dictionary<string, HashSet<string>>();   // dep -> roots that pull it
        foreach (string root in rootSet.Distinct())
        {
            string[] deps;
            try
            {
                deps = AssetDatabase.GetDependencies(root, true);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[P1Closure] GetDependencies failed for " + root + ": " + e.Message);
                continue;
            }
            foreach (string d in deps)
            {
                if (d == root) continue;
                if (!depOf.TryGetValue(d, out HashSet<string> set))
                {
                    set = new HashSet<string>();
                    depOf[d] = set;
                }
                set.Add(root);
            }
        }

        var shaderRows = new StringBuilder();
        shaderRows.AppendLine("shaderPath\tshaderName\tguid\tisDummy\treferencedFromRoots");
        var matRows = new StringBuilder();
        matRows.AppendLine("materialPath\tguid\tm_ScriptOrShader");
        int shaderCount = 0, matCount = 0;

        foreach (var kv in depOf.OrderBy(k => k.Key))
        {
            string path = kv.Key;
            string guid = AssetDatabase.AssetPathToGUID(path);
            string type = AssetDatabase.GetMainAssetTypeAtPath(path) != null
                ? AssetDatabase.GetMainAssetTypeAtPath(path).Name : "?";
            bool dummy = false;
            if (path.EndsWith(".shader"))
            {
                try
                {
                    string txt = File.ReadAllText(path);
                    dummy = txt.Contains("DummyShaderTextExporter");
                    string nm = "";
                    foreach (string line in txt.Split('\n'))
                    {
                        string t = line.TrimStart();
                        if (t.StartsWith("Shader "))
                        {
                            int a = t.IndexOf('"'), b = t.LastIndexOf('"');
                            if (a >= 0 && b > a) nm = t.Substring(a + 1, b - a - 1);
                            break;
                        }
                    }
                    shaderRows.AppendLine(string.Join("\t", new[]
                    {
                        path, nm, guid, dummy ? "1" : "0", kv.Value.Count.ToString()
                    }));
                    shaderCount++;
                }
                catch (Exception e)
                {
                    Debug.LogWarning("[P1Closure] shader read failed " + path + ": " + e.Message);
                }
            }
            else if (path.EndsWith(".mat"))
            {
                string shaderGuid = "";
                try
                {
                    foreach (string line in File.ReadAllLines(path))
                    {
                        if (line.Contains("m_Shader:"))
                        {
                            int i = line.IndexOf("guid:");
                            if (i >= 0)
                            {
                                string rest = line.Substring(i + 5).Trim();
                                int c = rest.IndexOf(',');
                                shaderGuid = c > 0 ? rest.Substring(0, c).Trim() : rest.Trim(' ', '}');
                            }
                            break;
                        }
                    }
                }
                catch { }
                matRows.AppendLine(path + "\t" + guid + "\t" + shaderGuid);
                matCount++;
            }
            sb.AppendLine(string.Join("\t", new[] { path, type, guid, dummy ? "1" : "0" }));
        }

        // re-emit with the root column properly
        var final = new StringBuilder();
        final.AppendLine("dependency\ttype\tguid\tisDummyShader\trootCount");
        foreach (var kv in depOf.OrderBy(k => k.Key))
        {
            string path = kv.Key;
            string guid = AssetDatabase.AssetPathToGUID(path);
            string type = AssetDatabase.GetMainAssetTypeAtPath(path) != null
                ? AssetDatabase.GetMainAssetTypeAtPath(path).Name : "?";
            bool dummy = path.EndsWith(".shader") && File.ReadAllText(path).Contains("DummyShaderTextExporter");
            final.AppendLine(string.Join("\t", new[]
            {
                path, type, guid, dummy ? "1" : "0", kv.Value.Count.ToString()
            }));
        }

        File.WriteAllText(DepsPath, final.ToString(), new UTF8Encoding(false));
        File.WriteAllText(ShadersPath, shaderRows.ToString(), new UTF8Encoding(false));
        File.WriteAllText(MatsPath, matRows.ToString(), new UTF8Encoding(false));

        Debug.Log("[P1Closure] distinct dependencies: " + depOf.Count
                  + "   shaders: " + shaderCount + "   materials: " + matCount);
        Debug.Log("[P1Closure] wrote " + DepsPath);
    }
}
