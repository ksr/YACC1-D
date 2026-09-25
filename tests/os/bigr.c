/* bigr.c - tests/os/big.session's reader (2026-09-25, 24-bit file positions): read a file written by bigw.c back
   and check it against the same pattern, byte i = (lo ^ (lo >> 8) ^ hi * 37) & 255 for i = hi * 65536 + lo.
     bigr PATH        byte by byte (GETC)
     bigr -s PATH     sector-wise (READ into a 512-byte buffer: the counts it returns are checked too)
     bigr -k PATH     SEEK (2026-09-25) to 1:300, 2:0, 0:65535 and 1:511 and check the 600 bytes after each (or the rest),
                      then to the end and past it
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

void seekcheck(int h, int x, int p) {  /* SEEK to x:p, then up to 600 bytes by GETC against the pattern */
    int n, c;
    putnum(fseek(h, x, p));
    hi = x; lo = p; h37 = hi * 37; bad = 0;
    n = 600;
    while (n && (c = fgetc(h)) != 65535) { check(c); n--; }
    putchar(bad ? '!' : '.');
}

void main() {
    char *a; int h, c, n, i, sec;
    a = argword(argstr(), path, 63);
    sec = 0;
    if (path[0] == '-' && path[1] == 's') { sec = 1; argword(a, path, 63); }
    if (path[0] == '-' && path[1] == 'k') { sec = 2; argword(a, path, 63); }
    h = fopen(path);
    if (!h) { puts("bigr: cannot open"); return; }
    if (sec == 2) {
        putstr("bigr seek: ");
        seekcheck(h, 1, 300); seekcheck(h, 2, 0); seekcheck(h, 0, 65535); seekcheck(h, 1, 511);
        putchar(' '); putnum(fseek(h, 2, 12295)); putnum(fgetc(h) == 65535); putnum(fseek(h, 2, 12296));
        putnum(fseek(h, 3, 0)); putchar(10);
        fclose(h);
        return;
    }
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
