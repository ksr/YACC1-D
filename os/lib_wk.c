/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* lib_wk.c - the window kernel from C (2026-11-20; os/wm/wmk.asm, its interface os/wm/wkabi.inc).

   The kernel is 4K at $C000-$CFFF, above the program: /lib/wmk on the disk. wk_load() checks the signature at $C000
   ('W', 'K', the version 1) and reads the file in when it is not there - a program that is not a window program
   may have overwritten it. A program that uses it keeps below $C000 (y1cc's --os programs run on the OS stack and
   their data follows their image: the image and the data under $C000). Each function sets the kernel's parameter
   block and calls its entry with call(). Cells: x 0..79, y 0..24; the pointer in dots: 0..639, 0..399.
     wk_load()                  1 = the kernel is there (loaded if it had to be), 0 = /lib/wmk cannot be read
     wk_init() / wk_done()      the screen the kernel's (graphics on, text off, the mouse on) / the text screen back
     wk_fill(x, y, w, h, even, odd)   cells in a pattern: $FF,$FF paper, $AA,$55 grey, $FF,$00 stripes
     wk_frame(x, y, w, h)  wk_inv(x, y, w, h)  wk_text(x, y, mask, s)   ($FF: dark letters on paper)
     wk_show() / wk_hide()      the pointer
     wk_event()                 0 nothing, 1 a key (wk_key()), 2 the mouse moved, 3 a button down (wk_down()),
                                4 one up; never waits
     wk_mx(), wk_my(), wk_buttons(), wk_key(), wk_down()   what the last event left
   Needs lib_fs.c (fopen, freadn, fclose) included before it. */

#define WK_BASE   0xC000
#define WK_PARM   0xC030

int wk_ok() { return peek(WK_BASE) == 87 && peek(WK_BASE + 1) == 75 && peek(WK_BASE + 2) == 1; }

int wk_load() {
    int h, a, n;
    if (wk_ok()) return 1;
    h = fopen("/lib/wmk");
    if (h == 0) return 0;
    a = WK_BASE;
    n = freadn(h, a, 256);
    while (n) {
        a = a + n;
        if (a >= 0xD000) n = 0;
        else n = freadn(h, a, 256);
    }
    fclose(h);
    return wk_ok();
}

void wk_cells(int x, int y, int w, int h) {
    poke(WK_PARM, x); poke(WK_PARM + 1, y); poke(WK_PARM + 2, w); poke(WK_PARM + 3, h);
}
void wk_init() { call(0xC004); }
void wk_fill(int x, int y, int w, int h, int even, int odd) {
    wk_cells(x, y, w, h); poke(WK_PARM + 4, even); poke(WK_PARM + 5, odd); call(0xC007);
}
void wk_frame(int x, int y, int w, int h) { wk_cells(x, y, w, h); call(0xC00A); }
void wk_inv(int x, int y, int w, int h) { wk_cells(x, y, w, h); call(0xC00D); }
void wk_text(int x, int y, int mask, char *s) {
    poke(WK_PARM, x); poke(WK_PARM + 1, y); poke(WK_PARM + 6, mask); pokew(WK_PARM + 8, s); call(0xC010);
}
void wk_show() { call(0xC013); }
void wk_hide() { call(0xC016); }
int wk_event() { return call(0xC01C) & 255; }
void wk_done() { call(0xC01F); }
int wk_mx() { return peekw(WK_PARM + 10); }
int wk_my() { return peekw(WK_PARM + 12); }
int wk_buttons() { return peek(WK_PARM + 14); }
int wk_key() { return peek(WK_PARM + 15); }
int wk_count() { return peek(WK_PARM + 17); }
int wk_down() { return peek(WK_PARM + 18); }
