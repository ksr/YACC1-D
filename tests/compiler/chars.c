/* chars.c - char semantics: 8-bit wrap on store, zero-extension on load, byte compares, getchar/putchar */
#include "y1lib.c"

char gc;
char buf[16];

void main() {
    char c, d;
    int n, i;
    c = 250; c += 10; putnum(c); putchar('\n');            /* 4 */
    c = 0; c--; putnum(c); putchar('\n');                  /* 255 */
    gc = 300; putnum(gc); putchar('\n');                   /* 44 */
    gc = gc * 3; putnum(gc); putchar('\n');                /* 132 */
    c = gc + 200; putnum(c); putchar('\n');                /* 76 */
    n = c + 200; putnum(n); putchar('\n');                 /* 276 */
    d = 'x'; c = d; if (c == 'x') puts("c==x");
    if (c > d) puts("BAD"); else puts("c>d false");
    if (c >= d && c <= d) puts("c==d");
    if (d != 'y') puts("d!=y");
    c = 128; if (c > 127) puts("unsigned char");
    if (c < 200) puts("c<200");
    n = 0;
    for (c = 0; c < 100; c++) n += c;
    putnum(n); putchar('\n');                              /* 4950 */
    n = 0;
    for (c = 200; c; c++) n++;                             /* 200..255: 56 */
    putnum(n); putchar('\n');
    /* getchar until end of input (0 on the emulator), echo upper-cased */
    i = 0;
    while ((c = getchar()) != 0 && i < 15) { buf[i++] = c >= 'a' && c <= 'z' ? c - 32 : c; }
    buf[i] = 0;
    puts(buf);
    putnum(i); putchar('\n');
}
