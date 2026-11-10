using UnityEngine;

/// <summary>
/// Replaces the Gamevil Java activity's popupAlertDialog(title, msg, receiverObject, receiverMethod):
/// shows a modal IMGUI dialog and, on OK, sends receiverMethod to the receiver GameObject.
/// </summary>
public class CompatDialog : MonoBehaviour
{
    string _title, _message, _receiver, _method;
    static CompatDialog _instance;

    /// <summary>True while a dialog is on screen (game buttons underneath should ignore taps).</summary>
    public static bool IsShowing { get { return _instance != null && _instance._message != null; } }

    public static void Show(string title, string message, string receiverObject, string receiverMethod)
    {
        if (_instance == null)
        {
            var go = new GameObject("CompatDialog");
            DontDestroyOnLoad(go);
            _instance = go.AddComponent<CompatDialog>();
        }
        _instance._title = title;
        _instance._message = message;
        _instance._receiver = receiverObject;
        _instance._method = receiverMethod;
        _instance.enabled = true;
    }

    GUIStyle _titleStyle, _labelStyle, _buttonStyle;
    int _styleSize;

    // Text is sized from the screen height so the box stays readable on high-resolution phones.
    void BuildStyles(int fontSize)
    {
        _styleSize = fontSize;
        _titleStyle = new GUIStyle(GUI.skin.label) { fontSize = fontSize, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter, wordWrap = true };
        _labelStyle = new GUIStyle(GUI.skin.label) { fontSize = fontSize, alignment = TextAnchor.MiddleCenter, wordWrap = true };
        _buttonStyle = new GUIStyle(GUI.skin.button) { fontSize = fontSize };
    }

    void OnGUI()
    {
        if (_message == null) return;
        GUI.depth = -1000;
        int fontSize = Mathf.Max(14, Mathf.RoundToInt(Screen.height / 20f));
        if (_labelStyle == null || _styleSize != fontSize) BuildStyles(fontSize);
        float w = Mathf.Min(Screen.width * 0.8f, fontSize * 26f), h = Mathf.Min(Screen.height * 0.7f, fontSize * 9f);
        var r = new Rect((Screen.width - w) / 2f, (Screen.height - h) / 2f, w, h);
        GUI.Box(new Rect(0, 0, Screen.width, Screen.height), GUIContent.none);
        GUI.Box(r, GUIContent.none);
        GUI.Box(r, GUIContent.none);
        float pad = fontSize * 0.6f;
        GUILayout.BeginArea(new Rect(r.x + pad, r.y + pad, r.width - 2f * pad, r.height - 2f * pad));
        if (!string.IsNullOrEmpty(_title)) GUILayout.Label(_title, _titleStyle);
        GUILayout.FlexibleSpace();
        GUILayout.Label(_message, _labelStyle);
        GUILayout.FlexibleSpace();
        if (GUILayout.Button("OK", _buttonStyle, GUILayout.Height(fontSize * 2.2f)))
        {
            string receiver = _receiver, method = _method;
            _message = null;
            enabled = false;
            if (!string.IsNullOrEmpty(receiver) && !string.IsNullOrEmpty(method))
            {
                GameObject target = GameObject.Find(receiver);
                if (target != null) target.SendMessage(method, SendMessageOptions.DontRequireReceiver);
            }
        }
        GUILayout.EndArea();
    }
}
