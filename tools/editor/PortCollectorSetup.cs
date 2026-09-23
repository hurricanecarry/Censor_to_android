using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using YooAsset.Editor;

namespace CensorPort.Editor
{
    /// <summary>
    /// Build the YooAsset collector configuration for the port and then REPORT what
    /// it would produce, before any (slow) bundle build runs.
    ///
    /// Layout: every bundle of the shipped manifest is a folder under
    /// Assets/AssetBundles/.  RootPackage takes the 63 rootpackage_* folders and
    /// DLCPackage takes the 5 dlcpackage_* ones, so both packages keep the exact
    /// bundle names the original manifest declares.
    ///
    /// Package flags copy the shipped manifest: EnableAddressable=true,
    /// LocationToLower=false, IncludeAssetGUID=false.
    ///
    /// ASCII-only on purpose.
    /// </summary>
    public static class PortCollectorSetup
    {
        private const string Root = "Assets/AssetBundles";
        private const string SettingPath = "Assets/AssetBundleCollectorSetting.asset";
        private const string ReportPath = @"<BUILD_DIR>\_cd\_port_collect_report.txt";

        public static void Run()
        {
            var sb = new StringBuilder();
            sb.AppendLine("=== Port collector setup ===");
            sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));

            string[] folders = Directory.GetDirectories(Root)
                                       .Select(d => Path.GetFileName(d))
                                       .OrderBy(d => d, StringComparer.Ordinal)
                                       .ToArray();
            var rootFolders = folders.Where(f => !f.StartsWith("dlcpackage_")).ToArray();
            var dlcFolders = folders.Where(f => f.StartsWith("dlcpackage_")).ToArray();
            sb.AppendLine("folders total=" + folders.Length
                          + "  rootpackage=" + rootFolders.Length
                          + "  dlcpackage=" + dlcFolders.Length);

            AssetBundleCollectorSetting setting =
                AssetDatabase.LoadAssetAtPath<AssetBundleCollectorSetting>(SettingPath);
            if (setting == null)
            {
                setting = ScriptableObject.CreateInstance<AssetBundleCollectorSetting>();
                Directory.CreateDirectory(Path.GetDirectoryName(SettingPath));
                AssetDatabase.CreateAsset(setting, SettingPath);
                sb.AppendLine("created " + SettingPath);
            }
            else
            {
                sb.AppendLine("reusing " + SettingPath);
            }

            setting.UniqueBundleName = false;
            setting.Packages = new List<AssetBundleCollectorPackage>();
            setting.Packages.Add(MakePackage("RootPackage", rootFolders));
            setting.Packages.Add(MakePackage("DLCPackage", dlcFolders));
            EditorUtility.SetDirty(setting);
            AssetDatabase.SaveAssets();
            sb.AppendLine("wrote " + setting.Packages.Count + " packages");

            // ---- report what would be collected, without building ----
            foreach (AssetBundleCollectorPackage pkg in setting.Packages)
            {
                sb.AppendLine();
                sb.AppendLine("--- package " + pkg.PackageName
                              + "  addressable=" + pkg.EnableAddressable
                              + "  includeGUID=" + pkg.IncludeAssetGUID
                              + "  groups=" + pkg.Groups.Count);
                foreach (AssetBundleCollectorGroup grp in pkg.Groups)
                {
                    sb.AppendLine("    group " + grp.GroupName
                                  + "  active=" + grp.ActiveRuleName
                                  + "  collectors=" + grp.Collectors.Count);
                    foreach (AssetBundleCollector c in grp.Collectors)
                    {
                        sb.AppendLine("       " + c.CollectPath
                                      + "  pack=" + c.PackRuleName
                                      + "  address=" + c.AddressRuleName
                                      + "  filter=" + c.FilterRuleName);
                    }
                }
            }

            // bundle-name probe: the rules are pure functions of the asset path, so
            // they can be exercised without running a build
            sb.AppendLine();
            sb.AppendLine("--- bundle name probe ---");
            var rule = new PackPortBundleFolder();
            int ok = 0, bad = 0;
            var produced = new HashSet<string>(StringComparer.Ordinal);
            foreach (string f in rootFolders)
            {
                // the rule requires an Assets/AssetBundles/ prefixed path; the first
                // version of this probe omitted the prefix and every case threw, which
                // is the rule behaving correctly and the probe being wrong
                string probe = Root + "/" + f + "/probe.txt";
                try
                {
                    PackRuleResult r = ((IPackRule)rule).GetPackRuleResult(
                        new PackRuleData(probe, Root + "/" + f, f, string.Empty));
                    string name = r.GetBundleName("RootPackage", false);
                    produced.Add(name);
                    string expected = f + ".bundle";
                    if (name == expected) ok++;
                    else
                    {
                        bad++;
                        if (bad <= 5) sb.AppendLine("   MISMATCH " + name + " vs " + expected);
                    }
                }
                catch (Exception e)
                {
                    bad++;
                    if (bad <= 5) sb.AppendLine("   EXCEPTION " + probe + " : " + e.Message);
                }
            }
            sb.AppendLine("   bundle names matching the folder name: " + ok + "   mismatching: " + bad);
            sb.AppendLine("   distinct bundle names produced: " + produced.Count);

            // address probe
            sb.AppendLine();
            sb.AppendLine("--- address probe (first 5 mapped + 2 unmapped) ---");
            var addr = new AddressByPortMap();
            var map = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (string line in File.ReadAllLines("Assets/PortBuild/PortAddressMap.tsv").Skip(1))
            {
                string[] c = line.Split('\t');
                if (c.Length >= 3) map[c[2].Trim().Replace('\\', '/')] = c[0].Trim();
            }
            foreach (var kv in map.Take(5))
            {
                string got = ((IAddressRule)addr).GetAssetAddress(
                    new AddressRuleData(kv.Key, string.Empty, string.Empty, string.Empty));
                sb.AppendLine("   " + kv.Key);
                sb.AppendLine("       expected=" + kv.Value + "   got=" + got + "   match=" + (got == kv.Value));
            }
            string unmapped = "Assets/AssetBundles/rootpackage_assets_art_uipanels_mainui/art/uipanels/MainUI.prefab";
            sb.AppendLine("   unmapped probe: " + ((IAddressRule)addr).GetAssetAddress(
                new AddressRuleData(unmapped, string.Empty, string.Empty, string.Empty)));

            File.WriteAllText(ReportPath, sb.ToString(), new UTF8Encoding(false));
            foreach (string l in sb.ToString().Split('\n')) Debug.Log("[PortCollectorSetup] " + l.TrimEnd());
        }

        private static AssetBundleCollectorPackage MakePackage(string name, string[] folders)
        {
            var pkg = new AssetBundleCollectorPackage
            {
                PackageName = name,
                PackageDesc = "ported from the shipped manifest",
                EnableAddressable = true,
                LocationToLower = false,
                IncludeAssetGUID = false,
                AutoCollectShaders = false,
                IgnoreRuleName = nameof(NormalIgnoreRule),
                Groups = new List<AssetBundleCollectorGroup>(),
            };
            var grp = new AssetBundleCollectorGroup
            {
                GroupName = name + "_All",
                GroupDesc = "one collector per shipped bundle folder",
                AssetTags = string.Empty,
                ActiveRuleName = nameof(EnableGroup),
                Collectors = new List<AssetBundleCollector>(),
            };
            foreach (string f in folders)
            {
                grp.Collectors.Add(new AssetBundleCollector
                {
                    CollectPath = Root + "/" + f,
                    CollectorGUID = AssetDatabase.AssetPathToGUID(Root + "/" + f),
                    CollectorType = ECollectorType.MainAssetCollector,
                    AddressRuleName = nameof(AddressByPortMap),
                    PackRuleName = nameof(PackPortBundleFolder),
                    FilterRuleName = nameof(CollectAll),
                    AssetTags = string.Empty,
                    UserData = string.Empty,
                });
            }
            pkg.Groups.Add(grp);
            return pkg;
        }
    }
}
