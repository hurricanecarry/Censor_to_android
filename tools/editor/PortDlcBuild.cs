using System;
using System.IO;
using System.Text;
using UnityEditor;
using YooAsset.Editor;

namespace CensorPort.Editor
{
    /// <summary>
    /// Builds the optional DLCPackage bundles and refreshes the package index.
    ///
    /// Why this exists: the shipped Windows build carries Assets/StreamingAssets/dynamic_assets/
    /// DLCPackage (5 bundles, ~20 MB, 37 addressed assets: the TV station extra prefabs, the three
    /// TV scenes and the TV NPCs), and the game asks AssetsManager.HasDLCPackage for them
    /// (MainPanelUI gates UI on it, SceneManager resolves DLC scenes through it).  Without the
    /// package the port runs "without DLC" and that content can never load.
    ///
    /// Every parameter mirrors PortAndroidBuild's RootPackage build so the two packages are built
    /// the same way (BuiltinBuildPipeline, LZ4, hash file names, no encryption, ClearAndCopyAll).
    /// The address rule (AddressByPortMap) covers the DLC assets because
    /// Assets/PortBuild/PortAddressMap.tsv now also carries the 37 rows taken from the original
    /// PackageManifest_DLCPackage_2026-08-18-969.bytes.
    ///
    /// ASCII-only on purpose.
    /// </summary>
    public static class PortDlcBuild
    {
        private const string PackageName = "DLCPackage";
        private const string PackageVersion = "1.0";
        private static readonly string ReportPath = @"<BUILD_DIR>\_cd\_port_dlc_build.txt";

        public static void Run()
        {
            var sb = new StringBuilder();
            sb.AppendLine("=== DLCPackage bundle build ===");
            sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            sb.AppendLine("activeBuildTarget = " + EditorUserBuildSettings.activeBuildTarget);

            var parameters = new BuiltinBuildParameters
            {
                BuildOutputRoot = AssetBundleBuilderHelper.GetDefaultBuildOutputRoot(),
                BuildinFileRoot = AssetBundleBuilderHelper.GetStreamingAssetsRoot(),
                BuildPipeline = EBuildPipeline.BuiltinBuildPipeline.ToString(),
                BuildTarget = BuildTarget.Android,
                BuildMode = EBuildMode.ForceRebuild,
                PackageName = PackageName,
                PackageVersion = PackageVersion,
                EnableSharePackRule = false,
                VerifyBuildingResult = true,
                FileNameStyle = EFileNameStyle.HashName,
                BuildinFileCopyOption = EBuildinFileCopyOption.ClearAndCopyAll,
                BuildinFileCopyParams = string.Empty,
                EncryptionServices = null,
                CompressOption = ECompressOption.LZ4,
                DisableWriteTypeTree = false,
                IgnoreTypeTreeChanges = true,
            };
            sb.AppendLine("  buildOutputRoot = " + parameters.BuildOutputRoot);
            sb.AppendLine("  buildinFileRoot = " + parameters.BuildinFileRoot);
            sb.AppendLine("  package         = " + parameters.PackageName + " " + parameters.PackageVersion);

            var sw = System.Diagnostics.Stopwatch.StartNew();
            BuildResult result;
            try
            {
                result = new BuiltinBuildPipeline().Run(parameters, true);
            }
            catch (Exception e)
            {
                sb.AppendLine("  BUILD THREW: " + e.GetType().Name + ": " + e.Message);
                sb.AppendLine(e.StackTrace);
                File.WriteAllText(ReportPath, sb.ToString(), new UTF8Encoding(false));
                UnityEngine.Debug.LogError("[PortDlcBuild] threw; see " + ReportPath);
                return;
            }
            sw.Stop();
            sb.AppendLine("  success    = " + result.Success + "   elapsed=" + sw.Elapsed.TotalSeconds.ToString("0.0") + " s");
            sb.AppendLine("  failedTask = " + result.FailedTask);
            sb.AppendLine("  errorInfo  = " + result.ErrorInfo);
            sb.AppendLine("  outputDir  = " + result.OutputPackageDirectory);

            if (result.Success)
                PortPackageIndex.Write(sb);

            File.WriteAllText(ReportPath, sb.ToString(), new UTF8Encoding(false));
            foreach (string l in sb.ToString().Split('\n'))
                UnityEngine.Debug.Log("[PortDlcBuild] " + l.TrimEnd());
        }
    }
}
