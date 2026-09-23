/* lib_num.c - 32-bit counts on a 16-bit int (Y1/OS, 2026-09-23): wc's counters, dir's sizes.
     inc32(c)         c[0] = high word, c[1] = low word; add one
     put32(hi, lo, w) print hi:lo in decimal, right-justified in w columns (0 = no padding)
   Ported from the P8X wc.c/dir.c 24-bit helpers (dm10/inc24/put24/putsize24: byte arrays, a byte-wise long
   division) 2026-09-23, changes: two words instead of three bytes, one shared copy instead of two. */
void inc32(int *c) { c[1]++; if (!c[1]) c[0]++; }

void put32(int hi, int lo, int w) {
    char d[10]; int n, r, t, q1, q0;
    n = 0;
    while (1) {                                  /* (hi:lo) /= 10, the remainder is the next digit */
        r = hi % 10; hi = hi / 10;
        t = r * 256 + (lo >> 8); q1 = t / 10; r = t % 10;
        t = r * 256 + (lo & 255); q0 = t / 10; r = t % 10;
        lo = (q1 << 8) + q0;
        d[n++] = '0' + r;
        if (!hi && !lo) break;
    }
    while (w > n) { putchar(' '); w--; }
    while (n) putchar(d[--n]);
}
