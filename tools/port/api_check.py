"""Check which UnityEngine members referenced by the game are missing (or obsolete-as-error) in Unity 2019.4.

Usage: api_check.py <api_refs.tsv> <UnityCsReference checkout>
Heuristic source scan: collects, per type name, all .cs files declaring it, then looks for a member declaration.
"""
import os, re, sys, collections

refs_path, ucs = sys.argv[1:3]
decl_files = collections.defaultdict(list)
type_decl = re.compile(r"\b(?:class|struct|enum|interface)\s+(\w+)")
for dp, _, fs in os.walk(ucs):
    for fn in fs:
        if fn.endswith(".cs"):
            p = os.path.join(dp, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for m in type_decl.finditer(t):
                decl_files[m.group(1)].append(p)
src_cache = {}


def src(p):
    if p not in src_cache:
        src_cache[p] = open(p, encoding="utf-8", errors="ignore").read()
    return src_cache[p]


def find_member(type_name, member, kind):
    files = decl_files.get(type_name.split(".")[-1].split("/")[-1], [])
    if not files:
        return "no-type"
    name = member
    if kind == "method":
        if member == ".ctor":
            name = type_name.split(".")[-1].split("/")[-1]
        elif member.startswith(("get_", "set_", "add_", "remove_")) and member not in ("get_Item", "set_Item"):
            name = member.split("_", 1)[1]
        elif member in ("get_Item", "set_Item"):
            name = "this"
    if name.startswith("op_"):
        return "ok"
    pat = re.compile(r"(\[[^\]]*\]\s*)*[^\n;{}]*\b" + re.escape(name) + r"\b\s*(\(|\{|=>|;|=|<|\[)")
    best = None
    for p in files:
        for m in pat.finditer(src(p)):
            s = src(p)
            line_start = s.rfind("\n", 0, m.start() + len(m.group(0)) - len(name) - 2) + 1
            # attribute lines directly above the declaration line
            prev = s[:line_start].rstrip("\n").split("\n")[-6:]
            attrs = []
            for ln in reversed(prev):
                if ln.strip().startswith("["):
                    attrs.append(ln)
                else:
                    break
            same_line = s[line_start:m.end()]
            obsolete_err = any(re.search(r"Obsolete\(.*\btrue\s*\)", a) for a in attrs) or \
                re.search(r"Obsolete\(.*\btrue\s*\)", same_line)
            text = m.group(0)
            if re.search(r"\b(public|protected|internal|extern|static|override|virtual|abstract|=>)\b", text) or kind == "field" or name == "this":
                if obsolete_err:
                    best = best or "obsolete-error"
                else:
                    return "ok"
    return best or "missing"


results = collections.defaultdict(list)
for line in open(refs_path):
    scope, typ, kind, member, sig, count = line.rstrip("\n").split("\t")
    if scope != "UnityEngine" or kind not in ("method", "field"):
        continue
    st = find_member(typ, member, kind)
    if st != "ok":
        results[st].append((typ, member, sig, int(count)))

for st, items in results.items():
    print(f"== {st}: {len(items)}")
    for typ, member, sig, count in sorted(items):
        print(f"   {count:4}  {typ}.{member}{sig}")
