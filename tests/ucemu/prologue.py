#!/usr/bin/env python3
"""The three-step fetch prologue (2026-09-29, design review L-1) holds the rules the hardware needs.

  prologue.py [test.hex] [--compare OLD.hex]

Checks every one of the 256 records of the control store (default: the tree's test.hex):
  1. steps 0, 1 and 2 are identical in every record: the IR latches at the leading edge of step 1, so steps 0 and 1
     are executed from the PREVIOUS opcode's record and the new record's words appear from step 2 (START, $00, the
     reset record, also asserts OUT-OFF in every step, as it always has: a flip-flop set, harmless one step late);
  2. they are the prologue: 0 = -MEM-RD at PC; 1 = the same + LD-INS-REG; 2 = -REG-FUNC-RD, -REG-UP on PC without
     -MEM-RD (review M-1: no memory drive against the register card's $FFFF in the fetch);
  3. step 3 is either the release step (step 2 without -REG-UP/-REG-FUNC-RD) or a body line that keeps REG-RD-ID = PC
     and asserts no -REG-UP, -REG-DN or -2-BYTE-OPERAND-SEL: the PC counts when -REG-UP rises, and that edge must not
     meet a change of register selection (a decoder glitch would count another register);
  4. the first body line (step 3, or 4 after a release) has no leading-edge latch: such a latch takes the bus the
     previous step left, which is now the prologue's, not memory at the new PC as in the six-step prologue.
With --compare, prints the steps saved per record against an older image.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ucode_wavedrom import signal_table, active, opcode_names

LEADING_EDGE = ["LD-INS-REG", "OPERAND-CLK", "BRANCH-LD-LO", "BRANCH-LD-HI", "INT-LD-LO", "INT-LD-HI",
                "-TMP-REG-LD0", "-TMP-REG-LD1", "-AC-LD", "-SR-LD"]
S = {n: (b, bt) for n, b, bt in signal_table()}


def load(path):
    recs = {}
    for l in open(path):
        if l.startswith("%"):
            d = bytes.fromhex(l[5:5 + 1024]); recs[int(l[3:5], 16)] = [d[i * 8:i * 8 + 8] for i in range(64)]
    return recs


def on(line, n): return active(line, S[n][0], S[n][1], n)
def field(line, prefix): return sum(on(line, "%s%d" % (prefix, i)) << i for i in range(4))
def asserted(line): return sorted(n for n in S if on(line, n) and not n.startswith(("REG-RD-ID", "REG-LD-ID", "ADDR-REG-ID", "ALU", "IOADDR")))
def length(steps): return next(i for i in range(64) if on(steps[i], "UCODE-COUNT-RESET")) + 1


def main():
    av = sys.argv[1:]
    old = load(av[av.index("--compare") + 1]) if "--compare" in av else None
    if "--compare" in av: del av[av.index("--compare"):av.index("--compare") + 2]
    recs = load(av[0] if av else os.path.join(ROOT, "firmware/microcode/ucode-generator2/test.hex"))
    names = opcode_names(); fails = []
    p = recs[0x03][:3]                                              # HALT's prologue as the reference
    def without_out_off(steps):                                     # START ($00, the reset record) asserts OUT-OFF in
        b, bt = S["OUT-OFF"]                                        # every step: harmless in steps 0-1 (a flip-flop
        return [bytes(x ^ (1 << bt) if i == b and x >> bt & 1 else x for i, x in enumerate(w)) for w in steps]   # set)
    for op in range(256):
        if recs[op][:3] != p and not (op == 0x00 and without_out_off(recs[op][:3]) == p):
            fails.append("$%02X: steps 0-2 differ from the other records" % op)
    s0, s1, s2 = p
    ok2 = (on(s0, "-MEM-RD") and field(s0, "ADDR-REG-ID") == 0 and not on(s0, "LD-INS-REG") and not on(s0, "-REG-UP")
           and on(s1, "-MEM-RD") and on(s1, "LD-INS-REG") and field(s1, "ADDR-REG-ID") == 0
           and not on(s2, "-MEM-RD") and on(s2, "-REG-FUNC-RD") and on(s2, "-REG-UP") and field(s2, "REG-RD-ID") == 0
           and not on(s2, "LD-INS-REG"))
    if not ok2: fails.append("the prologue is not -MEM-RD / + LD-INS-REG / PC++ without -MEM-RD: %s | %s | %s"
                             % (asserted(s0), asserted(s1), asserted(s2)))
    release = bytearray(s2)
    for n in ("-REG-UP", "-REG-FUNC-RD"):
        release[S[n][0]] |= 1 << S[n][1]                            # active-low: 1 = inactive
    release = bytes(release); nrel = 0
    for op in range(256):
        st = recs[op]; b = st[3]
        if b == release:
            nrel += 1; first = 4
        else:
            first = 3
            if field(b, "REG-RD-ID") != 0 or on(b, "-REG-UP") or on(b, "-REG-DN") or on(b, "-2-BYTE-OPERAND-SEL"):
                fails.append("$%02X step 3 changes the register selection or counts right after PC++: %s" % (op, asserted(b)))
        latches = [n for n in LEADING_EDGE if on(st[first], n)]
        if latches: fails.append("$%02X step %d (first body line) latches %s from the prologue's bus" % (op, first, latches))
    print("records: 256, prologue identical in all: %s, release step in %d, first-body-line rules: %s"
          % ("yes" if not any("differ" in f for f in fails) else "NO", nrel, "ok" if not fails else "see below"))
    if old:
        saved = {op: length(old[op]) - length(recs[op]) for op in range(256)}
        hist = {}
        for op, d in saved.items(): hist[d] = hist.get(d, 0) + 1
        print("steps saved per record (old - new): " + ", ".join("%d: %d records" % (d, hist[d]) for d in sorted(hist)))
    for f in fails: print("FAIL", f)
    print("prologue:", "PASS" if not fails else "FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
