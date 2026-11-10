"""Print release type trees for given classes in two Unity versions side by side (flattened)."""
import json, sys, difflib

def load(path):
    return {c["Name"]: c for c in json.load(open(path))["Classes"]}

def flat(node, depth=0, out=None):
    if out is None:
        out = []
    if node is None:
        return out
    flags = node.get("MetaFlag", 0)
    align = " (align)" if flags & 0x4000 else ""
    out.append(f"{'  ' * depth}{node['TypeName']} {node['Name']}{align}")
    for ch in node.get("SubNodes", []) or []:
        flat(ch, depth + 1, out)
    return out

a, b = load(sys.argv[1]), load(sys.argv[2])
for name in sys.argv[3:]:
    fa = flat(a.get(name, {}).get("ReleaseRootNode"))
    fb = flat(b.get(name, {}).get("ReleaseRootNode"))
    print(f"===== {name}: {len(fa)} -> {len(fb)} nodes")
    for line in difflib.unified_diff(fa, fb, lineterm="", n=1):
        if line.startswith(("---", "+++")):
            continue
        print(line)
