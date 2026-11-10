"""Source migrations for the recovered Colosseum Heroes scripts (Unity 3.4 decompiled -> Unity 2019.4 + IL2CPP).

Each rule is a regex applied to every .cs file under Assets (excluding Assets/Compat, which is hand-written).
Idempotent: safe to run repeatedly. Usage: migrate.py <Assets dir>
"""
import os, re, sys, collections

assets = sys.argv[1]
stats = collections.Counter()

RULES = [
    # decompiler artifact: explicit interface implementations cannot be virtual
    ("explicit-iface-virtual", re.compile(r"^(\s*)virtual (\S+(?:<[^>]*>)? I\w+\.)", re.M), r"\1\2"),
    # iOS keyboard auto-rotation flags: no modern equivalent (Screen.autorotate* would lock screen rotation)
    ("iphone-kb-autorotate", re.compile(r"^[ \t]*iPhoneKeyboard\.autorotateTo\w+\s*=\s*[^;]+;[ \t]*\r?\n", re.M), ""),
    ("iphone-reachability", re.compile(r"\biPhoneSettings\.internetReachability\b"), "Application.internetReachability"),
    ("iphone-reachability-enum", re.compile(r"\biPhoneNetworkReachability\b"), "NetworkReachability"),
    ("iphone-model", re.compile(r"\biPhoneSettings\.model\b"), "SystemInfo.deviceModel"),
    ("iphone-kb-type", re.compile(r"\biPhoneKeyboardType\b"), "TouchScreenKeyboardType"),
    ("iphone-kb", re.compile(r"\biPhoneKeyboard\b"), "TouchScreenKeyboard"),
    ("camera-maincamera", re.compile(r"\bCamera\.mainCamera\b"), "Camera.main"),
]

# Java plugins (prime31 Flurry/Facebook/IAB/Tapjoy/Twitter, Gamevil ads/billing) are not in the new build:
# make their wrappers take the non-Android (no-op) path.
PLUGIN_FILES = {"FlurryAndroid.cs", "FacebookAndroid.cs", "IABAndroid.cs", "TapjoyAndroid.cs",
                "TwitterAndroid.cs", "GamevilADBinding.cs"}
PLUGIN_RULES = [
    ("plugin-eq-android", re.compile(r"(?:Application\.platform|_platform)\s*==\s*RuntimePlatform\.Android"), "false /* Java plugin removed */"),
    ("plugin-ne-android", re.compile(r"(?:Application\.platform|_platform)\s*!=\s*RuntimePlatform\.Android"), "true /* Java plugin removed */"),
]

ALERT_BODY = re.compile(
    r"(public static void (ShowAlertDialog\d?)\(string title, string msg\)\s*\{).*?androidJavaObject\.Call\(\"popupAlertDialog\", title, msg, \"Scripts\", \"(\w+)\"\);\s*\}\s*\}",
    re.S)
TSTORE_CALL = re.compile(r"_jo\.Call\(\"setPurchaseMessageHandler\", \"Scripts\"\);\s*_jo\.Call\(\"Purchase\", text\);")


def replace_outside_strings(text, pat, repl, key):
    out, n_total = [], 0
    for line in text.split("\n"):
        parts = re.split(r'("(?:\\.|[^"\\])*")', line)
        for i in range(0, len(parts), 2):
            parts[i], n = pat.subn(repl, parts[i])
            n_total += n
        out.append("".join(parts))
    stats[key] += n_total
    return "\n".join(out)


def alias_random(text):
    """`using System;` + `using UnityEngine;` makes `Random` ambiguous; the game meant UnityEngine.Random."""
    if ("using System;" in text and "using UnityEngine;" in text
            and re.search(r"(?<![\w.])Random\.(Range|value|seed|insideUnit\w+|onUnit\w+|rotation\w*|ColorHSV|InitState)", text)
            and not re.search(r"new\s+Random\s*\(", text)
            and "using Random = UnityEngine.Random;" not in text):
        text = text.replace("using UnityEngine;", "using UnityEngine;\nusing Random = UnityEngine.Random;", 1)
        stats["alias-random"] += 1
    return text


def guitext(text):
    """GUIText was removed in Unity 2019.3; the project uses the GUITextCompat component instead."""
    return replace_outside_strings(text, re.compile(r"\bGUIText\b"), "GUITextCompat", "guitext-type")


def alerts(text):
    """Gamevil activity's popupAlertDialog -> CompatDialog (IMGUI)."""
    def body(m):
        stats["alert-dialog"] += 1
        return m.group(1) + f'\n\t\tCompatDialog.Show(title, msg, "Scripts", "{m.group(3)}");\n\t}}'
    text = ALERT_BODY.sub(body, text)
    text, n = TSTORE_CALL.subn(
        'CompatDialog.Show("T store", "In-app purchases are no longer available in this version.", null, null);', text)
    stats["tstore-purchase"] += n
    return text


FUNCS = [alias_random, guitext, alerts]


def migrate(text, filename=""):
    for name, pat, repl in RULES:
        text, n = pat.subn(repl, text)
        stats[name] += n
    if filename in PLUGIN_FILES:
        for name, pat, repl in PLUGIN_RULES:
            text, n = pat.subn(repl, text)
            stats[name] += n
    for fn in FUNCS:
        text = fn(text)
    return text


for dp, _, fs in os.walk(assets):
    if os.sep + "Compat" in dp:
        continue
    for fn in fs:
        if fn.endswith(".cs"):
            p = os.path.join(dp, fn)
            t = open(p, encoding="utf-8-sig").read()
            n = migrate(t, fn)
            if n != t:
                open(p, "w", encoding="utf-8").write(n)
                stats["files"] += 1
print(dict(stats))
