#!/usr/bin/env python3
"""Run the compiler test programs (and tests/assembler/brur) on the MICROCODE-level emulator (software/ucemu) and
compare with the expectations the instruction-level emulator established (tests/compiler/NAME.out).

  run.py [name ...] [--keep] [--ucode PATH] [--fight and|src]
    --ucode  control store to run (default: the tree's test.hex); --fight: the emulator's -F policy

Each program is compiled with --boot and run with the monitor ROM loaded (-m): under the microcode BRDEV always
branches, so the runtime's console goes through the monitor's charout/uartin and the I/O card's UART model, the
path the real machine takes. Differences that are expected on the hardware (the monitor's uartin ECHOES every
character it reads) are covered by NAME.ucout when present. Prints PASS/FAIL, steps, clocks and the bus-fight count.
"""
import os, sys, glob, subprocess, shutil, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CC = os.path.join(ROOT, "software/compiler/y1cc.py")
ASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMU = os.path.join(ROOT, "software/ucemu/y1ucemu")
CTESTS = os.path.join(ROOT, "tests/compiler")
BUILD = os.path.join(HERE, "build")


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)            # bytes: a program may emit any byte value
    r.stdout = r.stdout.decode("latin1"); r.stderr = r.stderr.decode("latin1"); return r


EXTRA = []

def run_image(img, inp, rom=True):
    with open(inp) if inp and os.path.exists(inp) else open(os.devnull) as f:
        try:
            e = sh([EMU, "-x"] + EXTRA + (["-m"] if rom else []) + ["-f", img], stdin=f, timeout=120)
        except subprocess.TimeoutExpired:
            return None, "timeout"
    return e, e.stderr.strip().splitlines()[-1] if e.stderr.strip() else ""


def run_one(src):
    name = os.path.basename(src)[:-2]
    d = os.path.join(BUILD, name); os.makedirs(d, exist_ok=True)
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    if os.path.exists(src[:-2] + ".err"): return None, "compile-error test, skipped"
    flags = re.search(r"//\s*y1cc:\s*(.*)", open(src).read())
    r = sh([sys.executable, CC, src, "-o", os.path.join(d, name + ".asm"), "--boot"] + (flags.group(1).split() if flags else []))
    if r.returncode: return False, "compile failed: " + r.stderr.strip()[-200:]
    a = sh([ASM, name, "-d=yacc1"], cwd=d)
    if not re.search(r"^0 Errors", a.stdout, re.M): return False, "assembler errors"
    exp_file = src[:-2] + ".ucout" if os.path.exists(src[:-2] + ".ucout") else src[:-2] + ".out"
    e, status = run_image(os.path.join(d, name + ".img"), src[:-2] + ".in")
    if e is None: return False, status
    expected = open(exp_file).read()
    if e.stdout != expected:
        open(os.path.join(d, name + ".got"), "w").write(e.stdout)
        return False, "output differs (see build/%s/%s.got)\n--- got ---\n%s\n--- expected ---\n%s" % (name, name, e.stdout[:300], expected[:300])
    m = re.search(r"after (\d+) instructions, (\d+) steps, (\d+) clocks.*bus fights: (\d+) in (\d+)", status)
    if not m: return False, "no HALT status: " + status
    return True, "%8s instr %9s steps %9s clocks  fights %s (%s pairs)" % m.groups()


def main():
    av = sys.argv[1:]
    if "--ucode" in av: i = av.index("--ucode"); EXTRA.extend(["-u", av[i + 1]]); del av[i:i + 2]
    if "--fight" in av: i = av.index("--fight"); EXTRA.extend(["-F", av[i + 1]]); del av[i:i + 2]
    args = [a for a in av if not a.startswith("--")]; keep = "--keep" in av
    if not os.path.exists(EMU): sys.exit("missing %s (make -C software/ucemu)" % EMU)
    os.makedirs(BUILD, exist_ok=True)
    tests = sorted(glob.glob(os.path.join(CTESTS, "*.c")))
    if args: tests = [t for t in tests if os.path.basename(t)[:-2] in args]
    passed = failed = 0
    for src in tests:
        ok, msg = run_one(src)
        if ok is None: continue
        passed += ok; failed += not ok
        print("%-14s %s  %s" % (os.path.basename(src)[:-2], "PASS" if ok else "FAIL", msg), flush=True)
    # the BRUR assembly test (port 2 console, no ROM)
    if not args or "brur" in args:
        d = os.path.join(BUILD, "brur"); os.makedirs(d, exist_ok=True)
        shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
        shutil.copy(os.path.join(ROOT, "tests/assembler/brur/brur.asm"), d)
        sh([ASM, "brur", "-d=yacc1"], cwd=d)
        e, status = run_image(os.path.join(d, "brur.img"), None, rom=False)
        ok = e is not None and e.stdout == "ABC0123"
        passed += ok; failed += not ok
        print("%-14s %s  %s" % ("brur", "PASS" if ok else "FAIL", status if e else "timeout"), flush=True)
    print("%d passed, %d failed" % (passed, failed))
    if not keep and not failed: shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
