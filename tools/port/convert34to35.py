"""Convert Unity 3.4.2 player data files to Unity 3.5.0 binary layout so AssetRipper (>=3.5) can read them.

Usage: convert34to35.py <src Data dir> <dst Data dir> <InfoJson dir>
Every object whose class layout differs structurally between 3.4.2 and 3.5.0 is parsed with the 3.4.2
release type tree (and must round-trip byte-exact), converted, and re-serialized with the 3.5.0 tree.
"""
import sys, os, shutil, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
import tt, sf8

src, dst, info = sys.argv[1:4]
T34 = tt.load_trees(os.path.join(info, "3.4.2.json"))
T35 = tt.load_trees(os.path.join(info, "3.5.0.json"))
DIFF = {cid for cid in T34 if cid in T35 and tt.shape(T34[cid]) != tt.shape(T35[cid])}
FILES = sf8.data_files(src)
stats = collections.Counter()


def convert_mesh(m):
    use16 = m.pop("m_Use16BitIndices", 1)
    ib = m["m_IndexBuffer"]
    if not use16:
        idx = struct.unpack(f"<{len(ib)//4}I", ib)
        assert max(idx, default=0) < 65536, "32-bit indices exceed 16-bit range"
        m["m_IndexBuffer"] = struct.pack(f"<{len(idx)}H", *idx)
        for sm in m["m_SubMeshes"]:
            sm["firstByte"] //= 2
        stats["mesh_32to16"] += 1
    verts, norms, cols = m.pop("m_Vertices"), m.pop("m_Normals"), m.pop("m_Colors")
    uv0, uv1, tans = m.pop("m_UV"), m.pop("m_UV1"), m.pop("m_Tangents")
    m.pop("m_CollisionTriangles", None)
    m.pop("m_CollisionVertexCount", None)
    n = len(verts)
    chans = [(0, verts, "3f", ("x", "y", "z")), (1, norms, "3f", ("x", "y", "z")), (2, cols, "I", ("rgba",)),
             (3, uv0, "2f", ("x", "y")), (4, uv1, "2f", ("x", "y")), (5, tans, "4f", ("x", "y", "z", "w"))]
    present = [(c, arr, fmt, keys) for c, arr, fmt, keys in chans if arr]
    for c, arr, fmt, keys in present:
        assert len(arr) == n, f"channel {c} has {len(arr)} items, expected {n}"
    mask = sum(1 << c for c, *_ in present)
    stride = sum(struct.calcsize("<" + fmt) for _, _, fmt, _ in present)
    data = bytearray()
    for i in range(n):
        for c, arr, fmt, keys in present:
            data += struct.pack("<" + fmt, *(arr[i][k] for k in keys))
    streams = [{"channelMask": mask, "offset": 0, "stride": stride if n else 0, "align": 0}] + \
              [{"channelMask": 0, "offset": 0, "stride": 0, "align": 0} for _ in range(3)]
    m["m_VertexData"] = {"m_CurrentChannels": mask if n else 0, "m_VertexCount": n,
                         **{f"m_Streams[{i}]": s for i, s in enumerate(streams)}, "m_DataSize": bytes(data)}
    cm = m["m_CompressedMesh"]
    cm["m_Colors"] = {"m_NumItems": 0, "m_Data": b"", "m_BitSize": 0}
    if cols and not n:
        raise ValueError("compressed mesh with colors not handled")
    stats["mesh"] += 1
    return m


def convert_quality(q):
    names = ["Fastest", "Fast", "Simple", "Good", "Beautiful", "Fantastic"]
    levels = []
    for nm in names:
        if nm in q:
            lv = dict(q[nm]); lv["name"] = nm; lv["lodBias"] = 1.0; lv["maximumLODLevel"] = 0
            levels.append(lv)
    return {"m_CurrentQuality": q.get("m_DefaultMobileQuality", 2), "m_QualitySettings": levels,
            "m_StrippedMaximumLODLevel": 0}


def convert(cid, d):
    if cid == 43:
        return convert_mesh(d)
    if cid == 47:
        return convert_quality(d)
    if cid == 28:
        d["m_ColorSpace"] = 1  # sRGB colour textures (game renders in gamma space)
    return d


os.makedirs(dst, exist_ok=True)
for entry in os.listdir(src):
    sp, dp = os.path.join(src, entry), os.path.join(dst, entry)
    if entry in FILES:
        continue
    if os.path.isdir(sp):
        shutil.copytree(sp, dp, dirs_exist_ok=True)
    else:
        shutil.copy2(sp, dp)

for f in FILES:
    s = sf8.SF8(os.path.join(src, f))
    for o in s.objects:
        if o.class_id not in DIFF:
            continue
        d, used = tt.read(T34[o.class_id], o.data)
        assert used == len(o.data), f"{f} pathID {o.path_id} class {o.class_id}: read {used} of {len(o.data)}"
        assert tt.write(T34[o.class_id], d) == bytes(o.data), f"{f} pathID {o.path_id}: 3.4 round-trip mismatch"
        new = tt.write(T35[o.class_id], convert(o.class_id, d))
        d2, used2 = tt.read(T35[o.class_id], new)
        assert used2 == len(new)
        o.data = new
        stats[f"class_{o.class_id}"] += 1
    s.save(os.path.join(dst, f), version="3.5.0f5")
    print(f"{f}: {len(s.objects)} objects written")
print(dict(stats))
