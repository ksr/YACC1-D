#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/asm/run.py - the video card bring-up programs (2026-10-10), assembled and checked on the microcode
emulator with its video card model (software/videomodel.h), the way the machine runs them: the image through the
monitor's ':' loader, then G3000.

  run.py            assemble every NAME.asm here, compare with the committed NAME.img (the ones to load on the machine
                    with tools/monload.py --go 3000), run the checks
  run.py --update   rewrite the committed images from this build (read the diff first)

Checks: vram (4 passes, 0 errors; with the card removed (-N) it reports errors), crtcreg (R14, R15 and the 256-access
repeat OK; R12/R13 read 00 00 as on an MC6845, 12 34 on a part that reads them), testcard (the screen and the CRTC
table), estrobe (an endless stream of R14 accesses, no write to the JP1 latch), vstress after testcard (every code of
rows 4-22 one up, the pass count on row 23).
"""
import os, re, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
UC = os.path.join(ROOT, "software/ucemu/y1ucemu")
NAMES = ["vram", "crtcreg", "testcard", "estrobe", "vstress"]
fails = 0


def check(name, ok, detail):
    global fails
    fails += not ok
    print("%-9s %s  %s" % (name, "PASS" if ok else "FAIL", detail))


def build(d):
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    for n in NAMES:
        shutil.copy(os.path.join(HERE, n + ".asm"), d)
        r = subprocess.run([ASM, n, "-d=yacc1"], cwd=d, capture_output=True)
        if not re.search(rb"^0 Errors", r.stdout, re.M): sys.exit("assembling %s failed:\n%s" % (n, r.stdout.decode("latin1")[-600:]))
    return {n: open(os.path.join(d, n + ".img")).read() for n in NAMES}


def run(images, extra=(), env=None, limit=300000000, tail=b"0"):
    data = b"".join(open(i, "rb").read() + b"G3000" for i in images) + tail
    r = subprocess.run([UC, "-x", "-m", "-V", "-l", str(limit)] + list(extra), input=data, capture_output=True,
                       env=dict(os.environ, **(env or {})), timeout=1800)
    return r.stdout.decode("latin1").replace("\r", ""), r.stderr.decode("latin1")


def screen(err):
    return [l[1:-1] for l in err.splitlines() if l.startswith("|")]


def main():
    d = tempfile.mkdtemp()
    imgs = build(d)
    path = {n: os.path.join(d, n + ".img") for n in NAMES}
    for n in NAMES:
        mine = os.path.join(HERE, n + ".img")
        if "--update" in sys.argv: open(mine, "w").write(imgs[n])
        elif not os.path.exists(mine) or open(mine).read() != imgs[n]:
            check("images", False, "%s.img differs from the build (run.py --update)" % n)
    out, err = run([path["vram"]])
    check("vram", out.count("ERRORS 0000") == 4 and "VRAM DONE" in out, "4 passes, 0 errors")
    out, err = run([path["vram"]], ["-N"])
    check("vram", "D000 GOT FF EXP D0" in out and "ERRORS 0800" in out, "no card (-N): errors reported")
    out, err = run([path["crtcreg"]])
    ok = re.search(r"R14 00>00 3F>3F 15>15 2A>2A 12>12 +OK", out) and re.search(r"R15 00>00 FF>FF 55>55 AA>AA 34>34 +OK", out) \
        and "0000 FAILED OK" in out and "R12 R13 READ: 00 00" in out and "LATCH D801 D803: FF FF" in out
    check("crtcreg", bool(ok), "R14, R15, 256 repeats, R12/R13 = 00 00 (MC6845), latch FF")
    out, err = run([path["crtcreg"]], env={"Y1VID_R12READ": "1"})
    check("crtcreg", "R12 R13 READ: 12 34" in out, "a part that reads R12/R13: 12 34")
    out, err = run([path["testcard"]])
    s = screen(err)
    want0 = " YACC1 VIDEO TEST CARD - 64 X 24 - TESTCARD.ASM"
    ok = len(s) == 24 and s[0].startswith(want0) and s[1] == ("0123456789" * 7)[:64] and \
        s[2] == "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_ !\"#$%&'()*+,-./0123456789:;<=>?" and \
        s[4].startswith("04*THE QUICK BROWN FOX") and s[4].endswith("*") and s[22].startswith("16*X JUMPS") and \
        s[23].startswith("ROW 23 - LAST ROW.") and "video: CRTC 5E 40 4B 08 1F 06 18 1B 00 07 67 07 00 00 03 20" in err
    check("testcard", ok, "the screen (64 x 24) and the CRTC table (cursor $0320)")
    out, err = run([path["estrobe"]], ["-W"], limit=3000000, tail=b"")
    n14 = err.count("video: CRTC R14 <- 2A")
    check("estrobe", n14 > 1000 and "JP1 latch" not in err, "%d R14 accesses, none to the latch" % n14)
    out, err = run([path["testcard"], path["vstress"]])
    s = screen(err)
    check("vstress", len(s) == 24 and s[4].startswith("15+UIF!RVJDL") and s[23][48:52] == "0001" and s[0].startswith(want0),
          "rows 4-22 one code up, pass count 0001 (the emulator's console always has a byte waiting: one pass)")
    shutil.rmtree(d)
    print("%d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
