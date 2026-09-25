/* video.c - the video card from Y1/OS (2026-09-25): mirror the console on it, clear it, start it.
     video          status: card found or not, mirroring, the CRTC cursor, the text cursor
     video on       mirror the console on the screen (every byte the ROM's CHAROUT sends, so the OS, the shell and
                    every program: what goes to a > file or a pipe is not console output and is not mirrored)
     video off      stop mirroring
     video clear    clear the screen, cursor home
     video init     program the CRTC's registers (the ROM's table), clear, home - the monitor's V I
     video probe    test $D000 again (after fitting the card without a reset)
     video -h       usage
   All of it is the ROM's (firmware/monitor/monitor.asm, the video unit): the flags at VIDPRES/VIDMIR ($0FF0/$0FF1)
   and the video entry VIDCTL ($FFBC) of ROM 2026-09-25 and later; on an older ROM (no JSR at $FFBC) video says so and
   changes nothing. The OS kernels need nothing for it: their console output is CHAROUT. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"

char *w;

int word(char *s) {                             /* w starts with the word s (case-insensitive), then a blank/end */
    char *p; int c;
    p = w;
    while (*s) {
        c = *p;
        if (c >= 'a' && c <= 'z') c = c - 32;
        if (c != *s) return 0;
        p++; s++;
    }
    return *p == 0 || *p == ' ';
}

void onoff(int v) { if (v) putstr("on"); else putstr("off"); }

void status() {
    if (peek(VIDPRES) == 1) putstr("video card found at D000"); else putstr("no video card at D000");
    putstr(", mirror "); onoff(peek(VIDMIR));
    putstr(", CRTC cursor "); onoff(peek(VIDCUR));
    putstr(", cursor row "); putnum(peek(VROW)); putstr(" col "); putnum(peek(VCOL));
    putchar(10);
}

void main() {
    w = argstr();
    while (*w == ' ') w++;
    if (w[0] == '-' && (w[1] == 'h' || w[1] == 'H')) {
        puts("usage: video [on|off|clear|init|probe]   the video card (no argument: status)"); return;
    }
    if (peek(VIDCTL) != VIDSIG) { eputs("video: this ROM has no video driver (ROM 2026-09-25 or later)"); return; }
    if (*w == 0) { status(); return; }
    if (word("ON")) {
        if (peek(VIDPRES) != 1) { eputs("video: no video card at D000"); return; }
        poke(VIDMIR, 1); return;
    }
    if (word("OFF")) { poke(VIDMIR, 0); return; }
    if (word("CLEAR")) { bios(VIDCTL, 0, 2); return; }
    if (word("INIT")) { bios(VIDCTL, 0, 1); status(); return; }
    if (word("PROBE")) { bios(VIDCTL, 0, 0); status(); return; }
    eput2("video: what? ", w);
}
