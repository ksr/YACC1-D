#!/usr/bin/env python3
"""Full overnight test of the memory card and the video card's display RAM through the Bus Test Card.

Phases (each prints PASS/FAIL and a running line of progress; ~4-5 h at 19200 baud):
  A. ROM: every byte $E000-$FFFF against firmware/rom/eprom-captured-2026-09-18.bin (the burned image)
  B. address lines: a unique byte at $0000 and at every single-bit address 1<<n (n = 0..15, $8000 lands in high RAM),
     read back after all writes - a shorted or open address line shows up here in seconds
  C. RAM fill/verify, pattern 1 (address-derived): write $0000-$7FFF and $8000-$CFFF in one sweep, verify in a second
     sweep (so the read of the first cell comes ~1 h after its write: retention is tested too)
  D. the same with the inverted pattern (every bit exercised both ways)
  E. video RAM $D000-$D3FF: both patterns, neighbour isolation, the block-0/9 write-through checks, read stability
  F. ROM again (the RAM sweeps must not have disturbed it) and the undecoded $D800-$DFFF echo check
usage: memory_full_test.py [port] [--log FILE]
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
rom = open(os.path.join(ROOT, "firmware", "rom", "eprom-captured-2026-09-18.bin"), "rb").read(); assert len(rom) == 8192
args = sys.argv[1:]
logf = open(args.pop(args.index("--log") + 1), "a") if "--log" in args else None
if "--log" in args: args.remove("--log")
port = next((a for a in args if not a.startswith("--")), PORT)
results = []; T0 = time.time()
def out(msg):
    line = "%s  %s" % (time.strftime("%H:%M:%S"), msg); print(line, flush=True)
    if logf: logf.write(line + "\n"); logf.flush()
def report(name, ok, detail=""):
    results.append((name, ok)); out("%-46s %s  %s" % (name, "PASS" if ok else "FAIL", detail))

bd = BusDriver(port); bd.wait_prompt(timeout=8)
MODE = ["DATABUS-RD-MODE"]   # the data-bus direction in force, so a reopened (reset) card can be put back into it
def setup():
    bd.pulse("-RESET"); bd.cmd("-BUS-EN", 1); bd.cmd("-VMA", 1); bd.cmd("ADDRBUS-WR-MODE", 1); bd.cmd("DATABUS-RD-MODE", 1)
    bd.readmem(0xF000)   # release the boot remap (RAM contents survive the reset)
    bd.cmd(MODE[0], 1)
def reopened():
    out("   ! port dropped and came back: card reset, setup redone, continuing"); setup()
bd.on_reopen = reopened
setup()
out("start: port %s" % port)
RAM = [(0x0000, 0x8000), (0x8000, 0x5000)]   # low RAM, high RAM (jumpered $8000-$CFFF)
def rd(a): return bd.readmem(a)
def wr(a, v): bd.writemem(a, v)
def rd_mode(): MODE[0] = "DATABUS-RD-MODE"; bd.cmd("DATABUS-RD-MODE", 1)
def wr_mode(): MODE[0] = "DATABUS-WR-MODE"; bd.cmd("DATABUS-WR-MODE", 1)

def rom_check(name):
    bad = []; t = time.time()
    for a in range(0xE000, 0x10000):
        if rd(a) != rom[a - 0xE000]: bad.append(a)
        if (a & 0x3FF) == 0x3FF: out("   ROM %04X ... %d bad so far" % (a, len(bad)))
    report(name, not bad, "8192 bytes, %d differ%s (%.0f s)" % (len(bad), (": " + ", ".join("%04X" % x for x in bad[:8])) if bad else "", time.time() - t))

# --- A
rd_mode(); rom_check("A. ROM $E000-$FFFF = burned image")

# --- B address lines
wr_mode()
cells = [0x0000] + [1 << n for n in range(16) if (1 << n) < 0xD000]
for i, a in enumerate(cells): wr(a, (0x11 * (i + 1)) & 0xFF)
rd_mode(); bad = [(a, rd(a), (0x11 * (i + 1)) & 0xFF) for i, a in enumerate(cells) if rd(a) != (0x11 * (i + 1)) & 0xFF]
report("B. address lines A0-A15 independent", not bad, "%d cells" % len(cells) if not bad else "bad: %s" % ["%04X got %02X exp %02X" % b for b in bad[:6]])

# --- C / D full RAM
def sweep(pat, name):
    t = time.time(); wr_mode(); n = 0
    for base, size in RAM:
        for a in range(base, base + size):
            wr(a, pat(a)); n += 1
            if (a & 0x7FF) == 0x7FF: out("   write %04X  (%.0f min)" % (a, (time.time() - t) / 60))
    rd_mode(); bad = []
    for base, size in RAM:
        for a in range(base, base + size):
            v = rd(a)
            if v != pat(a): bad.append((a, v, pat(a)))
            if (a & 0x7FF) == 0x7FF: out("   verify %04X  %d bad so far  (%.0f min)" % (a, len(bad), (time.time() - t) / 60))
    report(name, not bad, "%d cells, %d bad%s (%.0f min)" % (n, len(bad), (": " + ", ".join("%04X got %02X exp %02X" % b for b in bad[:6])) if bad else "", (time.time() - t) / 60))
pat1 = lambda a: ((a * 7 + 3) ^ (a >> 5) ^ (a >> 11)) & 0xFF
sweep(pat1, "C. RAM $0000-$7FFF + $8000-$CFFF pattern 1")
sweep(lambda a: ~pat1(a) & 0xFF, "D. RAM inverted pattern")

# --- E video RAM (as tests/video/video_ram_test.py, full 1K)
VB, VS = 0xD000, 0x400
def vfill(fn):
    wr_mode()
    for i in range(VS): wr(VB + i, fn(i) & 0xFF)
def vverify(fn, name):
    rd_mode(); bad = [(VB + i, rd(VB + i)) for i in range(VS) if rd(VB + i) != (fn(i) & 0xFF)]
    report(name, not bad, "%d cells" % VS if not bad else "%d bad: %s" % (len(bad), ["%04X=%02X" % b for b in bad[:6]]))
vp = lambda i: (i * 7 + 3) ^ (i >> 4)
vfill(vp); vverify(vp, "E1. video RAM pattern"); vfill(lambda i: ~vp(i)); vverify(lambda i: ~vp(i), "E2. video RAM inverted")
vfill(lambda i: 0); wr_mode(); wr(VB + 0x155, 0xA5); rd_mode()
nb = ["%04X=%02X" % (VB + (0x155 ^ (1 << b)), rd(VB + (0x155 ^ (1 << b)))) for b in range(10) if rd(VB + (0x155 ^ (1 << b))) != 0]
report("E3. video single cell, neighbours clear", not nb and rd(VB + 0x155) == 0xA5, ", ".join(nb) if nb else "ok")
for src in (0x0010, 0x9010, 0x0011, 0x1010):
    wr_mode(); wr(0xD010, 0x11); wr(src, 0x22); rd_mode(); rd(0xD3FF); v = rd(0xD010)
    report("E4. write to %04X must not reach D010" % src, v == 0x11, "D010 = %02X" % v)
wr_mode(); [wr(VB + i, (0x5A + i) & 0xFF) for i in range(32)]; rd_mode()
first = [rd(VB + i) for i in range(32)]; [rd(a) for a in (0x0000, 0xF000, 0x8000)]; second = [rd(VB + i) for i in range(32)]
exp = [(0x5A + i) & 0xFF for i in range(32)]; report("E5. video read stability", first == exp and second == exp)

# --- F
rd_mode(); rom_check("F. ROM again after the RAM sweeps")
wr_mode(); wr(0x0020, 0x77); rd_mode(); rd(0x0020); e1 = rd(0xD810); wr_mode(); wr(0x0020, 0x88); rd_mode(); rd(0x0020); e2 = rd(0xD810)
report("F2. $D800-$DFFF undecoded (echoes last bus value)", (e1, e2) == (0x77, 0x88), "%02X %02X" % (e1, e2))

n_ok = sum(1 for _, ok in results if ok)
out("DONE: %d/%d passed in %.1f h" % (n_ok, len(results), (time.time() - T0) / 3600))
sys.exit(0 if n_ok == len(results) else 1)
