using UnityEngine;

/// <summary>
/// Player-adjustable sizes added for modern phones (Options screen): the on-screen control buttons
/// and the HUD text (stage, gold, kills). Saved in PlayerPrefs.
/// </summary>
public static class ControlSettings
{
    public static readonly int[] ButtonPercents = { 100, 125, 150, 175, 200 };
    public static readonly int[] TextPercents = { 50, 75, 100, 125, 150, 175, 200 };
    const int DefaultButtonPercent = 100;
    const int DefaultTextPercent = 75;

    const string ButtonKey = "CH_ButtonSize";
    const string TextKey = "CH_TextSize";

    static int _buttonPercent = -1;
    static int _textPercent = -1;

    /// <summary>Changes whenever a setting changes, so layouts know to refresh.</summary>
    public static int Version { get; private set; }

    public static int ButtonPercent
    {
        get
        {
            if (_buttonPercent < 0) _buttonPercent = Valid(ButtonPercents, PlayerPrefs.GetInt(ButtonKey, DefaultButtonPercent), DefaultButtonPercent);
            return _buttonPercent;
        }
    }

    public static int TextPercent
    {
        get
        {
            if (_textPercent < 0) _textPercent = Valid(TextPercents, PlayerPrefs.GetInt(TextKey, DefaultTextPercent), DefaultTextPercent);
            return _textPercent;
        }
    }

    public static float ButtonScale { get { return ButtonPercent / 100f; } }

    public static float TextScale { get { return TextPercent / 100f; } }

    /// <summary>
    /// Scale for the HUD text. The game drew it at the font's own pixel size, which suited the
    /// 480-pixel-tall phones it was made for and is tiny on today's screens, so it is first scaled to
    /// look the same as it did there, then by the player's setting.
    /// </summary>
    public static float HudTextScale { get { return Mathf.Max(TextScale, Screen.height / 480f * TextScale); } }

    public static void CycleButtonSize()
    {
        _buttonPercent = Next(ButtonPercents, ButtonPercent);
        PlayerPrefs.SetInt(ButtonKey, _buttonPercent);
        PlayerPrefs.Save();
        Version++;
    }

    public static void CycleTextSize()
    {
        _textPercent = Next(TextPercents, TextPercent);
        PlayerPrefs.SetInt(TextKey, _textPercent);
        PlayerPrefs.Save();
        Version++;
    }

    /// <summary>Scales a rect by s, keeping the anchor point fixed (all values in the same space).</summary>
    public static Rect ScaleRect(Rect r, Vector2 anchor, float s)
    {
        return new Rect(anchor.x + (r.x - anchor.x) * s, anchor.y + (r.y - anchor.y) * s, r.width * s, r.height * s);
    }

    static int Next(int[] values, int current)
    {
        for (int i = 0; i < values.Length; i++)
            if (values[i] == current) return values[(i + 1) % values.Length];
        return values[0];
    }

    static int Valid(int[] values, int v, int fallback)
    {
        foreach (int x in values) if (x == v) return v;
        return fallback;
    }
}
