#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""TMP0/TMP1 (the memory card's IC26-IC29) through the Bus Test Card, CPU out (2026-10-10).

  load/read  38 16-bit patterns into each register (walking 1 and 0, $0000/$FFFF/$5555/$AAAA/...), the other register
             holding the complement; both read back after every load
  edge       each register keeps the value on the bus when -TMP-REG-LDn goes low, not a later one (finding M3)
The undriven data bus keeps its last value, so every read is arranged to follow a different value on the bus.
usage: tmp_test.py [port]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT
port = next((a for a in sys.argv[1:] if not a.startswith("--")), PORT)
bd = BusDriver(port); bd.wait_prompt(timeout=20)
c = bd.cmd
c("-BUS-EN", 1); bd.no_registers(); c("-VMA", 0); c("-MEM-RD", 0); c("-MEM-WR", 0)
for n in "01": c("-TMP-REG-RD" + n, 0); c("-TMP-REG-LD" + n, 0)

def load(n, v):
    c("DATABUS-WR-MODE", 1); c("WR-DATABUS", v); c("-TMP-REG-LD" + n, 1); c("-TMP-REG-LD" + n, 0); c("DATABUS-RD-MODE", 1)

def read(n):
    c("DATABUS-RD-MODE", 1); c("-TMP-REG-RD" + n, 1); v = int(c("RD-DATABUS")); c("-TMP-REG-RD" + n, 0); return v

pats = [0x0000, 0xFFFF, 0x5555, 0xAAAA, 0x1234, 0xFEDC] + [1 << i for i in range(16)] + [0xFFFF ^ (1 << i) for i in range(16)]
bad = []
for n, other in (("0", "1"), ("1", "0")):
    for v in pats:
        load(n, v); load(other, v ^ 0xFFFF)          # the bus now holds ~v: a TMPn that does not drive reads ~v
        a, b = read(n), read(other)
        if a != v or b != v ^ 0xFFFF:
            bad.append("TMP%s wrote $%04X read $%04X, TMP%s wrote $%04X read $%04X" % (n, v, a, other, v ^ 0xFFFF, b))
    print("TMP%s load/read  %s  %d patterns" % (n, "FAIL" if bad else "PASS", len(pats)), flush=True)
for n in "01":
    c("DATABUS-WR-MODE", 1); c("WR-DATABUS", 0x3C3C); c("-TMP-REG-LD" + n, 1); c("WR-DATABUS", 0xC3C3); c("-TMP-REG-LD" + n, 0)
    v = read(n)
    if v != 0x3C3C: bad.append("TMP%s edge: $%04X (exp $3C3C)" % (n, v))
    print("TMP%s edge       %s  $%04X" % (n, "PASS" if v == 0x3C3C else "FAIL", v), flush=True)
for b in bad[:10]: print("  " + b)
c("-BUS-EN", 0); bd.ser.close()
print("TMP registers:", "ALL PASS" if not bad else "%d FAIL" % len(bad))
sys.exit(1 if bad else 0)
