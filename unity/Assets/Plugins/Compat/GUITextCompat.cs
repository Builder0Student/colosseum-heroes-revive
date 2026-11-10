using UnityEngine;

/// <summary>
/// Stand-in for Unity's GUIText component (removed in Unity 2019.3). Same fields and screen-space
/// placement: transform.position.x/y are viewport coordinates (0..1), the anchor positions the text
/// block around that point, pixelOffset shifts it in pixels. Drawn with IMGUI on top of the scene.
/// </summary>
[ExecuteInEditMode]
public class GUITextCompat : MonoBehaviour
{
    public string text = "";
    public TextAnchor anchor = TextAnchor.UpperLeft;
    public TextAlignment alignment = TextAlignment.Left;
    public Vector2 pixelOffset;
    public float lineSpacing = 1f;
    public float tabSize = 4f;
    public Font font;
    public Material material;
    public int fontSize;
    public FontStyle fontStyle;
    public Color color = Color.white;
    public bool pixelCorrect = true;
    public bool richText = true;

    GUIStyle _style;
    readonly GUIContent _content = new GUIContent();

    void OnGUI()
    {
        if (string.IsNullOrEmpty(text)) return;
        float scale;
        Rect r = GetScreenRect(out scale);
        if (scale == 1f)
        {
            GUI.Label(r, _content, _style);
            return;
        }
        // Bitmap fonts can't be resized through the style, so the text is drawn scaled.
        Matrix4x4 old = GUI.matrix;
        GUI.matrix = old * Matrix4x4.TRS(new Vector3(r.x, r.y, 0f), Quaternion.identity, new Vector3(scale, scale, 1f));
        GUI.Label(new Rect(0f, 0f, r.width / scale, r.height / scale), _content, _style);
        GUI.matrix = old;
    }

    /// <summary>Where the text is drawn, in GUI screen pixels (origin top-left).</summary>
    public Rect GetScreenRect()
    {
        float scale;
        return GetScreenRect(out scale);
    }

    /// <summary>
    /// Where the text is drawn and its scale. The text is enlarged by ControlSettings.HudTextScale, and
    /// its distance from the nearest screen corner grows by the player's text setting so that stacked
    /// labels (stage, gold, kills) keep their spacing instead of overlapping.
    /// </summary>
    public Rect GetScreenRect(out float scale)
    {
        if (_style == null) _style = new GUIStyle();
        _style.font = font;
        bool dynamicFont = font == null || font.dynamic;
        _style.fontSize = dynamicFont ? fontSize : 0;
        _style.fontStyle = dynamicFont ? fontStyle : FontStyle.Normal;
        _style.richText = richText;
        _style.wordWrap = false;
        _style.alignment = alignment == TextAlignment.Left ? TextAnchor.UpperLeft
                         : alignment == TextAlignment.Center ? TextAnchor.UpperCenter : TextAnchor.UpperRight;
        Color c = color;
        if (material != null && material.HasProperty("_Color")) c *= material.color;
        _style.normal.textColor = c;

        _content.text = text;
        scale = ControlSettings.HudTextScale;
        Vector2 size = _style.CalcSize(_content) * scale;
        Vector3 p = transform.position;
        float t = ControlSettings.TextScale;
        float cornerX = p.x >= 0.5f ? 1f : 0f, cornerY = p.y >= 0.5f ? 1f : 0f;
        p.x = cornerX + (p.x - cornerX) * t;
        p.y = cornerY + (p.y - cornerY) * t;
        float x = p.x * Screen.width + pixelOffset.x * scale;
        float y = (1f - p.y) * Screen.height - pixelOffset.y * scale;
        switch (anchor)
        {
            case TextAnchor.UpperCenter: case TextAnchor.MiddleCenter: case TextAnchor.LowerCenter: x -= size.x * 0.5f; break;
            case TextAnchor.UpperRight: case TextAnchor.MiddleRight: case TextAnchor.LowerRight: x -= size.x; break;
        }
        switch (anchor)
        {
            case TextAnchor.MiddleLeft: case TextAnchor.MiddleCenter: case TextAnchor.MiddleRight: y -= size.y * 0.5f; break;
            case TextAnchor.LowerLeft: case TextAnchor.LowerCenter: case TextAnchor.LowerRight: y -= size.y; break;
        }
        if (pixelCorrect) { x = Mathf.Round(x); y = Mathf.Round(y); }
        return new Rect(x, y, size.x + scale, size.y + scale);
    }
}
