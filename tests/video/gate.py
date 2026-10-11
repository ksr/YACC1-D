#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/gate.py - the video card at gate level: y1ucemu -G REV against the behavioural card (2026-10-11).

  gate.py [name ...] [-v]      run the cases (all by default); -v prints each run's output

software/gatemodel generates software/ucemu/videogate.h from the V1.0 card's netlist with the bench reworks as netlist
edits; y1ucemu -G REV looks each step's decode up there (docs/cards/video.md section 9). The cases:

  gen      videogate.h is what software/gatemodel makes of the netlist and the revisions now; -G list names the six
           revisions; -G with an unknown name, or with -N, is refused
  equal    the behavioural card and -G v1.0 give the same run, byte for byte: the console output, the -V dump (screen
           and CRTC registers), the status line (instructions, steps, clocks, fights) and the card's state file
           (Y1VIDSTATE: registers, which were written, the selected register, the display RAM) - for the monitor's
           video unit (tests/video/emu.py's present/write/mirror, VI/VM1/VW/VS/VR), Y1/OS's video command, and the
           bring-up programs of tests/video/asm (vram, crtcreg, crtcreg on a part that reads R12/R13, testcard,
           testcard + vstress, estrobe with -W)
  events   with the card as fitted (-G v1.0) every one of those runs has 0 bus events, except crtcreg's two deliberate
           reads of the JP1 latch ($D801, $D803), reported as reads of floating inputs and nothing else
  rs       without the RS rework (-G v1.0-no-rs, the 6845 as drawn: RS = A0) the data register is unreachable, as
           hardware/cards/video/docs/fix-6845-register-select.md says: VR0E 12 then VR0E reads FF, R14 is never
           written, crtcreg reports BAD for R14/R15 and its repeat; every read of $D802 is an undriven-read event.
           With the 6845's socket empty (-G v1.0-no6845, the machine today) crtcreg fails the same way, the events
           name the empty socket; the RAM half still passes vram
  5v       without the +5V wire (-G v1.0-no-5v, the card of 2026-09-18): a write to $9010 (the monitor's ':' loader)
           lands in the display RAM at $D010, the write-through fault, with undefined-select events; with the wire
           (v1.0, v1.0-no6845) $D010 keeps $FF
  a0fix    the fix the document warns against (/A0 tied high): crtcreg's read of $D801 makes the 6845 and the JP1
           latch drive DATA0..7 together - contention events - and the latch reads 00 instead of FF
"""
import os, re, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UC = os.path.join(ROOT, "software/ucemu/y1ucemu")
LST = open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read()
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", LST, re.M).group(1).upper()   # the monitor's 0 command
ASM = os.path.join(HERE, "asm")
VERBOSE = "-v" in sys.argv
TMP = tempfile.mkdtemp()
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-7s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def img(*names):
    return b"".join(open(os.path.join(ASM, n + ".img"), "rb").read() + b"G3000" for n in names)


def run(data, extra=(), env=None, limit=400000000, disk=None, exit=True):
    """-> (stdout, stderr without the card's event lines, the event lines, the state file, the events counted)"""
    state = os.path.join(TMP, "state")
    if os.path.exists(state): os.remove(state)
    cmd = [UC, "-x", "-m", "-V", "-l", str(limit)] + (["-E", MON_EXIT] if exit else []) + list(extra)
    if disk: cmd += ["-c", disk]
    r = subprocess.run(cmd, input=data, capture_output=True, timeout=1800, env=dict(os.environ, Y1VIDSTATE=state, **(env or {})))
    out, err = r.stdout.decode("latin1"), r.stderr.decode("latin1")
    if VERBOSE: print(" ".join(cmd[5:]) + "\n" + out + "\n" + err)
    ev = [l for l in err.splitlines() if l.startswith("video card")]
    rest = "\n".join(l for l in err.splitlines() if not l.startswith("video card"))
    m = re.search(r"^video card \S+ \(gate level\): (\d+) bus events", err, re.M)
    st = open(state).read() if os.path.exists(state) else None
    return out, rest, ev, st, int(m.group(1)) if m else None


def disk_copy(tag):
    shutil.copy(os.path.join(ROOT, "os/disk.img"), os.path.join(TMP, tag + ".img"))
    return os.path.join(TMP, tag + ".img")


WRITE = ("VC\nVW0102 hello, world\nVB D0A0 41 42 43\nVW1700 bottom row [x]\nVW1800 no\nVR0E 12\nVR0E\nVF2E\nVD\n"
         "VB C000 41 00\nVW0050 0\n0")
OS = ("O\nvideo\nvideo init\nvideo on\necho first\nvideo clear\necho mirrored line\nvideo off\necho not on the screen\n"
      "video -h\nvideo bogus\nexit\n0")
SCENARIOS = [                                            # name, console input, options, environment, run to -E, Y1/OS disk
    ("present", b"VS\nVC\nH\n0", [], None, True, False),
    ("write", WRITE.encode(), [], None, True, False),
    ("write2", b"VC\nVW0102 hello, world\nVB D0A0 41 42 43\nVW1700 bottom row [x]\n0", [], None, True, False),
    ("mirror", b"VI\nVM1\nH\nH\nVM0\nVS\n0", [], None, True, False),
    ("vcmds", b"VS\nVI\nVR0E 12\nVR0E\nVW0000 HELLO\nVW1700 LAST ROW\nVM1\nVS\nH\nVM0\nVS\nVD\n0", ["-W"], None, True, False),
    ("os", OS.encode(), [], None, True, True),
    ("vram", img("vram") + b"0", [], None, True, False),
    ("crtcreg", img("crtcreg") + b"0", [], None, True, False),
    ("crtc-r12", img("crtcreg") + b"0", [], {"Y1VID_R12READ": "1"}, True, False),
    ("testcard", img("testcard") + b"0", [], None, True, False),
    ("vstress", img("testcard", "vstress") + b"0", [], None, True, False),
    ("estrobe", img("estrobe"), ["-W", "-l", "3000000"], None, False, False),
]


def case_gen():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "software/gatemodel"), "--check", os.path.join(ROOT, "software/ucemu/videogate.h")],
                       capture_output=True, text=True)
    check("gen", r.returncode == 0, r.stdout + r.stderr)
    r = subprocess.run([UC, "-G", "list"], capture_output=True, text=True)
    names = re.findall(r"^(v1\.0\S*)  ", r.stdout, re.M)
    check("gen", r.returncode == 0 and names == ["v1.0", "v1.0-no6845", "v1.0-no-rs", "v1.0-no-5v", "v1.0-drawn", "v1.0-a0fix"] and
          "wire IC17.24 (RS) wired to IC15.41 (ADDR1)" in r.stdout and "short +5V joined to VCC" in r.stdout, r.stdout[:600])
    bad = subprocess.run([UC, "-x", "-m", "-G", "v9"], capture_output=True, text=True, input="")
    both = subprocess.run([UC, "-x", "-m", "-G", "v1.0", "-N"], capture_output=True, text=True, input="")
    check("gen", bad.returncode == 1 and "-G list" in bad.stderr and both.returncode == 1 and "one video card or none" in both.stderr,
          bad.stderr + both.stderr)


def case_equal():
    for name, data, extra, env, ex, os_disk in SCENARIOS:
        lim = ["-l", "3000000000"] if os_disk else []
        b = run(data, extra + lim, env, disk=disk_copy("b") if os_disk else None, exit=ex)
        g = run(data, extra + lim + ["-G", "v1.0"], env, disk=disk_copy("g") if os_disk else None, exit=ex)
        same = b[0] == g[0] and b[1] == g[1] and b[3] == g[3] and b[3] is not None and b[2] == []
        if os_disk: same = same and open(os.path.join(TMP, "b.img"), "rb").read() == open(os.path.join(TMP, "g.img"), "rb").read()
        halted = re.search(r"^HALT at .*$", b[1], re.M)
        check("equal", same and halted is not None and "RUN TEST CODE" in b[0],
              "%s: the runs differ (stdout %s, stderr %s, state %s; %d bytes out, halted %s, %r)" %
              (name, b[0] == g[0], b[1] == g[1], b[3] == g[3], len(b[0]), halted is not None, b[2][:2]))
        ok = g[4] == 0 if name not in ("crtcreg", "crtc-r12") else \
            g[4] == 10 and all("a read of IC2 (the JP1 latch) with inputs FF floating" in l for l in g[2][:-1])
        check("events", ok, "%s: %r events: %s" % (name, g[4], "\n".join(g[2][:6])))


def case_rs():
    data = b"VR0E 12\nVR0E\n0"
    out, err, ev, st, n = run(data, ["-G", "v1.0"])
    good = "12" in re.split(r"[\r\n]+", out) and re.search(r"^video: CRTC( --){14} 12", err, re.M)
    out2, err2, ev2, st2, n2 = run(data, ["-G", "v1.0-no-rs"])
    bad = "FF" in re.split(r"[\r\n]+", out2) and re.search(r"^video: CRTC( --){18}", err2, re.M) and \
        n2 == 5 and all("read with RS = 0: the address register is write-only" in l for l in ev2[:-1])
    check("rs", bool(good) and n == 0 and bool(bad), "v1.0: %r / no-rs: %r %r" % (out[-200:], out2[-200:], ev2[:2]))
    out, err, ev, st, n = run(img("crtcreg") + b"0", ["-G", "v1.0-no-rs"])
    ok = re.search(r"R14 00>3F 3F>3F 15>3F 2A>3F 12>3F +BAD", out) and re.search(r"R15 00>FF FF>FF 55>FF AA>FF 34>FF +BAD", out) and \
        "00FF FAILED BAD" in out and "R12 R13 READ: FF FF" in out and any("RS = 0" in l for l in ev)
    check("rs", bool(ok), "crtcreg without the RS fix:\n%s\n%s" % (out[-500:], "\n".join(ev[:8])))
    out, err, ev, st, n = run(img("crtcreg") + b"0", ["-G", "v1.0-no6845"])
    ok = "R14 00>3F" in out and "BAD" in out and any("IC17 socket empty: its select (CS) is low" in l for l in ev)
    out2, err2, ev2, st2, n2 = run(img("vram") + b"0", ["-G", "v1.0-no6845"])
    check("rs", bool(ok) and out2.count("ERRORS 0000") == 4 and n2 == 0, "the empty socket:\n%s\n%s" % (out[-400:], out2[-300:]))


def case_5v():
    data = b":019010005A05\n:00000001FF\nBD000\n0"                     # the ':' loader writes $5A to $9010
    got = {}
    for rev in ("v1.0", "v1.0-no6845", "v1.0-no-5v"):
        out, err, ev, st, n = run(data, ["-G", rev])
        m = re.search(r"^D010: (..)", out.replace("\r", ""), re.M)
        got[rev] = (m.group(1) if m else None, n, ev)
    ok = got["v1.0"][:2] == ("FF", 0) and got["v1.0-no6845"][:2] == ("FF", 0) and got["v1.0-no-5v"][0] == "5A" and \
        any("~{CER} undefined: a write may land" in l for l in got["v1.0-no-5v"][2])
    check("5v", ok, "%r" % {k: (v[0], v[1], v[2][:4]) for k, v in got.items()})


def case_a0fix():
    out, err, ev, st, n = run(img("crtcreg") + b"0", ["-G", "v1.0-a0fix"])
    ok = "LATCH D801 D803: 00 00" in out.replace("\r", "") and \
        any("contention on the card: IC17 (6845) + IC2 (JP1 latch) drive DATA0..7 together, at $D801" in l for l in ev)
    check("a0fix", ok, "%s\n%s" % (out[-500:], "\n".join(ev[:6])))


CASES = {"gen": case_gen, "equal": case_equal, "rs": case_rs, "5v": case_5v, "a0fix": case_a0fix}
names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(CASES)
try:
    for n in names: CASES[n]()
finally:
    shutil.rmtree(TMP)
print("%d failed" % fails)
sys.exit(1 if fails else 0)
