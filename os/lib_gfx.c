/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* lib_gfx.c - the video card V4's graphics layer from a C program (2026-11-20; docs/cards/video-v4.md sections 7
   and 9). 640 x 400 dots, one bit a dot, over or under the text; two pages of 32K. A dot (x, y), x from the left, y
   from the top, is one bit of the graphics RAM:

       the plane   y & 15                  the scan line within the row of text; chosen in control 1
       the byte    (y >> 4) * 80 + (x >> 3) in the 2K window at $D800 (the 6845's start address being 0)
       the bit     $80 >> (x & 7)           bit 7 is the left-hand dot

   Control 1 (OUT PC, port 12) cannot be read back, so gfx_c1 is its copy and every change goes through gfx_ctl():
   bits 3..0 PLANE, 4 CPAGE (the page the window reaches), 5 DPAGE (the page shown), 6 GFX-ON (the layer shown; 0 is
   also direct mode, in which the CPU has the RAM to itself), 7 XOR (text and graphics XORed, not ORed). The ROM's
   V I (the video entry, bios(0xFFBC, 0, 1)) leaves control 1 at 0: gfx_c1 starts there too.

   The ink of a dot or a line: GFX_SET, GFX_CLR, GFX_INV. Everything is unsigned, as y1cc's int is: a coordinate off
   the screen (a "negative" one is a large number) is simply not drawn, dot by dot.

   gfx_line() is the line every program of this machine draws, so its dots are defined here: with dx and dy the
   distances and the longer one the major axis, it draws major + 1 dots from (x0, y0), stepping the major coordinate
   by one each time; an error term starts at major / 2 (rounded down), grows by minor at each step, and when it
   reaches major it loses major and the minor coordinate steps. tests/video/v40/run.py draws the same in Python. */

#define GFX_W   640
#define GFX_H   400
#define GFX_WIN 0xD800
#define GFX_SET 1
#define GFX_CLR 0
#define GFX_INV 2
#define GFX_ON  0x40
#define GFX_XOR 0x80

int gfx_c1;
char gfx_bit[8] = { 128, 64, 32, 16, 8, 4, 2, 1 };

void gfx_ctl(int v) { gfx_c1 = v; outp(12, v); }

/* the layer on (1) or off (0); off is direct mode, the quick way to draw */
void gfx_show(int on) {
    if (on) gfx_ctl(gfx_c1 | GFX_ON); else gfx_ctl(gfx_c1 & 0xBF);
}

/* the page the window reaches (0 or 1), and the page shown */
void gfx_pages(int cpage, int dpage) {
    gfx_ctl((gfx_c1 & 0xCF) | ((cpage & 1) << 4) | ((dpage & 1) << 5));
}

/* every dot of the page the window reaches off: sixteen planes of 2K */
void gfx_clear() {
    int p, a;
    for (p = 0; p < 16; p++) {
        gfx_ctl((gfx_c1 & 0xF0) | p);
        for (a = GFX_WIN; a != 0xE000; a++) poke(a, 0);
    }
}

void gfx_plot(int x, int y, int ink) {
    int a, r;
    char m, b;
    if (x >= GFX_W) return;
    if (y >= GFX_H) return;
    if ((gfx_c1 & 15) != (y & 15)) gfx_ctl((gfx_c1 & 0xF0) | (y & 15));
    r = y >> 4;
    a = GFX_WIN + (r << 6) + (r << 4) + (x >> 3);
    m = gfx_bit[x & 7];
    b = peek(a);
    if (ink == GFX_SET) b = b | m;
    else if (ink == GFX_CLR) b = b & (m ^ 255);
    else b = b ^ m;
    poke(a, b);
}

/* 1 if the dot is on, 0 if it is off or off the screen */
int gfx_point(int x, int y) {
    int r;
    if (x >= GFX_W) return 0;
    if (y >= GFX_H) return 0;
    if ((gfx_c1 & 15) != (y & 15)) gfx_ctl((gfx_c1 & 0xF0) | (y & 15));
    r = y >> 4;
    if (peek(GFX_WIN + (r << 6) + (r << 4) + (x >> 3)) & gfx_bit[x & 7]) return 1;
    return 0;
}

void gfx_line(int x0, int y0, int x1, int y1, int ink) {
    int dx, dy, sx, sy, e, n;
    if (x1 >= x0) { dx = x1 - x0; sx = 1; } else { dx = x0 - x1; sx = 0; }
    if (y1 >= y0) { dy = y1 - y0; sy = 1; } else { dy = y0 - y1; sy = 0; }
    if (dx >= dy) {
        e = dx >> 1;
        for (n = dx + 1; n; n--) {
            gfx_plot(x0, y0, ink);
            if (sx) x0++; else x0--;
            e = e + dy;
            if (e >= dx) { e = e - dx; if (sy) y0++; else y0--; }
        }
    } else {
        e = dy >> 1;
        for (n = dy + 1; n; n--) {
            gfx_plot(x0, y0, ink);
            if (sy) y0++; else y0--;
            e = e + dx;
            if (e >= dy) { e = e - dy; if (sx) x0++; else x0--; }
        }
    }
}
