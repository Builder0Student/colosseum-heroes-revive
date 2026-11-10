"""Check script references in an exported Unity project: every m_Script guid resolves to a .cs with .meta,
and list MonoBehaviours without serialized fields together with the public fields their class declares."""
import os, re, sys, collections

root = sys.argv[1]
guid2path = {}
for dp, _, fs in os.walk(root):
    for f in fs:
        if f.endswith(".meta"):
            m = re.search(r"^guid: ([0-9a-f]{32})", open(os.path.join(dp, f), errors="ignore").read(), re.M)
            if m:
                guid2path[m.group(1)] = os.path.join(dp, f[:-5])

missing = collections.Counter()
empty = collections.Counter()
used = collections.Counter()
for dp, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith((".unity", ".prefab", ".asset")):
            continue
        text = open(os.path.join(dp, f), errors="ignore").read()
        for doc in text.split("\n--- ")[1:]:
            if not doc.startswith("!u!114 "):
                continue
            m = re.search(r"m_Script: \{fileID: (-?\d+), guid: ([0-9a-f]+), type: (\d)\}", doc)
            if not m:
                continue
            g = m.group(2)
            p = guid2path.get(g)
            if not p:
                missing[g] += 1
                continue
            used[os.path.relpath(p, root)] += 1
            body = doc.split("m_EditorClassIdentifier:", 1)[1].strip().splitlines()[1:]
            if not body:
                empty[os.path.relpath(p, root)] += 1

print("distinct scripts used:", len(used), "MonoBehaviours:", sum(used.values()))
print("missing script guids:", dict(missing))
print("MonoBehaviours with no serialized fields, by script:")
for p, n in empty.most_common():
    src = open(os.path.join(root, p), errors="ignore").read() if p.endswith(".cs") else ""
    pub = re.findall(r"^\s*public\s+(?!static|const|override|virtual|abstract|void|class|enum|struct|delegate|event)([\w<>\[\],\. ]+?)\s+(\w+)\s*(=|;)", src, re.M)
    print(f"  {n:4} {p}  public fields: {[x[1] for x in pub][:8]}")
