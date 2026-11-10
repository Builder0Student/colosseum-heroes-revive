"""Find GameObjects that are inactive but have active children (visible in Unity 3.x, hidden in 4.x+)."""
import os, re, sys

assets = sys.argv[1]
for dp, _, fs in os.walk(assets):
    for fn in fs:
        if not fn.endswith((".unity", ".prefab")):
            continue
        text = open(os.path.join(dp, fn), encoding="utf-8").read()
        docs = {}
        for m in re.finditer(r"^--- !u!(\d+) &(-?\d+)[^\n]*\n(.*?)(?=^--- |\Z)", text, re.S | re.M):
            docs[m.group(2)] = (int(m.group(1)), m.group(3))
        go_active, go_name, tr_go, tr_children = {}, {}, {}, {}
        for fid, (cls, body) in docs.items():
            if cls == 1:
                go_active[fid] = re.search(r"m_IsActive: (\d)", body).group(1) == "1"
                go_name[fid] = re.search(r"m_Name: ?(.*)", body).group(1).strip()
            elif cls == 4:
                tr_go[fid] = re.search(r"m_GameObject: \{fileID: (-?\d+)\}", body).group(1)
                tr_children[fid] = re.findall(r"^  - \{fileID: (-?\d+)\}", body.split("m_Children:")[1].split("m_Father:")[0], re.M) if "m_Children:" in body else []
        for tr, kids in tr_children.items():
            g = tr_go[tr]
            if not go_active.get(g, True):
                active_kids = [go_name[tr_go[k]] for k in kids if k in tr_go and go_active.get(tr_go[k], False)]
                if active_kids:
                    print(f"{os.path.relpath(os.path.join(dp, fn), assets)}: inactive '{go_name[g]}' has active children {active_kids[:6]}{'...' if len(active_kids) > 6 else ''}")
