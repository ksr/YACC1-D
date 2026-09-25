/* cc6_stmt.c - pass 6 of the multi-pass y1cc (2026-09-24): the statements. y1cc.c's compile_func and gen_stmt for
   every live function, main first: labels, branches, loops, switch case labels, the frames' DS lines; each
   expression becomes a hole (R_HOLE) holding its tree, which cc7 annotates and cc8 turns into code in place.

     cc6 W          reads W.ast (twice: main, then the others in source order), W.sym; writes W.st
                    (--xisa, 2026-09-24: also reads W.opt, W.cg's reach rows, and writes W.zp: the page, below)

   Generated labels are symbols 1.. per function (R_ALLOC in the order y1cc.c's lbl() would make them; cc9 numbers
   them). An error here (break outside a loop, a duplicate case...) is deferred: y1cc.c would report an error in an
   earlier expression first, and that one is only found by cc8, so the error is written into W.st (R_ERROR) at its
   place and W.st ends there. Hole trees: n(2), then the columns kind(1 byte each) a b c d x (2 bytes each) of the
   nodes 1..n (the fields as in W.ast), ids local to the tree.

   --xisa: y1cc.c's zpage_plan. While the trees are copied every N_ID is resolved as vinfo would (the function's
   variables, then the globals) and counted; after the last function the candidates (uninitialised 2-byte globals,
   the 2-byte variables of each function in compile order, a recursive function's whole frame of 1..256 bytes) are
   taken densest first while they fit in 256 bytes. W.zp: used(1), then a bit per variable (bit v&7 of byte v>>3)
   = the variable is in the page; cc9 prints LDZ/STZ for them and puts their DS lines after zpad/zpage. An entry
   (main, a funcaddr() function: W.cg live 1) starts with the macro M_ZP (MVIW R6,zpage when the page is used). */
#include "pcommon.c"
#include "past.c"

int f_name[FUNCS_MAX];
int f_rbase[FUNCS_MAX];
char f_rptr[FUNCS_MAX];
int f_body[FUNCS_MAX];
char f_live[FUNCS_MAX];
int f_vfirst[FUNCS_MAX];
int f_vn[FUNCS_MAX];
int nfuncs;
int v_base[VARS_MAX];
int v_size_[VARS_MAX];
char v_serr[VARS_MAX];
int nvars;
int fmain;
int opt_xisa;                   /* --xisa: the page (above) */
int opt_stack;                  /* --stack ADDR (2026-09-25): main switches stacks (stk_rec, stk_out) */
int stk;                        /* opt_stack while main is compiled, else 0 */
int v_name[VARS_MAX];
int v_zc[VARS_MAX];             /* how often each variable is named */
char v_ini[VARS_MAX];           /* a global with an initializer (data, not BSS) */
char f_rec[FUNCS_MAX];          /* the function reaches itself (W.cg) */
int corder[FUNCS_MAX];          /* the functions in compile order */
int ncorder;
int nglob;
int cur_f;
int zu[VARS_MAX];               /* a candidate: a variable, or ZFRAME + a function (its frame); ZDONE once decided */
int zw;
int zused;
char zbits[VARS_MAX / 8 + 1];
#define ZFRAME 16384
#define ZDONE 32768

/* the tree of the hole being written */
char tnk[TREE_MAX];
int tna[TREE_MAX];
int tnb[TREE_MAX];
int tnc[TREE_MAX];
int tnd[TREE_MAX];
int tnx[TREE_MAX];
int tn;

int nsym;                       /* the function's label symbols */
int lp_brk[LOOPS_MAX];
int lp_cont[LOOPS_MAX];
int lp_n;
int cs_val[CASES_MAX];
int cs_lab[CASES_MAX];
int ncs;
int sw_def;
char nmbuf[ID_MAX];

void pass_fail(char *msg) { wb(R_ERROR); ws(msg); wclose(); io_done(); }
int lbl(int kind);
void ldef(int sym);
void br(int sym);
int tcopy(int e);
void hole_tree(void);
void gen_stmt(int s);
void stk_out(void);
void ret_rec(void);
void gen_switch(int e, int body);
void relabel(int first);
void compile_func(int fn);
void load_sym(void);
void z_count(int name);
int z_unit(int u);
void z_plan(void);

int lbl(int kind) {                                 /* y1cc.c lbl(): a fresh label, here a symbol of this function */
    if (nsym + 1 >= SYM7) fail("y1cc: too many labels in one function");
    nsym++;
    wb(R_ALLOC); wi(nsym); wb(kind);
    return nsym;
}
void ldef(int sym) { wb(R_LDEF); wi(sym); }
void br(int sym) { wb(R_CODE); wb(MN_BR); wb(F_L); wi(sym); }

/* ---- holes: the expression's tree, renumbered 1.. (a subtree shared by x op= e is copied twice: the same code) --- */
int tcopy(int e) {
    int k; int t; int a; int b; int c; int x;
    if (!e) return 0;
    k = nk[e];
    if (k == N_ID && opt_xisa) z_count(na[e]);
    a = na[e]; b = nb[e]; c = nc[e];
    if (k == N_UNARY || k == N_PREINC || k == N_POSTINC) b = tcopy(b);
    else if (k == N_SIZEOFE || k == N_MEMBER || k == N_ARROW) a = tcopy(a);
    else if (k == N_CALL) b = tcopy(b);
    else if (k == N_INDEX || k == N_ASSIGN || k == N_LOGOR || k == N_LOGAND) { a = tcopy(a); b = tcopy(b); }
    else if (k == N_COND) { a = tcopy(a); b = tcopy(b); c = tcopy(c); }
    else if (k == N_BIN) { b = tcopy(b); c = tcopy(c); }
    x = tcopy(nx[e]);                               /* the next argument of a call */
    if (tn + 1 >= TREE_MAX) fail("y1cc: expression too big (TREE_MAX)");
    tn++; t = tn;
    tnk[t] = k; tna[t] = a; tnb[t] = b; tnc[t] = c; tnd[t] = 0; tnx[t] = x;
    return t;
}
void hole_tree(void) {                              /* n, then the columns kind(b) a b c d x (w) of nodes 1..n */
    wi(tn);
    warrc(tnk + 1, tn); warr(tna + 1, tn); warr(tnb + 1, tn); warr(tnc + 1, tn); warr(tnd + 1, tn); warr(tnx + 1, tn);
}
void hole1(int hk, int e) { int r; tn = 0; r = tcopy(e); wb(R_HOLE); wb(hk); wi(r); hole_tree(); }

/* ---- statements (y1cc.c gen_stmt) ------------------------------------------------------------------------------ */
void gen_stmt(int s) {
    int k; int m; int els; int end; int top; int cont; int i; int l; int r;
    k = nk[s];
    if (k == N_BLOCK) { for (m = na[s]; m; m = nx[m]) gen_stmt(m); return; }
    if (k == N_DECL) {
        if (nc[s]) {                                /* gen_assign(new ID(name), init, 0) */
            tn = 0;
            r = tcopy(nc[s]);
            if (tn + 1 >= TREE_MAX) fail("y1cc: expression too big (TREE_MAX)");
            tn++; l = tn;
            tnk[l] = N_ID; tna[l] = nb[s]; tnb[l] = 0; tnc[l] = 0; tnd[l] = 0; tnx[l] = 0;
            wb(R_HOLE); wb(H_DECL); wi(l); wi(r); hole_tree();
        }
        return;
    }
    if (k == N_EXPR) { hole1(H_EXPR, na[s]); return; }
    if (k == N_EMPTY) return;
    if (k == N_RETURN) {
        if (na[s]) hole1(H_RET, na[s]);
        stk_out();
        ret_rec();
        return;
    }
    if (k == N_IF) {
        els = lbl(LK_ELSE); end = lbl(LK_END);
        tn = 0; r = tcopy(na[s]);
        wb(R_HOLE); wb(H_COND); wi(r); wi(nc[s] ? els : end); wb(0); hole_tree();
        gen_stmt(nb[s]);
        if (nc[s]) { br(end); ldef(els); gen_stmt(nc[s]); }
        ldef(end);
        return;
    }
    if (k == N_WHILE) {
        top = lbl(LK_TOP); end = lbl(LK_END);
        ldef(top);
        tn = 0; r = tcopy(na[s]);
        wb(R_HOLE); wb(H_COND); wi(r); wi(end); wb(0); hole_tree();
        if (lp_n >= LOOPS_MAX) fail("y1cc: loops nested too deep (LOOPS_MAX)");
        lp_brk[lp_n] = end; lp_cont[lp_n] = top; lp_n++;
        gen_stmt(nb[s]);
        lp_n--;
        br(top); ldef(end);
        return;
    }
    if (k == N_FOR) {
        top = lbl(LK_TOP); end = lbl(LK_END); cont = lbl(LK_NEXT);
        if (na[s]) hole1(H_EXPR, na[s]);
        ldef(top);
        if (nb[s]) { tn = 0; r = tcopy(nb[s]); wb(R_HOLE); wb(H_COND); wi(r); wi(end); wb(0); hole_tree(); }
        if (lp_n >= LOOPS_MAX) fail("y1cc: loops nested too deep (LOOPS_MAX)");
        lp_brk[lp_n] = end; lp_cont[lp_n] = cont; lp_n++;
        gen_stmt(nd[s]);
        lp_n--;
        ldef(cont);
        if (nc[s]) hole1(H_EXPR, nc[s]);
        br(top); ldef(end);
        return;
    }
    if (k == N_BREAK) {
        if (!lp_n) fail("y1cc: break outside a loop or switch");
        br(lp_brk[lp_n - 1]);
        return;
    }
    if (k == N_CONTINUE) {
        i = lp_n;
        while (i > 0 && !lp_cont[i - 1]) i--;
        if (!i) fail("y1cc: continue outside a loop");
        br(lp_cont[i - 1]);
        return;
    }
    if (k == N_SWITCH) { gen_switch(na[s], nb[s]); return; }
    if (k == N_LABEL) { ldef(na[s]); return; }
    if (k == N_CASE || k == N_DEFAULT) fail("y1cc: case/default outside a switch (or nested inside a statement)");
    fail("y1cc: cannot generate stmt");
}

/* ---- switch: the case labels here; the dispatch (compare chain or BRUR table) is cc8's hole + cc9's M_SWITCH --- */
void relabel(int first) {                           /* case/default -> labels, in place; into cs_* and sw_def */
    int m; int lab; int k; int i;
    for (m = first; m; m = nx[m]) {
        if (nk[m] == N_CASE) {
            lab = lbl(LK_C); k = na[m] & 65535;
            for (i = 0; i < ncs; i++) if (cs_val[i] == k) { e_start("y1cc: duplicate case "); e_n(k); e_go(); }
            if (ncs >= CASES_MAX) fail("y1cc: too many cases in a switch");
            cs_val[ncs] = k; cs_lab[ncs] = lab; ncs++;
            nk[m] = N_LABEL; na[m] = lab;
        } else if (nk[m] == N_DEFAULT) {
            if (sw_def) fail("y1cc: two defaults in a switch");
            sw_def = lbl(LK_D);
            nk[m] = N_LABEL; na[m] = sw_def;
        } else if (nk[m] == N_BLOCK) relabel(na[m]);
    }
}
void gen_switch(int e, int body) {
    int end; int miss; int i; int r;
    end = lbl(LK_SW);
    ncs = 0; sw_def = 0;
    relabel(na[body]);
    miss = sw_def ? sw_def : end;
    tn = 0; r = tcopy(e);
    wb(R_HOLE); wb(H_SWITCH); wi(r); wi(miss); wi(ncs);
    for (i = 0; i < ncs; i++) { wi(cs_val[i]); wi(cs_lab[i]); }
    hole_tree();
    if (lp_n >= LOOPS_MAX) fail("y1cc: loops nested too deep (LOOPS_MAX)");
    lp_brk[lp_n] = end; lp_cont[lp_n] = 0; lp_n++;
    gen_stmt(body);
    lp_n--;
    ldef(end);
}

/* --stack: main's first records MOVRR R1,R5 / MVIW R1,(ADDR) / PUSHR R5, and before each RET of main POPR R5 /
   MOVRR R5,R1 (as record bytes: a wb() per byte costs y1cc's code about 9 bytes each) */
char stk_rec[] = {R_CODE, MN_MOVRR, F_RR, 1, 5, R_CODE, MN_MVIW, F_RN, 1, R_CODE, MN_PUSHR, F_R, 5,
                  R_CODE, MN_POPR, F_R, 5, R_CODE, MN_MOVRR, F_RR, 5, 1};
void ret_rec(void) { wb(R_CODE); wb(MN_RET); wb(F_0); }
void stk_out(void) { if (stk) warrc(stk_rec + 13, 9); }
/* ---- functions (y1cc.c compile_func; the function's record is loaded, rec_h its N_FUNC node) ------------------ */
void compile_func(int fn) {
    int i; int v;
    nsym = 0; lp_n = 0; cur_f = fn;
    corder[ncorder] = fn; ncorder++;
    wb(R_FUNC); wi(fn); wi(f_name[fn]); wi(f_rbase[fn]); wb(f_rptr[fn]);
    wb(R_FLABEL); wi(fn);
    if (opt_xisa && f_live[fn] == 1) { wb(R_MACRO); wb(M_ZP); }
    stk = 0;
    if (f_name[fn] == NM_MAIN) {
        stk = opt_stack;
        if (stk) { warrc(stk_rec, 9); wi(stk); warrc(stk_rec + 9, 4); }
        wb(R_MACRO); wb(M_BSSCLR);
    }
    gen_stmt(nd[rec_h]);
    if (stk) { stk_out(); ret_rec(); }              /* always, as y1cc.py does */
    wb(R_RETIF);
    for (i = 0; i < f_vn[fn]; i++) {
        v = f_vfirst[fn] + i;
        if (v_serr[v]) {                            /* v_size(): a variable of an unknown struct type */
            nm_fetch(v_base[v] == 65535 ? 0 : v_base[v], nmbuf);
            e_start("y1cc: unknown type "); e_q(nmbuf); e_go();
        }
        wb(R_DSVAR); wi(v); wi(v_size_[v]);
    }
    wb(R_FEND);
}
void load_sym(void) {                              /* W.sym (cc5_layout.c): the columns this pass needs */
    int h; int ns; int nm; int n;
    h = ropen(".opt");                              /* the options: --xisa and --stack matter here */
    while (rb(h) % 256) {}
    while (rb(h) % 256) {}
    ri(h); opt_xisa = (rb(h) & OPT_XISA) != 0; opt_stack = ri(h);
    io_close(h);
    h = ropen(".sym");
    fmain = ri(h); nglob = ri(h); ns = ri(h); nm = ri(h); nfuncs = ri(h); nvars = ri(h);
    if (nfuncs >= FUNCS_MAX) fail("y1cc: too many functions (FUNCS_MAX)");
    if (nvars >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
    io_skip(h, ns * 8 + nm * 9);                       /* the structs and members */
    n = nfuncs;
    rarr(h, f_name + 1, n); rarr(h, f_rbase + 1, n); rarrc(h, f_rptr + 1, n); io_skip(h, n * 2);
    rarr(h, f_body + 1, n); rarrc(h, f_live + 1, n); rarr(h, f_vfirst + 1, n); rarr(h, f_vn + 1, n);
    io_skip(h, n * 4);
    n = nvars;
    rarr(h, v_name + 1, n); rarr(h, v_base + 1, n); io_skip(h, n * 4); rarr(h, v_size_ + 1, n); rarrc(h, v_serr + 1, n);
    io_close(h);
    if (!opt_xisa) return;
    h = ropen(".cg");                               /* the reach rows (cc4_calls.c): who reaches itself */
    n = ri(h); nm = ri(h); io_skip(h, n);
    for (ns = 1; ns <= n; ns++) {
        io_skip(h, ns >> 3);
        if ((rb(h) >> (ns & 7)) & 1) f_rec[ns] = 1;
        io_skip(h, nm - (ns >> 3) - 1);
    }
    io_close(h);
}
void z_count(int name) {                            /* an N_ID of the function being compiled, resolved as vinfo */
    int i; int v;
    v = 0;
    for (i = 0; i < f_vn[cur_f]; i++) if (v_name[f_vfirst[cur_f] + i] == name) v = f_vfirst[cur_f] + i;
    if (!v) for (i = 1; i <= nglob; i++) if (v_name[i] == name) v = i;
    if (v) v_zc[v]++;
}
int z_unit(int u) {                                 /* candidate u's size in bytes, its weight in zw */
    int first; int n; int i; int size;
    first = u & 16383; n = 1;
    if (u & ZFRAME) { n = f_vn[first]; first = f_vfirst[first]; }
    size = 0; zw = 0;
    for (i = 0; i < n; i++) { size = size + v_size_[first + i]; zw = (zw + v_zc[first + i]) & 65535; }
    return size;
}
void z_plan(void) {                                 /* y1cc.c zpage_plan: the candidates, densest first */
    int n; int i; int k; int f; int first; int size; int best; int bd; int used; int v; int bad;
    n = 0;
    for (v = 1; v <= nglob; v++) if (!v_ini[v] && v_size_[v] == 2) { zu[n] = v; n++; }
    for (k = 0; k < ncorder; k++) {
        f = corder[k]; first = f_vfirst[f];
        if (f_rec[f]) {
            size = 0; bad = 0;                      /* (a variable of unknown size keeps the frame out) */
            for (i = 0; i < f_vn[f] && size <= 256; i++) { size = size + v_size_[first + i]; if (!v_size_[first + i]) bad = 1; }
            if (size > 0 && size <= 256 && !bad) { zu[n] = f + ZFRAME; n++; }
        } else
            for (i = 0; i < f_vn[f]; i++) if (v_size_[first + i] == 2) { zu[n] = first + i; n++; }
    }
    used = 0;
    for (;;) {
        best = n; bd = 0;
        for (i = 0; i < n; i++) {
            if (zu[i] & ZDONE) continue;
            size = z_unit(zu[i]);
            if (zw && (best == n || zw / ((size + 1) / 2) > bd)) { best = i; bd = zw / ((size + 1) / 2); }
        }
        if (best == n) break;
        size = z_unit(zu[best]);
        if (used + size <= 256) {
            used = used + size;
            first = zu[best] & 16383; k = 1;
            if (zu[best] & ZFRAME) { k = f_vn[first]; first = f_vfirst[first]; }
            for (i = 0; i < k; i++) { v = first + i; zbits[v >> 3] = zbits[v >> 3] | (1 << (v & 7)); zused = 1; }
        }
        zu[best] = zu[best] | ZDONE;
    }
}
int fn_of(int d) {                                  /* the function a record's N_FUNC node defines, or 0 */
    int i;
    for (i = 1; i <= nfuncs; i++) if (f_name[i] == nb[d]) return i;
    return 0;
}
void y1cc_main(void) {
    int h; int d; int f; int i;
    p_args();
    load_sym();
    wopen(".st");
    h = ropen(".ast");                              /* main first */
    rec_ord = 0;
    while (rec_head(h)) {
        if (rec_ord == f_body[fmain]) { rec_body(h); compile_func(fmain); }
        else rec_skip(h);
    }
    io_close(h);
    h = ropen(".ast");                              /* then the other live functions, in source order */
    rec_ord = 0;
    while (rec_head(h)) {
        d = rec_ent[0];
        f = 0;
        if (rec_ne == 1 && nk[d] == N_FUNC && nb[d] != NM_MAIN) f = fn_of(d);
        if (f && f_live[f] && f_body[f] == rec_ord) { rec_body(h); compile_func(f); }
        else {
            for (f = 0; f < rec_ne; f++) {          /* --xisa: which globals have an initializer */
                d = rec_ent[f];
                if (nk[d] == N_GVAR && nc[d]) for (i = 1; i <= nglob; i++) if (v_name[i] == nb[d]) v_ini[i] = 1;
            }
            rec_skip(h);
        }
    }
    io_close(h);
    wclose();
    if (!opt_xisa) return;
    z_plan();
    wopen(".zp");
    wb(zused); warrc(zbits, nvars / 8 + 1);
    wclose();
}
