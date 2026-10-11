#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""vidsim.py - the video card V1.0 as a picture: what the 6845, the 2732 character generator and the dot pipeline put on
a monitor, from the card's state (2026-10-10). For debugging the card's software away from the machine, and for knowing
what the real card should show.

  vidsim.py run IMAGE.img [--go 3000] [--input TEXT] [--steps N] [--png OUT.png] [common options]
        run a program on the microcode emulator (software/ucemu/y1ucemu, the monitor in ROM, as on the bench: the image
        through the ':' loader, then G), print its console output, then draw the screen
  vidsim.py render STATE [--png OUT.png] [common options]
        draw a state file (written by either emulator with -V and Y1VIDSTATE=FILE, or by `tester`)
  vidsim.py tester [--port P] [--regs R0,R1,...] [--png OUT.png]
        read the REAL card's 2K display RAM through the bus tester (bus-driver firmware, CPU out) and draw it with the
        given CRTC table (default: the ROM's); R14/R15 are read from the card when a 6845 answers
  vidsim.py timing [--regs R0,R1,...] [--dotclock HZ]
        the raster the registers make: line and frame rates, displayed/sync positions, against a TV-rate monitor
        (15.734 kHz / 60 Hz), an IBM 5151 (MDA 18.432 kHz / 50 Hz) and an IBM 5153 (CGA 15.7 kHz / 60 Hz)
  vidsim.py chargen [--out FILE]
        write a 2732 character-generator image (4K) for this card's wiring with the font drawn here (a 2513-style
        64-character set): address = code*8 + row (code = VDATA0..5 on A3..A8, row = RA0..2), dots in D7..D3 (D7 the
        leftmost, shifted out first by the 74LS166), D2..D0 unused. Burn with `minipro -p 2732 -w FILE` if the fitted
        EPROM's contents are unknown or wrong.

Common options: --dotclock HZ (default 10e6, the ROM's assumption: the crystal is not in the tree), --chargen FILE (a
2732 image read from the card's EPROM with minipro, instead of the drawn font), --raster (draw the whole frame: the
display area, the horizontal sync in red, the vertical sync in blue, blanking grey), --nocursor, --scale N.

What is modelled (docs/cards/video.md sections 3.2-3.6): the CPU writes the IDT7134's lower 2K (A11R grounded); the 6845
scans MA0..11 (4K) from R12:R13, so a screen past the CPU's 2K shows the upper half no one can write (drawn as a hatch);
a byte's bits 0-5 pick the glyph, bit 7 is inverse video, bit 6 is not wired; 5 dots a character (IC28 divides by 5,
no gap between characters); RA0..2 only, so with R9 > 7 the glyph rows repeat; the cursor (R10 start line and blink
mode, R11 end line, R14:R15) XORs like the attribute. Not modelled: the review findings that would blank or tear a real
picture (6.1 the E one-shot, 6.2 the CHARCLOCK runt below ~16-20 MHz dot clocks, 6.3 the HC/LS levels) - the timing
report warns about 6.2.
"""
import os, re, sys, zlib, struct, argparse, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOTS = 5                     # dots per character: IC28 (74HC160) cleared at 5
ROM_TABLE = [126, 80, 98, 10, 31, 6, 24, 28, 0, 7, 0x67, 7, 0, 0, 0, 0]   # the monitor's vcrtab (monitor.asm)

# 5x7 glyphs for ASCII $20-$5F, column-major (bit 0 = top row), the classic HD44780-style shapes
_COLS = """
0000000000 00005F0000 0007000700 147F147F14 242A7F2A12 2313086462 3649552250 0005030000
001C224100 0041221C00 082A1C2A08 08083E0808 0050300000 0808080808 0060600000 2010080402
3E5149453E 00427F4000 4261514946 2141454B31 1814127F10 2745454539 3C4A494930 0171090503
3649494936 064949291E 0036360000 0056360000 0008142241 1414141414 4122140800 0201510906
324979413E 7E1111117E 7F49494936 3E41414122 7F4141221C 7F49494941 7F09090101 3E41415132
7F0808087F 00417F4100 2040413F01 7F08142241 7F40404040 7F0204027F 7F0408107F 3E4141413E
7F09090906 3E4151215E 7F09192946 4649494931 01017F0101 3F4040403F 1F2040201F 7F2018207F
6314081463 0304780403 6151494543 00007F4141 0204081020 41417F0000 0402010204 4040404040
""".split()


def font_rows(code):
    """8 rows of 5 dots (bit 4 = leftmost) for a character code 0..63 (2513 order: 00-1F = @A..Z[\\]^_, 20-3F = !..?)"""
    ascii_ = code | 0x40 if code < 0x20 else code
    cols = bytes.fromhex(_COLS[ascii_ - 0x20])
    return [sum(((cols[c] >> r) & 1) << (4 - c) for c in range(5)) for r in range(7)] + [0]


def chargen_image():
    img = bytearray(4096)
    for code in range(64):
        for r, bits in enumerate(font_rows(code)):
            img[code * 8 + r] = bits << 3              # D7..D3 = the five dots, D7 leftmost
    return bytes(img)


class State:
    def __init__(self, regs=None, ram=None, written=None):
        self.regs = list(regs or ROM_TABLE) + [0] * (18 - len(regs or ROM_TABLE))
        self.written = written or [1] * 16 + [0, 0]
        self.ram = bytearray(ram or bytes(2048))

    @staticmethod
    def load(path):
        d = {}
        for line in open(path):
            k, _, v = line.strip().partition(" ")
            d[k] = v
        regs = [int(x, 16) for x in d["regs"].split()]
        written = [int(x) for x in d.get("written", "1 " * 18).split()]
        return State(regs, bytes.fromhex(d["ram"]), written)

    def save(self, path):
        with open(path, "w") as f:
            f.write("regs " + " ".join("%02X" % r for r in self.regs) + "\n")
            f.write("written " + " ".join(str(w) for w in self.written) + "\n")
            f.write("sel 0\nram " + self.ram.hex().upper() + "\n")


def timing(regs, dotclock, out=print):
    r = regs
    char = dotclock / DOTS
    htot = r[0] + 1; lines_row = (r[9] & 0x1F) + 1
    vtot = (r[4] + 1) * lines_row + (r[5] & 0x1F)
    hfreq = char / htot; vfreq = hfreq / vtot if vtot else 0
    hsw = r[3] & 0x0F or 16
    out("dot clock %.3f MHz, %d dots a character -> character clock %.3f MHz" % (dotclock / 1e6, DOTS, char / 1e6))
    out("line: %d characters total = %.2f us -> %.3f kHz; displayed %d (%.1f us), HSYNC at %d for %d characters (%.2f us)" % (
        htot, htot / char * 1e6, hfreq / 1e3, r[1], r[1] / char * 1e6, r[2], hsw, hsw / char * 1e6))
    out("frame: %d rows x %d lines + %d = %d lines -> %.2f Hz; displayed %d rows (%d lines), VSYNC at row %d (16 lines, MC6845)" % (
        r[4] + 1, lines_row, r[5] & 0x1F, vtot, vfreq, r[6], r[6] * lines_row, r[7]))
    out("visible: %d x %d dots; interlace R8 = %d; cursor R10 = %02X (lines %d-%d, %s), R11 = %d; start R12:R13 = %04X, cursor R14:R15 = %04X" % (
        r[1] * DOTS, r[6] * lines_row, r[8] & 3, r[10], r[10] & 0x1F, r[11] & 0x1F,
        ["steady", "off", "blink 1/16", "blink 1/32"][(r[10] >> 5) & 3], r[11], (r[12] & 0x3F) << 8 | r[13], (r[14] & 0x3F) << 8 | r[15]))
    warn = []
    if r[1] >= htot: warn.append("R1 (displayed) must be less than R0+1 (total)")
    if not (r[1] <= r[2] and r[2] + hsw <= htot): warn.append("HSYNC (R2..R2+R3) should start after the display and end within the line")
    if r[6] > r[4] + 1: warn.append("R6 (rows displayed) exceeds the rows in the frame (R4+1)")
    if not (r[6] <= r[7] <= r[4] + 1): warn.append("VSYNC (R7) should come after the displayed rows and within the frame")
    if lines_row > 8: warn.append("R9+1 = %d lines a row: the card wires RA0..2 only, the glyph repeats from line 8" % lines_row)
    if dotclock < 16e6: warn.append("dot clock below ~16-20 MHz: review 6.2 - the 74LS166 load (CHARCLOCK runt) may be missed: a blank screen")
    scr = (((r[12] & 0x3F) << 8 | r[13]) + r[1] * r[6])
    if (r[12] & 0x3F) << 8 | r[13] < 2048 <= scr - 1 or scr > 2048:
        warn.append("the screen (start + R1*R6 = %d) runs past the CPU's 2K of display RAM: the rest shows the upper half no one can write" % scr)
    for name, h, v, tol in (("TV-rate monitor", 15734, 59.94, 0.03), ("IBM 5151 (MDA)", 18432, 50, 0.02), ("IBM 5153 (CGA)", 15700, 60, 0.03)):
        ok = abs(hfreq - h) / h < tol and abs(vfreq - v) / v < 0.08
        out("  %-17s %.3f kHz / %g Hz: %s" % (name, h / 1e3, v, "MATCH" if ok else "no (%.1f%% / %.1f%% off)" % ((hfreq - h) / h * 100, (vfreq - v) / v * 100)))
    for w in warn: out("  WARNING: " + w)
    return hfreq, vfreq, warn


def picture(st, chargen=None, raster=False, cursor=True):
    """-> (width, height, rows of RGB tuples) at one pixel a dot"""
    r = st.regs; cg = chargen or chargen_image()
    lines_row = (r[9] & 0x1F) + 1
    start = (r[12] & 0x3F) << 8 | r[13]; cur = (r[14] & 0x3F) << 8 | r[15]
    cs, ce, mode = r[10] & 0x1F, r[11] & 0x1F, (r[10] >> 5) & 3
    on, off, hatch = (230, 230, 230), (10, 10, 10), (90, 40, 40)
    if raster:
        W = (r[0] + 1) * DOTS; H = (r[4] + 1) * lines_row + (r[5] & 0x1F)
    else:
        W = r[1] * DOTS; H = r[6] * lines_row
    img = [[(60, 60, 60) if raster else off] * W for _ in range(H)]
    for row in range(r[6]):
        for line in range(lines_row):
            y = row * lines_row + line
            if y >= H: continue
            for col in range(r[1]):
                ma = (start + row * r[1] + col) & 0xFFF
                if ma >= 2048:
                    for d in range(DOTS):
                        img[y][col * DOTS + d] = hatch if (col * DOTS + d + y) % 4 == 0 else off
                    continue
                b = st.ram[ma]
                bits = cg[(b & 0x3F) * 8 + (line & 7)] >> 3
                inv = (b >> 7) & 1
                if cursor and ma == cur and mode != 1 and cs <= line <= ce: inv ^= 1
                for d in range(DOTS):
                    lit = ((bits >> (4 - d)) & 1) ^ inv
                    img[y][col * DOTS + d] = on if lit else off
    if raster:
        hs0, hsw = r[2] * DOTS, (r[3] & 0x0F or 16) * DOTS
        vs0 = r[7] * lines_row
        for y in range(H):
            for x in range(W):
                if hs0 <= x < hs0 + hsw: img[y][x] = (200, 40, 40)
                elif vs0 <= y < vs0 + 16: img[y][x] = (40, 60, 200)
    return W, H, img


def write_png(path, W, H, img, sx=2, sy=2):
    raw = bytearray()
    for y in range(H):
        row = bytearray([0])
        for x in range(W): row += bytes(img[y][x]) * sx
        for _ in range(sy): raw += row
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W * sx, H * sy, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


TESTCARD_TABLE = ROM_TABLE[:14] + [0x03, 0xE8]           # testcard.asm's crtab: the cursor at row 12, column 40


def testcard_ram():
    """the 2K display RAM exactly as tests/video/asm/testcard.asm leaves it"""
    ram = bytearray(b" " * 2048)
    def put(addr, text): ram[addr:addr + len(text)] = text.encode("ascii") if isinstance(text, str) else text
    put(0, " YACC1 VIDEO TEST CARD - 80 X 24 - TESTCARD.ASM"); put(80, "0123456789" * 8)
    put(160, bytes(range(64))); put(224, " CODES 00-3F"); put(240, bytes(c | 0x80 for c in range(64))); put(304, " INVERSE")
    text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG 0123456789 " * 2
    for row in range(4, 23):
        put(row * 80, "%02X*" % row + text[row - 4:row - 4 + 76] + "*")
    put(23 * 80, "ROW 23 - LAST ROW. CURSOR AT ROW 12, COLUMN 40.")
    return bytes(ram)


def text_view(st, out=print):
    r = st.regs; start = (r[12] & 0x3F) << 8 | r[13]
    out("+" + "-" * r[1] + "+")
    for row in range(r[6]):
        s = ""
        for col in range(r[1]):
            ma = (start + row * r[1] + col) & 0xFFF
            if ma >= 2048: s += "#"; continue
            c = st.ram[ma] & 0x3F
            s += chr(c | 0x40 if c < 0x20 else c)
        out("|" + s + "|")
    out("+" + "-" * r[1] + "+")


def show(st, a, label):
    cg = open(a.chargen, "rb").read() if a.chargen else None
    print("== %s" % label)
    if not any(st.written[:16]):
        print("(the program never wrote the CRTC: drawn with the ROM's table)")
        st.regs[:16] = ROM_TABLE
    timing(st.regs, a.dotclock)
    text_view(st)
    if a.png:
        W, H, img = picture(st, cg, a.raster, not a.nocursor)
        write_png(a.png, W, H, img, a.scale, a.scale * (1 if a.raster else 2))
        print("picture: %s (%d x %d dots%s)" % (a.png, W, H, ", whole raster" if a.raster else ""))


def parse_regs(s):
    v = [int(x, 0) for x in s.split(",")]
    return v + ROM_TABLE[len(v):]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["run", "render", "tester", "timing", "chargen"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--go", default="3000"); ap.add_argument("--input", default=""); ap.add_argument("--steps", type=int, default=300000000)
    ap.add_argument("--png"); ap.add_argument("--dotclock", type=float, default=10e6); ap.add_argument("--chargen")
    ap.add_argument("--raster", action="store_true"); ap.add_argument("--nocursor", action="store_true"); ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--regs"); ap.add_argument("--port", default="/dev/cu.usbserial-AB6WZCQX"); ap.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "timing":
        timing(parse_regs(a.regs) if a.regs else ROM_TABLE, a.dotclock)
    elif a.cmd == "chargen":
        out = a.out or os.path.join(ROOT, "firmware/video/chargen.bin")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(chargen_image()); print("wrote %s (4096 bytes, 64 glyphs x 8 rows in the low 512)" % out)
    elif a.cmd == "render":
        show(State.load(a.arg), a, a.arg)
    elif a.cmd == "run":
        fd, state = tempfile.mkstemp(suffix=".vid"); os.close(fd)
        env = dict(os.environ, Y1VIDSTATE=state)
        data = open(a.arg, "rb").read() + b"G" + a.go.encode() + a.input.encode().replace(b"\\r", b"\r") + b"0"
        r = subprocess.run([os.path.join(ROOT, "software/ucemu/y1ucemu"), "-x", "-m", "-V", "-l", str(a.steps)],
                           input=data, capture_output=True, env=env, timeout=1800)
        out = r.stdout.decode("latin1"); i = out.find("GO ADDRESS:")
        print("== console\n" + (out[i:] if i >= 0 else out).rstrip())
        print("== emulator: " + (r.stderr.decode("latin1").strip().splitlines() or [""])[-1])
        if os.path.getsize(state): show(State.load(state), a, "screen")
        os.unlink(state)
    elif a.cmd == "tester":
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from busdrv import BusDriver
        bd = BusDriver(a.port); bd.wait_prompt(timeout=20)
        bd.cmd("-BUS-EN", 1); bd.no_registers(); bd.cmd("-VMA", 1); bd.cmd("ADDRBUS-WR-MODE", 1); bd.cmd("DATABUS-RD-MODE", 1)
        bd.readmem(0xF000)                                  # release FORCE-ROM
        ram = bytes(bd.read_block(0xD000, 2048))
        regs = parse_regs(a.regs) if a.regs else list(ROM_TABLE)
        for reg in (14, 15):                                # readable on every 6845
            bd.cmd("DATABUS-WR-MODE", 1); bd.writemem(0xD800, reg); bd.cmd("DATABUS-RD-MODE", 1)
            regs[reg] = bd.readmem(0xD802)
        bd.cmd("-VMA", 0); bd.cmd("-BUS-EN", 0); bd.ser.close()
        st = State(regs, ram); st.save(a.out or os.path.join(tempfile.gettempdir(), "card.vid"))
        show(st, a, "the real card's RAM (R14/R15 from the card, the rest from --regs or the ROM's table)")


if __name__ == "__main__":
    main()
