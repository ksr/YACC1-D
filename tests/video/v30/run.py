#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/v30/run.py - the video card V3 in both emulators (2026-11-11; Y1VID_CARD=v3: software/videomodel.h
and the HD63484 of software/acrtcmodel.h; docs/cards/video-v3.md).

  run.py [-v]      -v prints each run's console output and the emulator's -V lines

1. tools/v3font.py --check: the font EPROM's image and the emulators' copy are the generator's.
2. model_test.c, the card and the chip on their own: the ports, the registers and FIFOs, every command the model has
   (the manual's examples where it gives one), the font EPROM, the raster count, the keyboard and the mouse.
3. v30card.asm through the monitor on the instruction-level emulator (int) and the microcode one (uc): a YACC1
   program starts the chip for 640 x 480, clears the screen, copies "V3 OK" from the font EPROM, draws a frame, a
   diagonal, a filled box and a dot, reads a word and the current pointer back, and takes a key and a mouse packet
   from the PS/2 controller. Checked: what it prints; the -V dump (the screen read back as text by matching the
   font's glyphs, the chip's line and frame rates); the frame buffer, dot for dot, against the same scene drawn
   here; int and uc the same.
4. tools/vidsim.py render draws the state file: 640 x 480, the same dots.
"""
import os, re, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator")), ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"))]
LST = open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read()
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", LST, re.M).group(1).upper()
sys.path.insert(0, os.path.join(ROOT, "tools"))
import v3font, vidsim
VERBOSE = "-v" in sys.argv
W, H, MW = 640, 480, 40
WANT = ["V3 CARD", "ID 60", "STATUS 23", "RD 3E 41", "CP 0140 00F0", "STATUS 23", "PS2 01:6B 03:2A 03:03 03:FE", "DONE"]
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-28s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def scene():
    """the picture v30card.asm draws, as rows of dots from the top (the chip's Y runs up from the bottom line)"""
    g = [[0] * W for _ in range(H)]
    def dot(x, y): g[H - 1 - y][x] = 1
    for i, ch in enumerate("V3 OK"):
        if ch == " ": continue
        for line, b in enumerate(v3font.glyph(ord(ch))):
            for k in range(8):
                if b >> k & 1: g[16 + line][(2 + i) * 8 + k] = 1
    for x in range(W): dot(x, 0); dot(x, H - 1)
    for y in range(H): dot(0, y); dot(W - 1, y)
    x0, y0, x1, y1 = 0, 0, W - 1, H - 1                           # the diagonal: Bresenham's, the last dot not drawn
    dx, dy, e, x, y = x1 - x0, -(y1 - y0), 0, x0, y0; e = dx + dy
    while (x, y) != (x1, y1):
        dot(x, y); e2 = 2 * e
        if e2 >= dy: e += dy; x += 1
        if e2 <= dx: e += dx; y += 1
    for y in range(100, 150):
        for x in range(100, 200): dot(x, y)
    dot(320, 240)
    return g


def run(emu, img, state):
    cmd = [emu, "-x", "-m", "-V", "-l", "400000000" if emu.endswith("y1ucemu") else "50000000"] + \
        (["-E", MON_EXIT] if emu.endswith("y1ucemu") else [])
    e = dict(os.environ, Y1VID_CARD="v3", Y1VID_KEYS="k", Y1VID_MOUSE="3,-2,2", Y1VIDSTATE=state)
    r = subprocess.run(cmd, input=img + b"G3000" + b"0", capture_output=True, env=e, timeout=1800)
    out, err = r.stdout.decode("latin1").replace("\r", ""), r.stderr.decode("latin1")
    if VERBOSE: print(out[out.find("V3 CARD"):] + "\n" + "\n".join(l for l in err.splitlines() if l[:1] in "v|+"))
    i = out.find("V3 CARD")
    return [l.strip() for l in out[i:].splitlines() if l.strip()][:len(WANT)] if i >= 0 else [], err


def main():
    d = tempfile.mkdtemp()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/v3font.py"), "--check"], capture_output=True, text=True)
    check("the font EPROM's image", r.returncode == 0, r.stdout)
    exe = os.path.join(d, "model_test")
    r = subprocess.run(["cc", "-O1", "-Wall", "-Wextra", "-Wno-unused-function", "-Werror", "-o", exe,
                        os.path.join(HERE, "model_test.c")], capture_output=True, text=True)
    check("model_test builds", r.returncode == 0, r.stderr[-600:])
    if r.returncode == 0:
        r = subprocess.run([exe], capture_output=True, text=True)
        check("model_test", r.returncode == 0, r.stdout[-800:])

    shutil.copy(DEF, d); shutil.copy(os.path.join(HERE, "v30card.asm"), d)
    open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    subprocess.run([ASM, "v30card", "-d=yacc1"], cwd=d, capture_output=True)
    imgf = os.path.join(d, "v30card.img")
    if not os.path.exists(imgf) or not os.path.getsize(imgf): sys.exit("v30card.asm did not assemble")
    img = open(imgf, "rb").read()

    want = scene(); states = {}
    for tag, emu in EMUS:
        state = os.path.join(d, tag + ".vid")
        lines, err = run(emu, img, state)
        check("the program, %s" % tag, lines == WANT, "%r" % lines)
        rows = [l[1:-1] for l in err.splitlines() if l.startswith("|")]
        ok = len(rows) == 30 and all(len(x) == 80 for x in rows) and rows[1].startswith("? V3 OK ") and rows[0] == "?" * 80 and \
            "640 x 480 dots, 80 x 30 characters" in err and "line 31.469 kHz, frame 59.94 Hz" in err and \
            "interleaved access" in err and ", 0 not modelled" in err
        check("the -V dump, %s" % tag, ok, "\n".join(rows[:3]) + "\n" + err[-400:])
        st = vidsim.read_state_file(state) if os.path.exists(state) else {}
        states[tag] = st
        if st.get("card") == "v3":
            w, h, got, mw, start = vidsim.v3_frame(st)
            bad = [(x, y) for y in range(H) for x in range(W) if got[y][x] != want[y][x]] if (w, h) == (W, H) else [None]
            check("the picture, %s" % tag, (w, h, mw, start) == (W, H, MW, 0) and not bad,
                  "%d x %d, %d dots differ, the first %r" % (w, h, len(bad), bad[:3]))
        else: check("the picture, %s" % tag, False, "no V3 state file")
    check("int = uc", states["int"] == states["uc"] and bool(states["int"]), "the two emulators' state files differ")

    png = os.path.join(d, "v30.png")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/vidsim.py"), "render", os.path.join(d, "int.vid"),
                        "--png", png, "--scale", "1"], capture_output=True, text=True)
    lit = sum(map(sum, want))
    ok = r.returncode == 0 and "640 x 480 dots from word $00000" in r.stdout and "%d dots lit" % lit in r.stdout and \
        os.path.exists(png) and os.path.getsize(png) > 0
    check("vidsim render", ok, r.stdout[-300:] + r.stderr[-300:])

    shutil.rmtree(d)
    print("v30: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
