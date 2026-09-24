/* cc4_calls.c - pass 4 of the multi-pass y1cc (2026-09-24): the call graph. y1cc.c's build_reach and the
   liveness of gen_program: which function can reach which (main must not be recursive), the roots named in
   funcaddr(), the functions that get compiled. It works on the call lists cc2 wrote into W.ast (every call of a
   function, in the order y1cc.c's walk() meets them), so no function body is loaded.

     cc4 W          reads W.ast (twice: the direct calls; funcaddr), W.s1, W.nam; writes W.cg

   W.cg  nfuncs(2) row(2), live(b) per function 1..nfuncs (1 a root - main or named in funcaddr(), even when another
         live function reaches it (2026-09-24, cc6 --xisa: an entry sets the page register) - 2 reached from one, 0 dropped), then nfuncs
         rows of `row` bytes: bit g of row f = f can reach g (for cc7's recursion and argument analysis). */
#include "pcommon.c"
#include "pnames.c"
#include "past.c"

int nm_fn[NAMES_MAX];
int f_name[FUNCS_MAX];
int f_body[FUNCS_MAX];
char f_live[FUNCS_MAX];
int nfuncs;
char rbits[REACH_BYTES];        /* reach[f] as a bit row of REACH_ROW bytes */
int wlist[FUNCS_MAX];           /* main's direct callees (y1cc.c walk W_LIST) */
int nwlist;
int f_first[FUNCS_MAX];         /* the ordinal of the W.ast record of a function's first definition */
int perr_key;                   /* the first (by f_first) body whose funcaddr() failed, and its message */
char perr_msg[EBUF_MAX];

void pass_fail(char *msg) { io_fail(msg); }
int bit(int f, int g);
void set_bit(int f, int g);
void load_s1(void);

int bit(int f, int g) { return (rbits[f * REACH_ROW + (g >> 3)] & (1 << (g & 7))) != 0; }
void set_bit(int f, int g) { rbits[f * REACH_ROW + (g >> 3)] = rbits[f * REACH_ROW + (g >> 3)] | (1 << (g & 7)); }
void load_s1(void) {                                /* W.s1 (cc3_decl.c): the functions' names and bodies */
    int h; int i; int ns; int nm;
    h = ropen(".s1");
    ns = ri(h); nm = ri(h); nfuncs = ri(h); ri(h);
    if (nfuncs >= FUNCS_MAX || nfuncs >= REACH_ROW * 8 || (nfuncs + 1) * REACH_ROW > REACH_BYTES)
        fail("y1cc: too many functions (FUNCS_MAX, REACH_ROW, REACH_BYTES)");
    skip(h, ns * 8 + nm * 9);
    rarr(h, f_name + 1, nfuncs); skip(h, nfuncs * 5); rarr(h, f_body + 1, nfuncs);
    io_close(h);
    for (i = 1; i <= nfuncs; i++) nm_fn[f_name[i]] = i;
}
void y1cc_main(void) {
    int h; int i; int j; int k; int t; int d; int f; int r; int c; int n; int kd; int a; int from; int m;
    p_args();
    names_load();
    load_s1();
    f = nm_fn[NM_MAIN];
    h = ropen(".ast");                              /* the direct calls of every function with a body (W_DIRECT) */
    rec_ord = 0;
    while (rec_head(h)) {
        d = rec_ent[0];
        from = 0;
        if (rec_ne == 1 && nk[d] == N_FUNC && f_body[nm_fn[nb[d]]] == rec_ord) from = nm_fn[nb[d]];
        for (i = 0; i < rec_ncall; i++) {
            c = ri(h); ri(h); rb(h); ri(h);
            k = nm_fn[c];
            if (from && k && f_body[k]) {
                set_bit(from, k);
                if (from == f) {                    /* main's direct callees, each once (W_LIST) */
                    for (j = 0; j < nwlist; j++) if (wlist[j] == k) k = 0;
                    if (k) { wlist[nwlist] = k; nwlist++; }
                }
            }
        }
        skip(h, rec_ndecl * 4); skip(h, rec_blen);
    }
    io_close(h);
    for (k = 1; k <= nfuncs; k++)                   /* Warshall: reach = the transitive closure of the direct calls */
        for (i = 1; i <= nfuncs; i++)
            if (bit(i, k)) for (j = 0; j < REACH_ROW; j++) rbits[i * REACH_ROW + j] = rbits[i * REACH_ROW + j] | rbits[k * REACH_ROW + j];
    if (bit(f, f)) {                                /* main cannot be part of a cycle */
        for (i = 0; i < nwlist; i++)                /* sorted by name, as y1cc.py prints them */
            for (j = i + 1; j < nwlist; j++)
                if (s_cmp(nm_text(f_name[wlist[j]]), nm_text(f_name[wlist[i]])) == 1) { t = wlist[i]; wlist[i] = wlist[j]; wlist[j] = t; }
        e_start("y1cc: main() can call itself (via ");
        k = 0;
        for (i = 0; i < nwlist; i++) {
            j = wlist[i];
            if (j == f || bit(j, f)) { if (k) e_s(", "); e_s(nm_text(f_name[j])); k = 1; }
        }
        e_s("): main cannot be recursive"); e_go();
    }
    f_live[f] = 1;                                  /* roots: main and every function named in funcaddr() */
    h = ropen(".ast");                              /* funcaddr(): y1cc.py goes through the bodies in the order of each */
    rec_ord = 0; perr_key = 0;                      /* function's first definition; in one body a malformed funcaddr() */
    while (rec_head(h)) {                           /* anywhere comes before a name that is not a function */
        d = rec_ent[0];
        r = 0;
        if (rec_ne == 1 && nk[d] == N_FUNC) {
            k = nm_fn[nb[d]];
            if (!f_first[k]) f_first[k] = rec_ord;
            if (f_body[k] == rec_ord) r = k;
        }
        t = 0; m = 0;                               /* a malformed one seen; the first name without a body */
        for (i = 0; i < rec_ncall; i++) {
            c = ri(h); n = ri(h); kd = rb(h); a = ri(h);
            if (!r || c != B_FUNCADDR) continue;
            if (n != 1 || kd != N_ID) t = 1;
            else {
                k = nm_fn[a];
                if (!k || !f_body[k]) { if (!m) m = a; }
                else f_live[k] = 1;
            }
        }
        if ((t || m) && (!perr_key || f_first[r] < perr_key)) {
            perr_key = f_first[r];
            if (t) e_start("y1cc: funcaddr() wants the name of a function");
            else { e_start("y1cc: funcaddr("); e_s(nm_text(m)); e_s("): no such function"); }
            for (j = 0; ebuf[j]; j++) perr_msg[j] = ebuf[j];
            perr_msg[j] = 0;
        }
        skip(h, rec_ndecl * 4); skip(h, rec_blen);
    }
    io_close(h);
    if (perr_key) fail(perr_msg);
    for (r = 1; r <= nfuncs; r++) if (f_live[r] && f_body[r]) for (t = 1; t <= nfuncs; t++) if (bit(r, t) && f_live[t] != 1) f_live[t] = 2;
    n = (nfuncs >> 3) + 1;
    wopen(".cg");
    wi(nfuncs); wi(n);
    warrc(f_live + 1, nfuncs);
    for (i = 1; i <= nfuncs; i++) warrc(rbits + i * REACH_ROW, n);
    wclose();
}
