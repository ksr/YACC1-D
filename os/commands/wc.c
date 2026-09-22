/* wc.c - count lines, words and bytes of a file (read through the OS's sector interface is not there yet: this
   version reads the CF sectors itself via the BIOS, so it also shows a program using the card directly) */
#include "../lib_abi.c"
#include "y1lib.c"
char buf[512];
void main() {
    int lba, n, i, lines, words, bytes, inword; char *a;
    a = argstr();
    if (!*a) { puts("usage: wc LBA COUNT  (raw sectors: the file layer belongs to the OS)"); return; }
    lba = 0; while (*a >= '0' && *a <= '9') { lba = lba * 10 + (*a - '0'); a++; }
    while (*a == ' ') a++;
    n = 0; while (*a >= '0' && *a <= '9') { n = n * 10 + (*a - '0'); a++; }
    lines = words = bytes = inword = 0;
    while (n--) {
        poke(CFLBA0, lba); poke(CFLBA1, lba >> 8); poke(CFLBA2, 0);
        if (bios(CFREAD, buf, 0)) { puts("read error"); return; }
        for (i = 0; i < 512; i++) {
            if (buf[i] == 0) break;
            bytes++;
            if (buf[i] == 10) lines++;
            if (buf[i] == ' ' || buf[i] == 10 || buf[i] == 13 || buf[i] == 9) inword = 0;
            else if (!inword) { inword = 1; words++; }
        }
        lba++;
    }
    putnum(lines); putchar(' '); putnum(words); putchar(' '); putnum(bytes); putchar(10);
}
