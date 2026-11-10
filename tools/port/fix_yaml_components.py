"""Scene/prefab YAML fixes for components removed in Unity 2019.3+:
GUIText (132) -> MonoBehaviour GUITextCompat (same fileID, so references keep working); GUILayer (92) -> removed.
Usage: fix_yaml_components.py <Assets dir> <GUITextCompat guid>"""
import os, re, sys, collections

assets, compat_guid = sys.argv[1:3]
stats = collections.Counter()


def field(body, name, default=""):
    m = re.search(rf"^  {name}: ?(.*)$", body, re.M)
    return m.group(1) if m else default


def convert_guitext(fid, body):
    color = field(body, "m_Color")
    rgba = re.search(r"rgba: (\d+)", body)
    if rgba and int(rgba.group(1)) != 0:
        v = int(rgba.group(1))
        c = [(v >> s & 255) / 255 for s in (0, 8, 16, 24)]
    else:
        c = [1, 1, 1, 1]   # 3.4 GUIText had no colour of its own (font material default = white)
    text_line = re.search(r"^  m_Text: ?(.*(?:\n    .*)*)$", body, re.M)
    text = text_line.group(1) if text_line else "''"
    stats["guitext"] += 1
    return (f"--- !u!114 &{fid}\nMonoBehaviour:\n  m_ObjectHideFlags: 0\n  m_CorrespondingSourceObject: {{fileID: 0}}\n"
            f"  m_PrefabInstance: {{fileID: 0}}\n  m_PrefabAsset: {{fileID: 0}}\n"
            f"  m_GameObject: {field(body, 'm_GameObject')}\n  m_Enabled: {field(body, 'm_Enabled', '1')}\n"
            f"  m_EditorHideFlags: 0\n  m_Script: {{fileID: 11500000, guid: {compat_guid}, type: 3}}\n"
            f"  m_Name: \n  m_EditorClassIdentifier: \n"
            f"  text: {text}\n  anchor: {field(body, 'm_Anchor', '0')}\n  alignment: {field(body, 'm_Alignment', '0')}\n"
            f"  pixelOffset: {field(body, 'm_PixelOffset', '{x: 0, y: 0}')}\n  lineSpacing: {field(body, 'm_LineSpacing', '1')}\n"
            f"  tabSize: {field(body, 'm_TabSize', '4')}\n  font: {field(body, 'm_Font', '{fileID: 0}')}\n"
            f"  material: {field(body, 'm_Material', '{fileID: 0}')}\n  fontSize: {field(body, 'm_FontSize', '0')}\n"
            f"  fontStyle: {field(body, 'm_FontStyle', '0')}\n"
            f"  color: {{r: {c[0]:.4g}, g: {c[1]:.4g}, b: {c[2]:.4g}, a: {c[3]:.4g}}}\n"
            f"  pixelCorrect: {field(body, 'm_PixelCorrect', '1')}\n  richText: {field(body, 'm_RichText', '1')}\n")


for dp, _, fs in os.walk(assets):
    for fn in fs:
        if not fn.endswith((".unity", ".prefab")):
            continue
        path = os.path.join(dp, fn)
        text = open(path, encoding="utf-8").read()
        head, *docs = re.split(r"(?m)^(?=--- !u!)", text)
        removed = set()
        out = []
        for d in docs:
            m = re.match(r"--- !u!(\d+) &(-?\d+)[^\n]*\n", d)
            cls, fid = int(m.group(1)), m.group(2)
            body = d[m.end():]
            if cls == 132:
                out.append(convert_guitext(fid, body))
            elif cls == 92:
                removed.add(fid); stats["guilayer"] += 1
            else:
                out.append(d)
        if removed:
            out = [re.sub(r"^  - component: \{fileID: (-?\d+)\}\n", lambda mm: "" if mm.group(1) in removed else mm.group(0), d, flags=re.M) for d in out]
        new = head + "".join(out)
        if new != text:
            open(path, "w", encoding="utf-8").write(new)
            stats["files"] += 1
print(dict(stats))
