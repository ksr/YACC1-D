#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/ybasic/run.py - BASIC in assembly against BASIC in C (2026-11-11).

  run.py [session ...] [--uc] [-v]
    session   only these (expr, prog, files, limits, gfx)
    --uc      the sessions on the microcode emulator too (slow: minutes)
    -v        print the transcripts' differences in full

os/commands-asm/basic.asm, /bin/basic, is the same program as os/commands/basic.c, its specification, which is on
the disk as /bin/basicc. One number differs (2026-11-20): the program area, 12,288 bytes in the assembly BASIC and
4,104 in the C one, whose room goes to its code. So the assembly BASIC is assembled here once more with the C one's
number (build/basicr), and that build is the one compared: it must say and do exactly what the C BASIC does. The
shipped /bin/basic is the same source with its own number, and check 5 is about that number alone. The checks:

1. Every session here (tests/ybasic/*.session: console lines sent after the monitor's O command, as tests/os does) is
   run twice on the instruction-level emulator, on a copy of os/disk.img whose /bin/basic is the assembly BASIC with
   the reference's program area, and on a copy whose /bin/basic is the C one (os/build/bin/basic.bin; the sessions
   type `basic`). The two console transcripts must be
   the same byte for byte, and the root directories must hold the same files of the same sizes afterwards.
     expr    expressions, strings, every function, direct statements, the errors a typed line can make
     prog    programs: FOR / NEXT, GOSUB / RETURN, IF, GOTO, INPUT, the line editor, Ctrl-C, RUN's errors, BYE
     files   SAVE / LOAD, OPEN / PRINT# / INPUT# / EOF / CLOSE, basic FILE, basic -r FILE, < > and |
     limits  32 variables and 16 strings, GOSUB and FOR 8 deep, brackets 20 deep, numbers, the lines RUN remembers,
             a typed token, a program that uses most statements, the program area filled to the byte (?OUT OF
             MEMORY: 44 lines of 93 bytes and the probes after them, for the reference's 4,104 bytes)
     gfx     the graphics statements (2026-11-20): SCREEN, CLS, COLOR, PIXELW, LINE, BOX [,FILL], CIRCLE (a circle
             or an ellipse, [,FILL]), PAGE, GTEXT, PAINT and PIXELR(), what they leave on the screen as PIXELR and
             PEEK of the window see it, in a program and LISTed, with names that only begin like a keyword, and
             every way to write them wrong. No line of it may be longer than the 98 characters BASIC takes: both
             BASICs cut a longer one alike, and what is cut would not be tried (2026-11-20: 24 lines were)
   A key typed while a program runs is read by the Ctrl-C check and kept for the next INPUT or prompt; one typed while
   `basic -r` runs is lost. The emulator's console always has the rest of the session waiting, so the sessions have a
   spare empty line where a key is lost.
2. tests/os/ybasic.session, the OS tests' own BASIC session (tests/os runs it with /bin/basic, the assembly one), with
   the C BASIC on both emulators: the transcripts must be tests/os/ybasic.int.out and ybasic.uc.out as well.
3. The speed, in instructions (the instruction-level emulator's PC histogram, the block of the program /bin/basic):
   RUN of  10 a=0 / 20 a=a+1 / 30 if a<1000 then goto 20  on both. The assembly BASIC must need less than a quarter of
   the C one's instructions (2026-11-11: 843 against 5,319 for a pass of lines 20 and 30).

4. The picture (2026-11-20): all the graphics statements - every ink, boxes filled and not, circles and ellipses,
   lines in every direction, shapes over each edge of the screen, text, both pages, PAINT of regions of every kind
   and of one that takes more than its stack (the fill stops with ?PAINT TOO DEEP, once, at the same dot) - as
   programs of at most 3,000 bytes (the reference's area), RUN one after the other by both BASICs with the emulator
   writing the video card's state (Y1VIDSTATE). The 64K of graphics RAM must be the same from the assembly BASIC and
   from the C one on the instruction-level emulator and from the assembly one on the microcode emulator, and the same
   as tests/ybasic/gfxref.py draws it (os/lib_gfx.c in Python); control 1 and control 2 as the last SCREEN and PAGE
   left them.

5. The shipped /bin/basic's own program area: its banner says 12286 bytes, 132 lines of 93 bytes go in, the line
   that leaves exactly 2 bytes is taken and the next one is refused - the same probes as `limits`, at 12,288.

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
LINE = 98                                     # the characters of a typed line BASIC takes (basic.c getline)
WHOLE = ("gfx",)                              # the sessions that must not have a longer line
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-34s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def run(tag, img, script, extra=(), env=None):
    """the console output from BOOT FROM CF on, and the end of the emulator's own messages"""
    cmd = [EMUS[tag], "-x", "-m", "-c", img, "-l", LIMIT[tag]] + list(extra) + (["-E", MON_EXIT] if tag == "uc" else [])
    r = subprocess.run(cmd, input=script, capture_output=True, timeout=3600, env=dict(os.environ, **(env or {})))
    out = r.stdout.decode("latin1")
    return out[max(out.find("BOOT FROM CF"), 0):], r.stderr.decode("latin1")[-200:]


def root_files(img):
    r = subprocess.run([sys.executable, FS, "ls", img, "/"], capture_output=True, text=True)
    return [" ".join(l.split()[:2]) for l in r.stdout.splitlines()[1:]]


def reference_size():
    """the C BASIC's program area, from its source"""
    return int(re.search(r"^#define PROGSZ (\d+)", open(os.path.join(ROOT, "os/commands/basic.c")).read(), re.M).group(1))


def assemble_reference():
    """os/commands-asm/basic.asm with the C BASIC's program area -> build/basicr/basic.bin (as os/Makefile builds basica)"""
    d = os.path.join(B, "basicr"); os.makedirs(d, exist_ok=True)
    src = open(os.path.join(ROOT, "os/commands-asm/basic.asm")).read()
    src, n = re.subn(r"^(PROGSZ:\s+EQU) \d+", r"\1 %d" % reference_size(), src, flags=re.M)
    if n != 1: sys.exit("basic.asm: no PROGSZ: EQU line")
    open(os.path.join(d, "basic.asm"), "w").write(src)
    shutil.copy(os.path.join(ROOT, "software/assembler/yacc1.def"), d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n-l\n")
    r = subprocess.run([os.path.join(ROOT, "software/assembler/asm"), "basic", "-d=yacc1"], cwd=d, capture_output=True, text=True)
    if not re.search(r"^0 Errors", r.stdout, re.M): sys.exit("the reference-size basic.asm did not assemble")
    out = os.path.join(d, "basic.bin")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/img2bin.py"), os.path.join(d, "basic.img"), out, "--base", "0x5000"],
                   check=True, capture_output=True)
    return out


def images():
    """build/asm.img: os/disk.img with /bin/basic the assembly BASIC at the reference's program area; build/c.img: the
    same with the C one there; build/ship.img: os/disk.img as it is, the shipped assembly BASIC"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], check=True, capture_output=True)
    os.makedirs(B, exist_ok=True)
    c, a, ship = os.path.join(B, "c.img"), os.path.join(B, "asm.img"), os.path.join(B, "ship.img")
    shutil.copy(os.path.join(ROOT, "os/disk.img"), ship); shutil.copy(ship, a); shutil.copy(ship, c)
    for img, prog in ((c, os.path.join(ROOT, "os/build/bin/basic.bin")), (a, assemble_reference())):
        subprocess.run([sys.executable, FS, "put", img, prog, "--name", "/bin/basic", "--load", "0x5000", "--exec", "0x5000",
                        "--replace"], check=True, capture_output=True)
    return c, a, ship


def area_check(ship):
    """the shipped /bin/basic: 12,288 bytes of program area, to the byte"""
    fill = ["%d rem %s" % (n, "1" * 88) for n in range(1, 133)]       # 132 records of 93 bytes: 12 bytes left
    script = ("O\nbasic\n" + "".join(l + "\n" for l in fill + ["133 rem 1", "134 rem 22", "print 5"]) + "bye\nexit\n0").encode()
    out, err = run("int", fresh(ship, "run.ship.img"), script)
    out = out.replace("\r", "")
    check("the shipped BASIC's program area", "Y1 BASIC  12286 bytes for the program" in out and out.count("?OUT OF MEMORY") == 1 and
          bool(re.search(r"> 134 rem 22\n\?OUT OF MEMORY\n> print 5\n5\n", out)), out[-160:] + err.strip()[-80:])


def fresh(img, name):
    """a copy to run on: the emulators write the image in place"""
    d = os.path.join(B, name); shutil.copy(img, d); return d


def compare(tag, name, c, a):
    script = b"O\n" + open(os.path.join(HERE, name + ".session"), "rb").read() + b"0"
    ci, ai = fresh(c, "run.c.img"), fresh(a, "run.asm.img")
    (co, ce), (ao, ae) = run(tag, ci, script), run(tag, ai, script)
    why = ""
    cut = [n for n, l in enumerate(script.split(b"\n")) if len(l) > LINE] if name in WHOLE else []
    if cut: why = "longer than the %d characters BASIC takes, so cut and not tried: line %s" % (LINE, ", ".join(map(str, cut)))
    elif not re.search(r"\n\r?bye", co): why = "the C BASIC's run did not reach the end: " + ce.strip()
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


# the picture: (statement, numbers) in order; BASIC runs them as a program, gfxref.py draws the same
PICTURE = [("cls",), ("box", 0, 0, 639, 399), ("line", 0, 0, 639, 399), ("line", 639, 0, 0, 399), ("boxf", 20, 20, 120, 80),
           ("color", 2), ("boxf", 40, 40, 200, 120), ("box", 30, 30, 210, 130), ("line", 0, 399, 639, 0), ("color", 1),
           ("circle", 320, 200, 150), ("circle", 320, 200, 5), ("circle", 320, 200, 0), ("circle", 500, 100, 1),
           ("color", 0), ("line", 20, 50, 120, 50), ("boxf", 60, 60, 70, 70), ("circle", 320, 200, 149), ("color", 1),
           ("box", 600, 380, 700, 450), ("circle", 0, 0, 30), ("line", -20, 100, 40, 130), ("line", 300, -30, 340, 20),
           ("boxf", -30, -30, 12, 9), ("boxf", 630, 390, 2000, 2000), ("boxf", 700, 10, 800, 20), ("boxf", 10, -50, 20, -40),
           ("box", -10, 200, 10, 220), ("box", 250, 380, 260, 420), ("circle", 639, 399, 40), ("circle", 320, -10, 25),
           ("line", 400, 300, 390, 280), ("line", 400, 300, 410, 280), ("line", 400, 300, 380, 310), ("line", 400, 300, 420, 310),
           ("line", 400, 300, 380, 290), ("line", 400, 300, 420, 290), ("line", 400, 300, 390, 320), ("line", 400, 300, 410, 320),
           ("line", 450, 300, 450, 330), ("line", 470, 330, 470, 300), ("line", 480, 300, 510, 300), ("line", 510, 310, 480, 310),
           ("box", 520, 300, 520, 300), ("box", 530, 300, 540, 300), ("box", 550, 300, 550, 310), ("boxf", 560, 300, 560, 300),
           ("pixelw", 100, 350), ("pixelw", 639, 0), ("pixelw", 640, 0), ("pixelw", 0, 400), ("pixelw", -1, -1),
           ("color", 5), ("pixelw", 100, 350), ("pixelw", 102, 350), ("color", 1), ("screen", 3),
           ("page", 1, 0), ("cls",), ("box", 100, 100, 539, 299), ("line", 100, 100, 539, 299), ("circle", 320, 200, 90),
           ("boxf", 110, 110, 150, 150), ("pixelw", 0, 0), ("page", 0, 1), ("pixelw", 320, 200), ("page", 3, 2),
           ("pixelw", 322, 200), ("page", 0, 1),
           # circles and ellipses, filled and not, every ink, thin ones, ones over the edges, radii of 0 and too large
           ("page", 1, 1), ("cls",), ("circlef", 80, 80, 60), ("color", 2), ("circlef", 110, 100, 40), ("circle", 80, 80, 70),
           ("color", 0), ("circle", 80, 80, 30), ("ellipsef", 80, 80, 20, 5), ("color", 1),
           ("ellipse", 320, 200, 300, 180), ("ellipse", 320, 200, 180, 190), ("ellipsef", 320, 200, 120, 40),
           ("color", 2), ("ellipsef", 320, 200, 40, 120), ("color", 1), ("ellipse", 500, 60, 100, 3), ("ellipse", 560, 200, 2, 150),
           ("ellipsef", 500, 330, 90, 2), ("ellipsef", 600, 300, 1, 80), ("ellipse", 200, 300, 0, 40), ("ellipse", 200, 300, 40, 0),
           ("ellipsef", 230, 350, 0, 20), ("ellipsef", 230, 350, 20, 0), ("circle", 260, 300, 0), ("circlef", 264, 300, 0),
           ("circle", 270, 300, 1), ("circlef", 280, 300, 1), ("circle", 290, 300, 2), ("circlef", 300, 300, 2),
           ("circlef", 0, 0, 50), ("circle", 639, 399, 60), ("ellipsef", 639, 200, 30, 90), ("ellipse", 320, -20, 200, 60),
           ("ellipsef", 320, 420, 100, 60), ("circle", 100, 300, 511), ("circle", 100, 300, 512), ("circlef", 100, 300, -5),
           ("ellipse", 100, 300, 600, 10), ("ellipsef", 100, 300, 10, 600), ("ellipse", 400, 100, 511, 511),
           # text: every character, sizes, inks over what is there, over the edges, sizes that draw nothing
           ("page", 0, 0), ("gtext", 220, 20, 1, " !#$%&'()*+,-./0123456789:;<=>?"), ("gtext", 220, 30, 1, "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"),
           ("gtext", 220, 40, 1, "`abcdefghijklmnopqrstuvwxyz{|}~"), ("gtext", 220, 60, 2, "YACC1 Basic 640x400"),
           ("gtext", 220, 80, 3, "Size 3"), ("gtext", 130, 150, 7, "Big"), ("color", 2), ("gtext", 30, 60, 2, "invert"),
           ("gtext", 30, 60, 2, "in"), ("color", 0), ("gtext", 25, 30, 1, "erased"), ("color", 1),
           ("gtext", 600, 200, 2, "edge"), ("gtext", -8, 300, 3, "left"), ("gtext", 300, -5, 2, "top"), ("gtext", 300, 392, 2, "bottom"),
           ("gtext", 400, 250, 0, "none"), ("gtext", 400, 250, 64, "none"), ("gtext", 400, 250, -2, "none"), ("gtext", 400, 250, 63, " "),
           ("gtext", 400, 260, 1, ""), ("gtext", 400, 270, 1, "12345678901234567890123456789012"),
           # PAINT: a box, a ring, the inverting ink on a disc and on what it then belongs to, a letter's hole, a
           # block erased round a hole, a corner cut off by a line, places off the screen, each ink on a dot that is
           # already so, and a comb that takes more than the stack has (the fill stops: "?PAINT TOO DEEP")
           ("page", 1, 1), ("cls",), ("box", 10, 10, 60, 40), ("paint", 30, 20), ("paint", 30, 20), ("circle", 120, 60, 40),
           ("circle", 120, 60, 20), ("paint", 120, 30), ("color", 2), ("paint", 120, 60), ("paint", 121, 60), ("color", 1),
           ("gtext", 200, 20, 6, "O8B"), ("paint", 210, 40), ("paint", 250, 30), ("paint", 250, 50), ("paint", 284, 30),
           ("boxf", 300, 100, 400, 160), ("color", 0), ("circlef", 350, 130, 20), ("paint", 301, 101), ("paint", 301, 101),
           ("color", 1), ("line", 0, 300, 100, 399), ("paint", 5, 395), ("paint", 700, 10), ("paint", 10, 500), ("paint", -1, -1),
           ("circle", 500, 300, 60), ("paint", 500, 300), ("color", 0), ("circlef", 500, 300, 30), ("color", 2), ("paint", 500, 300),
           ("color", 1), ("line", 0, 220, 639, 220), ("line", 0, 223, 639, 223), ("comb", 221), ("paint", 0, 222)]


def picture_check(c, a):
    sys.path.insert(0, HERE); import gfxref
    ref = gfxref.Gfx(); lines = []; size = 0; deep = 0
    for n, (op, *v) in enumerate(PICTURE):
        text = {"boxf": "box %d,%d,%d,%d,fill", "box": "box %d,%d,%d,%d", "line": "line %d,%d,%d,%d", "circle": "circle %d,%d,%d",
                "circlef": "circle %d,%d,%d,fill", "ellipse": "circle %d,%d,%d,%d", "ellipsef": "circle %d,%d,%d,%d,fill",
                "pixelw": "pixelw %d,%d", "color": "color %d", "screen": "screen %d", "cls": "cls", "page": "page %d,%d", "gtext": 'gtext %d,%d,%d,"%s"', "paint": "paint %d,%d",
                "comb": "for i = 0 to 319 : pixelw i + i, %d : next i"}[op] % tuple(v)
        if size + len(text) + 8 > 3000:                    # the reference's program area: on with a new program
            lines += ["run", "new"]; size = 0
        lines.append("%d %s" % (10 * n + 10, text)); size += len(text) + 8
        if op == "color": ref.ink = v[0]
        elif op == "boxf": ref.box(*v, 1)
        elif op in ("box", "line", "circle"): getattr(ref, op)(*v)
        elif op == "circlef": ref.ellipse(v[0], v[1], v[2], v[2], 1)
        elif op in ("ellipse", "ellipsef"): ref.ellipse(*v, op == "ellipsef")
        elif op == "pixelw": ref.plot(*v)
        elif op in ("screen", "page"): getattr(ref, op)(*v)
        elif op == "gtext": ref.text(*v)
        elif op == "paint": deep += ref.paint(*v)
        elif op == "comb":
            for i in range(320): ref.plot(i + i, v[0])
        elif op == "cls": ref.g[ref.base():ref.base() + 32768] = bytes(32768)
    script = ("O\nbasic\n" + "".join(l + "\n" for l in lines) + "run\nbye\nexit\n0").encode()
    got = {}
    for tag, img, who in (("int", a, "assembly"), ("int", c, "C"), ("uc", a, "assembly")):
        st = os.path.join(B, "gfx.%s.%s.vid" % (who, tag))
        if os.path.exists(st): os.remove(st)
        out, err = run(tag, fresh(img, "run.gfx.img"), script, ["-V"], {"Y1VIDSTATE": st})
        d = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
        g = got[who, tag] = bytes.fromhex(d.get("gram", ""))
        bad = [i for i in range(65536) if g[i] != ref.g[i]] if len(g) == 65536 else [-1]
        check("the picture, %s BASIC, %s" % (who, tag), "Ok" in out and "MEMORY" not in out and out.count("?PAINT TOO DEEP") == deep == 1 and
              not bad and d.get("control", "")[:1] == "%X" % (ref.hi >> 4) and
              d.get("control2") == "00", "%d bytes are not the reference's, the first at $%04X; control %s / %s; %s" %
              (len(bad), bad[0] if bad else 0, d.get("control"), d.get("control2"), err.strip()[-80:]))
    check("the picture: %d dots, the same from all three" % sum(bin(b).count("1") for b in ref.g),
          got["assembly", "int"] == got["C", "int"] == got["assembly", "uc"] and any(ref.g[:32768]) and any(ref.g[32768:]))


def main():
    c, a, ship = images()
    names = [x for x in sys.argv[1:] if not x.startswith("-")] or \
        sorted(os.path.basename(p)[:-8] for p in glob.glob(os.path.join(HERE, "*.session")))
    for name in names:
        compare("int", name, c, a)
        if "--uc" in sys.argv: compare("uc", name, c, a)
    script = b"O\n" + open(os.path.join(ROOT, "tests/os/ybasic.session"), "rb").read() + b"0"
    banner = re.compile(r"Y1/OS v[0-9.]+ \([0-9-]+\)")           # the two kernels' banners differ (tests/os/run.py)
    for tag in ("int", "uc"):
        out, err = run(tag, fresh(c, "run.c.img"), script)
        m = re.search(r"\n\r?bye", out)
        got = out[:out.find(">", m.start()) + 1] if m else out
        exp = open(os.path.join(ROOT, "tests/os/ybasic.%s.out" % tag), "rb").read().decode("latin1")
        area = re.compile(r"(Y1 BASIC  )\d+( bytes)")              # the C BASIC's program area is its own
        got, exp = area.sub(r"\1N\2", got), area.sub(r"\1N\2", exp)
        check("tests/os ybasic, in C, %s" % tag, banner.sub("", got) == banner.sub("", exp),
              "not the expected transcript: " + err.strip())
    if not [x for x in sys.argv[1:] if not x.startswith("-")]:
        picture_check(c, a)
        area_check(ship)
    loop = ["10 a=0", "20 a=a+1", "30 if a<1000 then goto 20"]
    n = {k: instructions(img, loop + ["run"]) - instructions(img, loop) for k, img in (("C", c), ("assembly", a))}
    check("speed", n["assembly"] * 4 < n["C"], "the loop: %d instructions in assembly, %d in C" % (n["assembly"], n["C"]))
    print("a pass of lines 20 and 30: %d instructions in assembly, %d in C (%.1f times)"
          % (n["assembly"] / 1000, n["C"] / 1000, n["C"] / n["assembly"]))
    print("ybasic: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
