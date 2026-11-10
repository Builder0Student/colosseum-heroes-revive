using System;
using UnityEngine;

/// <summary>
/// Two extra rows on the Options screen, styled like its BGM / SOUND / BLOOD pills: "BUTTONS : 100%"
/// and "TEXT : 100%". Tapping a row steps through the sizes in ControlSettings.
/// Positions use the sprite UI's 480x320 layout (scaled to the screen height and centred), the same
/// space the rest of the Options screen is laid out in.
/// </summary>
public class ControlSettingsPanel : MonoBehaviour
{
    static ControlSettingsPanel _instance;

    // Layout space (480x320, origin top-left), below the BLOOD pill and above BACK.
    public static Rect ButtonsRowRect = new Rect(40f, 222f, 195f, 38f);
    public static Rect TextRowRect = new Rect(245f, 222f, 195f, 38f);

    bool _visible;
    System.Action _onTap;
    Font _font;
    GUIStyle _pillStyle, _labelStyle;
    Texture2D _pillTexture;
    static readonly Color ValueColor = new Color(1f, 0.69f, 0.05f, 1f);
    static readonly Color LabelColor = new Color(0.92f, 0.92f, 0.92f, 1f);

    public static void SetVisible(bool visible, System.Action onTap)
    {
        if (_instance == null)
        {
            if (!visible) return;
            var go = new GameObject("CHControlSettings");
            DontDestroyOnLoad(go);
            _instance = go.AddComponent<ControlSettingsPanel>();
        }
        _instance._visible = visible;
        _instance._onTap = onTap;
    }

    public static bool IsVisible { get { return _instance != null && _instance._visible; } }

    /// <summary>Layout rect to GUI screen pixels, mapped the way the sprite UI maps it.</summary>
    public static Rect LayoutToScreen(Rect r)
    {
        float s = Screen.height / 320f;
        return new Rect((r.x - 240f) * s + Screen.width * 0.5f, r.y * s, r.width * s, r.height * s);
    }

    void BuildStyles()
    {
        // Rounded dark pill with a light rim, drawn 9-sliced.
        const int w = 64, h = 48, rad = 22;
        _pillTexture = new Texture2D(w, h, TextureFormat.RGBA32, false);
        _pillTexture.wrapMode = TextureWrapMode.Clamp;
        Color fill = new Color(0.16f, 0.16f, 0.17f, 0.92f), rim = new Color(0.42f, 0.42f, 0.44f, 1f);
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                float cx = Mathf.Clamp(x + 0.5f, rad, w - rad), cy = Mathf.Clamp(y + 0.5f, rad, h - rad);
                float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(cx, cy));
                Color c = d <= rad - 2f ? fill : (d <= rad ? rim : Color.clear);
                if (d > rad - 1f && d <= rad) c.a *= Mathf.Clamp01(rad - d + 0.5f);   // soft outer edge
                _pillTexture.SetPixel(x, y, c);
            }
        _pillTexture.Apply();
        _pillStyle = new GUIStyle();
        _pillStyle.normal.background = _pillTexture;
        _pillStyle.border = new RectOffset(rad, rad, rad, rad);

        foreach (Font f in Resources.FindObjectsOfTypeAll<Font>())
            if (f.name == "MAILRAYS") { _font = f; break; }
        _labelStyle = new GUIStyle();
        _labelStyle.font = _font;
        _labelStyle.alignment = TextAnchor.UpperLeft;
        _labelStyle.wordWrap = false;
        if (_font == null) _labelStyle.fontSize = 24;
    }

    void OnGUI()
    {
        if (!_visible) return;
        GUI.depth = -10;
        if (_pillStyle == null || _pillTexture == null) BuildStyles();
        if (Row(ButtonsRowRect, "BUTTONS : ", ControlSettings.ButtonPercent + "%"))
        {
            ControlSettings.CycleButtonSize();
            if (_onTap != null) _onTap();
        }
        if (Row(TextRowRect, "TEXT : ", ControlSettings.TextPercent + "%"))
        {
            ControlSettings.CycleTextSize();
            if (_onTap != null) _onTap();
        }
    }

    bool Row(Rect layoutRect, string label, string value)
    {
        Rect r = LayoutToScreen(layoutRect);
        Event e = Event.current;
        bool pressed = e.type != EventType.Layout && Input.GetMouseButton(0) && r.Contains(e.mousePosition);
        Rect draw = pressed ? new Rect(r.x + r.width * 0.03f, r.y + r.height * 0.05f, r.width * 0.94f, r.height * 0.9f) : r;
        if (e.type == EventType.Repaint)
        {
            GUI.Box(draw, GUIContent.none, _pillStyle);
            var labelContent = new GUIContent(label);
            var valueContent = new GUIContent(value);
            Vector2 a = _labelStyle.CalcSize(labelContent), b = _labelStyle.CalcSize(valueContent);
            float nativeW = a.x + b.x, nativeH = Mathf.Max(a.y, b.y);
            // Text fills about 60% of the pill height, shrunk so the longest row fits; both rows use
            // the same size.
            float widest = _labelStyle.CalcSize(new GUIContent("BUTTONS : 200%")).x;
            float k = Mathf.Min(draw.height * 0.6f / Mathf.Max(1f, nativeH * 0.7f), draw.width * 0.84f / Mathf.Max(1f, widest));
            float x = draw.x + (draw.width - nativeW * k) * 0.5f;
            float y = draw.y + (draw.height - nativeH * k) * 0.5f;
            Matrix4x4 old = GUI.matrix;
            GUI.matrix = old * Matrix4x4.TRS(new Vector3(x, y, 0f), Quaternion.identity, new Vector3(k, k, 1f));
            _labelStyle.normal.textColor = LabelColor;
            GUI.Label(new Rect(0f, 0f, a.x + 1f, nativeH + 1f), labelContent, _labelStyle);
            _labelStyle.normal.textColor = ValueColor;
            GUI.Label(new Rect(a.x, 0f, b.x + 1f, nativeH + 1f), valueContent, _labelStyle);
            GUI.matrix = old;
        }
        return GUI.Button(r, GUIContent.none, GUIStyle.none);
    }
}
