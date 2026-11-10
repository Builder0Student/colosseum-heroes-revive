// Play-test harness for remote debugging (run by the build window with "<id> play").
// Opens the first scene, enters Play mode and plays a scripted session: it taps through the menus
// by feeding touches into the game's own touch handler (_SpriteUI.LookAtTouch, the same path a
// phone touch takes), takes Game view screenshots of each screen, logs a report of every camera and
// renderer plus any exceptions, then quits. Lines are prefixed "CH-PLAY:" in the log.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

[InitializeOnLoad]
public static class ColosseumHeroesPlayTest
{
    const string KeyActive = "CH.PlayTest.Active";
    const string KeyId = "CH.PlayTest.Id";
    const string OutDir = "D:/Projects/ColosseumHeroes64-tools/playtest";
    // Scripted session. Tap coordinates are the centres of the game's own button rects, in its
    // 480x320 virtual screen (origin top-left), taken from MainMenuGUI, OptionGUI, SaveSlotGUI,
    // SelectCharGUI and DifficultyGUI.
    struct Step
    {
        public float t; public string kind; public float x, y; public string label;
        public Step(float t, string kind, float x, float y, string label) { this.t = t; this.kind = kind; this.x = x; this.y = y; this.label = label; }
    }
    static readonly Step[] Script =
    {
        new Step(1f,  "sizes", 100, 100, ""),
        new Step(4f,  "shot", 0, 0, "menu"),
        new Step(5f,  "tap", 378f, 220.5f, "Ranking"),
        new Step(6.5f, "shot", 0, 0, "ranking-message"),
        new Step(7f,  "closedialog", 0, 0, ""),
        new Step(8f,  "tap", 384f, 174f, "Option"),
        new Step(10f, "shot", 0, 0, "option"),
        new Step(10.3f, "sizes", 175, 150, ""),
        new Step(10.8f, "shot", 0, 0, "option-sizes"),
        new Step(11.3f, "tap", 240f, 298.5f, "Option/Back"),
        new Step(12.3f, "tap", 239.5f, 154f, "New Game"),
        new Step(14f, "shot", 0, 0, "save-slots"),
        new Step(15f, "tap", 80f, 118f, "Slot 1"),
        new Step(17f, "shot", 0, 0, "select-char"),
        new Step(18f, "tap", 150f, 180f, "Character 1"),
        new Step(20f, "shot", 0, 0, "difficulty"),
        new Step(21f, "tap", 240f, 135.5f, "Easy"),
        new Step(23f, "shot", 0, 0, "loading"),
        new Step(30f, "shot", 0, 0, "game-1"),
        new Step(31f, "yestutorial", 0, 0, ""),
        new Step(32.5f, "nextpage", 0, 0, ""),
        new Step(34f, "nextpage", 0, 0, ""),
        new Step(35.5f, "nextpage", 0, 0, ""),
        new Step(36.5f, "arrowshot", 0, 0, "arrow-move"),
        new Step(37f, "nextpage", 0, 0, ""),
        new Step(38f, "arrowshot", 0, 0, "arrow-attack"),
        new Step(38.5f, "nextpage", 0, 0, ""),
        new Step(40f, "nextpage", 0, 0, ""),
        new Step(41f, "arrowshot", 0, 0, "arrow-money"),
        new Step(41.5f, "nextpage", 0, 0, ""),
        new Step(43f, "shot", 0, 0, "shop-big-controls"),
        new Step(43.2f, "controls", 0, 0, ""),
        new Step(44f, "finishstage", 0, 0, ""),
        new Step(49.5f, "nextpage", 0, 0, ""),
        new Step(51f, "shot", 0, 0, "battle-big-controls"),
        new Step(51.2f, "controls", 0, 0, ""),
        new Step(51.4f, "attack", 0, 0, ""),
        new Step(51.7f, "shot", 0, 0, "battle-cooldown"),
        new Step(52f, "sizes", 100, 100, ""),
        new Step(52.5f, "applycontrols", 0, 0, ""),
        new Step(53.5f, "shot", 0, 0, "battle-default-size"),
        new Step(53.7f, "controls", 0, 0, ""),
        new Step(58f, "report", 0, 0, ""),
    };
    const float QuitTime = 61f;

    static double _playStart = -1;
    static int _nextStep;
    static int _shotNo;
    static readonly Dictionary<string, int> _errors = new Dictionary<string, int>();
    static readonly MethodInfo LookAtTouch = typeof(_SpriteUI).GetMethod("LookAtTouch", BindingFlags.NonPublic | BindingFlags.Instance);

    static ColosseumHeroesPlayTest()
    {
        if (SessionState.GetBool(KeyActive, false))
            EditorApplication.update += Tick;
    }

    // Entry point: -executeMethod ColosseumHeroesPlayTest.Run [-chPlayTestId N]
    public static void Run()
    {
        string id = "0";
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
            if (args[i] == "-chPlayTestId") id = args[i + 1];
        Directory.CreateDirectory(OutDir);
        foreach (string dll in new[] { "Assembly-CSharp-firstpass.dll", "Assembly-CSharp.dll" })
            if (!File.Exists("Library/ScriptAssemblies/" + dll))
                Debug.Log("CH-PLAY: WARNING game assembly missing: Library/ScriptAssemblies/" + dll + " (game scripts will not run)");
        SessionState.SetBool(KeyActive, true);
        SessionState.SetString(KeyId, id);
        EditorSceneManager.OpenScene(EditorBuildSettings.scenes.Length > 0 ? EditorBuildSettings.scenes[0].path : "Assets/loadingScene.unity");
        Debug.Log("CH-PLAY: entering play mode, id " + id);
        EditorApplication.isPlaying = true;
    }

    static void Tick()
    {
        if (!EditorApplication.isPlaying) return;
        if (_playStart < 0)
        {
            _playStart = EditorApplication.timeSinceStartup;
            Application.logMessageReceived += OnLog;
            return;
        }
        double t = EditorApplication.timeSinceStartup - _playStart;
        string id = SessionState.GetString(KeyId, "0");

        while (_nextStep < Script.Length && t >= Script[_nextStep].t)
        {
            Step s = Script[_nextStep++];
            try
            {
                if (s.kind == "shot" || s.kind == "arrowshot")
                {
                    if (s.kind == "arrowshot") LogArrow(s.label);
                    _shotNo++;
                    string path = OutDir + "/play-" + id + "-" + _shotNo + ".png";
                    ScreenCapture.CaptureScreenshot(path);
                    Debug.Log("CH-PLAY: screenshot " + path + " (" + s.label + ") at " + t.ToString("F1") + " s, screen " + Screen.width + "x" + Screen.height + ", " + UiState());
                }
                else if (s.kind == "tap") Tap(s.x, s.y, s.label);
                else if (s.kind == "closedialog") CloseDialog();
                else if (s.kind == "fonts") LogFonts();
                else if (s.kind == "notutorial") AnswerTutorial(false);
                else if (s.kind == "yestutorial") AnswerTutorial(true);
                else if (s.kind == "sizes") SetSizes((int)s.x, (int)s.y);
                else if (s.kind == "controls") LogControls();
                else if (s.kind == "applycontrols") { if (InGameGUI.current != null) InGameGUI.current.ApplyControlScale(); Debug.Log("CH-PLAY: applied control size"); }
                else if (s.kind == "nextpage") NextTutorialPage();
                else if (s.kind == "premiumshop") { GameManager.instance.overlayDisplay.StartPremiumShop(); Debug.Log("CH-PLAY: opened premium shop, CP " + SaveData.GetCPoint()); LogStyles(); }
                else if (s.kind == "probe") StartProbe();
                else if (s.kind == "endprobe") { var p = UnityEngine.Object.FindObjectOfType<CHStyleProbe>(); if (p != null) UnityEngine.Object.Destroy(p.gameObject); }
                else if (s.kind == "freebuy") FreeBuy(0);
                else if (s.kind == "tutorialbox") ShowTestTextBox();
                else if (s.kind == "finishstage") { foreach (var tb in Resources.FindObjectsOfTypeAll<TextBox>()) if (tb.gameObject.scene.IsValid() && tb.IsShow()) tb.Show(false); GameManager.instance.FinishStage(); Debug.Log("CH-PLAY: left the shop for the stage; camera size " + Camera.main.orthographicSize + " aspect " + Camera.main.aspect + " clear " + Camera.main.clearFlags); }
                else if (s.kind == "crit") { float px = PlayerChar.instance.GetTransform().position.x + 1f; GameManager.instance.inputManager.ShowCriticalEffect(px); Debug.Log("CH-PLAY: critical effect at world x " + px + ", camera x " + Camera.main.transform.position.x); }
                else if (s.kind == "attack") { PlayerChar.instance.Attack(0); Debug.Log("CH-PLAY: attack"); }
                else if (s.kind == "closepremium") { GameManager.instance.overlayDisplay.SetNoneState(); Debug.Log("CH-PLAY: closed premium shop"); }
                else if (s.kind == "report")
                {
                    try { Report(); } catch (Exception e) { Debug.Log("CH-PLAY: report failed " + e); }
                }
            }
            catch (Exception e) { Debug.Log("CH-PLAY: step " + s.kind + " " + s.label + " failed " + e); }
        }
        if (t >= QuitTime)
        {
            Application.logMessageReceived -= OnLog;
            var sb = new StringBuilder("CH-PLAY: ===== errors and exceptions during play: " + _errors.Count + " distinct\n");
            foreach (var kv in _errors) sb.AppendLine("CH-PLAY: x" + kv.Value + " " + kv.Key);
            Debug.Log(sb.ToString());
            SessionState.SetBool(KeyActive, false);
            Debug.Log("CH-PLAY: done");
            EditorApplication.Exit(0);
        }
    }


    // Closes a CompatDialog message box (what its OK button does) so the scripted session can go on.
    static void CloseDialog()
    {
        var inst = typeof(CompatDialog).GetField("_instance", BindingFlags.NonPublic | BindingFlags.Static);
        var dlg = inst != null ? inst.GetValue(null) as CompatDialog : null;
        Debug.Log("CH-PLAY: dialog showing=" + CompatDialog.IsShowing + (dlg != null ? " message='" + typeof(CompatDialog).GetField("_message", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(dlg) + "'" : ""));
        if (dlg != null) typeof(CompatDialog).GetField("_message", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(dlg, null);
    }

    // Bitmap-font metrics: advance and size of 'E' and the pixel width of "Empty" as IMGUI lays it out.
    static void LogFonts()
    {
        var sb = new StringBuilder();
        foreach (Font f in Resources.FindObjectsOfTypeAll<Font>())
        {
            CharacterInfo ci;
            bool has = f.GetCharacterInfo('E', out ci);
            var style = new GUIStyle();
            style.font = f;
            Vector2 size = style.CalcSize(new GUIContent("Empty"));
            sb.AppendLine("CH-PLAY: font '" + f.name + "' dynamic=" + f.dynamic + " lineHeight=" + f.lineHeight + " material=" + (f.material != null ? f.material.name + "/" + f.material.shader.name + "/" + (f.material.mainTexture != null ? f.material.mainTexture.name : "no texture") : "none") +
                          " E=" + (has ? "advance " + ci.advance + " w " + ci.glyphWidth + " h " + ci.glyphHeight : "missing") + " 'Empty' size=" + size);
        }
        Debug.Log(sb.ToString());
    }


    // Answers the tutorial question the way its Yes/No buttons do.
    static void AnswerTutorial(bool yes)
    {
        var box = UnityEngine.Object.FindObjectOfType<TextBox>();
        if (box == null || box.callback_onYesNo == null) { Debug.Log("CH-PLAY: no tutorial question box"); return; }
        box.callback_onYesNo.DynamicInvoke(yes);
        Debug.Log("CH-PLAY: answered tutorial " + (yes ? "Yes" : "No"));
    }

    // Sets the Options sizes the way tapping the rows does.
    static void SetSizes(int buttons, int text)
    {
        for (int i = 0; i < 10 && ControlSettings.ButtonPercent != buttons; i++) ControlSettings.CycleButtonSize();
        for (int i = 0; i < 10 && ControlSettings.TextPercent != text; i++) ControlSettings.CycleTextSize();
        Debug.Log("CH-PLAY: sizes buttons " + ControlSettings.ButtonPercent + "% text " + ControlSettings.TextPercent + "% (hud text scale " + ControlSettings.HudTextScale + "), panel visible " + ControlSettingsPanel.IsVisible
            + ", rows on screen " + ControlSettingsPanel.LayoutToScreen(ControlSettingsPanel.ButtonsRowRect) + " " + ControlSettingsPanel.LayoutToScreen(ControlSettingsPanel.TextRowRect));
    }

    // Logs the control layout: sprite button bounds, touch areas and HUD text rects.
    static void LogControls()
    {
        var gui = InGameGUI.current;
        var f = typeof(InGameGUI);
        var flags = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
        var left = (Rect)f.GetField("leftButtonRect", flags).GetValue(gui);
        var right = (Rect)f.GetField("rightButtonRect", flags).GetValue(gui);
        var atk = (Rect[])f.GetField("attackButtonsRect", flags).GetValue(gui);
        var im = GameManager.instance.inputManager;
        im.ApplyControlScale();   // normally done on the next touch
        var it = typeof(InputManager);
        var tl = (Rect)it.GetField("leftButtonRect", flags).GetValue(im);
        var tr = (Rect)it.GetField("rightButtonRect", flags).GetValue(im);
        var ta = (Rect[])it.GetField("attackButtonRects", flags).GetValue(im);
        Debug.Log("CH-PLAY: controls scale " + ControlSettings.ButtonScale + " anchors " + InGameGUI.MoveAnchor + " " + InGameGUI.AttackAnchor
            + "\n  art move " + left + " " + right + " attack0 " + atk[0] + " attack1 " + atk[1]
            + "\n  touch move " + tl + " " + tr + " attack0 " + ta[0] + " attack1 " + ta[1]);
        var gm = GameManager.instance;
        Debug.Log("CH-PLAY: hud text stage " + gm.stageNumText.GetScreenRect() + " gold " + gm.moneyTextObj.GetScreenRect() + " kills " + gm.killCountText.GetScreenRect());
    }

    static TextBox FindTextBox()
    {
        foreach (var b in Resources.FindObjectsOfTypeAll<TextBox>())
            if (b.gameObject.scene.IsValid()) return b;   // the box is inactive while hidden
        return null;
    }

    // Taps the tutorial box the way a touch does, moving to the next page.
    static void NextTutorialPage()
    {
        var box = FindTextBox();
        if (box == null || box.callback_onTouched == null) { Debug.Log("CH-PLAY: no tutorial box to tap"); return; }
        box.callback_onTouched.DynamicInvoke();
        Debug.Log("CH-PLAY: tutorial page tapped, box shown " + box.IsShow());
    }

    // Logs where the tutorial arrow points and what it points at.
    static void LogArrow(string label)
    {
        var box = FindTextBox();
        if (box == null) { Debug.Log("CH-PLAY: " + label + ": no text box"); return; }
        var f = typeof(TextBox).GetField("arrowTarget", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        var m = typeof(TextBox).GetMethod("ResolveArrowTarget", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        object[] args = { Vector2.zero, false };
        bool ok = (bool)m.Invoke(box, args);
        int target = (int)f.GetValue(box);
        string what = "";
        Rect r;
        if (target >= 0 && target < 4 && InGameGUI.current != null && InGameGUI.current.GetGuideTargetRect(target, out r))
        {
            Vector2 a = TextBox.LayoutToScreen(new Vector2(r.xMin, r.yMin)), b = TextBox.LayoutToScreen(new Vector2(r.xMax, r.yMax));
            what = " target rect layout " + r + " screen (" + a.x.ToString("0") + "," + a.y.ToString("0") + ")-(" + b.x.ToString("0") + "," + b.y.ToString("0") + ")";
        }
        else if (target == TextBox.ArrowTarget_Money) what = " money text screen rect " + GameManager.instance.moneyTextObj.GetScreenRect();
        Debug.Log("CH-PLAY: " + label + ": shown " + box.IsShow() + " target " + target + " resolved " + ok + " point " + args[0] + " down " + args[1] + what + " screen " + Screen.width + "x" + Screen.height);
    }

    // Taps a premium item the way the Premium Shop list does and checks it was given without spending CP.
    static void FreeBuy(int id)
    {
        PremiumItem item = PremiumItemManager.instance.GetPremiumItem(id);
        int cpBefore = SaveData.GetCPoint();
        bool before = item.Purchased();
        GameManager.instance.overlayDisplay.PurchasePremiumItem(true, item);
        Debug.Log("CH-PLAY: premium item " + id + " '" + item.GetDescription().Replace("\n", " ") + "' owned " + before + " -> " + item.Purchased() + ", CP " + cpBefore + " -> " + SaveData.GetCPoint());
    }


    // The overlay's four label styles as the game uses them (background texture, font, colours).
    static void LogStyles()
    {
        var od = GameManager.instance.overlayDisplay;
        var sb = new StringBuilder();
        var skinField = typeof(OverlayDisplay).GetField("guiSkin", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
        var skin = skinField != null ? skinField.GetValue(od) as GUISkin : null;
        sb.AppendLine("CH-PLAY: overlay skin " + (skin != null ? skin.name : "none"));
        for (int i = 0; i < 4; i++)
        {
            GUIStyle st = od.GetLabelGUIStyle(i);
            if (st == null) { sb.AppendLine("CH-PLAY: style " + i + " null"); continue; }
            Texture2D bg = st.normal.background;
            sb.AppendLine("CH-PLAY: style " + i + " '" + st.name + "' bg=" + (bg != null ? bg.name + " " + bg.width + "x" + bg.height + " px(0,0)=" + SafePixel(bg) : "none") +
                          " scaledBgs=" + (st.normal.scaledBackgrounds != null ? st.normal.scaledBackgrounds.Length : -1) +
                          " text=" + st.normal.textColor + " font=" + (st.font != null ? st.font.name : "none") + " border=" + st.border + " align=" + st.alignment);
        }
        Debug.Log(sb.ToString());
    }

    static string SafePixel(Texture2D t)
    {
        try { return t.GetPixel(0, 0).ToString(); } catch (Exception e) { return "unreadable (" + e.GetType().Name + ")"; }
    }


    static void StartProbe()
    {
        var od = GameManager.instance.overlayDisplay;
        GUIStyle s1 = od.GetLabelGUIStyle(1), s3 = od.GetLabelGUIStyle(3);
        var list = new List<GUIStyle>(); var names = new List<string>();
        list.Add(s1); names.Add("style1 textarea");
        list.Add(s3); names.Add("style3 custom");
        var a = new GUIStyle(s1); a.normal.textColor = Color.white; list.Add(a); names.Add("style1 white text");
        var b = new GUIStyle(s3); b.normal.textColor = Color.black; list.Add(b); names.Add("style3 black text");
        var c = new GUIStyle(s1); c.font = null; list.Add(c); names.Add("style1 default font");
        var d = new GUIStyle(); d.font = s1.font; d.normal.textColor = Color.black; d.alignment = TextAnchor.MiddleCenter; list.Add(d); names.Add("new style black");
        var e = new GUIStyle(); e.font = s1.font; e.normal.textColor = new Color(0f, 0f, 0f, 0.99f); e.alignment = TextAnchor.MiddleCenter; list.Add(e); names.Add("new style alpha .99");
        var f = new GUIStyle(); f.font = s1.font; f.normal.textColor = new Color(0.2f, 0.1f, 0.05f, 1f); f.alignment = TextAnchor.MiddleCenter; list.Add(f); names.Add("new style dark brown");
        var go = new GameObject("CHStyleProbe");
        var probe = go.AddComponent<CHStyleProbe>();
        probe.styles = list.ToArray(); probe.names = names.ToArray();
        var m = s1.font != null ? s1.font.material : null;
        Debug.Log("CH-PLAY: probe started; font " + (s1.font != null ? s1.font.name : "none") + " material " + (m != null ? m.name + " shader " + m.shader.name + " tex " + (m.mainTexture != null ? m.mainTexture.name : "none") : "none"));
    }


    // Shows the in-game text box with a three-line message, like the tutorial's shop explanation.
    static void ShowTestTextBox()
    {
        TextBox box = null;
        foreach (var b in Resources.FindObjectsOfTypeAll<TextBox>())
            if (b.gameObject.scene.IsValid()) { box = b; break; }   // the box is inactive while hidden
        if (box == null) { Debug.Log("CH-PLAY: no text box"); return; }
        box.SetText("This is the item shop.\nYou can buy more weapons and equipment with money.\nTap the relevant icon to make your purchase.");
        box.Show(true);
        var st = box.guiSkin.GetStyle("Label");
        Debug.Log("CH-PLAY: text box shown; screen " + Screen.width + "x" + Screen.height + " padding " + st.padding.left + "/" + st.padding.right + " overflow " + st.overflow.left + "/" + st.overflow.right);
    }

    static void OnLog(string condition, string stackTrace, LogType type)
    {
        if (type != LogType.Error && type != LogType.Exception && type != LogType.Assert) return;
        if (condition.StartsWith("CH-PLAY")) return;
        string first = stackTrace;
        int nl = first.IndexOf('\n');
        if (nl >= 0) first = first.Substring(0, nl);
        string key = type + ": " + condition + (first.Length > 0 ? " @ " + first : "");
        if (key.Length > 400) key = key.Substring(0, 400);
        int n;
        _errors.TryGetValue(key, out n);
        _errors[key] = n + 1;
    }

    // Current menu screen and whether the menu accepts input.
    static string UiState()
    {
        var ui = UnityEngine.Object.FindObjectOfType<MyUIManager>();
        if (ui == null) return "MyUIManager none";
        var active = typeof(MyUIManager).GetField("_bActive", BindingFlags.NonPublic | BindingFlags.Instance);
        return "screen " + (ui.CurrentGUIScene != null ? ui.CurrentGUIScene.GetType().Name : "null") +
               " inputActive=" + (active != null ? active.GetValue(ui) : "?") + " uiObjectActive=" + ui.gameObject.activeInHierarchy;
    }

    // A finger tap at (vx, vy) in the game's 480x320 virtual screen (origin top-left): a Began and an
    // Ended touch fed to every _SpriteUI, which maps it to screen pixels the same way it maps a real touch.
    static void Tap(float vx, float vy, string label)
    {
        int w = Screen.width, h = Screen.height;
        string before = UiState();
        var uis = UnityEngine.Object.FindObjectsOfType<_SpriteUI>();
        foreach (_SpriteUI ui in uis)
        {
            float vyBottom = ui.ZeroLocation == _SpriteUI.ZeroLocationEnum.UpperLeft ? 320f - vy : vy;
            var touch = new Touch();
            touch.fingerId = 0;
            touch.position = new Vector2((vx - 240f) * h / 320f + w * 0.5f, vyBottom * h / 320f);
            touch.phase = TouchPhase.Began;
            LookAtTouch.Invoke(ui, new object[] { touch });
            touch.phase = TouchPhase.Ended;
            LookAtTouch.Invoke(ui, new object[] { touch });
        }
        Debug.Log("CH-PLAY: tap '" + label + "' at virtual (" + vx + ", " + vy + ") on " + uis.Length + " sprite UI(s); before: " + before + "; after: " + UiState());
    }

    static string GetPath(Transform t)
    {
        var sb = new StringBuilder(t.name);
        for (Transform p = t.parent; p != null; p = p.parent) sb.Insert(0, p.name + "/");
        return sb.ToString();
    }

    static void Report()
    {
        var sb = new StringBuilder();
        sb.AppendLine("CH-PLAY: ===== report: active scene " + UnityEngine.SceneManagement.SceneManager.GetActiveScene().name +
                      ", screen " + Screen.width + "x" + Screen.height + ", time " + Time.time.ToString("F1"));
        foreach (Camera c in Camera.allCameras)
        {
            sb.AppendLine(string.Format("CH-PLAY: camera '{0}' enabled={1} depth={2} mask=0x{3:X} clear={4} bg={5} ortho={6} size={7} fov={8} near={9} far={10} pos={11} rot={12} rect={13}",
                GetPath(c.transform), c.enabled, c.depth, c.cullingMask, c.clearFlags, c.backgroundColor, c.orthographic, c.orthographicSize,
                c.fieldOfView, c.nearClipPlane, c.farClipPlane, c.transform.position, c.transform.eulerAngles, c.rect));
        }
        int n = 0;
        foreach (Renderer r in UnityEngine.Object.FindObjectsOfType<Renderer>())
        {
            if (n++ >= 400) { sb.AppendLine("CH-PLAY: (more renderers not listed)"); break; }
            Material m = r.sharedMaterial;
            string shader = m != null && m.shader != null ? m.shader.name + (m.shader.isSupported ? "" : " [UNSUPPORTED]") : "none";
            Texture tex = m != null && m.HasProperty("_MainTex") ? m.mainTexture : null;
            string mesh = "";
            var mf = r.GetComponent<MeshFilter>();
            if (mf != null && mf.sharedMesh != null) mesh = " mesh=" + mf.sharedMesh.name + " v=" + mf.sharedMesh.vertexCount + " meshBounds=" + mf.sharedMesh.bounds;
            sb.AppendLine(string.Format("CH-PLAY: renderer '{0}' type={1} active={2} enabled={3} visible={4} layer={5} bounds={6} shader={7} tex={8}{9} queue={10}",
                GetPath(r.transform), r.GetType().Name, r.gameObject.activeInHierarchy, r.enabled, r.isVisible, r.gameObject.layer, r.bounds,
                shader, tex != null ? tex.name + " " + tex.width + "x" + tex.height : "none", mesh, m != null ? m.renderQueue : -1));
        }
        foreach (MonoBehaviour mb in UnityEngine.Object.FindObjectsOfType<MonoBehaviour>())
            if (mb != null && !mb.enabled && mb.gameObject.activeInHierarchy)
                sb.AppendLine("CH-PLAY: disabled script " + mb.GetType().Name + " on '" + GetPath(mb.transform) + "'");
        Debug.Log(sb.ToString());
    }

    static string Safe(string n)
    {
        var sb = new StringBuilder();
        foreach (char ch in n) sb.Append(char.IsLetterOrDigit(ch) ? ch : '_');
        return sb.ToString();
    }

    // Renders each camera on its own into a texture pre-filled with dark teal (0, 0.5, 0.25), so whatever the camera
    // itself draws is visible (teal = untouched; magenta would be confused with Unity's error shader), and dumps material, mesh and lighting details.
    static void Diagnose(string id)
    {
        var sb = new StringBuilder();
        sb.AppendLine("CH-PLAY: ===== diagnose: gfx " + SystemInfo.graphicsDeviceType + ", colorSpace " + QualitySettings.activeColorSpace +
                      ", Camera.main " + (Camera.main != null ? GetPath(Camera.main.transform) : "null"));
        sb.AppendLine(string.Format("CH-PLAY: render settings fog={0} fogMode={1} fogColor={2} fogDensity={3} fogStart={4} fogEnd={5} ambientMode={6} ambientLight={7} skybox={8}",
            RenderSettings.fog, RenderSettings.fogMode, RenderSettings.fogColor, RenderSettings.fogDensity, RenderSettings.fogStartDistance,
            RenderSettings.fogEndDistance, RenderSettings.ambientMode, RenderSettings.ambientLight, RenderSettings.skybox != null ? RenderSettings.skybox.name : "none"));
        int w = Screen.width, h = Screen.height;
        foreach (Camera c in Camera.allCameras)
        {
            sb.AppendLine("CH-PLAY: camera '" + GetPath(c.transform) + "' projection=" + c.projectionMatrix.ToString().Replace("\n", " | ") +
                          " worldToCamera=" + c.worldToCameraMatrix.ToString().Replace("\n", " | "));
            sb.AppendLine(string.Format("CH-PLAY: camera '{0}' target={1} display={2} hdr={3} path={4} occlusion={5}",
                GetPath(c.transform), c.targetTexture != null ? c.targetTexture.name : "screen", c.targetDisplay, c.allowHDR, c.actualRenderingPath, c.useOcclusionCulling));
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
            RenderTexture prevActive = RenderTexture.active, prevTarget = c.targetTexture;
            RenderTexture.active = rt;
            GL.Clear(true, true, new Color(0f, 0.5f, 0.25f, 1f));
            c.targetTexture = rt;
            c.Render();
            c.targetTexture = prevTarget;
            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = prevActive;
            string path = OutDir + "/cam-" + id + "-" + Safe(c.name) + ".png";
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Color mid = tex.GetPixel(w / 2, h / 2), corner = tex.GetPixel(5, 5);
            sb.AppendLine("CH-PLAY: camera capture " + path + " center=" + mid + " corner=" + corner);
            UnityEngine.Object.DestroyImmediate(tex);
            rt.Release();
            UnityEngine.Object.DestroyImmediate(rt);
        }
        foreach (Renderer r in UnityEngine.Object.FindObjectsOfType<Renderer>())
        {
            if (r.gameObject.layer != 0) continue;
            Material m = r.sharedMaterial;
            if (m == null) { sb.AppendLine("CH-PLAY: detail '" + GetPath(r.transform) + "' no material"); continue; }
            Texture t = m.HasProperty("_MainTex") ? m.mainTexture : null;
            sb.AppendLine(string.Format("CH-PLAY: detail '{0}' shader={1} supported={2} passes={3} queue={4} keywords=[{5}] color={6} tex={7} texScale={8} texOffset={9} lossyScale={10} worldPos={11}",
                GetPath(r.transform), m.shader.name, m.shader.isSupported, m.passCount, m.renderQueue, string.Join(",", m.shaderKeywords),
                m.HasProperty("_Color") ? m.color.ToString() : "-",
                t != null ? t.name + " " + t.width + "x" + t.height + " " + t.GetType().Name + (t is Texture2D ? " fmt=" + ((Texture2D)t).format : "") : "none",
                m.HasProperty("_MainTex") ? m.mainTextureScale.ToString() : "-", m.HasProperty("_MainTex") ? m.mainTextureOffset.ToString() : "-",
                r.transform.lossyScale, r.transform.position));
            var mf = r.GetComponent<MeshFilter>();
            if (mf != null && mf.sharedMesh != null)
            {
                Mesh mesh = mf.sharedMesh;
                var v = new StringBuilder();
                Vector3[] verts = mesh.vertices; Vector2[] uv = mesh.uv; Vector3[] nrm = mesh.normals;
                for (int i = 0; i < verts.Length && i < 8; i++)
                    v.Append(" [" + verts[i] + (i < uv.Length ? " uv" + uv[i] : "") + (i < nrm.Length ? " n" + nrm[i] : "") + "]");
                sb.AppendLine("CH-PLAY: mesh '" + mesh.name + "' readable=" + mesh.isReadable + " tris=" + string.Join(",", mesh.triangles) + v);
            }
        }
        Debug.Log(sb.ToString());
    }

    // Renders the main camera alone into a teal-filled texture and returns the colours at a few points.
    static string Probe(Camera cam, System.Action drawExtra)
    {
        int w = Screen.width, h = Screen.height;
        var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
        RenderTexture prevActive = RenderTexture.active, prevTarget = cam.targetTexture;
        RenderTexture.active = rt;
        GL.Clear(true, true, new Color(0f, 0.5f, 0.25f, 1f));
        if (drawExtra != null) drawExtra();
        else { cam.targetTexture = rt; cam.Render(); cam.targetTexture = prevTarget; }
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        tex.Apply();
        RenderTexture.active = prevActive;
        string r = "center=" + tex.GetPixel(w / 2, h / 2) + " left=" + tex.GetPixel(w / 8, h / 2) + " top=" + tex.GetPixel(w / 2, h - 8);
        UnityEngine.Object.DestroyImmediate(tex);
        rt.Release();
        UnityEngine.Object.DestroyImmediate(rt);
        return r;
    }

    // Tries the background plane under controlled changes, to find what stops the main camera drawing it.
    static void Experiments()
    {
        var sb = new StringBuilder("CH-PLAY: ===== experiments\n");
        Camera cam = Camera.main;
        GameObject go = GameObject.Find("GUIBackground");
        if (cam == null || go == null) { Debug.Log("CH-PLAY: experiments skipped, camera " + (cam != null) + " background " + (go != null)); return; }
        Renderer r = go.GetComponent<Renderer>();
        MeshFilter mf = go.GetComponent<MeshFilter>();
        Material shared = r.sharedMaterial;
        var forceOff = typeof(Renderer).GetProperty("forceRenderingOff");
        sb.AppendLine("CH-PLAY: exp info renderingLayerMask=" + r.renderingLayerMask + " forceRenderingOff=" + (forceOff != null ? forceOff.GetValue(r, null) : "n/a") +
                      " staticBatch=" + r.isPartOfStaticBatch + " sortingLayer=" + r.sortingLayerID + "/" + r.sortingOrder + " hideFlags=" + go.hideFlags +
                      " inFrustum=" + GeometryUtility.TestPlanesAABB(GeometryUtility.CalculateFrustumPlanes(cam), r.bounds) +
                      " camType=" + cam.cameraType + " camScene=" + (cam.scene.IsValid() ? cam.scene.name : "none") + " objScene=" + go.scene.name);
        sb.AppendLine("CH-PLAY: exp V0 baseline " + Probe(cam, null));

        uint oldMask = r.renderingLayerMask;
        r.renderingLayerMask = 1;
        sb.AppendLine("CH-PLAY: exp V1 renderingLayerMask=1 " + Probe(cam, null));
        r.renderingLayerMask = oldMask;

        int oldCull = cam.cullingMask;
        cam.cullingMask = ~0;
        sb.AppendLine("CH-PLAY: exp V2 cullingMask=all " + Probe(cam, null));
        cam.cullingMask = oldCull;

        Shader unlit = Shader.Find("Unlit/Texture");
        Material test = null;
        if (unlit != null)
        {
            test = new Material(unlit);
            test.mainTexture = shared.mainTexture;
            r.sharedMaterial = test;
            sb.AppendLine("CH-PLAY: exp V3 Unlit/Texture " + Probe(cam, null));
            r.sharedMaterial = shared;
        }
        else sb.AppendLine("CH-PLAY: exp V3 Unlit/Texture not found");

        Material q3000 = new Material(shared);
        q3000.renderQueue = 3000;
        r.sharedMaterial = q3000;
        sb.AppendLine("CH-PLAY: exp V6 same shader, queue 3000 " + Probe(cam, null));
        r.sharedMaterial = shared;
        UnityEngine.Object.DestroyImmediate(q3000);

        RenderingPath oldPath = cam.renderingPath;
        cam.renderingPath = RenderingPath.Forward;
        sb.AppendLine("CH-PLAY: exp V7 camera Forward path (actual " + cam.actualRenderingPath + ") " + Probe(cam, null));
        cam.renderingPath = oldPath;

        Shader ff = Shader.Find("MyAlpha1");
        if (ff != null)
        {
            Material ffMat = new Material(ff);
            ffMat.mainTexture = shared.mainTexture;
            r.sharedMaterial = ffMat;
            sb.AppendLine("CH-PLAY: exp V8 fixed-function MyAlpha1 (queue " + ffMat.renderQueue + ") " + Probe(cam, null));
            ffMat.renderQueue = 2000;
            sb.AppendLine("CH-PLAY: exp V9 fixed-function MyAlpha1 at queue 2000 " + Probe(cam, null));
            r.sharedMaterial = shared;
            UnityEngine.Object.DestroyImmediate(ffMat);
        }

        Matrix4x4 model = r.localToWorldMatrix;
        Mesh mesh = mf != null ? mf.sharedMesh : null;
        System.Action drawNow = () =>
        {
            GL.PushMatrix();
            GL.LoadProjectionMatrix(cam.projectionMatrix);
            GL.modelview = cam.worldToCameraMatrix;
            bool ok = shared.SetPass(0);
            Graphics.DrawMeshNow(mesh, model);
            GL.PopMatrix();
            sb.AppendLine("CH-PLAY: exp V4 SetPass(0)=" + ok);
        };
        if (mesh != null) sb.AppendLine("CH-PLAY: exp V4 DrawMeshNow own material " + Probe(cam, drawNow));
        if (mesh != null && test != null)
        {
            System.Action drawUnlit = () =>
            {
                GL.PushMatrix();
                GL.LoadProjectionMatrix(cam.projectionMatrix);
                GL.modelview = cam.worldToCameraMatrix;
                test.SetPass(0);
                Graphics.DrawMeshNow(mesh, model);
                GL.PopMatrix();
            };
            sb.AppendLine("CH-PLAY: exp V5 DrawMeshNow Unlit/Texture " + Probe(cam, drawUnlit));
        }
        var unsupported = new StringBuilder();
        foreach (Shader sh in Resources.FindObjectsOfTypeAll<Shader>())
            if (!sh.isSupported) unsupported.Append(sh.name + "; ");
        sb.AppendLine("CH-PLAY: exp unsupported shaders: " + unsupported);
        if (test != null) UnityEngine.Object.DestroyImmediate(test);
        Debug.Log(sb.ToString());
    }
}
