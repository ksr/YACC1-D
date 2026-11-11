#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/emu.py - the ROM's video unit and Y1/OS's /bin/video on both emulators (2026-09-25).

  emu.py [name ...] [-v]      run the cases (all by default); -v prints each run's console output and screen

2026-11-11 (branch video-v3): the ROM drives the video card V3 - the HD63484 ACRTC on ports PA-PD, a 640 x 480 picture,
80 x 30 characters of 8 x 16 dots copied by the chip from the font, the PS/2 keyboard on PE / PF (software/videomodel.h
and acrtcmodel.h, the emulators' card on this branch). -V prints the screen read back as text - every cell matched
against the font's glyphs - and the chip's state on stderr at the end; -N takes the card away. The model keeps the chip
busy for each command's time and loses a byte written to a full FIFO, so each case also proves the driver's waits (no
"BYTES LOST"). Every case runs on the instruction-level emulator (int) and the microcode one (uc) through the monitor,
as a bench session would, and checks:

  present   the banner says VIDEO CARD FOUND, VS reports it, mirroring is OFF by default: after a help listing the chip
            has had no command and is still stopped
  write     VI (the chip started: 640 x 480, 31.469 kHz / 59.94 Hz, the screen blank); VW (text at a row and column,
            the last row too); a VW row or column out of range -> ? and the rest of the line dropped (its 0 must not
            reach the command loop); VR (a register byte read, written and read back); VX (bytes to the write FIFO: a
            word written to the frame buffer and read back through the read FIFO)
  mirror    VI, VM1, two help listings (40+ lines: the screen scrolls), VM0: the screen equals what a terminal model
            of the driver makes of the console bytes that were sent while mirroring was on (CR, LF, wrap, scroll; the
            font's lower case has the upper case's shapes)
  absent    -N: no banner line, VS says 00, VM1 changes nothing on the screen (there is none), the console still works
  keyboard  the monitor driven from the card's PS/2 keyboard (the console is the keyboard, Y1VID_KBD=stdin; the UART
            receives nothing): VI, VW, VS typed there
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
COLS, ROWS = 80, 30
VERBOSE = "-v" in sys.argv


def run(emu, script, extra=(), limit=400000000, disk=None, env=None):
    cmd = [emu, "-x", "-m", "-V", "-l", str(limit)] + list(extra)
    if disk: cmd += ["-c", disk]
    if emu.endswith("y1ucemu"): cmd += ["-E", MON_EXIT]
    env = dict(os.environ, Y1VID_CARD="v3", **(env or {}))
    r = subprocess.run(cmd, input=script.encode("latin1"), capture_output=True, timeout=1800, env=env)
    out, err = r.stdout.decode("latin1"), r.stderr.decode("latin1")
    if VERBOSE: print(out + "\n" + err)
    return out, err


def screen(err):
    """the rows of the -V dump (None when the card is absent or the chip was never started)"""
    lines = err.splitlines()
    try: i = next(k for k, l in enumerate(lines) if l.startswith("+-"))
    except StopIteration: return None
    rows = []
    for l in lines[i + 1:]:
        if l.startswith("+-"): break
        rows.append(l[1:-1])
    return rows


def started(err):
    """the chip runs the mode the ROM sets, and no byte was lost in its FIFO"""
    return "640 x 480 dots, 80 x 30 characters" in err and "line 31.469 kHz, frame 59.94 Hz" in err and \
        "running, interleaved access" in err and ", 0 not modelled" in err and "LOST" not in err


def model(data):
    """what the ROM's vputc makes of these console bytes on a blank screen, cursor home (monitor.asm, video driver);
    read back, the font's lower case is its upper case"""
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
    out, err = run(emu, "VS\nH\n0")
    ok = "VIDEO CARD FOUND" in out and "VIDEO 01  MIRROR 00  CRTC 00  ROW 00  COL 00  COLS 50" in out and \
        screen(err) is None and "the Base screen is not set up" in err and "OMR 0000 (stopped" in err and " 0 commands" in err
    check("present", tag, ok, "banner/status/chip: %r %r" % (out[:200], err[-300:]))


def case_write(tag, emu):
    out, err = run(emu, "VI\nVS\n0")
    check("write", tag, "VIDEO 01  MIRROR 00  CRTC 01  ROW 00  COL 00" in out and screen(err) == BLANK and started(err),
          "VI: %r" % err[-400:])
    out, err = run(emu, "VI\nVW0102 hello, world\nVW1D00 bottom row [x]\nVW1E00 no\nVW0050 0\nVS\n0")
    s = screen(err)
    ok = s is not None and s[1] == "  HELLO, WORLD".ljust(COLS) and s[29] == "BOTTOM ROW [X]".ljust(COLS) and \
        all(s[r] == " " * COLS for r in range(ROWS) if r not in (1, 29)) and out.count(" ?") == 2 and \
        "ROW 1D  COL 0E" in out and started(err)
    check("write", tag, ok, "VW rows: %r / %r" % (s and (s[1], s[29]), out[-200:]))
    # VR: HDW's byte (r85) is $4F; r8C (the Upper screen's height, unused) written and read back.
    # VX: RWP word 100 on the Base screen, WT $ABCD, RWP again, RD; then the read FIFO a byte at a time through VR00
    out, err = run(emu, "VI\nVR85\nVR8C 12\nVR8C\nVX 08 0C 40 00 08 0D 06 40 48 00 AB CD 08 0C 40 00 08 0D 06 40 44 00\n"
                        "VR00\nVR00\n0")
    vals = [l.strip() for l in out.replace("\r", "").splitlines() if re.fullmatch(r"\s*[0-9A-F]{2}\s*", l)]
    s = screen(err)
    ok = vals == ["4F", "12", "AB", "CD"] and started(err) and s is not None and s[0][40:42] == "??" and \
        s[0].count("?") == 2 and all(s[r] == " " * COLS for r in range(1, ROWS))      # word 100: line 2, dots 320-335
    check("write", tag, ok, "VR / VX: %r, row 0 %r" % (vals, s and s[0]))


def case_mirror(tag, emu):
    out, err = run(emu, "VI\nVM1\nH\nH\nVM0\nVS\n0", limit=900000000)
    scr = screen(err)
    i = out.find("\n\rVIDEO 01  MIRROR 01")                    # the first byte VM1's status sends, mirrored
    if tag == "int": j = out.find("\n\rVIDEO 01  MIRROR 00", i)   # VM0's status: no longer mirrored
    else: j = out.find("VM0", i) + 3                           # uc: the monitor's echo of VM0 still was
    ok = i >= 0 and scr == model(out[i:j]) and started(err)
    lines = out[i:j].count("\n")
    check("mirror", tag, ok and lines > ROWS, "%d lines mirrored; screen vs model:\n%s\n%s\n%s" %
          (lines, "\n".join(scr or []), "\n".join(model(out[i:j])), err[-300:]))


def case_absent(tag, emu):
    out, err = run(emu, "VS\nVM1\nH\nVS\n0", extra=["-N"])
    ok = "VIDEO CARD FOUND" not in out and "VIDEO 00  MIRROR 00" in out and "VIDEO 00  MIRROR 01" in out and \
        "INTEL-HEX LOAD" in out and "video: no card (-N)" in err
    check("absent", tag, ok, "%r / %r" % (out[-300:], err[-200:]))


def case_keyboard(tag, emu):
    # the fast emulator with the keyboard takes the ROM's machine path, where the 0 command is the stop loop: a limit
    out, err = run(emu, "VI\nVW0102 typed on the keyboard\nVS\n0", env={"Y1VID_KBD": "stdin"},
                   limit=400000000 if tag == "uc" else 20000000)
    scr = screen(err)
    ok = scr is not None and scr[1] == "  TYPED ON THE KEYBOARD".ljust(COLS) and \
        "VIDEO 01  MIRROR 00  CRTC 01  ROW 01  COL 17" in out and "PS/2 empty, 0 queued" in err and started(err)
    check("keyboard", tag, ok, "%r / %r" % (out[-300:], scr and scr[:2]))


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
        "usage: video" in out and "video: what? bogus" in out and started(err) and "CRTC cursor on" in out
    check("os", tag, ok, "\n" + out[out.find("BOOT FROM CF"):] + "\n" + text + "\n" + err[-300:])


CASES = {"present": case_present, "write": case_write, "mirror": case_mirror, "absent": case_absent,
         "os": case_os, "keyboard": case_keyboard}
names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(CASES)
for n in names:
    for tag, emu in EMUS:
        CASES[n](tag, emu)
print("%d failed" % fails)
sys.exit(1 if fails else 0)
