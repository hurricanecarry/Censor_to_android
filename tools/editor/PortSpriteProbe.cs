using System;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace CensorPort.Editor
{
    /// <summary>
    /// Prints the imported geometry of every Sprite sub-asset under the asset paths listed
    /// in PathsFile.  Used to prove what the importer actually produced, instead of
    /// inferring it from runtime values.  ASCII-only on purpose.
    /// </summary>
    public static class PortSpriteProbe
    {
        private const string PathsFile = @"<BUILD_DIR>\_probe\sprite_probe_paths.txt";
        private const string ReportPath = @"<BUILD_DIR>\_cd\_sprite_probe.txt";

        public static void Run()
        {
            var sb = new StringBuilder();
            sb.AppendLine("=== sprite probe " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " ===");
            if (!File.Exists(PathsFile))
            {
                sb.AppendLine("paths file missing: " + PathsFile);
            }
            else
            {
                foreach (string raw in File.ReadAllLines(PathsFile))
                {
                    string p = raw.Trim();
                    if (p.Length == 0 || p.StartsWith("#"))
                    {
                        continue;
                    }
                    sb.AppendLine();
                    sb.AppendLine("--- " + p);
                    UnityEngine.Object[] all = AssetDatabase.LoadAllAssetsAtPath(p);
                    if (all == null || all.Length == 0)
                    {
                        sb.AppendLine("    (nothing loaded)");
                        continue;
                    }
                    int n = 0;
                    foreach (UnityEngine.Object o in all)
                    {
                        Sprite s = o as Sprite;
                        if (s == null)
                        {
                            continue;
                        }
                        n++;
                        string tr;
                        try
                        {
                            tr = Fmt(s.textureRect);
                        }
                        catch (Exception e)
                        {
                            tr = "<throws " + e.GetType().Name + ">";
                        }
                        string tro;
                        try
                        {
                            tro = s.textureRectOffset.x.ToString("0.###") + "," + s.textureRectOffset.y.ToString("0.###");
                        }
                        catch (Exception e)
                        {
                            tro = "<throws " + e.GetType().Name + ">";
                        }
                        sb.AppendLine("    sprite=" + s.name
                            + " rect=" + Fmt(s.rect)
                            + " textureRect=" + tr
                            + " texRectOffset=" + tro
                            + " pivotPx=" + s.pivot.x.ToString("0.###") + "," + s.pivot.y.ToString("0.###")
                            + " ppu=" + s.pixelsPerUnit.ToString("0.####")
                            + " packed=" + (s.packed ? 1 : 0)
                            + " tex=" + (s.texture == null ? "<null>" : s.texture.width + "x" + s.texture.height));
                        // Which texture region does the MESH actually sample?  uGUI's Image
                        // derives its UVs from the sprite's mesh, so the min/max of s.uv is the
                        // authoritative answer to "is the artwork cropped/stretched or not".
                        Vector2[] uv = s.uv;
                        if (uv != null && uv.Length > 0)
                        {
                            float u0 = 1f, u1 = 0f, v0 = 1f, v1 = 0f;
                            for (int k = 0; k < uv.Length; k++)
                            {
                                if (uv[k].x < u0) u0 = uv[k].x;
                                if (uv[k].x > u1) u1 = uv[k].x;
                                if (uv[k].y < v0) v0 = uv[k].y;
                                if (uv[k].y > v1) v1 = uv[k].y;
                            }
                            int tw2 = s.texture == null ? 0 : s.texture.width;
                            int th2 = s.texture == null ? 0 : s.texture.height;
                            sb.AppendLine("      uv[" + uv.Length + "] = u " + u0.ToString("0.#####")
                                + ".." + u1.ToString("0.#####") + "  v " + v0.ToString("0.#####")
                                + ".." + v1.ToString("0.#####")
                                + "   => sampled px x " + (u0 * tw2).ToString("0.#") + ".." + (u1 * tw2).ToString("0.#")
                                + "  y " + (v0 * th2).ToString("0.#") + ".." + (v1 * th2).ToString("0.#")
                                + "  of " + tw2 + "x" + th2
                                + "   bounds=" + s.bounds.size.x.ToString("0.###") + "x" + s.bounds.size.y.ToString("0.###"));
                        }
                        else
                        {
                            sb.AppendLine("      uv = <none>");
                        }
                    }
                    sb.AppendLine("    sprites=" + n);
                }
            }
            File.WriteAllText(ReportPath, sb.ToString(), new UTF8Encoding(false));
            foreach (string l in sb.ToString().Split('\n'))
            {
                Debug.Log("[PortSpriteProbe] " + l.TrimEnd());
            }
        }

        private static string Fmt(Rect r)
        {
            return "(" + r.x.ToString("0.###") + "," + r.y.ToString("0.###") + " "
                 + r.width.ToString("0.###") + "x" + r.height.ToString("0.###") + ")";
        }

        private const string DumpPath = @"<BUILD_DIR>\_probe\sprite_import_dump.tsv";

        /// <summary>
        /// Writes a TSV of the IMPORTED geometry of every Sprite sub-asset in the project,
        /// so it can be matched against the geometry of the same sprite in the ORIGINAL
        /// game bundles (read with UnityPy).  The only defensible defect criterion is
        /// "our imported geometry differs from the original for the same object", not
        /// "rect != textureRect", not an area ratio, and not a sprite name.
        ///
        /// Columns: assetPath, guid, sprite, texW, texH, rectX, rectY, rectW, rectH,
        ///          trX, trY, trW, trH, pivotXpx, pivotYpx, ppu, packed
        /// </summary>
        public static void DumpAll()
        {
            var sb = new StringBuilder();
            sb.AppendLine("assetPath\tguid\tsprite\ttexW\ttexH\trectX\trectY\trectW\trectH"
                          + "\ttrX\ttrY\ttrW\ttrH\tpivotXpx\tpivotYpx\tppu\tpacked");
            string[] guids = AssetDatabase.FindAssets("t:Texture2D");
            int nTex = 0;
            int nSprite = 0;
            int nErr = 0;
            foreach (string g in guids)
            {
                string p = AssetDatabase.GUIDToAssetPath(g);
                if (string.IsNullOrEmpty(p) || !p.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                nTex++;
                UnityEngine.Object[] all;
                try
                {
                    all = AssetDatabase.LoadAllAssetsAtPath(p);
                }
                catch (Exception)
                {
                    nErr++;
                    continue;
                }
                if (all == null)
                {
                    continue;
                }
                foreach (UnityEngine.Object o in all)
                {
                    Sprite s = o as Sprite;
                    if (s == null)
                    {
                        continue;
                    }
                    nSprite++;
                    float trx = 0f, tryy = 0f, trw = 0f, trh = 0f;
                    try
                    {
                        Rect tr = s.textureRect;
                        trx = tr.x; tryy = tr.y; trw = tr.width; trh = tr.height;
                    }
                    catch (Exception)
                    {
                        trx = tryy = trw = trh = -1f;
                    }
                    Rect r = s.rect;
                    int tw = s.texture == null ? 0 : s.texture.width;
                    int th = s.texture == null ? 0 : s.texture.height;
                    sb.Append(p).Append('\t').Append(g).Append('\t').Append(s.name)
                      .Append('\t').Append(tw).Append('\t').Append(th)
                      .Append('\t').Append(r.x.ToString("0.###")).Append('\t').Append(r.y.ToString("0.###"))
                      .Append('\t').Append(r.width.ToString("0.###")).Append('\t').Append(r.height.ToString("0.###"))
                      .Append('\t').Append(trx.ToString("0.###")).Append('\t').Append(tryy.ToString("0.###"))
                      .Append('\t').Append(trw.ToString("0.###")).Append('\t').Append(trh.ToString("0.###"))
                      .Append('\t').Append(s.pivot.x.ToString("0.###")).Append('\t').Append(s.pivot.y.ToString("0.###"))
                      .Append('\t').Append(s.pixelsPerUnit.ToString("0.####"))
                      .Append('\t').Append(s.packed ? "1" : "0")
                      .Append('\n');
                }
            }
            File.WriteAllText(DumpPath, sb.ToString(), new UTF8Encoding(false));
            Debug.Log("[PortSpriteProbe] DumpAll textures=" + nTex + " sprites=" + nSprite
                      + " errors=" + nErr + " -> " + DumpPath);
        }
    }
}
