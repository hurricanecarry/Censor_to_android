using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;
using YooAsset.Editor;

namespace CensorPort.Editor
{
    /// <summary>
    /// Configure the Android player and build the RootPackage bundles, then write
    /// the package index from the REAL build output.
    ///
    /// 落实的验收要点：
    ///   * EncryptionServices is left null, and the produced manifest is re-read
    ///     afterwards to confirm every bundle reports Encrypted=false -- the
    ///     original manifest's Encrypted=false does not prove a new build will be
    ///     unencrypted, and the decompiled BundleStream XOR loop is still unfixed.
    ///   * The index is generated from the actual manifest and bundle files with
    ///     real manifestSize / manifestSha256 / bundleCount, replacing the
    ///     hand-written placeholder that the strict loader rejects.
    ///
    /// ASCII-only on purpose.
    /// </summary>
    public static class PortAndroidBuild
    {
        private const string BundleId = "com.bigsstudio.thecensor.port";
        private const string PackageName = "RootPackage";
        private const string PackageVersion = "1.0";
        private static readonly string ReportPath = @"<BUILD_DIR>\_cd\_port_bundle_build.txt";

        public static void Run()
        {
            var sb = new StringBuilder();
            sb.AppendLine("=== Android player settings + RootPackage bundle build ===");
            sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));

            ConfigurePlayer(sb);
            BuildBundles(sb);
            WriteIndex(sb);

            File.WriteAllText(ReportPath, sb.ToString(), new UTF8Encoding(false));
            foreach (string l in sb.ToString().Split('\n')) Debug.Log("[PortAndroidBuild] " + l.TrimEnd());
        }

        private static void ConfigurePlayer(StringBuilder sb)
        {
            sb.AppendLine();
            sb.AppendLine("--- player settings ---");
            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            {
                sb.AppendLine("switching active build target to Android ...");
                bool ok = EditorUserBuildSettings.SwitchActiveBuildTarget(
                    BuildTargetGroup.Android, BuildTarget.Android);
                sb.AppendLine("  switch returned " + ok
                              + "   now=" + EditorUserBuildSettings.activeBuildTarget);
            }
            else
            {
                sb.AppendLine("active build target already Android");
            }

            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, BundleId);
            // Gradle rejects versionCode 0:
            //   "android.defaultConfig.versionCode is set to 0, but it should be a
            //    positive integer"
            // The AssetRipper export left AndroidBundleVersionCode at 0.
            PlayerSettings.bundleVersion = "1.0";
            PlayerSettings.Android.bundleVersionCode = 1;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel22;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevelAuto;
            PlayerSettings.Android.useCustomKeystore = false;   // debug keystore
            PlayerSettings.SetApiCompatibilityLevel(BuildTargetGroup.Android,
                ApiCompatibilityLevel.NET_Standard_2_0);
            PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
            PlayerSettings.Android.forceInternetPermission = true;
            AssetDatabase.SaveAssets();

            sb.AppendLine("  bundleIdentifier      = " + PlayerSettings.GetApplicationIdentifier(BuildTargetGroup.Android));
            sb.AppendLine("  scriptingBackend      = " + PlayerSettings.GetScriptingBackend(BuildTargetGroup.Android));
            sb.AppendLine("  targetArchitectures   = " + PlayerSettings.Android.targetArchitectures);
            sb.AppendLine("  minSdk                = " + PlayerSettings.Android.minSdkVersion);
            sb.AppendLine("  apiCompatibilityLevel = " + PlayerSettings.GetApiCompatibilityLevel(BuildTargetGroup.Android));
            sb.AppendLine("  useCustomKeystore     = " + PlayerSettings.Android.useCustomKeystore);
        }

        private static void BuildBundles(StringBuilder sb)
        {
            sb.AppendLine();
            sb.AppendLine("--- YooAsset RootPackage build (BuiltinBuildPipeline, NO encryption) ---");

            var parameters = new BuiltinBuildParameters
            {
                BuildOutputRoot = AssetBundleBuilderHelper.GetDefaultBuildOutputRoot(),
                BuildinFileRoot = AssetBundleBuilderHelper.GetStreamingAssetsRoot(),
                BuildPipeline = EBuildPipeline.BuiltinBuildPipeline.ToString(),
                BuildTarget = BuildTarget.Android,
                BuildMode = EBuildMode.ForceRebuild,
                PackageName = PackageName,
                PackageVersion = PackageVersion,
                // FALSE on purpose.  The shipped manifest has 63 bundles with exactly
                // one dependency (bundle 5 -> bundle 42), and the export shows the same
                // material/shader duplicated inside many bundle folders -- that is the
                // signature of a build with NO share pack rule, where each collector's
                // folder is one self-contained bundle.  With sharing enabled the first
                // build produced 71 bundles instead of 63.
                EnableSharePackRule = false,
                VerifyBuildingResult = true,
                FileNameStyle = EFileNameStyle.HashName,      // original OutputNameStyle = 0
                BuildinFileCopyOption = EBuildinFileCopyOption.ClearAndCopyAll,
                BuildinFileCopyParams = string.Empty,
                EncryptionServices = null,                    // explicitly none
                CompressOption = ECompressOption.LZ4,
                DisableWriteTypeTree = false,
                IgnoreTypeTreeChanges = true,
            };
            sb.AppendLine("  buildOutputRoot = " + parameters.BuildOutputRoot);
            sb.AppendLine("  buildinFileRoot = " + parameters.BuildinFileRoot);
            sb.AppendLine("  encryption      = " + (parameters.EncryptionServices == null ? "NONE" : "SET"));

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
                return;
            }
            sw.Stop();
            sb.AppendLine("  success        = " + result.Success + "   elapsed=" + sw.Elapsed.TotalSeconds.ToString("0.0") + " s");
            sb.AppendLine("  failedTask     = " + result.FailedTask);
            sb.AppendLine("  errorInfo      = " + result.ErrorInfo);
            sb.AppendLine("  outputDir      = " + result.OutputPackageDirectory);
            if (!result.Success)
                return;

            // re-read the produced manifest and confirm encryption is off
            sb.AppendLine();
            sb.AppendLine("--- produced manifest ---");
            string pkgDir = result.OutputPackageDirectory;
            string manifestFile = Directory.GetFiles(pkgDir, "PackageManifest_*.bytes")
                                           .OrderByDescending(f => f).FirstOrDefault();
            if (manifestFile == null)
            {
                sb.AppendLine("  no PackageManifest_*.bytes found in " + pkgDir);
                return;
            }
            sb.AppendLine("  manifest = " + Path.GetFileName(manifestFile)
                          + "  " + new FileInfo(manifestFile).Length + " B");

            string manifestJson = File.ReadAllText(manifestFile);
            int encTrue = CountOccurrences(manifestJson, "\"Encrypted\":true")
                        + CountOccurrences(manifestJson, "\"Encrypted\": true");
            int encFalse = CountOccurrences(manifestJson, "\"Encrypted\":false")
                         + CountOccurrences(manifestJson, "\"Encrypted\": false");
            sb.AppendLine("  Encrypted true/false in manifest = " + encTrue + " / " + encFalse);

            // the built files land next to the manifest
            var files = Directory.GetFiles(pkgDir).Select(f => new FileInfo(f))
                                 .OrderByDescending(f => f.Length).ToArray();
            long total = files.Sum(f => f.Length);
            sb.AppendLine("  files in package dir = " + files.Length
                          + "   total = " + (total / 1024 / 1024) + " MB");
            foreach (var f in files.Take(8))
                sb.AppendLine("     " + f.Name + "  " + f.Length + " B");
        }

        private static void WriteIndex(StringBuilder sb)
        {
            // Delegated to PortPackageIndex: the index has to describe BOTH packages from their real
            // buildin output.  The previous version hardcoded "DLCPackage included=false", which
            // would switch the DLC off again on the next root-only bundle build even though the
            // DLCPackage bundles are still shipped.
            PortPackageIndex.Write(sb);
        }

        private static int CountOccurrences(string haystack, string needle)
        {
            int n = 0, i = 0;
            while ((i = haystack.IndexOf(needle, i, StringComparison.Ordinal)) >= 0)
            {
                n++;
                i += needle.Length;
            }
            return n;
        }

        private static string Sha256(string path)
        {
            using (var sha = SHA256.Create())
            using (var s = File.OpenRead(path))
                return string.Concat(sha.ComputeHash(s).Select(b => b.ToString("x2")));
        }
    }
}
