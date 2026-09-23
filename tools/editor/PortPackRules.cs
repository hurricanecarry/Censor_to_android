using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using YooAsset.Editor;

namespace CensorPort.Editor
{
    /// <summary>
    /// Bundle naming rule: the bundle name is the folder directly under
    /// Assets/AssetBundles/, which is exactly the original bundle name.
    ///
    /// Why a custom rule is required: measured against the shipped manifest, none of
    /// the built-in rules reproduce the originals.
    ///   PackDirectory  on Assets/AssetBundles/X/art/uipanels/Foo.prefab
    ///                  -> assets_assetbundles_X_art_uipanels.bundle   (not X.bundle)
    ///   PackCollector  -> assets_assetbundles_X.bundle                (wrong prefix)
    /// Our rule returns "X", and PackRuleResult.GetBundleName normalises it to
    /// "x.bundle" -- for example
    ///   rootpackage_assets_art_uipanels_mainui.bundle
    /// which matches the original name for all 63 bundles.
    ///
    /// ASCII-only on purpose.
    /// </summary>
    [DisplayName("Port: bundle folder under Assets/AssetBundles")]
    public class PackPortBundleFolder : IPackRule
    {
        private const string Root = "Assets/AssetBundles/";

        PackRuleResult IPackRule.GetPackRuleResult(PackRuleData data)
        {
            string p = data.AssetPath.Replace('\\', '/');
            if (!p.StartsWith(Root))
                throw new Exception("[PackPortBundleFolder] asset outside Assets/AssetBundles : " + p);
            string rest = p.Substring(Root.Length);
            int slash = rest.IndexOf('/');
            if (slash <= 0)
                throw new Exception("[PackPortBundleFolder] no bundle folder in path : " + p);
            string folder = rest.Substring(0, slash);
            return new PackRuleResult(folder, DefaultPackRule.AssetBundleFileExtension);
        }
    }

    /// <summary>
    /// Address rule backed by Assets/PortBuild/PortAddressMap.tsv.
    ///
    /// Addresses cannot be derived from paths -- the game calls
    /// AssetsManager.LoadSync("UI_MainUI") while the asset is
    /// Assets/Art/UIPanels/MainUI.prefab -- so the original manifest's 95
    /// (address, asset path) pairs are carried explicitly.  Assets that the
    /// original manifest never addressed fall back to the file name, matching what
    /// YooAsset would have produced with AddressByFileName.
    /// </summary>
    [DisplayName("Port: address from PortAddressMap.tsv")]
    public class AddressByPortMap : IAddressRule
    {
        private static Dictionary<string, string> _map;

        private static void EnsureLoaded()
        {
            if (_map != null)
                return;
            // OrdinalIgnoreCase, not Ordinal.  Six of the 95 shipped addresses point at
            // files whose extension case AssetRipper changed (.PNG -> .png), and a
            // case-sensitive lookup silently fell back to a path address for exactly
            // those six -- the first build's manifest contained 89 of 95 addresses.
            // Windows paths are case-insensitive, so ignoring case here is correct.
            _map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            string path = "Assets/PortBuild/PortAddressMap.tsv";
            if (!File.Exists(path))
            {
                Debug.LogWarning("[AddressByPortMap] " + path + " not found; falling back to file names.");
                return;
            }
            string[] lines = File.ReadAllLines(path);
            for (int i = 1; i < lines.Length; i++)   // skip header
            {
                string[] c = lines[i].Split('\t');
                if (c.Length < 3)
                    continue;
                string address = c[0].Trim();
                string assetPath = c[2].Trim().Replace('\\', '/');
                if (address.Length > 0 && assetPath.Length > 0 && !_map.ContainsKey(assetPath))
                    _map.Add(assetPath, address);
            }
            Debug.Log("[AddressByPortMap] loaded " + _map.Count + " address mappings.");
        }

        string IAddressRule.GetAssetAddress(AddressRuleData data)
        {
            EnsureLoaded();
            string p = data.AssetPath.Replace('\\', '/');
            string address;
            if (_map.TryGetValue(p, out address))
                return address;
            // Fall back to the asset path WITHOUT its "Assets/" prefix.
            //
            // Two constraints come from AssetBundleCollector.GetAllCollectAssets:
            //   * the address must not start with "Assets/" or "assets/", and
            //   * addresses must be unique within the collector.
            // The first attempt used the bare file name and collided
            //   ("The address is existed : nvdianyuan_laotou"
            //    for TextAsset/nvdianyuan_laotou.txt and Texture2D/nvdianyuan_laotou.png);
            // the second used the full path and was rejected for starting with "Assets/".
            // Stripping the prefix satisfies both.  The game only ever loads the 95
            // manifest addresses, so these extra addresses exist purely to satisfy
            // uniqueness.
            const string prefix = "Assets/";
            if (p.StartsWith(prefix))
                return p.Substring(prefix.Length);
            return p;
        }
    }
}
