#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""Register card test through the Bus Test Card (bus-driver firmware), CPU out (2026-10-10).

For each of R0..R7 (two cards, R0-R3 and R4-R7 by their J1-J3 jumpers) it first checks whether the register answers
(a load of a value and its complement both read back), then, for every register that does:
  load/read   16-bit patterns (walking 1 and 0, $0000/$FFFF/$5555/$AAAA/...) through both byte lanes, the other present
              registers loaded with distinct values first and read after (a register that answers for another shows up)
  lanes       -REG-LD-LO alone leaves the high byte, -REG-LD-HI alone the low byte; -REG-RD-LO alone reads the low
              byte with DATA8..15 at the pull-ups' $FF
  count       -REG-UP / -REG-DN across every nibble carry ($000F, $00FF, $0FFF, $FFFF up; $0010, $0100, $1000, $0000
              down): the 74HC193 chain
  swap        -REG-RD-HI with -HL-SWAP puts the high byte on DATA0..7
  address     ADDR-REG-ID = n with -VMA: the register drives ADDR0..15 (the tester's address bus in read mode)
  reset       -RESET clears every register to $0000
The memory card may stay in: -MEM-RD is never asserted, so it never drives the data bus.
usage: register_test.py [port] [--regs 0-7]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT

args = sys.argv[1:]
regs = range(8)
if "--regs" in args:
    lo, _, hi = args.pop(args.index("--regs") + 1).partition("-"); args.remove("--regs")
    regs = range(int(lo), int(hi or lo) + 1)
port = next((a for a in args if not a.startswith("--")), PORT)
bd = BusDriver(port); bd.wait_prompt(timeout=20)
c = bd.cmd
fails = 0

def report(name, bad, detail=""):
    global fails; fails += bool(bad)
    print("  %-10s %s  %s" % (name, "FAIL" if bad else "PASS", "; ".join(bad[:6]) if bad else detail), flush=True)

def field(prefix, n):
    for i in range(4):
        c("%s%d" % (prefix, i), (n >> i) & 1)

def idle():
    for s in ("-REG-FUNC-RD", "-REG-FUNC-LD", "-REG-RD-LO", "-REG-RD-HI", "-REG-LD-LO", "-REG-LD-HI", "-REG-UP",
              "-REG-DN", "-HL-SWAP", "-VMA", "-MEM-RD", "-MEM-WR", "-TMP-REG-RD0", "-TMP-REG-RD1"):
        c(s, 0)
    bd.no_registers(); c("DATABUS-RD-MODE", 1); c("ADDRBUS-RD-MODE", 1)

last = 0
def load(n, v, lo=True, hi=True):
    global last; last = v
    field("REG-LD-ID", n); c("DATABUS-WR-MODE", 1); c("-REG-FUNC-LD", 1); c("WR-DATABUS", v)
    if lo: c("-REG-LD-LO", 1); c("-REG-LD-LO", 0)
    if hi: c("-REG-LD-HI", 1); c("-REG-LD-HI", 0)
    c("-REG-FUNC-LD", 0); c("DATABUS-RD-MODE", 1)

def read(n, lo=True, hi=True, swap=False):
    # the undriven bus keeps its last value: leave the complement of the last load on it, so a register that does
    # not drive cannot read back as the value just loaded
    c("DATABUS-WR-MODE", 1); c("WR-DATABUS", last ^ 0xFFFF)
    field("REG-RD-ID", n); c("DATABUS-RD-MODE", 1); c("-REG-FUNC-RD", 1)
    if swap: c("-HL-SWAP", 1)
    if lo: c("-REG-RD-LO", 1)
    if hi: c("-REG-RD-HI", 1)
    v = int(c("RD-DATABUS"))
    c("-REG-RD-LO", 0); c("-REG-RD-HI", 0); c("-HL-SWAP", 0); c("-REG-FUNC-RD", 0)
    return v

def count(n, strobe, times=1):
    field("REG-RD-ID", n); c("-REG-FUNC-RD", 1)
    for _ in range(times):
        c(strobe, 1); c(strobe, 0)
    c("-REG-FUNC-RD", 0)

def drive_addr(n):
    c("ADDRBUS-WR-MODE", 1); c("WR-ADDRBUS", last ^ 0xFFFF)
    field("ADDR-REG-ID", n); c("ADDRBUS-RD-MODE", 1); c("-VMA", 1)
    v = int(c("RD-ADDRBUS")); c("-VMA", 0); bd.no_registers()
    return v

c("-BUS-EN", 1); idle()
bd.pulse("-RESET")

present = []
for n in regs:
    load(n, 0x1234); a = read(n); load(n, 0xEDCB); b = read(n)
    ok = a == 0x1234 and b == 0xEDCB
    print("R%d %s" % (n, "answers" if ok else "does not answer (read $%04X / $%04X)" % (a, b)), flush=True)
    if ok: present.append(n)

pats = [0x0000, 0xFFFF, 0x5555, 0xAAAA, 0x1234, 0xFEDC] + [1 << i for i in range(16)] + [0xFFFF ^ (1 << i) for i in range(16)]
for n in present:
    print("R%d" % n, flush=True)
    others = [m for m in present if m != n]
    bad = []
    keep = {m: (0x1111 * (m + 1)) ^ (0x0F0F * (n + 1)) & 0xFFFF for m in others}   # distinct values, set once
    for m, e in keep.items(): load(m, e)
    for v in pats:
        load(n, v); r = read(n)
        if r != v: bad.append("wrote $%04X read $%04X" % (v, r))
    for m, e in keep.items():
        r = read(m)
        if r != e: bad.append("R%d changed: $%04X, was $%04X" % (m, r, e))
    report("load/read", bad, "%d patterns" % len(pats))

    bad = []
    load(n, 0xA55A); load(n, 0x3CC3, hi=False)
    r = read(n)
    if r != 0xA5C3: bad.append("LD-LO only: $%04X (exp $A5C3)" % r)
    load(n, 0x0FF0, lo=False)
    r = read(n)
    if r != 0x0FC3: bad.append("LD-HI only: $%04X (exp $0FC3)" % r)
    r = read(n, hi=False)
    if r != 0xFFC3: bad.append("RD-LO only: $%04X (exp $FFC3)" % r)
    report("lanes", bad)

    bad = []
    for start, s, exp in ((0x000F, "-REG-UP", 0x0010), (0x00FF, "-REG-UP", 0x0100), (0x0FFF, "-REG-UP", 0x1000),
                          (0xFFFF, "-REG-UP", 0x0000), (0x1233, "-REG-UP", 0x1234), (0x0010, "-REG-DN", 0x000F),
                          (0x0100, "-REG-DN", 0x00FF), (0x1000, "-REG-DN", 0x0FFF), (0x0000, "-REG-DN", 0xFFFF)):
        load(n, start); count(n, s); r = read(n)
        if r != exp: bad.append("$%04X %s -> $%04X (exp $%04X)" % (start, s[5:], r, exp))
    load(n, 0x7FF0); count(n, "-REG-UP", 20); r = read(n)
    if r != 0x8004: bad.append("$7FF0 +20 -> $%04X (exp $8004)" % r)
    report("count", bad, "carries and borrows across all four 193s")

    bad = []
    load(n, 0x5AC3); r = read(n, lo=False, swap=True) & 0xFF
    if r != 0x5A: bad.append("RD-HI + HL-SWAP: DATA0..7 = $%02X (exp $5A)" % r)
    report("swap", bad)

    bad = []
    for v in (0x0000, 0xFFFF, 0x5555, 0xAAAA, 0x1234, 0x8001):
        load(n, v); r = drive_addr(n)
        if r != v: bad.append("R%d=$%04X, address bus $%04X" % (n, v, r))
    report("address", bad)

if present:
    for n in present: load(n, 0xBEEF)
    bd.pulse("-RESET")
    bad = ["R%d = $%04X" % (n, r) for n in present for r in [read(n)] if r != 0]
    print("all"); report("reset", bad, "every register $0000 after -RESET")

idle(); c("-BUS-EN", 0); bd.ser.close()
print("registers answering: %s; %s" % (" ".join("R%d" % n for n in present) or "none",
                                       "ALL PASS" if not fails and present else "%d FAIL" % fails if fails else "nothing to test"))
sys.exit(1 if fails or not present else 0)
