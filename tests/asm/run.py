#!/usr/bin/env python3
"""The native assembler /BIN/ASM (os/commands/asm.c) against the host assembler RC/asm (software/assembler), 2026-09-25.

  run.py [-v] [--only SUBSTR] [--target]

1. tools/gen_y1_optab.py --check: os/asm_optab.c is what software/assembler/yacc1.def gives.
2. asm.c is built for the Mac (host_asm.c + host_sys.c: the YACC1's integer types, the Y1/OS file syscalls emulated),
   so the code the machine runs is the code tested here.
3. The corpus, each source through RC/asm (`asm NAME -d=yacc1` with -h, and once more without it for the .prg's start
   address) and through the native assembler twice:
     asm -h NAME.asm OUT   Intel hex: must be byte-identical to RC/asm's NAME.img
     asm NAME.asm OUT      the program file: must be RC/asm's bytes from the lowest address to the highest (zeros in
                           the gaps), load = the lowest address, exec = END's address (else the load address); a
                           source whose code goes down in address (an ORG back) must be refused
   A source RC/asm reports errors for must fail in the native assembler too (no output file left).
   The corpus: every y1cc compile of tests/compiler/corpus.py (the compiler tests with their option sets, the bench
   sources, y1os.c, every /BIN command, the nine compiler passes, y1cc.c itself), each also with --xisa; and every
   hand-written YACC1 source in the tree (firmware/ monitor and BASIC with their candidates, monnew, tests/assembler,
   tests/ucemu/isa.asm, os/y1os.asm with its INCLUDE).
4. --target: the Y1/OS runs on both emulators (tests/asm/target.py): a disk with sources, `asm` run under the OS,
   the results fetched back and compared with RC/asm's.
Exit 1 on any difference. The work files are in tests/asm/build/ (git-ignored).
"""
import os, sys, re, glob, shutil, subprocess, concurrent.futures

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(HERE, "build")
RCASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
Y1CC = os.path.join(ROOT, "software/compiler/y1cc.py")
NATIVE = os.path.join(BUILD, "asm")
sys.path.insert(0, os.path.join(ROOT, "tests/compiler"))
import corpus                                    # noqa: E402


def sh(cmd, cwd=None, env=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace", env=env)
    return r.returncode, r.stdout, r.stderr


def build_native():
    rc, out, err = sh([sys.executable, os.path.join(ROOT, "tools/gen_y1_optab.py"), "--check"])
    print(out.strip() or err.strip())
    if rc: sys.exit(1)
    rc, out, err = sh(["cc", "-O1", "-funsigned-char", "-fno-builtin", "-fno-common", "-Wall", "-Wextra", "-Wno-keyword-macro",
                       "-o", NATIVE, os.path.join(HERE, "host_asm.c"), os.path.join(HERE, "host_sys.c")])
    if rc or err.strip(): sys.exit("host build of os/commands/asm.c:\n" + out + err)


def hexmem(path):
    """Intel hex -> (records [(addr, bytes)], memory {addr: byte})."""
    recs, mem = [], {}
    for line in open(path):
        if not line.startswith(":"): continue
        n, a, t = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
        if t: continue
        b = bytes.fromhex(line[9:9 + 2 * n])
        recs.append((a, b))
        for i, x in enumerate(b): mem[a + i] = x
    return recs, mem


def prepare(d):
    """d/ runs RC/asm with -h (the .img), d/prg/ without (the .prg, for END's start address)."""
    os.makedirs(os.path.join(d, "prg"), exist_ok=True)
    for sub, rc_opts in ((d, "-h\n"), (os.path.join(d, "prg"), "")):
        shutil.copy(DEF, sub)
        open(os.path.join(sub, "rcasm.rc"), "w").write(rc_opts)
    for inc in glob.glob(os.path.join(d, "*.inc")): shutil.copy(inc, os.path.join(d, "prg"))


def rcasm(d, name):
    """RC/asm on d/NAME.asm: (ok, errors text, img path, start address from the .prg)."""
    shutil.copy(os.path.join(d, name + ".asm"), os.path.join(d, "prg"))
    rc, out, _ = sh([RCASM, name, "-d=yacc1"], cwd=d)
    ok = "\n0 Errors" in out
    errs = "\n".join(l for l in out.splitlines() if "ERR" in l or "not found" in l)[:300]
    _, pout, _ = sh([RCASM, name, "-d=yacc1"], cwd=os.path.join(d, "prg"))
    m = re.search(r"^\*([0-9a-f]{4})$", open(os.path.join(d, "prg", name + ".prg")).read(), re.M)
    return ok, errs, os.path.join(d, name + ".img"), int(m.group(1), 16) if m else 0


def check(item):
    """One source: RC/asm, then the native assembler both ways. Returns (name, status, detail)."""
    title, name, d = item
    r = check1(name, d)
    return (title,) + r[1:]


def check1(name, d):
    ok, errs, img, start = rcasm(d, name)
    src = name + ".asm"
    nimg, nbin = name + ".n.img", name + ".n.bin"
    for f in (nimg, nbin):
        if os.path.exists(os.path.join(d, f)): os.remove(os.path.join(d, f))
    rc, out, err = sh([NATIVE, "-h", src, nimg], cwd=d)
    if not ok:                                   # RC/asm reports errors: the native assembler must fail too
        if rc and not os.path.exists(os.path.join(d, nimg)):
            return name, "error", "both report errors (RC/asm: %s | asm: %s)" % (
                errs.splitlines()[0] if errs else "?", err.strip().splitlines()[0] if err.strip() else "?")
        return name, "FAIL", "RC/asm reports errors, the native assembler does not: " + errs[:200]
    if rc: return name, "FAIL", "native -h failed: " + err.strip()[:300]
    if open(img, "rb").read() != open(os.path.join(d, nimg), "rb").read():
        return name, "FAIL", "-h output differs from RC/asm's .img"
    recs, mem = hexmem(img)
    down = any(recs[i][0] < recs[i - 1][0] + len(recs[i - 1][1]) for i in range(1, len(recs)))
    rc, out, err = sh([NATIVE, src, nbin], cwd=d)
    if down:
        if rc and "addresses go down" in err and not os.path.exists(os.path.join(d, nbin)):
            return name, "ok-hex", "hex identical; program file refused (an ORG back), as it must be"
        return name, "FAIL", "an ORG back: the program file should be refused"
    if rc: return name, "FAIL", "native program file failed: " + err.strip()[:300]
    got = open(os.path.join(d, nbin), "rb").read()
    if mem:
        lo, hi = min(mem), max(mem)
        want = bytes(mem.get(a, 0) for a in range(lo, hi + 1))
    else:
        lo, want = 0, b""
    if got != want: return name, "FAIL", "program file differs (%d bytes, expected %d)" % (len(got), len(want))
    m = re.search(r"created \S+ load ([0-9A-F]{4}) exec ([0-9A-F]{4})", err)
    exp_exec = start if start else lo
    if not m or int(m.group(1), 16) != lo or int(m.group(2), 16) != exp_exec:
        return name, "FAIL", "load/exec %s, expected %04X/%04X" % (m.groups() if m else None, lo, exp_exec)
    labels = re.search(r"(\d+) bytes, (\d+) labels", out)
    return name, "ok", "%s bytes, %s labels" % labels.groups() if labels else ""


def y1cc_items(only):
    """Compile the y1cc corpus (plain and --xisa) into build/c; returns [(name, dir)]."""
    d = os.path.join(BUILD, "c")
    os.makedirs(d, exist_ok=True)
    jobs = []
    for n, (tag, path, opts) in enumerate(corpus.items()):
        if tag == "err": continue
        base = "%s_%s_%d" % (tag, os.path.basename(path)[:-2], n)
        for x in ([], ["--xisa"]):
            name = (base + ("_x" if x else "")).lower()
            if only and only not in name: continue
            jobs.append((name, path, opts + x))

    def comp(j):                                 # the file is c<index>.asm: Y1/OS command lines are short
        i, (name, path, opts) = j
        rc, out, err = sh([sys.executable, Y1CC, os.path.join(ROOT, path), "-o", os.path.join(d, "c%03d.asm" % i)] + opts)
        return name, rc, err
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for name, rc, err in ex.map(comp, enumerate(jobs)):
            if rc: sys.exit("y1cc failed on %s: %s" % (name, err[-300:]))
    return [(name, "c%03d" % i, d) for i, (name, _, _) in enumerate(jobs)]


def hand_items(only):
    """The hand-written sources, copied into build/hand under clean names (some have spaces)."""
    d = os.path.join(BUILD, "hand")
    os.makedirs(d, exist_ok=True)
    srcs = sorted(glob.glob(os.path.join(ROOT, "firmware/**/*.asm"), recursive=True) +
                  glob.glob(os.path.join(ROOT, "tests/assembler/**/*.asm"), recursive=True) +
                  [os.path.join(ROOT, "tests/ucemu/isa.asm"), os.path.join(ROOT, "os/y1os.asm")] +
                  glob.glob(os.path.join(HERE, "src/*.asm")))
    for inc in glob.glob(os.path.join(HERE, "src/*.inc")): shutil.copy(inc, d)
    items = []
    for s in srcs:
        rel = os.path.relpath(s, ROOT)
        if "/build/" in rel: continue
        name = re.sub(r"[^a-z0-9]+", "_", rel[:-4].lower()).strip("_")
        if only and only not in name: continue
        short = "h%03d" % len(items)
        shutil.copy(s, os.path.join(d, short + ".asm"))
        items.append((name, short, d))
    if any(n == "os_y1os" for n, _, _ in items):   # y1os.asm INCLUDEs its strings, made by os/mkstrings.py
        rc, out, err = sh([sys.executable, os.path.join(ROOT, "os/mkstrings.py"), os.path.join(ROOT, "os/strings.txt")])
        if rc: sys.exit("mkstrings.py: " + err)
        open(os.path.join(d, "y1os_str.inc"), "w").write(out)
    return items


def main():
    verbose = "-v" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1].lower() if "--only" in sys.argv else ""
    os.makedirs(BUILD, exist_ok=True)
    build_native()
    items = y1cc_items(only) + hand_items(only)
    for d in sorted({d for _, _, d in items}): prepare(d)
    counts = {}
    fails = []
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for name, status, detail in ex.map(check, items):
            counts[status] = counts.get(status, 0) + 1
            if status == "FAIL": fails.append((name, detail))
            if verbose or status == "FAIL": print("%-44s %-7s %s" % (name, status, detail))
    print("tests/asm: %d sources: %d identical (hex and program file), %d identical in hex (program file refused: "
          "an ORG back), %d rejected by both assemblers, %d FAILED" % (len(items), counts.get("ok", 0),
          counts.get("ok-hex", 0), counts.get("error", 0), counts.get("FAIL", 0)))
    if "--target" in sys.argv:
        rc = subprocess.run([sys.executable, os.path.join(HERE, "target.py")]).returncode
        if rc: fails.append(("target", "the emulator runs failed"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
