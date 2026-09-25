/* bigw.c - tests/os/big.session's writer (2026-09-25, 24-bit file positions): write a file over 64K with a pattern
   the host check recomputes, byte i = (lo ^ (lo >> 8) ^ hi * 37) & 255 for i = hi * 65536 + lo.
     bigw PATH K      K * 1024 + 7 bytes, 512 at a time through WRITE (the last 7 on their own)
   run.py compiles it (y1cc --os) and puts it on the session's disk as /BIGW. */
#include "../../os/lib_fs.c"
#include "../../os/lib_num.c"
#include "y1lib.c"
char buf[512];
char path[64];
char num[16];
int hi, lo, h37;                        /* h37 = hi * 37 (a multiply per byte is slow: rt_mul) */

void fill(int m) {                      /* the next m bytes of the pattern */
    int i;
    for (i = 0; i < m; i++) {
        buf[i] = lo ^ (lo >> 8) ^ h37;
        lo++;
        if (!lo) { hi++; h37 = hi * 37; }
    }
}

void main() {
    char *a; int h, k, n, i;
    a = argword(argstr(), path, 63);
    argword(a, num, 15);
    k = 0;
    for (i = 0; num[i]; i++) k = k * 10 + num[i] - '0';
    h = fcreate(path, 0, 0);
    if (!h) { puts("bigw: cannot create"); return; }
    n = k * 2;
    while (n) {
        fill(512);
        if (fwrite(h, buf, 512) != 512) { puts("bigw: write refused"); fclose(h); return; }
        n--;
    }
    fill(7);
    fwrite(h, buf, 7);
    if (!fclose(h)) { puts("bigw: close failed"); return; }
    putstr("bigw: "); put32(hi, lo, 0); putstr(" bytes to "); puts(path);
}
