"""Compare original vs patched APK: game data unchanged, native proxies patched, shim refs resolvable.
Usage: verify.py original.apk patched.apk patched_smali_dir"""
import sys, zipfile, re, pathlib

orig, new = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
smali = pathlib.Path(sys.argv[3])
oi = {i.filename: i for i in orig.infolist()}
ni = {i.filename: i for i in new.infolist()}

data = [n for n in oi if n.startswith("assets/")]
changed = [n for n in data if n not in ni or ni[n].CRC != oi[n].CRC]
print(f"assets: {len(data)} in original, changed/missing in patched: {len(changed)} {changed[:5]}")
stored_lost = [n for n in data if oi[n].compress_type == 0 and ni.get(n) and ni[n].compress_type != 0]
print(f"assets that were stored but are now compressed: {stored_lost}")
for n in ("lib/armeabi/libunity.so", "lib/armeabi/libmono.so", "classes.dex", "AndroidManifest.xml"):
    print(f"{n}: changed={oi[n].CRC != ni[n].CRC}")
print("signature files:", sorted(n for n in ni if n.startswith("META-INF/")))

shim = (smali / "com/gamevil/colosseumheroes/marketfree/compat/Shim.smali").read_text()
defined = set(re.findall(r"\.method public static (\w+\([^)]*\)\S+)", shim))
refs = {}
for f in smali.rglob("*.smali"):
    for m in re.findall(r"Lcom/gamevil/colosseumheroes/marketfree/compat/Shim;->(\w+\([^)]*\)\S+)", f.read_text()):
        refs[m] = refs.get(m, 0) + 1
missing = [r for r in refs if r not in defined]
print("Shim call targets:", {k: v for k, v in sorted(refs.items())})
print("unresolved Shim refs:", missing)
