/* dep.c - deposit hex bytes into memory: dep addr b b b ...
     dep 8000 A9 01 60   store $A9, $01, $60 from $8000
     dep -h              usage
   Quiet on success. It writes anywhere, the OS ($1000..$4FFF) and this program ($5000..) included: with great
   power. Up to ~40 bytes per line (the shell's 127-character argument tail).
   Ported from P8X os/commands/dep.c 2026-09-23, changes: none but the mechanical pass (y1cc syntax, eputs from
   lib_err.c, no & 255 masks: char and int are unsigned). */
#include "../lib_err.c"
#include "y1lib.c"

int hx(int c) {                                 /* a hex digit's value, 99 if not one */
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return 99;
}

char *hexword(char *a, int *v) {                /* hex digits at a -> *v; returns a past them (a itself: none) */
    int d, n;
    n = 0;
    while ((d = hx(*a)) < 16) { n = n * 16 + d; a++; }
    *v = n;
    return a;
}

void main() {
    char *a, *b; int addr, v;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: dep addr b b ...   store hex bytes at hex address addr"); return;
    }
    b = hexword(a, &addr);
    if (b == a) { eputs("dep: bad address"); return; }
    a = b;
    while (1) {
        while (*a == ' ') a++;
        if (!*a) return;
        b = hexword(a, &v);
        if (b == a) return;                     /* a non-hex word ends it */
        poke(addr, v);
        addr++;
        a = b;
    }
}
