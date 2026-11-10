"""Decode generated Mesh YAML via its m_Channels layout and compare against the original Unity 3.4 mesh data."""
import sys, os, re, struct, glob
sys.path.insert(0, os.path.dirname(__file__))
import sf8, tt

src, info, assets = sys.argv[1:4]
T34 = tt.load_trees(os.path.join(info, "3.4.2.json"))
orig = {}
for f in [x for x in sf8.data_files(src) if x != "unity default resources"]:
    for o in sf8.SF8(os.path.join(src, f)).objects:
        if o.class_id == 43:
            d, _ = tt.read(T34[43], o.data)
            orig.setdefault(d["m_Name"], []).append(d)

FMT = {0: ("f", 4), 2: ("B", 1), 10: ("I", 4)}
checked = bad = 0
for path in sorted(glob.glob(os.path.join(assets, "Mesh", "*.asset"))):
    y = open(path).read()
    name = re.search(r"m_Name: ?(.*)", y).group(1).strip()
    n = int(re.search(r"m_VertexCount: (\d+)", y).group(1))
    chans = [tuple(int(v) for v in m) for m in re.findall(r"- stream: (\d+)\n      offset: (\d+)\n      format: (\d+)\n      dimension: (\d+)", y)]
    data = bytes.fromhex(re.search(r"_typelessdata: ?([0-9a-f]*)", y).group(1))
    idx = struct.unpack(f"<{len(re.search(r'm_IndexBuffer: ?([0-9a-f]*)', y).group(1)) // 4}H", bytes.fromhex(re.search(r"m_IndexBuffer: ?([0-9a-f]*)", y).group(1)))
    # stream strides/offsets as Unity computes them: streams laid out in order, each 16-byte aligned
    strides = {}
    for s, off, fmt, dim in chans:
        if dim:
            strides[s] = max(strides.get(s, 0), off + FMT[fmt][1] * dim)
    starts, pos = {}, 0
    for s in sorted(strides):
        pos = (pos + 15) & ~15
        starts[s] = pos
        pos += strides[s] * n
    assert pos == len(data), (name, pos, len(data))

    def read(ch, i):
        s, off, fmt, dim = chans[ch]
        c, sz = FMT[fmt]
        return struct.unpack_from(f"<{dim}{c}", data, starts[s] + strides[s] * i + off)

    cands = orig[name]
    ok = False
    for d in cands:
        if len(d["m_Vertices"]) != n:
            continue
        good = all(abs(read(0, i)[k] - d["m_Vertices"][i]["xyz"[k]]) < 1e-6 for i in range(n) for k in range(3))
        if d["m_UV"]:
            good &= all(abs(read(4, i)[k] - d["m_UV"][i]["xy"[k]]) < 1e-6 for i in range(n) for k in range(2))
        if d["m_Normals"]:
            good &= all(abs(read(1, i)[k] - d["m_Normals"][i]["xyz"[k]]) < 1e-6 for i in range(n) for k in range(3))
        if bool(d["m_Skin"]) != (chans[13][3] == 4):
            continue
        if d["m_Skin"]:
            good &= all(read(13, i)[k] == d["m_Skin"][i][f"boneIndex[{k}]"] and abs(read(12, i)[k] - d["m_Skin"][i][f"weight[{k}]"]) < 1e-6
                        for i in range(n) for k in range(4))
        good &= len(idx) % 3 == 0 and all(i < n for i in idx)
        if good:
            ok = True
            break
    checked += 1
    if not ok:
        bad += 1
        print("MISMATCH", os.path.basename(path))
print(f"verified {checked} meshes, {bad} mismatches")
