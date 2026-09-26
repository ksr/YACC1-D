#!/usr/bin/env python3
"""The native assembler /BIN/ASM (os/commands/asm.c) against the host assembler RC/asm (software/assembler), 2026-09-25.

  run.py [-v] [--only SUBSTR] [--no-native] [--uc] [--target]

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
4. asm.asm (os/commands-asm, the assembler in YACC1 assembly, 2026-09-26) under Y1/OS on the instruction-level
   emulator, on the whole corpus (unless --no-native): disks built here with the OS and its build as /BIN/ASM, the
   sources in directories of 18, 72 to a session, the sessions in parallel; each source assembled with -h and to a
   program file, and the console output (the messages, the summary) and the file written (bytes, load, exec) must
   be what the host build of asm.c gives for the same command line. Where asm.c's symbol table is full (y1cc.c's
   own compile), asm.asm's bigger table gets further: it must refuse the source too. The instruction counts of the
   emulator's program watch are summed. --uc: also the sources of UC_SET on the microcode emulator (~2 minutes).
5. --target: the Y1/OS runs on both emulators (tests/asm/target.py): a disk with sources, `asm` run under the OS,
   the results fetched back and compared with RC/asm's.
Exit 1 on any difference. The work files are in tests/asm/build/ (git-ignored).
"""
import os, sys, re, glob, shutil, subprocess, concurrent.futures, types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(HERE, "build")
RCASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
Y1CC = os.path.join(ROOT, "software/compiler/y1cc.py")
NATIVE = os.path.join(BUILD, "asm")
sys.path.insert(0, os.path.join(ROOT, "tests/compiler"))
import corpus                                    # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tools"))
import p8xfs as P                                # noqa: E402  (disk images built in memory)
EMUS = {"int": os.path.join(ROOT, "software/emulator/emulator"), "uc": os.path.join(ROOT, "software/ucemu/y1ucemu")}
ASMA = os.path.join(ROOT, "os/build/asma/asm.bin")       # asm.asm, /BIN/ASM (os/Makefile)
OSBIN = os.path.join(ROOT, "os/build/y1os.bin")
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read(),
                     re.M).group(1).upper()
UC_SET = ["hello", "quirks", "isa", "err_undef", "err_expr", "err_dup", "romdiag", "monitor_monitor"]   # --uc


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


def host_ref(name, d, args, tag):
    """asm.c built for the Mac (NATIVE) with the command line the Y1/OS run gets, in d: (console text as the machine
    shows it: the error lines and the summary in order, the created file's bytes, load, exec) - what asm.asm must
    give. The host build writes the messages to stderr and the summary to stdout; there is never both."""
    out = name + "." + tag
    if os.path.exists(os.path.join(d, out)): os.remove(os.path.join(d, out))
    rc, so, se = sh([NATIVE] + args + [name + ".asm", out], cwd=d)
    m = re.search(r"host_sys: created \S+ load ([0-9A-F]{4}) exec ([0-9A-F]{4})", se)
    con = "".join(l + "\n" for l in se.splitlines() if not l.startswith("host_sys: ")) + so
    f = os.path.join(d, out)
    data = open(f, "rb").read() if os.path.exists(f) else None
    return con, (data, int(m.group(1), 16), int(m.group(2), 16)) if data is not None and m else None


def mkdisk(path, batches, extra_secs):
    """A fresh volume: the OS, /BIN/ASM = asm.asm, and per batch a directory /Dk with its sources and INCLUDE files"""
    need = 64 + extra_secs
    for files in batches:
        for f in files: need += 2 * (os.path.getsize(f) // 512 + 2)
    img = bytearray(max(need, P.DATA_V2 + 64) * P.SEC)
    b = P.sec(img, P.BOOT_LBA); b[0:2] = b"P8"; b[2] = 2; b[3] = 0
    import struct; struct.pack_into("<H", img, 4, P.DATA_V2)
    P.init_dir_extent(img, P.ROOT_LBA, P.ROOT_SECS, P.ROOT_LBA, P.ROOT_SECS)
    osimg = open(OSBIN, "rb").read()
    n = (len(osimg) + 511) // 512
    for i in range(n): P.sec(img, P.OS_LBA + i)[:] = osimg[i * 512:(i + 1) * 512].ljust(512, b"\0")
    img[3] = n

    def mkdir(path):
        parent, leaf = P.split_path(path)
        pd = P.resolve_dir(img, parent)
        lba = P.alloc(img, P.SUBDIR_SECS)
        P.init_dir_extent(img, lba, P.SUBDIR_SECS, pd[0], pd[1])
        P.add_entry(img, pd[0], pd[1], leaf, lba, P.SUBDIR_SECS * P.SEC, 0, 0, P.F_DIR)
    mkdir("/BIN")
    P.put_file(img, ASMA, "/BIN/ASM", 0x5000, 0x5000)
    for k, files in enumerate(batches):
        mkdir("/D%d" % k)
        for f in files: P.put_file(img, f, "/D%d/%s" % (k, os.path.basename(f)), 0, 0)
    P.write_img(path, img)


def native_batch(job):
    """One disk, one emulator session: every item of the batches assembled with -h and to a program file by asm.asm;
    returns [(item name, status, detail)] and the per-item instructions (-S, int only)."""
    k, emu, batches, work = job
    img = os.path.join(work, "n%d.%s.img" % (k, emu))
    files = []
    for b in batches:
        fs = []
        for name, short, d in b:
            fs.append(os.path.join(d, short + ".asm"))
            if short.startswith("h"): fs += sorted(glob.glob(os.path.join(d, "*.inc")))
        files.append(sorted(set(fs)))
    mkdisk(img, files, sum(len(b) for b in batches) * 8)
    cmds = []
    lines = ["O"]
    for j, b in enumerate(batches):
        lines.append("cd /D%d" % j)
        for name, short, d in b:
            for args, tag in ((["-h"], "xh"), ([], "xp")):
                lines.append("asm %s%s.asm %s.%s" % ("-h " if args else "", short, short, tag))
                cmds.append((name, short, d, args, tag, j))
    lines += ["exit", "0", ""]
    size = sum(os.path.getsize(os.path.join(d, s + ".asm")) for b in batches for _, s, d in b)
    if emu == "int": cmd = [EMUS["int"], "-x", "-m", "-c", img, "-l", str(40000000 + 1500 * size), "-S"]
    else: cmd = [EMUS["uc"], "-x", "-m", "-c", img, "-l", str(600000000 + 30000 * size), "-E", MON_EXIT]
    r = subprocess.run(cmd, input="\n".join(lines).encode(), capture_output=True)
    out = r.stdout.decode("latin1"); err = r.stderr.decode("latin1")
    res = []
    if "\nbye" not in out:
        return [(c[0], "FAIL", "%s: the session did not end: %s" % (emu, (out[-300:] + err[-300:]).replace("\n", " | ")))
                for c in cmds[::2]], {}
    body = out[out.find("BOOT FROM CF"):out.find("\nbye")].replace("\r", "")
    # each command's output follows its prompt (the microcode emulator also shows the command, as the machine echoes it)
    parts = re.split(r"/D\d+> \n" if emu == "int" else r"/D\d+> [^\n]*\n\n", body)[1:]
    if parts: parts[-1] = re.sub(r"/D\d+> (exit)?\n?$", "", parts[-1])     # the prompt before `exit`
    # the prompts: one after each `cd` (empty output) and one after each command
    seq = []
    idx = 0
    for j, b in enumerate(batches):
        idx += 1 if j else 0                              # the prompt after `cd /Dj` (the first cd is at "/> ")
        for _ in range(2 * len(b)):
            seq.append(parts[idx] if idx < len(parts) else None); idx += 1
    counts = [int(m.group(1)) for m in re.finditer(r"program \d+: (\d+) instructions", err)]
    tree, _ = tree_files(img)
    ins = {}
    for i, (name, short, d, args, tag, j) in enumerate(cmds):
        con, f = host_ref(short, d, args, tag)
        got = seq[i]
        fails = []
        if got is None: fails.append("no output")
        elif "symbol table full" in con:              # asm.c's capacity: asm.asm's table is bigger, it must refuse the
            if gf_absent(tree, j, short, tag) and re.search(r"^asm: \d+ errors?\n$", got, re.M):   # source (y1cc.c)
                res.append((name, "full", "asm.c's symbol table is full; asm.asm refuses it too: " + got.splitlines()[0]))
                continue
            fails.append("%s: asm.c's symbol table is full, asm.asm: %r" % (tag, got[:160]))
        elif got != con: fails.append("%s output %r, asm.c: %r" % (tag, got[:160], con[:160]))
        gf = tree.get("/D%d/%s.%s" % (j, short, tag))
        if f is None and gf is not None: fails.append("%s: a file where asm.c leaves none" % tag)
        if f is not None and gf != f:
            fails.append("%s: file %s" % (tag, "missing" if gf is None else "%d bytes load %04X exec %04X, asm.c %d %04X %04X"
                                          % (len(gf[0]), gf[1], gf[2], len(f[0]), f[1], f[2])))
        if emu == "int" and i < len(counts): ins[(name, tag)] = counts[i]
        res.append((name, "FAIL" if fails else "ok", "; ".join(fails)))
    merged = {}
    for name, st, det in res:
        if name not in merged or st == "FAIL" or (st == "full" and merged[name][0] == "ok"): merged[name] = (st, det)
    if emu == "int" and len(counts) != len(cmds): merged[cmds[0][0]] = ("FAIL", "the program watch saw %d runs, not %d" % (len(counts), len(cmds)))
    return [(n,) + v for n, v in merged.items()], ins


def gf_absent(tree, j, short, tag):
    return "/D%d/%s.%s" % (j, short, tag) not in tree


def tree_files(img_path):
    """{path: (bytes, load, exec)} of every file on an image"""
    img = P.read_img(img_path)
    files = {}
    todo = [(P.ROOT_LBA, P.ROOT_SECS, "")]
    while todo:
        dlba, dsecs, path = todo.pop()
        for e in P.iter_dir(img, dlba, dsecs):
            nm = e["name"].decode("latin1").rstrip()
            if e["flags"] not in (P.F_FILE, P.F_DIR) or nm in (".", ".."): continue
            if e["flags"] == P.F_DIR: todo.append((e["start"], P.dir_secs(e), path + "/" + nm))
            else: files[path + "/" + nm] = (bytes(img[e["start"] * P.SEC: e["start"] * P.SEC + e["length"]]), e["load"], e["exec"])
    return files, 0


def native(items, emu, verbose):
    """asm.asm (/BIN/ASM) under Y1/OS on emulator emu over items: batches of 18 (a directory holds 62 entries), a disk
    of up to 4 batches per session, the sessions in parallel"""
    work = os.path.join(BUILD, "native"); os.makedirs(work, exist_ok=True)
    per_disk = 72 if emu == "int" else 18
    jobs = []
    order = sorted(items, key=lambda it: -os.path.getsize(os.path.join(it[2], it[1] + ".asm")))
    for k in range(0, len(order), per_disk):
        chunk = order[k:k + per_disk]
        jobs.append((len(jobs), emu, [chunk[i:i + 18] for i in range(0, len(chunk), 18)], work))
    results, ins = [], {}
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for r, n in ex.map(native_batch, jobs):
            results += r; ins.update(n)
    return results, ins


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
    if "--no-native" not in sys.argv:                 # asm.asm, the installed /BIN/ASM, on the same corpus
        sys.stdout.flush()
        r = subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "build/asma/asm.bin", "build/y1os.bin"],
                           capture_output=True, text=True)
        if r.returncode: sys.exit("os build failed:\n" + r.stdout[-800:] + r.stderr[-800:])
        for emu in ["int"] + (["uc"] if "--uc" in sys.argv else []):
            its = items if emu == "int" else [it for it in items if any(u in it[0] for u in UC_SET)]
            res, ins = native(its, emu, verbose)
            c = {}
            for name, st, det in res:
                c[st] = c.get(st, 0) + 1
                if st == "FAIL": fails.append((name, det))
                if verbose or st == "FAIL": print("%-44s %-7s %s" % (name, st + " " + emu, det[:300]))
            print("tests/asm: asm.asm under Y1/OS (%s emulator): %d sources, %d with the same messages and files as "
                  "asm.c, %d refused by both where asm.c's symbol table is full, %d FAILED%s" % (
                      emu, len(res), c.get("ok", 0), c.get("full", 0), c.get("FAIL", 0),
                                          (", %d instructions" % sum(ins.values())) if ins else ""))
    if "--target" in sys.argv:
        sys.stdout.flush()
        rc = subprocess.run([sys.executable, os.path.join(HERE, "target.py")]).returncode
        if rc: fails.append(("target", "the emulator runs failed"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
