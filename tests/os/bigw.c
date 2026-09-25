/* bigw.c - tests/os/big.session's writer (2026-09-25, 24-bit file positions): write a file over 64K with a pattern
   the host check recomputes, byte i = (lo ^ (lo >> 8) ^ hi * 37) & 255 for i = hi * 65536 + lo.
     bigw PATH K      K * 1024 + 7 bytes, 512 at a time through WRITE (the last 7 on their own)
     bigw -v PATH K   the same bytes through WRITE in pieces of 1, 300, 513, 7, 200, 0 and 1000 bytes in turn
                      (2026-09-25: the assembly OS's WRITE copies the rest of each sector in one go)
   run.py compiles it (y1cc --os) and puts it on the session's disk as /BIGW. */
#include "../../os/lib_fs.c"
#include "../../os/lib_num.c"
#include "y1lib.c"
char buf[1000];
int sizes[7];
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
    char *a; int h, k, n, i, v, m;
    sizes[0] = 1; sizes[1] = 300; sizes[2] = 513; sizes[3] = 7; sizes[4] = 200; sizes[5] = 0; sizes[6] = 1000;
    a = argword(argstr(), path, 63);
    v = 0;
    if (path[0] == '-' && path[1] == 'v') { v = 1; a = argword(a, path, 63); }
    argword(a, num, 15);
    k = 0;
    for (i = 0; num[i]; i++) k = k * 10 + num[i] - '0';
    h = fcreate(path, 0, 0);
    if (!h) { puts("bigw: cannot create"); return; }
    if (v) {                            /* k * 1024 + 7 bytes in pieces */
        n = k; m = 0; i = 0;            /* n:m = the bytes left, in 1K and bytes */
        m = 7;
        for (;;) {
            k = sizes[i % 7]; i++;
            if (!n && k > m) k = m;
            fill(k);
            if (fwrite(h, buf, k) != k) { puts("bigw: write refused"); fclose(h); return; }
            if (!n && k == m) break;
            while (k) { if (!m) { n--; m = 1024; } m--; k--; }
        }
        if (!fclose(h)) { puts("bigw: close failed"); return; }
        putstr("bigw: "); put32(hi, lo, 0); putstr(" bytes to "); puts(path);
        return;
    }
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
