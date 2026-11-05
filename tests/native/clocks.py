#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/native/clocks.py - the fast emulator's clocks are the machine's (2026-11-05).

software/opclocks.h gives every opcode's length in clocks, and `emulator -P` adds them up (tools/speed.py). Three checks:

  1. the table is what `y1ucemu -Y` makes of the microcode in the tree (regenerate with: y1ucemu -x -Y > software/opclocks.h);
  2. `y1ucemu -Q` on a real session: every opcode has ONE length, and it is the table's;
  3. the same session's total on both emulators agrees within 0.1% (the small difference is the polling of the console
     and the idle loops, which depend on the emulator).
"""
import os, re, sys, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OS = os.path.join(ROOT, "os")
B = os.path.join(HERE, "build", "clocks")
UC = os.path.join(ROOT, "software/ucemu/y1ucemu")
EMU = os.path.join(ROOT, "software/emulator/emulator")
SESSION = b"O\ncd /src/os/commands\nmake touch\nexit\n0\n"


def main():
    subprocess.run(["make", "-s", "-C", OS], check=True)
    shutil.rmtree(B, ignore_errors=True); os.makedirs(B)
    fails = []
    header = open(os.path.join(ROOT, "software/opclocks.h")).read()
    if subprocess.run([UC, "-x", "-Y"], capture_output=True, text=True).stdout != header:
        fails.append("software/opclocks.h is not what y1ucemu -Y makes of the microcode")
    table = [int(x) for x in re.findall(r"(\d+),", header.split("{", 1)[1])]

    mon = open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read()
    stop = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", mon, re.M).group(1).upper()
    a, b, q, p = [os.path.join(B, f) for f in ("uc.img", "int.img", "q.txt", "p.txt")]
    shutil.copy(os.path.join(OS, "disk.img"), a); shutil.copy(os.path.join(OS, "disk.img"), b)
    r = subprocess.run([UC, "-x", "-m", "-c", a, "-l", "30000000000", "-E", stop, "-Q", q], input=SESSION, capture_output=True)
    m = re.search(r"after (\d+) instructions, \d+ steps, (\d+) clocks", r.stderr.decode("latin1"))
    if not m: sys.exit("clocks: no summary from y1ucemu: " + r.stderr.decode("latin1")[-200:])
    uclk = int(m.group(2))
    seen = 0
    for line in open(q):
        w = line.split(); o = int(w[0], 16); seen += 1
        lens = [int(x.split(":")[0]) for x in w[4:]]
        if len(lens) != 1: fails.append("%s %s has %d lengths: %s" % (w[0], w[1], len(lens), " ".join(w[4:])))
        elif lens[0] != table[o]: fails.append("%s %s: %d clocks, the table says %d" % (w[0], w[1], lens[0], table[o]))
    subprocess.run([EMU, "-x", "-m", "-c", b, "-l", "30000000000", "-P", p], input=SESSION, capture_output=True)
    iclk = 0
    for line in open(p):
        w = line.split()
        if len(w) == 3 and w[0] not in ("op", "cf"): iclk += int(w[2])
    diff = 100.0 * abs(iclk - uclk) / uclk
    if diff > 0.1: fails.append("totals differ by %.3f%%: emulator %d, y1ucemu %d" % (diff, iclk, uclk))
    print("clocks: %d opcodes seen, each with one length; %d clocks on the microcode emulator, %d on the fast one (%.3f%%)"
          % (seen, uclk, iclk, diff))
    for f in fails[:20]: print("  FAIL " + f)
    print("clocks: %d problems" % len(fails))
    if not fails: shutil.rmtree(B)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
