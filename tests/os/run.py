#!/usr/bin/env python3
"""Y1/OS tests: build os/disk.img, boot it on both emulators with a scripted console session, compare transcripts.

  run.py [name ...] [--keep] [--update]
    name       run only these sessions
    --update   rewrite the expected transcripts from this run (after checking them by eye)
    --keep     leave the per-run disk images in tests/os/build/
  run.py --cuts [N]   the reset-safety proof of pack (instruction-level emulator only, ~N x 0.3 s): N cuts, see cuts()

Sessions live in tests/os/*.session (one console line per line, sent after the monitor's O command boots the
OS; a Ctrl-D byte ends a program's console input). The expected transcript is NAME.int.out for the instruction-level
emulator and NAME.uc.out for the microcode emulator (the latter shows the monitor's input echo, as the machine
does). The comparison starts at "BOOT FROM CF" and ends after the OS says "bye" and the monitor prompt returns.

Every run boots a fresh COPY of os/disk.img (tests/os/build/NAME.TAG.img): the emulators write the CF image in place
(software/cfmodel.h), and since 2026-09-23 the OS writes files. After a session listed in HOST the copy is checked
from the host side with tools/p8xfs.py (fsck, ls, get + compare), which proves the OS's writes are what the host
tool would have written. The per-emulator step limits (LIMITS) are a budget: a session must say "bye" inside it. After
`exit` the script sends the monitor's `0` command, which ends the run (since 2026-09-25; before, the monitor spun on
an empty console until the limit).
"""
import os, sys, glob, subprocess, shutil, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OS = os.path.join(ROOT, "os")
FS = os.path.join(ROOT, "tools/p8xfs.py")
BUILD = os.path.join(HERE, "build")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import p8xfs as P                                # the format's helpers, for the checks that walk the image
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator")),
        ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"))]
LIMITS = {"basic": (8000000, 120000000),         # instructions (int) / microcode steps (uc): the session must finish
          "api": (12000000, 200000000),          # inside them; a program-heavy session needs more (2026-09-23)
          "write": (14000000, 220000000),
          "wave1": (8000000, 110000000),         # 4.5M / 62M needed (2026-09-23); 4.9M / 73M with --os output
          "wave2": (9000000, 130000000),         # 5.7M / 79M needed; 5.9M / 49M with --os
          "redirect": (4000000, 60000000),       # 1.9M / 27M needed (2026-09-23)
          "pipe": (13000000, 180000000),         # 9.8M / 136M needed: every byte crosses CONOUT, then CONIN
          "pack": (120000000, 1600000000),       # 2026-09-25: the C OS needs ~70M (cmp of two 56K files alone ~45M)
          "badhandle": (6000000, 90000000),
          "big": (600000000, 9000000000)}        # 2026-09-25: 72K + 144K written, read back 5 times, copied, appended; + a 72K file in odd pieces, READN twice (asm OS 117M / 1.8G, the C OS 324M / 5.6G)      # 2026-09-23: writes and reads through bad handles, empty loads         # <= 30M / <= 420M needed (2026-09-23, two-step pack): ~430 sectors moved
DEFAULT_LIMIT = (12000000, 200000000)

# host-side checks on the disk image a session leaves behind: ("fsck",) must pass; ("ls", path, present, absent)
# lists a directory and checks names; ("get", path, hostfile, nbytes) fetches a file and compares it with the first
# nbytes (0 = all) of a host file; ("data", path, bytes) fetches a file and compares it with the bytes given;
# ("packed",) = no dead sector: the free pointer is DATA_V2 + the sectors of every live extent (files and
# subdirectories), computed from the image; ("same", gone) = every file of the pristine os/disk.img is still there
# with the same bytes, load and exec address, except the paths in gone, which must be absent (2026-09-23, pack)
def pattern(n):
    """big.session (2026-09-25): bigw.c's bytes, byte i = (lo ^ (lo >> 8) ^ hi * 37) & 255, i = hi * 65536 + lo"""
    return bytes(((i & 0xFFFF) ^ ((i & 0xFFFF) >> 8) ^ ((i >> 16) * 37)) & 255 for i in range(n))


HOST = {
    "big": [("fsck",),                          # 2026-09-25: files over 64K and 128K (24-bit positions)
            ("data", "/BIG1", pattern(70 * 1024 + 7)),
            ("data", "/COPY1", pattern(70 * 1024 + 7)),
            ("data", "/BIG3", pattern(70 * 1024 + 7)),      # 2026-09-25: WRITE in odd pieces
            ("data", "/BIG2", pattern(140 * 1024 + 7) + b"tail\n")],
    "badhandle": [("fsck",), ("boot",), ("same", []),       # 2026-09-23: nothing written through a bad handle
                  ("data", "/BADH.TXT", b"ABC")],
    "api": [("fsck",), ("get", "/COPY.TXT", "os/disk/README.TXT", 0)],
    "write": [("fsck",),
              ("ls", "/", ["T", "T2", "SAVED.BIN"], ["README.TXT"]),
              ("ls", "/T", ["KEEP.TXT"], ["COPY.TXT", "H.BIN", "SUB"]),
              ("get", "/T/KEEP.TXT", "os/disk/README.TXT", 0),
              ("get", "/T2/HELLO", "os/build/bin/hello.bin", 16),
              ("get", "/SAVED.BIN", "os/build/bin/hello.bin", 0x84)],
    "vi": [("fsck",), ("ls", "/", ["T.TXT"], [])],
    "redirect": [("fsck",),                    # 2026-09-23: > >> < and the write-handle rule
                 ("ls", "/", ["R1.TXT", "R2.TXT", "R3.TXT", "R5.TXT"], ["R4.TXT", "R6.BIN", "B"]),
                 ("data", "/R1.TXT", b"hello\nmore\nthird\n"),
                 ("data", "/R2.TXT", b"apple 3 red\napple 3 red\nbanana 12 yellow\nbanana 12 yellow\n"
                                     b"cherry 40 red\nfig 7 purple\npear 5 green\n"),     # sort F > F
                 ("data", "/R3.TXT", b"/BIN\n"),
                 ("data", "/R5.TXT", b"")],
    "pipe": [("fsck",),                        # 2026-09-23: pipes; the temp files are gone afterwards
             ("ls", "/", ["P1.TXT"], ["PIPE0.TMP", "PIPE1.TMP"]),
             ("data", "/P1.TXT", b"5 15 69\n")],
    "pack": [("fsck",), ("packed",), ("same", ["/FRUIT2.TXT"]),   # 2026-09-23: the hole of /FRUIT2.TXT moves /MAN, /DOCS...
             ("ls", "/", ["PK"], ["FRUIT2.TXT", "X.TXT", "PIPE0.TMP", "PIPE1.TMP"]),
             ("ls", "/PK", ["A.TXT", "LOG", "U.TXT", "NEW.TXT", "SUB"], ["G.TXT", "EMPTY"]),
             ("data", "/PK/LOG", b"one\ntwo\n"),
             ("data", "/PK/A.TXT", b"alpha2\n"),
             ("data", "/PK/NEW.TXT", b"new\n"),
             ("data", "/PK/SUB/DEEP/LAST.TXT", b"last\n"),
             ("data", "/PK/SUB/DEEP/MID.TXT", b"mid\n"),
             ("data", "/PK/U.TXT", b"apple 3 red\nbanana 12 yellow\ncherry 40 red\nfig 7 purple\npear 5 green\n"),
             ("get", "/PK/SUB/Y1CC.MD", "software/compiler/README.md", 0),
             ("get", "/PK/SUB/DEEP/MD.MD", "os/docs/mddemo.md", 0),
             ("get", "/PK/SUB/H", "os/build/bin/hello.bin", 0)],
    "wave2": [("fsck",),
              ("ls", "/T", ["E1", "E2", "FRUIT.TXT", "H", "S"], []),
              ("ls", "/U", ["E3", "S"], ["E1", "E2", "FRUIT.TXT", "H"]),
              ("ls", "/U/S", ["F2.TXT", "FRUIT.TXT", "FRUIT2.TXT", "H", "F1.TXT"], ["README.TXT"]),
              ("get", "/FRUIT.TXT", "os/disk/FRUIT.TXT", 0),
              ("get", "/T/S/F2.TXT", "os/disk/FRUIT2.TXT", 0),
              ("get", "/U/S/F1.TXT", "os/disk/FRUIT.TXT", 0),
              ("get", "/U/S/H", "os/build/bin/hello.bin", 0)],
}


# extra files a session's disk copy gets before it boots (2026-09-23): (host source, disk name, load/exec); a .c
# source is compiled first with y1cc --os at $5000, as os/Makefile compiles /BIN commands
EXTRA = {"badhandle": [("badh.c", "/BADH", 0x5000), ("", "/ZERO.BIN", 0x6000)],
         "big": [("bigw.c", "/BIGW", 0x5000), ("bigr.c", "/BIGR", 0x5000)],
         "systab": [("systab.c", "/SYSTAB", 0x5000)],
         "exec": [("exe.c", "/EXE", 0x5000), ("exe.c", "/EXES", 0x5000, ["--stack", "0xCFFF"]),
                  ("", "/BIG.TXT", 0xC000, 20000)]}


def extras(name, img):
    for e in EXTRA.get(name, []):
        src, disk, addr = e[:3]
        more = e[3] if len(e) > 3 and isinstance(e[3], list) else []     # (2026-09-25) extra y1cc flags
        fill = e[3] if len(e) > 3 and isinstance(e[3], int) else 0       # or the size of a zero-filled file
        if src.endswith(".c"):
            base = os.path.splitext(src)[0]
            shutil.copy(os.path.join(ROOT, "software/assembler/yacc1.def"), BUILD)
            open(os.path.join(BUILD, "rcasm.rc"), "w").write("-h\n")
            subprocess.run([sys.executable, os.path.join(ROOT, "software/compiler/y1cc.py"), os.path.join(HERE, src),
                            "-o", os.path.join(BUILD, base + ".asm"), "--org", "0x5000", "--os"] + more +
                           (["--xisa"] if os.environ.get("XISA") else []), check=True)
            lst = subprocess.run([os.path.join(ROOT, "software/assembler/asm"), base, "-d=yacc1"], cwd=BUILD,
                                 capture_output=True, text=True).stdout
            if "\n0 Errors" not in lst: sys.exit("%s: assembler errors" % src)
            host = os.path.join(BUILD, base + ".bin")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/img2bin.py"), os.path.join(BUILD, base + ".img"),
                            host, "--base", "0x5000"], check=True, capture_output=True)
        else:
            host = os.path.join(BUILD, "fill%d.bin" % fill); open(host, "wb").write(bytes(fill))
        rc, out = p8xfs("put", img, host, "--name", disk, "--load", hex(addr), "--exec", hex(addr))
        if rc: sys.exit("put %s: %s" % (disk, out))


# numbers in a transcript that follow the disk's contents rather than the session: pack's summary lines give the free
# pointer and how many files moved, and every man page or /DOCS edit changes both. Numbers of two or more digits on
# those lines become N (the one-digit counts the session itself makes stay checked; the "packed" host check
# verifies the free pointer from the image)
MASK = {"pack": (re.compile(r"^(pack: .*)$", re.M), re.compile(r"\d\d+"))}


# the banner's version: y1os.asm is v0.2, y1os.c (the specification, `make -C os OS=c`) v0.1; both must pass the same
# transcripts, which carry the default (assembly) OS's banner (2026-09-23)
BANNER = re.compile(r"Y1/OS v[0-9.]+ \([0-9-]+\)")


# XISA=1 (2026-09-24: the /BIN programs built with y1cc --xisa): the programs are smaller (or, the smallest, 2 bytes
# larger), so the sizes that `ls` and `load` print are masked; everything else must be the same transcript
XSIZES = [(re.compile(r"(?m)^(\s*)\d+(  \S+  @[0-9A-F]{4})$"), r"\1N\2"), (re.compile(r"loaded \d+ bytes"), "loaded N bytes")]


def xmask(s):
    if os.environ.get("XISA"):
        for rx, rep in XSIZES: s = rx.sub(rep, s)
    return s


def same(got, exp): return xmask(BANNER.sub("Y1/OS v", got)) == xmask(BANNER.sub("Y1/OS v", exp))


def mask(name, s):
    if name not in MASK: return s
    line, num = MASK[name]
    return line.sub(lambda m: num.sub("N", m.group(1)), s)


MON_EXIT = 0xF10E           # the monitor's `0` command (cmd_exit): the session's last line; the instruction-level emulator
                            # stops at its $00 byte, the microcode one with -E (2026-09-25: the limits no longer have to
                            # be run out after `exit`)


def transcript(emu, limit, img, script):
    stop = ["-E", "%X" % MON_EXIT] if emu.endswith("y1ucemu") else []
    p = subprocess.Popen([emu, "-x", "-m", "-c", img, "-l", str(limit)] + stop, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try: out, err = p.communicate(script, timeout=900)
    except subprocess.TimeoutExpired: p.kill(); out, err = p.communicate(); return None, "timeout"
    s = out.decode("latin1")
    i = s.find("BOOT FROM CF"); j = s.find("\nbye", i)
    if i < 0 or j < 0: return None, "no boot/bye in the output (limit too low?): " + s[-300:]
    k = s.find(">", j)                           # the monitor prompt after the OS returned
    status = err.decode("latin1").strip().splitlines()[-1] if err.strip() else ""
    return s[i:k + 1], status


def p8xfs(*args):
    r = subprocess.run([sys.executable, FS] + list(args), capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout + r.stderr


def tree_files(img):
    """Walk a volume (iteratively): {path: (bytes, load, exec)} of every live file, and the sectors of every live
    extent (files and subdirectories; the root's own extent is not in the data area)."""
    files = {}; nsec = 0
    todo = [(P.ROOT_LBA, P.ROOT_SECS, "")]
    while todo:
        dlba, dsecs, path = todo.pop()
        for e in P.iter_dir(img, dlba, dsecs):
            nm = e["name"].decode("latin1").rstrip()
            if e["flags"] not in (P.F_FILE, P.F_DIR) or nm in (".", ".."): continue
            if e["flags"] == P.F_DIR:
                nsec += P.dir_secs(e); todo.append((e["start"], P.dir_secs(e), path + "/" + nm))
            else:
                nsec += max(1, (e["length"] + P.SEC - 1) // P.SEC)
                files[path + "/" + nm] = (bytes(img[e["start"] * P.SEC: e["start"] * P.SEC + e["length"]]),
                                          e["load"], e["exec"])
    return files, nsec


def host_check(name, img):
    """Run the HOST checks for a session on its disk image; returns a list of failure strings."""
    fails = []
    for chk in HOST.get(name, []):
        if chk[0] == "packed":
            vol = P.read_img(img); _, nsec = tree_files(vol)
            if P.get_free(vol) != P.DATA_V2 + nsec:
                fails.append("not packed: free pointer %d, live extents end at %d" % (P.get_free(vol), P.DATA_V2 + nsec))
        elif chk[0] == "same":
            want, _ = tree_files(P.read_img(os.path.join(OS, "disk.img")))
            got, _ = tree_files(P.read_img(img))
            for path, v in sorted(want.items()):
                if path in chk[1]:
                    if path in got: fails.append("%s should be gone" % path)
                elif path not in got: fails.append("%s is missing" % path)
                elif got[path] != v: fails.append("%s differs from the pristine image" % path)
        elif chk[0] == "boot":                  # the boot block as the pristine image has it: 'P8', version, OSCNT,
            vol = P.read_img(img); ref = P.read_img(os.path.join(OS, "disk.img"))   # a free pointer not below it
            if bytes(vol[0:4]) != bytes(ref[0:4]) or P.get_free(vol) < P.get_free(ref):
                fails.append("boot block changed: %r free %d" % (bytes(vol[0:6]), P.get_free(vol)))
        elif chk[0] == "fsck":
            rc, out = p8xfs("fsck", img)
            if rc: fails.append("fsck failed:\n" + out.strip())
        elif chk[0] == "ls":
            rc, out = p8xfs("ls", img, chk[1])
            names = {l.split()[0] for l in out.splitlines()[2:] if l.strip() and not l.endswith("entries") and not l.endswith("entry")}
            for n in chk[2]:
                if n not in names: fails.append("ls %s: %s missing (got %s)" % (chk[1], n, sorted(names)))
            for n in chk[3]:
                if n in names: fails.append("ls %s: %s should be gone" % (chk[1], n))
        elif chk[0] == "data":
            tmp = img + ".get"
            rc, out = p8xfs("get", img, chk[1], "--out", tmp)
            if rc: fails.append("get %s: %s" % (chk[1], out.strip())); continue
            got = open(tmp, "rb").read(); os.remove(tmp)
            if got != chk[2]: fails.append("get %s: %r, expected %r" % (chk[1], got[:60], chk[2]))
        elif chk[0] == "get":
            tmp = img + ".get"
            rc, out = p8xfs("get", img, chk[1], "--out", tmp)
            if rc: fails.append("get %s: %s" % (chk[1], out.strip())); continue
            want = open(os.path.join(ROOT, chk[2]), "rb").read()
            if chk[3]: want = want[:chk[3]]
            got = open(tmp, "rb").read(); os.remove(tmp)
            if got != want: fails.append("get %s: %d bytes, differs from %s (%d bytes)" % (chk[1], len(got), chk[2], len(want)))
    return fails


def cuts(n):
    """Cut `pack -v` off at n points spread over its run (the emulator's instruction limit is the reset) and prove it
    reset-safe: after EVERY cut fsck passes and every file of the fragmented volume is still there, byte-identical
    with the same load/exec; then a fresh boot runs pack again, which must finish, leave no dead sector and keep
    every file. The fragmented volume is pack.session up to its first `pack` (scenario A: a 1-sector hole early,
    so nearly every move takes two steps), and the same plus `del /DOCS/PORT.MD` (scenario B: a 91-sector hole,
    so what follows it moves in one step); n cuts each. Each cut is classified by the last
    line pack -v printed ("from>to [via scratch]: " + a letter per step done: c e C E), so the report shows that the
    cuts hit the scratch copy, the two entry rewrites and the one-step moves (2026-09-23)."""
    bad = 0
    for tag, extra in (("A", ""), ("B", "del /DOCS/PORT.MD\n")):
        bad += cut_scenario(tag, extra, n)
    print("all: %d cuts, %d failed" % (2 * n, bad))
    sys.exit(1 if bad else 0)


def cut_scenario(tag, extra, n):
    emu = EMUS[0][1]
    pre = open(os.path.join(HERE, "pack.session")).read().split("\npack\n")[0] + "\n" + extra
    img = os.path.join(BUILD, "cut.img")
    def boot(script, limit):
        shutil.copy(os.path.join(OS, "disk.img"), img) if script is not None else None
        p = subprocess.run([emu, "-x", "-m", "-c", img, "-l", str(limit)], capture_output=True,
                           input=b"O\n" + (script if script is not None else "pack\nexit\n").encode())
        return p.stdout.decode("latin1").replace("\r", "")
    boot(pre + "exit\n", 40000000)                      # the reference: the fragmented volume, no pack
    ref, _ = tree_files(P.read_img(img))
    def started(limit):                                  # has pack -v printed its first move / its summary?
        out = boot(pre + "pack -v\n", limit)
        return (re.search(r"^\d+>\d+", out, re.M) is not None), ("sectors reclaimed" in out), out
    def first(pred, lo, hi):                             # smallest limit in (lo, hi] where pred holds (to 1K)
        while hi - lo > 1000:
            mid = (lo + hi) // 2
            if pred(mid): hi = mid
            else: lo = mid
        return hi
    lo = first(lambda l: started(l)[0], 1000000, 40000000)
    hi = first(lambda l: started(l)[1], lo, 60000000)
    print("scenario %s: pack -v runs from ~%d to ~%d instructions; %d cuts" % (tag, lo, hi, n))
    kinds = {}; bad = 0
    for k in range(n):
        limit = lo - 20000 + (hi - lo + 40000) * k // (n - 1)
        out = started(limit)[2]
        moves = re.findall(r"^(\d+)>(\d+)( via \d+)?: ?([ceCE]*)", out, re.M)
        if "sectors reclaimed" in out: kind = "after the last write"
        elif not moves: kind = "before the first move"
        else:
            via, st = moves[-1][2], moves[-1][3]
            kind = {("v", ""): "2-step: copying to scratch", ("v", "c"): "2-step: scratch copied, entry not yet",
                    ("v", "ce"): "2-step: entry on scratch, copying down", ("v", "ceC"): "2-step: copied down, entry still on scratch",
                    ("v", "ceCE"): "2-step: done (next step not started)", ("", ""): "1-step: copying",
                    ("", "C"): "1-step: copied, entry not yet", ("", "CE"): "1-step: done"}[("v" if via else "", st)]
        rc, fs = p8xfs("fsck", img)
        got, _ = tree_files(P.read_img(img))
        lost = [q for q, v in ref.items() if got.get(q) != v]
        boot(None, 12000000)                             # a fresh boot of the same image: pack again
        rc2, fs2 = p8xfs("fsck", img)
        vol = P.read_img(img); got2, nsec = tree_files(vol)
        lost2 = [q for q, v in ref.items() if got2.get(q) != v]
        packed = P.get_free(vol) == P.DATA_V2 + nsec
        ok = rc == 0 and not lost and rc2 == 0 and not lost2 and packed
        kinds[kind] = kinds.get(kind, 0) + 1
        if not ok:
            bad += 1
            print("  cut at %d (%s): fsck %s, lost %s; rerun: fsck %s, lost %s, %s" % (limit, kind,
                  "ok" if rc == 0 else "FAIL", lost[:4], "ok" if rc2 == 0 else "FAIL", lost2[:4],
                  "packed" if packed else "NOT packed"))
    for kind, c in sorted(kinds.items()): print("  %3d cuts %s" % (c, kind))
    print("  %d cuts, %d failed (a failure = fsck, a lost or changed file, or a rerun that does not finish)" % (n, bad))
    os.remove(img)
    return bad


def main():
    update = "--update" in sys.argv; keep = "--keep" in sys.argv
    if "--cuts" in sys.argv:
        r = subprocess.run(["make", "-s", "-C", OS], capture_output=True, text=True)
        if r.returncode: sys.exit("os build failed")
        os.makedirs(BUILD, exist_ok=True)
        i = sys.argv.index("--cuts")
        cuts(int(sys.argv[i + 1]) if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit() else 60)
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    r = subprocess.run(["make", "-s", "-C", OS], capture_output=True, text=True)
    if r.returncode: sys.exit("os build failed:\n" + r.stdout[-800:] + r.stderr[-800:])
    os.makedirs(BUILD, exist_ok=True)
    passed = failed = 0
    for sess in sorted(glob.glob(os.path.join(HERE, "*.session"))):
        name = os.path.basename(sess)[:-8]
        if only and name not in only: continue
        script = b"O\n" + open(sess, "rb").read() + b"0\n"
        for (tag, emu), limit in zip(EMUS, LIMITS.get(name, DEFAULT_LIMIT)):
            img = os.path.join(BUILD, "%s.%s.img" % (name, tag))
            shutil.copy(os.path.join(OS, "disk.img"), img)
            extras(name, img)
            got, status = transcript(emu, limit, img, script)
            if got is not None: got = mask(name, got)
            exp_file = os.path.join(HERE, "%s.%s.out" % (name, tag))
            if got is None: print("%-12s %-4s FAIL  %s" % (name, tag, status)); failed += 1; continue
            if update: open(exp_file, "w", newline="").write(got)
            if not os.path.exists(exp_file): print("%-12s %-4s FAIL  no %s (run with --update)" % (name, tag, os.path.basename(exp_file))); failed += 1; continue
            exp = open(exp_file, newline="").read()          # keep the CR LF pairs the monitor prints
            fails = host_check(name, img)
            if not same(got, exp):
                open(os.path.join(HERE, "%s.%s.got" % (name, tag)), "w", newline="").write(got)
                fails.insert(0, "transcript differs (see %s.%s.got)" % (name, tag))
            if fails:
                print("%-12s %-4s FAIL  %s" % (name, tag, "; ".join(fails))); failed += 1
            else:
                print("%-12s %-4s PASS  %s%s" % (name, tag, status[:70], "  host: p8xfs ok" if name in HOST else "")); passed += 1
            if not keep: os.remove(img)
    print("%d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
