#!/usr/bin/env python3
"""img2bin.py - Intel-hex (.img from the assembler) -> flat binary, for p8xfs.py (boot / put need raw bytes).

  img2bin.py in.img out.bin [--base 0x1000] [--end 0xF000] [--fill 0xFF] [--size 8192]
    --base  the address the binary starts at (default: the lowest address in the file)
    --end   stop before this address (default: 0xF000, so a compiler --boot stub is left out)
    --fill  the byte for addresses never written (default 0; 0xFF for an EEPROM/EPROM image)
    --size  pad (with the fill byte) or truncate the output to exactly this many bytes (a whole chip)
Bytes never written inside [base, last) come out as the fill byte (zero unless --fill).
"""
import sys

def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    base = int(a[a.index("--base") + 1], 0) if "--base" in a else None
    end = int(a[a.index("--end") + 1], 0) if "--end" in a else 0xF000
    fill = int(a[a.index("--fill") + 1], 0) if "--fill" in a else 0
    size = int(a[a.index("--size") + 1], 0) if "--size" in a else None
    mem = {}
    for line in open(a[0]):
        if not line.startswith(":"): continue
        n, addr, typ = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
        if typ != 0: continue
        for i in range(n):
            if addr + i < end: mem[addr + i] = int(line[9 + 2 * i:11 + 2 * i], 16)
    if not mem: sys.exit("img2bin: no data below 0x%04X" % end)
    lo = min(mem) if base is None else base; hi = max(mem)
    if size is not None: hi = lo + size - 1
    out = bytes(mem.get(x, fill) for x in range(lo, hi + 1))
    open(a[1], "wb").write(out)
    print("img2bin: %s -> %s: %d bytes from $%04X" % (a[0], a[1], len(out), lo))

if __name__ == "__main__": main()
