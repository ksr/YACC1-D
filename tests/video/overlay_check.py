#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""overlay_check.py - the proposed graphics overlay's model in tools/vidsim.py (2026-10-21): its addressing
(RA2..0:MA10..0, 6 dots a byte in bits 7..2), the CPU window and banks, the 480-entry x table, and that a plotted dot
comes out at the right place in the picture with each combine mode. No hardware; part of `make check`."""
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
check("CPU window bank 2 offset $10", ov.ram[0x810] == 0xFC and ov.dots(16, 1) == 0x3F)

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
print("overlay model: %s" % ("ALL PASS" if not fails else "%d FAIL" % fails))
sys.exit(1 if fails else 0)
