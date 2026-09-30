#!/usr/bin/env python3
"""The generator's idle-step pass (2026-09-29, review S1) removed only what the hardware does not need.

  idle.py [test.hex]

Builds firmware/microcode/ucode-generator2 with -DKEEPIDLE (the records as the generator writes them, before the pass)
in a temporary folder and compares every record of the tree's test.hex with it, applying its own copy of the rules
in main.c's removeIdleSteps() comment:
  1. each record is the reference record with some steps deleted, and every deleted step is idle (nothing asserted
     but -VMA, OUT-ON/OUT-OFF, SPARE3); steps 0-2 (the common prologue) are never deleted;
  2. where steps were deleted, the two steps now adjacent (P, N) and each deleted step satisfy the rules;
  3. no idle step left in the tree's image would pass the rules (the pass and this copy agree).
Prints the steps removed and the per-record saving.
"""
import os, sys, glob, shutil, subprocess, tempfile, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GEN = os.path.join(ROOT, "firmware/microcode/ucode-generator2")
sys.path.insert(0, HERE)
ARGV = sys.argv[:]; sys.argv = [sys.argv[0]]
import prologue as P                                    # load(), on(), field(), length(), asserted()

QUIET = {"-VMA", "OUT-OFF", "OUT-ON", "SPARE3"}
LEADING = ["LD-INS-REG", "OPERAND-CLK", "BRANCH-LD-LO", "BRANCH-LD-HI", "INT-LD-LO", "INT-LD-HI",
           "-TMP-REG-LD0", "-TMP-REG-LD1", "-AC-LD", "-SR-LD"]
TRAILING = ["REG-LD-LO", "REG-LD-HI", "-MEM-WR", "-IO-WR"]
COUNTS = ["-REG-UP", "-REG-DN"]
ACTIONS = ["BR-TEST", "INT-EN", "INT-START", "SOFT-HALT", "-INTA", "-IO-ADDR-LD", "-IO-RD", "-IO-WR"]


def on(w, n): return n in P.S and P.on(w, n)
def act(w): return set(P.asserted(w)) - QUIET
def idle(w): return not act(w)
def sel(w): return tuple(P.field(w, f) for f in ("ADDR-REG-ID", "REG-RD-ID", "REG-LD-ID", "ALU")) + (P.field(w, "IOADDR") if "IOADDR0" in P.S else 0,)
def anyof(w, L): return any(on(w, x) for x in L)


def why_not(p, i, n):
    """the first rule that keeps the idle step i between p and n, or None"""
    if not idle(i): return "not idle"
    if anyof(p, TRAILING): return "P ends a load or write: the idle step is its hold"
    if anyof(n, LEADING): return "N latches at its leading edge: it takes the idle step's bus"
    if anyof(n, TRAILING): return "N loads or writes: it needs a set-up step"
    if anyof(p, ACTIONS) or anyof(n, ACTIONS): return "I/O, BR-TEST, INT or halt next to it"
    for o in ("OUT-ON", "OUT-OFF"):
        if on(i, o) != on(p, o) or on(i, o) != on(n, o): return "the idle step holds %s that P or N does not" % o
    if on(n, "UCODE-COUNT-RESET") and act(n) - {"UCODE-COUNT-RESET"}: return "the reset step is not a pure hold"
    rdP, rdN = P.field(p, "REG-RD-ID"), P.field(n, "REG-RD-ID")
    twoP, twoN = on(p, "-2-BYTE-OPERAND-SEL"), on(n, "-2-BYTE-OPERAND-SEL")
    if anyof(p, COUNTS) and (rdN != rdP or twoN): return "P's count edge would meet a register-selection change"
    if anyof(n, COUNTS) and (rdN != rdP or twoN != twoP or anyof(p, COUNTS)): return "N counts with a selection not already stable"
    if twoN and not twoP: return "-2-BYTE-OPERAND-SEL starts in N"
    if sel(i) != sel(p) and sel(i) != sel(n): return "the idle step is a set-up step of its own"
    return None


def reference():
    tmp = tempfile.mkdtemp()
    for f in glob.glob(os.path.join(GEN, "*.c")) + glob.glob(os.path.join(GEN, "*.h")): shutil.copy(f, tmp)
    exe = os.path.join(tmp, "ucodegen")
    # the sources include ../yaccsignal*.h and ../../opcodes.h: build in place from GEN's own paths
    r = subprocess.run(["cc", "-O2", "-w", "-DKEEPIDLE", "-I" + GEN, "-o", exe] + sorted(glob.glob(os.path.join(GEN, "*.c"))),
                       capture_output=True, text=True, cwd=GEN)
    if r.returncode: sys.exit("idle.py: building the -DKEEPIDLE generator failed:\n" + r.stderr)
    subprocess.run([exe], cwd=tmp, capture_output=True, check=True)
    ref = P.load(os.path.join(tmp, "test.hex")); shutil.rmtree(tmp); return ref


def main():
    new = P.load(ARGV[1] if len(ARGV) > 1 else os.path.join(GEN, "test.hex"))
    ref = reference(); fails = []; removed = 0; saved = collections.Counter()
    for op in range(256):
        a, b = ref[op][:P.length(ref[op])], new[op][:P.length(new[op])]
        j = 0; kept = []                                    # kept[k] = index in a of b[k]
        for i, w in enumerate(a):
            if j < len(b) and w == b[j]: kept.append(i); j += 1
            elif not idle(w): fails.append("$%02X: step %d of the reference (not idle) is missing" % (op, i)); break
            elif i < 3: fails.append("$%02X: prologue step %d deleted" % (op, i)); break
        if j != len(b): fails.append("$%02X: the record is not the reference minus idle steps" % op); continue
        for k in range(len(kept) - 1):
            gap = range(kept[k] + 1, kept[k + 1])
            for i in gap:
                why = why_not(a[kept[k]], a[i], a[kept[k + 1]])
                if why and len(gap) == 1: fails.append("$%02X: reference step %d deleted although %s" % (op, i, why))
                elif why: fails.append("$%02X: reference steps %d-%d deleted together (check by hand): %s" % (op, gap[0], gap[-1], why))
            removed += len(gap)
        saved[len(a) - len(b)] += 1
        for i in range(3, len(b) - 1):                      # exhaustive: nothing left that the rules would remove
            if idle(b[i]) and why_not(b[i - 1], b[i], b[i + 1]) is None:
                fails.append("$%02X: idle step %d could still go" % (op, i))
    left = sum(1 for op in range(256) for i in range(P.length(new[op])) if idle(new[op][i]))
    print("idle steps removed: %d; idle steps kept: %d; records by steps saved: %s"
          % (removed, left, ", ".join("%d: %d" % (d, saved[d]) for d in sorted(saved))))
    for f in fails[:20]: print("FAIL", f)
    print("idle:", "PASS" if not fails else "FAIL (%d)" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
