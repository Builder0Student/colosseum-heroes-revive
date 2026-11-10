"""Apply compatibility patches to the decoded smali tree. Usage: patch_smali.py <apktool_dir>"""
import re, sys, pathlib, collections

root = pathlib.Path(sys.argv[1]) / "smali"
SHIM = "Lcom/gamevil/colosseumheroes/marketfree/compat/Shim;"
counts = collections.Counter()

def sub_all(text, pattern, repl, key):
    new, n = re.subn(pattern, repl, text)
    counts[key] += n
    return new

CTX_RECV = r"L(?:android/content/Context|android/content/ContextWrapper|android/app/Activity);"

for f in root.rglob("*.smali"):
    rel = f.relative_to(root).as_posix()
    if rel.startswith("com/gamevil/colosseumheroes/marketfree/compat/"):
        continue
    t = f.read_text(encoding="utf-8")
    o = t
    # 1. IMEI access -> safe wrapper (falls back to ANDROID_ID)
    t = sub_all(t, r"invoke-virtual(/range)? \{([^}]*)\}, Landroid/telephony/TelephonyManager;->getDeviceId\(\)Ljava/lang/String;",
                lambda m: f"invoke-static{m.group(1) or ''} {{{m.group(2)}}}, {SHIM}->getDeviceId(Landroid/telephony/TelephonyManager;)Ljava/lang/String;",
                "getDeviceId")
    # 2. world-readable/writeable modes -> masked
    t = sub_all(t, r"invoke-virtual(/range)? \{([^}]*)\}, " + CTX_RECV + r"->getSharedPreferences\(Ljava/lang/String;I\)Landroid/content/SharedPreferences;",
                lambda m: f"invoke-static{m.group(1) or ''} {{{m.group(2)}}}, {SHIM}->getSharedPreferences(Landroid/content/Context;Ljava/lang/String;I)Landroid/content/SharedPreferences;",
                "getSharedPreferences")
    t = sub_all(t, r"invoke-virtual(/range)? \{([^}]*)\}, " + CTX_RECV + r"->openFileOutput\(Ljava/lang/String;I\)Ljava/io/FileOutputStream;",
                lambda m: f"invoke-static{m.group(1) or ''} {{{m.group(2)}}}, {SHIM}->openFileOutput(Landroid/content/Context;Ljava/lang/String;I)Ljava/io/FileOutputStream;",
                "openFileOutput")
    # 3. implicit service intents (old Market billing, Unity LVL, KT store library)
    if rel in ("com/prime31/billing/BillingService.smali", "com/unity3d/player/a/e.smali"):
        t = sub_all(t, r"invoke-virtual \{([^}]*)\}, L(?:com/prime31/billing/BillingService|android/content/Context);->bindService\(Landroid/content/Intent;Landroid/content/ServiceConnection;I\)Z",
                    lambda m: f"invoke-static {{{m.group(1)}}}, {SHIM}->bindService(Landroid/content/Context;Landroid/content/Intent;Landroid/content/ServiceConnection;I)Z",
                    "bindService")
    if rel == "com/kaf/KafManager.smali":
        t = sub_all(t, r"invoke-virtual(/range)? \{([^}]*)\}, Landroid/content/Context;->startService\(Landroid/content/Intent;\)Landroid/content/ComponentName;",
                    lambda m: f"invoke-static{m.group(1) or ''} {{{m.group(2)}}}, {SHIM}->startService(Landroid/content/Context;Landroid/content/Intent;)Landroid/content/ComponentName;",
                    "startService")
    # 4. Unity CPU detection hardening
    if rel == "com/unity3d/player/a.smali":
        ctor = re.search(r"\.method constructor <init>\(\)V.*?\.end method", t, re.S)
        body = ctor.group(0)
        nb, n = re.subn(r"invoke-static \{(v\d+)\}, Ljava/lang/Integer;->decode\(Ljava/lang/String;\)Ljava/lang/Integer;",
                        lambda m: f"invoke-static {{{m.group(1)}}}, {SHIM}->decodeArch(Ljava/lang/String;)Ljava/lang/Integer;", body)
        counts["decodeArch"] += n
        assert nb.count("return-void") == 1
        nb = nb.replace("return-void",
                        "iget v0, p0, Lcom/unity3d/player/a;->a:I\n\n"
                        f"    invoke-static {{v0}}, {SHIM}->fixCpuFlags(I)I\n\n"
                        "    move-result v0\n\n"
                        "    iput v0, p0, Lcom/unity3d/player/a;->a:I\n\n"
                        "    return-void")
        counts["fixCpuFlags"] += 1
        t = t.replace(body, nb)
    # 5. dead Gamevil ad/news server -> fail fast like offline
    t = sub_all(t, r'"http://www\.gamevil\.com/preload/', '"http://127.0.0.1:9/preload/', "gamevil_url")
    if t != o:
        f.write_text(t, encoding="utf-8")
        counts["files"] += 1

for k, v in sorted(counts.items()):
    print(f"{k}: {v}")
