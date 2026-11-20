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

   The ink of a dot or a line: GFX_SET, GFX_CLR, GFX_INV (any ink but 0 and 1 inverts). A coordinate is a signed
   16-bit number in y1cc's unsigned int: a dot off the screen - to the left of it or above it too - is not drawn,
   dot by dot, so a shape may hang over any edge. A line or a shape more than 32,767 dots long or wide is not
   drawn right (it still ends).

   gfx_line() is the line every program of this machine draws, so its dots are defined here: with dx and dy the
   distances and the longer one the major axis, it draws major + 1 dots from (x0, y0), stepping the major coordinate
   by one each time; an error term starts at major / 2 (rounded down), grows by minor at each step, and when it
   reaches major it loses major and the minor coordinate steps. tests/video/v40/run.py draws the same in Python.

   gfx_box() and gfx_ellipse() draw every dot once, so the inverting ink leaves none of them as it was. A box's
   outline is its top row, its bottom row, and the two columns between them; filled, it is its rows from the top,
   cut to the screen first.

   gfx_ellipse(cx, cy, a, b) is the ellipse with the half-axes a (across) and b (up), and a circle when they are
   the same; a radius over 511 (a negative one is that) draws nothing. Its dots are those of one walk of a quarter
   of it, from (a, 0) to (0, b), reflected four ways (Zingl's ellipse; 32-bit sums, kept in two ints):
       dx = b*b - 2*a*b*b, dy = a*a, er = dx + dy, x = a, y = 0
       each step: the dot (x, y); e2 = 2*er; if e2 >= dx: x steps in (the walk ends when x is already 0),
           dx += 2*b*b, er += dx; if e2 <= dy (the e2 of before): y steps up, dy += 2*a*a, er += dy
       then, for a thin one whose walk ended below the top, the dots (0, y) up to b.
   Filled, each row is drawn once, between the reflections of the first dot the walk makes in it, which is its
   widest. A radius of 0 gives a line, both a dot.

   gfx_screen() is what is on the screen: 0 the text alone, 1 the text and the graphics, 2 the graphics alone,
   3 the two XORed. The text is switched in control 2 (OUT PF, port 15), through the ROM's copy of it (VIDC2,
   $0FF9), which the ROM's cursor writes back to the port at every move. That copy means something only once the
   ROM's video unit has been started (V I, `video init`): its flag VIDCUR ($0FF2) is 0 from a reset until then. So
   with VIDCUR 0 gfx_screen() starts the unit first, through the ROM's video entry - the 6845's table, the text
   screen cleared, both control registers 0 - and a program that says SCREEN has a picture whatever came before. */

#define GFX_W   640
#define GFX_H   400
#define GFX_WIN 0xD800
#define GFX_SET 1
#define GFX_CLR 0
#define GFX_INV 2
#define GFX_ON  0x40
#define GFX_XOR 0x80
#define GFX_VIDC2 0x0FF9
#define GFX_VIDCUR 0x0FF2
#define GFX_VIDCTL 0xFFBC

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
    if ((x1 ^ 32768) >= (x0 ^ 32768)) { dx = x1 - x0; sx = 1; } else { dx = x0 - x1; sx = 0; }
    if ((y1 ^ 32768) >= (y0 ^ 32768)) { dy = y1 - y0; sy = 1; } else { dy = y0 - y1; sy = 0; }
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

void gfx_box(int x0, int y0, int x1, int y1, int fill, int ink) {
    int t, y;
    if ((x1 ^ 32768) < (x0 ^ 32768)) { t = x0; x0 = x1; x1 = t; }
    if ((y1 ^ 32768) < (y0 ^ 32768)) { t = y0; y0 = y1; y1 = t; }
    if (fill) {
        if (x1 & 32768) return;
        if (y1 & 32768) return;
        if (x0 & 32768) x0 = 0;
        if (y0 & 32768) y0 = 0;
        if (x0 >= GFX_W) return;
        if (y0 >= GFX_H) return;
        if (x1 >= GFX_W) x1 = GFX_W - 1;
        if (y1 >= GFX_H) y1 = GFX_H - 1;
        for (y = y0; y <= y1; y++) gfx_line(x0, y, x1, y, ink);
        return;
    }
    gfx_line(x0, y0, x1, y0, ink);
    if (y1 == y0) return;
    gfx_line(x0, y1, x1, y1, ink);
    for (y = y0 + 1; y != y1; y++) {
        gfx_plot(x0, y, ink);
        if (x1 != x0) gfx_plot(x1, y, ink);
    }
}

/* the four dots (cx +- x, cy +- y), each once */
void gfx_dot4(int cx, int cy, int x, int y, int ink) {
    gfx_plot(cx + x, cy + y, ink);
    if (x) gfx_plot(cx - x, cy + y, ink);
    if (y) {
        gfx_plot(cx + x, cy - y, ink);
        if (x) gfx_plot(cx - x, cy - y, ink);
    }
}

/* 32-bit numbers for the ellipse, in two ints, the high one first: add (d may be s), negate, multiply by an int,
   and "a >= b" for two signed ones */
int ge_dx[2];
int ge_dy[2];
int ge_er[2];
int ge_e2[2];
int ge_ta[2];
int ge_tb[2];
int ge_t[2];
int ge_cx, ge_cy, ge_fill, ge_ink, ge_last;

void g32add(int *d, int *s) {
    int l;
    l = d[1] + s[1];
    d[0] = d[0] + s[0];
    if (l < s[1]) d[0] = d[0] + 1;
    d[1] = l;
}
void g32neg(int *d) {
    d[0] = d[0] ^ 65535;
    d[1] = (d[1] ^ 65535) + 1;
    if (d[1] == 0) d[0] = d[0] + 1;
}
void g32mul(int *d, int *s, int k) {
    ge_t[0] = s[0]; ge_t[1] = s[1];
    d[0] = 0; d[1] = 0;
    while (k) {
        if (k & 1) g32add(d, ge_t);
        g32add(ge_t, ge_t);
        k = k >> 1;
    }
}
int g32ge(int *a, int *b) {
    if (a[0] != b[0]) return (a[0] ^ 32768) > (b[0] ^ 32768);
    return a[1] >= b[1];
}

/* a dot of the ellipse's walk, x to the side of the centre and y above it: its four reflections - or, filled, the
   two rows it bounds, at the first dot of a row */
void gfx_erow(int x, int y) {
    if (!ge_fill) gfx_dot4(ge_cx, ge_cy, x, y, ge_ink);
    else if (y != ge_last) {
        gfx_line(ge_cx - x, ge_cy + y, ge_cx + x, ge_cy + y, ge_ink);
        if (y) gfx_line(ge_cx - x, ge_cy - y, ge_cx + x, ge_cy - y, ge_ink);
    }
    ge_last = y;
}

void gfx_ellipse(int cx, int cy, int a, int b, int fill, int ink) {
    int x, y, sx, sy, done;
    if (a > 511) return;
    if (b > 511) return;
    ge_cx = cx; ge_cy = cy; ge_fill = fill; ge_ink = ink; ge_last = 65535;
    ge_e2[0] = 0; ge_e2[1] = b;
    g32mul(ge_tb, ge_e2, b);
    g32mul(ge_dx, ge_tb, a + a);
    g32neg(ge_dx);
    g32add(ge_dx, ge_tb);
    g32add(ge_tb, ge_tb);
    ge_e2[1] = a;
    g32mul(ge_ta, ge_e2, a);
    ge_dy[0] = ge_ta[0]; ge_dy[1] = ge_ta[1];
    g32add(ge_ta, ge_ta);
    ge_er[0] = ge_dx[0]; ge_er[1] = ge_dx[1];
    g32add(ge_er, ge_dy);
    x = a; y = 0; done = 0;
    while (!done) {
        gfx_erow(x, y);
        ge_e2[0] = ge_er[0]; ge_e2[1] = ge_er[1];
        g32add(ge_e2, ge_e2);
        sx = g32ge(ge_e2, ge_dx);
        sy = g32ge(ge_dy, ge_e2);
        if (sx) {
            if (x == 0) done = 1; else x--;
            g32add(ge_dx, ge_tb);
            g32add(ge_er, ge_dx);
        }
        if (sy) {
            y++;
            g32add(ge_dy, ge_ta);
            g32add(ge_er, ge_dy);
        }
    }
    for (y = ge_last + 1; y <= b; y++) gfx_erow(0, y);
}

void gfx_screen(int mode) {
    int c;
    if (peek(GFX_VIDCUR) == 0) { bios(GFX_VIDCTL, 0, 1); gfx_c1 = 0; }
    c = peek(GFX_VIDC2) & 0xFE;
    if (mode == 2) c = c | 1;
    poke(GFX_VIDC2, c);
    outp(15, c);
    c = gfx_c1 & 0x3F;
    if (mode) c = c | GFX_ON;
    if (mode == 3) c = c | GFX_XOR;
    gfx_ctl(c);
}
