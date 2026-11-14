#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""overlay_check.py - the proposed graphics overlay's model in tools/vidsim.py (2026-10-21): its addressing
(RA2..0:MA10..0, 6 dots a byte in bits 7..2), the CPU window and banks, the 480-entry x table, and that a plotted dot
comes out at the right place in the picture with each combine mode; and (2026-10-22) the v1.3 card's model - 8-dot
cells (the overlay 512 x 192, a byte's eight bits), both 6845 tables' rates, the two-font EPROM image
(firmware/video/chargen-v13.bin) and a glyph drawn in each mode; the V2.0 card's control register, CPU window and
picture, and after its design review its status bit, direct mode, text-only build and 28C64 image (chargen-v20.bin);
and (2026-11-14) the V4 card's character generator image (firmware/video/chargen-v40.bin: that it is what the tool
writes from the font, its layout, its lines and blocks) and its picture: the two characters of a count, the cursor's
half, the control registers' bits, the graphics layer, the monitor's frame.
No hardware; part of `make check`."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import vidsim

fails = 0
def check(name, ok, detail=""):
    global fails; fails += not ok
    print("%-40s %s  %s" % (name, "PASS" if ok else "FAIL", detail))

vidsim.DOTS = 6
ov = vidsim.Overlay()
check("size: 8 planes x 2K", len(ov.ram) == 16384 == vidsim.GRAM)
check("dot (0,0)", ov.locate(0, 0) == (0, 0x80), "%s" % (ov.locate(0, 0),))
check("dot (5,0): last dot of cell 0", ov.locate(5, 0) == (0, 0x04))
check("dot (6,0): cell 1", ov.locate(6, 0) == (1, 0x80))
check("dot (0,1): plane 1", ov.locate(0, 1) == (0x800, 0x80))
check("dot (0,8): next text row", ov.locate(0, 8) == (80, 0x80))
check("dot (479,191): the last", ov.locate(479, 191) == (7 << 11 | 1919, 0x04), "%s" % (ov.locate(479, 191),))
xt = vidsim.x_table()
check("x table: 480 entries", len(xt) == 480 and xt[0] == (0, 0x80) and xt[479] == (79, 0x04))

ov.cpu_write(2, 0x10, 0xFC)                      # bank 2 of the 1K window = overlay address $0810: plane 1, cell 16
check("CPU window bank 2 offset $10", ov.ram[0x810] == 0xFC and ov.dots(16, 1) == 0xFC)

st = vidsim.State(vidsim.TESTCARD_TABLE, bytes(b" " * 2048))
ov = vidsim.Overlay(); ov.plot(100, 50)
W, H, img = vidsim.picture(st, cursor=False, overlay=ov)
lit = [(x, y) for y in range(H) for x in range(W) if img[y][x] != (10, 10, 10)]
check("a plotted dot on a blank screen", lit == [(100, 50)], "%s" % lit[:3])

st = vidsim.State(vidsim.TESTCARD_TABLE, bytes([0xA0]) + bytes(b" " * 2047))   # cell 0 an inverse space: all 6 dots lit
ov = vidsim.Overlay(); ov.plot(0, 0); ov.plot(5, 0)
row = lambda gm, ly=("text", "gfx"): [vidsim.picture(st, cursor=False, overlay=ov, gmode=gm, layers=ly)[2][0][x]
                                     != (10, 10, 10) for x in range(6)]
check("gmode or", row("or") == [True] * 6)
check("gmode xor", row("xor") == [False, True, True, True, True, False])
check("layers gfx only (TEXT-ON off)", row("or", ("gfx",)) == [True, False, False, False, False, True])
check("layers text only (GFX-ON off)", row("or", ("text",)) == [True] * 6 and row("xor", ("text",)) == [True] * 6)
check("layers none: blank", row("or", ()) == [False] * 6)

demo = vidsim.overlay_demo()
check("demo drawing", 1000 < sum(bin(b >> 2).count("1") for b in demo.ram) < 20000 and not any(b & 3 for b in demo.ram),
      "spare bits 1..0 untouched")
# ---- the v1.3 card: 12 MHz, the DOTS jumper
vidsim.CARD, vidsim.DOTS = "v1.3", 8
ov = vidsim.Overlay(cols=64)
check("v1.3 8 dots: dot (0,0)", ov.locate(0, 0) == (0, 0x80))
check("v1.3 8 dots: dot (7,0) last of cell 0", ov.locate(7, 0) == (0, 0x01))
check("v1.3 8 dots: dot (8,0) cell 1", ov.locate(8, 0) == (1, 0x80))
check("v1.3 8 dots: dot (511,191)", ov.locate(511, 191) == (7 << 11 | 1535, 0x01), "%s" % (ov.locate(511, 191),))
check("v1.3 8 dots: x table 512 entries", len(vidsim.x_table(64)) == 512 and vidsim.x_table(64)[511] == (63, 0x01))
st = vidsim.State(vidsim.V13_TABLES[8], bytes(b" " * 2048))
ov.plot(500, 100)
W, H, img = vidsim.picture(st, cursor=False, overlay=ov)
lit = [(x, y) for y in range(H) for x in range(W) if img[y][x] != (10, 10, 10)]
check("v1.3 8 dots: a plotted dot, 512 x 192", (W, H) == (512, 192) and lit == [(500, 100)], "%s" % lit[:3])

for d, cols in ((6, 80), (8, 64)):
    vidsim.DOTS = d
    h, v, w = vidsim.timing(vidsim.V13_TABLES[d], 12e6, out=lambda *_: None)
    check("v1.3 %d dots: %d columns, 15.7 kHz / 60 Hz" % (d, cols), vidsim.V13_TABLES[d][1] == cols and
          abs(h - 15734) / 15734 < 0.01 and abs(v - 59.94) / 59.94 < 0.01 and not [x for x in w if "monitor" in x],
          "%.3f kHz %.2f Hz" % (h / 1e3, v))

img13 = vidsim.chargen_v13_image()
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "firmware", "video", "chargen-v13.bin")
check("chargen-v13.bin = vidsim.py chargen --card v1.3", open(path, "rb").read() == img13)
check("chargen-v13 layout", all(img13[c * 8 + r] == vidsim.font7_rows(c)[r] << 1 and
                                img13[0x400 + c * 8 + r] == vidsim.font_rows(c)[r] << 3 for c in range(64) for r in range(8))
      and not any(img13[0x200:0x400]) and not any(img13[0x600:]) and not any(b & 1 for b in img13[:0x200])
      and not any(b & 7 for b in img13[0x400:0x600]), "8-dot font $000 (D0 = 0), 6-dot font $400 (D2..D0 = 0)")

for d in (6, 8):
    vidsim.DOTS = d
    st = vidsim.State(vidsim.V13_TABLES[d], bytes([0x01]) + bytes(b" " * 2047))       # code 01 = A in cell 0
    img = vidsim.picture(st, cursor=False)[2]
    want = vidsim.font7_rows(1) if d == 8 else vidsim.font_rows(1)
    width = 7 if d == 8 else 5
    got = [sum((img[r][x] != (10, 10, 10)) << (width - 1 - x) for x in range(width)) for r in range(8)]
    gap = all(img[r][x] == (10, 10, 10) for r in range(8) for x in range(width, d))
    check("v1.3 %d dots: the A in cell 0" % d, got == want and gap, "rows %s" % " ".join("%02X" % g for g in got))
# ---- the V2.0 card: the graphics layer on a time-shared 62256 (two 16K pages), the control register on port PC
vidsim.CARD, vidsim.DOTS = "v2.0", 8
C = vidsim.V20Control
check("v2.0 control reset value $00", C(0).layers() == ("text",) and C(0).plane == 0 and not C(0).xor,
      "text on, graphics off, plane 0, page 0")
check("v2.0 control bits", C(C.make(plane=5, cpage=1, dpage=1, text=False, gfx=True, xor=True)).value == 0xFD and
      (C(0xFD).plane, C(0xFD).cpage, C(0xFD).dpage, C(0xFD).layers(), C(0xFD).xor) == (5, 1, 1, ("gfx",), True))
check("v2.0 CPU window: $D800 plane 0 page 0", vidsim.v20_cpu_address(0x00, 0xD800) == 0)
check("v2.0 CPU window: $DFFF plane 7 page 1", vidsim.v20_cpu_address(0x0F, 0xDFFF) == 16384 + 7 * 2048 + 0x7FF)
check("v2.0 display: page 1, RA 3, MA 100", vidsim.v20_display_address(0x10, 100, 3) == 16384 + 3 * 2048 + 100)
ov = vidsim.Overlay(cols=64, pages=2, window=2048)
ov.plot(500, 100)                                 # page 0: plane 100 & 7 = 4, cell (100 >> 3) * 64 + 500 >> 3 = 830
a = vidsim.v20_cpu_address(C.make(plane=4), 0xD800 + 830)
check("v2.0 plot = what the CPU writes through the window", ov.ram[a] == 0x80 >> (500 & 7), "$%04X" % a)
ov.cpu_write(8 + 2, 0x10, 0xFF)                   # bank = page 1 * 8 + plane 2 (2K window): $D810 with PLANE 2, CPAGE 1
check("v2.0 cpu_write bank = CPAGE:PLANE", ov.ram[vidsim.v20_cpu_address(C.make(plane=2, cpage=1), 0xD810)] == 0xFF)
st = vidsim.State(vidsim.V13_TABLES[8], bytes(b" " * 2048))
for page, want in ((0, [(500, 100)]), (1, [(x, 2) for x in range(128, 136)])):
    ov.page = page
    W, H, img = vidsim.picture(st, cursor=False, overlay=ov)
    lit = [(x, y) for y in range(H) for x in range(W) if img[y][x] != (10, 10, 10)]
    check("v2.0 DPAGE %d displayed" % page, lit == want, "%s" % lit[:3])
vidsim.DOTS = 6                                  # 6-dot mode: GDG = dot AND GFX-ON AND NOT DOTS -> never shown
ov.page = 0
W, H, img = vidsim.picture(st, cursor=False, overlay=ov)
check("v2.0 6-dot mode: graphics forced off", not any(img[y][x] != (10, 10, 10) for y in range(H) for x in range(W)))
# ---- V2.0 after the design review (2026-10-22): the status bit, direct mode, the text-only build, the 28C64 image
check("v2.0 IN PC: ID $5x, DOTS, VSYNC, DE, TEXT-ONLY", vidsim.v20_status(8) == 0x50 and vidsim.v20_status(6) == 0x51 and
      vidsim.v20_status(8, vsync=True, de=True) == 0x56 and vidsim.v20_status(8, text_only=True) == 0x58,
      "bit 3 = 0 with the graphics chips fitted")
card = vidsim.V20Card(clock=6e6)
check("v2.0 reset: GFX-ON = 0 = direct mode", card.mode == "direct" and not card.shown())
check("v2.0 direct mode at 6 MHz: a plain SRAM", card.write(0xD812, 0xA5) and card.read(0xD812) == 0xA5 and
      card.ram[0x12] == 0xA5)
card.out_pc(C.make(plane=3, cpage=1))
check("v2.0 direct mode: CPAGE, PLANE address the window", card.write(0xD800, 0x3C) and
      card.ram[16384 + 3 * 2048] == 0x3C)
card.out_pc(C.make(gfx=True))
check("v2.0 slot mode (GFX-ON = 1) at 6 MHz: lost", card.mode == "slot" and card.write(0xD800, 1) is False and
      card.read(0xD800) is None and card.shown())
card.clock = 1e6
check("v2.0 slot mode at 1 MHz: works", card.write(0xD801, 0x77) and card.read(0xD801) == 0x77)
card.dots = 6
check("v2.0 6-dot mode: graphics never shown", not card.shown())
tcard = vidsim.V20Card(text_only=True)
check("v2.0 text-only build: IN PC bit 3 = 1, the window is empty", tcard.in_pc() & 0x08 and
      tcard.write(0xD800, 1) is False and tcard.read(0xD800) is None)
img20 = vidsim.chargen_v20_image()
path20 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "firmware", "video", "chargen-v20.bin")
check("chargen-v20.bin = vidsim.py chargen --card v2.0", open(path20, "rb").read() == img20)
check("chargen-v20 layout: 8K, the v1.3 image at $0000 and $1000", len(img20) == 8192 and
      img20[:4096] == img20[4096:] == vidsim.chargen_v13_image())

# the video card V4 (2026-11-14): its character generator - Terminus Font's bold 8 x 16 laid out for the card - and
# its picture: two characters a count, the cursor's half, the two control registers, the graphics layer
img40 = vidsim.chargen_v40_image()
path40 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "firmware", "video", "chargen-v40.bin")
check("chargen-v40.bin = vidsim.py chargen --card v4", open(path40, "rb").read() == img40)
def gl(code, flag=0): return img40[flag * 4096 + code * 16:flag * 4096 + code * 16 + 16]
def inv(b): return bytes(x ^ 0xFF for x in b)
check("chargen-v40 layout: 8K, $80-$FF inverse, cursor forms", len(img40) == 8192 and
      all(gl(c | 0x80) == inv(gl(c)) for c in range(128)) and all(gl(c, 1) == inv(gl(c)) == gl(c ^ 0x80) for c in range(256)))
bdf = vidsim.bdf_glyphs(os.path.join(vidsim.ROOT, vidsim.V4_FONT))
check("chargen-v40: ASCII is the font's, unchanged", all(gl(c) == bdf[c] for c in range(0x20, 0x7F)) and
      gl(0x41) == bytes.fromhex("00007cc6c6c6c6fec6c6c6c600000000") and gl(0x67)[13:15] == b"\x06\x7c")
check("chargen-v40: $00 $20 $7F blank, $A0 solid", gl(0) == gl(0x20) == gl(0x7F) == bytes(16) and gl(0xA0) == b"\xff" * 16)
check("chargen-v40: a frame's lines join cell to cell", gl(1)[7] == gl(1)[8] == 0xFF and set(gl(2)) == {0x18} and
      gl(0x0B) == bytes(a | b for a, b in zip(gl(1), gl(2))))
check("chargen-v40: 2 x 2 blocks are exact quarters", gl(0x0C) == b"\xf0" * 8 + bytes(8) and gl(0x0D) == b"\x0f" * 8 + bytes(8) and
      gl(0x0E) == bytes(8) + b"\xf0" * 8 and gl(0x0F) == bytes(8) + b"\x0f" * 8 and gl(0x10) == b"\xff" * 8 + bytes(8) and
      gl(0x11) == b"\xf0" * 16 and gl(0x12) == b"\xf0" * 8 + b"\x0f" * 8)
vidsim.CARD = "v4"
tb = vidsim.card_table()
check("v4 table: 40 counts = 80 characters, 25 rows of 16 lines", (tb[1], tb[6], tb[9]) == (40, 25, 15))
row, col = vidsim.V4_TESTCARD_CURSOR
st = vidsim.State(tb[:14] + [(row * 40 + col // 2) >> 8, (row * 40 + col // 2) & 0xFF], vidsim.testcard_ram_v4())
off = (10, 10, 10)
def cell(pic, r, c): return bytes(sum((pic[r * 16 + l][c * 8 + d] != off) << (7 - d) for d in range(8)) for l in range(16))
def curs(b): return b[:14] + inv(b[14:])                 # R10 / R11 = 14 / 15: the cursor's form on the last two lines
W, H, pic = vidsim.picture_v4(st, control2=2)
check("v4 picture: 640 x 400, a character is its glyph", (W, H) == (640, 400) and cell(pic, 0, 1) == gl(ord("Y")) and
      cell(pic, 4, 33) == inv(gl(ord("!"))))
check("v4 cursor: CURH = 1, the right-hand character", cell(pic, row, col) == curs(gl(st.ram[row * 80 + col])) and
      cell(pic, row, col - 1) == gl(st.ram[row * 80 + col - 1]))
pic0 = vidsim.picture_v4(st, control2=0)[2]
check("v4 cursor: CURH = 0, the left-hand one", cell(pic0, row, col - 1) == curs(gl(st.ram[row * 80 + col - 1])) and
      cell(pic0, row, col) == gl(st.ram[row * 80 + col]))
check("v4 TEXT-OFF: no text, no cursor", all(p == off for r in vidsim.picture_v4(st, control2=3)[2] for p in r))
check("v4 guns: red off, the dots are cyan", {p for r in vidsim.picture_v4(st, control2=0x22)[2] for p in r} == {off, (0, 230, 230)})
st.regs[13] = 40                                          # the start address is in counts: 40 = a row
up = vidsim.picture_v4(st, cursor=False)[2]             # the last row: bytes 2000-2047, then the ring's bytes 0-31
check("v4 start address 40: the screen a row up, the RAM a ring", cell(up, 0, 0) == gl(ord("0")) and
      all(cell(up, 24, c) == bytes(16) for c in range(49)) and cell(up, 24, 49) == gl(ord("Y")))
st.regs[13] = 0
Wf, Hf, fr = vidsim.picture_v4(st, raster=True, control2=2)
check("v4 --raster: 480 lines, the text on 42-441", (Wf, Hf) == (640, 480) and fr[42:442] == pic and fr[41][0] == fr[442][0] == (48, 48, 48))
vidsim.V4_RASTER = 70
Wf, Hf, fr = vidsim.picture_v4(vidsim.State(vidsim.card_table(), st.ram), raster=True, cursor=False)
check("v4 --raster, the 70 Hz table: 400 lines, all text", (Wf, Hf) == (640, 400) and cell(fr, 0, 1) == gl(ord("Y")))
vidsim.V4_RASTER = 60
blank = vidsim.State(tb, bytes(b" " * 2048))
gram = bytearray(65536); gram[32768 + 5 * 2048 + 83] = 0xA5      # page 1, plane 5, the place of row 1, column 3
def lit(pic): return [(x, y) for y in range(len(pic)) for x in range(640) if pic[y][x] != off]
check("v4 graphics: page DPAGE, plane = the scan line", lit(vidsim.picture_v4(blank, cursor=False, control=0x60, gram=gram)[2]) ==
      [(24, 21), (26, 21), (29, 21), (31, 21)])
check("v4 graphics: not the other page, not with GFX-ON = 0", lit(vidsim.picture_v4(blank, cursor=False, control=0x40, gram=gram)[2]) == [] and
      lit(vidsim.picture_v4(blank, cursor=False, control=0x20, gram=gram)[2]) == [])
ram = bytearray(b" " * 2048); ram[83] = ord("A")
gram = bytearray(65536)
for plane in range(16): gram[plane * 2048 + 83] = 0xFF
check("v4 layers: OR and XOR", cell(vidsim.picture_v4(vidsim.State(tb, ram), cursor=False, control=0x40, gram=gram)[2], 1, 3) == b"\xff" * 16 and
      cell(vidsim.picture_v4(vidsim.State(tb, ram), cursor=False, control=0xC0, gram=gram)[2], 1, 3) == inv(gl(ord("A"))))
vidsim.CARD, vidsim.DOTS = "v1.0", 6

print("overlay model: %s" % ("ALL PASS" if not fails else "%d FAIL" % fails))
sys.exit(1 if fails else 0)
