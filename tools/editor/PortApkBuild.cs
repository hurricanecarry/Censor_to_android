using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace CensorPort.Editor
{
    /// <summary>
    /// Build the first real-game diagnostic APK.
    ///
    /// The APK contains the actual entry scene (Assets/Main.unity), the real
    /// Assembly-CSharp (the decompiled and repaired game code), and the Android
    /// RootPackage bundles copied into Assets/StreamingAssets/dynamic_assets/ by
    /// the YooAsset build.  It is NOT a probe APK.
    ///
    /// Output is named and journalled so a later build cannot silently overwrite an
    /// earlier one: the number is "highest ever used + 1", taken from the APK files on
    /// disk and from the ledger, never a count of the files present.  The resulting
    /// SHA256 is printed for the report.
    ///
    /// ASCII-only on purpose.
    /// </summary>
    public static class PortApkBuild
    {
        private const string ApkDir = @"<BUILD_DIR>\_probe";
        private const string LedgerPath = @"<BUILD_DIR>\_probe\BUILD_LEDGER.tsv";
        private static readonly string ReportPath = @"<BUILD_DIR>\_cd\_port_apk_build.txt";

        public static void Run()
        {
            Build(false);
        }

        /// <summary>
        /// Same as Run(), but as a Development build so that android:debuggable is
        /// true and "adb shell run-as &lt;pkg&gt;" can write the diagnostic control file
        /// into the app's private directory.  Used for the runtime A/B harness
        /// (PortDebugSwitches); never for acceptance.
        /// </summary>
        public static void RunDiagnostic()
        {
            Build(true);
        }

        private const string DiagnosticDefine = "CENSOR_PORT_DIAGNOSTICS";

        /// <summary>
        /// PortDebugSwitches is compiled only when this symbol is present.  Diagnostic
        /// builds get it; release candidates must not, so a leftover port_debug.txt in
        /// Application.persistentDataPath cannot drive a shipping build.
        /// </summary>
        private static void SetDiagnosticDefine(bool enabled)
        {
            string current = PlayerSettings.GetScriptingDefineSymbolsForGroup(BuildTargetGroup.Android);
            var symbols = new List<string>();
            if (!string.IsNullOrEmpty(current))
            {
                foreach (string s in current.Split(';'))
                {
                    string t = s.Trim();
                    if (t.Length > 0 && t != DiagnosticDefine)
                    {
                        symbols.Add(t);
                    }
                }
            }
            if (enabled)
            {
                symbols.Add(DiagnosticDefine);
            }
            PlayerSettings.SetScriptingDefineSymbolsForGroup(
                BuildTargetGroup.Android, string.Join(";", symbols.ToArray()));
            Debug.Log("[PortApkBuild] " + DiagnosticDefine + " " + (enabled ? "ON" : "OFF")
                      + "; defines now: " + string.Join(";", symbols.ToArray()));
        }

        private static void Build(bool development)
        {
            var sb = new StringBuilder();
            sb.AppendLine("=== Port diagnostic APK build ===");
            sb.AppendLine("development: " + development);
            sb.AppendLine("time: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));

            Directory.CreateDirectory(ApkDir);
            int hi = HighestUsedBuildNumber();
            int n = hi + 1;
            string apk;
            do
            {
                apk = Path.Combine(ApkDir, string.Format("CensorPort_P1_b{0:00}.apk", n));
                n++;
            }
            while (File.Exists(apk));
            sb.AppendLine("highest used build number: " + hi);
            sb.AppendLine("target apk: " + apk);

            EditorUserBuildSettings.buildAppBundle = false;
            EditorUserBuildSettings.development = development;
            EditorUserBuildSettings.connectProfiler = false;
            EditorUserBuildSettings.allowDebugging = false;
            SetDiagnosticDefine(development);
            PlayerSettings.Android.useCustomKeystore = false;
            // Set here as well as in PortAndroidBuild: the APK builder is run on its
            // own, so relying on the other entry point left versionCode at 0 and Gradle
            // rejected the build with
            //   "android.defaultConfig.versionCode is set to 0"
            PlayerSettings.bundleVersion = "1.0";
            PlayerSettings.Android.bundleVersionCode = 1;
            AssetDatabase.SaveAssets();
            sb.AppendLine("bundleVersion     = " + PlayerSettings.bundleVersion
                          + "   versionCode = " + PlayerSettings.Android.bundleVersionCode);
            sb.AppendLine("bundleIdentifier  = " + PlayerSettings.GetApplicationIdentifier(BuildTargetGroup.Android));
            sb.AppendLine("scriptingBackend  = " + PlayerSettings.GetScriptingBackend(BuildTargetGroup.Android));
            sb.AppendLine("architectures     = " + PlayerSettings.Android.targetArchitectures);

            // sanity: the bundle build must have copied the manifest into StreamingAssets
            string sa = Path.Combine(Application.dataPath,
                "StreamingAssets", "dynamic_assets", "RootPackage");
            sb.AppendLine("streamingAssets RootPackage exists: " + Directory.Exists(sa));
            if (Directory.Exists(sa))
            {
                sb.AppendLine("  bundles: " + Directory.GetFiles(sa, "*.bundle").Length);
                foreach (string m in Directory.GetFiles(sa, "PackageManifest_*.bytes"))
                    sb.AppendLine("  manifest: " + Path.GetFileName(m) + "  " + new FileInfo(m).Length + " B");
            }
            string idx = Path.Combine(Application.dataPath, "Resources", "CensorPackageIndex.txt");
            sb.AppendLine("package index exists: " + File.Exists(idx));

            var options = new BuildPlayerOptions
            {
                scenes = new[] { "Assets/Main.unity" },
                locationPathName = apk,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = development ? BuildOptions.Development : BuildOptions.None,
            };
            sb.AppendLine("scenes: " + string.Join(", ", options.scenes));

            var sw = System.Diagnostics.Stopwatch.StartNew();
            BuildReport report;
            try
            {
                report = BuildPipeline.BuildPlayer(options);
            }
            catch (Exception e)
            {
                sw.Stop();
                sb.AppendLine("BUILD THREW after " + sw.Elapsed.TotalMinutes.ToString("0.0") + " min");
                sb.AppendLine(e.GetType().Name + ": " + e.Message);
                sb.AppendLine(e.StackTrace);
                File.WriteAllText(ReportPath, sb.ToString(), new UTF8Encoding(false));
                Debug.LogError("[PortApkBuild] threw; see " + ReportPath);
                return;
            }
            sw.Stop();

            BuildSummary s = report.summary;
            sb.AppendLine();
            sb.AppendLine("--- result ---");
            sb.AppendLine("  result       = " + s.result);
            sb.AppendLine("  elapsed      = " + sw.Elapsed.TotalMinutes.ToString("0.0") + " min");
            sb.AppendLine("  outputPath   = " + s.outputPath);
            sb.AppendLine("  totalSize    = " + s.totalSize + " B  (" + (s.totalSize / 1024 / 1024) + " MB)");
            sb.AppendLine("  totalErrors  = " + s.totalErrors);
            sb.AppendLine("  totalWarnings= " + s.totalWarnings);
            sb.AppendLine("  platform     = " + s.platform);
            sb.AppendLine("  buildStarted = " + s.buildStartedAt);
            sb.AppendLine("  buildEnded   = " + s.buildEndedAt);

            if (s.result == BuildResult.Succeeded && File.Exists(apk))
            {
                string sha = Sha256(apk);
                long size = new FileInfo(apk).Length;
                sb.AppendLine();
                sb.AppendLine("  APK sha256   = " + sha);
                sb.AppendLine("  APK size     = " + size + " B");
                var lines = new List<string>();
                if (File.Exists(LedgerPath))
                    lines.AddRange(File.ReadAllLines(LedgerPath));
                else
                    lines.Add("apk\tgates\tsizeBytes\tsha256\tbuiltAt\tresult");
                lines.Add(string.Join("\t", new[]
                {
                    Path.GetFileName(apk),
                    development ? "P1-real-game+debugswitches-dev" : "P1-real-game",
                    size.ToString(), sha,
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"), s.result.ToString()
                }));
                File.WriteAllLines(LedgerPath, lines);
                sb.AppendLine("  ledger       = " + LedgerPath);
            }
            else
            {
                sb.AppendLine();
                sb.AppendLine("  FAILED -- first errors from the build report:");
                int shown = 0;
                foreach (BuildStep step in report.steps)
                {
                    foreach (BuildStepMessage msg in step.messages)
                    {
                        if (msg.type != LogType.Error && msg.type != LogType.Exception)
                            continue;
                        sb.AppendLine("     [" + step.name + "] " + msg.content);
                        if (++shown >= 25) break;
                    }
                    if (shown >= 25) break;
                }
            }

            File.WriteAllText(ReportPath, sb.ToString(), new UTF8Encoding(false));
            foreach (string l in sb.ToString().Split('\n')) Debug.Log("[PortApkBuild] " + l.TrimEnd());
        }

        /// <summary>
        /// Highest build number ever used, scanned from BOTH the APK files still in the
        /// output directory AND the build ledger.
        ///
        /// The previous rule was "1 + number of CensorPort_P1_b*.apk files present".  That
        /// is wrong as soon as an APK is deleted or moved out (superseded builds are moved
        /// to _probe\_hold to keep the directory small): the count drops, the next build
        /// reuses an old number and silently overwrites a kept APK.  The b06
        /// "P1-real-game" acceptance build was destroyed exactly that way.  Numbers are
        /// therefore never reused, and the ledger is scanned too because moved-away APKs
        /// are still recorded there.
        /// </summary>
        private static int HighestUsedBuildNumber()
        {
            int max = 0;
            var rx = new Regex(@"CensorPort_P1_b(\d+)\.apk", RegexOptions.IgnoreCase);
            if (Directory.Exists(ApkDir))
            {
                // Recurse: superseded APKs are moved to _probe\_hold, and a non-recursive
                // scan would not see them, so their numbers could be handed out again.
                foreach (string f in Directory.GetFiles(ApkDir, "CensorPort_P1_b*.apk",
                             SearchOption.AllDirectories))
                {
                    Match m = rx.Match(Path.GetFileName(f));
                    int v;
                    if (m.Success && int.TryParse(m.Groups[1].Value, out v) && v > max)
                    {
                        max = v;
                    }
                }
            }
            // The ledger records the name the build actually wrote.  Historical rows are
            // NOT trustworthy for this (4 builds between 18:19 and 18:36 all wrote
            // CensorPort_P1_b01.apk because the old count-based rule collapsed, and the
            // final names on disk were assigned by hand afterwards), so this is only a
            // backstop for APKs that have since been deleted from disk entirely.
            if (File.Exists(LedgerPath))
            {
                foreach (string line in File.ReadAllLines(LedgerPath))
                {
                    Match m = rx.Match(line);
                    int v;
                    if (m.Success && int.TryParse(m.Groups[1].Value, out v) && v > max)
                    {
                        max = v;
                    }
                }
            }
            return max;
        }

        private static string Sha256(string path)
        {
            using (var sha = SHA256.Create())
            using (var s = File.OpenRead(path))
                return string.Concat(sha.ComputeHash(s).Select(b => b.ToString("x2")));
        }
    }
}
