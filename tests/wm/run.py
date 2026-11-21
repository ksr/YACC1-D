#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/wm/run.py - windows in dots on the video card V4: the drawing routines of wkdemo.asm (2026-11-20).

  run.py [-v] [--png FILE]      -v: the costs' table in clocks too; --png: the scene's picture (tools/vidsim.py)
  run.py --try [--port=N]       wkmouse.asm in the browser debugger (software/y1dbg --ui web): the browser's mouse
                                moves the pointer on the emulated screen
  run.py --try desk [--port=N]  wmdesk.c (os/lib_wm.c) under Y1/OS in the browser debugger: windows to drag, bring
                                to the front and close

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
6. Windows (os/lib_wm.c): wmdesk.c under Y1/OS the same way, with a script of packets (DESK_PACKETS) that drags
   Notes by its title bar, brings About to the front and closes it, brings Files to the front and presses in it,
   and presses in the menu bar. The 64K must then be the desktop painted afresh with the windows where the script
   left them (desk_model) - what each repaint uncovered painted again exactly - and the line its counts.
7. The finder (/bin/finder, os/commands/finder.c) on a copy of the disk: / listed, bin pressed twice (opened),
   dir pressed twice (run: the finder writes /finder.sh, "/bin/dir" and "finder -w /bin", and EXECs it), a key,
   q. dir's listing of / and the finder's prompt on the console, /finder.sh as written, and the 64K the finder back in
   /bin with nothing selected and the pointer in the middle (finder_model, from the disk's own listing of /bin).
8. The editor (/bin/write, os/commands/write.c) on a copy of the disk with /note.txt: a press on its second line,
   then keys - characters, Backspace, the arrows, Enter, End, Ctrl-S, Ctrl-Q. The file must be what the edits make
   of it, and the 64K the window with that text, the cursor, "saved" in the menu bar (write_model).
9. The command line (/bin/term, os/commands/term.c) on a copy of the disk: echo hello, cd /bin, pwd and bye typed.
   /term.log must hold each prompt and line and what echo and pwd printed, and the 64K the window showing it with
   bye typed at the last prompt (term_model).
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


# wmdesk.c's script, from the pointer's start (320, 200); the arrow's tip is one dot right and below its place
DESK_PACKETS = [(-160, 148, 0), (0, 0, 1), (80, -64, 1), (0, 0, 0),          # Notes: to the front, dragged 10 right, 4 down
                (130, 48, 0), (0, 0, 1), (0, 0, 0), (0, 0, 1), (0, 0, 0),     # About: to the front, then its close box
                (30, -204, 0), (0, 0, 1), (0, 0, 0), (0, 0, 1), (0, 0, 0),    # Files: to the front, then a press in it
                (-192, 134, 0), (-192, 134, 0), (0, 0, 1), (0, 0, 0)]         # the menu bar


def desk_window(x, y, w, h, title, lines):
    """os/lib_wm.c's wm_draw as a script"""
    t = int((w - len(title) - 2) // 2)
    sc = ["1,%d,%d,%d,%d,0ffh,0ffh" % (x, y, w, h), "1,%d,%d,%d,1,0ffh,000h" % (x, y, w), "2,%d,%d,%d,%d" % (x, y, w, h),
          "1,%d,%d,1,1,0ffh,0ffh" % (x + 1, y), "2,%d,%d,1,1" % (x + 1, y),
          "3,%d,%d,0ffh,' ',0" % (x + t, y), "3,%d,%d,0ffh,'%s',0" % (x + t + 1, y, title), "3,%d,%d,0ffh,' ',0" % (x + t + 1 + len(title), y)]
    return sc + ["3,%d,%d,0ffh,'%s',0" % (x + 1 + c, y + 1 + r, s) for r, c, s in lines]


NOTES = [(1, 1, "Drag a window by its title"), (2, 1, "bar: its outline follows"), (3, 1, "the mouse. The box at the"),
         (4, 1, "left closes it. A line too long for the window is cut at its edge."[:27]), (6, 1, "q ends this.")]
FILES = [(0, 1, "Name         Size"), (1, 1, "asm         11046"), (2, 1, "basic       11209"), (3, 1, "cat          1322"),
         (4, 1, "kermit       9834"), (5, 1, "make         6002"), (6, 1, "vi           7421"), (8, 1, "/lib/wmk     3783")]


def desk_model():
    """where wmdesk's script leaves things - Notes at (15, 7) behind, Files in front, About closed, the pointer at the
    menu bar - painted afresh: -> (the 64K, the line it prints)"""
    sc = ["1,0,0,80,1,0ffh,0ffh", "2,0,0,80,1", "3,1,0,0ffh,'YACC1   File   Edit   View',0", "1,0,1,80,24,0aah,055h"]
    sc += desk_window(15, 7, 30, 9, "Notes", NOTES) + desk_window(28, 8, 28, 12, "Files", FILES)
    x, y = 320, 200
    for dx, dy, b in DESK_PACKETS: x = min(639, max(0, x + dx)); y = min(399, max(0, y - dy))
    sc.append("4,%d,%d,%d,%d" % (x >> 8, x & 255, y >> 8, y & 255))
    text = "".join("        DB %s\n" % l for l in sc) + "        DB 0\n"
    return bytes(model(script_bytes("\nscene:\n" + text + "\nscend:\n"))), "MENU 01 CLOSED 01 CLICKS 01 FRONT 02"


# the finder's script: / listed; bin pressed twice (opened); dir, the 12th row of /bin, pressed twice (run: it lists /).
# Then a key (the finder -w that comes back) and q
FINDER_PACKETS = [(-237, 146, 0), (0, 0, 1), (0, 0, 0), (0, 0, 1), (0, 0, 0),
                  (0, -176, 0), (0, 0, 1), (0, 0, 0), (0, 0, 1), (0, 0, 0)]


def finder_model(disk):
    """the finder come back in /bin, nothing selected, the pointer in the middle: -> the 64K"""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "ls", disk, "/bin"], capture_output=True, text=True)
    rows = [("..", "dir", "(up)")]
    for l in r.stdout.splitlines()[2:]:
        f = l.split()
        if len(f) < 4 or f[0].startswith("."): continue
        if "<DIR>" in l: rows.append((f[0], "dir", "folder")); continue
        kind = "program" if f[3].startswith("5000/") else "script" if f[0].endswith(".sh") else "file"
        rows.append((f[0], f[1], kind))
    sc = ["1,0,0,80,1,0ffh,0ffh", "2,0,0,80,1", "3,1,0,0ffh,'YACC1   Open   Up   Quit',0", "1,0,1,80,24,0aah,055h"]
    lines = [(0, 1, "Name           Size  Kind")] + [(i + 1, 1, ("%-13s%6s  %s" % r).ljust(47)) for i, r in enumerate(rows[:20])]
    sc += desk_window(2, 1, 50, 24, "/bin", lines)
    sc.append("4,1,64,0,200")
    text = "".join("        DB %s\n" % l for l in sc) + "        DB 0\n"
    return bytes(model(script_bytes("\nscene:\n" + text + "\nscend:\n"))), rows


def finder_check(d):
    """/bin/finder on a copy of the disk, both emulators: open /bin, run dir, a key, back in /bin, q"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], check=True, capture_output=True)
    c = os.path.join(d, "finder"); os.makedirs(c, exist_ok=True)
    disk = os.path.join(c, "disk.img"); shutil.copy(os.path.join(ROOT, "os/disk.img"), disk)
    want, rows = finder_model(disk)
    check("the finder's model: dir is the 12th row of /bin", [r[0] for r in rows].index("dir") == 11, "%r" % rows[:22])
    menv = {"Y1VID_KBD": "stdin", "Y1VID_MOUSE": ";".join("%d,%d,%d" % p for p in FINDER_PACKETS)}
    for tag in ("int", "uc"):
        run_disk = os.path.join(c, "run.img"); shutil.copy(disk, run_disk)
        st = os.path.join(c, tag + ".vid")
        if os.path.exists(st): os.remove(st)
        cmd = [EMUS[tag], "-x", "-m", "-V", "-c", run_disk, "-l", "8000000000" if tag == "uc" else "400000000"] + \
            (["-E", MON_EXIT] if tag == "uc" else [])
        env = dict(os.environ, Y1VID_CARD="v4", Y1VIDSTATE=st, **menv)
        rr = subprocess.run(cmd, input=b"O\rfinder\r qexit\r0", capture_output=True, env=env, timeout=3600)
        out = rr.stdout.decode("latin1").replace("\r", "")
        s = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
        gm = bytes.fromhex(s.get("gram", ""))
        bad = [i for i in range(65536) if gm[i] != want[i]] if len(gm) == 65536 else [-1]
        sh = subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "get", run_disk, "/finder.sh", "--out",
                             os.path.join(c, "f.sh")], capture_output=True)
        fsh = open(os.path.join(c, "f.sh")).read() if sh.returncode == 0 else None
        check("the finder, %s: /bin opened, dir run, back" % tag,
              not bad and "fruit.txt" in out and "-- a key: back to the desktop --" in out and
              fsh == "/bin/dir\nfinder -w /bin\n" and int(s.get("control2", "1"), 16) & 1 == 0 and "sh: stopped" not in out,
              "%d bytes are not the model's, the first at $%04X; /finder.sh %r; the console %r" % (
                  len(bad), bad[0] if bad else 0, fsh, out[out.find("finder"):][-500:]))


# the editor's script: a press on the second line's 7th character, then keys: XY, Backspace, two Rights, Enter, Down,
# End, !, Ctrl-S, Ctrl-Q
WRITE_TEXT = "first line\nsecond line\nthird\n"
WRITE_PACKETS = [(-131, 146, 0), (-131, 0, 0), (0, 0, 1), (0, 0, 0)]
WRITE_KEYS = b"XY\x08\x1b[C\x1b[C\r\x1b[B\x1b[F!\x13\x11"


def write_model():
    """the editor's window after the script -> (the 64K, the file it saved)"""
    text = "first line\nsecondX l\nine\nthird!\n"
    sc = ["1,0,0,80,1,0ffh,0ffh", "2,0,0,80,1", "3,1,0,0ffh,'YACC1   Save   Quit',0", "1,0,1,80,24,0aah,055h"]
    sc += desk_window(0, 1, 80, 24, "/note.txt", [(r, 0, l) for r, l in enumerate(text.split("\n")) if l])
    sc += ["3,68,0,0ffh,'saved  ',0", "5,7,5,1,1"]               # the status; the cursor after the ! (line 3, column 6)
    # no pointer: a key is handled with it hidden, and Ctrl-Q ends the editor before it is shown again
    t = "".join("        DB %s\n" % l for l in sc) + "        DB 0\n"
    return bytes(model(script_bytes("\nscene:\n" + t + "\nscend:\n"))), text


def write_check(d):
    """/bin/write on a copy of the disk, both emulators: /note.txt opened, the script's press and keys, saved"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], check=True, capture_output=True)
    c = os.path.join(d, "write"); os.makedirs(c, exist_ok=True)
    disk = os.path.join(c, "disk.img"); shutil.copy(os.path.join(ROOT, "os/disk.img"), disk)
    open(os.path.join(c, "note.txt"), "w").write(WRITE_TEXT)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "put", disk, os.path.join(c, "note.txt"), "--name", "/note.txt"],
                   check=True, capture_output=True)
    want, text = write_model()
    menv = {"Y1VID_KBD": "stdin", "Y1VID_MOUSE": ";".join("%d,%d,%d" % p for p in WRITE_PACKETS)}
    for tag in ("int", "uc"):
        run_disk = os.path.join(c, "run.img"); shutil.copy(disk, run_disk)
        st = os.path.join(c, tag + ".vid")
        if os.path.exists(st): os.remove(st)
        cmd = [EMUS[tag], "-x", "-m", "-V", "-c", run_disk, "-l", "8000000000" if tag == "uc" else "400000000"] + \
            (["-E", MON_EXIT] if tag == "uc" else [])
        env = dict(os.environ, Y1VID_CARD="v4", Y1VIDSTATE=st, **menv)
        rr = subprocess.run(cmd, input=b"O\rwrite /note.txt\r" + WRITE_KEYS + b"exit\r0", capture_output=True, env=env, timeout=3600)
        out = rr.stdout.decode("latin1").replace("\r", "")
        s = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
        gm = bytes.fromhex(s.get("gram", ""))
        bad = [i for i in range(65536) if gm[i] != want[i]] if len(gm) == 65536 else [-1]
        g = subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "get", run_disk, "/note.txt", "--out",
                            os.path.join(c, "got.txt")], capture_output=True)
        got = open(os.path.join(c, "got.txt")).read() if g.returncode == 0 else None
        check("the editor, %s: a press, keys, saved" % tag, not bad and got == text and int(s.get("control2", "1"), 16) & 1 == 0,
              "%d bytes are not the model's, the first at $%04X (row %d, column %d); the file %r; the console %r" % (
                  len(bad), bad[0] if bad else 0, (bad[0] if bad else 0) % 2048 // 80, (bad[0] if bad else 0) % 80, got,
                  out[out.find("write"):][-300:]))


TERM_KEYS = b"echo hello\rcd /bin\rpwd\rbye\r"
TERM_LOG = "/> echo hello\nhello\n/> cd /bin\n/bin> pwd\n/bin\n"


def term_model():
    """term's window when bye has been typed: the log, the prompt with bye, the cursor, the pointer in the middle"""
    sc = ["1,0,0,80,1,0ffh,0ffh", "2,0,0,80,1", "3,1,0,0ffh,'YACC1   Quit',0", "1,0,1,80,24,0aah,055h"]
    lines = TERM_LOG.split("\n")[:-1] + ["/bin> bye"]
    sc += desk_window(0, 1, 80, 24, "Terminal", [(r, 0, l) for r, l in enumerate(lines)])
    sc += ["5,%d,%d,1,1" % (1 + len(lines[-1]), 2 + len(lines) - 1), "4,1,64,0,200"]
    t = "".join("        DB %s\n" % l for l in sc) + "        DB 0\n"
    return bytes(model(script_bytes("\nscene:\n" + t + "\nscend:\n")))


def term_check(d):
    """/bin/term on a copy of the disk, both emulators: echo, cd, pwd typed and run, then bye"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], check=True, capture_output=True)
    c = os.path.join(d, "term"); os.makedirs(c, exist_ok=True)
    disk = os.path.join(c, "disk.img"); shutil.copy(os.path.join(ROOT, "os/disk.img"), disk)
    want = term_model()
    for tag in ("int", "uc"):
        run_disk = os.path.join(c, "run.img"); shutil.copy(disk, run_disk)
        st = os.path.join(c, tag + ".vid")
        if os.path.exists(st): os.remove(st)
        cmd = [EMUS[tag], "-x", "-m", "-V", "-c", run_disk, "-l", "8000000000" if tag == "uc" else "400000000"] + \
            (["-E", MON_EXIT] if tag == "uc" else [])
        env = dict(os.environ, Y1VID_CARD="v4", Y1VIDSTATE=st, Y1VID_KBD="stdin")
        rr = subprocess.run(cmd, input=b"O\rterm\r" + TERM_KEYS + b"exit\r0", capture_output=True, env=env, timeout=3600)
        out = rr.stdout.decode("latin1").replace("\r", "")
        s = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
        gm = bytes.fromhex(s.get("gram", ""))
        bad = [i for i in range(65536) if gm[i] != want[i]] if len(gm) == 65536 else [-1]
        g = subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "get", run_disk, "/term.log", "--out",
                            os.path.join(c, "log.txt")], capture_output=True)
        got = open(os.path.join(c, "log.txt")).read() if g.returncode == 0 else None
        check("the command line, %s: echo, cd, pwd, bye" % tag, not bad and got == TERM_LOG and "sh: stopped" not in out,
              "%d bytes are not the model's, the first at $%04X (row %d, column %d); the log %r; the console %r" % (
                  len(bad), bad[0] if bad else 0, (bad[0] if bad else 0) % 2048 // 80, (bad[0] if bad else 0) % 80, got,
                  out[out.find("term"):][-400:]))


def os_check(d, want, line, menv, prog="wkc", what="the same picture and line as wkmouse"):
    """PROG.c compiled for Y1/OS and put on a copy of os/disk.img as /bin/PROG; booted and run on both emulators with
    the mouse's packets: the picture and the line it must leave, the kernel loaded from the disk"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], check=True, capture_output=True)
    c = os.path.join(d, "c-" + prog); os.makedirs(c, exist_ok=True)
    asm = os.path.join(c, prog + ".asm")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "software/compiler/y1cc.py"), os.path.join(HERE, prog + ".c"), "-o", asm,
                        "--org", "0x5000", "--os"], capture_output=True, text=True)
    check("%s.c compiles" % prog, r.returncode == 0, (r.stdout + r.stderr)[-300:])
    if r.returncode: return
    shutil.copy(DEF, c); open(os.path.join(c, "rcasm.rc"), "w").write("-h\n-l\n")
    r = subprocess.run([ASM, prog, "-d=yacc1"], cwd=c, capture_output=True, text=True, errors="replace")
    top = max([int(m.group(1), 16) for m in re.finditer(r"^\s*\d+\s+([0-9a-f]{4}):", r.stdout, re.M)] or [0x10000])
    binf = os.path.join(c, prog + ".bin")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/img2bin.py"), os.path.join(c, prog + ".img"), binf, "--base", "0x5000"],
                   check=True, capture_output=True)
    check("%s: image and data end at $%04X, below the kernel" % (prog, top), "\n0 Errors" in r.stdout and top < 0xC000, r.stdout[-200:])
    disk = os.path.join(c, "disk.img"); shutil.copy(os.path.join(ROOT, "os/disk.img"), disk)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "put", disk, binf, "--name", "/bin/" + prog,
                    "--load", "0x5000", "--exec", "0x5000"], check=True, capture_output=True)
    for tag in ("int", "uc"):
        run_disk = os.path.join(c, "run.img"); shutil.copy(disk, run_disk)
        st = os.path.join(c, tag + ".vid")
        if os.path.exists(st): os.remove(st)
        cmd = [EMUS[tag], "-x", "-m", "-V", "-c", run_disk, "-l", "8000000000" if tag == "uc" else "300000000"] + \
            (["-E", MON_EXIT] if tag == "uc" else [])
        env = dict(os.environ, Y1VID_CARD="v4", Y1VIDSTATE=st, **menv)
        rr = subprocess.run(cmd, input=b"O\r" + prog.encode() + b"\rqexit\r0", capture_output=True, env=env, timeout=3600)
        out = rr.stdout.decode("latin1")
        s = dict(l.strip().partition(" ")[::2] for l in open(st)) if os.path.exists(st) else {}
        gm = bytes.fromhex(s.get("gram", ""))
        bad = [i for i in range(65536) if gm[i] != want[i]] if len(gm) == 65536 else [-1]
        check("Y1/OS: /bin/%s, %s" % (prog, tag), not bad and line in out and int(s.get("control2", "1"), 16) & 1 == 0,
              "%d bytes are not the model's, the first at $%04X; the console %r" % (len(bad), bad[0] if bad else 0,
                                                                                      out[-300:].replace("\r", "")))


def try_desk(d):
    """--try desk: wmdesk on a copy of the disk in the browser debugger, Y1/OS booted and wmdesk typed"""
    subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os"), "disk.img"], check=True)
    asm = os.path.join(d, "wmdesk.asm")
    subprocess.run([sys.executable, os.path.join(ROOT, "software/compiler/y1cc.py"), os.path.join(HERE, "wmdesk.c"), "-o", asm,
                    "--org", "0x5000", "--os"], check=True)
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    subprocess.run([ASM, "wmdesk", "-d=yacc1"], cwd=d, capture_output=True)
    binf = os.path.join(d, "wmdesk.bin")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/img2bin.py"), os.path.join(d, "wmdesk.img"), binf, "--base", "0x5000"],
                   check=True, capture_output=True)
    disk = os.path.join(d, "disk.img"); shutil.copy(os.path.join(ROOT, "os/disk.img"), disk)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools/p8xfs.py"), "put", disk, binf, "--name", "/bin/wmdesk",
                    "--load", "0x5000", "--exec", "0x5000"], check=True, capture_output=True)
    print("wmdesk in the browser debugger (Y1/OS on a copy of the disk). On its page: tick \"and the mouse\" under the\n"
          "screen, press Run (F5), click the screen (Esc gives the mouse back). Drag a window by its title bar, click\n"
          "one behind to bring it to the front, the box at a title's left closes it. \"keys to\" the PS/2 keyboard and\n"
          "q ends it. Ctrl-C here ends the debugger.")
    subprocess.run([sys.executable, os.path.join(ROOT, "software/y1dbg"), "--ui", "web", "--disk", disk,
                    "-c", "key O\\nwmdesk\\n"] + [a for a in sys.argv[1:] if a.startswith("--port=")])


def try_it():
    """--try: wkmouse.asm in the browser debugger, the browser's mouse the card's; --try desk: wmdesk under Y1/OS"""
    d = tempfile.mkdtemp(prefix="wm-try-")
    if "desk" in sys.argv:
        try: return try_desk(d)
        finally: shutil.rmtree(d, ignore_errors=True)
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
    entries = ["k_init", "wkfill", "wkframe", "wkinv", "wktext", "k_show", "k_hide", "k_script", "k_event", "k_done", "wkxframe"]
    names = ["wk_init", "wk_fill", "wk_frame", "wk_inv", "wk_text", "wk_show", "wk_hide", "wk_script", "wk_event", "wk_done",
             "wk_xframe"]
    table = all(hexmem.get(abi[n]) is not None and (hexmem[abi[n] + 1] << 8 | hexmem[abi[n] + 2]) == klabel(e)
                for n, e in zip(names, entries))
    end = klabel("WK_FONT") + 95 * 16
    check("the kernel: 'WK' 2, its table, $C000-$%04X" % (end - 1), [hexmem.get(0xC000 + i) for i in range(4)] == [87, 75, 2, 0] and
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
    # 6. windows (os/lib_wm.c): wmdesk.c, its packets, and the desktop painted afresh as the script leaves it
    g, line = desk_model()
    os_check(d, g, line, {"Y1VID_KBD": "stdin", "Y1VID_MOUSE": ";".join("%d,%d,%d" % p for p in DESK_PACKETS)},
             "wmdesk", "the desktop as it would be painted afresh")
    # 7. the finder (os/commands/finder.c, /bin/finder)
    finder_check(d)
    # 8. the editor (os/commands/write.c, /bin/write)
    write_check(d)
    # 9. the command line (os/commands/term.c, /bin/term)
    term_check(d)
    shutil.rmtree(d, ignore_errors=True)
    print("wm: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
