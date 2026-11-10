"""Fix GameObject active flags lost by AssetRipper for Unity 3.x data.

* Scene objects (mainData = loadingScene, level0 = GameScene): restore m_IsActive from the raw data.
* Prefab assets: Unity 3.x stored project prefabs inactive and activated clones on Instantiate;
  modern Unity copies the asset's flag, so prefab GameObjects become active.
Usage: fix_active.py <converted Data dir> <InfoJson 3.5.0.json> <Assets dir>
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
import sf8, tt

data, tree, assets = sys.argv[1:4]
T = tt.load_trees(tree)
SCENES = {"mainData": "loadingScene.unity", "level0": "GameScene.unity"}
stats = collections.Counter()


def raw_scene(f):
    s = sf8.SF8(os.path.join(data, f))
    objs = {o.path_id: o for o in s.objects}
    rd = lambda pid: tt.read(T[objs[pid].class_id], objs[pid].data)[0]
    go, parent, comps = {}, {}, {}
    for pid, o in objs.items():
        if o.class_id == 1:
            d = rd(pid)
            go[pid] = (d["m_Name"], d["m_IsActive"])
            comps[pid] = sorted(p["first"] for p in d["m_Component"])
    tr_go = {}
    for pid, o in objs.items():
        if o.class_id == 4:
            d = rd(pid)
            tr_go[pid] = d["m_GameObject"]["m_PathID"]
    for pid, o in objs.items():
        if o.class_id == 4:
            fa = rd(pid)["m_Father"]["m_PathID"]
            if fa:
                parent[tr_go[pid]] = tr_go[fa]
    def path(g):
        parts = []
        while g:
            parts.append(go[g][0]); g = parent.get(g)
        return "/".join(reversed(parts))
    out = collections.defaultdict(list)
    for g in go:
        out[(path(g), tuple(comps[g]))].append(go[g][1])
    return out


def yaml_docs(text):
    return [(m.start(), int(m.group(1)), m.group(2), m.group(3)) for m in
            re.finditer(r"^--- !u!(\d+) &(-?\d+)[^\n]*\n(.*?)(?=^--- |\Z)", text, re.S | re.M)]


def comp_class(docs_by_id, cid):
    return docs_by_id[cid][0]


for raw_file, scene in SCENES.items():
    path = os.path.join(assets, scene)
    text = open(path, encoding="utf-8").read()
    docs = yaml_docs(text)
    by_id = {fid: (cls, body) for _, cls, fid, body in docs}
    name, parent, tr_go = {}, {}, {}
    for _, cls, fid, body in docs:
        if cls == 1:
            name[fid] = re.search(r"m_Name: ?(.*)", body).group(1).strip()
        elif cls == 4:
            tr_go[fid] = re.search(r"m_GameObject: \{fileID: (-?\d+)\}", body).group(1)
    for _, cls, fid, body in docs:
        if cls == 4:
            fa = re.search(r"m_Father: \{fileID: (-?\d+)\}", body).group(1)
            if fa != "0":
                parent[tr_go[fid]] = tr_go[fa]
    def ypath(g):
        parts = []
        while g:
            parts.append(name[g]); g = parent.get(g)
        return "/".join(reversed(parts))
    raw = raw_scene(raw_file)
    used = collections.Counter()
    new_text = text
    for _, cls, fid, body in docs:
        if cls != 1:
            continue
        cids = re.findall(r"component: \{fileID: (-?\d+)\}", body)
        # GUIText (132) became MonoBehaviour (114), GUILayer (92) was removed during conversion
        sig = tuple(sorted(by_id[c][0] for c in cids))
        key = (ypath(fid), sig)
        cands = raw.get(key)
        if cands is None:
            # fall back to path-only match (component list changed by conversions)
            alts = [v for (p, s), v in raw.items() if p == key[0]]
            cands = alts[0] if len(alts) == 1 else None
        if cands is None:
            stats["scene unmatched"] += 1
            print(f"  ?? {scene}: {key[0]} {sig}")
            continue
        i = used[key]; used[key] += 1
        active = cands[min(i, len(cands) - 1)]
        new_text = re.sub(rf"(^--- !u!1 &{fid}\n(?:(?!^--- ).)*?m_IsActive: )\d", rf"\g<1>{active}", new_text, count=1, flags=re.S | re.M)
        stats[f"scene active={active}"] += 1
    open(path, "w", encoding="utf-8").write(new_text)

for dp, _, fs in os.walk(assets):
    for fn in fs:
        if fn.endswith(".prefab"):
            p = os.path.join(dp, fn)
            t = open(p, encoding="utf-8").read()
            t2, n = re.subn(r"^  m_IsActive: 0$", "  m_IsActive: 1", t, flags=re.M)
            if n:
                open(p, "w", encoding="utf-8").write(t2)
                stats["prefab objects activated"] += n
print(dict(stats))
