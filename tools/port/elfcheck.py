"""Analyze ARM32 shared libs: count relocations that land in the executable (text) segment,
list relocation types there, and print .so names referenced in strings (possible dlopen targets)."""
import sys, re, collections
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

for path in sys.argv[1:]:
    with open(path, 'rb') as fh:
        elf = ELFFile(fh)
        loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        text = [s for s in loads if s['p_flags'] & 1][0]
        lo, hi = text['p_vaddr'], text['p_vaddr'] + text['p_memsz']
        types = collections.Counter()
        total = 0
        for sec in elf.iter_sections():
            if isinstance(sec, RelocationSection):
                for r in sec.iter_relocations():
                    total += 1
                    if lo <= r['r_offset'] < hi:
                        types[(sec.name, r['r_info_type'])] += 1
        print(f"== {path}")
        print(f"   text segment {lo:#x}-{hi:#x}, total relocs {total}, relocs in text: {sum(types.values())}")
        for k, v in types.most_common():
            print(f"   {k}: {v}")
        data = open(path, 'rb').read()
        libs = sorted(set(m.decode() for m in re.findall(rb'[A-Za-z0-9_\-./]{2,60}\.so(?![A-Za-z0-9])', data)))
        print("   .so strings:", libs)
