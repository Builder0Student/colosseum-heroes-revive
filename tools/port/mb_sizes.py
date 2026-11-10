"""For each MonoBehaviour in the converted data, report script class name and bytes of field data beyond the base."""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
import sf8, tt

data = sys.argv[1]
T = tt.load_trees(sys.argv[2])
files = ["mainData", "level0", "sharedassets0.assets", "sharedassets1.assets"]
sfs = {f: sf8.SF8(os.path.join(data, f)) for f in files}

# externals order per file (file index 1..n) -> resolve PPtr to MonoScript in sharedassets0 (holds MonoScripts)
def externals(s):
    b = s.raw; p = s.meta_tail_off
    n, = struct.unpack_from("<i", b, p); p += 4
    out = []
    for _ in range(n):
        e = b.index(b"\0", p); p = e + 1           # empty string
        p += 16 + 4                                # guid + type
        e = b.index(b"\0", p); out.append(b[p:e].decode()); p = e + 1
    return out

scripts = {}
for f, s in sfs.items():
    for o in s.objects:
        if o.class_id == 115:
            d, _ = tt.read(T[115], o.data)
            scripts[(f, o.path_id)] = d["m_ClassName"]

report = collections.defaultdict(list)
for f, s in sfs.items():
    ext = externals(s)
    for o in s.objects:
        if o.class_id != 114:
            continue
        b = o.data
        fid, pid = struct.unpack_from("<ii", b, 12)
        nlen, = struct.unpack_from("<i", b, 20)
        base = 24 + ((nlen + 3) & ~3)
        target = f if fid == 0 else os.path.basename(ext[fid - 1])
        cls = scripts.get((target, pid), f"?{target}:{pid}")
        report[cls].append((f, o.path_id, len(b) - base))

for cls in sys.argv[3:]:
    print(cls, report.get(cls))
