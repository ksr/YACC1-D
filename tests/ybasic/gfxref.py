# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/ybasic/gfxref.py - os/lib_gfx.c in Python (2026-11-20): the 64K of the video card V4's graphics RAM after the
same calls, with the machine's 16-bit arithmetic. The reference of tests/ybasic/run.py's graphics check: what the
assembly BASIC and the C BASIC must both have drawn."""
import os, re
M = 0xFFFF
_LIB = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "os", "lib_gfx.c")).read()
FONT = bytes(int(v) for name in ("gfx_f%d" % k for k in range(8))                    # GTEXT's font, as the C has it
             for v in re.search(r"char %s\[\d+\] = \{(.*?)\};" % name, _LIB, re.S).group(1).split(","))
def sg(v): return (v & M) ^ 0x8000                       # the bias of a signed compare

class Gfx:
    def __init__(self): self.g = bytearray(65536); self.ink = 1; self.hi = 0     # hi: control 1's bits 7..4
    def screen(self, mode): self.hi = self.hi & 0x30 | (0x40 if mode & M else 0) | (0x80 if mode & M == 3 else 0)
    def page(self, c, d): self.hi = self.hi & 0xC0 | (c & 1) << 4 | (d & 1) << 5
    def base(self): return (self.hi >> 4 & 1) * 32768                           # the page drawn on
    def plot(self, x, y, ink=None):
        ink = self.ink if ink is None else ink
        x &= M; y &= M
        if x >= 640 or y >= 400: return
        a = self.base() + (y & 15) * 2048 + (y >> 4) * 80 + (x >> 3); m = 0x80 >> (x & 7)
        self.g[a] = self.g[a] | m if ink == 1 else self.g[a] & ~m & 255 if ink == 0 else self.g[a] ^ m
    def point(self, x, y):
        x &= M; y &= M
        if x >= 640 or y >= 400: return 0
        return self.g[self.base() + (y & 15) * 2048 + (y >> 4) * 80 + (x >> 3)] >> (7 - (x & 7)) & 1
    def line(self, x0, y0, x1, y1, ink=None):
        x0 &= M; y0 &= M; x1 &= M; y1 &= M
        dx, sx = ((x1 - x0) & M, 1) if sg(x1) >= sg(x0) else ((x0 - x1) & M, -1)
        dy, sy = ((y1 - y0) & M, 1) if sg(y1) >= sg(y0) else ((y0 - y1) & M, -1)
        if dx >= dy:
            e = dx >> 1; n = (dx + 1) & M
            while n:
                self.plot(x0, y0, ink); x0 = (x0 + sx) & M; e = (e + dy) & M
                if e >= dx: e = (e - dx) & M; y0 = (y0 + sy) & M
                n -= 1
        else:
            e = dy >> 1; n = (dy + 1) & M
            while n:
                self.plot(x0, y0, ink); y0 = (y0 + sy) & M; e = (e + dx) & M
                if e >= dy: e = (e - dy) & M; x0 = (x0 + sx) & M
                n -= 1
    def box(self, x0, y0, x1, y1, fill=0, ink=None):
        x0 &= M; y0 &= M; x1 &= M; y1 &= M
        if sg(x1) < sg(x0): x0, x1 = x1, x0
        if sg(y1) < sg(y0): y0, y1 = y1, y0
        if fill:
            if x1 & 0x8000 or y1 & 0x8000: return
            if x0 & 0x8000: x0 = 0
            if y0 & 0x8000: y0 = 0
            if x0 >= 640 or y0 >= 400: return
            x1 = min(x1, 639); y1 = min(y1, 399)
            for y in range(y0, y1 + 1): self.line(x0, y, x1, y, ink)
            return
        self.line(x0, y0, x1, y0, ink)
        if y1 == y0: return
        self.line(x0, y1, x1, y1, ink)
        y = (y0 + 1) & M
        while y != y1:
            self.plot(x0, y, ink)
            if x1 != x0: self.plot(x1, y, ink)
            y = (y + 1) & M
    def dot4(self, cx, cy, x, y, ink):
        self.plot(cx + x, cy + y, ink)
        if x: self.plot(cx - x, cy + y, ink)
        if y:
            self.plot(cx + x, cy - y, ink)
            if x: self.plot(cx - x, cy - y, ink)
    def circle(self, cx, cy, r, ink=None): self.ellipse(cx, cy, r, r, 0, ink)
    def ellipse(self, cx, cy, a, b, fill=0, ink=None):
        a &= M; b &= M
        if a > 511 or b > 511: return
        last = [M]
        def row(x, y):
            if not fill: self.dot4(cx, cy, x, y, ink)
            elif y != last[0]:
                self.line(cx - x, cy + y, cx + x, cy + y, ink)
                if y: self.line(cx - x, cy - y, cx + x, cy - y, ink)
            last[0] = y
        tb = b * b; dx = tb - tb * (a + a); tb += tb
        dy = a * a; ta = dy + dy
        er = dx + dy
        x, y, done = a, 0, False
        while not done:
            row(x, y)
            e2 = er + er
            sx, sy = e2 >= dx, dy >= e2
            if sx:
                if x == 0: done = True
                else: x -= 1
                dx += tb; er += dx
            if sy:
                y += 1; dy += ta; er += dy
        for y in range(last[0] + 1, b + 1): row(0, y)
    def text(self, x, y, size, t, ink=None):
        size &= M
        if size == 0 or size > 63: return
        for ch in t.encode("latin1"):
            if 32 <= ch < 127:
                f = FONT[(ch - 32) * 5:(ch - 32) * 5 + 5]
                for col in range(5):
                    for row in range(7):
                        if f[col] >> row & 1:
                            px, py = x + col * size, y + row * size
                            self.box(px, py, px + size - 1, py + size - 1, 1, ink)
            x += 6 * size
    def paint(self, x, y, ink=None):
        """-> 1 if the stack of 128 places ran out (the fill stopped there), else 0"""
        ink = self.ink if ink is None else ink
        x &= M; y &= M
        if x >= 640 or y >= 400: return 0
        t = self.point(x, y)
        n = 1 if ink == 1 else 0 if ink == 0 else 1 - t
        if n == t: return 0
        st = [(x, y)]; over = [False]
        def push(px, py):
            if len(st) == 128: over[0] = True
            else: st.append((px, py))
        while st:
            x, y = st.pop()
            if self.point(x, y) != t: continue
            while x and self.point(x - 1, y) == t: x -= 1
            up = dn = False
            while x < 640 and self.point(x, y) == t:
                self.plot(x, y, n)
                if y:
                    if self.point(x, y - 1) == t:
                        if not up: push(x, y - 1); up = True
                    else: up = False
                if y < 399:
                    if self.point(x, y + 1) == t:
                        if not dn: push(x, y + 1); dn = True
                    else: dn = False
                if over[0]: return 1
                x += 1
        return 0
