/* bigr.c - tests/os/big.session's reader (2026-09-25, 24-bit file positions): read a file written by bigw.c back
   and check it against the same pattern, byte i = (lo ^ (lo >> 8) ^ hi * 37) & 255 for i = hi * 65536 + lo.
     bigr PATH        byte by byte (GETC)
     bigr -s PATH     sector-wise (READ into a 512-byte buffer: the counts it returns are checked too)
   Prints the bytes read (32 bits) and the first offset that differs from the pattern, or "pattern ok". run.py
   compiles it (y1cc --os) and puts it on the session's disk as /BIGR. */
#include "../../os/lib_fs.c"
#include "../../os/lib_num.c"
#include "y1lib.c"
char buf[512];
char path[64];
int hi, lo, h37, bad, bhi, blo, odd;    /* h37 = hi * 37 (a multiply per byte is slow: rt_mul) */

void check(int c) {                     /* the next byte of the file against the pattern */
    if (!bad && c != ((lo ^ (lo >> 8) ^ h37) & 255)) { bad = 1; bhi = hi; blo = lo; }
    lo++;
    if (!lo) { hi++; h37 = hi * 37; }
}

void main() {
    char *a; int h, c, n, i, sec;
    a = argword(argstr(), path, 63);
    sec = 0;
    if (path[0] == '-' && path[1] == 's') { sec = 1; argword(a, path, 63); }
    h = fopen(path);
    if (!h) { puts("bigr: cannot open"); return; }
    if (sec) {
        while ((n = fread(h, buf))) {
            if (n != 512) odd++;            /* only the last sector may be short */
            for (i = 0; i < n; i++) check(buf[i]);
        }
    } else while ((c = fgetc(h)) != 65535) check(c);
    fclose(h);
    putstr("bigr: "); put32(hi, lo, 0); putstr(" bytes, ");
    if (bad) { putstr("first difference at "); put32(bhi, blo, 0); }
    else putstr("pattern ok");
    if (odd > 1) putstr(", short sectors in the middle");
    putchar(10);
}
