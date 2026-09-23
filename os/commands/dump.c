/* dump.c - hex dump of memory, 256 bytes a page: dump addr
     dump 5000     16 rows of  AAAA: bb bb ... bb  cccccccccccccccc  then a key: '.' (or q, or Ctrl-D) quits,
                   anything else shows the next 256 bytes
   Ported from P8X os/commands/dump.c 2026-09-23, changes: the key is conin() (no echo; 65535 = end of console
   input also quits), q quits as well as '.', rows end in LF only (the P8X printed CR LF). */
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
    char *a; int addr, d, any, row, i, b, k;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: dump addr   show 256 bytes from hex address addr (a key: next page, . or q: quit)"); return;
    }
    addr = 0; any = 0;
    while ((d = hx(*a)) < 16) { addr = addr * 16 + d; a++; any = 1; }
    if (!any) { eputs("dump: bad address"); return; }
    while (1) {
        for (row = 0; row < 16; row++) {
            puthex(addr); putstr(": ");
            for (i = 0; i < 16; i++) { puthex2(peek(addr + i)); putchar(' '); }
            putchar(' ');
            for (i = 0; i < 16; i++) { b = peek(addr + i); putchar(b >= 32 && b < 127 ? b : '.'); }
            putchar(10);
            addr += 16;
        }
        k = conin();
        if (k == '.' || k == 'q' || k == 'Q' || k == 65535) return;
    }
}
