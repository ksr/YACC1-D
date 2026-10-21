#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""crtc_regs.py - the video card's 6845 register interface through the Bus Test Card, CPU out (2026-10-10).

  crtc_regs.py [port] [--gap S] [--repeat N]

The tester's strobes last milliseconds, so this checks the decode and the register path statically; the E pulse comes
from the card's RC one-shot (IC27/F, R1, C1 -> IC1/A), which the slow strobes stretch to its RC limit:
  latch    $D801 / $D803 read (the JP1 read-back latch, $FF with nothing jumpered); never written (finding 6.4)
  R14/R15  written through $D800 (address register) / $D802 (data register) and read back: 6 and 8 bits; they read
           back on every 6845 (R12/R13 are write-only on Motorola's MC6845, readable on e.g. an HD6845S)
  repeat   N write/read pairs of R15 with --gap seconds between accesses (default 0): review finding 6.1 - C1 has no
           charging path except IC1's input current, so after the first access E may be missing until C1 recovers;
           failures with --gap 0 that go away with --gap 0.5 are that finding (fix: a pull-up on IC27 pin 12, N$3)
  R12/R13  written 12/34 and read: 00 00 = an MC6845 (or nothing answering), 12 34 = a part that reads them
Reads go through the firmware's RDBLK, which samples the bus well under a millisecond after -MEM-RD: E lasts only until
C1 (1 uF, through R1 10k) discharges, ~12 ms, and the per-command read (-MEM-RD, then RD-DATABUS-L as a second serial
command) samples after E has gone - every register then reads as the undriven bus, FF (found 2026-10-21).
Every 00 or FF read back from a register means the 6845 did not answer: -CS (IC17 pin 25 must go low for $D800/$D802),
RS still on A0 (the bench fix moves IC17 pin 24 to ADDR1), or no E (IC17 pin 23). tests/video/hold_address.py D800
[--rd] parks an address for the meter. docs/procedures/VIDEO-BRINGUP.md has the order of the bring-up.
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT

args = sys.argv[1:]
def opt(name, default):
    if name in args:
        v = args.pop(args.index(name) + 1); args.remove(name); return v
    return default
gap = float(opt("--gap", 0)); repeat = int(opt("--repeat", 32))
port = next((a for a in args if not a.startswith("--")), PORT)
bd = BusDriver(port); bd.wait_prompt(timeout=20)
c = bd.cmd
fails = 0

def report(name, ok, detail):
    global fails; fails += not ok
    print("%-8s %s  %s" % (name, "PASS" if ok else "FAIL", detail), flush=True)

def wr(addr, v):
    c("DATABUS-WR-MODE", 1); bd.writemem(addr, v); c("DATABUS-RD-MODE", 1)
    if gap: time.sleep(gap)

def rd(addr, precharge):
    c("DATABUS-WR-MODE", 1); c("WR-DATABUS", precharge); c("DATABUS-RD-MODE", 1)   # the undriven bus keeps its last value
    v = bd.read_block(addr, 1)[0]   # sampled inside the firmware: E (R1 10k, C1 1 uF) ends ~12 ms after the strobe
    if gap: time.sleep(gap)
    return v

def reg_rw(reg, v):
    wr(0xD800, reg); wr(0xD802, v); wr(0xD800, reg)
    return rd(0xD802, v ^ 0xFF)

c("-BUS-EN", 1); bd.no_registers(); c("-VMA", 1); c("ADDRBUS-WR-MODE", 1); c("DATABUS-RD-MODE", 1)
bd.pulse("-RESET"); bd.readmem(0xF000)                     # the 6845's -RES, FORCE-ROM released

a, b = rd(0xD801, 0x00), rd(0xD803, 0x00)
report("latch", a == b, "$D801 = %02X, $D803 = %02X (FF: nothing jumpered on JP1; must be equal)" % (a, b))

for reg, mask, vals in ((14, 0x3F, (0x00, 0x3F, 0x15, 0x2A, 0x12)), (15, 0xFF, (0x00, 0xFF, 0x55, 0xAA, 0x34))):
    got = [reg_rw(reg, v) & mask for v in vals]
    report("R%d" % reg, got == [v & mask for v in vals], " ".join("%02X>%02X" % (v, g) for v, g in zip(vals, got)))

bad = []
for i in range(repeat):
    v = (i * 37 + 11) & 0xFF
    g = reg_rw(15, v)
    if g != v: bad.append((i, v, g))
report("repeat", not bad, "%d R15 write/read pairs, gap %g s: %d failed%s" % (
    repeat, gap, len(bad), (" - first at #%d (%02X>%02X)" % bad[0]) if bad else ""))
if bad and gap == 0:
    print("         failures with no gap: rerun with --gap 0.5; if they go away, it is finding 6.1 (C1 not recharging)")

wr(0xD800, 12); wr(0xD802, 0x12); wr(0xD800, 13); wr(0xD802, 0x34)
wr(0xD800, 12); r12 = rd(0xD802, 0xED); wr(0xD800, 13); r13 = rd(0xD802, 0xCB)
print("R12/R13  read %02X %02X: %s" % (r12, r13, "an MC6845 (write-only there)" if (r12, r13) == (0, 0) else
      "a part that reads them" if (r12, r13) == (0x12, 0x34) else "neither - check the read path"))
wr(0xD800, 12); wr(0xD802, 0); wr(0xD800, 13); wr(0xD802, 0)

c("-VMA", 0); c("-BUS-EN", 0); bd.ser.close()
print("6845 register interface: %s" % ("ALL PASS" if not fails else "%d FAIL" % fails))
sys.exit(1 if fails else 0)
