"""Rewrite removed component shortcut properties (x.renderer etc.) to GetComponent<T>() at the exact
positions reported by the compiler (CS0117/CS1061/CS0103). Usage: fix_by_errors.py <Assets dir> <log>..."""
import re, sys, os, collections

SHORTCUTS = {"animation": "Animation", "collider": "Collider", "renderer": "Renderer", "rigidbody": "Rigidbody",
             "camera": "Camera", "audio": "AudioSource", "light": "Light", "constantForce": "ConstantForce",
             "hingeJoint": "HingeJoint"}
assets = sys.argv[1]
err = re.compile(r"^(.*?)\((\d+),(\d+)\): error (CS0117|CS1061|CS0103): .*?'(\w+)'(?: does not exist| could not be found| and no accessible|$)")
edits = collections.defaultdict(set)
for log in sys.argv[2:]:
    for line in open(log, errors="ignore"):
        m = re.match(r"^(.*?)\((\d+),(\d+)\): error (CS0117|CS1061|CS0103): (.*)$", line.strip())
        if not m:
            continue
        path, ln, col, code, msg = m.groups()
        names = re.findall(r"'(\w+)'", msg)
        member = names[1] if code in ("CS0117", "CS1061") and len(names) > 1 else (names[0] if names else None)
        if member in SHORTCUTS:
            edits[path].add((int(ln), int(col), member))

total = 0
for path, items in edits.items():
    lines = open(path, encoding="utf-8").read().split("\n")
    for ln, col, member in sorted(items, key=lambda x: (x[0], -x[1])):
        s = lines[ln - 1]
        i = col - 1
        if s[i:i + len(member)] != member:
            print(f"!! {path}:{ln}:{col} expected {member!r}, found {s[i:i+len(member)]!r}")
            continue
        lines[ln - 1] = s[:i] + f"GetComponent<{SHORTCUTS[member]}>()" + s[i + len(member):]
        total += 1
    open(path, "w", encoding="utf-8").write("\n".join(lines))
print(f"rewrote {total} shortcut uses in {len(edits)} files")
