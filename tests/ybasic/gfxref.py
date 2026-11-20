# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/ybasic/gfxref.py - os/lib_gfx.c in Python (2026-11-20): the 64K of the video card V4's graphics RAM after the
same calls, with the machine's 16-bit arithmetic. The reference of tests/ybasic/run.py's graphics check: what the
assembly BASIC and the C BASIC must both have drawn."""
M = 0xFFFF
def sg(v): return (v & M) ^ 0x8000                       # the bias of a signed compare

class Gfx:
    def __init__(self): self.g = bytearray(65536); self.ink = 1
    def plot(self, x, y, ink=None):
        ink = self.ink if ink is None else ink
        x &= M; y &= M
        if x >= 640 or y >= 400: return
        a = (y & 15) * 2048 + (y >> 4) * 80 + (x >> 3); m = 0x80 >> (x & 7)
        self.g[a] = self.g[a] | m if ink == 1 else self.g[a] & ~m & 255 if ink == 0 else self.g[a] ^ m
    def point(self, x, y):
        x &= M; y &= M
        if x >= 640 or y >= 400: return 0
        return self.g[(y & 15) * 2048 + (y >> 4) * 80 + (x >> 3)] >> (7 - (x & 7)) & 1
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
    def circle(self, cx, cy, r, ink=None):
        x, y, d = 0, r & M, (1 - r) & M
        while x <= y:
            self.dot4(cx, cy, x, y, ink)
            if x != y: self.dot4(cx, cy, y, x, ink)
            if d & 0x8000: d = (d + x + x + 3) & M
            else: d = (d + x + x - y - y + 5) & M; y = (y - 1) & M
            x = (x + 1) & M
