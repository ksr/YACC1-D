#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""The generator's hold-step pass (2026-11-06) removed only what the hardware does not need.

  hold.py [test.hex]

Builds firmware/microcode/ucode-generator2 with -DKEEPHOLD (the records as removeIdleSteps() left them, the image of
e48d869) in a temporary folder and compares every record of the tree's test.hex with it, applying its own copy of the
rules in main.c's removeHoldSteps() comment. It does not run the pass: it finds, for each record, how the shorter one
came from the longer one, and judges each step that went.
  1. each record is the reference record with some steps deleted; steps 0-2 (the prologue) are never deleted; a kept
     step is unchanged, except REG-RD-ID in the step before a deleted selection step (rule B);
  2. no deleted step held a strobe, a count or BR-TEST; records with I/O, interrupt, OUT or halt actions are unchanged;
  3. no trailing-edge strobe lost its hold: after REG-LD-LO/HI or -MEM-WR, the next step keeps the source, or is the
     reset step, which holds it for its clock;
  4. no strobe lost its set-up: the step before a strobe is still a step with the strobe's selection and data, and a
     leading-edge latch of memory data has the read on in the step before it;
  5. the count rule: around every count the register selection is the same in the step before, and in the step after;
  6. the reset step is the only step with the reset bit, and is the last.
Rules 3-5 judge the pairs of steps the pass made adjacent or changed; a pair already in the reference is the image the
machine runs (LDR's first load has its selection in the strobe step, RET counts on a selection set in that step).
Prints the steps removed.
"""
import os, sys, glob, shutil, subprocess, tempfile, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GEN = os.path.join(ROOT, "firmware/microcode/ucode-generator2")
sys.path.insert(0, HERE)
ARGV = sys.argv[:]; sys.argv = [sys.argv[0]]
import prologue as P                                    # load(), on(), field(), length(), asserted()

LEADING = ["LD-INS-REG", "OPERAND-CLK", "BRANCH-LD-LO", "BRANCH-LD-HI", "INT-LD-LO", "INT-LD-HI",
           "-TMP-REG-LD0", "-TMP-REG-LD1", "-AC-LD", "-SR-LD"]
TRAILING = ["REG-LD-LO", "REG-LD-HI", "-MEM-WR", "-IO-WR"]
COUNTS = ["-REG-UP", "-REG-DN"]
STAYS = ["-IO-RD", "-IO-WR", "-IO-ADDR-LD", "INT-EN", "INT-START", "-INTA", "INT-LD-LO", "INT-LD-HI", "-INT-JMP",
         "SOFT-HALT", "OUT-ON", "OUT-OFF"]
RESET = "UCODE-COUNT-RESET"


def on(w, n): return n in P.S and P.on(w, n)
def anyof(w, L): return any(on(w, x) for x in L)
def rd(w): return P.field(w, "REG-RD-ID")
def two(w): return on(w, "-2-BYTE-OPERAND-SEL")


def same_but_rd(a, b):
    """equal except the REG-RD-ID field"""
    return P.asserted(a) == P.asserted(b) and all(P.field(a, f) == P.field(b, f) for f in ("ADDR-REG-ID", "REG-LD-ID", "ALU"))


def reference():
    d = tempfile.mkdtemp()
    exe = os.path.join(d, "ucodegen")
    r = subprocess.run(["cc", "-O2", "-w", "-DKEEPHOLD", "-I" + GEN, "-o", exe] + sorted(glob.glob(GEN + "/*.c")),
                       capture_output=True, text=True)
    if r.returncode: sys.exit("hold.py: building the -DKEEPHOLD generator failed:\n" + r.stderr)
    subprocess.run([exe], cwd=d, capture_output=True)
    return d


def align(old, new):
    """the indices of old that new keeps (in order), or None. new[i] == old[k[i]], but for REG-RD-ID (rule B)"""
    k = []; j = 0
    for i, w in enumerate(new):
        while j < len(old) and old[j] != w and not (same_but_rd(old[j], w) and not on(w, "-REG-FUNC-RD") and j >= 3):
            j += 1
        if j == len(old): return None
        k.append(j); j += 1
    return k


def check(op, old, new, why):
    if old == new: return 0
    if any(anyof(w, STAYS) for w in old): why("has I/O, interrupt, OUT or halt actions, and changed"); return 0
    if not on(new[-1], RESET) or any(on(w, RESET) for w in new[:-1]): why("the reset step is not last, alone"); return 0
    # the reset step of old maps to the reset step of new
    k = align(old[:-1], new[:-1])
    if k is None: why("not the reference record with steps deleted"); return 0
    k.append(len(old) - 1)
    if k[:3] != [0, 1, 2]: why("the prologue changed"); return 0
    gone = [i for i in range(len(old)) if i not in k]
    for i in gone:
        if anyof(old[i], LEADING + TRAILING + COUNTS + ["BR-TEST"]): why("step %d held a strobe, a count or BR-TEST" % i)
    for i in range(len(new) - 1):
        a, b = new[i], new[i + 1]
        if k[i + 1] == k[i] + 1 and a == old[k[i]] and b == old[k[i + 1]]:
            continue                                    # the pass did not make this pair (the image on the machine has it)
        if anyof(a, TRAILING) and not on(b, RESET):     # 3: the hold
            for s in ("-MEM-RD", "-REG-FUNC-LD", "-REG-FUNC-RD", "-REG-RD-LO", "-REG-RD-HI", "-AC-RD", "-BRANCH-RD"):
                if on(a, s) and not on(b, s) and s != "-MEM-WR": why("step %d: the hold lost %s" % (i + 1, s))
            if P.field(a, "ADDR-REG-ID") != P.field(b, "ADDR-REG-ID"): why("step %d: the hold moved the address" % (i + 1))
        if anyof(b, TRAILING) and i >= 3:               # 4: the set-up
            if P.field(a, "ADDR-REG-ID") != P.field(b, "ADDR-REG-ID") and not on(b, "-MEM-RD") and on(b, "-MEM-WR"):
                why("step %d: a write with no address set-up" % (i + 1))
            if on(b, "REG-LD-LO") or on(b, "REG-LD-HI"):
                if not on(a, "-REG-FUNC-LD") or P.field(a, "REG-LD-ID") != P.field(b, "REG-LD-ID"):
                    why("step %d: a load with no selection set-up" % (i + 1))
        if anyof(b, LEADING) and i >= 3 and on(b, "-MEM-RD") and not on(a, "-MEM-RD"):
            why("step %d: a latch of memory data with no read before it" % (i + 1))
        if anyof(b, COUNTS):                            # 5: the count, from the step before
            if rd(a) != rd(b) or two(a) != two(b) or anyof(a, COUNTS): why("step %d: a count on a changing selection" % (i + 1))
        if anyof(a, COUNTS):                            # and after
            if rd(a) != rd(b) or two(b): why("step %d: the selection changes on the count edge" % (i + 1))
    return len(gone)


def main():
    tree = ARGV[1] if len(ARGV) > 1 else os.path.join(GEN, "test.hex")
    new = P.load(tree)
    d = reference()
    ref = P.load(os.path.join(d, "test.hex"))
    shutil.rmtree(d)
    bad = 0; total = 0; saved = collections.Counter()
    for op in range(256):
        a = ref[op][:P.length(ref[op])]; b = new[op][:P.length(new[op])]
        def why(msg, op=op):
            nonlocal bad
            bad += 1
            print("  $%02X %s" % (op, msg))
        n = check(op, a, b, why)
        total += n
        if n: saved[n] += 1
    print("hold: %d steps removed; records by steps saved: %s" % (total, " ".join("%d:%d" % kv for kv in sorted(saved.items()))))
    print("hold: %d problems" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
