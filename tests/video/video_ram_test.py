#!/usr/bin/env python3
"""Video card RAM read/write test through the Bus Test Card.

Card map (hardware/cards/video/README.md): the card decodes the $D000 2K block; the LOW half ($D000-$D3FF) is the
display RAM (IDT7134, A11R grounded), the HIGH half addresses the 6845 (only its address register is reachable as built).
The memory card leaves $D000 undecoded, so a read from an address nothing drives returns the last value on the bus:
a RAM cell that "reads back what was written" is only proof when the read comes after OTHER traffic, which the
patterns below arrange.

Tests (each prints PASS/FAIL):
  1. walking pattern over the whole display RAM: write addr-derived bytes to every cell, then read all back
  2. inverted pattern (every bit exercised both ways)
  3. row/column independence: write 00 everywhere, set one cell, check its neighbours (address-line shorts)
  4. write-through fault (the 2026-09-18 finding): a write to $0010 / $9010 must NOT land in $D010
  5. read stability: read $D000-$D01F twice with unrelated bus traffic in between
usage: video_ram_test.py [port] [--quick]   (--quick tests the first 64 cells only)
"""
import sys, os, time, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT

RAM_BASE, RAM_SIZE = 0xD000, 0x400
port = next((a for a in sys.argv[1:] if not a.startswith("--")), PORT)
quick = "--quick" in sys.argv
size = 64 if quick else RAM_SIZE
results = []

def report(name, ok, detail=""):
    results.append((name, ok)); print("%-52s %s  %s" % (name, "PASS" if ok else "FAIL", detail), flush=True)

bd = BusDriver(port)
print("waiting for the bus tester prompt ...", flush=True); bd.wait_prompt(timeout=8)
bd.pulse("-RESET"); bd.cmd("-BUS-EN", 1); bd.cmd("-VMA", 1)
bd.cmd("ADDRBUS-WR-MODE", 1); bd.cmd("DATABUS-RD-MODE", 1)
bd.readmem(0xF000)   # release the memory card's boot remap

def fill(fn):
    bd.cmd("DATABUS-WR-MODE", 1)
    for i in range(size): bd.writemem(RAM_BASE + i, fn(i) & 0xFF)
def verify(fn, name):
    bd.cmd("DATABUS-RD-MODE", 1)
    bad = []
    for i in range(size):
        v = bd.readmem(RAM_BASE + i)
        if v != (fn(i) & 0xFF): bad.append((RAM_BASE + i, fn(i) & 0xFF, v))
    report(name, not bad, ("%d bad, first: %s" % (len(bad), ["%04X exp %02X got %02X" % b for b in bad[:4]])) if bad else "%d cells" % size)
    return bad

t0 = time.time()
# 1. address-derived pattern, 2. its inverse
pat = lambda i: (i * 7 + 3) ^ (i >> 4)
fill(pat); verify(pat, "1. address-derived pattern, %d cells" % size)
fill(lambda i: ~pat(i)); verify(lambda i: ~pat(i), "2. inverted pattern")

# 3. one cell set, neighbours (each single address bit flipped) must stay clear
fill(lambda i: 0x00)
probe = 0x155 if not quick else 0x15
bd.cmd("DATABUS-WR-MODE", 1); bd.writemem(RAM_BASE + probe, 0xA5)
bd.cmd("DATABUS-RD-MODE", 1)
bad = []
for bit in range(10 if not quick else 6):
    a = probe ^ (1 << bit)
    v = bd.readmem(RAM_BASE + a)
    if v != 0x00: bad.append("%04X=%02X" % (RAM_BASE + a, v))
v = bd.readmem(RAM_BASE + probe)
report("3. single cell %04X, neighbours clear" % (RAM_BASE + probe), not bad and v == 0xA5, ("probe reads %02X; " % v) + (", ".join(bad) if bad else "all neighbours 00"))

# 4. write-through from block 0 and block 9 (A11=0, A0=0 cases from the 2026-09-18 tests)
for src in (0x0010, 0x9010, 0x0011, 0x1010):
    bd.cmd("DATABUS-WR-MODE", 1); bd.writemem(0xD010, 0x11); bd.writemem(src, 0x22)
    bd.cmd("DATABUS-RD-MODE", 1); bd.readmem(0xD3FF); v = bd.readmem(0xD010)
    report("4. write to %04X must not reach D010" % src, v == 0x11, "D010 = %02X" % v)

# 5. stability: same 32 cells read twice with a memory-card access in between
bd.cmd("DATABUS-WR-MODE", 1)
for i in range(32): bd.writemem(RAM_BASE + i, (0x5A + i) & 0xFF)
bd.cmd("DATABUS-RD-MODE", 1)
first = [bd.readmem(RAM_BASE + i) for i in range(32)]
for a in (0x0000, 0xF000, 0x8000): bd.readmem(a)
second = [bd.readmem(RAM_BASE + i) for i in range(32)]
exp = [(0x5A + i) & 0xFF for i in range(32)]
report("5. read stability across other traffic", first == exp and second == exp, "first %s, second %s" % ("ok" if first == exp else "BAD", "ok" if second == exp else "BAD"))

print("\n%d/%d passed in %.0f s" % (sum(1 for _, ok in results if ok), len(results), time.time() - t0))
sys.exit(0 if all(ok for _, ok in results) else 1)
