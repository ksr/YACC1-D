#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/wm/run.py - windows in dots on the video card V4: the drawing routines of wkdemo.asm (2026-11-20).

  run.py [-v] [--png FILE]      -v: the costs' table in clocks too; --png: the scene's picture (tools/vidsim.py)
  run.py --try [--port=N]       wkmouse.asm in the browser debugger (software/y1dbg --ui web): the browser's mouse
                                moves the pointer on the emulated screen

wkdemo.asm draws a desktop - a grey ground, a menu bar, two windows that overlap, text in both, the pointer twice
(once over the right and bottom edges) - with wk.inc's routines, which work on cells of 8 x 16 dots (its header).
wkmouse.asm moves the pointer with the card's mouse. Checks:

1. It assembles (RC/asm), with the card's font appended: firmware/video/chargen-v40.bin's codes $20-$7E as WK_FONT.
   The run of 80 "byte, next byte" pairs is 160 bytes (it is entered by an address computed from the width).
2. The scene: the script between scene: and scend: in the source is read here and drawn again in Python. The 64K of
   graphics RAM the emulator ends with must be that, byte for byte, from the instruction-level emulator and from
   the microcode one; the second page untouched; control 1 = $4F (GFX-ON, the last plane), TEXT-OFF in control 2.
3. What it costs, in instructions (the instruction-level emulator's PC histogram, -P, summed over the program): the
   script replaced by one thing at a time, less the run of an empty script. Printed, and held under a ceiling each
   (a third over the 2026-11-20 figures) so a slower routine shows.
4. The mouse: wkmouse.asm (its header) on both emulators with the keyboard on the console (Y1VID_KBD=stdin) and a
   script of fifteen packets (Y1VID_MOUSE, PACKETS below): movement both ways, past each edge of the screen (the
   pointer stops there, and at the bottom right corner is cut off), the left button pressed three times and held
   across a move, the right button. Then q. The graphics RAM must be the desktop with the three cells inverted and
   the pointer at the last place, and the program's line the same place, buttons and count: all worked out here.
   The text layer is back (control 2) and the layer hidden (control 1) when it ends. Before that, the kernel
   (os/wm/wmk.asm): it assembles to $C000-$CFFF with 'WK' 1 at $C000 and its table of entries where wkabi.inc says;
   wkmouse is a program of it, loaded beside it.
5. Under Y1/OS: wkc.c (os/lib_wk.c) compiled for the OS and put on a copy of os/disk.img, its image and data below
   $C000; booted on both emulators, the PS/2 keyboard as the console, `wkc` typed: it loads the kernel from
   /lib/wmk and must leave the same picture and print the same line as wkmouse.
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
# the pointer: the arrow's body, a word a line (bit 15 the left dot); its outline is every dot beside the body
BODY = [0, 0x4000, 0x6000, 0x7000, 0x7800, 0x7C00, 0x7E00, 0x7F00, 0x7F80, 0x7C00, 0x6C00, 0x4600, 0x0600, 0x0300, 0x0300, 0]
def outline(body):
    """the body and every dot beside it (the eight neighbours), within the 16 x 16"""
    out = []
    for r in range(16):
        m = 0
        for q in (r - 1, r, r + 1):
            if 0 <= q < 16: m |= body[q] | body[q] << 1 | body[q] >> 1
        out.append(m & 0xFFFF)
    return out


MASK = outline(BODY)
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-44s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


WM = os.path.join(ROOT, "os/wm")
sys.path.insert(0, WM)
import mkfont                                       # noqa: E402 - the kernel's font, as os/Makefile makes it


def source(scene=None, name="wkdemo"):
    """a program here (or the kernel, name "wmk"); scene = other lines for the script (the costs' runs)"""
    s = open(os.path.join(WM if name == "wmk" else HERE, name + ".asm")).read()
    if scene is not None:
        i = s.index("\nscene:"); j = s.index("\nscend:")
        s = s[:i] + "\nscene:" + "".join("\n        DB " + l for l in scene) + "\n        DB 0" + s[j:]
    return s


def assemble(d, text):
    os.makedirs(d, exist_ok=True)
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n-l\n")
    for f in ("wk.inc", "wkabi.inc"): shutil.copy(os.path.join(WM, f), d)
    open(os.path.join(d, "wkfont.inc"), "w").write(mkfont.text())
    open(os.path.join(d, "wkdemo.asm"), "w").write(text)
    r = subprocess.run([ASM, "wkdemo", "-d=yacc1"], cwd=d, capture_output=True, text=True, errors="replace")
    img = os.path.join(d, "wkdemo.img")
    ok = os.path.exists(img) and "\n0 Errors" in r.stdout
    open(os.path.join(d, "wkdemo.lst"), "w").write(r.stdout)                 # -l: the listing is what it prints
    return (open(img, "rb").read() if ok else None), r.stdout[-600:]


def run(tag, img, st=None, prof=None, keys=b"", env=None):
    cmd = [EMUS[tag], "-x", "-m", "-V", "-l", "4000000000" if tag == "uc" else "40000000"] + \
        (["-E", MON_EXIT] if tag == "uc" else []) + (["-P", prof] if prof else [])
    env = dict(os.environ, Y1VID_CARD="v4", **({"Y1VIDSTATE": st} if st else {}), **(env or {}))
    if st and os.path.exists(st): os.remove(st)
    r = subprocess.run(cmd, input=img + b"G3000" + keys + b"0", capture_output=True, env=env, timeout=3600)
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


def at(p, r, c): return p * 2048 + r * 80 + c


def pointer(g, px, py):
    """wkpon: the arrow with its top left dot at (px, py) - the outline's dots lit, the body's dark, the others as
    they were -> what was under it, for pointer_off: [(place, byte)]"""
    under = []
    for r in range(16):
        yy = py + r
        if yy >= 400: break
        m = MASK[r] << 8 >> (px & 7); o = (MASK[r] & ~BODY[r]) << 8 >> (px & 7)   # 24 bits: three bytes from column px >> 3
        for k in range(3):
            c = (px >> 3) + k
            if c < 80:
                a = at(yy & 15, yy >> 4, c); under.append((a, g[a]))
                g[a] = g[a] & ~(m >> (16 - 8 * k)) & 255 | o >> (16 - 8 * k) & 255
    return under


def pointer_off(g, under):
    for a, v in under: g[a] = v


def invert(g, x, y, w, h):
    for p in range(16):
        for r in range(y, y + h):
            for c in range(x, x + w): g[at(p, r, c)] ^= 0xFF


def model(b):
    """the script drawn in Python -> the 64K of graphics RAM (page 0: plane * 2048 + row * 80 + column)"""
    g = bytearray(65536); i = 0; under = []
    while b[i]:
        op = b[i]; i += 1
        if op == 6: pointer_off(g, under)
        elif op in (1, 2, 5):
            x, y, w, h = b[i:i + 4]; i += 4
            if op == 5: invert(g, x, y, w, h)
            elif op == 1:
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
            under = pointer(g, px, py)
    return g


# wkmouse.asm's script of packets: (across, up, buttons), from the middle of the screen
PACKETS = [(10, 5, 0), (-30, -20, 0), (0, 0, 1), (4, 0, 1), (0, 0, 0), (-255, 255, 0), (-255, 0, 0), (0, 0, 1), (0, 0, 0),
           (255, -255, 0), (255, -255, 0), (255, -255, 0), (0, 0, 1), (0, 0, 0), (-100, 50, 2)]


def mouse_model(g):
    """the packets on wkmouse's desktop -> (x, y, buttons, packets): the pointer moved, a cell inverted at each press"""
    x, y, bt = 320, 200, 0
    for dx, dy, b in PACKETS:
        x = min(639, max(0, x + dx)); y = min(399, max(0, y - dy))
        if b & 1 and not bt & 1: invert(g, x >> 3, y >> 4, 1, 1)
        bt = b
    pointer(g, x, y)
    return x, y, bt, len(PACKETS)


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


def os_check(d, want, line, menv):
    """wkc.c compiled for Y1/OS and put on a copy of os/disk.img as /bin/wkc; booted and run on both emulators with
    the mouse's packets: the same picture and line as wkmouse, the kernel loaded from the disk"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], check=True, capture_output=True)
    c = os.path.join(d, "c"); os.makedirs(c, exist_ok=True)
    asm = os.path.join(c, "wkc.asm")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "software/compiler/y1cc.py"), os.path.join(HERE, "wkc.c"), "-o", asm,
                        "--org", "0x5000", "--os"], capture_output=True, text=True)
    check("wkc.c compiles", r.returncode == 0, (r.stdout + r.stderr)[-300:])
    if r.returncode: return
    shutil.copy(DEF, c); open(os.path.join(c, "rcasm.rc"), "w").write("-h\n-l\n")
    r = subprocess.run([ASM, "wkc", "-d=yacc1"], cwd=c, capture_output=True, text=True, errors="replace")
    top = max([int(m.group(1), 16) for m in re.finditer(r"^\s*\d+\s+([0-9a-f]{4}):", r.stdout, re.M)] or [0x10000])
    binf = os.path.join(c, "wkc.bin")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/img2bin.py"), os.path.join(c, "wkc.img"), binf, "--base", "0x5000"],
                   check=True, capture_output=True)
    check("wkc: image and data end at $%04X, below the kernel" % top, "\n0 Errors" in r.stdout and top < 0xC000, r.stdout[-200:])
    disk = os.path.join(c, "disk.img"); shutil.copy(os.path.join(ROOT, "os/disk.img"), disk)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "put", disk, binf, "--name", "/bin/wkc",
                    "--load", "0x5000", "--exec", "0x5000"], check=True, capture_output=True)
    for tag in ("int", "uc"):
        run_disk = os.path.join(c, "run.img"); shutil.copy(disk, run_disk)
        st = os.path.join(c, tag + ".vid")
        if os.path.exists(st): os.remove(st)
        cmd = [EMUS[tag], "-x", "-m", "-V", "-c", run_disk, "-l", "8000000000" if tag == "uc" else "300000000"] + \
            (["-E", MON_EXIT] if tag == "uc" else [])
        env = dict(os.environ, Y1VID_CARD="v4", Y1VIDSTATE=st, **menv)
        rr = subprocess.run(cmd, input=b"O\rwkc\rqexit\r0", capture_output=True, env=env, timeout=3600)
        out = rr.stdout.decode("latin1")
        s = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
        gm = bytes.fromhex(s.get("gram", ""))
        bad = [i for i in range(65536) if gm[i] != want[i]] if len(gm) == 65536 else [-1]
        check("Y1/OS: /bin/wkc with /lib/wmk, %s" % tag, not bad and line in out and int(s.get("control2", "1"), 16) & 1 == 0,
              "%d bytes are not the model's, the first at $%04X; the console %r" % (len(bad), bad[0] if bad else 0,
                                                                                      out[-300:].replace("\r", "")))


def try_it():
    """--try: wkmouse.asm in the browser debugger, the browser's mouse the card's"""
    d = tempfile.mkdtemp(prefix="wm-try-")
    kimg, msg = assemble(os.path.join(d, "k"), source(name="wmk"))
    if kimg is None: sys.exit("os/wm/wmk.asm did not assemble: " + msg)
    img, msg = assemble(d, source(name="wkmouse"))
    if img is None: sys.exit("wkmouse.asm did not assemble: " + msg)
    open(os.path.join(d, "wkdemo.img"), "wb").write(kimg + img)
    print("wkmouse in the browser debugger. On its page: tick \"and the mouse\" under the screen, press Run (F5), click the\n"
          "screen (the pointer is now the card's mouse; Esc gives it back). \"keys to\" the PS/2 keyboard and q ends the\n"
          "program. Ctrl-C here ends the debugger.")
    try:
        subprocess.run([sys.executable, os.path.join(ROOT, "software/y1dbg"), "--ui", "web", "-f", os.path.join(d, "wkdemo.img"),
                        "-c", "key G3000"] + [a for a in sys.argv[1:] if a.startswith("--port=")])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if "--try" in sys.argv: return try_it()
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

    want = bytes(model(script_bytes(text))); got = {}
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
             ("the pointer drawn", ['4,1,44,0,180'], 3000),
             ("the pointer drawn and taken away: a move", ['4,1,44,0,180', '6'], 5200)]
    print("  what it costs: instructions (seconds at 1 MHz from each instruction's clocks with the tree's microcode,")
    print("  software/opclocks.h; the image in the machine since 2026-10-04 takes about a quarter longer)")
    for name, scene, ceiling in parts:
        n, k = cost(c, scene)
        n -= base[0]; k -= base[1]
        print("  %-52s %7d  (%.2f s%s)" % (name, n, k / 1e6, ", %d clocks" % k if VERBOSE else ""))
        check("  under %d" % ceiling, 0 < n < ceiling, "%d instructions" % n)
    n, k = cost(c, None)
    print("  %-52s %7d  (%.2f s)" % ("the scene and the pointer's eight forms", n, k / 1e6))

    # 4. the kernel, and the mouse through it
    kimg, msg = assemble(os.path.join(d, "k"), source(name="wmk"))
    check("os/wm/wmk.asm assembles", kimg is not None, msg)
    if kimg is None: sys.exit(1)
    klst = open(os.path.join(d, "k", "wkdemo.lst"), errors="replace").read()
    def klabel(name):
        m = re.search(r"^\s*\d+\s+([0-9a-f]{4}):[ 0-9a-f]*?\s%s:" % re.escape(name), klst, re.M)
        return int(m.group(1), 16) if m else -1
    abi = dict((n, int(v, 16)) for n, v in re.findall(r"^(\w+):\s+EQU\s+0([0-9a-f]+)h", open(os.path.join(WM, "wkabi.inc")).read(), re.M))
    hexmem = {}
    for l in kimg.decode().splitlines():
        if l.startswith(":") and l[7:9] == "00":
            a = int(l[3:7], 16)
            for k2 in range(int(l[1:3], 16)): hexmem[a + k2] = int(l[9 + 2 * k2:11 + 2 * k2], 16)
    entries = ["k_init", "wkfill", "wkframe", "wkinv", "wktext", "k_show", "k_hide", "k_script", "k_event", "k_done"]
    names = ["wk_init", "wk_fill", "wk_frame", "wk_inv", "wk_text", "wk_show", "wk_hide", "wk_script", "wk_event", "wk_done"]
    table = all(hexmem.get(abi[n]) is not None and (hexmem[abi[n] + 1] << 8 | hexmem[abi[n] + 2]) == klabel(e)
                for n, e in zip(names, entries))
    end = klabel("WK_FONT") + 95 * 16
    check("the kernel: 'WK' 1, its table, $C000-$%04X" % (end - 1), [hexmem.get(0xC000 + i) for i in range(4)] == [87, 75, 1, 0] and
          table and min(hexmem) == 0xC000 and 0xC050 <= klabel("k_init") and end <= 0xD000 and
          not any(0xC030 <= a < 0xC050 for a in hexmem), "end $%04X, table %r" % (end, table))
    mtext = source(name="wkmouse")
    mimg, msg = assemble(os.path.join(d, "m"), mtext)
    check("wkmouse.asm assembles", mimg is not None, msg)
    if mimg is not None:
        mimg = kimg + mimg
        g = model(script_bytes(mtext)); x, y, bt, n = mouse_model(g)
        line = "X %04X Y %04X B %02X N %02X" % (x, y, bt, n)
        menv = {"Y1VID_KBD": "stdin", "Y1VID_MOUSE": ";".join("%d,%d,%d" % p for p in PACKETS)}
        for tag in ("int", "uc"):
            st = os.path.join(d, tag + ".m.vid")
            out, err = run(tag, mimg, st, keys=b"q", env=menv)
            s = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
            gm = bytes.fromhex(s.get("gram", ""))
            bad = [i for i in range(65536) if gm[i] != g[i]] if len(gm) == 65536 else [-1]
            check("the mouse, %s: %s" % (tag, line), not bad and line in out and int(s.get("control2", "1"), 16) & 1 == 0 and
                  s.get("control", "")[:1] == "0",
                  "%d bytes are not the model's, the first at $%04X; the console %r; control %s / %s" % (
                      len(bad), bad[0] if bad else 0, out[-60:], s.get("control"), s.get("control2")))
    # 5. under Y1/OS: the kernel from /lib/wmk, a C program of it (wkc.c, os/lib_wk.c)
    if mimg is not None: os_check(d, g, line, menv)
    shutil.rmtree(d, ignore_errors=True)
    print("wm: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
