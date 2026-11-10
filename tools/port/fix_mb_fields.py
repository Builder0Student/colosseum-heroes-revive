"""Restore MonoBehaviour field values that AssetRipper dropped, decoding them from the raw 3.5-layout data.

Usage: fix_mb_fields.py <converted Data dir> <InfoJson 3.5.0.json> <exported Assets dir>
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
import sf8, tt

data_dir, tree_path, assets = sys.argv[1:4]
T = tt.load_trees(tree_path)
FILES = [f for f in sf8.data_files(data_dir) if f != "unity default resources"]

# class -> list of (field, kind[, target class id / script])
FIELDS = {
    "PlaySound": [("audioSource", "pptr", 82)],
    "ScoreText": [("guiText", "pptr", 132)],
    "DestroyAfterTime": [("destroyTime", "float")],
    "FramesPerSecond": [("updateInterval", "float")],
    "LoadingScene": [("_sceneToLoad", "string")],
    "iOSMessageHandler": [("myUIManager", "pptr", "MyUIManager")],
    "EZGUIEventHandler": [("_myUIManager", "pptr", "MyUIManager")],
}

# ---------- raw side ----------
sfs = {f: sf8.SF8(os.path.join(data_dir, f)) for f in FILES}


def externals(s):
    b, p = s.raw, s.meta_tail_off
    n, = struct.unpack_from("<i", b, p); p += 4
    out = []
    for _ in range(n):
        e = b.index(b"\0", p); p = e + 1
        p += 20
        e = b.index(b"\0", p); out.append(os.path.basename(b[p:e].decode())); p = e + 1
    return out


EXT = {f: externals(s) for f, s in sfs.items()}
OBJ = {(f, o.path_id): o for f, s in sfs.items() for o in s.objects}


def resolve(f, fid, pid):
    return (f if fid == 0 else EXT[f][fid - 1], pid)


def rd(key):
    o = OBJ[key]
    return tt.read(T[o.class_id], o.data)[0]


SCRIPT = {}
for k, o in OBJ.items():
    if o.class_id == 115:
        SCRIPT[k] = rd(k)["m_ClassName"]

GO_OF = {}      # component key -> go key
GO_COMPS = {}   # go key -> [(class_id, comp key)]
TR_PARENT = {}  # go key -> parent go key
for k, o in OBJ.items():
    if o.class_id == 1:
        d = rd(k)
        comps = []
        for pair in d["m_Component"]:
            cid, ptr = pair["first"], pair["second"]
            ck = resolve(k[0], ptr["m_FileID"], ptr["m_PathID"])
            comps.append((cid, ck)); GO_OF[ck] = k
        GO_COMPS[k] = comps
for go, comps in GO_COMPS.items():
    for cid, ck in comps:
        if cid == 4 and ck in OBJ:
            d = rd(ck)
            fa = d["m_Father"]
            if fa["m_PathID"]:
                TR_PARENT[go] = GO_OF.get(resolve(ck[0], fa["m_FileID"], fa["m_PathID"]))


def go_name(go):
    return rd(go)["m_Name"]


def go_path(go):
    parts = []
    while go:
        parts.append(go_name(go)); go = TR_PARENT.get(go)
    return "/".join(reversed(parts))


def mb_script(k):
    d = OBJ[k].data
    fid, pid = struct.unpack_from("<ii", d, 12)
    return SCRIPT.get(resolve(k[0], fid, pid))


# ---------- yaml side ----------
guid_of_script = {}
for dp, _, fs in os.walk(assets):
    for fn in fs:
        if fn.endswith(".cs.meta"):
            g = re.search(r"^guid: (\w+)", open(os.path.join(dp, fn)).read(), re.M).group(1)
            guid_of_script[fn[:-8]] = g


class YFile:
    def __init__(self, path):
        self.path = path
        self.text = open(path).read()
        self.docs = {}
        for m in re.finditer(r"^--- !u!(\d+) &(-?\d+)[^\n]*\n(.*?)(?=^--- |\Z)", self.text, re.S | re.M):
            self.docs[m.group(2)] = (int(m.group(1)), m.group(3))
        self.go_name, self.go_comps, self.parent = {}, {}, {}
        tr_go = {}
        for fid, (cls, body) in self.docs.items():
            if cls == 1:
                self.go_name[fid] = re.search(r"m_Name: ?(.*)", body).group(1).strip()
                self.go_comps[fid] = re.findall(r"component: \{fileID: (-?\d+)\}", body)
            elif cls == 4:
                tr_go[fid] = re.search(r"m_GameObject: \{fileID: (-?\d+)\}", body).group(1)
        for fid, (cls, body) in self.docs.items():
            if cls == 4:
                fa = re.search(r"m_Father: \{fileID: (-?\d+)\}", body).group(1)
                if fa != "0":
                    self.parent[tr_go[fid]] = tr_go.get(fa)

    def path_of(self, go):
        parts = []
        while go:
            parts.append(self.go_name[go]); go = self.parent.get(go)
        return "/".join(reversed(parts))

    def find_go(self, path):
        return [g for g in self.go_name if self.path_of(g) == path]

    def comp(self, go, cls=None, script_guid=None):
        for c in self.go_comps[go]:
            ccls, body = self.docs[c]
            if cls is not None and ccls != cls:
                continue
            if script_guid and f"guid: {script_guid}," not in body:
                continue
            return c
        return None


yfiles = []
for dp, _, fs in os.walk(assets):
    for fn in fs:
        if fn.endswith((".unity", ".prefab")):
            yfiles.append(YFile(os.path.join(dp, fn)))

# ---------- patch ----------
edits = collections.defaultdict(list)
claimed = set()
log = []
for k, o in OBJ.items():
    if o.class_id != 114:
        continue
    cls = mb_script(k)
    if cls not in FIELDS:
        continue
    d = o.data
    nlen, = struct.unpack_from("<i", d, 20)
    p = 24 + ((nlen + 3) & ~3)
    go = GO_OF[k]
    gpath = go_path(go)
    lines = []
    for spec in FIELDS[cls]:
        name, kind = spec[0], spec[1]
        if kind == "float":
            v, = struct.unpack_from("<f", d, p); p += 4
            lines.append((name, repr(v)))
        elif kind == "string":
            n, = struct.unpack_from("<i", d, p); p += 4
            v = d[p:p + n].decode(); p += (n + 3) & ~3
            lines.append((name, v))
        elif kind == "pptr":
            fid, pid = struct.unpack_from("<ii", d, p); p += 8
            lines.append((name, ("ref", resolve(k[0], fid, pid) if pid else None, spec[2])))
    assert p == len(d), (cls, k, p, len(d))
    matches = [(yf, g) for yf in yfiles for g in yf.find_go(gpath)]
    sguid = guid_of_script[cls]
    placed = False
    for yf, g in matches:
        mb = yf.comp(g, 114, sguid)
        if not mb:
            continue
        if (yf.path, mb) in claimed:
            continue
        out = []
        for name, v in lines:
            if isinstance(v, tuple):
                tgt = v[1]
                if tgt is None:
                    out.append(f"  {name}: {{fileID: 0}}")
                    continue
                tgo = GO_OF[tgt]
                tpath = go_path(tgo)
                tg = [g2 for g2 in yf.find_go(tpath)]
                assert tg, (cls, name, tpath, yf.path)
                want = v[2]
                tc = yf.comp(tg[0], want) if isinstance(want, int) else yf.comp(tg[0], 114, guid_of_script[want])
                assert tc, (cls, name, tpath, want)
                out.append(f"  {name}: {{fileID: {tc}}}")
            else:
                out.append(f"  {name}: {v}")
        claimed.add((yf.path, mb))
        edits[yf.path].append((mb, out))
        log.append(f"{cls} on '{gpath}' in {os.path.relpath(yf.path, assets)}: {out}")
        placed = True
        break
    if not placed:
        log.append(f"!! no YAML match for {cls} on '{gpath}'")

for path, items in edits.items():
    text = open(path).read()
    for fid, out in items:
        pat = re.compile(rf"(^--- !u!114 &{fid}\n(?:(?!^--- ).)*?m_EditorClassIdentifier:[^\n]*\n)", re.S | re.M)
        text, n = pat.subn(lambda m: m.group(1) + "\n".join(out) + "\n", text, count=1)
        assert n == 1, (path, fid)
    open(path, "w").write(text)
print("\n".join(log))
