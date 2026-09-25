#!/usr/bin/env python3
"""tests/native/run.py - C compiled, assembled and run on the emulated YACC1 (2026-09-25): the first native builds.

Under Y1/OS, on a copy of the OS disk (which carries the compiler since 2026-09-25: /BIN/CC, the passes
/LIB/CC/CC1..CC9, /LIB/Y1CCRT.TXT, /LIB/Y1LIB.C, and the assembler /BIN/ASM), each program of PROGRAMS is

  1. compiled by the native compiler: `cc NAME.c -o /OUT/NAME/NAME.ASM --org 0x5000 --os [flags]` in its source directory
     (the sources are on the disk under /R as they are in the repository, so the #includes resolve as on the Mac;
     `cc` runs the nine passes, each EXECing the next);
  2. assembled by the native assembler: `asm /OUT/NAME/NAME.ASM` -> the program file /OUT/NAME/NAME;
  3. run: `run /OUT/NAME/NAME args < input > /OUT/NAME/NAME.TXT` (programs that poke the OS's tables or write to port 2
     directly are only compiled and assembled);

and the host checks, from the disk image afterwards (tools/p8xfs.py get), that the assembly is byte-identical to
what y1cc.py writes on the Mac (the header's date masked: Y1/OS has no clock), that the program file is
byte-identical to the host toolchain's (y1cc.py + the host assembler + img2bin; a /BIN command's also to the
Makefile's build of it), and that the program's output is the expected one (tests/compiler/NAME.out, or what the
/BIN build of the same command prints in the same session).

  run.py [name ...] [--int | --uc] [--all-uc] [-v] [--keep]
    name       only these programs;  --int / --uc   one emulator only (default: both)
    --all-uc   every program on the microcode emulator too (default: UC_SET; the rest take long there)

On the instruction-level emulator the program watch (`emulator -S`: one line per program Y1/OS starts) gives the
instructions of every step, and each compiler pass's deepest stack point, which must stay above the pass's last
byte of data (bss_end, counted from its assembly as tests/compiler/passes.py does). The microcode emulator gives the
session's steps and clocks; their ratio to its instructions turns the instruction counts into an estimate of the
time on the machine at 1 MHz (a clock period of 1 us).
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
ASM = os.path.join(ROOT, "software/assembler/asm")
EMUS = {"int": os.path.join(ROOT, "software/emulator/emulator"), "uc": os.path.join(ROOT, "software/ucemu/y1ucemu")}
MON_EXIT = "F10E"                                    # the monitor's `0` (cmd_exit): ucemu stops there (-E)
PASSN = ["lex", "parse", "decl", "calls", "layout", "stmt", "sema", "emit", "final"]
TPA = 0x5000
C = "tests/compiler/"
# name (the file name on the disk, up to 8 characters), source, extra y1cc flags, the run (None: compile and assemble
# only; else (arguments, stdin file on the disk or None, expected output: "out" = tests/compiler/NAME.out, "skip1" =
# the same without its first line, "bin CMD" = what CMD prints in the same session)), and the /BIN program the result
# must equal byte for byte (os/build/bin/NAME.bin), if any
PROGRAMS = [
    ("hello", C + "hello.c", [], ("", None, "out")),
    ("fib", C + "fib.c", [], ("", None, "out")),
    ("sieve", C + "sieve.c", [], ("", None, "out")),
    ("arith", C + "arith.c", [], ("", None, "out")),
    ("arrays", C + "arrays.c", [], ("", None, "out")),
    ("calls", C + "calls.c", [], ("", None, "out")),
    ("chars", C + "chars.c", [], ("", "/R/tests/compiler/chars.in", "out")),
    ("control", C + "control.c", [], ("", None, "out")),
    ("globals", C + "globals.c", [], ("", None, "out")),
    ("io", C + "io.c", [], None),                    # its outp(2) goes past the shell's > to the screen
    ("rcalc", C + "rcalc.c", [], ("", None, "out")),
    ("rfact", C + "rfact.c", [], ("", None, "out")),
    ("rlocals", C + "rlocals.c", [], ("", None, "out")),
    ("rmutual", C + "rmutual.c", [], ("", None, "out")),
    ("stack", C + "stack.c", ["--stack", "0xC7FF"], ("", None, "skip1")),   # line 1: the caller's SP (the shell's)
    ("structs", C + "structs.c", [], ("", None, "out")),
    ("switch", C + "switch.c", [], ("", None, "out")),
    ("switchnb", C + "switchnb.c", ["--no-brur"], ("", None, "out")),
    ("syscall", C + "syscall.c", [], None),          # installs its own SYSTAB entries: not under the OS
    ("syscall2", C + "syscall2.c", [], None),
    ("xisa", C + "xisa.c", ["--xisa"], ("", None, "out")),
    ("fibx", C + "fib.c", ["--xisa"], ("", None, "out")),
    ("chello", "os/commands/hello.c", [], ("a b c", None, "bin hello a b c"), "hello"),
    ("cecho", "os/commands/echo.c", [], ("native echo", None, "bin echo native echo"), "echo"),
    ("ccat", "os/commands/cat.c", [], ("/FRUIT.TXT /README.TXT", None, "bin cat /FRUIT.TXT /README.TXT"), "cat"),
    ("cwc", "os/commands/wc.c", [], ("/R/tests/compiler/fib.c", None, "bin wc /R/tests/compiler/fib.c"), "wc"),
    ("cc4", "software/compiler/c/target/calls.c", [], None),     # the compiler compiling its own pass 4
]
UC_SET = ["hello", "fib", "cecho", "ccat"]
EMPTY = "/R/EMPTY"


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)
    if r.returncode: sys.exit("native: %s failed:\n%s%s" % (" ".join(cmd), r.stdout[-2000:], r.stderr[-2000:]))
    return r.stdout


def bss_end(name):
    """the address of a pass's bss_end (its last byte of uninitialised data) from its assembly"""
    code, data, bss = twin.estimate(open(os.path.join(OS, "build/cc", name + ".asm")).read())
    return TPA + code + data + bss - 1


def host_build(p):
    """y1cc.py + the host assembler + img2bin: (assembly text, program bytes)"""
    name, src, flags = p[0], p[1], p[2]
    d = os.path.join(BUILD, "host"); os.makedirs(d, exist_ok=True)
    shutil.copy(twin.DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    sh([sys.executable, PY, os.path.join(ROOT, src), "-o", os.path.join(d, name + ".asm"), "--org", "0x5000", "--os"] +
       flags, cwd=ROOT)
    lst = sh([ASM, name, "-d=yacc1"], cwd=d)
    if "\n0 Errors" not in lst: sys.exit("native: host assembler errors in %s" % name)
    sh([sys.executable, os.path.join(ROOT, "tools/img2bin.py"), os.path.join(d, name + ".img"),
        os.path.join(d, name + ".bin"), "--base", "0x5000"])
    return open(os.path.join(d, name + ".asm"), encoding="latin1").read(), open(os.path.join(d, name + ".bin"), "rb").read()


def make_disk(progs, img):
    """os/disk.img + the sources under /R (the repository's paths), an empty file for stdin, /OUT"""
    shutil.copy(os.path.join(OS, "disk.img"), img)
    files = {"os/lib_" + f for f in ("abi.c", "fs.c", "err.c", "stdin.c", "glob.c", "globx.c", "num.c", "apath.c",
                                    "rdline.c")}
    for p in progs:
        files.add(p[1])
        if p[3] and p[3][1]: files.add(p[3][1][3:])
    if any(p[0] == "cc4" for p in progs):           # the pass's own sources
        cdir = "software/compiler/c"
        for f in os.listdir(os.path.join(ROOT, cdir)):
            if f.endswith((".c", ".h")) and f.startswith(("p", "cc4", "io", "target")): files.add(cdir + "/" + f)
        files.add(cdir + "/ylim/calls.h")
    dirs = {"/R"}
    sh(FS + ["mkdir", img, "/R"])
    for f in sorted(files):
        parts = f.split("/")
        for i in range(1, len(parts)):
            d = "/R/" + "/".join(parts[:i])
            if d not in dirs: sh(FS + ["mkdir", img, d]); dirs.add(d)
        sh(FS + ["put", img, os.path.join(ROOT, f), "--name", "/R/" + f])
    e = os.path.join(BUILD, "empty"); open(e, "wb").close()
    sh(FS + ["put", img, e, "--name", EMPTY])
    sh(FS + ["mkdir", img, "/OUT"])
    for p in progs: sh(FS + ["mkdir", img, "/OUT/" + p[0].upper()])    # (a directory holds 62 entries)


def script(progs):
    lines = ["O"]
    for p in progs:
        name, src, flags, run = p[0], p[1], p[2], p[3]
        N = name.upper()
        lines.append("cd /R/" + os.path.dirname(src))
        lines.append("cc %s -o /OUT/%s/%s.ASM --org 0x5000 --os %s" % (os.path.basename(src), N, N, " ".join(flags)))
        lines.append("cd /")
        lines.append("asm /OUT/%s/%s.ASM" % (N, N))
        if run:
            args, stdin, expect = run
            lines.append("run /OUT/%s/%s %s < %s > /OUT/%s/%s.TXT" % (N, N, args, stdin or EMPTY, N, N))
            if expect.startswith("bin "): lines.append("%s > /OUT/%s/%s.REF" % (expect[4:], N, N))
    lines += ["exit", "0", ""]
    return "\n".join(lines)


def steps_of(p):
    """the programs Y1/OS starts for p, in order: cc, the nine passes, asm, the run, the /BIN reference"""
    n = ["cc"] + ["cc%d" % i for i in range(1, 10)] + ["asm"]
    if p[3]:
        n.append("run")
        if p[3][2].startswith("bin "): n.append("ref")
    return n


def get(img, path):
    out = os.path.join(BUILD, "get.tmp")
    r = subprocess.run(FS + ["get", img, path, "--out", out], capture_output=True, text=True)
    if r.returncode: return None
    data = open(out, "rb").read(); os.remove(out)
    return data


def check(p, img, host):
    """the host's checks for program p on a disk image: a list of failures"""
    name, src, flags, run = p[0], p[1], p[2], p[3]
    N = name.upper(); fails = []
    D = "/OUT/%s/%s" % (N, N)
    want_asm, want_bin = host
    got = get(img, D + ".ASM")
    if got is None: return ["no %s.ASM" % D]
    if corpus.normalize(got.decode("latin1")) != corpus.normalize(want_asm): fails.append("assembly differs")
    got = get(img, D)
    if got is None: fails.append("no program file " + D)
    elif got != want_bin:
        fails.append("program file differs from the host toolchain's (%d / %d bytes)" % (len(got), len(want_bin)))
    elif len(p) > 4 and open(os.path.join(OS, "build/bin", p[4] + ".bin"), "rb").read() != got:
        fails.append("differs from /BIN/" + p[4].upper())
    if run:
        out = get(img, D + ".TXT")
        kind = run[2]
        exp = get(img, D + ".REF") if kind.startswith("bin ") else open(os.path.join(ROOT, src[:-2] + ".out"), "rb").read()
        if kind == "skip1" and out is not None: out = out.split(b"\n", 1)[-1]; exp = exp.split(b"\n", 1)[-1]
        if out is None: fails.append("no output file")
        elif out != exp: fails.append("output differs: %r, expected %r" % (out[:80], (exp or b"")[:80]))
    return fails


def main():
    av = sys.argv[1:]
    verbose = "-v" in av
    names = [a for a in av if not a.startswith("-")]
    progs = [p for p in PROGRAMS if not names or p[0] in names]
    tags = ["int"] if "--int" in av else ["uc"] if "--uc" in av else ["int", "uc"]
    shutil.rmtree(BUILD, ignore_errors=True); os.makedirs(BUILD)
    sh(["make", "-s", "-C", OS])                    # the disk: the OS, /BIN (CC and ASM among them), /LIB, the passes
    host = {p[0]: host_build(p) for p in progs}
    bad = 0; stats = {}; uc_ratio = None
    for tag in tags:
        pl = progs if tag == "int" or "--all-uc" in av else [p for p in progs if p[0] in UC_SET]
        if not pl: continue
        img = os.path.join(BUILD, "native.%s.img" % tag)
        make_disk(pl, img)
        cmd = [EMUS[tag], "-x", "-m", "-c", img, "-l", "40000000000"] + (["-S"] if tag == "int" else ["-E", MON_EXIT])
        r = subprocess.run(cmd, input=script(pl).encode(), capture_output=True)
        out = r.stdout.decode("latin1"); err = r.stderr.decode("latin1")
        if verbose: print(out[out.find("BOOT FROM CF"):])
        if "\nbye" not in out:
            print("%-4s the session did not end (no bye): %s" % (tag, out[-600:])); bad += 1; continue
        n_ok = 0
        for p in pl:
            fails = check(p, img, host[p[0]])
            if fails: bad += 1; print("%-4s %-9s FAIL  %s" % (tag, p[0], "; ".join(fails)))
            else: n_ok += 1
        print("%-4s %d of %d programs compiled, assembled%s on the emulated YACC1 as on the Mac: %s" % (
            tag, n_ok, len(pl), " and run" if any(p[3] for p in pl) else "", " ".join(p[0] for p in pl)))
        if tag == "uc":
            m = re.search(r"after (\d+) instructions, (\d+) steps, (\d+) clocks", err)
            if m:
                i, s, c = (int(x) for x in m.groups())
                uc_ratio = (s / i, c / i)
                print("uc   the session: %d instructions, %d steps (%.1f an instruction), %d clocks (%.1f)" % (
                    i, s, s / i, c, c / i))
        if tag == "int":
            segs = [(int(m.group(1)), m.group(3)) for m in re.finditer(
                r"program \d+: (\d+) instructions(, stack \$[0-9A-F]+ down to \$([0-9A-F]+))?", err)]
            want = sum(len(steps_of(p)) for p in pl)
            if len(segs) != want:
                print("int  expected %d programs started, the watch saw %d:\n%s" % (want, len(segs), err[-1500:]))
                bad += 1; continue
            k = 0
            for p in pl:
                st = {}
                for what in steps_of(p): st[what] = segs[k]; k += 1
                stats[p[0]] = st
    if stats:
        low = [0x10000] * 9
        cpi = uc_ratio[1] if uc_ratio else 33.0
        print("instructions (int)  %9s %10s %10s %11s   %s" % ("compile", "asm", "run", "all", "at 1 MHz (estimated)"))
        tot = [0, 0, 0]
        for p in progs:
            st = stats.get(p[0])
            if not st: continue
            comp = sum(st[w][0] for w in ["cc"] + ["cc%d" % i for i in range(1, 10)])
            a = st["asm"][0]; r = st["run"][0] if "run" in st else 0
            tot[0] += comp; tot[1] += a; tot[2] += r
            for i in range(9):
                lo = st["cc%d" % (i + 1)][1]
                if lo: low[i] = min(low[i], int(lo, 16))
            secs = (comp + a) * cpi / 1e6
            print("  %-17s %9d %10d %10d %11d   %s to compile and assemble" % (
                p[0], comp, a, r, comp + a + r, "%dh %02dm" % (secs // 3600, secs % 3600 // 60) if secs >= 3600
                else "%dm %02ds" % (secs // 60, secs % 60)))
        print("  %-17s %9d %10d %10d %11d" % ("all", tot[0], tot[1], tot[2], sum(tot)))
        per = [sum(st["cc%d" % (i + 1)][0] for st in stats.values()) for i in range(9)]
        print("  the passes' share of the compiles: " + ", ".join("cc%d %.0f%%" % (i + 1, 100.0 * per[i] / tot[0])
                                                                 for i in range(9)))
        print("(estimate: %.1f clocks an instruction%s, a clock 1 us)" % (
            cpi, ", the ratio in the microcode emulator's session" if uc_ratio else " (assumed)"))
        print("%-5s %-7s %7s %7s %7s" % ("pass", "", "bss_end", "lowest", "room"))
        for i, n in enumerate(PASSN):
            be = bss_end(n); room = low[i] - be - 1
            if room < 0: bad += 1
            print("cc%d   %-7s   $%04X   $%04X %7d%s" % (i + 1, n, be, low[i], room, "" if room >= 0 else "  COLLISION"))
    print("native: %d problems" % bad)
    if "--keep" not in av and not bad: shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
