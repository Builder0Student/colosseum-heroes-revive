"""Generic Unity type-tree reader/writer (little-endian object data) driven by TypeTreeDumps InfoJson."""
import json, struct

ALIGN = 0x4000
PRIM = {
    "bool": "?", "char": "c", "SInt8": "b", "UInt8": "B", "SInt16": "h", "UInt16": "H", "short": "h",
    "unsigned short": "H", "SInt32": "i", "UInt32": "I", "int": "i", "unsigned int": "I", "float": "f",
    "SInt64": "q", "UInt64": "Q", "double": "d", "long long": "q", "unsigned long long": "Q", "FileSize": "I",
}


def load_trees(path):
    out = {}
    for c in json.load(open(path))["Classes"]:
        if c.get("ReleaseRootNode"):
            out[c["TypeID"]] = c["ReleaseRootNode"]
    return out


def shape(n):
    """Structural signature (ignores indices/versions/other flags)."""
    return (n["TypeName"], n["Name"], bool(n.get("MetaFlag", 0) & ALIGN), tuple(shape(c) for c in n.get("SubNodes") or []))


def _is_array_node(n):
    return n["TypeName"] == "Array" or (n["TypeName"] == "TypelessData")


class Reader:
    def __init__(self, buf):
        self.b, self.p = buf, 0

    def align(self):
        self.p = (self.p + 3) & ~3

    def prim(self, t):
        f = PRIM[t]
        v = struct.unpack_from("<" + f, self.b, self.p)[0]
        self.p += struct.calcsize(f)
        return v

    def read(self, n):
        t, subs = n["TypeName"], n.get("SubNodes") or []
        if t in PRIM and not subs:
            v = self.prim(t)
        elif t == "string":
            arr = subs[0]
            size = self.prim("SInt32")
            v = bytes(self.b[self.p:self.p + size]).decode("utf-8", "replace")
            self.p += size
            if arr.get("MetaFlag", 0) & ALIGN:
                self.align()
        elif _is_array_node(n):
            size = self.prim("SInt32")
            elem = subs[1]
            if elem["TypeName"] in ("UInt8", "SInt8", "char") and not elem.get("SubNodes"):
                v = bytes(self.b[self.p:self.p + size])
                self.p += size
            else:
                v = [self.read(elem) for _ in range(size)]
        elif t in ("vector", "map", "set", "staticvector") or (len(subs) == 1 and _is_array_node(subs[0])):
            v = self.read(subs[0])
        else:
            v = {}
            for c in subs:
                v[c["Name"]] = self.read(c)
        if n.get("MetaFlag", 0) & ALIGN:
            self.align()
        return v


class Writer:
    def __init__(self):
        self.out = bytearray()

    def align(self):
        while len(self.out) % 4:
            self.out.append(0)

    def prim(self, t, v):
        self.out += struct.pack("<" + PRIM[t], v)

    def write(self, n, v, path=""):
        t, subs = n["TypeName"], n.get("SubNodes") or []
        if t in PRIM and not subs:
            if v is None:
                v = b"\0" if t == "char" else (False if t == "bool" else 0)
            self.prim(t, v)
        elif t == "string":
            data = (v or "").encode("utf-8")
            self.prim("SInt32", len(data))
            self.out += data
            if subs[0].get("MetaFlag", 0) & ALIGN:
                self.align()
        elif _is_array_node(n):
            elem = subs[1]
            if v is None:
                v = b"" if elem["TypeName"] in ("UInt8", "SInt8", "char") else []
            self.prim("SInt32", len(v))
            if isinstance(v, (bytes, bytearray)):
                self.out += v
            else:
                for i, e in enumerate(v):
                    self.write(elem, e, f"{path}[{i}]")
        elif t in ("vector", "map", "set", "staticvector") or (len(subs) == 1 and _is_array_node(subs[0])):
            self.write(subs[0], v, path)
        else:
            v = v or {}
            for c in subs:
                self.write(c, v.get(c["Name"]), f"{path}.{c['Name']}")
        if n.get("MetaFlag", 0) & ALIGN:
            self.align()


def read(node, buf):
    r = Reader(buf)
    v = r.read(node)
    return v, r.p


def write(node, value):
    w = Writer()
    w.write(node, value)
    return bytes(w.out)
