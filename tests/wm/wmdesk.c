/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* wmdesk.c - three windows on the desktop (2026-11-20; os/lib_wm.c): Notes (tag 1), Files (2), About (3), each with
   its content function. wm_event() in a loop: a key q ends it; a press in the menu bar, a close and a press in a
   window's content are counted. At the end the text screen comes back and the line
   MENU nn CLOSED nn CLICKS nn FRONT nn  (hex) is printed.
   tests/wm/run.py runs it under Y1/OS with a script of mouse packets that drags Notes by its title bar, brings About
   to the front and closes it, brings Files to the front and presses in it, and presses in the menu bar; the
   picture must then be the desktop painted afresh with the windows where the script left them. */
#include "../../os/lib_fs.c"
#include "../../os/lib_wk.c"
#include "../../os/lib_wm.c"

void notes() {
    wm_text(1, 1, "Drag a window by its title");
    wm_text(2, 1, "bar: its outline follows");
    wm_text(3, 1, "the mouse. The box at the");
    wm_text(4, 1, "left closes it. A line too long for the window is cut at its edge.");
    wm_text(6, 1, "q ends this.");
}

void files() {
    wm_text(0, 1, "Name         Size");
    wm_text(1, 1, "asm         11046");
    wm_text(2, 1, "basic       11209");
    wm_text(3, 1, "cat          1322");
    wm_text(4, 1, "kermit       9834");
    wm_text(5, 1, "make         6002");
    wm_text(6, 1, "vi           7421");
    wm_text(8, 1, "/lib/wmk     3783");
}

void about() {
    wm_text(1, 2, "YACC1 windows, version 1");
    wm_text(3, 2, "drawn in dots on the V4 card");
}

void say(char *s) { while (*s) { putchar(*s); s++; } }

void hex2(int v) {
    char *d;
    d = "0123456789ABCDEF";
    putchar(d[(v >> 4) & 15]); putchar(d[v & 15]);
}

void main() {
    int e, menu, closed, clicks;
    if (!wm_start("YACC1   File   Edit   View")) { say("?NO /LIB/WMK"); putchar(10); return; }
    wm_open(5, 3, 30, 9, "Notes", funcaddr(notes), 1);
    wm_open(28, 8, 28, 12, "Files", funcaddr(files), 2);
    wm_open(45, 4, 32, 7, "About", funcaddr(about), 3);
    menu = 0; closed = 0; clicks = 0;
    while (1) {
        e = wm_event();
        if (e == WM_KEY && (wk_key() == 113 || wk_key() == 81)) break;
        if (e == WM_MENU) menu++;
        if (e == WM_CLOSE) closed++;
        if (e == WM_CLICK) clicks++;
    }
    wm_stop();
    say("MENU "); hex2(menu); say(" CLOSED "); hex2(closed); say(" CLICKS "); hex2(clicks); say(" FRONT "); hex2(wm_front());
    putchar(10);
}
