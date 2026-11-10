// Colosseum Heroes (2011, Unity 3.4) recovered and ported to Unity 2019.4 (2019.4.41f2) for 64-bit Android.
// Applies the Android player settings once per editor session and adds menu items:
//   Colosseum Heroes > Apply Android 64-bit Settings
//   Colosseum Heroes > Build 64-bit APK
using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;
using UnityEngine.Rendering;

[InitializeOnLoad]
public static class ColosseumHeroesBuild
{
    const string SessionKey = "ColosseumHeroes.SettingsApplied";
    static readonly string[] Scenes = { "Assets/loadingScene.unity", "Assets/GameScene.unity" };
    const string ApkPath = "Builds/ColosseumHeroes-64bit.apk";

    static ColosseumHeroesBuild()
    {
        EditorApplication.delayCall += () =>
        {
            if (SessionState.GetBool(SessionKey, false)) return;
            SessionState.SetBool(SessionKey, true);
            Apply();
        };
    }

    [MenuItem("Colosseum Heroes/Apply Android 64-bit Settings")]
    public static void Apply()
    {
        PlayerSettings.companyName = "Gamevil";
        PlayerSettings.productName = "Colosseum Heroes";
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "com.gamevil.colosseumheroes.marketfree");
        PlayerSettings.bundleVersion = "1.0.8";
        PlayerSettings.Android.bundleVersionCode = 109;

        // 64-bit: ARM64 requires IL2CPP. ARMv7 kept so older 32-bit phones still work.
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64 | AndroidArchitecture.ARMv7;
        PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel24;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevelAuto;

        // The original renders in gamma space with legacy fixed-function shaders.
        PlayerSettings.colorSpace = ColorSpace.Gamma;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.OpenGLES3 });

        // Landscape only, either way up; full screen on modern tall displays.
        PlayerSettings.defaultInterfaceOrientation = UIOrientation.AutoRotation;
        PlayerSettings.allowedAutorotateToPortrait = false;
        PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
        PlayerSettings.allowedAutorotateToLandscapeLeft = true;
        PlayerSettings.allowedAutorotateToLandscapeRight = true;
        PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
        PlayerSettings.Android.renderOutsideSafeArea = false;
        PlayerSettings.Android.maxAspectRatio = 2.4f;

        var icon = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Icon/app_icon.png");
        if (icon != null)
        {
            var setIcons = typeof(PlayerSettings).GetMethod("SetIconsForTargetGroup", new[] { typeof(BuildTargetGroup), typeof(Texture2D[]) });
            if (setIcons != null) setIcons.Invoke(null, new object[] { BuildTargetGroup.Unknown, new[] { icon } });
        }

        var buildScenes = new EditorBuildSettingsScene[Scenes.Length];
        for (int i = 0; i < Scenes.Length; i++) buildScenes[i] = new EditorBuildSettingsScene(Scenes[i], true);
        EditorBuildSettings.scenes = buildScenes;

        AssetDatabase.SaveAssets();
        Debug.Log("Colosseum Heroes: Android 64-bit (IL2CPP, ARM64 + ARMv7) settings applied.");
    }

    // An asset whose import crashed the editor is replaced by an empty placeholder (DefaultAsset) on the
    // next start ("A default asset was created ... because the asset importer crashed on it last time").
    // Force a real reimport of any prefab, scene or asset that is still such a placeholder.
    [MenuItem("Colosseum Heroes/Repair Crashed Imports")]
    public static void RepairCrashedImports()
    {
        int n = 0;
        foreach (string path in AssetDatabase.GetAllAssetPaths())
        {
            if (!path.StartsWith("Assets/")) continue;
            if (!(path.EndsWith(".prefab") || path.EndsWith(".unity") || path.EndsWith(".asset"))) continue;
            if (AssetDatabase.GetMainAssetTypeAtPath(path) != typeof(DefaultAsset)) continue;
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            System.Type now = AssetDatabase.GetMainAssetTypeAtPath(path);
            Debug.Log("CH-REIMPORT: " + path + " -> " + (now != null ? now.Name : "null"));
            n++;
        }
        Debug.Log("CH-REIMPORT: " + n + " placeholder asset(s) reimported");
    }

    [MenuItem("Colosseum Heroes/Build 64-bit APK")]
    public static void BuildApk()
    {
        RepairCrashedImports();
        Apply();
        if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
        EditorUserBuildSettings.androidBuildSystem = AndroidBuildSystem.Gradle;
        EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
        EditorUserBuildSettings.buildAppBundle = false;
        PlayerSettings.Android.useCustomKeystore = false;
        Directory.CreateDirectory(Path.GetDirectoryName(ApkPath));

        BuildReport report = null;
        try
        {
            report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = Scenes,
                locationPathName = ApkPath,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = BuildOptions.None,
            });
        }
        catch (Exception e)
        {
            Debug.LogError("CH-BUILD-ERROR: " + e);
        }

        bool ok = report != null && report.summary.result == BuildResult.Succeeded;
        if (report != null)
        {
            foreach (var step in report.steps)
                foreach (var msg in step.messages)
                    if (msg.type == LogType.Error || msg.type == LogType.Exception)
                        Debug.Log("CH-BUILD-ERROR: [" + step.name + "] " + msg.content);
            Debug.Log($"CH-BUILD-RESULT: {report.summary.result}, {report.summary.totalErrors} errors, " +
                      $"{report.summary.totalSize / (1024 * 1024)} MB, {report.summary.totalTime} -> {Path.GetFullPath(ApkPath)}");
        }
        // Started by the build window (-executeMethod), with or without -batchmode: quit with the result.
        // Unity 2019.4 batch mode needs a legacy .ulf license, which free Personal licenses no longer get,
        // so the build window runs the editor windowed and relies on this exit code.
        bool fromCommandLine = Application.isBatchMode ||
                               Array.IndexOf(Environment.GetCommandLineArgs(), "-executeMethod") >= 0;
        if (fromCommandLine)
            EditorApplication.Exit(ok ? 0 : 1);
        else if (ok)
            EditorUtility.RevealInFinder(ApkPath);
    }
}
