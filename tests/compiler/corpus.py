#!/usr/bin/env python3
"""The y1cc compile corpus (2026-09-24): every C program the tree compiles, with the option sets the Makefiles and test
runners use, plus a few extra option combinations for coverage. Shared by

  tests/compiler/diffcheck.py   old y1cc.py (a git revision) against the working y1cc.py: identical assembly
  tests/compiler/twin.py        y1cc.py against the C twin software/compiler/c/y1cc: identical assembly

  corpus.py            list the corpus (path + options), one compile per line

items() yields (tag, path relative to the repo root, [options]). Options never include -o. The first line of every
output is a comment with the compile date and time ("; y1cc: prog.c  (2026-09-24 12:34)"); normalize() masks that
timestamp, which is the only text allowed to differ between two compilers run at different minutes.
"""
import os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def rel(p): return os.path.relpath(p, ROOT)


def flags_of(path):                                   # per-test flags, as tests/compiler/run.py reads them
    m = re.search(r"//\s*y1cc:\s*(.*)", open(path).read())
    return m.group(1).split() if m else []


def items():
    for src in sorted(glob.glob(os.path.join(HERE, "*.c"))):
        name = os.path.basename(src)[:-2]; fl = flags_of(src)
        if os.path.exists(src[:-2] + ".err"):         # expected compile error: the error text is compared
            yield ("err", rel(src), ["--boot"] + fl); continue
        yield ("boot", rel(src), ["--boot"] + fl)                          # tests/compiler/run.py, tests/ucemu/run.py
        yield ("plain", rel(src), fl)                                      # tests/bench/run.py, tests/monload/run.py
        yield ("os", rel(src), ["--org", "0x5000", "--os"] + fl)           # coverage: the --os runtime
        if "--no-brur" not in fl: yield ("nobrur", rel(src), ["--boot", "--no-brur"] + fl)
    for name in ("hello", "fib", "calls"):
        yield ("vector", rel(os.path.join(HERE, name + ".c")), ["--vector"])
    for src in sorted(glob.glob(os.path.join(ROOT, "software/compiler/bench/*.c")) +
                      glob.glob(os.path.join(ROOT, "software/compiler/bench/full/*.c"))):
        yield ("bench", rel(src), ["--boot"])                              # software/compiler/bench/sizecmp.sh
    for src in sorted(glob.glob(os.path.join(ROOT, "tests/bench/diag/*.c"))):
        yield ("diag", rel(src), [])
    yield ("os-c", "os/y1os.c", ["--org", "0x1000", "--os"])              # os/Makefile OS=c
    for src in sorted(glob.glob(os.path.join(ROOT, "os/commands/*.c"))):
        yield ("bin", rel(src), ["--org", "0x5000", "--os"])              # os/Makefile /BIN commands
    for src in sorted(glob.glob(os.path.join(ROOT, "tests/os/*.c"))):
        yield ("os-test", rel(src), ["--org", "0x5000", "--os"])          # tests/os/run.py EXTRA programs
    cc = os.path.join(ROOT, "software/compiler/c/target.c")               # y1cc.c (the C twin) compiled as a Y1/OS program
    if os.path.exists(cc):
        yield ("self", rel(cc), ["--org", "0x5000", "--os"])


STAMP = re.compile(r"^(; y1cc: .*)  \(\d{4}-\d\d-\d\d \d\d:\d\d\)$", re.M)


def normalize(text):
    return STAMP.sub(r"\1  (DATE)", text, count=1)


if __name__ == "__main__":
    n = 0
    for tag, path, opts in items():
        print("%-8s %-44s %s" % (tag, path, " ".join(opts))); n += 1
    print("%d compiles" % n)
