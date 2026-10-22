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
  vidsim.py overlay [--overlay FILE] [--save-overlay FILE] [--gmode or|xor] [--layers L] [--tint] [--png OUT.png]
        the PROPOSED graphics overlay (--layers text,gfx|text|gfx|none) (BACKLOG "Video: graphics overlay", 2026-10-21; not built): the test card's text
        with a demo drawing (or a 16K overlay image) in a second RAM that the same 6845 scans - see "The overlay" below
  vidsim.py testcard [--card v1.0|v1.3|v2.0] [--dots N] [--regs R0,R1,...] [--png OUT.png]
        the test card (tests/video/asm/testcard.asm's layout, laid out for R1 columns) with the card's own table
  vidsim.py chargen [--card v1.0|v1.3|v2.0] [--out FILE]
        write a character-generator image for the card's wiring with the fonts drawn here (2513-style 64-character
        sets): address = code*8 + row (code = VDATA0..5 on A3..A8, row = RA0..2), D7 the leftmost dot, shifted out first
        by the 74LS166. v1.0 (firmware/video/chargen.bin, a 2732, 4K): 5 dots in D7..D3, D2..D0 unused. v1.3
        (firmware/video/chargen-v13.bin, a 2732, 4K): the 8-dot font at $000 (a 7-dot glyph in D7..D1) and the 6-dot
        font at $400 (D7..D3), A10 = the DOTS jumper; burn with `minipro -p 2732A@DIP24 -w FILE`. v2.0
        (firmware/video/chargen-v20.bin, an AT28C64B, 8K): the v1.3 image at $0000-$0FFF, A12 and A11 grounded on the
        card (the copy at $1000 is never read); burn with `minipro -p AT28C64B -u -P -w FILE`, as the ROM.

Common options: --card v1.0 (the card in the machine, the default) | v1.3 (the design with the DOTS jumper: 12 MHz, --dots 6
= 80 x 24, --dots 8 = 64 x 24, both fonts in one EPROM; BACKLOG "Video v1.3") | v2.0 (v1.3 + the graphics layer, 8-dot
mode only, see "V2.0" below; --dots 8 the default), --dotclock HZ (default the card's crystal:
v1.0 11.0592e6, Q2 fitted 2026-10-21, SV4 on 1-2; v1.3 12e6), --dots N (v1.0: 6 = IC28 a 74163 since 2026-10-18, a blank
6th dot; 5 = the drawn 74HC160; v1.3: 6 or 8), --chargen FILE (a
2732 image read from the card's EPROM with minipro, instead of the drawn font), --raster (draw the whole frame: the
display area, the horizontal sync in red, the vertical sync in blue, blanking grey), --nocursor, --scale N.

What is modelled (docs/cards/video.md sections 3.2-3.6): the CPU writes the IDT7134's lower 2K (A11R grounded); the 6845
scans MA0..11 (4K) from R12:R13, so a screen past the CPU's 2K shows the upper half no one can write (drawn as a hatch);
a byte's bits 0-5 pick the glyph, bit 7 is inverse video, bit 6 is not wired; 6 dots a character (IC28 a 74163 divides by 6,
the 6th dot blank: a gap between characters; --dots 5 for the drawn 74HC160, no gap); RA0..2 only, so with R9 > 7 the glyph rows repeat; the cursor (R10 start line and blink
mode, R11 end line, R14:R15) XORs like the attribute.

The overlay (a proposal for the next card, modelled 2026-10-21): a 16K RAM read at every character time together with the
text RAM, addressed RA2..0:MA10..0 - eight planes of 2K, plane n = scan line n of every character cell. A byte is one
cell's dots on one line from bit 7 down (the order the second 74LS166 shifts them out): 6 dots in bits 7..2 with 1..0
spare (480 x 192), or on the v1.3 card's 8-dot mode all eight bits (512 x 192 at 64 columns, cell (y >> 3) * 64 + x >> 3). Its dots are ORed (or XORed: --gmode) with the text dots before the video output, and two control bits switch each layer
on or off (TEXT-ON, GFX-ON: --layers text,gfx | text | gfx | none).
The CPU sees it through a window (default 1K: 16 banks, `Overlay.cpu_write(bank, offset, value)`); dot (x, y) is at
plane y & 7, cell (y >> 3) * columns + x / 6, mask $80 >> x % 6 (`Overlay.locate`, `x_table` = the 480-entry lookup
table a YACC1 program would use instead of dividing by 6). --overlay FILE takes any 16K image, in run/render too. Not modelled: the review findings that would blank or tear a real
picture (6.1 the E one-shot, 6.2 the CHARCLOCK runt below ~16-20 MHz dot clocks, 6.3 the HC/LS levels) - the timing
report warns about 6.2.

V2.0 (the design of 2026-10-22, BACKLOG "Video card V2.0"; `--card v2.0`): the v1.3 text card plus a graphics layer in a
32K RAM (two 16K pages), each page addressed RA2..0:MA10..0 like the overlay above, 8 dots a byte (512 x 192 at 64
columns), shown only in 8-dot mode (6-dot mode: the layer is forced off, whatever the control register says). The
control register (OUT PC, `V20Control`): bits 0-2 PLANE (the plane the CPU window $D800-$DFFF shows), 3 CPAGE (the
page it writes), 4 DPAGE (the page displayed), 5 TEXT-OFF, 6 GFX-ON, 7 XOR. On the command line --layers / --gmode set
TEXT-OFF / GFX-ON / XOR and --dpage the displayed page, or --control BYTE sets the register outright; --overlay FILE
takes a 16K page or a 32K image (both pages). `v20_cpu_address(control, addr)` is where a CPU byte at $D800-$DFFF lands.
After the design review (2026-10-22): GFX-ON = 0 is DIRECT MODE - the CPU owns the RAM (the muxes hold the CPU address,
-WE is the CPU's write strobe, reads pass through a buffer), so the window is a plain SRAM at any clock the machine runs
(test: tests/video/v20_timing.py); GFX-ON = 1 is the slot mode, time-shared with the display, which needs a CPU clock of
at most ~1.8 MHz (review V2-24). `V20Card` models the CPU side: OUT PC, IN PC (`v20_status`: bit 0 DOTS, 1 VSYNC,
2 DE, 3 TEXT-ONLY, 7..4 = 0101), the window in both modes, and the text-only build (no graphics chips: bit 3 = 1, the
window reads the floating bus, writes go nowhere).
"""
import os, re, sys, zlib, struct, argparse, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOTS = 6                     # dots per character: IC28 a 74163 (synchronous clear) since 2026-10-18; the drawn 74HC160: 5
ROM_TABLE = [116, 80, 94, 9, 31, 6, 24, 27, 0, 7, 0x67, 7, 0, 0, 0, 0]    # the monitor's vcrtab (monitor.asm): 80 x 24, 11.0592 MHz
CARD = "v1.0"                # v1.0: the card in the machine (11.0592 MHz, IC24 loads EPROM D7..D3 only, A..C grounded);
                             # v1.3: the design (12 MHz, the DOTS jumper: 6 or 8 dots, IC24 loads all eight bits, two fonts)
CARD_CLOCK = {"v1.0": 11.0592e6, "v1.3": 12e6, "v2.0": 12e6}
V13_TABLES = {6: [126, 80, 98, 10, 31, 6, 24, 27, 0, 7, 0x67, 7, 0, 0, 0, 0],    # DOTS open: /6, 2.0 MHz, 80 x 24
              8: [94, 64, 75, 8, 31, 6, 24, 27, 0, 7, 0x67, 7, 0, 0, 0, 0]}     # DOTS fitted: /8, 1.5 MHz, 64 x 24


def card_table(card=None, dots=None):
    """the 6845 table for a card (and, on v1.3, the DOTS mode): R0..R15"""
    card = card or CARD; dots = dots or DOTS
    return list(V13_TABLES[dots] if card in ("v1.3", "v2.0") else ROM_TABLE)

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


# 7x7 glyphs for the v1.3 card's 8-dot cells, in 2513 order (codes 00-3F), 7 rows each, bit 6 = the leftmost dot; drawn
# for this card (2026-10-22): row 8 and the 8th column are the gaps between characters
_FONT7 = """
3E415D555E403E 1C2241417F4141 7E41417E41417E 3E41404040413E 7C42414141427C 7F40407C40407F 7F40407C404040 3E41404F41413E
4141417F414141 3E08080808083E 1F02020242423C 42444870484442 4040404040407F 41635549414141 41615149454341 3E41414141413E
7E41417E404040 3E41414145423D 7E41417E444241 3E41403E01413E 7F080808080808 4141414141413E 41414122221408 41414149556341
41221408142241 41221408080808 7F02040810207F 1E10101010101E 40201008040201 3C04040404043C 08142241000000 0000000000007F
00000000000000 08080808080008 14141400000000 14147F147F1414 083E483E093E08 61620408102343 38444830494639 08081000000000
04081010100804 10080404040810 00492A1C2A4900 0008087F080800 000000000C0810 0000003E000000 00000000001818 01020408102040
3E43454951613E 0818280808083E 3E41011E20407F 3E41011E01413E 060A12227F0202 7F407E0101413E 1E20407E41413E 7F010204080808
3E41413E41413E 3E41413F01023C 00181800181800 00181800180810 04081020100804 00007F007F0000 10080402040810 3E410106080008
""".split()


def font7_rows(code):
    """8 rows of 7 dots (bit 6 = leftmost) for a character code 0..63, the v1.3 card's 8-dot font"""
    h = _FONT7[code & 0x3F]
    return [int(h[i:i + 2], 16) for i in range(0, 14, 2)] + [0]


def chargen_v13_image():
    """the v1.3 card's 2732: the 8-dot font at $000 (A10 = DOTS low), a 7-dot glyph in D7..D1, D0 = 0; the 6-dot font at
    $400 (A10 = DOTS high), the 5-dot glyph in D7..D3, D2..D0 = 0; address = A10 + code*8 + row; the rest $00"""
    img = bytearray(4096)
    for code in range(64):
        for r in range(8):
            img[code * 8 + r] = font7_rows(code)[r] << 1
            img[0x400 + code * 8 + r] = font_rows(code)[r] << 3
    return bytes(img)


def font_base():
    """where the fitted font starts in the EPROM: v1.3 puts DOTS on A10 (6 dots -> $400)"""
    return 0x400 if CARD in ("v1.3", "v2.0") and DOTS == 6 else 0


def load_mask():
    """the EPROM bits IC24 loads: v1.0 wires D..H to O3..O7 only (A..C grounded); v1.3 all eight"""
    return 0xF8 if CARD == "v1.0" else 0xFF


def default_chargen():
    return chargen_v13_image() if CARD in ("v1.3", "v2.0") else chargen_image()


def chargen_v20_image():
    """the V2.0 card's AT28C64B (8K): the v1.3 image at $0000-$0FFF (A12 and A11 grounded on the card, A10 = DOTS), a
    copy of it at $1000-$1FFF so the chip reads the same whatever A12 does"""
    img = chargen_v13_image()
    return img + img


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


GRAM = 16384                 # the overlay RAM: 8 planes (RA0..2) x 2K (MA0..10)


def x_table(cols=80):
    """the lookup a YACC1 program would keep for the overlay: x -> (column, mask); 480 entries for 80 columns"""
    return [(x // DOTS, 0x80 >> (x % DOTS)) for x in range(cols * DOTS)]


class Overlay:
    """the graphics overlay RAM (16K a page, address RA2..0:MA10..0, a byte's dots from bit 7: 6 or 8 of them); V2.0's
    62256 holds two pages (pages=2), `page` is the one displayed (DPAGE)"""
    def __init__(self, data=None, cols=80, start=0, window=1024, pages=1, page=0):
        self.ram = bytearray(data if data is not None else bytes(GRAM * pages))
        assert len(self.ram) in (GRAM, 2 * GRAM), "an overlay image is 16384 bytes (one page) or 32768 (two)"
        self.cols, self.start, self.window, self.page = cols, start, window, page

    def locate(self, x, y):
        """-> (address, mask) of dot (x, y): plane y & 7, cell (y >> 3) * cols + x / 6"""
        cell = (self.start + (y >> 3) * self.cols + x // DOTS) & 0x7FF
        return self.page * GRAM + ((y & 7) << 11 | cell), 0x80 >> (x % DOTS)

    def plot(self, x, y, on=True):
        if 0 <= x < self.cols * DOTS and 0 <= y < 192:
            a, m = self.locate(x, y)
            self.ram[a] = (self.ram[a] | m) if on else (self.ram[a] & ~m & 0xFF)

    def line(self, x0, y0, x1, y1):
        dx, dy = abs(x1 - x0), -abs(y1 - y0); sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1); e = dx + dy
        while True:
            self.plot(x0, y0)
            if (x0, y0) == (x1, y1): return
            e2 = 2 * e
            if e2 >= dy: e += dy; x0 += sx
            if e2 <= dx: e += dx; y0 += sy

    def ellipse(self, cx, cy, rx, ry, steps=720):
        import math
        for i in range(steps):
            t = 2 * math.pi * i / steps
            self.plot(round(cx + rx * math.cos(t)), round(cy + ry * math.sin(t)))

    def cpu_write(self, bank, offset, value):
        """a CPU write through the window: bank (the bank register) * window size + offset"""
        assert 0 <= offset < self.window and 0 <= bank < len(self.ram) // self.window
        self.ram[bank * self.window + offset] = value & 0xFF

    def dots(self, ma, line):
        """the byte the overlay gives the cell at MA on scan line `line`: its dots from bit 7 (the leftmost) down, DOTS
        of them (6: bits 7..2, 8: bits 7..0)"""
        return self.ram[(self.page * GRAM if len(self.ram) > GRAM else 0) + ((line & 7) << 11 | (ma & 0x7FF))]


class V20Control:
    """V2.0's control register (OUT PC, a 74LS273 cleared by -RESET: plane 0, page 0, text on, graphics off)"""
    def __init__(self, value=0):
        self.value = value & 0xFF

    plane = property(lambda s: s.value & 7)
    cpage = property(lambda s: (s.value >> 3) & 1)
    dpage = property(lambda s: (s.value >> 4) & 1)
    text_on = property(lambda s: not (s.value >> 5) & 1)
    gfx_on = property(lambda s: bool((s.value >> 6) & 1))
    xor = property(lambda s: bool((s.value >> 7) & 1))

    @staticmethod
    def make(plane=0, cpage=0, dpage=0, text=True, gfx=False, xor=False):
        return (plane & 7) | cpage << 3 | dpage << 4 | (0 if text else 0x20) | (0x40 if gfx else 0) | (0x80 if xor else 0)

    def layers(self):
        return tuple(n for n, on in (("text", self.text_on), ("gfx", self.gfx_on)) if on)


def v20_cpu_address(control, addr):
    """the 62256 address a CPU access to addr ($D800-$DFFF) reaches: CPAGE, PLANE, ADDR10..0 (the 74LS157s' A side)"""
    c = V20Control(control)
    assert 0xD800 <= addr <= 0xDFFF, "the V2.0 graphics window is $D800-$DFFF"
    return c.cpage * GRAM + c.plane * 2048 + (addr & 0x7FF)


SLOT_MODE_MAX_CLOCK = 1.8e6     # review V2-24: the slot mode's writes need ~1.1 us of strobe (-MEM-WR is 2 clocks)
DIRECT_MODE_MAX_CLOCK = 7.7e6   # tests/video/v20_timing.py: the one-step read window against the direct read path


def v20_status(dots=8, vsync=False, de=False, text_only=False):
    """IN PC (IC34): bit 0 DOTS (1 = 6 dots, the jumper open), 1 VSYNC, 2 DE, 3 TEXT-ONLY (1 = no graphics chips: IC44/B
    absent, R27 pulls it high), bits 7..4 = 0101 (the card ID $5x)"""
    return 0x50 | (dots == 6) | vsync << 1 | de << 2 | text_only << 3


class V20Card:
    """the CPU's view of V2.0's graphics side: the control register (OUT PC), the status (IN PC) and the window
    $D800-$DFFF. GFX-ON = 0 is direct mode (plain SRAM, no clock limit of its own below the machine's); GFX-ON = 1 is the
    slot mode (time-shared with the display: accesses need clock <= SLOT_MODE_MAX_CLOCK, faster ones are lost or read
    an earlier byte - returned as None / False here). text_only: the graphics chips are not fitted."""
    def __init__(self, clock=1e6, text_only=False, dots=8):
        self.clock, self.text_only, self.dots = clock, text_only, dots
        self.control = V20Control(0)                         # -RESET clears IC33: GFX-ON = 0, i.e. direct mode
        self.ram = bytearray(2 * GRAM)

    def out_pc(self, value):
        self.control = V20Control(value)

    def in_pc(self, vsync=False, de=False):
        return v20_status(self.dots, vsync, de, self.text_only)

    @property
    def mode(self):
        return "slot" if self.control.gfx_on else "direct"

    def _ok(self):
        return self.mode == "direct" and self.clock <= DIRECT_MODE_MAX_CLOCK or self.clock <= SLOT_MODE_MAX_CLOCK

    def write(self, addr, value):
        """a CPU write to the window; True when the byte is in the RAM"""
        if self.text_only or not self._ok():
            return False
        self.ram[v20_cpu_address(self.control.value, addr)] = value & 0xFF
        return True

    def read(self, addr):
        """a CPU read of the window: the byte, or None (text-only build: nothing drives the bus; too fast in slot mode)"""
        if self.text_only or not self._ok():
            return None
        return self.ram[v20_cpu_address(self.control.value, addr)]

    def shown(self):
        """whether the graphics layer is on the screen: GFX-ON, 8-dot mode, the chips fitted"""
        return self.control.gfx_on and self.dots == 8 and not self.text_only


def v20_display_address(control, ma, ra):
    """the 62256 address the display half reads for MA, RA: DPAGE, RA2..0, MA10..0 (the 74LS157s' B side)"""
    return V20Control(control).dpage * GRAM + ((ra & 7) << 11 | (ma & 0x7FF))


def overlay_demo(cols=80):
    """a drawing to look at: a frame, a circle (round on the monitor: dots are about twice as tall as wide), a sine wave
    and the two diagonals"""
    import math
    ov = Overlay(cols=cols); W = cols * DOTS
    ov.line(0, 0, W - 1, 0); ov.line(0, 191, W - 1, 191); ov.line(0, 0, 0, 191); ov.line(W - 1, 0, W - 1, 191)
    ov.line(0, 0, W - 1, 191); ov.line(0, 191, W - 1, 0)
    ov.ellipse(W // 2, 96, 120, 60); ov.ellipse(W // 2, 96, 121, 61)
    for x in range(W):
        ov.plot(x, round(96 - 70 * math.sin(2 * math.pi * x / W * 2)))
    return ov


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
    if CARD == "v2.0":
        out("graphics window: direct mode (GFX-ON = 0) a plain SRAM up to %.1f MHz CPU clock (the machine's own limit, "
            "~6 MHz, comes first); slot mode (GFX-ON = 1, the layer shown) up to %.1f MHz" % (
                DIRECT_MODE_MAX_CLOCK / 1e6, SLOT_MODE_MAX_CLOCK / 1e6))
    if CARD in ("v1.3", "v2.0"):
        lo = 2 if DOTS == 6 else 4                          # QC over counts 10..15 (/6) or 8..15 (/8): low 2 or 4 dots
        out("6845 clock (IC28 QC): low %d / high %d dots = %.0f / %.0f ns; EPROM time a character %.0f ns" % (
            lo, DOTS - lo, lo / dotclock * 1e9, (DOTS - lo) / dotclock * 1e9, DOTS / dotclock * 1e9))
    warn = []
    if CARD in ("v1.3", "v2.0") and 2 / dotclock * 1e9 < 160 + 20 and DOTS == 6:
        warn.append("the 6845's clock is low for only %.0f ns: little margin over the MC6845's minimum (v1.3 README)" % (2 / dotclock * 1e9))
    if r[1] >= htot: warn.append("R1 (displayed) must be less than R0+1 (total)")
    if not (r[1] <= r[2] and r[2] + hsw <= htot): warn.append("HSYNC (R2..R2+R3) should start after the display and end within the line")
    if r[6] > r[4] + 1: warn.append("R6 (rows displayed) exceeds the rows in the frame (R4+1)")
    if not (r[6] <= r[7] <= r[4] + 1): warn.append("VSYNC (R7) should come after the displayed rows and within the frame")
    if lines_row > 8: warn.append("R9+1 = %d lines a row: the card wires RA0..2 only, the glyph repeats from line 8" % lines_row)
    if dotclock < 16e6 and DOTS == 5: warn.append("dot clock below ~16-20 MHz: review 6.2 - the 74LS166 load (CHARCLOCK runt) may be missed: a blank screen")
    scr = (((r[12] & 0x3F) << 8 | r[13]) + r[1] * r[6])
    if (r[12] & 0x3F) << 8 | r[13] < 2048 <= scr - 1 or scr > 2048:
        warn.append("the screen (start + R1*R6 = %d) runs past the CPU's 2K of display RAM: the rest shows the upper half no one can write" % scr)
    for name, h, v, tol in (("TV-rate monitor", 15734, 59.94, 0.03), ("IBM 5151 (MDA)", 18432, 50, 0.02), ("IBM 5153 (CGA)", 15700, 60, 0.03)):
        ok = abs(hfreq - h) / h < tol and abs(vfreq - v) / v < 0.08
        out("  %-17s %.3f kHz / %g Hz: %s" % (name, h / 1e3, v, "MATCH" if ok else "no (%.1f%% / %.1f%% off)" % ((hfreq - h) / h * 100, (vfreq - v) / v * 100)))
    for w in warn: out("  WARNING: " + w)
    return hfreq, vfreq, warn


def picture(st, chargen=None, raster=False, cursor=True, overlay=None, gmode="or", tint=False, layers=("text", "gfx")):
    """-> (width, height, rows of RGB tuples) at one pixel a dot; overlay: an Overlay scanned with the text, gmode how
    the two meet (or / xor), layers which are switched on (the proposed control bits TEXT-ON and GFX-ON; the cursor
    belongs to the text layer), tint: overlay dots green where the text has none"""
    text_on, gfx_on = "text" in layers, "gfx" in layers
    if CARD == "v2.0" and DOTS != 8:
        gfx_on = False                                      # V2.0: GDG = dot AND GFX-ON AND NOT DOTS (8-dot mode only)
    r = st.regs; cg = chargen or default_chargen(); base, mask = font_base(), load_mask()
    lines_row = (r[9] & 0x1F) + 1
    start = (r[12] & 0x3F) << 8 | r[13]; cur = (r[14] & 0x3F) << 8 | r[15]
    cs, ce, mode = r[10] & 0x1F, r[11] & 0x1F, (r[10] >> 5) & 3
    on, off, hatch, green = (230, 230, 230), (10, 10, 10), (90, 40, 40), (90, 230, 110)
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
                bits = cg[base + (b & 0x3F) * 8 + (line & 7)] & mask
                inv = (b >> 7) & 1
                if cursor and ma == cur and mode != 1 and cs <= line <= ce: inv ^= 1
                g = overlay.dots(ma, line) if overlay else 0
                for d in range(DOTS):
                    t = (((bits >> (7 - d)) & 1) if d < 8 else 0) ^ inv
                    gd = (g >> (7 - d)) & 1 if d < 8 else 0
                    t &= text_on; gd &= gfx_on
                    lit = t ^ gd if gmode == "xor" else t | gd
                    img[y][col * DOTS + d] = (green if tint and gd and not t else on) if lit else off
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


def testcard_ram(cols=80):
    """the 2K display RAM exactly as tests/video/asm/testcard.asm leaves it (cols = 80, the standard); other widths
    lay the same card out on cols-character rows (crtc_picture.py with R1 = 64, 72 ...): with room past the 64 codes
    (76 columns or more) rows 2 and 3 also get their labels"""
    ram = bytearray(b" " * 2048)
    def put(addr, text):
        b = text.encode("ascii") if isinstance(text, str) else text
        ram[addr:addr + len(b)] = b
    put(0, (" YACC1 VIDEO TEST CARD - %d X 24 - TESTCARD.ASM" % cols)[:cols]); put(cols, ("0123456789" * 9)[:cols])
    put(2 * cols, bytes(range(64))[:cols]); put(3 * cols, bytes(c | 0x80 for c in range(64))[:cols])
    if cols >= 76: put(2 * cols + 64, " CODES 00-3F"); put(3 * cols + 64, " INVERSE")
    text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG 0123456789 " * 3
    for row in range(4, 23):
        put(row * cols, "%02X*" % row + text[row - 4:row - 4 + cols - 4] + "*")
    put(23 * cols, ("ROW 23 - LAST ROW. CURSOR AT ROW 12, COLUMN %d." % (cols // 2))[:cols])
    return bytes(ram[:2048])


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


def show(st, a, label, overlay=None):
    cg = open(a.chargen, "rb").read() if a.chargen else None
    if overlay is None and a.overlay:
        r = st.regs
        overlay = Overlay(open(a.overlay, "rb").read(), r[1], (r[12] & 0x3F) << 8 | r[13], page=a.dpage)
    print("== %s" % label)
    if not any(st.written[:16]):
        print("(the program never wrote the CRTC: drawn with the ROM's table)")
        st.regs[:16] = card_table()
    timing(st.regs, a.dotclock)
    text_view(st)
    if a.png:
        W, H, img = picture(st, cg, a.raster, not a.nocursor, overlay, a.gmode, a.tint, a.layers.split(","))
        write_png(a.png, W, H, img, a.scale, a.scale * (1 if a.raster else 2))
        print("picture: %s (%d x %d dots%s)" % (a.png, W, H, ", whole raster" if a.raster else ""))


def parse_regs(s):
    v = [int(x, 0) for x in s.split(",")]
    return v + card_table()[len(v):]


def testcard_table(table):
    """a table with the test card's cursor: row 12, the middle column"""
    cur = 12 * table[1] + table[1] // 2
    return table[:14] + [cur >> 8, cur & 0xFF]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["run", "render", "tester", "timing", "chargen", "overlay", "testcard"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--go", default="3000"); ap.add_argument("--input", default=""); ap.add_argument("--steps", type=int, default=300000000)
    ap.add_argument("--png"); ap.add_argument("--dotclock", type=float, help="the crystal (default: the card's: v1.0 11.0592 MHz, v1.3 12 MHz)")
    ap.add_argument("--chargen")
    ap.add_argument("--card", choices=["v1.0", "v1.3", "v2.0"], default="v1.0", help="v1.0 = the card in the machine (default); "
                    "v1.3 = the design with the DOTS jumper (--dots 6: 80 x 24, --dots 8: 64 x 24, 12 MHz, two fonts); "
                    "v2.0 = v1.3 + the graphics layer (8-dot mode only; --dots 8 the default)")
    ap.add_argument("--raster", action="store_true"); ap.add_argument("--nocursor", action="store_true"); ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--regs"); ap.add_argument("--port", default="/dev/cu.usbserial-AB6WZCQX"); ap.add_argument("--out")
    ap.add_argument("--dots", type=int, help="dots a character. v1.0: 6 = IC28 a 74163 (a clean CHARCLOCK and a blank 6th dot; "
                    "fitted 2026-10-18, the default), 5 = the drawn 74HC160. v1.3: 6 (DOTS open, the default) or 8 (fitted)")
    ap.add_argument("--overlay", help="a 16K overlay image (RA2..0:MA10..0, a byte's dots from bit 7: 6 or 8 of them) to draw over the text")
    ap.add_argument("--save-overlay", help="overlay: write the demo drawing's 16K image here")
    ap.add_argument("--gmode", choices=["or", "xor"], default="or", help="how the overlay meets the text")
    ap.add_argument("--layers", default="text,gfx", help="the layers switched on: text, gfx, both (default) or none "
                    "(the proposed TEXT-ON / GFX-ON control bits)")
    ap.add_argument("--tint", action="store_true", help="draw overlay dots green where the text has none (the card is monochrome)")
    ap.add_argument("--control", type=lambda v: int(v, 0), help="v2.0: the control register (OUT PC) outright: bits 0-2 "
                    "PLANE, 3 CPAGE, 4 DPAGE, 5 TEXT-OFF, 6 GFX-ON, 7 XOR (overrides --layers, --gmode, --dpage)")
    ap.add_argument("--dpage", type=int, choices=[0, 1], default=0, help="v2.0: the page displayed (DPAGE)")
    a = ap.parse_args()
    global DOTS, CARD
    CARD = a.card
    DOTS = a.dots or (8 if CARD == "v2.0" else 6)
    if DOTS not in ((5, 6) if CARD == "v1.0" else (6, 8)):
        ap.error("--dots %d does not exist on card %s" % (DOTS, CARD))
    a.dotclock = a.dotclock or CARD_CLOCK[CARD]
    if CARD == "v2.0":
        if a.control is None:
            ly = a.layers.split(",")
            a.control = V20Control.make(dpage=a.dpage, text="text" in ly, gfx="gfx" in ly, xor=a.gmode == "xor")
        c = V20Control(a.control)
        a.layers, a.gmode, a.dpage = ",".join(c.layers()) or "none", "xor" if c.xor else "or", c.dpage
    table = card_table()
    if a.cmd == "timing":
        timing(parse_regs(a.regs) if a.regs else table, a.dotclock)
    elif a.cmd == "chargen":
        out = a.out or os.path.join(ROOT, {"v1.0": "firmware/video/chargen.bin", "v1.3": "firmware/video/chargen-v13.bin",
                                           "v2.0": "firmware/video/chargen-v20.bin"}[CARD])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        img = chargen_v20_image() if CARD == "v2.0" else default_chargen()
        open(out, "wb").write(img)
        print("wrote %s (%d bytes, %s)" % (out, len(img), {
            "v1.0": "64 glyphs x 8 rows in the low 512",
            "v1.3": "the 8-dot font at $000, the 6-dot font at $400",
            "v2.0": "an AT28C64B: the 8-dot font at $000, the 6-dot font at $400, the 4K copied at $1000"}[CARD]))
    elif a.cmd == "testcard":
        tb = testcard_table(parse_regs(a.regs) if a.regs else table)
        show(State(tb, testcard_ram(tb[1])), a, "the test card, card %s, %d dots a character" % (CARD, DOTS))
    elif a.cmd == "overlay":
        tb = testcard_table(parse_regs(a.regs) if a.regs else table)
        st = State(tb, testcard_ram(tb[1]))
        ov = Overlay(open(a.overlay, "rb").read(), tb[1]) if a.overlay else overlay_demo(tb[1])
        if CARD == "v2.0":
            if len(ov.ram) == GRAM:                         # a one-page image: it goes in the displayed page
                ov.ram = bytearray(ov.ram + bytes(GRAM)) if a.dpage == 0 else bytearray(bytes(GRAM) + ov.ram)
            ov.page, ov.window = a.dpage, 2048
            print("V2.0 control register (OUT PC) = $%02X: %s" % (a.control, "layers %s, %s, displayed page %d%s" % (
                a.layers, a.gmode, a.dpage, "" if DOTS == 8 else "; 6-dot mode: the graphics layer is forced off")))
        if a.save_overlay:
            open(a.save_overlay, "wb").write(ov.ram); print("wrote %s (16384 bytes)" % a.save_overlay)
        lit = sum(bin(b >> (8 - DOTS)).count("1") for b in ov.ram)
        print("overlay: 16K = 8 planes x 2K (RA2..0:MA10..0), %d of %d dots set; CPU window %d bytes x %d banks" % (
            lit, tb[1] * DOTS * 192, ov.window, GRAM // ov.window))
        a.overlay = None
        show(st, a, "the test card with the overlay (layers %s, %s%s)" % (a.layers, a.gmode, ", tinted" if a.tint else ""), ov)
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
        regs = parse_regs(a.regs) if a.regs else list(table)
        for reg in (14, 15):                                # readable on every 6845
            bd.cmd("DATABUS-WR-MODE", 1); bd.writemem(0xD800, reg); bd.cmd("DATABUS-RD-MODE", 1)
            regs[reg] = bd.readmem(0xD802)
        bd.cmd("-VMA", 0); bd.cmd("-BUS-EN", 0); bd.ser.close()
        st = State(regs, ram); st.save(a.out or os.path.join(tempfile.gettempdir(), "card.vid"))
        show(st, a, "the real card's RAM (R14/R15 from the card, the rest from --regs or the ROM's table)")


if __name__ == "__main__":
    main()
