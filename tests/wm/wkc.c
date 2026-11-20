/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* wkc.c - a C program of the window kernel under Y1/OS (2026-11-20; os/lib_wk.c, os/wm/wmk.asm). It loads the
   kernel from /lib/wmk (wk_load), draws the desktop wkmouse.asm draws - the same cells, with calls instead of a
   script - shows the pointer, and runs wk_event: a key q ends it; the left button going down inverts the cell
   under the pointer. Then the text screen back and the line X hhhh Y hhhh B hh N hh, as wkmouse prints it.
   tests/wm/run.py puts it on a copy of the disk as /bin/wkc and runs it on both emulators with the same packets. */
#include "../../os/lib_fs.c"
#include "../../os/lib_wk.c"

void say(char *s) { while (*s) { putchar(*s); s++; } }

void hex2(int v) {
    char *d;
    d = "0123456789ABCDEF";
    putchar(d[(v >> 4) & 15]); putchar(d[v & 15]);
}

void main() {
    int e, x, y;
    if (!wk_load()) { puts("?NO /LIB/WMK"); return; }
    wk_init();
    wk_fill(0, 0, 80, 25, 0xAA, 0x55);
    wk_fill(0, 0, 80, 1, 0xFF, 0xFF);
    wk_frame(0, 0, 80, 1);
    wk_text(2, 0, 0xFF, "YACC1   Mouse");
    wk_fill(14, 4, 52, 9, 0xFF, 0xFF);
    wk_fill(14, 4, 52, 1, 0xFF, 0x00);
    wk_frame(14, 4, 52, 9);
    wk_text(34, 4, 0xFF, " The mouse ");
    wk_text(16, 6, 0xFF, "Move the mouse: the arrow follows it.");
    wk_text(16, 8, 0xFF, "The left button inverts the cell under the");
    wk_text(16, 9, 0xFF, "tip of the arrow.");
    wk_text(16, 11, 0xFF, "The key q ends this.");
    wk_show();
    while (1) {
        e = wk_event();
        if (e == 1) {
            if (wk_key() == 113 || wk_key() == 81) break;
        } else if (e == 3) {
            if (wk_down() & 1) {
                wk_hide();
                x = wk_mx() >> 3; y = wk_my() >> 4;
                wk_inv(x, y, 1, 1);
                wk_show();
            }
        }
    }
    wk_done();
    say("X "); hex2(wk_mx() >> 8); hex2(wk_mx()); say(" Y "); hex2(wk_my() >> 8); hex2(wk_my());
    say(" B "); hex2(wk_buttons()); say(" N "); hex2(wk_count()); putchar(10);
}
