#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/ybasic/run.py - BASIC in assembly against BASIC in C (2026-11-11).

  run.py [session ...] [--uc] [-v]
    session   only these (expr, prog, files, limits)
    --uc      the sessions on the microcode emulator too (slow: minutes)
    -v        print the transcripts' differences in full

os/commands-asm/basic.asm (`make -C os basica`: os/build/basica/basic.bin) is the same program as
os/commands/basic.c, which is /bin/basic and the specification. Three checks:

1. Every session here (tests/ybasic/*.session: console lines sent after the monitor's O command, as tests/os does) is
   run twice on the instruction-level emulator, on a copy of os/disk.img (the C BASIC) and on a copy whose /bin/basic
   is the assembly one. The two console transcripts must be the same byte for byte, and the root directories must
   hold the same files of the same sizes afterwards.
     expr    expressions, strings, every function, direct statements, the errors a typed line can make
     prog    programs: FOR / NEXT, GOSUB / RETURN, IF, GOTO, INPUT, the line editor, Ctrl-C, RUN's errors, BYE
     files   SAVE / LOAD, OPEN / PRINT# / INPUT# / EOF / CLOSE, basic FILE, basic -r FILE, < > and |
     limits  32 variables and 16 strings, GOSUB and FOR 8 deep, brackets 20 deep, numbers, the lines RUN remembers,
             a typed token, a program that uses most statements, the program area filled (?OUT OF MEMORY)
   A key typed while a program runs is read by the Ctrl-C check and kept for the next INPUT or prompt; one typed while
   `basic -r` runs is lost. The emulator's console always has the rest of the session waiting, so the sessions have a
   spare empty line where a key is lost.
2. tests/os/ybasic.session, the OS tests' own BASIC session, with the assembly BASIC on both emulators: the transcripts
   must be tests/os/ybasic.int.out and ybasic.uc.out, the ones the C BASIC is held to.
3. The speed, in instructions (the instruction-level emulator's PC histogram, the block of the program /bin/basic):
   RUN of  10 a=0 / 20 a=a+1 / 30 if a<1000 then goto 20  on both. The assembly BASIC must need less than a quarter of
   the C one's instructions (2026-11-11: 843 against 5,319 for a pass of lines 20 and 30).

Work files in tests/ybasic/build (git-ignored).
"""
import os, re, sys, glob, shutil, difflib, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
B = os.path.join(HERE, "build")
EMUS = {"int": os.path.join(ROOT, "software/emulator/emulator"), "uc": os.path.join(ROOT, "software/ucemu/y1ucemu")}
LIMIT = {"int": "2000000000", "uc": "40000000000"}
FS = os.path.join(ROOT, "tools/p8xfs.py")
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read(),
                     re.M).group(1).upper()
VERBOSE = "-v" in sys.argv
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-34s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def run(tag, img, script, extra=()):
    """the console output from BOOT FROM CF on, and the end of the emulator's own messages"""
    cmd = [EMUS[tag], "-x", "-m", "-c", img, "-l", LIMIT[tag]] + list(extra) + (["-E", MON_EXIT] if tag == "uc" else [])
    r = subprocess.run(cmd, input=script, capture_output=True, timeout=3600)
    out = r.stdout.decode("latin1")
    return out[max(out.find("BOOT FROM CF"), 0):], r.stderr.decode("latin1")[-200:]


def root_files(img):
    r = subprocess.run([sys.executable, FS, "ls", img, "/"], capture_output=True, text=True)
    return [" ".join(l.split()[:2]) for l in r.stdout.splitlines()[1:]]


def images():
    """build/c.img: os/disk.img; build/asm.img: the same with the assembly BASIC as /bin/basic"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img", "basica"], check=True, capture_output=True)
    os.makedirs(B, exist_ok=True)
    c, a = os.path.join(B, "c.img"), os.path.join(B, "asm.img")
    shutil.copy(os.path.join(ROOT, "os/disk.img"), c); shutil.copy(c, a)
    subprocess.run([sys.executable, FS, "put", a, os.path.join(ROOT, "os/build/basica/basic.bin"), "--name", "/bin/basic",
                    "--load", "0x5000", "--exec", "0x5000", "--replace"], check=True, capture_output=True)
    return c, a


def fresh(img, name):
    """a copy to run on: the emulators write the image in place"""
    d = os.path.join(B, name); shutil.copy(img, d); return d


def compare(tag, name, c, a):
    script = b"O\n" + open(os.path.join(HERE, name + ".session"), "rb").read() + b"0"
    ci, ai = fresh(c, "run.c.img"), fresh(a, "run.asm.img")
    (co, ce), (ao, ae) = run(tag, ci, script), run(tag, ai, script)
    why = ""
    if not re.search(r"\n\r?bye", co): why = "the C BASIC's run did not reach the end: " + ce.strip()
    elif co != ao:
        d = list(difflib.unified_diff(co.replace("\r", "").splitlines(), ao.replace("\r", "").splitlines(),
                                      "C", "assembly", lineterm="", n=1))
        why = "the transcripts differ:\n" + "\n".join("    " + l[:160] for l in (d if VERBOSE else d[:14]))
    elif root_files(ci) != root_files(ai): why = "the files left in / differ"
    check("%s %s (%d lines)" % (name, tag, co.count("\n")), not why, why)


def instructions(img, lines):
    """the instructions of the first program Y1/OS starts (basic) in a session of these BASIC lines"""
    d = fresh(img, "speed.img"); prof = os.path.join(B, "speed.prof")
    run("int", d, ("O\nbasic\n" + "".join(l + "\n" for l in lines) + "bye\nexit\n0").encode(), ["-P", prof])
    n = 0; blk = -1
    for l in open(prof):
        if l.startswith("program"): blk = int(l.split()[1]); continue
        m = re.fullmatch(r"[0-9A-F]{4} (\d+) \d+\n", l)
        if m and blk == 1: n += int(m.group(1))
    return n


def main():
    c, a = images()
    names = [x for x in sys.argv[1:] if not x.startswith("-")] or \
        sorted(os.path.basename(p)[:-8] for p in glob.glob(os.path.join(HERE, "*.session")))
    for name in names:
        compare("int", name, c, a)
        if "--uc" in sys.argv: compare("uc", name, c, a)
    script = b"O\n" + open(os.path.join(ROOT, "tests/os/ybasic.session"), "rb").read() + b"0"
    banner = re.compile(r"Y1/OS v[0-9.]+ \([0-9-]+\)")           # the two kernels' banners differ (tests/os/run.py)
    for tag in ("int", "uc"):
        out, err = run(tag, fresh(a, "run.asm.img"), script)
        m = re.search(r"\n\r?bye", out)
        got = out[:out.find(">", m.start()) + 1] if m else out
        exp = open(os.path.join(ROOT, "tests/os/ybasic.%s.out" % tag), "rb").read().decode("latin1")
        check("tests/os ybasic %s" % tag, banner.sub("", got) == banner.sub("", exp),
              "not the expected transcript: " + err.strip())
    loop = ["10 a=0", "20 a=a+1", "30 if a<1000 then goto 20"]
    n = {k: instructions(img, loop + ["run"]) - instructions(img, loop) for k, img in (("C", c), ("assembly", a))}
    check("speed", n["assembly"] * 4 < n["C"], "the loop: %d instructions in assembly, %d in C" % (n["assembly"], n["C"]))
    print("a pass of lines 20 and 30: %d instructions in assembly, %d in C (%.1f times)"
          % (n["assembly"] / 1000, n["C"] / 1000, n["C"] / n["assembly"]))
    print("ybasic: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
