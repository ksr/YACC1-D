#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/wm/run.py - windows in dots on the video card V4: the drawing routines of wkdemo.asm (2026-11-20).

  run.py [-v] [--png FILE]      -v: the costs' table in clocks too; --png: the scene's picture (tools/vidsim.py)

wkdemo.asm draws a desktop - a grey ground, a menu bar, two windows that overlap, text in both, the pointer twice
(once over the right and bottom edges) - with four routines that work on cells of 8 x 16 dots (its header). Checks:

1. It assembles (RC/asm), with the card's font appended: firmware/video/chargen-v40.bin's codes $20-$7E as WK_FONT.
   The run of 80 "byte, next byte" pairs is 160 bytes (it is entered by an address computed from the width).
2. The scene: the script between scene: and scend: in the source is read here and drawn again in Python. The 64K of
   graphics RAM the emulator ends with must be that, byte for byte, from the instruction-level emulator and from
   the microcode one; the second page untouched; control 1 = $4F (GFX-ON, the last plane), TEXT-OFF in control 2.
3. What it costs, in instructions (the instruction-level emulator's PC histogram, -P, summed over the program): the
   script replaced by one thing at a time, less the run of an empty script. Printed, and held under a ceiling each
   (a third over the 2026-11-20 figures) so a slower routine shows.
"""
import os, re, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMUS = {"int": os.path.join(ROOT, "software/emulator/emulator"), "uc": os.path.join(ROOT, "software/ucemu/y1ucemu")}
LST = open(os.path.join(ROOT, "firmware/monitor/monitor.lst"), errors="replace").read()
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", LST, re.M).group(1).upper()
CG = open(os.path.join(ROOT, "firmware/video/chargen-v40.bin"), "rb").read()
VERBOSE = "-v" in sys.argv
ARROW = [0x8000, 0xC000, 0xE000, 0xF000, 0xF800, 0xFC00, 0xFE00, 0xFF00, 0xFF80, 0xFFC0, 0xFC00, 0xEE00, 0xC700, 0x8700,
         0x0380, 0x0380]
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-44s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def font_text():
    """WK_FONT: the glyphs $20-$7E of the card's character generator, 16 bytes each"""
    return "WK_FONT:\n" + "".join("        DB " + ", ".join("0%02xh" % b for b in CG[c * 16:c * 16 + 16]) + "\n"
                                  for c in range(32, 127))


def source(scene=None):
    """wkdemo.asm with the font; scene = other lines for the script (the costs' runs)"""
    s = open(os.path.join(HERE, "wkdemo.asm")).read()
    if scene is not None:
        i = s.index("\nscene:"); j = s.index("\nscend:")
        s = s[:i] + "\nscene:" + "".join("\n        DB " + l for l in scene) + "\n        DB 0" + s[j:]
    return s + font_text()


def assemble(d, text):
    os.makedirs(d, exist_ok=True)
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n-l\n")
    open(os.path.join(d, "wkdemo.asm"), "w").write(text)
    r = subprocess.run([ASM, "wkdemo", "-d=yacc1"], cwd=d, capture_output=True, text=True, errors="replace")
    img = os.path.join(d, "wkdemo.img")
    ok = os.path.exists(img) and "\n0 Errors" in r.stdout
    open(os.path.join(d, "wkdemo.lst"), "w").write(r.stdout)                 # -l: the listing is what it prints
    return (open(img, "rb").read() if ok else None), r.stdout[-600:]


def run(tag, img, st=None, prof=None):
    cmd = [EMUS[tag], "-x", "-m", "-V", "-l", "4000000000" if tag == "uc" else "40000000"] + \
        (["-E", MON_EXIT] if tag == "uc" else []) + (["-P", prof] if prof else [])
    env = dict(os.environ, Y1VID_CARD="v4", **({"Y1VIDSTATE": st} if st else {}))
    if st and os.path.exists(st): os.remove(st)
    r = subprocess.run(cmd, input=img + b"G3000" + b"0", capture_output=True, env=env, timeout=3600)
    return r.stdout.decode("latin1"), r.stderr.decode("latin1")


def script_bytes(text):
    """the bytes of the DB lines between scene: and scend:"""
    i = text.index("\nscene:") + 7; j = text.index("\nscend:")
    out = []
    for line in text[i:j].splitlines():
        line = line.strip()
        if not line.startswith("DB "): continue
        for m in re.finditer(r"'([^']*)'|([0-9][0-9a-fA-F]*h?)", line[3:]):
            if m.group(1) is not None: out += [ord(c) for c in m.group(1)]
            else:
                t = m.group(2)
                out.append(int(t[:-1], 16) if t.lower().endswith("h") else int(t))
    return out


def model(b):
    """the script drawn in Python -> the 64K of graphics RAM (page 0: plane * 2048 + row * 80 + column)"""
    g = bytearray(65536); i = 0
    def at(p, r, c): return p * 2048 + r * 80 + c
    while b[i]:
        op = b[i]; i += 1
        if op in (1, 2):
            x, y, w, h = b[i:i + 4]; i += 4
            if op == 1:
                pa, pb = b[i:i + 2]; i += 2
                for p in range(16):
                    for r in range(y, y + h):
                        for c in range(x, x + w): g[at(p, r, c)] = pb if p & 1 else pa
            else:
                for c in range(x, x + w): g[at(0, y, c)] = 0; g[at(15, y + h - 1, c)] = 0
                for p in range(16):
                    for r in range(y, y + h): g[at(p, r, x)] &= 0x7F; g[at(p, r, x + w - 1)] &= 0xFE
        elif op == 3:
            x, y, m = b[i:i + 3]; i += 3
            while b[i]:
                ch = b[i] if 32 <= b[i] <= 126 else 32
                for p in range(16): g[at(p, y, x)] = CG[ch * 16 + p] ^ m
                x += 1; i += 1
            i += 1
        else:
            px = b[i] << 8 | b[i + 1]; py = b[i + 2] << 8 | b[i + 3]; i += 4
            for r, bits in enumerate(ARROW):
                yy = py + r
                if yy >= 400: break
                v = bits << 8 >> (px & 7)                       # 24 bits: three bytes from column px >> 3
                for k in range(3):
                    c = (px >> 3) + k
                    if c < 80: g[at(yy & 15, yy >> 4, c)] ^= v >> (16 - 8 * k) & 255
    return bytes(g)


def cost(d, scene):
    """(instructions, clocks) of the program with this script, from the PC histogram"""
    img, msg = assemble(d, source(scene))
    if img is None: sys.exit("the costs' build did not assemble: " + msg)
    prof = os.path.join(d, "prof")
    run("int", img, prof=prof)
    n = c = 0
    for l in open(prof):
        m = re.fullmatch(r"([0-9A-F]{4}) (\d+) (\d+)\n", l)
        if m and 0x3000 <= int(m.group(1), 16) < 0x5000: n += int(m.group(2)); c += int(m.group(3))
    return n, c


def main():
    d = tempfile.mkdtemp(prefix="wm-")
    text = source()
    img, msg = assemble(os.path.join(d, "a"), text)
    check("wkdemo.asm assembles", img is not None, msg)
    if img is None: sys.exit(1)
    lst = open(os.path.join(d, "a", "wkdemo.lst"), errors="replace").read()
    def label(name):
        m = re.search(r"^\s*\d+\s+([0-9a-f]{4}):[ 0-9a-f]*?\s%s:" % re.escape(name), lst, re.M)
        return int(m.group(1), 16) if m else -1
    check("the run is 160 bytes, the image under $5000", label("wf_ret") - label("wf_run") == 160 and
          0 < label("WK_FONT") + 95 * 16 <= 0x5000, "wf_run %04X wf_ret %04X WK_FONT %04X" % (label("wf_run"), label("wf_ret"), label("WK_FONT")))

    want = model(script_bytes(text)); got = {}
    for tag in ("int", "uc"):
        st = os.path.join(d, tag + ".vid")
        out, err = run(tag, img, st)
        s = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
        g = got[tag] = bytes.fromhex(s.get("gram", ""))
        bad = [i for i in range(65536) if g[i] != want[i]] if len(g) == 65536 else [-1]
        check("the scene, %s" % tag, not bad and s.get("control") == "4F" and int(s.get("control2", "0"), 16) & 1 == 1,
              "%d bytes are not the model's, the first at $%04X (plane %d, row %d, column %d); control %s / %s; %s" % (
                  len(bad), bad[0] if bad else 0, (bad[0] if bad else 0) // 2048, (bad[0] if bad else 0) % 2048 // 80,
                  (bad[0] if bad else 0) % 2048 % 80, s.get("control"), s.get("control2"), err.strip()[-120:]))
    lit = sum(bin(x).count("1") for x in want[:32768])
    check("the scene: %d dots lit, the second page empty" % lit, got.get("int") == got.get("uc") and lit > 50000 and
          not any(want[32768:]) and not any(got.get("int", b"\1")[32768:]))
    if "--png" in sys.argv:
        png = sys.argv[sys.argv.index("--png") + 1]
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/vidsim.py"), "render", os.path.join(d, "int.vid"), "--png", png],
                           capture_output=True, text=True)
        check("the picture", r.returncode == 0 and os.path.exists(png), (r.stdout + r.stderr)[-300:])

    # 3. the costs
    c = os.path.join(d, "c")
    base = cost(c, [])
    line = "'The quick brown fox jumps over the lazy '"                      # 40 characters
    parts = [("the desktop: 80 x 25 cells of grey", ['1,0,0,80,25,0aah,055h'], 100000),
             ("a window of 36 x 14 cells: paper, title bar, frame", ['1,4,3,36,14,0ffh,0ffh', '1,4,3,36,1,0ffh,000h', '2,4,3,36,14'], 37000),
             ("40 characters of text", ['3,0,5,0ffh,' + line + ',0'], 6500),
             ("the whole screen of text: 2000 characters", ['3,0,%d,0ffh,%s,%s,0' % (r, line, line) for r in range(25)], 320000),
             ("the pointer, drawn once", ['4,1,44,0,180'], 2200)]
    print("  what it costs: instructions (seconds at 1 MHz from each instruction's clocks with the tree's microcode,")
    print("  software/opclocks.h; the image in the machine since 2026-10-04 takes about a quarter longer)")
    for name, scene, ceiling in parts:
        n, k = cost(c, scene)
        n -= base[0]; k -= base[1]
        print("  %-52s %7d  (%.2f s%s)" % (name, n, k / 1e6, ", %d clocks" % k if VERBOSE else ""))
        check("  under %d" % ceiling, 0 < n < ceiling, "%d instructions" % n)
    n, k = cost(c, None)
    print("  %-52s %7d  (%.2f s)" % ("the scene and the pointer's eight forms", n, k / 1e6))
    shutil.rmtree(d, ignore_errors=True)
    print("wm: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
