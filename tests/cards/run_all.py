#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""Every bus-tester card test in one run, CPU out (2026-10-10): after each card goes back on the backplane, this
checks that the cards already in still work and tests the new one.

  memory   tests/memory/memory_status.py (--rom FILE: the image burned on the chip)   ~1 min
  tmp      tests/memory/tmp_test.py                                                    ~1 min
  regs     tests/registers/register_test.py (R0-R7; a missing card's registers just do not answer)  ~12 min
  alu      tests/alu/alu_test.py                                                       ~15 min
  io       tests/io/io_test.py (needs the console cable on the Mac)                    ~3 min
usage: run_all.py [--rom FILE] [--only memory,tmp,...] [--skip alu,...] [--log FILE]
Prints each test's summary line; the full output goes to --log (default tests/cards/run-<date>-<time>.log).
"""
import sys, os, subprocess, time
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
args = sys.argv[1:]
def opt(name, default=None):
    if name in args:
        v = args.pop(args.index(name) + 1); args.remove(name); return v
    return default
rom = opt("--rom"); only = opt("--only"); skip = opt("--skip", "")
log = opt("--log", os.path.join(ROOT, "tests", "cards", time.strftime("run-%Y-%m-%d-%H%M.log")))
TESTS = [("memory", ["tests/memory/memory_status.py"] + (["--rom", rom] if rom else [])),
         ("tmp", ["tests/memory/tmp_test.py"]), ("regs", ["tests/registers/register_test.py"]),
         ("alu", ["tests/alu/alu_test.py"]), ("io", ["tests/io/io_test.py"])]
sel = [t for t in TESTS if (not only or t[0] in only.split(",")) and t[0] not in skip.split(",")]
results = []
with open(log, "w") as f:
    for name, cmd in sel:
        t0 = time.time(); print("%-7s running ..." % name, end="", flush=True)
        p = subprocess.run([sys.executable] + cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        f.write("== %s (exit %d, %.0f s)\n%s\n" % (name, p.returncode, time.time() - t0, p.stdout)); f.flush()
        last = [l for l in p.stdout.splitlines() if l.strip()][-1:] or ["(no output)"]
        print("\r%-7s %s  %s  (%.0f s)" % (name, "PASS" if p.returncode == 0 else "FAIL", last[0], time.time() - t0), flush=True)
        results.append(p.returncode == 0)
print("%s; log %s" % ("ALL PASS" if all(results) else "%d of %d FAILED" % (results.count(False), len(results)), os.path.relpath(log, ROOT)))
sys.exit(0 if all(results) else 1)
