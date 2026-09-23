/* examine.c - view and change memory a byte at a time: examine addr
     examine 5000   shows  5000: vv  and reads keys (keyin, no echo; what is typed is echoed by examine):
                      Enter            keep the byte, go to the next address
                      two hex digits   store that byte, go to the next address
                      .  or Ctrl-D     quit
   The interactive counterpart of dump (view) and dep (blind write); the ROM monitor's E command does the same.
   The keys are keyin() (the KEYIN syscall, 2026-09-23): the keyboard even under a < or a pipe.
   Ported from P8X os/commands/examine.c 2026-09-23, changes: the keys come from keyin() without echo, so examine
   echoes the digits itself (the P8X getchar() echoed and queued an LF after Enter, which examine swallowed);
   Enter is CR or LF; lines end in LF. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"

int hx(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return 99;
}

void main() {
    char *a; int addr, d, any, c, hi, lo;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: examine addr   view/modify memory (Enter=next, 2 hex=write, .=quit)"); return;
    }
    addr = 0; any = 0;
    while ((d = hx(*a)) < 16) { addr = addr * 16 + d; a++; any = 1; }
    if (!any) { eputs("examine: bad address"); return; }
    while (1) {
        puthex(addr); putstr(": "); puthex2(peek(addr)); putchar(' ');
        c = keyin();
        if (c == 65535 || c == '.') { putchar(10); return; }
        if (c == 13 || c == 10) { putchar(10); addr++; continue; }
        hi = hx(c);
        if (hi < 16) {
            putchar(c);
            c = keyin();
            lo = hx(c);
            if (lo < 16) { putchar(c); poke(addr, hi * 16 + lo); addr++; }
        }
        putchar(10);
        if (c == 65535) return;
    }
}
