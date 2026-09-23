using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// 灰度发布后的复核项：
///   * the real entry scene and the key UI / pipeline assets must have ZERO
///     missing scripts after the reference migration;
///   * the migrated component types must resolve to the expected managed types.
///
/// The scene is opened additively-free (single) in batch mode and inspected, then
/// closed without saving.  ASCII-only on purpose.
/// </summary>
public static class PostRolloutVerify
{
    private static readonly string OutPath = @"<BUILD_DIR>\_cd\_post_rollout.txt";
    private static readonly StringBuilder Sb = new StringBuilder();
    private static int _fail;

    private const string ScenePath = "Assets/Main.unity";
    private static readonly string[] KeyAssets =
    {
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainpanel_mainpanel/art/uipanels/mainpanel/MainPanel.prefab",
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_startgamepanel_startgamepanel/art/uipanels/startgamepanel/StartGamePanel.prefab",
        "Assets/MonoBehaviour/Renderer2D.asset",
        "Assets/UniversalRenderPipelineGlobalSettings.asset",
        "Assets/MonoBehaviour/UniversalRenderPipelineGlobalSettings.asset",
        "Assets/Resources/TMP Settings.asset"
    };

    public static void Run()
    {
        Sb.AppendLine("=== POST-ROLLOUT VERIFICATION ===");
        Sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));

        CheckScene();
        foreach (string a in KeyAssets) CheckAsset(a);

        Sb.AppendLine();
        Sb.AppendLine("=== RESULT: " + (_fail == 0 ? "PASS" : ("FAIL (" + _fail + ")")) + " ===");
        File.WriteAllText(OutPath, Sb.ToString(), new UTF8Encoding(false));
        Debug.Log("[PostRolloutVerify] wrote " + OutPath + " fail=" + _fail);
    }

    private static void CheckScene()
    {
        Sb.AppendLine();
        Sb.AppendLine("--- scene: " + ScenePath);
        if (!File.Exists(Path.Combine(Directory.GetCurrentDirectory(), ScenePath)))
        {
            Sb.AppendLine("  file not found");
            _fail++;
            return;
        }
        Scene scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        if (!scene.IsValid())
        {
            Sb.AppendLine("  could not open scene");
            _fail++;
            return;
        }
        Sb.AppendLine("  opened: " + scene.name + "  rootObjects=" + scene.rootCount);

        var all = new List<Component>();
        foreach (GameObject root in scene.GetRootGameObjects())
            all.AddRange(root.GetComponentsInChildren<Component>(true));

        int missing = all.Count(c => c == null);
        Sb.AppendLine("  components: " + all.Count + "   NULL (Missing Script): " + missing);
        if (missing != 0) _fail++;

        var hist = all.Where(c => c != null).GroupBy(c => c.GetType().FullName)
                      .OrderByDescending(g => g.Count()).Take(25).ToList();
        Sb.AppendLine("  top component types:");
        foreach (var g in hist) Sb.AppendLine("     " + g.Count().ToString().PadLeft(5) + "  " + g.Key);

        // the pipeline assets the scene depends on must be resolvable, not null
        var cams = all.OfType<Camera>().ToList();
        Sb.AppendLine("  cameras: " + cams.Count);
        foreach (Camera c in cams.Take(4))
            Sb.AppendLine("     " + c.name + "  pipelineAsset=" +
                          (c.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>() == null
                              ? "(no URP camera data)" : "URP camera data present"));
    }

    private static void CheckAsset(string path)
    {
        Sb.AppendLine();
        Sb.AppendLine("--- asset: " + path);
        UnityEngine.Object obj = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(path);
        if (obj == null)
        {
            Sb.AppendLine("  LOAD FAILED");
            _fail++;
            return;
        }
        Sb.AppendLine("  type: " + obj.GetType().FullName);

        var go = obj as GameObject;
        if (go == null)
        {
            var so = new SerializedObject(obj);
            SerializedProperty sp = so.FindProperty("m_Script");
            MonoScript ms = sp != null ? sp.objectReferenceValue as MonoScript : null;
            Sb.AppendLine("  m_Script -> " + (ms == null ? "(null)" : ms.name) +
                          "   GetClass=" + (ms != null && ms.GetClass() != null ? ms.GetClass().FullName : "(null)"));
            if (ms == null || ms.GetClass() == null || ms.GetClass() != obj.GetType()) _fail++;
            return;
        }

        Component[] comps = go.GetComponentsInChildren<Component>(true);
        int missing = comps.Count(c => c == null);
        Sb.AppendLine("  components: " + comps.Length + "   NULL (Missing Script): " + missing);
        if (missing != 0) _fail++;
        var hist = comps.Where(c => c != null).GroupBy(c => c.GetType().FullName)
                        .OrderByDescending(g => g.Count()).Take(20).ToList();
        foreach (var g in hist) Sb.AppendLine("     " + g.Count().ToString().PadLeft(5) + "  " + g.Key);
    }
}
