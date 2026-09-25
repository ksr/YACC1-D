#!/usr/bin/env python3
"""tests/video/emu.py - the ROM's video unit and Y1/OS's /BIN/VIDEO on both emulators (2026-09-25).

  emu.py [name ...] [-v]      run the cases (all by default); -v prints each run's console output and screen

The emulators model the card (software/videomodel.h): display RAM at $D000-$D7FF, the 6845 at $D800/$D802, -V prints
the screen and the CRTC registers on stderr at the end, -N takes the card away. Every case runs on the instruction-
level emulator (int) and the microcode one (uc) through the monitor, as a bench session would, and checks:

  present   the banner says VIDEO CARD FOUND, VS reports it, mirroring is OFF by default: after VC and a help
            listing the screen is still blank
  write     VC, VW (text at a row/column, upper-cased), VB (bytes), VF + VD (the screen as text over the console),
            VR (a CRTC register written and read back); a VW row or column out of range and a VB address outside
            $Dxxx -> ? and the rest of the line dropped (its 0 must not reach the command loop)
  mirror    VI (the CRTC table: R1/R6 = 80/24, the dump follows them), VM1, two help listings (40+ lines: the screen
            scrolls), VM0: the screen equals what a terminal model of the driver makes of the console bytes that were
            sent while mirroring was on (CR, LF, wrap, scroll, upper case)
  absent    -N: no banner line, VS says 00, VM1 changes nothing on the screen (there is none), the console still works
  os        Y1/OS (os/disk.img): video (status), video init, video on, echo, video clear, echo, video off, echo:
            the screen shows what came between the clear and off and nothing else; video -h, a bad word
"""
import os, sys, re, subprocess, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator")),
        ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"))]
LST = open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read()
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", LST, re.M).group(1).upper()   # the monitor's 0 command
COLS, ROWS = 80, 24
VERBOSE = "-v" in sys.argv


def run(emu, script, extra=(), limit=400000000, disk=None):
    cmd = [emu, "-x", "-m", "-V", "-l", str(limit)] + list(extra)
    if disk: cmd += ["-c", disk]
    if emu.endswith("y1ucemu"): cmd += ["-E", MON_EXIT]
    r = subprocess.run(cmd, input=script.encode("latin1"), capture_output=True, timeout=1800)
    out, err = r.stdout.decode("latin1"), r.stderr.decode("latin1")
    if VERBOSE: print(out + "\n" + err)
    return out, err


def screen(err):
    """the rows of the -V dump (None when the card is absent)"""
    lines = err.splitlines()
    try: i = next(k for k, l in enumerate(lines) if l.startswith("+-"))
    except StopIteration: return None
    rows = []
    for l in lines[i + 1:]:
        if l.startswith("+-"): break
        rows.append(l[1:-1])
    return rows


def crtc(err):
    m = re.search(r"^video: CRTC ((?:[0-9A-F-]{2} ?){18})", err, re.M)
    return m.group(1).split() if m else None


def model(data):
    """what the ROM's vputc makes of these console bytes on a blank screen, cursor home (monitor.asm, video driver)"""
    g = [[" "] * COLS for _ in range(ROWS)]; row = col = 0

    def lf():
        nonlocal row, col
        col = 0
        if row + 1 == ROWS: g.pop(0); g.append([" "] * COLS)
        else: row += 1

    def put(c):
        nonlocal col
        g[row][col] = c; col += 1
        if col == COLS: lf()

    for ch in data:
        c = ord(ch) & 0x7F
        if c < 0x20:
            if c == 13: col = 0
            elif c == 10: lf()
            elif c == 8: col = max(0, col - 1)
            elif c == 12: g = [[" "] * COLS for _ in range(ROWS)]; row = col = 0
            elif c == 9:
                put(" ")
                while col & 7: put(" ")
        elif c != 0x7F:
            if c >= 0x60: c -= 0x20
            put(chr(c))
    return ["".join(r) for r in g]


BLANK = [" " * COLS] * ROWS
fails = 0


def check(name, tag, ok, why=""):
    global fails
    print("%-8s %-4s %s%s" % (name, tag, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def case_present(tag, emu):
    out, err = run(emu, "VS\nVC\nH\n0")
    scr = screen(err)
    ok = "VIDEO CARD FOUND" in out and "VIDEO 01  MIRROR 00  CRTC 00  ROW 00  COL 00" in out and scr == BLANK
    check("present", tag, ok, "banner/status/screen: %r %r" % (out[:200], scr and scr[:2]))


def case_write(tag, emu):
    out, err = run(emu, "VC\nVW0102 hello, world\nVB D0A0 41 42 43\nVW1700 bottom row [x]\nVW1800 no\n"
                        "VR0C 12\nVR0C\nVF2E\nVD\nVB C000 41 00\nVW0050 0\n0")
    scr = screen(err)
    vd = [l[3:] for l in out.splitlines() if re.match(r"^[0-9A-F]{2} ", l) and len(l) == 3 + COLS]
    want = ["." * COLS] * ROWS                                   # VF2E filled every byte with '.'
    ok1 = scr == want and vd == want
    check("write", tag, ok1, "VF/VD: %r / %r" % (scr and scr[0], vd[:1]))
    out2, err2 = run(emu, "VC\nVW0102 hello, world\nVB D0A0 41 42 43\nVW1700 bottom row [x]\n0")
    s2 = screen(err2)
    ok2 = s2 is not None and s2[1].startswith("  HELLO, WORLD ") and s2[2].startswith("ABC ") and \
        s2[23].startswith("BOTTOM ROW [X] ") and all(s2[r] == " " * COLS for r in (0,) + tuple(range(3, 23)))
    check("write", tag, ok2, "VW/VB rows: %r" % (s2 and s2[:3]))
    regs = crtc(err)
    ok3 = out.count(" ?") == 3 and regs is not None and regs[12] == "12" and "\n12\n" in out.replace("\n\r", "\n")
    check("write", tag, ok3, "VW row 18 -> ?, VR0C 12 read back: %r" % (regs,))


def case_mirror(tag, emu):
    out, err = run(emu, "VI\nVM1\nH\nH\nVM0\nVS\n0")
    scr = screen(err); regs = crtc(err)
    i = out.find("\n\rVIDEO 01  MIRROR 01")                    # the first byte VM1's status sends, mirrored
    if tag == "int": j = out.find("\n\rVIDEO 01  MIRROR 00", i)   # VM0's status: no longer mirrored
    else: j = out.find("VM0", i) + 3                           # uc: the monitor's echo of VM0 still was
    ok = i >= 0 and scr == model(out[i:j]) and regs[1] == "50" and regs[6] == "18" and "CRTC R1/R6" in err
    lines = out[i:j].count("\n")
    check("mirror", tag, ok and lines > ROWS, "%d lines mirrored; screen vs model:\n%s\n%s" %
          (lines, "\n".join(scr or []), "\n".join(model(out[i:j]))))


def case_absent(tag, emu):
    out, err = run(emu, "VS\nVM1\nH\nVS\n0", extra=["-N"])
    ok = "VIDEO CARD FOUND" not in out and "VIDEO 00  MIRROR 00" in out and "VIDEO 00  MIRROR 01" in out and \
        "INTEL-HEX LOAD" in out and "video: no card (-N)" in err
    check("absent", tag, ok, "%r / %r" % (out[-300:], err[-200:]))


def case_os(tag, emu):
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os")], check=True, capture_output=True)
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    disk = os.path.join(HERE, "build", "video.%s.img" % tag)
    shutil.copy(os.path.join(ROOT, "os/disk.img"), disk)
    script = ("O\nvideo\nvideo init\nvideo on\necho first\nvideo clear\necho mirrored line\nvideo off\n"
              "echo not on the screen\nvideo -h\nvideo bogus\nexit\n0")
    out, err = run(emu, script, disk=disk, limit=3000000000 if tag == "uc" else 40000000)
    scr = screen(err) or []
    text = "\n".join(scr)
    echo = tag == "uc"                          # the typed commands come back only where the ROM echoes (uartin)
    ok = "video card found at D000, mirror off, CRTC cursor off" in out and "MIRRORED LINE" in text and \
        ("ECHO MIRRORED LINE" in text and "VIDEO OFF" in text) == echo and "NOT ON THE SCREEN" not in text and \
        "FIRST" not in text and \
        "usage: video" in out and "video: what? bogus" in out and crtc(err)[1] == "50" and "CRTC cursor on" in out
    check("os", tag, ok, "\n" + out[out.find("BOOT FROM CF"):] + "\n" + text)


CASES = {"present": case_present, "write": case_write, "mirror": case_mirror, "absent": case_absent, "os": case_os}
names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(CASES)
for n in names:
    for tag, emu in EMUS:
        CASES[n](tag, emu)
print("%d failed" % fails)
sys.exit(1 if fails else 0)
