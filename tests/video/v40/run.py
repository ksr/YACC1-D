#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/v40/run.py - the video card V4 in both emulators, and its ROM (2026-11-14; docs/cards/video-v4.md,
software/videomodel.h with Y1VID_CARD=v4, the V4 build of firmware/monitor/monitor.asm: monitor-v4.img).

  run.py [-v]      -v prints each run's console output and the emulator's -V lines

1. The V4 monitor image is the V4 build of monitor.asm (tools/monvariant.py v4, assembled here), and the source as it
   stands still assembles to the V2.0 image: the two ROMs come from one file.
2. model_test.c, the model on its own: the ports, both control registers, the 64K behind the window, the text-only
   build, VSYNC / DE to the clock at 16 dots a count.
3. v40card.asm through the V4 monitor, on the instruction-level emulator (int) and the microcode one (uc), in three
   builds: as designed, the text-only build, and a 3.5 MHz CPU clock. Each run checks the status port, the 6845
   through PA/PB, the 32 plane/page pairs of the window, control 2, VSYNC's pulse and frame in polls (against the
   frame's clocks and the poll loop's clocks from software/opclocks.h), DE's share of 256 polls (61% of the time;
   35-85% allowed), three keys typed on the PS/2 keyboard (the console, Y1VID_KBD=stdin) and the -V line; int and uc
   must agree.
4. v40scr.asm, the ROM's screen driver: the video unit started through $FFBC, the console mirrored, 30 lines with
   lower case printed. The -V screen must be 80 x 25, scrolled six times (lines 07-1E on rows 0-23, "end" on row
   24), the 6845's table the card's, its cursor (24 * 80 + 3) / 2 with CURH set; int and uc must show the same screen.
5. The table the ROM loaded is tools/vidsim.py's table for the card (V4_TABLES[60]), and its timing check passes that
   table and the 70 Hz one with no warning: VGA's 31.469 kHz, 59.94 and 70.09 Hz.
6. The picture: the state file the emulator writes after v40scr (Y1VIDSTATE), drawn by tools/vidsim.py with the
   card's character generator (firmware/video/chargen-v40.bin). `vidsim.py render` takes the card from the file and
   prints the screen the emulator's -V printed; in the picture a character is its glyph from the image, and the
   cursor is the last two lines of the character CURH names, the right-hand one of count $03C1.
"""
import os, re, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator")), ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"))]
MON = os.path.join(ROOT, "firmware/monitor")
LST = open(os.path.join(MON, "monitor-v4.lst"), errors="replace").read()
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", LST, re.M).group(1).upper()
CLOCKS = [int(x) for x in re.findall(r"(\d+),", open(os.path.join(ROOT, "software/opclocks.h")).read().split("{", 1)[1])]
TABLE = "31 28 2A 26 1F 0D 19 1C 00 0F 6E 0F 00 00"          # R0-R13 of the note's section 3
VERBOSE = "-v" in sys.argv
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-34s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def assemble(d, name, text=None):
    """name.asm (from this folder, or the text given) assembled in d: the image's bytes"""
    os.makedirs(d, exist_ok=True)
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    if text is None: shutil.copy(os.path.join(HERE, name + ".asm"), d)
    else: open(os.path.join(d, name + ".asm"), "w").write(text)
    subprocess.run([ASM, name, "-d=yacc1"], cwd=d, capture_output=True)
    img = os.path.join(d, name + ".img")
    if not os.path.exists(img): sys.exit("%s.asm did not assemble" % name)
    return open(img, "rb").read()


def run(emu, img, env, keys=b""):
    # (as tests/video/v20/run.py: the fast emulator's 0 command ends in the stop loop, so its run ends at the limit)
    cmd = [emu, "-x", "-m", "-V", "-l", "400000000" if emu.endswith("y1ucemu") else "20000000"] + \
        (["-E", MON_EXIT] if emu.endswith("y1ucemu") else [])
    e = dict(os.environ, Y1VID_CARD="v4", **env)
    r = subprocess.run(cmd, input=img + b"G3000" + keys + b"0", capture_output=True, env=e, timeout=1800)
    out, err = r.stdout.decode("latin1").replace("\r", ""), r.stderr.decode("latin1")
    if VERBOSE: print(out[-900:] + "\n" + "\n".join(l for l in err.splitlines() if l.startswith(("video:", "|"))))
    return out, err


def main():
    d = tempfile.mkdtemp()

    # 1. one source, two ROMs
    sys.path.insert(0, os.path.join(ROOT, "tools")); import monvariant
    src = open(os.path.join(MON, "monitor.asm")).read()
    v4 = assemble(os.path.join(d, "v4"), "monitor", monvariant.variant(src, "v4"))
    check("monitor-v4.img is the V4 build", v4 == open(os.path.join(MON, "monitor-v4.img"), "rb").read())
    v2 = assemble(os.path.join(d, "v2"), "monitor", src)
    check("monitor.img is the source as it is", v2 == open(os.path.join(MON, "monitor.img"), "rb").read())
    check("the tags come off for V2.0", assemble(os.path.join(d, "v2b"), "monitor", monvariant.variant(src, "v2")) == v2)
    end = max(int(a, 16) for a in re.findall(r"^\s*\d+ ([0-9a-f]{4}): [0-9a-f]{2} ", LST.split("isrcode:")[0], re.M))
    check("the V4 monitor ends below $FF90", end < 0xFF90, "its last byte is at $%04X" % end)

    # 2. the model
    exe = os.path.join(d, "model_test")
    r = subprocess.run(["cc", "-O1", "-Wall", "-Wextra", "-Werror", "-o", exe, os.path.join(HERE, "model_test.c")],
                       capture_output=True, text=True)
    check("model_test builds", r.returncode == 0, r.stderr[-400:])
    if r.returncode == 0:
        r = subprocess.run([exe], capture_output=True, text=True)
        check("model_test", r.returncode == 0, r.stdout[-800:])

    # 3. the card's CPU side through the V4 monitor
    img = assemble(os.path.join(d, "card"), "v40card")
    loop = sum(CLOCKS[o] for o in (0x55, 0x9C, 0xB3, 0xA1))     # INCR R5, INP PC, ANDI, BRNZ / BRZ
    builds = [("as designed", {}, "70", "00 5D 54 5D", 1e6),
              ("text-only", {"Y1VID_TEXTONLY": "1"}, "78", "40 FF 54 FF", 1e6),
              ("3.5 MHz CPU", {"Y1_CLOCK": "3500000"}, "70", "00 5D 54 5D", 3.5e6)]
    for name, env, status, gfx, hz in builds:
        got = {}
        for tag, emu in EMUS:
            out, err = run(emu, img, dict(env, Y1VID_KBD="stdin"), b"Hi\r")
            r = got[tag] = dict(re.findall(r"^(STATUS|CRTC|GFX|VSYNC|DE|KEYS) (.*)$", out, re.M))
            frame = 525 * 50 * 16 / 25.175e6 * hz / loop        # lines x counts x dots / the dot clock, in polls
            pulse = 16 * 50 * 16 / 25.175e6 * hz / loop
            vs = [int(x, 16) for x in r.get("VSYNC", "0 0").split()]
            de = int(r.get("DE", "0"), 16)
            m = re.search(r"^video: V4 control 1 (..) .* control 2 (..) ", err, re.M)
            ok = "DONE" in out and r.get("STATUS") == status and r.get("CRTC") == "15 A5" and r.get("GFX") == gfx and \
                r.get("KEYS") == "48 69 0D 01" and abs(vs[0] - pulse) <= 2 and abs(sum(vs) - frame) <= 3 and \
                0.35 < de / 256 < 0.85 and bool(m) and m.groups() == ("00", "00")
            check("%s, %s" % (name, tag), ok, "%r; VSYNC want ~%.1f / ~%.1f polls; %s" % (r, pulse, frame, m and m.groups()))
        a, b = got["int"], got["uc"]
        same = all(a.get(k) == b.get(k) for k in ("STATUS", "CRTC", "GFX", "KEYS")) and \
            abs(sum(int(x, 16) for x in a.get("VSYNC", "0").split()) - sum(int(x, 16) for x in b.get("VSYNC", "0").split())) <= 1
        check("%s, int = uc" % name, same, "%r / %r" % (a, b))

    # 4. the ROM's screen driver
    img = assemble(os.path.join(d, "scr"), "v40scr")
    want = ["line %02X abcdefghijklmnopqrstuvwxyz {|}~" % n for n in range(7, 31)] + ["end"]
    screens = {}
    for tag, emu in EMUS:
        out, err = run(emu, img, {})
        rows = [l[1:-1] for l in err.splitlines() if l.startswith("|") and l.endswith("|")]
        screens[tag] = rows
        geo = re.search(r"^video: (\d+) x (\d+) from \$D000", err, re.M)
        crtc = re.search(r"^video: CRTC ((?:.. ){16})", err, re.M)
        ctl = re.search(r"control 2 (..) \(text on, cursor (\w+),", err)
        check("screen 80 x 25, %s" % tag, bool(geo) and geo.groups() == ("80", "25") and len(rows) == 25 and
              all(len(r) == 80 for r in rows), "%s, %d rows" % (geo and geo.groups(), len(rows)))
        check("scrolled, lower case, %s" % tag, [r.rstrip() for r in rows] == want,
              "\n" + "\n".join(r.rstrip() for r in rows[:3] + rows[-2:]))
        check("the 6845's table, %s" % tag, bool(crtc) and crtc.group(1).startswith(TABLE), crtc and crtc.group(1))
        check("cursor $03C1 and CURH, %s" % tag, bool(crtc) and crtc.group(1).split()[14:16] == ["03", "C1"] and
              "CUR 03 C1" in out and bool(ctl) and ctl.groups() == ("02", "right") and "DONE" in out,
              "%s; %s; console %r" % (crtc and crtc.group(1).split()[14:16], ctl and ctl.groups(), out[-60:]))
    check("the screen, int = uc", screens["int"] == screens["uc"] and bool(screens["int"]))

    # 5. the ROM's table is the one tools/vidsim.py checks
    import vidsim
    check("the ROM's table is vidsim's", " ".join("%02X" % v for v in vidsim.V4_TABLES[60][:14]) == TABLE)
    for raster, rate in ((60, "640 x 480 at 60 Hz"), (70, "640 x 400 at 70 Hz")):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/vidsim.py"), "timing", "--card", "v4", "--v4raster",
                            str(raster)], capture_output=True, text=True)
        ok = r.returncode == 0 and "WARNING" not in r.stdout and re.search(r"VGA %s .*: MATCH" % rate, r.stdout) and \
            "31.469 kHz" in r.stdout
        check("vidsim timing, %d Hz" % raster, bool(ok), r.stdout[-400:] + r.stderr[-200:])
    st = os.path.join(d, "v4.vid")
    subprocess.run([EMUS[0][1], "-x", "-m", "-V", "-l", "200000"], input=b"0", capture_output=True,
                   env=dict(os.environ, Y1VID_CARD="v4", Y1VIDSTATE=st))
    text = open(st).read() if os.path.exists(st) else ""
    check("the state file", "card v4" in text and bool(re.search(r"^control2 00$", text, re.M)) and
          bool(re.search(r"^gram [0-9A-F]{131072}$", text, re.M)), text[:200])

    # 6. the picture of the ROM's screen
    st = os.path.join(d, "scr.vid"); png = os.path.join(d, "scr.png")
    run(EMUS[0][1], img, {"Y1VIDSTATE": st})
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/vidsim.py"), "render", st, "--png", png],
                       capture_output=True, text=True)
    rows = [l[1:-1] for l in r.stdout.splitlines() if l.startswith("|") and l.endswith("|")]
    check("vidsim render: the card from the file", r.returncode == 0 and "== " + st in r.stdout and
          "control 2 (OUT PF) = $02" in r.stdout and "cursor on the right-hand character" in r.stdout and
          "640 x 400 dots" in r.stdout and os.path.exists(png), r.stdout[-300:] + r.stderr[-300:])
    check("vidsim render: the emulator's screen", rows == screens["int"] and len(rows) == 25,
          "\n" + "\n".join(x.rstrip() for x in rows[:2] + rows[-2:]))
    s = vidsim.State.load(st); x = s.extra
    cg = open(os.path.join(ROOT, "firmware/video/chargen-v40.bin"), "rb").read()
    W, H, pic = vidsim.picture_v4(s, cg, control=int(x["control"], 16), control2=int(x["control2"], 16),
                                  gram=bytes.fromhex(x["gram"]))
    def cell(row, col):
        return bytes(sum((pic[row * 16 + l][col * 8 + k] != (10, 10, 10)) << (7 - k) for k in range(8)) for l in range(16))
    def glyph(ch): return cg[ord(ch) * 16:ord(ch) * 16 + 16]
    check("the picture: 640 x 400, glyphs", (W, H) == (640, 400) and cell(0, 0) == glyph("l") and
          cell(0, 9) == glyph("b") and cell(23, 38) == glyph("~") and cell(24, 0) == glyph("e"))
    check("the picture: the cursor, row 24 column 3", cell(24, 3) == bytes(14) + b"\xff\xff" and cell(24, 2) == glyph("d") and
          sum(map(sum, (cell(24, c) for c in range(3, 80)))) == 2 * 255)

    shutil.rmtree(d)
    print("v40: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
