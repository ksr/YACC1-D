/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* deep.c - bench diagnostic (2026-10-04): xisa.c's deep(20, 1, 2, 3, 4, 5) gives 925 on the machine (microcode
   stage 1) and 945 on both emulators. This program, the same recursion elsewhere in memory, gives 945 on the
   machine too: the fault follows the address (zero_readback.py: a $00 read back wrong near $3Fxx, review M-1), not
   the code.
   deep1 is xisa.c's deep with one change: the bottom of the recursion prints a..e.
   deep2 is the same recursion recording a..e and keep at every level in globals, printed afterwards.
   deep3 drops keep (a 12-byte frame instead of 14). Then the steps alone, outside any recursion. */
// y1cc: --xisa
#include "y1lib.c"

int la[21]; int lb[21]; int lc[21]; int ld[21]; int le[21]; int lk[21];

void pv(char *s, int v) { putstr(s); putnum(v); putchar(32); }

int deep1(int n, int a, int b, int c, int d, int e) {
    int keep;
    if (n == 0) { pv("a", a); pv("b", b); pv("c", c); pv("d", d); pv("e", e); putchar(10); return a + b + c + d + e; }
    keep = n * 3;
    return deep1(n - 1, a + 1, b + 2, c + 3, d + 4, e + 5) + keep;
}

int deep2(int n, int a, int b, int c, int d, int e) {
    int keep;
    la[n] = a; lb[n] = b; lc[n] = c; ld[n] = d; le[n] = e;
    if (n == 0) { lk[0] = 0; return a + b + c + d + e; }
    keep = n * 3;
    lk[n] = keep;
    return deep2(n - 1, a + 1, b + 2, c + 3, d + 4, e + 5) + keep;
}

int deep3(int n, int a, int b, int c, int d, int e) {
    if (n == 0) return a + b + c + d + e;
    return deep3(n - 1, a + 1, b + 2, c + 3, d + 4, e + 5) + n * 3;
}

int main() {
    int i; int x;
    pv("deep1", deep1(20, 1, 2, 3, 4, 5)); putchar(10);
    pv("deep2", deep2(20, 1, 2, 3, 4, 5)); putchar(10);
    for (i = 21; i > 0; i--) {            /* int is unsigned: i - 1 = 20 .. 0 */
        x = i - 1;
        pv("n", x); pv("a", la[x]); pv("b", lb[x]); pv("c", lc[x]); pv("d", ld[x]); pv("e", le[x]); pv("k", lk[x]);
        putchar(10);
    }
    pv("deep3", deep3(20, 1, 2, 3, 4, 5)); putchar(10);
    x = 1; x = x + 1; pv("inc1", x);
    x = 1; x = x + 4; pv("add4", x);
    x = 1; x = x + 5; pv("add5", x);
    x = 7; x = x * 3; pv("mul3", x);
    putchar(10);
    puts("xprobe done");
    return 0;
}
