#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/v20/run.py - the video card V2.0 in both emulators (2026-11-10; software/videomodel.h, Y1VID_CARD=v2.0).

  run.py [-v]      -v prints each run's console output and the emulator's -V lines

1. model_test.c, the model on its own: the console as the PS/2 keyboard (Y1VID_KBD=stdin), the controller's timing
   and interrupt request, VSYNC / DE to the clock.
2. v20card.asm through the monitor, on the instruction-level emulator (int) and the microcode one (uc), in four builds
   of the card: as designed (8 dots, the graphics chips fitted), the text-only build, DOTS open, and a 2 MHz CPU clock.
   Each run checks the status port, the 6845 through PA/PB, the 16 plane/page pairs of the window, VSYNC's pulse and
   frame in polls (against the frame's clocks and the poll loop's clocks from software/opclocks.h), DE's share of
   256 polls (55% of the time; 30-75% allowed: the poll loop beats against the 54 or 40.5 clocks of a scan line),
   three keys from Y1VID_KEYS (on the branch video-v3 the ROM drives the V3 card, so the monitor is on the UART
   here), and the -V line; int and uc must agree.
3. tools/vidsim.py render draws a V2.0 state file (Y1VIDSTATE) with its graphics layer.
"""
import os, re, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator")), ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"))]
LST = open(os.path.join(ROOT, "firmware/monitor/monitor.lst")).read()
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", LST, re.M).group(1).upper()
CLOCKS = [int(x) for x in re.findall(r"(\d+),", open(os.path.join(ROOT, "software/opclocks.h")).read().split("{", 1)[1])]
VERBOSE = "-v" in sys.argv
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-28s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def build(d):
    shutil.copy(DEF, d); shutil.copy(os.path.join(HERE, "v20card.asm"), d)
    open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    subprocess.run([ASM, "v20card", "-d=yacc1"], cwd=d, capture_output=True)
    img = os.path.join(d, "v20card.img")
    if not os.path.exists(img): sys.exit("v20card.asm did not assemble")
    return open(img, "rb").read()


def run(emu, img, env, state=None):
    cmd = [emu, "-x", "-m", "-V", "-l", "400000000"] + (["-E", MON_EXIT] if emu.endswith("y1ucemu") else [])
    # (branch video-v3: the ROM drives the V3 card and does not know this one, so the monitor is on the UART - the
    # console - and the program's three keys come from Y1VID_KEYS. The ROM's probe for a V3 card is an IN PE, which
    # on this card is the keyboard's data: it takes the first byte waiting, so one stands in front for it)
    e = dict(os.environ, Y1VID_CARD="v2.0", Y1VID_KEYS="\\x00Hi\\r", **env)
    if state: e["Y1VIDSTATE"] = state
    r = subprocess.run(cmd, input=img + b"G3000" + b"0", capture_output=True, env=e, timeout=1800)
    out, err = r.stdout.decode("latin1").replace("\r", ""), r.stderr.decode("latin1")
    if VERBOSE: print(out[out.find("V2.0 CARD"):] + "\n" + "\n".join(l for l in err.splitlines() if l.startswith("video:")))
    res = dict(re.findall(r"^(STATUS|CRTC|GFX|VSYNC|DE|KEYS) (.*)$", out, re.M))
    res["done"] = "DONE" in out
    m = re.search(r"^video: V2.0 control .*$", err, re.M)
    res["vline"] = m.group(0) if m else ""
    return res


def poll_clocks(*ops):
    return sum(CLOCKS[o] for o in ops)


def main():
    d = tempfile.mkdtemp()
    exe = os.path.join(d, "model_test")
    r = subprocess.run(["cc", "-O1", "-Wall", "-Wextra", "-Werror", "-o", exe, os.path.join(HERE, "model_test.c")],
                       capture_output=True, text=True)
    check("model_test builds", r.returncode == 0, r.stderr[-400:])
    if r.returncode == 0:
        r = subprocess.run([exe], capture_output=True, text=True)
        check("model_test", r.returncode == 0, r.stdout[-800:])

    img = build(d)
    # the VSYNC loops: INCR R5 ($55), INP PC ($9C), ANDI ($B3), BRNZ / BRZ ($A2 / $A1)
    loop = poll_clocks(0x55, 0x9C, 0xB3, 0xA1)
    builds = [("as designed", {}, "50", "00 4B 54", 8, 1e6),
              ("text-only", {"Y1VID_TEXTONLY": "1"}, "58", "20 FF 54", 8, 1e6),
              ("DOTS open", {"Y1VID_DOTS": "6"}, "51", "00 4B 54", 6, 1e6),
              ("2 MHz CPU", {"Y1_CLOCK": "2000000"}, "50", "00 4B 54", 8, 2e6)]
    for name, env, status, gfx, dots, hz in builds:
        got = {}
        for tag, emu in EMUS:
            r = got[tag] = run(emu, img, env)
            frame = 370 * 81 * dots / 12e6 * hz / loop          # the MDA frame in polls: lines x characters / rate
            pulse = 16 * 81 * dots / 12e6 * hz / loop
            vs = [int(x, 16) for x in r.get("VSYNC", "0 0").split()]
            de = int(r.get("DE", "0"), 16)
            ok = r["done"] and r.get("STATUS") == status and r.get("CRTC") == "15 A5" and r.get("GFX") == gfx and \
                r.get("KEYS") == "48 69 0D 00" and abs(vs[0] - pulse) <= 2 and abs(sum(vs) - frame) <= 3 and \
                0.3 < de / 256 < 0.75 and r["vline"].startswith("video: V2.0 control 00")
            check("%s, %s" % (name, tag), ok, "%r; VSYNC want ~%.1f / ~%.1f polls" % (r, pulse, frame))
        a, b = got["int"], got["uc"]
        same = all(a.get(k) == b.get(k) for k in ("STATUS", "CRTC", "GFX", "KEYS")) and \
            abs(sum(int(x, 16) for x in a["VSYNC"].split()) - sum(int(x, 16) for x in b["VSYNC"].split())) <= 1
        check("%s, int = uc" % name, same, "%r / %r" % (a, b))

    # vidsim draws the state, its graphics layer from the 32K (control 40: the layer on)
    state = os.path.join(d, "v20.vid"); png = os.path.join(d, "v20.png")
    run(EMUS[0][1], img, {}, state)
    st = open(state).read()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/vidsim.py"), "render", state, "--control", "0x40",
                        "--png", png], capture_output=True, text=True)
    ok = "card v2.0" in st and re.search(r"^gram [0-9A-F]{65536}$", st, re.M) and r.returncode == 0 and \
        "layers text,gfx" in r.stdout and "512 x 256 dots" in r.stdout and os.path.getsize(png) > 0
    check("vidsim render", bool(ok), r.stdout[-300:] + r.stderr[-300:])

    shutil.rmtree(d)
    print("v20: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
