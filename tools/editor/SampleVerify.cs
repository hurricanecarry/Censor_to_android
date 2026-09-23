using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// GATE 2 for the sample reference migration.
///
/// Gate 1 (already run outside Unity) proved at the byte level that only the
/// m_Script lines changed in the two sample assets.  That proves field
/// preservation AT THE SERIALIZED LEVEL, but it does not prove the new
/// identities actually resolve.  This script closes that gap: it loads the two
/// real assets and shows
///   * how many components came back null (i.e. became Missing Script),
///   * that each migrated identity resolves to the EXPECTED managed type,
///   * that key serialized fields are still readable and populated.
///
/// ASCII-only on purpose: this project has already been bitten by tools reading
/// non-ASCII source with the wrong code page.
/// </summary>
public static class SampleVerify
{
    private const string PrefabPath =
        "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainpanel_mainpanel/art/uipanels/mainpanel/MainPanel.prefab";
    private const string ConfigPath = "Assets/MonoBehaviour/Renderer2D.asset";
    private static readonly string OutPath = @"<BUILD_DIR>\_cd\_sample_verify.txt";

    private static readonly StringBuilder Sb = new StringBuilder();
    private static int _fail;

    public static void Run()
    {
        Sb.AppendLine("=== GATE 2: Unity deserialization check for the sample migration ===");
        Sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));

        CheckPrefab();
        CheckConfig();

        Sb.AppendLine();
        Sb.AppendLine("=== RESULT: " + (_fail == 0 ? "PASS" : ("FAIL (" + _fail + ")")) + " ===");
        File.WriteAllText(OutPath, Sb.ToString(), new UTF8Encoding(false));
        Debug.Log("[SampleVerify] wrote " + OutPath + "  fail=" + _fail);
        foreach (string line in Sb.ToString().Split('\n').Take(400))
            Debug.Log("[SampleVerify] " + line.TrimEnd());
    }

    private static void CheckPrefab()
    {
        Sb.AppendLine();
        Sb.AppendLine("--- A) prefab: " + PrefabPath);
        GameObject root = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
        if (root == null)
        {
            Sb.AppendLine("  LOAD FAILED -- the prefab does not load at all");
            _fail++;
            return;
        }
        Sb.AppendLine("  loaded: " + root.name);

        Component[] comps = root.GetComponentsInChildren<Component>(true);
        int missing = comps.Count(c => c == null);
        Sb.AppendLine("  total components (incl. inactive): " + comps.Length);
        Sb.AppendLine("  NULL components (Missing Script): " + missing);
        if (missing != 0) _fail++;

        var hist = comps.Where(c => c != null)
                        .GroupBy(c => c.GetType().FullName)
                        .OrderByDescending(g => g.Count())
                        .ToList();
        Sb.AppendLine("  distinct component types resolved: " + hist.Count);
        foreach (var g in hist) Sb.AppendLine("     " + g.Count().ToString().PadLeft(5) + "  " + g.Key);

        string[] expected =
        {
            "UnityEngine.UI.Image", "UnityEngine.UI.Button", "TMPro.TextMeshProUGUI",
            "UnityEngine.UI.Text", "UnityEngine.UI.ContentSizeFitter",
            "UnityEngine.UI.VerticalLayoutGroup", "UnityEngine.UI.HorizontalLayoutGroup",
            "UnityEngine.UI.RawImage", "UnityEngine.EventSystems.EventTrigger",
            "UnityEngine.UI.Mask", "UnityEngine.UI.RectMask2D", "UnityEngine.UI.Outline",
            "UnityEngine.UI.GridLayoutGroup"
        };
        Sb.AppendLine("  expected migrated types present?");
        var got = new HashSet<string>(hist.Select(g => g.Key));
        foreach (string e in expected)
        {
            bool ok = got.Contains(e);
            if (!ok) _fail++;
            Sb.AppendLine("     " + (ok ? "OK  " : "MISS") + "  " + e);
        }

        // key serialized fields must still be readable and populated
        Sb.AppendLine("  key field spot checks:");
        var tmp = comps.OfType<TMPro.TextMeshProUGUI>().FirstOrDefault();
        if (tmp != null)
            Sb.AppendLine("     TextMeshProUGUI.text = " + Short(tmp.text) +
                          "   fontAsset=" + (tmp.font == null ? "NULL" : tmp.font.name) +
                          "   fontSize=" + tmp.fontSize);
        else { Sb.AppendLine("     TextMeshProUGUI: none"); _fail++; }

        var txt = comps.OfType<UnityEngine.UI.Text>().FirstOrDefault();
        if (txt != null)
            Sb.AppendLine("     UI.Text.text = " + Short(txt.text) +
                          "   font=" + (txt.font == null ? "NULL" : txt.font.name));

        var img = comps.OfType<UnityEngine.UI.Image>().FirstOrDefault();
        if (img != null)
            Sb.AppendLine("     Image.sprite = " + (img.sprite == null ? "NULL" : img.sprite.name) +
                          "   color=" + img.color +
                          "   raycastTarget=" + img.raycastTarget +
                          "   type=" + img.type);

        var btn = comps.OfType<UnityEngine.UI.Button>().FirstOrDefault();
        if (btn != null)
            Sb.AppendLine("     Button.onClick persistent targets = " + btn.onClick.GetPersistentEventCount() +
                          "   interactable=" + btn.interactable +
                          "   targetGraphic=" + (btn.targetGraphic == null ? "NULL" : btn.targetGraphic.GetType().Name));
        else { Sb.AppendLine("     Button: none"); _fail++; }

        var csf = comps.OfType<UnityEngine.UI.ContentSizeFitter>().FirstOrDefault();
        if (csf != null)
            Sb.AppendLine("     ContentSizeFitter horizontalFit=" + csf.horizontalFit +
                          " verticalFit=" + csf.verticalFit);

        var vlg = comps.OfType<UnityEngine.UI.VerticalLayoutGroup>().FirstOrDefault();
        if (vlg != null)
            Sb.AppendLine("     VerticalLayoutGroup spacing=" + vlg.spacing +
                          " padding=" + vlg.padding.left + "," + vlg.padding.right +
                          "," + vlg.padding.top + "," + vlg.padding.bottom);

        var rt = root.GetComponent<RectTransform>();
        if (rt != null)
            Sb.AppendLine("     root RectTransform sizeDelta=" + rt.sizeDelta + " anchoredPosition=" + rt.anchoredPosition);

        // SerializedObject view: proves MonoBehaviour identity, not just a shim
        Sb.AppendLine("  SerializedObject identity checks (first instance of each type):");
        foreach (string t in new[]
                 {
                     "UnityEngine.UI.Image", "TMPro.TextMeshProUGUI", "UnityEngine.UI.Button",
                     "UnityEngine.EventSystems.EventTrigger", "UnityEngine.UI.ContentSizeFitter"
                 })
        {
            Component c = comps.FirstOrDefault(x => x != null && x.GetType().FullName == t);
            if (c == null)
            {
                Sb.AppendLine("     MISS " + t);
                _fail++;
                continue;
            }
            var so = new SerializedObject(c);
            SerializedProperty scriptProp = so.FindProperty("m_Script");
            string scriptName = scriptProp != null && scriptProp.objectReferenceValue != null
                ? scriptProp.objectReferenceValue.name : "(null)";
            MonoScript ms = scriptProp != null ? scriptProp.objectReferenceValue as MonoScript : null;
            string classOfScript = ms != null && ms.GetClass() != null ? ms.GetClass().FullName : "(GetClass null)";
            Sb.AppendLine("     " + t);
            Sb.AppendLine("        m_Script asset = " + scriptName);
            Sb.AppendLine("        MonoScript.GetClass = " + classOfScript + "   match=" + (classOfScript == t));
            if (classOfScript != t) _fail++;
            Sb.AppendLine("        serialized property count = " + CountProps(so));
        }
    }

    private static int CountProps(SerializedObject so)
    {
        int n = 0;
        SerializedProperty p = so.GetIterator();
        while (p.NextVisible(true)) n++;
        return n;
    }

    private static void CheckConfig()
    {
        Sb.AppendLine();
        Sb.AppendLine("--- B) URP config: " + ConfigPath);
        ScriptableObject so = AssetDatabase.LoadAssetAtPath<ScriptableObject>(ConfigPath);
        if (so == null)
        {
            Sb.AppendLine("  LOAD FAILED");
            _fail++;
            return;
        }
        Type t = so.GetType();
        Sb.AppendLine("  loaded type      : " + t.FullName);
        Sb.AppendLine("  assembly         : " + t.Assembly.GetName().Name);
        bool okType = t.FullName == "UnityEngine.Rendering.Universal.Renderer2DData";
        Sb.AppendLine("  expected Renderer2DData: " + okType);
        if (!okType) _fail++;

        var ser = new SerializedObject(so);
        Sb.AppendLine("  serialized properties:");
        SerializedProperty p = ser.GetIterator();
        int shown = 0;
        while (p.NextVisible(true) && shown < 40)
        {
            string val;
            switch (p.propertyType)
            {
                case SerializedPropertyType.ObjectReference:
                    val = p.objectReferenceValue == null
                        ? "null"
                        : (p.objectReferenceValue.name + " [" + p.objectReferenceValue.GetType().Name + "]");
                    break;
                case SerializedPropertyType.Integer:
                    val = p.intValue.ToString();
                    break;
                case SerializedPropertyType.Float:
                    val = p.floatValue.ToString("0.###");
                    break;
                case SerializedPropertyType.Boolean:
                    val = p.boolValue.ToString();
                    break;
                case SerializedPropertyType.String:
                    val = Short(p.stringValue);
                    break;
                case SerializedPropertyType.Enum:
                    val = p.enumValueIndex.ToString();
                    break;
                default:
                    val = "(" + p.propertyType + ")";
                    break;
            }
            Sb.AppendLine("     " + p.propertyPath.PadRight(46) + " = " + val);
            shown++;
        }
        Sb.AppendLine("  total properties: " + CountProps(ser));

        // a renderer-2D config must reference its blit/renderer shaders and the
        // post-process data; those are the fields whose loss would be visible.
        foreach (string key in new[] { "m_RendererShaders", "m_PostProcessData", "m_Shaders", "m_LightBlendStyles" })
        {
            SerializedProperty q = ser.FindProperty(key);
            if (q == null)
            {
                Sb.AppendLine("     " + key + ": (property not present in this version)");
                continue;
            }
            string info = q.isArray
                ? ("array size=" + q.arraySize)
                : (q.propertyType == SerializedPropertyType.ObjectReference
                    ? (q.objectReferenceValue == null ? "null" : q.objectReferenceValue.name)
                    : "(" + q.propertyType + ")");
            Sb.AppendLine("     " + key + ": " + info);
        }
    }

    private static string Short(string s)
    {
        if (s == null) return "null";
        s = s.Replace("\n", "\\n").Replace("\r", "");
        return "\"" + (s.Length > 48 ? s.Substring(0, 48) + "..." : s) + "\"";
    }
}
