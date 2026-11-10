"""Make an ARM32 .so with text relocations loadable by apps targeting API 23-25.

Bionic refuses DT_TEXTREL for targetSdk >= 23, but still allows writable+executable PT_LOAD
segments for targetSdk < 26. So: drop DT_TEXTREL (and DF_TEXTREL) and mark the text segment RWX,
letting the linker apply the few text relocations directly. Usage: patch_textrel.py in.so out.so
"""
import struct, sys

PT_LOAD, PT_DYNAMIC = 1, 2
PF_X, PF_W = 1, 2
DT_NULL, DT_TEXTREL, DT_FLAGS = 0, 22, 30
DF_TEXTREL = 0x4

src, dst = sys.argv[1], sys.argv[2]
b = bytearray(open(src, "rb").read())
assert b[:4] == b"\x7fELF" and b[4] == 1 and b[5] == 1, "expected ELF32 little-endian"
e_phoff, = struct.unpack_from("<I", b, 0x1C)
e_phentsize, e_phnum = struct.unpack_from("<HH", b, 0x2A)

dyn_off = dyn_size = None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack_from("<8I", b, off)
    if p_type == PT_LOAD and p_flags & PF_X and not p_flags & PF_W:
        struct.pack_into("<I", b, off + 24, p_flags | PF_W)
        print(f"  PT_LOAD @{p_vaddr:#x}: flags {p_flags:#x} -> {p_flags | PF_W:#x}")
    if p_type == PT_DYNAMIC:
        dyn_off, dyn_size = p_offset, p_filesz

entries = [struct.unpack_from("<iI", b, dyn_off + j * 8) for j in range(dyn_size // 8)]
end = next(j for j, (t, _) in enumerate(entries) if t == DT_NULL)
live = entries[:end]
kept = [(t, v & ~DF_TEXTREL if t == DT_FLAGS else v) for t, v in live if t != DT_TEXTREL]
removed = len(live) - len(kept)
kept += [(DT_NULL, 0)] * (len(entries) - len(kept))
for j, (t, v) in enumerate(kept):
    struct.pack_into("<iI", b, dyn_off + j * 8, t, v)
print(f"  removed {removed} DT_TEXTREL entr{'y' if removed == 1 else 'ies'}")
open(dst, "wb").write(b)
