#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""/BIN/DISASM (os/commands/disasm.c) against the assembler: disassemble, reassemble, compare (2026-09-29).

  run.py [-v] [--only SUBSTR] [--quick]

1. tools/gen_y1_distab.py --check: os/dis_optab.c is what software/assembler/yacc1.def gives (the generator itself
   proves the table on every register/port combination and checks the opcodes against software/opcodes.h).
2. disasm.c is built for the Mac (host_disasm.c + host_sys.c: the YACC1's integer types, the few syscalls emulated),
   so the code the machine runs is the code tested here.
3. The round trip, on
     - every source of tests/asm's corpus (the y1cc corpus plain and --xisa, the firmware, the hand-written tests,
       y1os.asm, tests/asm/src), assembled by RC/asm and flattened to a program file (lowest to highest address,
       gaps as zeros, load = the lowest address) - --quick: the hand-written sources only;
     - every program the OS build makes: /BIN (os/build/bin, asm.asm's build), the compiler passes, the OS image;
     - the ROM (firmware/rom/shipped/rom.bin) in memory at $E000 with -m, and the monitor's half alone;
     - random bytes (three 60K files) and every opcode followed by every operand byte (four files): the DB paths;
   each disassembled twice by the host build: `disasm -s FILE` must reassemble (RC/asm, -h) to the same bytes, and the
   listing (`disasm FILE`) must be the -s lines with the address and the bytes in front, both true to the file.
4. START and COUNT: ranges of a few programs and of the ROM: the lines start at START, every instruction starts in
   the range and the next one would not, and the listing's bytes are the file's.
Exit 1 on any difference. Work files in tests/disasm/build/ (git-ignored). tests/os/disasm.session runs the command
under Y1/OS on both emulators, with /BIN/ASM reassembling its -s output there.
"""
import os, sys, re, glob, random, shutil, subprocess, importlib.util, concurrent.futures

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(HERE, "build")
RCASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
HOST = os.path.join(BUILD, "disasm")
ROM = os.path.join(ROOT, "firmware/rom/shipped/rom.bin")


def sh(cmd, cwd=None, env=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace", env=env)
    return r.returncode, r.stdout, r.stderr


def asm_module():
    """tests/asm/run.py, for its corpus (y1cc_items, hand_items), built into our own build directory"""
    spec = importlib.util.spec_from_file_location("asmrun", os.path.join(ROOT, "tests/asm/run.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.BUILD = os.path.join(BUILD, "corpus")
    return m


def build_host():
    rc, out, err = sh([sys.executable, os.path.join(ROOT, "tools/gen_y1_distab.py"), "--check"])
    print(out.strip() or err.strip())
    if rc: sys.exit(1)
    rc, out, err = sh(["cc", "-O1", "-funsigned-char", "-fno-builtin", "-fno-common", "-Wall", "-Wextra",
                       "-Wno-keyword-macro", "-o", HOST, os.path.join(HERE, "host_disasm.c"), os.path.join(HERE, "host_sys.c")])
    if rc or err.strip(): sys.exit("host build of os/commands/disasm.c:\n" + out + err)


def hexmem(path):
    mem = {}
    for line in open(path):
        if not line.startswith(":"): continue
        n, a, t = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
        if t: continue
        for i, x in enumerate(bytes.fromhex(line[9:9 + 2 * n])): mem[a + i] = x
    return mem


def reassemble(src_text, d, name):
    """RC/asm -h on the text: the bytes {addr: byte}, or an error string"""
    os.makedirs(d, exist_ok=True)
    shutil.copy(DEF, d)
    open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    open(os.path.join(d, name + ".asm"), "w").write(src_text)
    rc, out, _ = sh([RCASM, name, "-d=yacc1"], cwd=d)
    if "\n0 Errors" not in out:
        return "RC/asm: " + " | ".join(l for l in out.splitlines() if "ERR" in l)[:300]
    return hexmem(os.path.join(d, name + ".img"))


def disasm(args, load=None, memfile=None):
    """the host build; a file argument (a path) is passed as its bare name from its directory: Y1/OS command
    tails are short (disasm reads 63 characters of a name)"""
    env = dict(os.environ)
    if load is not None: env["Y1_LOAD"] = "%X" % load
    if memfile: env["Y1_MEM"] = memfile
    cwd = None
    for i, a in enumerate(args):
        if os.sep in a: cwd = os.path.dirname(a); args = args[:i] + [os.path.basename(a)] + args[i + 1:]
    return sh([HOST] + args, cwd=cwd, env=env)


LINE = re.compile(r"^([0-9A-F]{4})  ((?:[0-9A-F]{2} ){1,3})( *) (\S.*)$")


def check_listing(lst, src, data, base, first=None):
    """The listing against the -s output and the bytes: (instructions, error or None). data[i] is the byte at base+i."""
    ls = lst.splitlines(); ss = src.splitlines()
    if not ss or not re.match(r"^        ORG 0?[0-9A-F]{4}H$", ss[0]): return 0, "-s: no ORG line first"
    if len(ls) != len(ss) - 1: return 0, "listing %d lines, -s %d" % (len(ls), len(ss) - 1)
    at = first if first is not None else base
    if int(ss[0][12:-1], 16) != at: return 0, "-s: ORG %s, expected %04X" % (ss[0][12:], at)
    for l, s in zip(ls, ss[1:]):
        m = LINE.match(l)
        if not m or len(m.group(2)) + len(m.group(3)) != 9: return 0, "listing line %r" % l
        if s != "        " + m.group(4): return 0, "listing %r against -s %r" % (l, s)
        a = int(m.group(1), 16); bs = bytes.fromhex(m.group(2))
        if a != at: return 0, "line %r: address %04X expected" % (l, at)
        if bs != bytes(data[a - base:a - base + len(bs)]): return 0, "line %r: bytes are not the file's" % l
        at += len(bs)
    return len(ls), None


def round_trip(job):
    """(title, program file or ('mem', image, at), load, work dir name) -> (title, status, detail)"""
    title, what, base, wname = job
    d = os.path.join(BUILD, "rt", wname)
    if isinstance(what, tuple):                  # memory: -m over the image at base
        _, path, start, count = what
        data = open(path, "rb").read()
        args = ["-m", "%X" % start, "%X" % count]
        rc1, lst, e1 = disasm(args, memfile="%s@%X" % (path, base))
        rc2, src, e2 = disasm(["-s"] + args, memfile="%s@%X" % (path, base))
        want = data[start - base:]
    else:
        data = open(what, "rb").read()
        rc1, lst, e1 = disasm([what], load=base)
        rc2, src, e2 = disasm(["-s", what], load=base)
        want = data[:0x10000 - base]
        start = base
    if rc1 or rc2 or e1 or e2: return title, "FAIL", "disasm: %s %s" % (e1.strip()[:200], e2.strip()[:200])
    n, err = check_listing(lst, src, data, base, start)
    if err: return title, "FAIL", err
    got = reassemble(src, d, "r")
    if isinstance(got, str): return title, "FAIL", got
    if not got: return title, "FAIL", "nothing reassembled"
    lo, hi = min(got), max(got)
    if lo != start: return title, "FAIL", "reassembled from %04X, not %04X" % (lo, start)
    if len(got) != hi - lo + 1: return title, "FAIL", "the reassembled bytes have a gap"
    back = bytes(got[a] for a in range(lo, hi + 1))
    if isinstance(what, tuple):
        if back != want[:len(back)] or len(back) < what[3]: return title, "FAIL", "reassembled bytes differ from memory"
    elif back != want: return title, "FAIL", "reassembled %d bytes differ from the file's %d" % (len(back), len(want))
    shutil.rmtree(d, ignore_errors=True)
    return title, "ok", "%d lines, %d bytes" % (n, len(back))


def corpus_jobs(quick, only):
    """tests/asm's corpus through RC/asm into program files: [(title, path, load, work name)]"""
    m = asm_module()
    os.makedirs(m.BUILD, exist_ok=True)
    items = ([] if quick else m.y1cc_items(only)) + m.hand_items(only)
    for d in sorted({d for _, _, d in items}):
        shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")

    def one(it):
        name, short, d = it
        rc, out, _ = sh([RCASM, short, "-d=yacc1"], cwd=d)
        if "\n0 Errors" not in out: return None          # the sources both assemblers refuse
        mem = hexmem(os.path.join(d, short + ".img"))
        if not mem or max(mem) > 0xFFFF: return None
        lo, hi = min(mem), max(mem)
        path = os.path.join(d, short + ".prog")
        open(path, "wb").write(bytes(mem.get(a, 0) for a in range(lo, hi + 1)))
        return ("asm:" + name, path, lo, "c_" + short + "_" + os.path.basename(d))
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        return [j for j in ex.map(one, items) if j], len(items)


def program_jobs():
    r = subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], capture_output=True, text=True)
    if r.returncode: sys.exit("os build failed:\n" + r.stdout[-800:] + r.stderr[-800:])
    jobs = []
    for p in sorted(glob.glob(os.path.join(ROOT, "os/build/bin/*.bin")) + [os.path.join(ROOT, "os/build/asma/asm.bin")] +
                    sorted(glob.glob(os.path.join(ROOT, "os/build/cc/*.bin")))):
        rel = os.path.relpath(p, os.path.join(ROOT, "os/build"))
        jobs.append(("bin:" + rel, p, 0x5000, "b_" + rel.replace("/", "_")))
    jobs.append(("os:y1os.bin", os.path.join(ROOT, "os/build/y1os.bin"), 0x1000, "os"))
    jobs.append(("rom: -m E000 2000", ("mem", ROM, 0xE000, 0x2000), 0xE000, "rom"))
    jobs.append(("rom: -m F000 1000 (the monitor)", ("mem", ROM, 0xF000, 0x1000), 0xE000, "mon"))
    return jobs


def synthetic_jobs():
    d = os.path.join(BUILD, "syn"); os.makedirs(d, exist_ok=True)
    jobs = []
    for seed in range(3):
        p = os.path.join(d, "random%d.bin" % seed)
        rng = random.Random(seed)
        open(p, "wb").write(bytes(rng.randrange(256) for _ in range(60000)))
        jobs.append(("random bytes, seed %d" % seed, p, 0x1000 + 0x100 * seed, "syn%d" % seed))
    for q in range(4):                           # every opcode followed by every second byte (and a third, 5A)
        p = os.path.join(d, "pairs%d.bin" % q)
        open(p, "wb").write(bytes(x for op in range(64 * q, 64 * q + 64) for b in range(256) for x in (op, b, 0x5A)))
        jobs.append(("every opcode + operand byte, opcodes %02X-%02X" % (64 * q, 64 * q + 63), p, 0, "pairs%d" % q))
    return jobs


def range_checks():
    """START/COUNT: the lines start at START, each instruction starts in the range, the next one would not"""
    fails = []
    rnd = random.Random(7)
    progs = [os.path.join(ROOT, "os/build/bin/hello.bin"), os.path.join(ROOT, "os/build/bin/disasm.bin")]
    n = 0
    for p in progs:
        data = open(p, "rb").read()
        for _ in range(40):
            s = 0x5000 + rnd.randrange(len(data)); c = rnd.randrange(1, 40)
            for mode in (["%X" % s, "%X" % c], ["%X" % s]):
                rc, lst, err = disasm([p] + mode, load=0x5000)
                rc2, src, _ = disasm(["-s", p] + mode, load=0x5000)
                k, e = check_listing(lst, src, data, 0x5000, s)
                if rc or err or e: fails.append("%s %s: %s %s" % (os.path.basename(p), mode, err.strip(), e)); continue
                addrs = [int(l[:4], 16) for l in lst.splitlines()]
                stop = s + c - 1 if len(mode) == 2 else 0x5000 + len(data) - 1
                lastlen = len(lst.splitlines()[-1][6:15].split())
                if addrs[0] != s or addrs[-1] > stop or (addrs[-1] + lastlen <= stop and addrs[-1] + lastlen < 0x5000 + len(data)):
                    fails.append("%s %s: lines %04X..%04X" % (os.path.basename(p), mode, addrs[0], addrs[-1]))
                n += 1
    for s, c in ((0xFFF0, 0x40), (0xFFFE, 1), (0xE000, 1), (0xF800, 0x33)):     # memory, up to $FFFF and no further
        data = open(ROM, "rb").read()
        rc, lst, err = disasm(["-m", "%X" % s, "%X" % c], memfile="%s@E000" % ROM)
        rc2, src, _ = disasm(["-s", "-m", "%X" % s, "%X" % c], memfile="%s@E000" % ROM)
        k, e = check_listing(lst, src, data, 0xE000, s)
        addrs = [int(l[:4], 16) for l in lst.splitlines()]
        if rc or err or e or addrs[0] != s or addrs[-1] > min(0xFFFF, s + c - 1):
            fails.append("-m %X %X: %s %s" % (s, c, err.strip(), e))
        n += 1
    for args, want in ((["-m", "zz"], "disasm: bad address: zz"), (["NOFILE"], "disasm: not found: NOFILE"),
                       (["-m", "10", "12345"], "disasm: bad count: 12345"),
                       ([progs[0], "4000"], "disasm: START is not in the file: 4000")):
        rc, out, err = disasm(args, load=0x5000)
        if err.strip() != want or out: fails.append("%s: %r %r" % (args, out, err))
        n += 1
    rc, out, err = disasm([])
    if not out.startswith("usage: disasm") or err: fails.append("no arguments: %r" % out)
    return n, fails


def main():
    verbose = "-v" in sys.argv
    quick = "--quick" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1].lower() if "--only" in sys.argv else ""
    os.makedirs(BUILD, exist_ok=True)
    build_host()
    cj, ncorpus = corpus_jobs(quick, only)
    jobs = cj + program_jobs() + synthetic_jobs()
    counts = {}; fails = []; lines = 0
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for title, st, det in ex.map(round_trip, jobs):
            counts[st] = counts.get(st, 0) + 1
            if st == "ok": lines += int(det.split()[0])
            if st == "FAIL": fails.append((title, det))
            if verbose or st == "FAIL": print("%-50s %-5s %s" % (title, st, det))
    ncj = len(cj)
    print("tests/disasm: round trip (disasm -s, RC/asm, the same bytes; the listing checked against it): %d of the "
          "tests/asm corpus's %d sources (the others refused by RC/asm), %d programs of the OS build, the ROM twice, "
          "7 synthetic: %d ok, %d FAILED; %d instructions and DBs" % (ncj, ncorpus, len(jobs) - ncj - 9, counts.get("ok", 0),
                                                                    counts.get("FAIL", 0), lines))
    n, rf = range_checks()
    for f in rf: print("range FAIL", f)
    print("tests/disasm: START/COUNT and errors: %d runs, %d FAILED" % (n, len(rf)))
    sys.exit(1 if fails or rf else 0)


if __name__ == "__main__":
    main()
