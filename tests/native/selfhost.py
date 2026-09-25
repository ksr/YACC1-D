#!/usr/bin/env python3
"""tests/native/selfhost.py - the YACC1 toolchain rebuilds itself under Y1/OS on the emulated YACC1 (2026-09-25).

Stage 1 (the native build): on a copy of the OS disk, with the toolchain's own sources on it under /R (as they are in
the repository: software/compiler/c's pass sources, target/, ylim/, the os/lib_*.c libraries, os/asm_optab.c,
os/commands/asm.c and cc.c; /LIB/Y1LIB.C and /LIB/Y1CCRT.TXT are on the OS disk already), the host-built compiler
(/BIN/CC + /LIB/CC/CC1..CC9) compiles

  - each of the nine passes, software/compiler/c/target/NAME.c, with os/Makefile's flags for them
    (--org 0x5000 --os --stack 0xCFFF --xisa), and
  - the assembler os/commands/asm.c and the driver os/commands/cc.c, with the /BIN flags (--org 0x5000 --os),

and the host-built /BIN/ASM assembles each one into a program file. The host fetches the eleven assemblies and program
files off the image (tools/p8xfs.py get) and compares them byte for byte with os/build (the Makefile's host builds:
y1cc.py + the host assembler + img2bin; the assembly with the header's date masked, Y1/OS has no clock).

Stage 2 (the fixed point): a fresh copy of the OS disk with the NATIVELY built CC1..CC9 (in /LIB/CC), CC and ASM (in
/BIN) in place of the host-built ones (taken off stage 1's image), and the same eleven compiles and assemblies again:
every output must again be the host's, byte for byte. Then the YACC1 toolchain reproduces itself with no host
involved (the host only puts the sources on the disk and reads the results).

  selfhost.py [name ...] [--stage 1|2] [--uc] [-v] [--keep]
    name       only these programs (lex parse decl calls layout stmt sema emit final asm cc; default: all eleven);
               stage 2 then installs host builds for the programs not rebuilt
    --stage N  only stage N (stage 2 alone installs the host builds: a check of the procedure, not of the fixed point)
    --uc       stage 1 also on the microcode emulator (the clocks; all eleven: about 30 minutes, 79G clocks)
    --keep     keep tests/native/build/selfhost (the images) also when everything passed

On the instruction-level emulator (and with --uc stage 1 on the microcode emulator, ~70x slower). The program watch
(`emulator -S`) gives each step's instructions, and each pass's deepest stack, which must stay above its last byte of
data (bss_end). The estimate at 1 MHz takes 32.4 clocks an instruction (the microcode emulator's ratio on
tests/native/run.py's programs, 2026-09-25) and a clock of 1 us. About 30 seconds for the 4.7G
instructions of both stages: in `make check`, and alone `make selfhost`.
"""
import os, sys, re, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run                                           # sh, get, the emulator, corpus.normalize, bss_end

ROOT, OS, FS = run.ROOT, run.OS, run.FS
BUILD = os.path.join(HERE, "build", "selfhost")
CPI = 32.4                                           # clocks an instruction (tests/native/run.py's uc ratio)
PFLAGS = "--org 0x5000 --os --stack 0xCFFF --xisa"  # os/Makefile, the passes
BFLAGS = "--org 0x5000 --os"                         # os/Makefile, a /BIN command (make without XISA=1)
CDIR = "software/compiler/c"
# name, source, flags, the host build in os/build, where it goes on the disk
PROGS = [(n, CDIR + "/target/%s.c" % n, PFLAGS, "cc/" + n, "/LIB/CC/CC%d" % (i + 1)) for i, n in enumerate(run.PASSN)]
PROGS += [("asm", "os/commands/asm.c", BFLAGS, "bin/asm", "/BIN/ASM"),
          ("cc", "os/commands/cc.c", BFLAGS, "bin/cc", "/BIN/CC")]


def sources():
    """the repository files the eleven compiles read (their #includes), as paths relative to the root"""
    files = set(p[1] for p in PROGS)
    c = os.path.join(ROOT, CDIR)
    for f in os.listdir(c):
        if f.endswith((".c", ".h")) and f.startswith(("cc", "p", "io", "target")): files.add(CDIR + "/" + f)
    for f in os.listdir(os.path.join(c, "ylim")): files.add(CDIR + "/ylim/" + f)
    for f in os.listdir(OS):
        if f.startswith("lib_") and f.endswith(".c"): files.add("os/" + f)
    files.add("os/asm_optab.c")
    for f in files:
        if len(os.path.basename(f)) > 12: sys.exit("selfhost: %s: a name over P8XFS's 12 characters" % f)
    return sorted(files)


def make_disk(img, progs, native=None):
    """os/disk.img + the sources under /R + /OUT/NAME for each program; native: {name: program bytes} to install"""
    shutil.copy(os.path.join(OS, "disk.img"), img)
    dirs = {"/R"}
    run.sh(FS + ["mkdir", img, "/R"])
    for f in sources():
        parts = f.split("/")
        for i in range(1, len(parts)):
            d = "/R/" + "/".join(parts[:i])
            if d not in dirs: run.sh(FS + ["mkdir", img, d]); dirs.add(d)
        run.sh(FS + ["put", img, os.path.join(ROOT, f), "--name", "/R/" + f])
    run.sh(FS + ["mkdir", img, "/OUT"])
    for p in progs: run.sh(FS + ["mkdir", img, "/OUT/" + p[0].upper()])
    for name, data in (native or {}).items():
        p = [q for q in PROGS if q[0] == name][0]
        f = os.path.join(BUILD, "install.tmp"); open(f, "wb").write(data)
        run.sh(FS + ["put", img, f, "--name", p[4], "--load", "0x5000", "--exec", "0x5000", "--replace"])
        os.remove(f)


def script(progs):
    lines = ["O"]
    for p in progs:
        N = p[0].upper()
        lines += ["cd /R/" + os.path.dirname(p[1]),
                  "cc %s -o /OUT/%s/%s.ASM %s" % (os.path.basename(p[1]), N, N, p[2]),
                  "cd /",
                  "asm /OUT/%s/%s.ASM" % (N, N)]
    return "\n".join(lines + ["exit", "0", ""])


def host(p):
    return (open(os.path.join(OS, "build", p[3] + ".asm"), encoding="latin1").read(),
            open(os.path.join(OS, "build", p[3] + ".bin"), "rb").read())


def hm(n):
    s = n * CPI / 1e6
    return "%dh %02dm" % (s // 3600, s % 3600 // 60) if s >= 3600 else "%dm %02ds" % (s // 60, s % 60)


def check(img, p):
    """the host's comparison of program p's results on an image: (failures, assembly bytes, program bytes)"""
    want_asm, want_bin = host(p)
    N = p[0].upper(); D = "/OUT/%s/%s" % (N, N)
    fails = []
    ga = run.get(img, D + ".ASM")
    if ga is None: fails.append("no " + D + ".ASM")
    elif run.corpus.normalize(ga.decode("latin1")) != run.corpus.normalize(want_asm):
        fails.append("assembly differs (%d / %d bytes)" % (len(ga), len(want_asm)))
    gb = run.get(img, D)
    if gb is None: fails.append("no program file " + D)
    elif gb != want_bin: fails.append("program file differs (%d / %d bytes)" % (len(gb), len(want_bin)))
    return fails, ga or b"", gb


def session(img, progs, tag, verbose):
    """the emulator on the image with the script; its stdout and stderr, or None if the session did not end"""
    if tag == "int": cmd = [run.EMUS["int"], "-x", "-m", "-c", img, "-l", "400000000000", "-S"]
    else: cmd = [run.EMUS["uc"], "-x", "-m", "-c", img, "-l", "4000000000000", "-E", run.MON_EXIT]
    r = subprocess.run(cmd, input=script(progs).encode(), capture_output=True)
    out = r.stdout.decode("latin1"); err = r.stderr.decode("latin1")
    if verbose: print(out[out.find("BOOT FROM CF"):])
    if "\nbye" not in out:
        print("%s: the session did not end (no bye): %s\n%s" % (tag, out[-1500:], err[-800:])); return None, None
    return out, err


def stage_uc(progs, verbose):
    """stage 1 on the microcode emulator: the same checks; the session's instructions, steps and clocks"""
    img = os.path.join(BUILD, "stage1uc.img")
    make_disk(img, progs)
    out, err = session(img, progs, "uc", verbose)
    if out is None: return 1
    bad = 0
    for p in progs:
        fails, ga, gb = check(img, p)
        bad += len(fails) > 0
        print("  uc %-8s %s" % (p[0], "; ".join(fails) or "identical (%d bytes)" % len(gb)))
    m = re.search(r"after (\d+) instructions, (\d+) steps, (\d+) clocks", err)
    if m:
        i, s, c = (int(x) for x in m.groups())
        print("uc   the session: %d instructions, %d steps (%.1f an instruction), %d clocks (%.1f): %s at 1 MHz" % (
            i, s, s / i, c, c / i, hm(c / CPI)))
    return bad


def stage(k, progs, native, verbose):
    """one session: every program compiled and assembled; the checks; (failures, {name: program bytes}, instructions)"""
    img = os.path.join(BUILD, "stage%d.img" % k)
    make_disk(img, progs, native)
    out, err = session(img, progs, "int", verbose)
    bad = 0; got = {}
    if out is None: return 1, got, 0
    segs = [(int(m.group(1)), m.group(3)) for m in re.finditer(
        r"program \d+: (\d+) instructions(, stack \$[0-9A-F]+ down to \$([0-9A-F]+))?", err)]
    if len(segs) != 11 * len(progs):
        print("stage %d: expected %d programs started, the watch saw %d:\n%s\n%s" % (
            k, 11 * len(progs), len(segs), out[-2000:], err[-1500:]))
        return 1, got, 0
    print("stage %d%s  %11s %11s %11s   %-18s %s" % (k, " (native CC1..CC9, CC, ASM)" if k == 2 else " (host-built tools)",
                                                  "compile", "assemble", "both", "at 1 MHz", "result"))
    tot = [0, 0]; low = {}
    for i, p in enumerate(progs):
        st = segs[11 * i: 11 * i + 11]
        comp = sum(s[0] for s in st[:10]); a = st[10][0]; tot[0] += comp; tot[1] += a
        for j in range(9):
            if st[1 + j][1]:
                n = run.PASSN[j]; low[n] = min(low.get(n, 0x10000), int(st[1 + j][1], 16))
        fails, ga, gb = check(img, p)
        if not fails: got[p[0]] = gb
        bad += len(fails) > 0
        print("  %-8s %-9s %11d %11d %11d   %-18s %s" % (p[0], "(%dK)" % ((len(ga) + 512) // 1024), comp, a,
                                                        comp + a, hm(comp + a),
                                                        "; ".join(fails) or "identical (%d bytes)" % len(gb)))
    print("  %-18s %11d %11d %11d   %s" % ("all", tot[0], tot[1], sum(tot), hm(sum(tot))))
    for n in run.PASSN:
        if n not in low: continue
        room = low[n] - run.bss_end(n) - 1
        if room < 0: bad += 1; print("  cc%d %s: the stack ran into its data (%d bytes)" % (run.PASSN.index(n) + 1, n, room))
    print("  the passes' least room between stack and data: " + ", ".join(
        "cc%d %d" % (run.PASSN.index(n) + 1, low[n] - run.bss_end(n) - 1) for n in run.PASSN if n in low))
    return bad, got, sum(tot)


def main():
    av = sys.argv[1:]
    verbose = "-v" in av
    only = None
    if "--stage" in av: only = int(av[av.index("--stage") + 1]); del av[av.index("--stage"):av.index("--stage") + 2]
    names = [a for a in av if not a.startswith("-")]
    progs = [p for p in PROGS if not names or p[0] in names]
    if not progs: sys.exit("selfhost: no such program: " + " ".join(names))
    shutil.rmtree(BUILD, ignore_errors=True); os.makedirs(BUILD)
    run.sh(["make", "-s", "-C", OS])                 # the disk: the OS, /BIN (CC, ASM), /LIB, the passes (host builds)
    run.BUILD = BUILD
    bad = 0; native = {}; total = 0
    if only in (None, 1):
        b, native, n = stage(1, progs, None, verbose); bad += b; total += n
    if only in (None, 2):
        if only == 2: native = {p[0]: host(p)[1] for p in progs}
        if not bad:
            b, got, n = stage(2, progs, native, verbose); bad += b; total += n
            same = [p for p in progs if p[0] in got and got[p[0]] == native.get(p[0])]
            if len(same) == len(progs) and only is None:
                print("fixed point: the natively built toolchain rebuilt itself byte for byte (%d programs)" % len(progs))
    if "--uc" in av and only in (None, 1):
        print("stage 1 on the microcode emulator (%s)" % " ".join(p[0] for p in progs))
        bad += stage_uc(progs, verbose)
    if only is None and total: print("both stages: %d instructions, %s at 1 MHz (%.1f clocks an instruction)" % (
        total, hm(total), CPI))
    print("selfhost: %d problems" % bad)
    if "--keep" not in av and not bad: shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
