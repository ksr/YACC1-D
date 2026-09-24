/* xisa.c (2026-09-24) - the --xisa code on purpose: LDZ/STZ of the page's variables (and LDR/STR of the ones that
   did not fit: there are more than 256 bytes of word variables here), a recursive function whose whole frame is in
   the page (its inline frame save/restore uses LDZ/STZ R4), one with a frame over 8 bytes (rt_fsave/rt_frest, which
   reload R6), ADDIW (array element and struct member offsets over 3, R3 and R4), SHL16 (int indexing, *2, *4,
   rt_mul, rt_shl), rt_divmod with its remainder in R5, and putchar/puts through the ROM (R6 reloaded after it).
   Everything prints, so a wrong page register or a wrong ADDIW/SHL16 shows. Also a bench test (tests/bench). */
// y1cc: --xisa
#include "y1lib.c"

struct rec { int a; int b; int c; int d; int e; char tag; };

int t0, t1, t2, t3, t4, t5, t6, t7, t8, t9, ta, tb, tc, td, te, tf;     /* 64 word globals and 64 word locals: more than a page */
int u0, u1, u2, u3, u4, u5, u6, u7, u8, u9, ua, ub, uc, ud, ue, uf;
int v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, va, vb, vc, vd, ve, vf;
int w0, w1, w2, w3, w4, w5, w6, w7, w8, w9, wa, wb, wc, wd, we, wf;
int table[40];
struct rec recs[4];
int hot;

int sum64(void) {           /* every global once: some from the page (LDZ), the rest with LDR (4 terms a statement:
                               the passes' trees hold 40 nodes, and their stack grows with the depth) */
    int s;
    s = 0;
    s = s + t0 + t1 + t2 + t3;
    s = s + t4 + t5 + t6 + t7;
    s = s + t8 + t9 + ta + tb;
    s = s + tc + td + te + tf;
    s = s + u0 + u1 + u2 + u3;
    s = s + u4 + u5 + u6 + u7;
    s = s + u8 + u9 + ua + ub;
    s = s + uc + ud + ue + uf;
    s = s + v0 + v1 + v2 + v3;
    s = s + v4 + v5 + v6 + v7;
    s = s + v8 + v9 + va + vb;
    s = s + vc + vd + ve + vf;
    s = s + w0 + w1 + w2 + w3;
    s = s + w4 + w5 + w6 + w7;
    s = s + w8 + w9 + wa + wb;
    s = s + wc + wd + we + wf;
    return s;
}

void setall(int k) {
    t0 = k; t1 = k; t2 = k; t3 = k; t4 = k; t5 = k; t6 = k; t7 = k; t8 = k; t9 = k; ta = k; tb = k; tc = k; td = k; te = k; tf = k;
    u0 = k; u1 = k; u2 = k; u3 = k; u4 = k; u5 = k; u6 = k; u7 = k; u8 = k; u9 = k; ua = k; ub = k; uc = k; ud = k; ue = k; uf = k;
    v0 = k; v1 = k; v2 = k; v3 = k; v4 = k; v5 = k; v6 = k; v7 = k; v8 = k; v9 = k; va = k; vb = k; vc = k; vd = k; ve = k; vf = k;
    w0 = k; w1 = k; w2 = k; w3 = k; w4 = k; w5 = k; w6 = k; w7 = k; w8 = k; w9 = k; wa = k; wb = k; wc = k; wd = k; we = k; wf = k;
    t1 = k + 1; t2 = k + 2; t3 = k + 3;
}

int locals(int k) {         /* 64 word locals: set, then summed */
    int s;
    int k0, k1, k2, k3, k4, k5, k6, k7, k8, k9, ka, kb, kc, kd, ke, kf;
    int l0, l1, l2, l3, l4, l5, l6, l7, l8, l9, la, lb, lc, ld, le, lf;
    int m0, m1, m2, m3, m4, m5, m6, m7, m8, m9, ma, mb, mc, md, me, mf;
    int n0, n1, n2, n3, n4, n5, n6, n7, n8, n9, na, nb, nc, nd, ne, nf;
    k0 = k; k1 = k; k2 = k; k3 = k; k4 = k; k5 = k; k6 = k; k7 = k; k8 = k; k9 = k; ka = k; kb = k; kc = k; kd = k; ke = k; kf = k;
    l0 = k; l1 = k; l2 = k; l3 = k; l4 = k; l5 = k; l6 = k; l7 = k; l8 = k; l9 = k; la = k; lb = k; lc = k; ld = k; le = k; lf = k;
    m0 = k; m1 = k; m2 = k; m3 = k; m4 = k; m5 = k; m6 = k; m7 = k; m8 = k; m9 = k; ma = k; mb = k; mc = k; md = k; me = k; mf = k;
    n0 = k; n1 = k; n2 = k; n3 = k; n4 = k; n5 = k; n6 = k; n7 = k; n8 = k; n9 = k; na = k; nb = k; nc = k; nd = k; ne = k; nf = k;
    s = 0;
    s = s + k0 + k1 + k2 + k3;
    s = s + k4 + k5 + k6 + k7;
    s = s + k8 + k9 + ka + kb;
    s = s + kc + kd + ke + kf;
    s = s + l0 + l1 + l2 + l3;
    s = s + l4 + l5 + l6 + l7;
    s = s + l8 + l9 + la + lb;
    s = s + lc + ld + le + lf;
    s = s + m0 + m1 + m2 + m3;
    s = s + m4 + m5 + m6 + m7;
    s = s + m8 + m9 + ma + mb;
    s = s + mc + md + me + mf;
    s = s + n0 + n1 + n2 + n3;
    s = s + n4 + n5 + n6 + n7;
    s = s + n8 + n9 + na + nb;
    s = s + nc + nd + ne + nf;
    return s;
}

int gcd(int a, int b) {     /* recursive, a 4-byte frame: saved inline (LDZ/STZ R4: named often enough for the page) */
    if (b == 0) return a;
    if (a == b) return a;
    if (b == 1) return b;
    return gcd(b, a % b);
}

int deep(int n, int a, int b, int c, int d, int e) {   /* recursive, a 12-byte frame: rt_fsave/rt_frest */
    int keep;
    if (n == 0) return a + b + c + d + e;
    keep = n * 3;
    return deep(n - 1, a + 1, b + 2, c + 3, d + 4, e + 5) + keep;
}

void line(char *s, int v) { putstr(s); putnum(v); putchar(10); }

int main() {
    int i; int s; int *p; struct rec *r;
    setall(7);
    line("sum64 ", sum64());                            /* 64 * 7 + 6 = 454 */
    line("locals ", locals(9));                         /* 576 */
    for (i = 0; i < 40; i++) table[i] = i * i + 1000;
    s = 0;
    for (i = 0; i < 40; i = i + 3) s = s + table[i];     /* SHL16 for the index */
    line("table ", s);
    line("t37 ", table[37]);                            /* ADDIW R3,g_table+74 */
    for (i = 0; i < 4; i++) { r = &recs[i]; r->e = i * 100 + 5; r->d = i + 50; r->tag = 'A' + i; }
    s = 0;
    for (i = 0; i < 4; i++) s = s + recs[i].e + recs[i].d;
    line("recs ", s);
    p = &table[20]; p[5] = 4321;                        /* ADDIW R4 (a store through a pointer + 10) */
    line("p5 ", table[25]);
    r = &recs[2]; r->e = 999;                           /* ADDIW R4,8 */
    line("r2e ", recs[2].e);
    line("mul ", 123 * table[3]);                       /* rt_mul */
    line("div ", 60000 / 7);                            /* folded */
    hot = 60000;
    line("div2 ", hot / 7);                             /* rt_divmod */
    line("mod ", hot % 7);                              /* R5 */
    line("shl ", 3 << ((hot >> 4) & 7));                /* rt_shl: SHL16 (and rt_shr) */
    line("x4 ", hot * 4);                               /* SHL16 twice */
    line("gcd ", gcd(1071, 462));                       /* 21 */
    line("gcd2 ", gcd(65535, 4369));                    /* 4369 */
    line("deep ", deep(20, 1, 2, 3, 4, 5));             /* 15 + 5*20 + ... */
    for (i = 0; i < 4; i++) putchar(recs[i].tag);
    putchar(10);
    puts("xisa ok");
    return 0;
}
