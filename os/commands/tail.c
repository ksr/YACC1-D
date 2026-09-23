/* tail.c - the last lines of the files named, or of the console.
     tail FILE        the last 10 lines
     tail -5 FILE     the last 5 (1..40)
   The input streams through a ring of 40 line slots of 256 bytes (10K, inside the program); a line is cut at
   255 characters, CR is dropped. Several names (globs, "-") are one stream, each file ending a line.
   Ported from P8X os/commands/tail.c 2026-09-23, changes: several names via lib_stdin.c; the console is conin();
   a bare "-" is the console, so the count needs its digits (-5), as in head. */
#include "../lib_stdin.c"
#include "y1lib.c"
char buf[10240];                                /* 40 slots x 256 */

void main() {
    char *a, *p; int n, c, col, slot, total, count, base;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: tail [-N] [file ...]   the last N lines (default 10, max 40)"); return; }
    n = 10;
    if (a[0] == '-' && a[1] >= '0' && a[1] <= '9') {
        a++; n = 0;
        while (*a >= '0' && *a <= '9') n = n * 10 + *a++ - '0';
    }
    if (n < 1) n = 1;
    if (n > 40) n = 40;
    if (openarg(a) == 2) { notfound("tail"); return; }
    sepfiles = 1;
    col = 0; slot = 0; total = 0;
    while ((c = nextc()) != 65535) {
        if (c == 10) {
            buf[slot * 256 + col] = 0;
            if (++slot >= n) slot = 0;
            total++; col = 0;
        } else if (c != 13 && col < 255) buf[slot * 256 + col++] = c;
    }
    if (col) { buf[slot * 256 + col] = 0; if (++slot >= n) slot = 0; total++; }
    count = total > n ? n : total;
    base = total > n ? slot : 0;
    while (count) {
        p = buf + base * 256;
        puts(p);
        if (++base >= n) base = 0;
        count--;
    }
}
