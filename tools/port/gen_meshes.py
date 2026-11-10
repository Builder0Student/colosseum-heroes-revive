"""Regenerate Unity 2019.4 Mesh YAML for every exported mesh from the original Unity 3.4.2 data.

Fixes: triangle strips -> triangle lists, explicit vertex channel layout, skin weights as BlendWeight/BlendIndices
in a separate stream, bind poses, bone name hashes, per-bone AABBs. Keeps each asset file's GUID/fileID.
Usage: gen_meshes.py <original Data dir> <InfoJson dir> <exported Assets dir>
"""
import sys, os, re, struct, zlib, math, glob
sys.path.insert(0, os.path.dirname(__file__))
import sf8, tt

src, info, assets = sys.argv[1:4]
T34 = tt.load_trees(os.path.join(info, "3.4.2.json"))
FILES = [f for f in sf8.data_files(src) if f != "unity default resources"]

raw_meshes = []
smr_bones = {}  # (file, mesh pathID) -> [bone names]
objs = {}
for f in FILES:
    s = sf8.SF8(os.path.join(src, f))
    for o in s.objects:
        objs[(f, o.path_id)] = o
for (f, pid), o in objs.items():
    if o.class_id == 43:
        d, _ = tt.read(T34[43], o.data)
        raw_meshes.append(((f, pid), d))


def rd(key):
    o = objs[key]
    return tt.read(T34[o.class_id], o.data)[0]


for (f, pid), o in objs.items():
    if o.class_id != 137:
        continue
    d = rd((f, pid))
    mp = d["m_Mesh"]
    if mp["m_FileID"] != 0:
        continue
    names = []
    for b in d["m_Bones"]:
        tr = rd((f, b["m_PathID"]))
        go = rd((f, tr["m_GameObject"]["m_PathID"]))
        names.append(go["m_Name"])
    smr_bones[(f, mp["m_PathID"])] = names


def pack35(d):
    """Same packing as convert34to35 (used only to match exported assets by their vertex bytes)."""
    chans = [(d["m_Vertices"], "3f", "xyz"), (d["m_Normals"], "3f", "xyz"), (d["m_Colors"], "I", None),
             (d["m_UV"], "2f", "xy"), (d["m_UV1"], "2f", "xy"), (d["m_Tangents"], "4f", "xyzw")]
    out = bytearray()
    for i in range(len(d["m_Vertices"])):
        for arr, fmt, keys in chans:
            if arr:
                out += struct.pack("<" + fmt, arr[i]["rgba"]) if keys is None else struct.pack("<" + fmt, *(arr[i][k] for k in keys))
    return bytes(out)


def strip_to_list(idx):
    tris = []
    for i in range(len(idx) - 2):
        a, b, c = idx[i], idx[i + 1], idx[i + 2]
        if a == b or b == c or a == c:
            continue
        tris += [a, b, c] if i % 2 == 0 else [b, a, c]
    return tris


def f(v):
    r = repr(float(v))
    return r[:-2] if r.endswith(".0") else r


def aabb_yaml(center, extent, indent):
    return (f"{indent}m_Center: {{x: {f(center['x'])}, y: {f(center['y'])}, z: {f(center['z'])}}}\n"
            f"{indent}m_Extent: {{x: {f(extent['x'])}, y: {f(extent['y'])}, z: {f(extent['z'])}}}\n")


def bounds(points):
    if not points:
        return {"x": 0, "y": 0, "z": 0}, {"x": 0, "y": 0, "z": 0}
    mn = [min(p[i] for p in points) for i in range(3)]
    mx = [max(p[i] for p in points) for i in range(3)]
    c = {k: (mn[i] + mx[i]) / 2 for i, k in enumerate("xyz")}
    e = {k: (mx[i] - mn[i]) / 2 for i, k in enumerate("xyz")}
    return c, e


def build_yaml(name, d, bone_names):
    verts = d["m_Vertices"]; n = len(verts)
    ib = d["m_IndexBuffer"]
    idx_all = list(struct.unpack(f"<{len(ib)//2}H", ib)) if d["m_Use16BitIndices"] else list(struct.unpack(f"<{len(ib)//4}I", ib))
    new_idx, subs = [], []
    for sm in d["m_SubMeshes"]:
        first = sm["firstByte"] // (2 if d["m_Use16BitIndices"] else 4)
        part = idx_all[first:first + sm["indexCount"]]
        tris = strip_to_list(part) if sm["isTriStrip"] else part
        used = tris or [0]
        pts = [(verts[i]["x"], verts[i]["y"], verts[i]["z"]) for i in set(tris)]
        c, e = bounds(pts)
        subs.append({"firstByte": len(new_idx) * 2, "indexCount": len(tris), "firstVertex": min(used),
                     "vertexCount": max(used) - min(used) + 1 if tris else 0, "c": c, "e": e})
        new_idx += tris
    skinned = bool(d["m_Skin"])
    # streams
    s0 = [("pos", 0, 0, 3, 12, d["m_Vertices"], "3f", "xyz")]
    if d["m_Normals"]: s0.append(("nrm", 1, 0, 3, 12, d["m_Normals"], "3f", "xyz"))
    if d["m_Tangents"]: s0.append(("tan", 2, 0, 4, 16, d["m_Tangents"], "4f", "xyzw"))
    s1 = []
    if d["m_Colors"]: s1.append(("col", 3, 2, 4, 4, d["m_Colors"], "I", None))
    if d["m_UV"]: s1.append(("uv0", 4, 0, 2, 8, d["m_UV"], "2f", "xy"))
    if d["m_UV1"]: s1.append(("uv1", 5, 0, 2, 8, d["m_UV1"], "2f", "xy"))
    streams = [s0, s1] if skinned else [s0 + s1]
    if skinned:
        w = [{"x": s["weight[0]"], "y": s["weight[1]"], "z": s["weight[2]"], "w": s["weight[3]"]} for s in d["m_Skin"]]
        bi = [{"x": s["boneIndex[0]"], "y": s["boneIndex[1]"], "z": s["boneIndex[2]"], "w": s["boneIndex[3]"]} for s in d["m_Skin"]]
        streams.append([("bw", 12, 0, 4, 16, w, "4f", "xyzw"), ("bi", 13, 10, 4, 16, bi, "4I", "xyzw")])
    channels = [(0, 0, 0, 0)] * 14
    data = bytearray()
    for si, st in enumerate(streams):
        if not st:
            continue
        while len(data) % 16:
            data.append(0)
        base = len(data); off = 0
        for _, ch, fmt_code, dim, size, arr, pk, keys in st:
            channels[ch] = (si, off, fmt_code, dim); off += size
        stride = off
        for i in range(n):
            for _, ch, fmt_code, dim, size, arr, pk, keys in st:
                data += struct.pack("<" + pk, arr[i]["rgba"]) if keys is None else struct.pack("<" + pk, *(arr[i][k] for k in keys))
        assert len(data) - base == stride * n
    # bones
    bind = d["m_BindPose"]
    hashes = b"".join(struct.pack("<I", zlib.crc32(nm.encode()) & 0xFFFFFFFF) for nm in bone_names) if bone_names else b""
    bone_aabb = []
    for bidx, m in enumerate(bind):
        pts = []
        for i, s in enumerate(d["m_Skin"]):
            for k in range(4):
                if s[f"boneIndex[{k}]"] == bidx and s[f"weight[{k}]"] > 0:
                    v = verts[i]
                    pts.append(tuple(m[f"e{r}0"] * v["x"] + m[f"e{r}1"] * v["y"] + m[f"e{r}2"] * v["z"] + m[f"e{r}3"] for r in range(3)))
                    break
        if pts:
            bone_aabb.append(([min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]))
        else:
            bone_aabb.append(([0, 0, 0], [0, 0, 0]))
    la = d["m_LocalAABB"]
    y = []
    y.append("%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!43 &4300000\nMesh:\n")
    y.append("  m_ObjectHideFlags: 0\n  m_CorrespondingSourceObject: {fileID: 0}\n  m_PrefabInstance: {fileID: 0}\n  m_PrefabAsset: {fileID: 0}\n")
    y.append(f"  m_Name: {name}\n  serializedVersion: 10\n  m_SubMeshes:\n")
    for s in subs:
        y.append(f"  - serializedVersion: 2\n    firstByte: {s['firstByte']}\n    indexCount: {s['indexCount']}\n    topology: 0\n"
                 f"    baseVertex: 0\n    firstVertex: {s['firstVertex']}\n    vertexCount: {s['vertexCount']}\n    localAABB:\n"
                 + aabb_yaml(s["c"], s["e"], "      "))
    y.append("  m_Shapes:\n    vertices: []\n    shapes: []\n    channels: []\n    fullWeights: []\n")
    if bind:
        y.append("  m_BindPose:\n")
        for m in bind:
            y.append("  - " + "\n    ".join(f"e{r}{c}: {f(m[f'e{r}{c}'])}" for r in range(4) for c in range(4)) + "\n")
    else:
        y.append("  m_BindPose: []\n")
    y.append(f"  m_BoneNameHashes: {hashes.hex()}\n  m_RootBoneNameHash: 0\n")
    if bone_aabb:
        y.append("  m_BonesAABB:\n")
        for mn, mx in bone_aabb:
            y.append(f"  - m_Min: {{x: {f(mn[0])}, y: {f(mn[1])}, z: {f(mn[2])}}}\n    m_Max: {{x: {f(mx[0])}, y: {f(mx[1])}, z: {f(mx[2])}}}\n")
    else:
        y.append("  m_BonesAABB: []\n")
    y.append("  m_VariableBoneCountWeights:\n    m_Data: \n")
    y.append("  m_MeshCompression: 0\n  m_IsReadable: 1\n  m_KeepVertices: 1\n  m_KeepIndices: 1\n  m_IndexFormat: 0\n")
    y.append("  m_IndexBuffer: " + struct.pack(f"<{len(new_idx)}H", *new_idx).hex() + "\n")
    y.append(f"  m_VertexData:\n    serializedVersion: 3\n    m_VertexCount: {n}\n    m_Channels:\n")
    for st, off, fmt_code, dim in channels:
        y.append(f"    - stream: {st}\n      offset: {off}\n      format: {fmt_code}\n      dimension: {dim}\n")
    y.append(f"    m_DataSize: {len(data)}\n    _typelessdata: {bytes(data).hex()}\n")
    pbv_f = "      m_NumItems: 0\n      m_Range: 0\n      m_Start: 0\n      m_Data: \n      m_BitSize: 0\n"
    pbv_i = "      m_NumItems: 0\n      m_Data: \n      m_BitSize: 0\n"
    y.append("  m_CompressedMesh:\n")
    for nm in ["m_Vertices", "m_UV", "m_Normals", "m_Tangents"]:
        y.append(f"    {nm}:\n" + pbv_f)
    for nm in ["m_Weights", "m_NormalSigns", "m_TangentSigns"]:
        y.append(f"    {nm}:\n" + pbv_i)
    y.append("    m_FloatColors:\n" + pbv_f)
    for nm in ["m_BoneIndices", "m_Triangles"]:
        y.append(f"    {nm}:\n" + pbv_i)
    y.append("    m_UVInfo: 0\n")
    y.append("  m_LocalAABB:\n" + aabb_yaml(la["m_Center"], la["m_Extent"], "    "))
    y.append("  m_MeshUsageFlags: 0\n  m_BakedConvexCollisionMesh: \n  m_BakedTriangleCollisionMesh: \n"
             "  m_MeshMetrics[0]: 1\n  m_MeshMetrics[1]: 1\n  m_MeshOptimizationFlags: 1\n"
             "  m_StreamData:\n    offset: 0\n    size: 0\n    path: \n")
    return "".join(y), len(new_idx) // 3


by_bytes = {}
for key, d in raw_meshes:
    by_bytes.setdefault(pack35(d).hex(), []).append((key, d))

done, problems = 0, []
for path in sorted(glob.glob(os.path.join(assets, "Mesh", "*.asset"))):
    text = open(path).read()
    name = re.search(r"m_Name: ?(.*)", text).group(1).strip()
    blob = re.search(r"_typelessdata: ?([0-9a-f]*)", text).group(1)
    cands = [c for c in by_bytes.get(blob, []) if c[1]["m_Name"] == name] or by_bytes.get(blob, [])
    if not cands:
        problems.append(f"no source match for {os.path.basename(path)}")
        continue
    key, d = cands[0]
    yaml, ntri = build_yaml(name, d, smr_bones.get(key, []))
    open(path, "w").write(yaml)
    done += 1
print(f"regenerated {done} meshes; problems: {problems}")
