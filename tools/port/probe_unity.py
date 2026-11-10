"""Probe Unity 3.4 data with UnityPy: count object types per file and try reading a few of each."""
import sys, collections, traceback, pathlib
import UnityPy

data_dir = pathlib.Path(sys.argv[1])
env = UnityPy.load(str(data_dir))
types = collections.Counter()
ok = collections.Counter()
fail = collections.Counter()
first_err = {}
for obj in env.objects:
    t = obj.type.name
    types[t] += 1
    if ok[t] + fail[t] >= 40:
        continue
    try:
        d = obj.read()
        ok[t] += 1
    except Exception as e:
        fail[t] += 1
        first_err.setdefault(t, f"{type(e).__name__}: {str(e)[:120]}")
print("files:", len(env.files))
for f_name, f in list(env.files.items())[:5]:
    print("  ", f_name, getattr(f, "unity_version", "?"))
print(f"{'type':28} {'count':>6} {'read_ok':>8} {'read_fail':>9}")
for t, n in types.most_common():
    print(f"{t:28} {n:6} {ok[t]:8} {fail[t]:9}  {first_err.get(t, '')}")
