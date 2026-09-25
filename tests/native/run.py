#!/usr/bin/env python3
"""tests/native/run.py - the native C compiler under Y1/OS (2026-09-25): the nine passes of the multi-pass y1cc
(software/compiler/c/cc1_lex.c .. cc9_final.c) built as Y1/OS programs (make -C os passes: y1cc.py --os --org 0x5000
--stack 0xCFFF --xisa), on the OS disk with the compiler's library (/LIB/CC/CC1..CC9, /LIB/Y1CCRT.TXT, /LIB/Y1LIB.C)
and /BIN/CC, which starts the chain (each pass EXECs the next), run on the emulated YACC1 to compile C programs; the
assembly they write must be byte-identical to what y1cc.py writes on the Mac (the header's date masked: Y1/OS has
no clock).

  run.py [name ...] [-v] [--keep]     name = a program of PROGRAMS (default: all)

The stack (y1cc --stack, BACKLOG "The road to a native compiler" step 2): every pass starts with MVIW R1,$CFFF and
runs on its own stack above its tables. The instruction-level emulator's stack watch (-S) reports, for every
program that does that, the lowest R1 it reached; that must stay above the pass's last byte of uninitialised data
(bss_end, counted from its assembly as tests/compiler/passes.py does). The report gives each pass's deepest point,
its room left, and its instruction count.
"""
import os, sys, re, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tests/compiler"))
import corpus, twin                                  # normalize() (the header's date), estimate() (image + bss)

BUILD = os.path.join(HERE, "build")
OS = os.path.join(ROOT, "os")
FS = [sys.executable, os.path.join(ROOT, "tools/p8xfs.py")]
PY = os.path.join(ROOT, "software/compiler/y1cc.py")
EMU = os.path.join(ROOT, "software/emulator/emulator")
PASSN = ["lex", "parse", "decl", "calls", "layout", "stmt", "sema", "emit", "final"]
TPA = 0x5000
# (name, source relative to the repo, y1cc options): compiled on the machine and on the Mac
C = "tests/compiler/"
PROGRAMS = [("hello", C + "hello.c", []), ("fib", C + "fib.c", []), ("sieve", C + "sieve.c", []),
            ("calls", C + "calls.c", []), ("globals", C + "globals.c", []), ("chars", C + "chars.c", []),
            ("structs", C + "structs.c", []), ("switch", C + "switch.c", []), ("rfact", C + "rfact.c", []),
            ("stack", C + "stack.c", ["--stack", "0xC7FF"])]


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)
    if r.returncode: sys.exit("native: %s failed:\n%s%s" % (" ".join(cmd), r.stdout[-2000:], r.stderr[-2000:]))
    return r.stdout


def bss_end(name):
    """the address of the pass's bss_end (its last byte of uninitialised data) from its assembly"""
    code, data, bss = twin.estimate(open(os.path.join(OS, "build/cc", name + ".asm")).read())
    return TPA + code + data + bss - 1


def make_disk(progs):
    sh(["make", "-s", "-C", OS])                    # the disk has the compiler: /BIN/CC, /LIB/CC/CC1..CC9, /LIB/...
    os.makedirs(BUILD, exist_ok=True)
    img = os.path.join(BUILD, "native.img")
    shutil.copy(os.path.join(OS, "disk.img"), img)
    sh(FS + ["mkdir", img, "/SRC"])
    sh(FS + ["mkdir", img, "/OUT"])
    for name, src, opts in progs:
        sh(FS + ["put", img, os.path.join(ROOT, src), "--name", "/SRC/" + os.path.basename(src)])
    return img


def main():
    av = sys.argv[1:]
    verbose = "-v" in av
    names = [a for a in av if not a.startswith("-")]
    progs = [p for p in PROGRAMS if not names or p[0] in names]
    img = make_disk(progs)
    lines = ["O"]
    for name, src, opts in progs:
        lines.append("cc /SRC/%s -o /OUT/%s.ASM %s" % (os.path.basename(src), name.upper(), " ".join(opts)))
    lines += ["exit", "0", ""]
    r = subprocess.run([EMU, "-x", "-S", "-m", "-c", img, "-l", "2000000000"], input="\n".join(lines).encode(),
                       capture_output=True)
    out = r.stdout.decode("latin1"); err = r.stderr.decode("latin1")
    if verbose: print(out[out.find("BOOT FROM CF"):])
    segs = [tuple(int(x[1:], 16) if x.startswith("$") else int(x) for x in m.groups())
            for m in re.finditer(r"stack \d+: (\$[0-9A-F]+) down to (\$[0-9A-F]+), (\d+) bytes, (\d+) instructions", err)]
    bad = 0
    if len(segs) != 9 * len(progs):
        print("expected %d stack segments (9 passes x %d programs), got %d:\n%s" % (9 * len(progs), len(progs), len(segs), err[-1500:]))
        bad += 1
    low = [0x10000] * 9; insn = [0] * 9; per = []
    for k, (top, lo, nbytes, n) in enumerate(segs[:9 * len(progs)]):
        i = k % 9
        low[i] = min(low[i], lo); insn[i] += n
        if i == 0: per.append(0)
        per[-1] += n
    same = 0
    for j, (name, src, opts) in enumerate(progs):
        want = os.path.join(BUILD, name + ".want.asm"); got = os.path.join(BUILD, name + ".got.asm")
        sh([sys.executable, PY, os.path.join(ROOT, src), "-o", want] + opts)
        g = subprocess.run(FS + ["get", img, "/OUT/%s.ASM" % name.upper(), "--out", got], capture_output=True, text=True)
        ok = g.returncode == 0 and corpus.normalize(open(got, encoding="latin1").read()) == corpus.normalize(open(want).read())
        if not ok: bad += 1
        else: same += 1
        print("%-8s %-28s %s  %9d instructions" % (name, src, "identical" if ok else "DIFFERENT", per[j] if j < len(per) else 0))
    print("%-5s %-7s %7s %7s %7s %12s" % ("pass", "", "bss_end", "lowest", "room", "instructions"))
    for i, n in enumerate(PASSN):
        be = bss_end(n)
        room = low[i] - be - 1
        if room < 0: bad += 1
        print("cc%d   %-7s   $%04X   $%04X %7d %12d%s" % (i + 1, n, be, low[i], room, insn[i], "" if room >= 0 else "  COLLISION"))
    print("%d programs compiled on the emulated YACC1 (instruction-level emulator): %d identical to y1cc.py; %d problems"
          % (len(progs), same, bad))
    if "--keep" not in av and not bad: shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
