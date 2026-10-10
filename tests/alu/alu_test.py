#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""ALU card (V3.2) test through the Bus Test Card (bus-driver firmware), CPU out (2026-10-10).

The tester plays the sequencer: it puts the operand on DATA, sets ALU0..3, and strobes -AC-LD / -SR-LD exactly as the
microcode does (aluOp() and shiftOp() in firmware/microcode/ucode-generator2/accumulator.c: function and operand set
first, then the strobe; the accumulator and the carry latch on its leading edge). The accumulator is read with
-ALU-FUNC + -AC-RD; the carry and the branch conditions through BR-COND (the tester reads C24). docs/cards/alu.md.

  accumulator   load and read back (DATA function), walking 1 and 0; DATA8..15 = $FF while the card drives
  invert        DATA with -AC-LD-INV: AC = NOT operand (INVA)
  logic         AND, OR, XOR, ZERO over a set of operand pairs; the carry must not change
  add / sub     results and carry/borrow, the shift-out cleared first (the 2026-09-23 carry fix); ADD with carry in
  shift         SHL, SHR, rotate both ways, sign-propagating right, through-carry both ways; carry = the bit out
  conditions    BR-COND for always, BDATA<AC, ==, >, low byte zero, 16-bit zero, carry; and inverted by -AC-LD-INV
  reset         -RESET clears the carry
The IN condition (BRINH/BRINL) is not tested: the tester reads IN, it cannot drive it. The memory and register cards may
stay in (no -MEM-RD, no register function, no register on the address bus).
usage: alu_test.py [port]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT

DATA, SUB, AND, OR, XOR, SHIFT, ZERO, ADD = range(8)
CARRY = 8                                     # ALU3: add the carry (ADD) / serial-input select (SHIFT)
S_LOAD, S_LEFT, S_RIGHT = 3, 1, 2             # 74*194 modes on ALU0..1
S_ZERO, S_RING, S_PROP, S_CARRY = 0, 4, 8, 12 # serial input on ALU2..3

port = next((a for a in sys.argv[1:] if not a.startswith("--")), PORT)
bd = BusDriver(port); bd.wait_prompt(timeout=20)
c = bd.cmd
fails = 0

def report(name, bad, detail=""):
    global fails; fails += bool(bad)
    print("%-12s %s  %s" % (name, "FAIL" if bad else "PASS", "; ".join(bad[:6]) + (" (+%d)" % (len(bad) - 6) if len(bad) > 6 else "") if bad else detail), flush=True)

def alu(code):
    for i in range(4): c("ALU%d" % i, (code >> i) & 1)

def drive(v):
    c("DATABUS-WR-MODE", 1); c("WR-DATABUS", v & 0xFFFF)

def strobe(name):
    c(name, 1); c(name, 0)

def clear_shiftout():                         # what aluOp() does before every add/subtract
    alu(S_LOAD); strobe("-SR-LD")

def op(code, operand=0, inv=False):
    """one accumulator load: AC <- function(AC, operand)"""
    drive(operand); c("-ALU-FUNC", 1)
    if (code & 7) in (ADD, SUB): clear_shiftout()
    alu(code)
    if inv: c("-AC-LD-INV", 1)
    strobe("-AC-LD")
    c("-AC-LD-INV", 0); c("-ALU-FUNC", 0)

def set_ac(v):
    op(DATA, v)

def read_ac(expect):
    drive(~expect)                            # the undriven bus keeps its last value: leave something else on it
    c("DATABUS-RD-MODE", 1); c("-ALU-FUNC", 1); c("-AC-RD", 1)
    v = int(c("RD-DATABUS")); c("-AC-RD", 0); c("-ALU-FUNC", 0)
    return v

def cond(code, operand=0, inv=False):
    drive(operand); c("-ALU-FUNC", 1); alu(code)
    if inv: c("-AC-LD-INV", 1)
    v = int(c("RBR-COND")); c("-AC-LD-INV", 0); c("-ALU-FUNC", 0)
    return v

def carry():
    return cond(ADD)                          # condition 7 = C/SHIFT

def shift(v, mode):
    set_ac(v); c("-ALU-FUNC", 1)
    alu(S_LOAD); strobe("-SR-LD"); alu(mode); strobe("-SR-LD"); alu(SHIFT); strobe("-AC-LD")
    c("-ALU-FUNC", 0)

def set_carry(b):
    set_ac(0xFF if b else 0x00); op(ADD, 1)   # $FF+1 sets it, $00+1 clears it

for s in ("-ALU-FUNC", "-AC-RD", "-AC-LD", "-AC-LD-INV", "-SR-LD", "-MEM-RD", "-MEM-WR", "-VMA", "-REG-FUNC-RD",
          "-REG-FUNC-LD", "-TMP-REG-RD0", "-TMP-REG-RD1", "-HL-SWAP"):
    c(s, 0)
c("-BUS-EN", 1); bd.no_registers(); c("ADDRBUS-WR-MODE", 1); c("WR-ADDRBUS", 0)
bd.pulse("-RESET")

walk = [0x00, 0xFF, 0x55, 0xAA] + [1 << i for i in range(8)] + [0xFF ^ (1 << i) for i in range(8)]
bad = []
for v in walk:
    set_ac(v); r = read_ac(v | 0xFF00)
    if r != 0xFF00 | v: bad.append("$%02X read $%04X" % (v, r))
report("accumulator", bad, "%d values, DATA8..15 = $FF" % len(walk))

bad = []
for v in walk:
    op(DATA, v, inv=True); r = read_ac(0xFF00 | v ^ 0xFF) & 0xFF
    if r != v ^ 0xFF: bad.append("NOT $%02X = $%02X" % (v, r))
report("invert", bad)

vals = [0x00, 0xFF, 0x0F, 0xF0, 0x55, 0xAA, 0x3C, 0x81]
bad = []
for cin in (0, 1):
    set_carry(cin)
    for name, code, f in (("AND", AND, lambda a, b: a & b), ("OR", OR, lambda a, b: a | b),
                          ("XOR", XOR, lambda a, b: a ^ b), ("ZERO", ZERO, lambda a, b: 0)):
        for a in vals:
            for b in vals:
                set_ac(a); op(code, b); e = f(a, b); r = read_ac(0xFF00 | e) & 0xFF
                if r != e: bad.append("$%02X %s $%02X = $%02X (exp $%02X)" % (a, name, b, r, e))
    if carry() != cin: bad.append("carry %d changed by logic ops" % cin)
report("logic", bad, "AND OR XOR ZERO, %d pairs each, carry kept" % (len(vals) ** 2))

pairs = [(0x00, 0x00), (0x12, 0x34), (0x7F, 0x01), (0xFF, 0x01), (0x80, 0x80), (0xFF, 0xFF), (0x0F, 0x01), (0xA5, 0x5A),
         (0x01, 0xFF), (0x99, 0x66), (0xF0, 0x0F), (0x55, 0xAB)]
bad = []
for a, b in pairs:
    set_carry(1); set_ac(a); op(ADD, b); e = (a + b) & 0xFF; r = read_ac(0xFF00 | e) & 0xFF; k = carry()
    if r != e or k != (a + b > 0xFF): bad.append("$%02X+$%02X = $%02X C%d (exp $%02X C%d)" % (a, b, r, k, e, a + b > 0xFF))
report("add", bad, "%d pairs, carry out" % len(pairs))

bad = []
for cin in (0, 1):
    for a, b in pairs:
        set_carry(cin); set_ac(a); op(ADD | CARRY, b); s = a + b + cin; e = s & 0xFF
        r = read_ac(0xFF00 | e) & 0xFF; k = carry()
        if r != e or k != (s > 0xFF): bad.append("$%02X+$%02X+%d = $%02X C%d (exp $%02X C%d)" % (a, b, cin, r, k, e, s > 0xFF))
report("add carry", bad, "ADDIC/ADDTC with carry 0 and 1")

bad = []
for a, b in pairs + [(0x05, 0x03), (0x03, 0x05), (0x00, 0x01), (0x80, 0x01), (0x42, 0x42)]:
    set_carry(1); set_ac(a); op(SUB, b); e = (a - b) & 0xFF; r = read_ac(0xFF00 | e) & 0xFF; k = carry()
    if r != e or k != (a < b): bad.append("$%02X-$%02X = $%02X C%d (exp $%02X C%d)" % (a, b, r, k, e, a < b))
report("subtract", bad, "carry = borrow")

def rotl(v, cin, mode):
    s = mode & 12; ins = {S_ZERO: 0, S_RING: v >> 7, S_CARRY: cin}[s]
    return ((v << 1) & 0xFF) | ins, v >> 7
def rotr(v, cin, mode):
    s = mode & 12; ins = {S_ZERO: 0, S_RING: v & 1, S_PROP: v >> 7, S_CARRY: cin}[s]
    return (v >> 1) | (ins << 7), v & 1
bad = []
modes = [("SHL", S_LEFT | S_ZERO, rotl), ("SHR", S_RIGHT | S_ZERO, rotr), ("RSHL", S_LEFT | S_RING, rotl),
         ("RSHR", S_RIGHT | S_RING, rotr), ("PSHR", S_RIGHT | S_PROP, rotr), ("CSHL", S_LEFT | S_CARRY, rotl),
         ("CSHR", S_RIGHT | S_CARRY, rotr)]
for name, mode, f in modes:
    for cin in ((0, 1) if mode & 12 == S_CARRY else (0,)):
        for v in walk + [0x96, 0x69]:
            set_carry(cin); shift(v, mode); e, out = f(v, cin, mode)
            r = read_ac(0xFF00 | e) & 0xFF; k = carry()
            if r != e or k != out: bad.append("%s $%02X (C%d) = $%02X C%d (exp $%02X C%d)" % (name, v, cin, r, k, e, out))
report("shift", bad, "SHL SHR RSHL RSHR PSHR CSHL CSHR, carry = bit out")

bad = []
for a, b in [(0x40, 0x20), (0x20, 0x40), (0x33, 0x33), (0x00, 0x00), (0xFF, 0x00), (0x00, 0xFF), (0x80, 0x7F), (0x7F, 0x80)]:
    set_ac(a)
    for code, name, e in ((DATA, "always", 1), (SUB, "B<AC", b < a), (AND, "B=AC", b == a), (OR, "B>AC", b > a),
                          (XOR, "B lo=0", b == 0)):
        for inv in (False, True):
            r = cond(code, b, inv)
            if r != (int(e) ^ inv): bad.append("AC=$%02X B=$%02X %s%s = %d" % (a, b, "NOT " if inv else "", name, r))
for w in (0x0000, 0x0001, 0x0100, 0x8000, 0x00FF, 0xFF00, 0xFFFF):
    for inv in (False, True):
        r = cond(ZERO, w, inv); e = (w == 0) ^ inv
        if r != e: bad.append("16-bit zero $%04X%s = %d" % (w, " inverted" if inv else "", r))
for cin in (0, 1):
    set_carry(cin)
    for inv in (False, True):
        r = cond(ADD, 0, inv)
        if r != cin ^ inv: bad.append("carry %d%s = %d" % (cin, " inverted" if inv else "", r))
report("conditions", bad, "always, <, =, >, zero, 16-bit zero, carry; each inverted too")

set_carry(1); bd.pulse("-RESET"); k = carry()
report("reset", ["carry %d after -RESET" % k] if k else [], "carry cleared")

for s in ("-ALU-FUNC", "-AC-RD", "-AC-LD", "-AC-LD-INV", "-SR-LD"): c(s, 0)
c("DATABUS-RD-MODE", 1); c("-BUS-EN", 0); bd.ser.close()
print("ALU card:", "ALL PASS" if not fails else "%d FAIL" % fails)
sys.exit(1 if fails else 0)
