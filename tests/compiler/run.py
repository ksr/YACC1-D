#!/usr/bin/env python3
"""y1cc test runner: compile every tests/compiler/*.c, assemble it, run it on the emulator, compare the output.

  run.py [name ...] [--oracle] [--keep]
    name      run only these tests (basenames without .c)
    --oracle  (re)generate NAME.out with the HOST C compiler through host_shim.h (int = unsigned short,
              char unsigned) for every test that is not marked `// no-oracle`; then run as usual
    --keep    leave the build directory (asm, img, listing) in tests/compiler/build/

Per test: NAME.c, NAME.out (expected stdout), optional NAME.in (stdin), or NAME.err (expected substring of a
compile ERROR instead of an output). The emulator runs `-x -f NAME.img` with the --boot stub (stack, JSR main,
HALT). Prints PASS/FAIL, code+data bytes and the instruction count.
"""
import os, sys, glob, subprocess, shutil, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CC = os.path.join(ROOT, "software/compiler/y1cc.py")
ASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMU = os.path.join(ROOT, "software/emulator/emulator")
BUILD = os.path.join(HERE, "build")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def oracle(src, out):
    exe = os.path.join(BUILD, "host_" + os.path.basename(src)[:-2])
    r = sh(["cc", "-w", "-funsigned-char", "-include", os.path.join(HERE, "host_shim.h"),
            "-I", os.path.join(ROOT, "software/compiler/lib"), "-o", exe, src])
    if r.returncode: sys.exit("oracle: host cc failed for %s:\n%s" % (src, r.stderr))
    inp = src[:-2] + ".in"
    with open(inp) if os.path.exists(inp) else open(os.devnull) as f:
        r = sh([exe], stdin=f)
    open(out, "w").write(r.stdout)


def run_one(src, want_oracle):
    name = os.path.basename(src)[:-2]
    d = os.path.join(BUILD, name); os.makedirs(d, exist_ok=True)
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    err_file, out_file, in_file = src[:-2] + ".err", src[:-2] + ".out", src[:-2] + ".in"
    flags = re.search(r"//\s*y1cc:\s*(.*)", open(src).read())         # per-test compiler flags, e.g. // y1cc: --no-brur
    r = sh([sys.executable, CC, src, "-o", os.path.join(d, name + ".asm"), "--boot"] + (flags.group(1).split() if flags else []))
    if os.path.exists(err_file):
        want = open(err_file).read().strip()
        ok = r.returncode != 0 and want in (r.stderr + r.stdout)
        return ok, "expected compile error %r: %s" % (want, "seen" if ok else "NOT seen: " + (r.stderr + r.stdout).strip()[-200:])
    if r.returncode: return False, "compile failed: " + (r.stderr + r.stdout).strip()[-400:]
    a = sh([ASM, name, "-d=yacc1"], cwd=d)
    open(os.path.join(d, name + ".lst"), "w").write(a.stdout)
    m = re.search(r"Object Code:(\d+) bytes", a.stdout)
    errs = re.search(r"^(\d+) Errors", a.stdout, re.M)
    if a.returncode or not errs or errs.group(1) != "0" or not m:
        bad = [l for l in a.stdout.splitlines() if "ERR" in l or "not found" in l][:5]
        return False, "assembler: " + "; ".join(bad)
    size = int(m.group(1))
    if want_oracle and "no-oracle" not in open(src).read(): oracle(src, out_file)
    if not os.path.exists(out_file): return False, "no %s" % os.path.basename(out_file)
    with open(in_file) if os.path.exists(in_file) else open(os.devnull) as f:
        try:
            e = sh([EMU, "-x", "-f", os.path.join(d, name + ".img")], stdin=f, timeout=60)
        except subprocess.TimeoutExpired:
            return False, "emulator: timeout (no HALT within 60 s)"
    inst = re.search(r"after (\d+) instructions", e.stderr)
    expected = open(out_file).read()
    if e.stdout != expected:
        open(os.path.join(d, name + ".got"), "w").write(e.stdout)
        return False, "output differs (got %d bytes, expected %d; see build/%s/%s.got)\n--- got ---\n%s\n--- expected ---\n%s" % (
            len(e.stdout), len(expected), name, name, e.stdout[:300], expected[:300])
    if not inst: return False, "emulator did not HALT: " + e.stderr.strip()[-200:]
    return True, "%5d bytes  %8s instructions" % (size, inst.group(1))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want_oracle = "--oracle" in sys.argv; keep = "--keep" in sys.argv
    for t in (ASM, EMU):
        if not os.path.exists(t): sys.exit("missing %s (run `make` at the repo root)" % t)
    os.makedirs(BUILD, exist_ok=True)
    tests = sorted(glob.glob(os.path.join(HERE, "*.c")))
    if args: tests = [t for t in tests if os.path.basename(t)[:-2] in args]
    passed = 0
    for src in tests:
        ok, msg = run_one(src, want_oracle)
        passed += ok
        print("%-14s %s  %s" % (os.path.basename(src)[:-2], "PASS" if ok else "FAIL", msg), flush=True)
    print("%d/%d passed" % (passed, len(tests)))
    if not keep and passed == len(tests): shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    main()
