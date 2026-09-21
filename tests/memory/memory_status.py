#!/usr/bin/env python3
"""Quick status of the memory card (and whatever else answers on the bus) through the Bus Test Card.

What it reports, in order:
  boot remap   after -RESET the ROM must appear at $0000 (FORCE-ROM) until the first access with A15 high
  ROM          $E000-$FFFF sampled (first 32 bytes of each 1K, plus the BIOS vectors at $FFC0) against firmware/rom/eprom-captured-2026-09-18.bin (= shipped/rom)
  low RAM      write/read at 8 spots in $0000-$7FFF
  block map    every 4K block $8000-$FFFF classified as RAM (write/read works), ROM (matches the image, writes ignored),
               VIDEO ($D000-$D7FF if a video card answers) or undecoded (reads echo the last bus value)
  expected     $8000-$CFFF RAM, $D000 video / undecoded, $E000-$FFFF ROM (docs/system/MACHINE.md jumper table)
usage: memory_status.py [port]
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
rom = open(os.path.join(ROOT, "firmware", "rom", "eprom-captured-2026-09-18.bin"), "rb").read()   # binary twin of shipped/rom (Intel hex), byte-identical to the chip
assert len(rom) == 8192
port = next((a for a in sys.argv[1:] if not a.startswith("--")), PORT)
ok_all = True
def line(name, ok, detail):
    global ok_all; ok_all &= ok; print("%-14s %s  %s" % (name, "OK  " if ok else "FAIL", detail), flush=True)

bd = BusDriver(port); bd.wait_prompt(timeout=8)
t0 = time.time()
bd.pulse("-RESET"); bd.cmd("-BUS-EN", 1); bd.cmd("-VMA", 1)
bd.cmd("ADDRBUS-WR-MODE", 1); bd.cmd("DATABUS-RD-MODE", 1)

# --- boot remap: with A15 low the ROM's $F000 page must answer at $0000
got = [bd.readmem(a) for a in range(0x0000, 0x0010)]
exp = list(rom[0x1000:0x1010])
line("boot remap", got == exp, "read $0000-$000F after reset = ROM $F000 page" if got == exp else "got %s exp %s" % (" ".join("%02X" % v for v in got), " ".join("%02X" % v for v in exp)))
bd.readmem(0xF000)   # releases the remap

def rd(a): return bd.readmem(a)
def wr(a, v): bd.writemem(a, v)
def rw_ok(a):
    """write two values, read back each (with another address touched in between so an undecoded echo can't pass)"""
    bd.cmd("DATABUS-WR-MODE", 1); wr(a, 0x5A); wr(a ^ 0x0F, 0x00)
    bd.cmd("DATABUS-RD-MODE", 1); rd(a ^ 0x0F); v1 = rd(a)
    bd.cmd("DATABUS-WR-MODE", 1); wr(a, 0xA5); wr(a ^ 0x0F, 0xFF)
    bd.cmd("DATABUS-RD-MODE", 1); rd(a ^ 0x0F); v2 = rd(a)
    return v1 == 0x5A and v2 == 0xA5, (v1, v2)

# --- ROM
bad = []
for base in list(range(0xE000, 0x10000, 0x400)) + [0xFFC0, 0xFFE0]:
    for a in range(base, min(base + 32, 0x10000)):
        v = rd(a)
        if v != rom[a - 0xE000]: bad.append("%04X=%02X(exp %02X)" % (a, v, rom[a - 0xE000]))
line("ROM", not bad, "%d bytes sampled over $E000-$FFFF = the burned image" % (8 * 32 + 64) if not bad else "%d mismatches: %s" % (len(bad), bad[:5]))

# --- low RAM
res = [(a,) + rw_ok(a) for a in (0x0000, 0x0010, 0x00FF, 0x0F00, 0x1000, 0x3FFF, 0x4000, 0x7FF0)]
line("low RAM", all(r[1] for r in res), "8 spots $0000-$7FF0" if all(r[1] for r in res) else "bad: %s" % ["%04X got %s" % (r[0], r[2]) for r in res if not r[1]])

# --- 4K block map of the upper half
expected = {0x8: "RAM", 0x9: "RAM", 0xA: "RAM", 0xB: "RAM", 0xC: "RAM", 0xD: "VIDEO/undecoded", 0xE: "ROM", 0xF: "ROM"}
summary = []
for blk in range(0x8, 0x10):
    a = (blk << 12) | 0x0123
    if blk >= 0xE:
        kind = "ROM" if rd(a) == rom[a - 0xE000] else "?"
        bd.cmd("DATABUS-WR-MODE", 1); wr(a, rom[a - 0xE000] ^ 0xFF); bd.cmd("DATABUS-RD-MODE", 1)
        if rd(a) != rom[a - 0xE000]: kind = "ROM but WRITABLE!"
    else:
        ok, _ = rw_ok(a)
        if ok:
            kind = "RAM"
            if blk == 0xD:
                lo, _ = rw_ok(0xD010); hi, _ = rw_ok(0xD810)
                kind = "VIDEO (D000-D7FF answers%s)" % ("" if lo and not hi else "; D800 too") if lo else "RAM?"
        else:
            # undecoded: the read echoes whatever was last on the bus
            bd.cmd("DATABUS-WR-MODE", 1); wr(0x0020, 0x77); bd.cmd("DATABUS-RD-MODE", 1); rd(0x0020); e1 = rd(a)
            bd.cmd("DATABUS-WR-MODE", 1); wr(0x0020, 0x88); bd.cmd("DATABUS-RD-MODE", 1); rd(0x0020); e2 = rd(a)
            kind = "undecoded (echoes last bus value)" if (e1, e2) == (0x77, 0x88) else "undecoded/odd (%02X %02X)" % (e1, e2)
    good = kind.startswith(expected[blk].split("/")[0]) or (blk == 0xD and kind.startswith(("VIDEO", "undecoded")))
    summary.append((blk, kind, good))
for blk, kind, good in summary:
    line("$%X000 block" % blk, good, "%s   (expected %s)" % (kind, expected[blk]))
print("\n%s in %.0f s" % ("ALL OK" if ok_all else "PROBLEMS ABOVE", time.time() - t0))
sys.exit(0 if ok_all else 1)
