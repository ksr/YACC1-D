#!/usr/bin/env python3
"""diffcheck.py - differential proof for a y1cc.py change (2026-09-24, written for the recursion support): compile the
whole corpus (tests/compiler/corpus.py: the compiler tests in four option sets, the bench sources, the Y1/OS C kernel,
every /BIN command, the OS test programs) with an OLD y1cc.py taken from git and with the working one, and diff.

  diffcheck.py [--base REV] [--keep] [-v]
    --base REV   the old compiler's git revision (default: c847a97, the last y1cc.py without recursion)
    --keep       leave the outputs in tests/compiler/build/diffcheck/{old,new}/
    -v           print every compile

Every program the old compiler accepts must come out byte-identical (the header's timestamp masked). A program the
old compiler REJECTS is allowed to differ only if the old error was its "recursion is not supported" (the programs
that only compile since recursion exists), or if the old compiler crashed (a Python traceback: fixed bugs such as
tests/compiler/adjstr.c); for expected-error tests the error texts must be equal. Exit 1 on any other difference.
Compiles with --xisa (2026-09-24: tests/compiler/xisa.c asks for it) or --stack (2026-09-25: tests/compiler/stack.c) are
not compared when the old compiler predates the option (it ignores the flag): they are counted apart; the default
output is what this proves unchanged.
"""
import os, sys, subprocess, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus

ROOT = corpus.ROOT
NEW = os.path.join(ROOT, "software/compiler/y1cc.py")
BUILD = os.path.join(corpus.HERE, "build", "diffcheck")


def old_compiler(rev, d):
    """The old y1cc.py with ITS lib/ beside it (y1cc resolves #include "y1lib.c" relative to itself)."""
    os.makedirs(os.path.join(d, "lib"), exist_ok=True)
    for p in ("software/compiler/y1cc.py", "software/compiler/lib/y1lib.c"):
        r = subprocess.run(["git", "show", "%s:%s" % (rev, p)], cwd=ROOT, capture_output=True)
        if r.returncode: sys.exit("diffcheck: git show %s:%s failed: %s" % (rev, p, r.stderr.decode().strip()))
        open(os.path.join(d, p.replace("software/compiler/", "")), "wb").write(r.stdout)
    return os.path.join(d, "y1cc.py")


def compile_(cc, src, opts, out):
    r = subprocess.run([sys.executable, cc, os.path.join(ROOT, src), "-o", out] + opts, cwd=ROOT,
                       capture_output=True, text=True)
    text = corpus.normalize(open(out).read()) if r.returncode == 0 and os.path.exists(out) else None
    return r.returncode, text, (r.stderr + r.stdout).strip()


def main():
    av = sys.argv[1:]
    rev = av[av.index("--base") + 1] if "--base" in av else "c847a97"
    verbose = "-v" in av
    shutil.rmtree(BUILD, ignore_errors=True)
    tmp = tempfile.mkdtemp(prefix="y1cc-old-")
    old = old_compiler(rev, tmp)
    same = newonly = errs = crashed = xonly = 0; bad = []
    oldtext = open(old).read()
    for i, (tag, src, opts) in enumerate(corpus.items()):
        newopt = [o for o in ("--xisa", "--stack") if o in opts and o not in oldtext]
        if newopt:                                       # an option the old compiler does not have
            xonly += 1
            if verbose: print("%-44s %-28s %s" % (src, " ".join(opts), "%s: new option, not compared" % newopt[0]))
            continue
        base = "%03d_%s_%s" % (i, tag, os.path.basename(src)[:-2])
        outs = {}
        for side, cc in (("old", old), ("new", NEW)):
            d = os.path.join(BUILD, side); os.makedirs(d, exist_ok=True)
            outs[side] = compile_(cc, src, opts, os.path.join(d, base + ".asm"))
        (orc, otext, oerr), (nrc, ntext, nerr) = outs["old"], outs["new"]
        if orc == 0:
            ok = nrc == 0 and otext == ntext
            if ok: same += 1
            else: bad.append((src, opts, "differs" if nrc == 0 else "new compiler failed: " + nerr[-200:]))
            state = "identical" if ok else "DIFFERENT"
        elif "Traceback (most recent call last)" in oerr:   # the old compiler crashed: nothing to compare
            crashed += 1; state = "old crashed (%s), new: %s" % (oerr.splitlines()[-1][:60], "compiles" if nrc == 0 else nerr[-60:])
        elif "recursion is not supported" in oerr:
            if nrc == 0: newonly += 1; state = "new: compiles (old: recursion rejected)"
            else: errs += 1; state = "both reject (new: %s)" % nerr[-90:]
        else:
            ok = nrc != 0 and oerr == nerr
            if ok: errs += 1
            else: bad.append((src, opts, "old error %r, new %r" % (oerr[-120:], nerr[-120:])))
            state = "same error" if ok else "ERROR DIFFERS"
        if verbose or state.isupper() or state.startswith("ERROR"):
            print("%-44s %-28s %s" % (src, " ".join(opts), state))
    shutil.rmtree(tmp, ignore_errors=True)
    print("diffcheck against %s: %d identical, %d compile only with the new y1cc (recursion), %d expected errors, "
          "%d crashed the old one, %d DIFFERENT%s" % (rev, same, newonly, errs, crashed, len(bad),
          "; %d --xisa/--stack compiles not compared (options the old y1cc does not have)" % xonly if xonly else ""))
    for src, opts, why in bad: print("  DIFF %s %s: %s" % (src, " ".join(opts), why))
    if "--keep" not in av and not bad: shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
