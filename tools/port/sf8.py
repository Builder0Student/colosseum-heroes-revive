"""Minimal Unity serialized-file (format 8, Unity 3.4) reader/writer: metadata at end of file."""
import struct


class Obj:
    __slots__ = ("path_id", "start", "size", "type_id", "class_id", "destroyed", "data", "entry_off")


class SF8:
    def __init__(self, path):
        self.path = path
        b = open(path, "rb").read()
        self.raw = b
        meta_size, file_size, fmt, data_off = struct.unpack_from(">IIII", b, 0)
        assert fmt == 8 and file_size == len(b), (path, fmt, file_size, len(b))
        self.meta_size, self.data_off = meta_size, data_off
        m = file_size - meta_size
        self.meta_start = m
        p = m
        endian = b[p]; p += 1
        assert endian == 0, "expected little-endian metadata"
        end = b.index(b"\0", p)
        self.version_off = p
        self.version = b[p:end].decode(); p = end + 1
        self.platform, = struct.unpack_from("<i", b, p); p += 4
        type_count, = struct.unpack_from("<i", b, p); p += 4
        assert type_count == 0, f"embedded type trees not supported ({type_count})"
        self.big_id, = struct.unpack_from("<i", b, p); p += 4
        count, = struct.unpack_from("<i", b, p); p += 4
        self.objects = []
        for _ in range(count):
            o = Obj()
            o.entry_off = p
            o.path_id, o.start, o.size, o.type_id, o.class_id, o.destroyed = struct.unpack_from("<iIIiHH", b, p)
            p += 20
            o.data = b[data_off + o.start: data_off + o.start + o.size]
            self.objects.append(o)
        self.meta_tail_off = p  # externals etc. follow, kept verbatim

    def save(self, path, version=None):
        meta = bytearray(self.raw[self.meta_start:])
        if version:
            old = self.version.encode()
            new = version.encode()
            assert len(new) == len(old)
            off = self.version_off - self.meta_start
            meta[off:off + len(old)] = new
        body = bytearray(b"\0" * 16)
        # keep objects in original order of their data offsets
        order = sorted(self.objects, key=lambda o: o.start)
        starts = {}
        for o in order:
            while (len(body) - self.data_off) % 8:
                body.append(0)
            starts[id(o)] = len(body) - self.data_off
            body += o.data
        while len(body) % 8:
            body.append(0)
        for o in self.objects:
            rel = o.entry_off - self.meta_start
            struct.pack_into("<iIIiHH", meta, rel, o.path_id, starts[id(o)], len(o.data), o.type_id, o.class_id, o.destroyed)
        total = len(body) + len(meta)
        struct.pack_into(">IIII", body, 0, len(meta), total, 8, self.data_off)
        open(path, "wb").write(bytes(body) + bytes(meta))


def data_files(data_dir):
    """All Unity serialized files in a 3.4 Data folder: named ones plus 32-hex resource files."""
    import os, re
    named = ["mainData", "level0", "level1", "level2", "sharedassets0.assets", "sharedassets1.assets",
             "sharedassets2.assets", "unity default resources"]
    out = [n for n in named if os.path.isfile(os.path.join(data_dir, n))]
    out += sorted(n for n in os.listdir(data_dir) if re.fullmatch(r"[0-9a-f]{32}", n))
    return out
