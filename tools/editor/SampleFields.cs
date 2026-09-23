using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Dump, for one real instance of every migrated component type, the COMPLETE
/// serialized property path list that the NEW managed type actually exposes.
///
/// Purpose: byte-level equality only proves the YAML did not change.  If the new
/// type lacks a serialized field the old type had, that data survives in the YAML
/// but is silently ignored at load.  Comparing this dump against the YAML keys of
/// the same component is the only way to find such a loss.
///
/// ASCII-only on purpose.
/// </summary>
public static class SampleFields
{
    private const string PrefabPath =
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainpanel_mainpanel/art/uipanels/mainpanel/MainPanel.prefab";
    private const string ConfigPath = "Assets/MonoBehaviour/Renderer2D.asset";
    private static readonly string OutPath = @"<BUILD_DIR>\_cd\_sample_fields.tsv";

    private static readonly string[] Types =
    {
        "UnityEngine.UI.Image", "UnityEngine.UI.Button", "TMPro.TextMeshProUGUI",
        "UnityEngine.UI.Text", "UnityEngine.UI.ContentSizeFitter",
        "UnityEngine.UI.VerticalLayoutGroup", "UnityEngine.UI.HorizontalLayoutGroup",
        "UnityEngine.UI.RawImage", "UnityEngine.EventSystems.EventTrigger",
        "UnityEngine.UI.Mask", "UnityEngine.UI.RectMask2D", "UnityEngine.UI.Outline",
        "UnityEngine.UI.GridLayoutGroup",
        "UnityEngine.Rendering.Universal.Renderer2DData"
    };

    public static void Run()
    {
        var sb = new StringBuilder();
        sb.AppendLine("type\tpropertyPath\tpropertyType\tisArray\tassetPath\tcomponentFileId");

        GameObject root = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
        if (root == null)
        {
            sb.AppendLine("ERROR\tprefab did not load\t\t\t\t");
            File.WriteAllText(OutPath, sb.ToString(), new UTF8Encoding(false));
            Debug.LogError("[SampleFields] prefab did not load");
            return;
        }

        Component[] comps = root.GetComponentsInChildren<Component>(true);

        foreach (string t in Types)
        {
            Component c = comps.FirstOrDefault(x => x != null && x.GetType().FullName == t);
            ScriptableObject so = null;
            UnityEngine.Object target = c;
            string assetPath = PrefabPath;
            if (target == null)
            {
                // the URP config is a standalone asset, not part of the prefab
                var cfg = AssetDatabase.LoadAssetAtPath<ScriptableObject>(ConfigPath);
                if (cfg != null && cfg.GetType().FullName == t)
                {
                    so = cfg;
                    target = cfg;
                    assetPath = ConfigPath;
                }
            }
            if (target == null)
            {
                sb.AppendLine(t + "\t(NOT_FOUND)\t\t\t" + assetPath + "\t");
                continue;
            }

            long fid = 0;
            if (c != null)
            {
                var s = new SerializedObject(c);
                SerializedProperty sp = s.FindProperty("m_Script");
                if (sp != null && sp.objectReferenceValue != null)
                {
                    // local file id of the component inside the prefab
                    AssetDatabase.TryGetGUIDAndLocalFileIdentifier(c, out string g, out long lid);
                    fid = lid;
                }
            }

            var ser = new SerializedObject(target);
            SerializedProperty p = ser.GetIterator();
            int n = 0;
            // Next(true), NOT NextVisible(true): NextVisible skips [HideInInspector]
            // serialized fields.  URP's Renderer2DData declares
            //   [SerializeField, Reload(...)][HideInInspector] Texture2D m_FallOffLookup
            // so NextVisible hid a field that really is serialized and really is
            // loaded, and the comparison wrongly reported it as a dropped field.
            // The complete set is required for a sound field-compatibility check.
            while (p.Next(true))
            {
                sb.AppendLine(string.Join("\t", new[]
                {
                    t, p.propertyPath, p.propertyType.ToString(),
                    p.isArray ? "1" : "0", assetPath, fid.ToString()
                }));
                n++;
            }
            Debug.Log("[SampleFields] " + t + " -> " + n + " properties, fileId=" + fid);
        }

        File.WriteAllText(OutPath, sb.ToString(), new UTF8Encoding(false));
        Debug.Log("[SampleFields] wrote " + OutPath);
    }
}
