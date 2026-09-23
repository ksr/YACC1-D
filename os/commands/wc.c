/* wc.c - count lines, words and bytes (2026-09-23: through the OS file API, byte-wise with fgetc; the v0 version
   read raw CF sectors through the BIOS because the OS had no file layer yet).
     wc PATH   the file
     wc        the console until Ctrl-D (conin), as a filter */
#include "../lib_fs.c"
#include "y1lib.c"

void main() {
    int h, c, lines, words, bytes, inword; char *a;
    a = argstr();
    while (*a == ' ') a++;
    h = 0;
    if (*a) { h = fopen(a); if (!h) { puts("wc: not found"); return; } }
    lines = words = bytes = inword = 0;
    while (1) {
        c = h ? fgetc(h) : conin();
        if (c == 65535) break;
        bytes++;
        if (c == 10) lines++;
        if (c == ' ' || c == 10 || c == 13 || c == 9) inword = 0;
        else if (!inword) { inword = 1; words++; }
    }
    if (h) fclose(h);
    putnum(lines); putchar(' '); putnum(words); putchar(' '); putnum(bytes); putchar(10);
}
