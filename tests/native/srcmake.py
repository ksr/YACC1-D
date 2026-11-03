#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/native/srcmake.py - the disk's /SRC built by /BIN/MAKE under Y1/OS, byte-identical to the host (2026-11-03).

On a copy of os/disk.img, on the instruction-level emulator, one console session:

  cd /SRC, make            /SRC/Makefile: cd to each directory and make there (nested scripts: make EXECs its
                           MAKE.SH, a recipe line's make runs its own, then the first goes on), which builds every
                           /BIN command the native compiler can (os/mksrcmk.py NATIVE_NO lists the two it cannot),
                           ASM from its assembly, and CC1 .. CC9
  make                     again: every program exists, so nothing is compiled ("make: nothing to do" in each)
  make install             the programs copied to /BIN and /LIB/CC

and the host then checks, from the image (tools/p8xfs.py get), every program file in /SRC against os/Makefile's
build of the same source (os/build/bin, asma, cc), and the installed /BIN and /LIB/CC files against them too; that
no script stopped ("sh: stopped"); and that the second make compiled nothing. Since the natively built compiler is
the host's byte for byte, and tests/native/selfhost.py proves that it rebuilds itself, the installed system is the
one the session started with.

  srcmake.py [--keep]      --keep: leave tests/native/build/srcmake/disk.img
"""
import os, sys, re, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OS = os.path.join(ROOT, "os")
B = os.path.join(HERE, "build", "srcmake")
sys.path.insert(0, OS)
import mksrcmk                                       # PASSN, NATIVE_NO
EMU = os.path.join(ROOT, "software/emulator/emulator")
LIMIT = "200000000000"                               # instructions; the whole session needs about 2.5G


def get(img, path):
    out = os.path.join(B, "got.bin")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "get", img, path, "--out", out],
                       capture_output=True)
    return open(out, "rb").read() if r.returncode == 0 else None


def main():
    subprocess.run(["make", "-s", "-C", OS], check=True)
    os.makedirs(B, exist_ok=True)
    img = os.path.join(B, "disk.img")
    shutil.copy(os.path.join(OS, "disk.img"), img)
    # what /SRC builds: (directory, program, the host's build, where install puts it)
    progs = []
    for f in sorted(os.listdir(os.path.join(OS, "commands"))):
        if f.endswith(".c"):
            n = f[:-2].upper(); n = "ASMC" if n == "ASM" else n
            if n not in mksrcmk.NATIVE_NO:
                progs.append(("/SRC/os/commands", n, "bin/%s.bin" % f[:-2], "/BIN/" + n))
    progs.append(("/SRC/os/commands-asm", "ASM", "asma/asm.bin", "/BIN/ASM"))
    for i, p in enumerate(mksrcmk.PASSN):
        progs.append(("/SRC/software/compiler/c/target", "CC%d" % (i + 1), "cc/%s.bin" % p, "/LIB/CC/CC%d" % (i + 1)))
    script = "O\ncd /SRC\nmake\nmake\nmake install\nexit\n0\n"
    r = subprocess.run([EMU, "-x", "-m", "-c", img, "-l", LIMIT], input=script.encode(), capture_output=True)
    out = r.stdout.decode("latin1")
    open(os.path.join(B, "session.txt"), "w").write(out)
    fails = []
    if "sh: stopped" in out: fails.append("a script stopped (see %s)" % os.path.join(B, "session.txt"))
    if not re.search(r"\n\r?bye", out): fails.append("the session did not end (limit too low?)")
    ncc = len(re.findall(r"> cc ", out))             # each compile, as the script shows it: once per C program
    if ncc != len(progs) - 1: fails.append("%d compiles for %d C programs (the second make compiled?)" % (ncc, len(progs) - 1))
    for d, n, host, inst in progs:
        want = open(os.path.join(OS, "build", host), "rb").read()
        got = get(img, "%s/%s" % (d, n))
        if got is None: fails.append("%s/%s: not built" % (d, n))
        elif got != want: fails.append("%s/%s: differs from os/build/%s (%d / %d bytes)" % (d, n, host, len(got), len(want)))
        got = get(img, inst)
        if got != want: fails.append("%s: not the build after make install" % inst)
    print("srcmake: %d programs built from /SRC by make under Y1/OS, compared with the host's builds" % len(progs))
    for f in fails: print("  FAIL " + f)
    print("srcmake: %d problems" % len(fails))
    if not fails and "--keep" not in sys.argv: shutil.rmtree(B)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
