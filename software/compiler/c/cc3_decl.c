/* cc3_decl.c - pass 3 of the multi-pass y1cc (2026-09-24): the declarations. y1cc.c's gen_program up to the
   check for main(): the struct/union layouts, the function table, the globals (their labels) and the global data.

     cc3 W          reads W.ast (three times: structs and functions; globals; their data; the bodies skipped),
                    W.typ, W.nam, W.lit; writes W.dat (the global data, a stream for cc9) and W.s1 (for cc4, cc5)

   W.s1  nstructs(2) nmembers(2) nfuncs(2) nglobals(2), then the tables a column at a time (ids 1..; w = 2-byte
         words, b = bytes):
           structs  tag(w) size(w) mfirst(w) nmembers(w)
           members  name(w) off(w) base(w) ptr(b) count(w)
           functions (in order of first appearance)  name(w) rbase(w) rptr(b) nparams(w) body(w)
                    (body = the ordinal of the W.ast record of its last definition, 0 = none)
           globals (variable ids 1..)  name(w) base(w) ptr(b) count(w)   (cc5 makes their labels)
   W.dat records (pdefs.h R_*): R_DSVAR, R_STRUSE, R_DATALAB, R_DWSTR, R_DWVAR, R_DBLIT, R_TEXT (section 1). */
#include "pcommon.c"
#include "pnames.c"
#include "past.c"

int ty_b[TYPES_MAX];
int ty_p[TYPES_MAX];
int ty_c[TYPES_MAX];
int ntypes;
int lit_len[LITS_MAX];
int nlits;
int nm_glob[NAMES_MAX];         /* global variable (var index) */
int nm_fn[NAMES_MAX];           /* function (fn index) */
int nm_st[NAMES_MAX];           /* struct/union (struct index) */

/* structs/unions: 1.., members 1.. */
int s_tag[STRUCTS_MAX];
int s_size[STRUCTS_MAX];
int s_mfirst[STRUCTS_MAX];
int s_mn[STRUCTS_MAX];
int nstructs;
int m_name[MEMBERS_MAX];
int m_off[MEMBERS_MAX];
int m_base[MEMBERS_MAX];
char m_ptr[MEMBERS_MAX];
int m_cnt[MEMBERS_MAX];
int nmembers;

/* functions: 1.. */
int f_name[FUNCS_MAX];
int f_rbase[FUNCS_MAX];
char f_rptr[FUNCS_MAX];
int f_np[FUNCS_MAX];
int f_body[FUNCS_MAX];
int nfuncs;

/* globals: variables 1.. (their labels are cc5's, made in this order) */
int v_base[VARS_MAX];
char v_ptr[VARS_MAX];
int v_cnt[VARS_MAX];
int v_name[VARS_MAX];
int nvars;

char db[LINE_MAX];
int dbn;

void pass_fail(char *msg) { io_fail(msg); }
int size_of(int base, int ptr);
int v_size(int v);
void register_struct(int d);
void add_function(int d);
void declare_global(int g);
void emit_global(int g);
void const_data(int g, int pass);
int addr_of(int name);
void db_byte(int b);
void db_end(void);
void data_text(char *t);
void load_tables(void);

int size_of(int base, int ptr) {
    if (ptr > 0 || base == K_INT) return 2;
    if (base == K_CHAR) return 1;
    if (base && nm_st[base]) return s_size[nm_st[base]];
    e_start("y1cc: unknown type "); e_q(base ? nm_text(base) : ""); e_go();
    return 0;
}
int v_size(int v) {                                 /* bytes a global occupies */
    if (v_cnt[v]) return v_cnt[v] * size_of(v_base[v], v_ptr[v]);
    if (v_ptr[v] == 0 && nm_st[v_base[v]]) return s_size[nm_st[v_base[v]]];
    return size_of(v_base[v], v_ptr[v]);
}

/* ---- structs, functions, globals (y1cc.c gen_program's first loops) ------------------------------------------- */
void register_struct(int d) {
    int s; int off; int size; int m; int sz; int t; int un; int k;
    un = na[d] == 2;
    if (nstructs + 1 >= STRUCTS_MAX) fail("y1cc: too many structs (STRUCTS_MAX)");
    nstructs++; s = nstructs;
    s_mfirst[s] = nmembers + 1; s_mn[s] = 0; s_tag[s] = nb[d];
    off = 0; size = 0;
    for (m = nc[d]; m; m = nx[m]) {
        t = na[m];
        sz = ty_c[t] ? ty_c[t] * size_of(ty_b[t], ty_p[t]) : size_of(ty_b[t], ty_p[t]);
        if (nmembers + 1 >= MEMBERS_MAX) fail("y1cc: too many struct members (MEMBERS_MAX)");
        nmembers++; k = nmembers;
        m_name[k] = nb[m]; m_off[k] = un ? 0 : off; m_base[k] = ty_b[t]; m_ptr[k] = ty_p[t]; m_cnt[k] = ty_c[t];
        s_mn[s]++;
        if (un) { if (sz > size) size = sz; }
        else off = off + sz;
    }
    s_size[s] = un ? size : off;
    if (nb[d]) nm_st[nb[d]] = s;
}
void add_function(int d) {
    int f; int t; int n; int p;
    f = nm_fn[nb[d]];
    if (!f) {
        if (nfuncs + 1 >= FUNCS_MAX) fail("y1cc: too many functions (FUNCS_MAX)");
        nfuncs++; f = nfuncs; f_name[f] = nb[d]; nm_fn[nb[d]] = f;
    }
    t = na[d]; f_rbase[f] = ty_b[t]; f_rptr[f] = ty_p[t];
    n = 0; for (p = nc[d]; p; p = nx[p]) n++;
    f_np[f] = n;
    if (nk[d] == N_FUNC) f_body[f] = rec_ord;
}
void declare_global(int g) {
    int t; int base; int ptr; int arr; int count; int name; int init; int m; int n;
    t = na[g]; base = ty_b[t]; ptr = ty_p[t]; count = ty_c[t]; name = nb[g]; init = nc[g]; arr = nd[g] & 1;
    if (nd[g] & 2) {
        if (!init) { e_start("y1cc: array "); e_q(nm_text(name)); e_s(" needs a size or an initializer"); e_go(); }
        if (nk[init] == N_INITSTR && base == K_CHAR && ptr == 0) count = lit_len[na[init]] + 1;
        else if (nk[init] == N_INITLIST) { n = 0; for (m = na[init]; m; m = nx[m]) n++; count = n; }
        else { e_start("y1cc: cannot infer the size of "); e_q(nm_text(name)); e_go(); }
    }
    if (nm_glob[name]) { e_start("y1cc: global "); e_q(nm_text(name)); e_s(" declared twice"); e_go(); }
    if (nvars + 1 >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
    nvars++;
    v_base[nvars] = base; v_ptr[nvars] = ptr; v_cnt[nvars] = arr ? count : 0;
    v_name[nvars] = name;
    nm_glob[name] = nvars;
}

/* ---- the global data (y1cc.c emit_globals / const_data), as W.dat records -------------------------------------- */
void data_text(char *t) { wb(R_TEXT); wb(1); ws(t); }
void db_byte(int b) {                               /* DB lines of 16 numbers (the assembler upper-cases text) */
    if (dbn == 0) { db[0] = 0; bcat(db, "        DB "); } else bchr(db, ',');
    bnum(db, b & 255);
    dbn++;
    if (dbn == 16) { data_text(db); dbn = 0; }
}
void db_end(void) { if (dbn) { data_text(db); dbn = 0; } }
int addr_of(int name) {
    if (!nm_glob[name]) { e_start("y1cc: initializer names unknown global "); e_q(nm_text(name)); e_go(); }
    return nm_glob[name];
}
void emit_global(int g) {                           /* after every global has its label (initializers may point at any) */
    int v;
    v = nm_glob[nb[g]];
    if (!nc[g]) { wb(R_DSVAR); wi(v); wi(v_size(v)); return; }
    const_data(g, 0);                               /* y1cc.py makes the strings first, then the label and the lines */
    wb(R_DATALAB); wi(v);
    const_data(g, 1);
}
void const_data(int g, int pass) {                  /* pass 0: make the strings; pass 1: the data lines */
    int t; int base; int ptr; int arr; int count; int init; int esz; int v; int i; int n; int it; int items;
    t = na[g]; base = ty_b[t]; ptr = ty_p[t]; init = nc[g]; arr = nd[g] & 1;
    v = nm_glob[nb[g]]; count = v_cnt[v];
    esz = size_of(base, ptr);
    if (!arr) {
        if (nk[init] == N_INITSTR) {
            if (ptr == 0) fail("y1cc: string initializer for a non-pointer");
            wb(R_STRUSE); wi(na[init]);
            if (pass) { wb(R_DWSTR); wi(na[init]); }
        } else if (nk[init] == N_INITADDR) {
            if (!pass) return;
            if (esz != 2) fail("y1cc: address initializer for a non-pointer");
            wb(R_DWVAR); wi(addr_of(na[init]));
        } else if (nk[init] == N_INITNUM) {
            if (!pass) return;
            if (esz == 2) { db[0] = 0; bcat(db, "        DW "); bnum(db, na[init] & 65535); data_text(db); }
            else { db_byte(na[init]); db_end(); }
        } else if (pass) fail("y1cc: brace initializer for a scalar");
        return;
    }
    if (base == K_CHAR && ptr == 0 && nk[init] == N_INITSTR) {
        if (!pass) return;
        wb(R_DBLIT); wi(na[init]); wi(count);       /* the literal's bytes, zeros up to count (cc9) */
        return;
    }
    if (nk[init] != N_INITLIST) { if (pass) fail("y1cc: array needs a brace initializer or a string"); return; }
    items = 0;
    for (it = na[init]; it; it = nx[it]) items++;
    if (items > count) fail("y1cc: too many initializers");
    for (it = na[init]; it; it = nx[it]) {
        if (nk[it] == N_INITSTR || nk[it] == N_INITADDR) {
            if (esz != 2) fail("y1cc: string/address initializer for a non-pointer element");
            if (nk[it] == N_INITSTR) {
                wb(R_STRUSE); wi(na[it]);
                if (pass) { db_end(); wb(R_DWSTR); wi(na[it]); }
            } else if (pass) { db_end(); wb(R_DWVAR); wi(addr_of(na[it])); }
        } else if (nk[it] == N_INITNUM) {
            if (pass) {
                if (esz == 2) { db[0] = 0; bcat(db, "        DW "); bnum(db, na[it] & 65535); data_text(db); }
                else db_byte(na[it]);
            }
        } else fail("y1cc: nested brace initializer not supported");
    }
    if (!pass) return;
    db_end();
    n = mul16(count - items, esz);                  /* REAL zeros in the image: DS would leave RAM as it powers up */
    for (i = 0; i < n; i++) db_byte(0);
    db_end();
}

/* ---- the driver ------------------------------------------------------------------------------------------------- */
void load_tables(void) {
    int h; int i; int n;
    names_load();
    h = ropen(".typ");
    ntypes = ri(h);
    if (ntypes >= TYPES_MAX) fail("y1cc: too many types (TYPES_MAX)");
    for (i = 1; i <= ntypes; i++) { ty_b[i] = ri(h); ty_p[i] = rb(h); ty_c[i] = ri(h); }
    io_close(h);
    h = ropen(".lit");
    nlits = ri(h);
    if (nlits >= LITS_MAX) fail("y1cc: too many string literals (LITS_MAX)");
    for (i = 1; i <= nlits; i++) { n = ri(h); lit_len[i] = n; while (n) { rb(h); n--; } }
    io_close(h);
}
void y1cc_main(void) {
    int h; int i; int k; int d;
    p_args();
    load_tables();
    h = ropen(".ast");                              /* 1: structs and the function table */
    rec_ord = 0;
    while (rec_head(h)) {
        for (i = 0; i < rec_ne; i++) {
            d = rec_ent[i];
            if (nk[d] == N_STRUCTDEF) register_struct(d);
            else if (nk[d] == N_FUNC || nk[d] == N_PROTO) add_function(d);
        }
        rec_skip(h);
    }
    io_close(h);
    h = ropen(".ast");                              /* 2: every global gets its label */
    rec_ord = 0;
    while (rec_head(h)) {
        for (i = 0; i < rec_ne; i++) if (nk[rec_ent[i]] == N_GVAR) declare_global(rec_ent[i]);
        rec_skip(h);
    }
    io_close(h);
    h = ropen(".ast");                              /* 3: their data */
    wopen(".dat");
    rec_ord = 0;
    while (rec_head(h)) {
        for (i = 0; i < rec_ne; i++) if (nk[rec_ent[i]] == N_GVAR) emit_global(rec_ent[i]);
        rec_skip(h);
    }
    wclose();
    io_close(h);
    k = nm_fn[NM_MAIN];
    if (!k || !f_body[k]) fail("y1cc: no main()");
    wopen(".s1");
    wi(nstructs); wi(nmembers); wi(nfuncs); wi(nvars);
    warr(s_tag + 1, nstructs); warr(s_size + 1, nstructs); warr(s_mfirst + 1, nstructs); warr(s_mn + 1, nstructs);
    warr(m_name + 1, nmembers); warr(m_off + 1, nmembers); warr(m_base + 1, nmembers);
    warrc(m_ptr + 1, nmembers); warr(m_cnt + 1, nmembers);
    warr(f_name + 1, nfuncs); warr(f_rbase + 1, nfuncs); warrc(f_rptr + 1, nfuncs); warr(f_np + 1, nfuncs);
    warr(f_body + 1, nfuncs);
    warr(v_name + 1, nvars); warr(v_base + 1, nvars); warrc(v_ptr + 1, nvars); warr(v_cnt + 1, nvars);
    wclose();
}
