/* head.c - the first lines of the files named, or of the console.
     head FILE        the first 10 lines
     head -5 FILE     the first 5
     head             the console (up to Ctrl-D, or until the lines are out)
   Several names (globs, "-") are read as one stream, as cat would print them.
   Ported from P8X os/commands/head.c 2026-09-23, changes: several names via lib_stdin.c; the console is conin(). */
#include "../lib_stdin.c"
#include "y1lib.c"

void main() {
    char *a; int n, lines, c;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: head [-N] [file ...]   the first N lines (default 10)"); return; }
    n = 10;
    if (a[0] == '-' && a[1] >= '0' && a[1] <= '9') {
        a++; n = 0;
        while (*a >= '0' && *a <= '9') n = n * 10 + *a++ - '0';
    }
    if (openarg(a) == 2) { notfound("head"); return; }
    lines = 0;
    while (lines < n && (c = nextc()) != 65535) { putchar(c); if (c == 10) lines++; }
}
