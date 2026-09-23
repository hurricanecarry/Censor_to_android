using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Establish the TRUE identity of every shader involved in the reference
/// migration: (guid, localFileID) as Unity itself reports it.
///
/// 已纠正的错误假设："同一个 shader 会因引用字段不同而携带不同的 fileID"。
/// A local file id
/// identifies an object WITHIN the target file; it is a property of the target,
/// not of the reference.  The claim must therefore be replaced by measurement:
/// ask Unity for each shader's own (guid, localID) and require the migrated
/// references to use exactly that.
///
/// ASCII-only on purpose.
/// </summary>
public static class ShaderIdentity
{
    private static readonly string OutPath = @"<BUILD_DIR>\_cd\_shader_identity.tsv";

    public static void Run()
    {
        var sb = new StringBuilder();
        sb.AppendLine("assetPath\tguid\tlocalFileID\tname\tisDummy\torigin");

        // every shader anywhere the AssetDatabase can see: Assets + Packages
        string[] guids = AssetDatabase.FindAssets("t:Shader");
        Debug.Log("[ShaderIdentity] FindAssets(t:Shader) => " + guids.Length);

        var seen = new HashSet<string>();
        int n = 0;
        foreach (string g in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(g);
            if (string.IsNullOrEmpty(path) || !seen.Add(path)) continue;

            Shader sh = AssetDatabase.LoadAssetAtPath<Shader>(path);
            if (sh == null)
            {
                sb.AppendLine(path + "\t" + g + "\tLOAD_FAILED\t\t\t");
                continue;
            }

            string guid = "";
            long localId = 0;
            string status;
            try
            {
                bool ok = AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sh, out guid, out localId);
                status = ok ? "OK" : "TRYGET_FAILED";
            }
            catch (Exception e)
            {
                status = "EXC:" + e.GetType().Name;
            }

            bool dummy = false;
            string origin = path.StartsWith("Packages/") ? "PACKAGE" : "ASSETS";
            if (origin == "ASSETS")
            {
                try { dummy = File.ReadAllText(path).Contains("DummyShaderTextExporter"); }
                catch { }
            }

            sb.AppendLine(string.Join("\t", new[]
            {
                path, guid, localId.ToString(), sh.name,
                dummy ? "1" : "0", origin + (status == "OK" ? "" : "(" + status + ")")
            }));
            n++;
        }

        File.WriteAllText(OutPath, sb.ToString(), new UTF8Encoding(false));
        Debug.Log("[ShaderIdentity] rows=" + n + " wrote " + OutPath);

        // the decisive measurement: what local id do shaders actually use?
        var byLocal = guids.Length > 0 ? new Dictionary<string, int>() : null;
        foreach (string line in sb.ToString().Split('\n').Skip(1))
        {
            string[] c = line.Split('\t');
            if (c.Length < 3) continue;
            byLocal.TryGetValue(c[2], out int cur);
            byLocal[c[2]] = cur + 1;
        }
        foreach (var kv in byLocal.OrderByDescending(k => k.Value).Take(10))
            Debug.Log("[ShaderIdentity] localFileID " + kv.Key + " used by " + kv.Value + " shaders");
    }
}
