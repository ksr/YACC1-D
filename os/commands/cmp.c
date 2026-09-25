/* cmp.c - compare two files byte for byte: cmp file1 file2
     silent when they are the same; otherwise one of
       cmp: files differ: byte N, line M
       cmp: EOF on file1        (file1 is a prefix of file2)
       cmp: EOF on file2        (file2 is a prefix of file1)
   Ported from P8X os/commands/cmp.c 2026-09-23, changes: both files are streamed side by side through two Y1/OS
   read handles (the P8X BIOS had ONE read stream, so file1 was read into an 8K buffer first and was limited to
   8K); no size limit but the OS's 16M per file (64K until 2026-09-25); y1lib putnum/putstr. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
char n1[64], n2[64];

void main() {
    char *a; int h1, h2, c1, c2, off, line;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: cmp file1 file2   report the first differing byte (silent if equal)"); return;
    }
    a = argword(a, n1, 63);
    a = argword(a, n2, 63);
    if (!*n2) { eputs("usage: cmp file1 file2"); return; }
    h1 = fopen(n1);
    if (!h1) { eputs("cmp: file1 not found"); return; }
    h2 = fopen(n2);
    if (!h2) { fclose(h1); eputs("cmp: file2 not found"); return; }
    off = 1; line = 1;
    while (1) {
        c1 = fgetc(h1); c2 = fgetc(h2);
        if (c1 == 65535 && c2 == 65535) break;
        if (c1 == 65535) { eputs("cmp: EOF on file1"); break; }
        if (c2 == 65535) { eputs("cmp: EOF on file2"); break; }
        if (c1 != c2) {
            putstr("cmp: files differ: byte "); putnum(off); putstr(", line "); putnum(line); putchar(10);
            break;
        }
        if (c1 == 10) line++;
        off++;
    }
    fclose(h1); fclose(h2);
}
