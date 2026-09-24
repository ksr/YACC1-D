/* cc8_emit.c - pass 8 of the multi-pass y1cc (2026-09-24): the expression code generator. Every hole in W.se is
   replaced by its code: y1cc.c's gen_expr, gen_assign, gen_bin, gen_cond, gen_call..., function by function, with
   two changes. The analysis they ask (fold, type_of, type_lval, vinfo, struct_member, sizeof, the call graph) is
   read from the attributes cc7 wrote beside each node, and an attribute cc7 found poisoned raises its error here, at
   the moment y1cc.c would have. And the output is records, not text: instructions (R_CODE: a mnemonic number and
   operands, labels as symbols, addresses as label + terms), and macros for the fixed sequences (add_const, the
   shifts, branch_rel, frame_save...), which cc9 expands exactly as y1cc.c's functions of the same name.

     cc8 W          reads W.se, W.sym (the struct sizes), W.nam (the text of a message); writes W.em

   Labels this pass makes are symbols SYM7+1.. per function, so they never meet cc6's. The first error met stops
   the compile; so does an R_ERROR of cc6 once every hole before it is done (the order y1cc.c reports in). */
#include "pcommon.c"

char *kindname[] = {"", "num", "str", "id", "unary", "preinc", "postinc", "sizeoft", "sizeofe", "call", "index",
                    "member", "arrow", "assign", "cond", "logor", "logand", "bin"};

int s_tag[STRUCTS_MAX];         /* the struct sizes, for size_of() */
int s_size[STRUCTS_MAX];
int nstructs;

/* the tree of the hole and its attributes (cc7) */
char nk[TREE_MAX];
int na[TREE_MAX];
int nb[TREE_MAX];
int nc[TREE_MAX];
int nd[TREE_MAX];
int nx[TREE_MAX];
int tn;
char a_fok[TREE_MAX];
int a_fv[TREE_MAX];
char a_ferr[TREE_MAX];
int a_tb[TREE_MAX];
char a_tp[TREE_MAX];
char a_terr[TREE_MAX];
int a_lb[TREE_MAX];
char a_lp[TREE_MAX];
char a_lerr[TREE_MAX];
int a_v[TREE_MAX];              /* N_ID: the variable; N_MEMBER/ARROW: the offset; N_SIZEOF*: the size; N_CALL: fn */
int a_b[TREE_MAX];              /* N_ID / member: the base type; N_CALL: nparams */
char a_p[TREE_MAX];             /* N_ID / member: the pointer depth; N_CALL: live */
int a_c[TREE_MAX];              /* N_ID / member: the array count; N_CALL: the frame bytes */
char a_s[TREE_MAX];             /* N_ID: slot; N_CALL: rec + 2 * rchar */
char a_verr[TREE_MAX];
int a_fvar[TREE_MAX];           /* N_CALL: the callee's first variable (its frame) */
int a_fer[TREE_MAX];            /* N_CALL: frame_err */
int a_tv[TREE_MAX];             /* an argument: the parameter it is stored in */
char a_ts[TREE_MAX];            /*   that parameter is a char slot */
char a_haz[TREE_MAX];           /*   it waits on the stack */
int a_esc[TREE_MAX];            /*   escapes() */
char a_eerr[TREE_MAX];
char e_code[TERR_MAX];
int e_a1[TERR_MAX];
int e_a2[TERR_MAX];

/* the address being built (y1cc.c's abuf): a label, then "+term"s (32 bits each: high, low) */
int ak;
int aid;
int ant;
int aterm_h[ATERMS_MAX];
int aterm_l[ATERMS_MAX];
int m_hi;                       /* mul32() */
int m_lo;

int cur_name;                   /* the function being compiled */
int cur_rbase;
int cur_rptr;
int nsym;
int park[PARK_MAX];
int npark;
int cs_val[CASES_MAX];          /* a switch's cases: value, label symbol */
int cs_sym[CASES_MAX];
int inh;
int fv;
int tb;
int tp;
int sm_off;
int sm_base;
int sm_ptr;
int sm_cnt;
int sl_base;                    /* static_lval(): the address is in ak/aid/aterm */
int sl_ptr;
int sl_slot;
int bs_a;                       /* binscale() */
int bs_b;
int bs_scale;
char nmbuf[ID_MAX];

void pass_fail(char *msg) { io_fail(msg); }
void raise(int err);
void e_name(int id);
int fold(int e);
void type_of(int e);
void type_lval(int e);
void member(int e);
int var_of(int e);
int sizeof_expr(int e);
int size_of(int base, int ptr);
int dec_ptr(int p);
int lbl(int kind);
void label_def(int sym);
void need(int h);
void w_addr(void);
void ins0(int mn);
void insr(int mn, int r);
void insn(int mn, int n);
void insl(int mn, int sym);
void insa(int mn);
void insrn(int mn, int r, int n);
void insrl(int mn, int r, int sym);
void insrr(int mn, int a, int b);
void insra(int mn, int r);
void insv(int mn, int r, int v);
void jsr_rt(int h);
void zext(void);
void m_addk(int k);
void m_adda(void);
void m_simple(int m);
void m_logk(int op, int k);
void m_scale(int esz);
void m_brel(int rel, int sym, int lomode, int lok);
void a_var(int v);
void kadd(int off);
int is_char(int e);
int is_array(int e);
int static_addr(int e);
int static_lval(int e);
int is_narrow(int e);
int simple_byte(int e);
void byte_src(int e);
void gen_byte_acc(int e);
void load_static(int reg, int base, int ptr, int slot);
void store_static_r3(int base, int ptr, int slot, int narrow);
int is_leaf(int e);
void gen_leaf(int reg, int e);
void gen_address(int e);
void deref_r3(int base, int ptr);
void gen_expr(int e);
void gen_assign(int lhs, int rhs, int want);
int simple_address(int lhs);
void load_address_r4(int lhs);
int is_commutative(int op);
int is_relop(int op);
void binscale(int op, int a, int b);
void operands(int op, int a, int b);
void gen_bin(int e);
void materialize(int e);
int neg_rel(int rel);
void gen_relcond(int rel, int a, int b, int label, int when);
void gen_cond(int e, int label, int when);
int port(int e);
int nth_arg(int e, int i);
void gen_call(int e);
void gen_builtin(int e);
void frame(int e, int restore);
void gen_expr_stmt(int e);
void read_tree(void);
void copy(int n);
void load_structs(void);

/* ---- the attributes: a poisoned one raises its error ---------------------------------------------------------- */
void e_name(int id) { nm_fetch(id == 65535 ? 0 : id, nmbuf); e_s(nmbuf); }
void raise(int err) {                               /* y1cc.c's message for a recorded analysis error */
    int c; int a1; int a2;
    err = err & 255;                                /* (a byte column: signed on the Mac) */
    c = e_code[err]; a1 = e_a1[err]; a2 = e_a2[err];
    e_start("y1cc: ");
    if (c == E_UNDECL) { e_s("undeclared identifier '"); e_name(a1); e_s("' (in "); e_name(a2); e_s(")"); }
    else if (c == E_NOTSTRUCT) { e_s("not a struct/union: '"); e_name(a1); e_s("'"); }
    else if (c == E_NOMEMBER) { e_s("'"); e_name(a1); e_s("' has no member '"); e_name(a2); e_s("'"); }
    else if (c == E_CALLUNDECL) { e_s("call of undeclared function '"); e_name(a1); e_s("'"); }
    else if (c == E_DEREF) e_s("dereference of a non-pointer");
    else if (c == E_INDEX) e_s("index of a non-pointer");
    else if (c == E_NOTLVAL) { e_s("not an lvalue: "); e_q(a1 <= N_BIN ? kindname[a1] : "?"); }
    else { e_s("unknown type '"); e_name(a1); e_s("'"); }
    e_go();
}
int fold(int e) { if (a_ferr[e]) raise(a_ferr[e]); fv = a_fv[e]; return a_fok[e]; }
void type_of(int e) { if (a_terr[e]) raise(a_terr[e]); tb = a_tb[e]; tp = a_tp[e]; }
void type_lval(int e) { if (a_lerr[e]) raise(a_lerr[e]); tb = a_lb[e]; tp = a_lp[e]; }
void member(int e) {                                /* struct_member(member_tag(e), nb[e]) -> sm_* */
    if (a_verr[e]) raise(a_verr[e]);
    sm_off = a_v[e]; sm_base = a_b[e]; sm_ptr = a_p[e]; sm_cnt = a_c[e];
}
int var_of(int e) { if (a_verr[e]) raise(a_verr[e]); return a_v[e]; }   /* vinfo(na[e]) of an N_ID */
int sizeof_expr(int e) { if (a_verr[e]) raise(a_verr[e]); return a_v[e]; }
int size_of(int base, int ptr) {
    int s;
    if (ptr > 0 || base == K_INT) return 2;
    if (base == K_CHAR) return 1;
    for (s = nstructs; s > 0; s--) if (base && s_tag[s] == base) return s_size[s];   /* the last definition wins */
    e_start("y1cc: unknown type '"); e_name(base); e_s("'"); e_go();
    return 0;
}
int dec_ptr(int p) { if (p > 0) return p - 1; return 0; }

/* ---- output records ------------------------------------------------------------------------------------------- */
int lbl(int kind) {
    if (nsym + 1 >= SYM7) fail("y1cc: too many labels in one function");
    nsym++;
    wb(R_ALLOC); wi(SYM7 + nsym); wb(kind);
    return SYM7 + nsym;
}
void label_def(int sym) { wb(R_LDEF); wi(sym); }
void need(int h) { wb(R_NEED); wb(h); }
void w_addr(void) { int i; wb(ak); wi(aid); wb(ant); for (i = 0; i < ant; i++) { wi(aterm_h[i]); wi(aterm_l[i]); } }
void ins0(int mn) { wb(R_CODE); wb(mn); wb(F_0); }
void insr(int mn, int r) { wb(R_CODE); wb(mn); wb(F_R); wb(r); }
void insn(int mn, int n) { wb(R_CODE); wb(mn); wb(F_N); wi(n); }
void insl(int mn, int sym) { wb(R_CODE); wb(mn); wb(F_L); wi(sym); }
void insa(int mn) { wb(R_CODE); wb(mn); wb(F_A); w_addr(); }
void insrn(int mn, int r, int n) { wb(R_CODE); wb(mn); wb(F_RN); wb(r); wi(n); }
void insrl(int mn, int r, int sym) { wb(R_CODE); wb(mn); wb(F_RL); wb(r); wi(sym); }
void insrr(int mn, int a, int b) { wb(R_CODE); wb(mn); wb(F_RR); wb(a); wb(b); }
void insra(int mn, int r) { wb(R_CODE); wb(mn); wb(F_RA); wb(r); w_addr(); }
void insv(int mn, int r, int v) { wb(R_CODE); wb(mn); wb(F_RA); wb(r); wb(A_VAR); wi(v); wb(0); }  /* label of v */
void jsr_rt(int h) { wb(R_CODE); wb(MN_JSR); wb(F_A); wb(A_RT); wi(h); wb(0); }
void zext(void) { insn(MN_LDAI, 0); insr(MN_MVARH, 3); }
void m_addk(int k) { wb(R_MACRO); wb(M_ADDK); wi(k & 65535); }
void m_adda(void) { wb(R_MACRO); wb(M_ADDA); w_addr(); }
void m_simple(int m) { wb(R_MACRO); wb(m); }
void m_logk(int op, int k) { wb(R_MACRO); wb(M_LOGK); wb(op); wi(k & 65535); }
void m_scale(int esz) { wb(R_MACRO); wb(M_SCALE); wi(esz); }
void m_brel(int rel, int sym, int lomode, int lok) { wb(R_MACRO); wb(M_BREL); wb(rel); wi(sym); wb(lomode); wi(lok); }

/* ---- static addresses: the assembler expression in ak/aid/aterm (y1cc.c's abuf) ------------------------------ */
void a_var(int v) { ak = A_VAR; aid = v; ant = 0; }
void kadd2(int hi, int lo) {                        /* "+term", unless the term is 0 */
    if (hi || lo) {
        if (ant >= ATERMS_MAX) fail("y1cc: address too deep (ATERMS_MAX)");
        aterm_h[ant] = hi; aterm_l[ant] = lo; ant++;
    }
}
void kadd(int off) { kadd2(0, off); }
void mul32(int a, int b) {                          /* a * b, 32 bits, in m_hi:m_lo (16-bit arithmetic only) */
    int p; int t;
    m_lo = (a & 255) * (b & 255);
    m_hi = (a >> 8) * (b >> 8);
    p = (a & 255) * (b >> 8);                       /* the two middle products, each shifted 8 */
    t = (p & 255) << 8;
    if (m_lo > 65535 - t) m_hi++;
    m_lo = (m_lo + t) & 65535; m_hi = (m_hi + (p >> 8)) & 65535;
    p = (a >> 8) * (b & 255);
    t = (p & 255) << 8;
    if (m_lo > 65535 - t) m_hi++;
    m_lo = (m_lo + t) & 65535; m_hi = (m_hi + (p >> 8)) & 65535;
}
int is_char(int e) { type_of(e); return tb == K_CHAR && tp == 0; }
int is_array(int e) {                               /* e is an array object (not a pointer variable) */
    if (nk[e] == N_ID) { var_of(e); return a_c[e] > 0; }
    if (nk[e] == N_MEMBER || nk[e] == N_ARROW) { member(e); return sm_cnt > 0; }
    return 0;
}
int static_addr(int e) {                            /* 1 when &e is a link-time constant (in ak/aid/aterm) */
    int k; int i; int b; int bt; int bp;
    k = nk[e];
    if (k == N_ID) { a_var(var_of(e)); return 1; }
    if (k == N_STR) { wb(R_STRUSE); wi(na[e]); ak = A_STR; aid = na[e]; ant = 0; return 1; }
    if (k == N_MEMBER) {
        if (!static_addr(na[e])) return 0;
        member(e);
        kadd(sm_off);
        return 1;
    }
    if (k == N_INDEX) {
        b = na[e];
        if (!fold(nb[e])) return 0;
        i = fv;
        if (!is_array(b)) return 0;
        if (!static_addr(b)) return 0;
        type_of(b); bt = tb; bp = tp;
        mul32(i, size_of(bt, dec_ptr(bp)));         /* y1cc.c: kadd(i * size): printed unmasked */
        kadd2(m_hi, m_lo);
        return 1;
    }
    return 0;
}
int static_lval(int e) {                            /* a scalar lvalue at a constant address: 1, address/sl_* set */
    int v;
    if (nk[e] == N_ID) {
        v = var_of(e);
        if (a_c[e]) return 0;
        a_var(v); sl_base = a_b[e]; sl_ptr = a_p[e]; sl_slot = a_s[e];
        return 1;
    }
    if (nk[e] == N_MEMBER || nk[e] == N_INDEX) {
        if (is_array(e)) return 0;
        if (!static_addr(e)) return 0;
        type_lval(e);
        sl_base = tb; sl_ptr = tp; sl_slot = 0;
        return 1;
    }
    return 0;
}

/* ---- narrow (8-bit) values -------------------------------------------------------------------------------------- */
int is_narrow(int e) {                              /* e's value fits a byte and is available as one */
    int k; int n;
    k = nk[e];
    if (k == N_NUM) return na[e] <= 255;
    if (k == N_CALL) {
        n = na[e];
        if (n == B_GETCHAR || n == B_PEEK || n == B_INP || n == B_BIOS) return 1;
        return (a_s[e] & 2) != 0;                  /* a function of that name returning char (cc7) */
    }
    if (k == N_ID || k == N_INDEX || k == N_MEMBER || k == N_ARROW || (k == N_UNARY && na[e] == O_STAR))
        return is_char(e) && !is_array(e);
    if (k == N_COND) return is_narrow(nb[e]) && is_narrow(nc[e]);
    if (k == N_ASSIGN || k == N_PREINC || k == N_POSTINC) { type_of(e); return tb == K_CHAR && tp == 0; }
    return 0;
}
int simple_byte(int e) {                            /* loadable into ACC without touching R3/R4/TMP */
    int k;
    k = nk[e];
    if (k == N_NUM) return 1;
    return (k == N_ID || k == N_INDEX || k == N_MEMBER) && is_char(e) && static_lval(e);
}
void byte_src(int e) {                              /* the address of a static char byte */
    static_lval(e);
    if (sl_slot) kadd(1);
}
void gen_byte_acc(int e) {
    int k;
    k = nk[e];
    if (k == N_NUM) { insn(MN_LDAI, na[e] & 255); return; }
    if (simple_byte(e)) { byte_src(e); insa(MN_LDA); return; }
    if (k == N_UNARY && na[e] == O_STAR) { gen_expr(nb[e]); insr(MN_LDAVR, 3); return; }
    if (k == N_INDEX || k == N_MEMBER || k == N_ARROW) { gen_address(e); insr(MN_LDAVR, 3); return; }
    gen_expr(e); insr(MN_MVRLA, 3);
}

/* ---- loads / stores of static variables (the address is in ak/aid/aterm) ------------------------------------ */
void load_static(int reg, int base, int ptr, int slot) {
    if (slot || size_of(base, ptr) == 2) { insra(MN_LDR, reg); return; }
    if (size_of(base, ptr) != 1) fail("y1cc: struct/union used as a value");
    insa(MN_LDA); insr(MN_MVARL, reg); insn(MN_LDAI, 0); insr(MN_MVARH, reg);
}
void store_static_r3(int base, int ptr, int slot, int narrow) {
    if (size_of(base, ptr) == 2) { insra(MN_STR, 3); return; }
    if (size_of(base, ptr) != 1) fail("y1cc: whole struct/array assignment not supported");
    if (slot) {
        if (!narrow) zext();
        insra(MN_STR, 3);
    } else {
        insr(MN_MVRLA, 3); insa(MN_STA);
    }
}

/* ---- leaves: constants and static scalars, loadable into any register -------------------------------------- */
int is_leaf(int e) {
    int k;
    k = nk[e];
    if (k == N_NUM || k == N_STR || k == N_ID || k == N_SIZEOFT || k == N_SIZEOFE) return 1;
    if (k == N_UNARY && na[e] == O_AMP) return static_addr(nb[e]);
    if (k == N_INDEX || k == N_MEMBER) return static_addr(e);
    return 0;
}
void gen_leaf(int reg, int e) {
    int k;
    k = nk[e];
    if (k == N_NUM) { insrn(MN_MVIW, reg, na[e] & 65535); return; }
    if (k == N_STR) { static_addr(e); insra(MN_MVIW, reg); return; }
    if (k == N_SIZEOFT || k == N_SIZEOFE) { insrn(MN_MVIW, reg, sizeof_expr(e)); return; }
    if (k == N_UNARY) { static_addr(nb[e]); insra(MN_MVIW, reg); return; }
    if (is_array(e)) { static_addr(e); insra(MN_MVIW, reg); return; }
    if (!static_lval(e)) fail("y1cc: internal: leaf");
    load_static(reg, sl_base, sl_ptr, sl_slot);
}

/* ---- addresses (lvalues): address in R3 ---------------------------------------------------------------------- */
void gen_address(int e) {
    int k; int b; int i; int bt; int bp; int esz; int ki;
    k = nk[e];
    if (static_addr(e)) { insra(MN_MVIW, 3); return; }
    if (k == N_UNARY && na[e] == O_STAR) { gen_expr(nb[e]); return; }
    if (k == N_MEMBER) { gen_address(na[e]); member(e); m_addk(sm_off); return; }
    if (k == N_ARROW) { gen_expr(na[e]); member(e); m_addk(sm_off); return; }
    if (k == N_INDEX) {
        b = na[e]; i = nb[e];
        type_of(b); bt = tb; bp = tp;
        esz = size_of(bt, dec_ptr(bp));
        if (fold(i)) {                              /* base + constant */
            ki = fv;
            gen_expr(b); m_addk(mul16(ki, esz)); return;
        }
        gen_expr(i); m_scale(esz);
        if (is_array(b) && static_addr(b)) { m_adda(); return; }
        if (is_leaf(b)) { gen_leaf(4, b); m_simple(M_ADDR4); return; }
        insr(MN_PUSHR, 3); gen_expr(b); insr(MN_POPR, 4); m_simple(M_ADDR4); return;
    }
    e_start("y1cc: not an lvalue: "); e_q(k <= N_BIN ? kindname[k] : "?"); e_go();
}
void deref_r3(int base, int ptr) {                  /* R3 = *(R3) of type (base, ptr): M_DEREF */
    int sz;
    sz = size_of(base, ptr);
    if (sz != 1 && sz != 2) fail("y1cc: struct/union used as a value");
    wb(R_MACRO); wb(M_DEREF); wb(sz);
}

/* ---- expressions: result in R3 ------------------------------------------------------------------------------------ */
void gen_expr(int e) {
    int k; int op; int v; int no; int end; int lv; int bt; int bp; int esz;
    k = nk[e];
    if (k == N_NUM) { insrn(MN_MVIW, 3, na[e] & 65535); return; }
    if (k == N_STR) { static_addr(e); insra(MN_MVIW, 3); return; }
    if (k == N_SIZEOFT || k == N_SIZEOFE) { insrn(MN_MVIW, 3, sizeof_expr(e)); return; }
    if (k == N_ID) {
        v = var_of(e);
        a_var(v);
        if (a_c[e]) insra(MN_MVIW, 3);             /* array -> its address */
        else load_static(3, a_b[e], a_p[e], a_s[e]);
        return;
    }
    if (k == N_UNARY) {
        op = na[e];
        if (op == O_AMP) { gen_address(nb[e]); return; }
        if (op == O_STAR) { gen_expr(nb[e]); type_lval(e); deref_r3(tb, tp); return; }
        if (op == O_NOT) { materialize(e); return; }
        if (op == O_TILDE) { gen_expr(nb[e]); m_simple(M_NOT); return; }
        if (fold(e)) { insrn(MN_MVIW, 3, fv); return; }
        gen_expr(nb[e]); m_simple(M_NOT); insr(MN_INCR, 3);
        return;
    }
    if (k == N_INDEX || k == N_MEMBER || k == N_ARROW) {
        if (is_array(e)) { gen_address(e); return; }  /* array member decays */
        if (static_lval(e)) { load_static(3, sl_base, sl_ptr, sl_slot); return; }
        gen_address(e); type_lval(e); deref_r3(tb, tp);
        return;
    }
    if (k == N_ASSIGN) { gen_assign(na[e], nb[e], 1); return; }
    if (k == N_COND) {
        no = lbl(LK_F); end = lbl(LK_E);
        gen_cond(na[e], no, 0); gen_expr(nb[e]); insl(MN_BR, end);
        label_def(no); gen_expr(nc[e]); label_def(end);
        return;
    }
    if (k == N_LOGAND || k == N_LOGOR) { materialize(e); return; }
    if (k == N_BIN) { gen_bin(e); return; }
    if (k == N_CALL) { gen_call(e); return; }
    if (k == N_PREINC) { gen_assign(nb[e], nd[e], 1); return; }
    if (k == N_POSTINC) {                           /* value = the OLD value; the variable gets old +- 1 */
        lv = nb[e];
        op = na[e] == O_INC ? O_PLUS : O_MINUS;
        if (static_lval(lv) && size_of(sl_base, sl_ptr) == 2) {   /* a word at a fixed address: old kept in R4 */
            gen_expr(lv); insrr(MN_MOVRR, 3, 4);
            type_of(lv); bt = tb; bp = tp;
            esz = bp ? size_of(bt, dec_ptr(bp)) : 1;
            m_addk(op == O_PLUS ? esz : 65535 - esz + 1);
            static_lval(lv);                        /* (gen_expr used the address: the address again) */
            insra(MN_STR, 3); insrr(MN_MOVRR, 4, 3);
        } else {
            gen_expr(lv); insr(MN_PUSHR, 3);
            gen_assign(lv, nd[e], 0);
            insr(MN_POPR, 3);
        }
        return;
    }
    fail("y1cc: cannot generate expr");
}

/* ---- assignment ----------------------------------------------------------------------------------------------- */
void gen_assign(int lhs, int rhs, int want) {
    int b; int p; int sz; int narrow; int base; int ptr; int slot;
    type_lval(lhs); b = tb; p = tp;
    sz = size_of(b, p);
    if (sz != 1 && sz != 2) fail("y1cc: whole struct/array assignment not supported (assign members)");
    narrow = is_narrow(rhs);
    if (static_lval(lhs)) {                         /* a scalar at a fixed address */
        base = sl_base; ptr = sl_ptr; slot = sl_slot;
        if (sz == 1 && !slot && simple_byte(rhs) && !want) {   /* byte = byte: through ACC only */
            gen_byte_acc(rhs); static_lval(lhs); insa(MN_STA); return;
        }
        gen_expr(rhs);
        static_lval(lhs);
        store_static_r3(base, ptr, slot, narrow);
        if (want && sz == 1 && !narrow) zext();    /* the value is the stored byte */
        return;
    }
    /* through a computed address: value in R3, address in R4 (or the other way round for a leaf value) */
    if (sz == 1 && simple_byte(rhs)) {              /* byte store: address -> R3, byte -> ACC */
        gen_address(lhs); gen_byte_acc(rhs); insr(MN_STAVR, 3);
        if (want) { insr(MN_MVARL, 3); zext(); }
        return;
    }
    if (is_leaf(rhs)) {                             /* address in R3, value in R4 */
        gen_address(lhs); gen_leaf(4, rhs);
        if (sz == 2) {
            insr(MN_MVRHA, 4); insr(MN_STAVR, 3); insr(MN_INCR, 3);
            insr(MN_MVRLA, 4); insr(MN_STAVR, 3);
        } else { insr(MN_MVRLA, 4); insr(MN_STAVR, 3); }
        if (want) insrr(MN_MOVRR, 4, 3);
        return;
    }
    if (simple_address(lhs)) { gen_expr(rhs); load_address_r4(lhs); }   /* value in R3, address in R4 */
    else { gen_address(lhs); insr(MN_PUSHR, 3); gen_expr(rhs); insr(MN_POPR, 4); }
    if (sz == 2) {
        insr(MN_MVRHA, 3); insr(MN_STAVR, 4); insr(MN_INCR, 4);
        insr(MN_MVRLA, 3); insr(MN_STAVR, 4);
    } else {
        insr(MN_MVRLA, 3); insr(MN_STAVR, 4);
        if (want && !narrow) zext();
    }
}
int simple_address(int lhs) {                      /* &lhs is a pointer variable (+ constant), loadable into R4 */
    int k;
    k = nk[lhs];
    if (k == N_UNARY && na[lhs] == O_STAR) return nk[nb[lhs]] == N_ID && static_lval(nb[lhs]);
    if (k == N_ARROW) return nk[na[lhs]] == N_ID && static_lval(na[lhs]);
    if (k == N_INDEX) return fold(nb[lhs]) && nk[na[lhs]] == N_ID && static_lval(na[lhs]);
    return 0;
}
void load_address_r4(int lhs) {                     /* R4 = &lhs for a simple_address lhs (uses ACC only) */
    int off; int bt; int bp; int i;
    if (nk[lhs] == N_UNARY) { gen_leaf(4, nb[lhs]); return; }
    if (nk[lhs] == N_ARROW) {
        gen_leaf(4, na[lhs]); member(lhs); off = sm_off;
    } else {
        type_of(na[lhs]); bt = tb; bp = tp;
        gen_leaf(4, na[lhs]);
        fold(nb[lhs]);
        off = mul16(fv, size_of(bt, dec_ptr(bp)));
    }
    off = off & 65535;
    if (off == 0) return;
    if (off <= 3) { for (i = 0; i < off; i++) insr(MN_INCR, 4); return; }
    insr(MN_MVRLA, 4); insn(MN_ADDI, off & 255); insr(MN_MVARL, 4);
    insr(MN_MVRHA, 4); insn(MN_ADDIC, off >> 8); insr(MN_MVARH, 4);
}

/* ---- binary operators ------------------------------------------------------------------------------------------ */
int is_commutative(int op) {
    return op == O_PLUS || op == O_STAR || op == O_AMP || op == O_BAR || op == O_CARET || op == O_EQ || op == O_NE;
}
int is_relop(int op) { return op == O_LT || op == O_GT || op == O_LE || op == O_GE || op == O_EQ || op == O_NE; }
void binscale(int op, int a, int b) {               /* pointer arithmetic: bs_a/bs_b with the pointer on the left */
    int lb_; int lp; int rb; int rp;
    bs_a = a; bs_b = b; bs_scale = 1;
    if (op == O_PLUS || op == O_MINUS) {
        type_of(a); lb_ = tb; lp = tp;
        type_of(b); rb = tb; rp = tp;
        if (lp > 0 && rp == 0) bs_scale = size_of(lb_, lp - 1);
        else if (op == O_PLUS && rp > 0 && lp == 0) { bs_a = b; bs_b = a; bs_scale = size_of(rb, rp - 1); }
    }
}
void operands(int op, int a, int b) {               /* a in R3, b in R4, avoiding a push/pop when a side is a leaf */
    if (is_leaf(b)) { gen_expr(a); gen_leaf(4, b); }
    else if (is_leaf(a) && is_commutative(op)) { gen_expr(b); gen_leaf(4, a); }
    else if (is_leaf(a)) { gen_expr(b); insrr(MN_MOVRR, 3, 4); gen_leaf(3, a); }
    else { gen_expr(b); insr(MN_PUSHR, 3); gen_expr(a); insr(MN_POPR, 4); }
}
void gen_bin(int e) {
    int op; int a; int b; int scale; int kb; int hkb; int ka; int hka; int lt; int lp; int esz; int t; int sh; int i;
    op = na[e]; a = nb[e]; b = nc[e];
    if (fold(e)) { insrn(MN_MVIW, 3, fv); return; }            /* y1cc.c: fold_bin(op, a, b) */
    if (is_relop(op)) { materialize(e); return; }
    if (op == O_MINUS) {
        type_of(a); lt = tb; lp = tp;
        if (lp > 0) {
            type_of(b);
            if (tp > 0) {                           /* pointer - pointer = element count */
                esz = size_of(lt, lp - 1);
                operands(op, a, b); need(RT_SUB); jsr_rt(RT_SUB);
                if (esz == 2) m_simple(M_SHR1);
                else if (esz != 1) { insrn(MN_MVIW, 4, esz); need(RT_DIVMOD); jsr_rt(RT_DIVMOD); }
                return;
            }
        }
    }
    binscale(op, a, b); a = bs_a; b = bs_b; scale = bs_scale;
    hkb = fold(b); kb = fv;
    if (op == O_PLUS || op == O_MINUS) {
        if (hkb) {
            gen_expr(a);
            t = mul16(kb, scale);
            m_addk(op == O_PLUS ? t : 65535 - t + 1);
            return;
        }
        if (scale != 1) {                           /* pointer +- int: scale the int first */
            gen_expr(b); m_scale(scale);
            if (op == O_PLUS) {
                if (is_leaf(a)) { gen_leaf(4, a); m_simple(M_ADDR4); return; }
                insr(MN_PUSHR, 3); gen_expr(a); insr(MN_POPR, 4); m_simple(M_ADDR4); return;
            }
            insrr(MN_MOVRR, 3, 4);
            if (is_leaf(a)) gen_leaf(3, a);
            else { insr(MN_PUSHR, 4); gen_expr(a); insr(MN_POPR, 4); }
            need(RT_SUB); jsr_rt(RT_SUB); return;
        }
        if (op == O_PLUS) {
            if (fold(a)) { ka = fv; gen_expr(b); m_addk(ka); return; }
        }
        operands(op, a, b);
        if (op == O_PLUS) m_simple(M_ADDR4); else { need(RT_SUB); jsr_rt(RT_SUB); }
        return;
    }
    if (op == O_AMP || op == O_BAR || op == O_CARET) {
        if (hkb) { gen_expr(a); m_logk(op, kb); return; }
        if (fold(a)) { ka = fv; gen_expr(b); m_logk(op, ka); return; }
        operands(op, a, b); wb(R_MACRO); wb(M_LOGR4); wb(op); return;
    }
    if (op == O_STAR) {
        hka = fold(a); ka = fv;
        if (!hkb && hka) { t = a; a = b; b = t; kb = ka; hkb = 1; }
        if (hkb) {
            if (kb == 0) { gen_expr(a); insrn(MN_MVIW, 3, 0); return; }
            if (kb == 1) { gen_expr(a); return; }
            if (kb == 2 || kb == 4 || kb == 8) {
                gen_expr(a);
                m_simple(M_SHL1);
                if (kb >= 4) m_simple(M_SHL1);
                if (kb == 8) m_simple(M_SHL1);
                return;
            }
            if (kb == 256) {
                gen_expr(a); insr(MN_MVRLA, 3); insr(MN_MVARH, 3); insn(MN_LDAI, 0); insr(MN_MVARL, 3); return;
            }
        }
        operands(op, a, b); need(RT_MUL); jsr_rt(RT_MUL); return;
    }
    if (op == O_SLASH || op == O_PERCENT) {
        if (hkb && kb > 0 && (kb & (kb - 1)) == 0) {   /* power of two */
            sh = 0;
            for (t = kb; t > 1; t = t >> 1) sh++;
            gen_expr(a);
            if (op == O_PERCENT) { m_logk(O_AMP, kb - 1); return; }
            if (sh == 8) { insr(MN_MVRHA, 3); insr(MN_MVARL, 3); insn(MN_LDAI, 0); insr(MN_MVARH, 3); return; }
            if (sh <= 3) { for (i = 0; i < sh; i++) m_simple(M_SHR1); return; }
            insrn(MN_MVIW, 4, sh); need(RT_SHR); jsr_rt(RT_SHR); return;
        }
        operands(op, a, b); need(RT_DIVMOD); jsr_rt(RT_DIVMOD);
        if (op == O_PERCENT) insrr(MN_MOVRR, 5, 3);
        return;
    }
    if (op == O_SHL || op == O_SHR) {
        if (hkb) {
            gen_expr(a);
            if (kb == 0) return;
            if (kb >= 16) { insrn(MN_MVIW, 3, 0); return; }
            if (kb == 8) {
                if (op == O_SHL) { insr(MN_MVRLA, 3); insr(MN_MVARH, 3); insn(MN_LDAI, 0); insr(MN_MVARL, 3); }
                else { insr(MN_MVRHA, 3); insr(MN_MVARL, 3); insn(MN_LDAI, 0); insr(MN_MVARH, 3); }
                return;
            }
            if (kb <= 3) { for (i = 0; i < kb; i++) { if (op == O_SHL) m_simple(M_SHL1); else m_simple(M_SHR1); } return; }
            insrn(MN_MVIW, 4, kb);
        } else operands(op, a, b);
        if (op == O_SHL) { need(RT_SHL); jsr_rt(RT_SHL); }
        else { need(RT_SHR); jsr_rt(RT_SHR); }
        return;
    }
    fail("y1cc: operator not supported");
}

/* ---- conditions -------------------------------------------------------------------------------------------------- */
void materialize(int e) {                           /* a condition as a 0/1 VALUE in R3 */
    int t; int end;
    t = lbl(LK_T); end = lbl(LK_E);
    gen_cond(e, t, 1);
    insrn(MN_MVIW, 3, 0); insl(MN_BR, end);
    label_def(t); insrn(MN_MVIW, 3, 1); label_def(end);
}
int neg_rel(int rel) {
    if (rel == O_LT) return O_GE;
    if (rel == O_GE) return O_LT;
    if (rel == O_GT) return O_LE;
    if (rel == O_LE) return O_GT;
    if (rel == O_EQ) return O_NE;
    return O_EQ;
}
void gen_relcond(int rel, int a, int b, int label, int when) {
    int hka; int ka; int hkb; int kb; int t;
    if (!when) rel = neg_rel(rel);
    hka = fold(a); ka = fv;
    hkb = fold(b); kb = fv;
    if (is_narrow(a) && is_narrow(b) && !(hka && hkb)) {   /* two bytes: one compare (ACC = a, TMP = b) */
        if (hkb) { gen_byte_acc(a); insn(MN_LDTI, kb & 255); }
        else if (simple_byte(b)) { gen_byte_acc(a); byte_src(b); insa(MN_LDT); }
        else if (simple_byte(a)) { gen_byte_acc(b); ins0(MN_MVAT); gen_byte_acc(a); }
        else { gen_byte_acc(a); ins0(MN_PUSH); gen_byte_acc(b); ins0(MN_MVAT); ins0(MN_POP); }
        m_brel(rel, label, 0, 0);
        return;
    }
    /* 16 bits: L in R3, R in R4 or a constant; high bytes first, low bytes only when they are equal */
    if (!hkb && hka && (rel == O_EQ || rel == O_NE)) { t = a; a = b; b = t; kb = ka; hkb = 1; }
    if (hkb && kb == 0 && (rel == O_EQ || rel == O_NE)) {   /* x == 0 / x != 0: OR the bytes, one branch */
        gen_expr(a);
        insr(MN_MVRLA, 3); ins0(MN_MVAT); insr(MN_MVRHA, 3); ins0(MN_ORT);
        insl(rel == O_EQ ? MN_BRZ : MN_BRNZ, label);
        return;
    }
    if (hkb) {
        gen_expr(a);
        insr(MN_MVRHA, 3); insn(MN_LDTI, (kb >> 8) & 255);
        m_brel(rel, label, 1, kb);
        return;
    }
    operands(rel, a, b);
    insr(MN_MVRHA, 4); ins0(MN_MVAT); insr(MN_MVRHA, 3);
    m_brel(rel, label, 2, 0);
}
void gen_cond(int e, int label, int when) {         /* jump to label if (truth of e) == when, else fall through */
    int k; int f; int t; int j;
    k = nk[e];
    if (fold(e)) { if ((fv != 0) == (when != 0)) insl(MN_BR, label); return; }
    if (k == N_BIN && is_relop(na[e])) { gen_relcond(na[e], nb[e], nc[e], label, when); return; }
    if (k == N_UNARY && na[e] == O_NOT) { gen_cond(nb[e], label, !when); return; }
    if (k == N_LOGAND) {
        if (!when) { gen_cond(na[e], label, 0); gen_cond(nb[e], label, 0); }
        else { f = lbl(LK_A); gen_cond(na[e], f, 0); gen_cond(nb[e], label, 1); label_def(f); }
        return;
    }
    if (k == N_LOGOR) {
        if (when) { gen_cond(na[e], label, 1); gen_cond(nb[e], label, 1); }
        else { t = lbl(LK_O); gen_cond(na[e], t, 1); gen_cond(nb[e], label, 0); label_def(t); }
        return;
    }
    j = when ? MN_BRNZ : MN_BRZ;
    if (is_narrow(e)) { gen_byte_acc(e); insl(j, label); return; }   /* a byte: load it and test */
    if (k == N_BIN && na[e] == O_AMP && fold(nc[e]) && fv <= 255) {  /* (x & mask8) */
        t = fv;
        gen_expr(nb[e]); insr(MN_MVRLA, 3); insn(MN_ANDI, t); insl(j, label); return;
    }
    gen_expr(e);
    insr(MN_MVRLA, 3); ins0(MN_MVAT); insr(MN_MVRHA, 3); ins0(MN_ORT); insl(j, label);
}

/* ---- calls ------------------------------------------------------------------------------------------------------- */
int port(int e) {
    if (!fold(e) || fv > 15) fail("y1cc: port must be a constant 0..15");
    return fv;
}
int nth_arg(int e, int i) { int a; a = nb[e]; while (i && a) { a = nx[a]; i--; } return a; }
void gen_builtin(int e) {                           /* y1cc.c gen_call's builtins */
    int name; int nargs; int a; int b; int c; int i; int n; int hn; int base;
    name = na[e]; nargs = nc[e];
    if (name == B_PUTCHAR) {
        a = nth_arg(e, 0);
        if (is_narrow(a)) gen_byte_acc(a); else { gen_expr(a); insr(MN_MVRLA, 3); }
        need(RT_PUTC); jsr_rt(RT_PUTC); return;
    }
    if (name == B_GETCHAR) {
        need(RT_GETC); jsr_rt(RT_GETC);
        insr(MN_MVARL, 3); zext(); return;
    }
    if (name == B_PUTS) { gen_expr(nth_arg(e, 0)); need(RT_PUTS); need(RT_PUTC); jsr_rt(RT_PUTS); return; }
    if (name == B_PEEK) { gen_expr(nth_arg(e, 0)); deref_r3(K_CHAR, 0); return; }
    if (name == B_PEEKW) { gen_expr(nth_arg(e, 0)); deref_r3(K_INT, 0); return; }
    if (name == B_POKE || name == B_POKEW) {        /* memory at addr = value (byte / big-endian word) */
        a = nth_arg(e, 0); b = nth_arg(e, 1);
        if (name == B_POKE && simple_byte(b)) { gen_expr(a); gen_byte_acc(b); insr(MN_STAVR, 3); return; }
        if (is_leaf(a)) { gen_expr(b); gen_leaf(4, a); }
        else { gen_expr(a); insr(MN_PUSHR, 3); gen_expr(b); insr(MN_POPR, 4); }
        if (name == B_POKEW) { insr(MN_MVRHA, 3); insr(MN_STAVR, 4); insr(MN_INCR, 4); }
        insr(MN_MVRLA, 3); insr(MN_STAVR, 4); return;
    }
    if (name == B_INP) {
        n = port(nth_arg(e, 0));
        wb(R_CODE); wb(MN_INP); wb(F_P); wb(n);
        insr(MN_MVARL, 3); zext(); return;
    }
    if (name == B_OUTP) {                           /* always OUTA: the emulator's console (port 2) ignores OUTI */
        b = nth_arg(e, 1);
        if (is_narrow(b)) gen_byte_acc(b); else { gen_expr(b); insr(MN_MVRLA, 3); }
        n = port(nth_arg(e, 0));
        wb(R_CODE); wb(MN_OUTA); wb(F_P); wb(n);
        return;
    }
    if (name == B_HALT) { ins0(MN_HALT); return; }
    if (name == B_CALL) {                           /* call(addr): JSRUR to a computed address; R3 = what it returns */
        gen_expr(nth_arg(e, 0)); insrr(MN_MOVRR, 3, 7); insr(MN_JSRUR, 7); return;
    }
    if (name == B_ARGSTR) { insrn(MN_MVIW, 3, ARGBUF); return; }
    if (name == B_SYS) {                            /* sys(n, a, b, c): Y1/OS syscall n through SYSTAB */
        if (nargs < 1 || nargs > 4) fail("y1cc: sys() takes 1 to 4 arguments (the number, then up to three)");
        a = nth_arg(e, 0);
        hn = fold(a); n = fv;
        if (hn && n > SYSMAX) { e_start("y1cc: sys() number must be 0.."); e_n(SYSMAX); e_go(); }
        if (!hn) { gen_expr(a); m_simple(M_SHL1); m_addk(SYSTAB); insr(MN_PUSHR, 3); }
        base = npark;
        i = 0;
        for (c = nx[a]; c; c = nx[c]) {            /* a later argument that calls anything could run a sys() itself */
            gen_expr(c);
            if (a_haz[c]) {
                insr(MN_PUSHR, 3);
                if (npark >= PARK_MAX) fail("y1cc: too many parked arguments");
                park[npark] = i; npark++;
            } else insrn(MN_STR, 3, SYSARG + 2 * i);
            i++;
        }
        while (npark > base) { npark--; insr(MN_POPR, 4); insrn(MN_STR, 4, SYSARG + 2 * park[npark]); }
        if (hn) insrn(MN_LDR, 7, SYSTAB + 2 * n);
        else {
            insr(MN_POPR, 3); insr(MN_LDAVR, 3); ins0(MN_MVAT); insr(MN_INCR, 3);
            insr(MN_LDAVR, 3); insr(MN_MVARL, 7); ins0(MN_MVTA); insr(MN_MVARH, 7);
        }
        insr(MN_JSRUR, 7); insrn(MN_LDR, 3, SYSRES); return;
    }
    if (name == B_FUNCADDR) {                       /* funcaddr(f): the address of function f, as an int */
        if (!a_v[e]) {
            e_start("y1cc: funcaddr() wants the name of a defined function (in "); e_name(cur_name); e_s(")"); e_go();
        }
        wb(R_CODE); wb(MN_MVIW); wb(F_RA); wb(3); wb(A_FUNC); wi(a_v[e]); wb(0); return;
    }
    /* bios(addr, r7, acc) -> ACC */
    if (!fold(nth_arg(e, 0))) fail("y1cc: bios() address must be a constant");
    n = fv;
    gen_expr(nth_arg(e, 1)); insrr(MN_MOVRR, 3, 7);
    c = nth_arg(e, 2);
    if (is_narrow(c)) gen_byte_acc(c); else { gen_expr(c); insr(MN_MVRLA, 3); }
    insn(MN_JSR, n); insr(MN_MVARL, 3); zext();
}
void frame(int e, int restore) {                    /* frame_save / frame_restore of the callee: M_FSAVE / M_FREST */
    if (a_fer[e]) { e_start("y1cc: unknown type '"); e_name(a_fer[e]); e_s("'"); e_go(); }
    if (!a_c[e]) return;
    wb(R_MACRO); wb(restore ? M_FREST : M_FSAVE); wi(a_fvar[e]); wi(a_c[e]);
}
void gen_call(int e) {
    int name; int nargs; int a; int fn; int rec; int v; int base;
    name = na[e]; nargs = nc[e];
    if (name >= B_GETCHAR && name <= B_FUNCADDR) { gen_builtin(e); return; }
    fn = a_v[e];
    if (!fn) { e_start("y1cc: call of undeclared function '"); e_name(name); e_s("'"); e_go(); }
    if (nargs != a_b[e]) {
        e_start("y1cc: "); e_name(name); e_s("() takes "); e_n(a_b[e]); e_s(" argument(s), "); e_n(nargs);
        e_s(" given"); e_go();
    }
    if (!a_p[e]) { e_start("y1cc: "); e_name(name); e_s("() has no definition"); e_go(); }
    rec = a_s[e] & 1;                               /* a call inside a recursive cycle (the callee can reach us) */
    if (rec) {
        for (a = nb[e]; a; a = nx[a]) {
            if (a_eerr[a]) raise(a_eerr[a]);
            v = a_esc[a];
            if (v) {
                e_start("y1cc: "); e_name(cur_name); e_s("(): the address of local '"); e_name(v);
                e_s("' is passed to "); e_name(name); e_s("(), which can re-enter "); e_name(cur_name);
                e_s("() (a recursive function's locals live in static slots): use a global"); e_go();
            }
        }
        frame(e, 0);
    }
    base = npark;
    for (a = nb[e]; a; a = nx[a]) {
        v = a_tv[a];
        gen_expr(a);
        if (a_ts[a] && !is_narrow(a)) zext();
        if (a_haz[a]) {
            insr(MN_PUSHR, 3);
            if (npark >= PARK_MAX) fail("y1cc: too many parked arguments");
            park[npark] = v; npark++;
        } else insv(MN_STR, 3, v);
    }
    while (npark > base) { npark--; insr(MN_POPR, 4); insv(MN_STR, 4, park[npark]); }
    wb(R_CODE); wb(MN_JSR); wb(F_A); wb(A_FUNC); wi(fn); wb(0);
    if (rec) frame(e, 1);
}
void gen_expr_stmt(int e) {
    if (nk[e] == N_ASSIGN) gen_assign(na[e], nb[e], 0);
    else if (nk[e] == N_PREINC || nk[e] == N_POSTINC) gen_assign(nb[e], nd[e], 0);
    else gen_expr(e);
}

/* ---- the stream -------------------------------------------------------------------------------------------------- */
void read_tree(void) {                              /* a hole's tree with cc7's attributes */
    int n;
    n = ri(inh);
    if (n >= TREE_MAX) fail("y1cc: expression too big (TREE_MAX)");
    tn = n;
    rarrc(inh, nk + 1, n); rarr(inh, na + 1, n); rarr(inh, nb + 1, n); rarr(inh, nc + 1, n);
    rarr(inh, nd + 1, n); rarr(inh, nx + 1, n);
    rarrc(inh, a_fok + 1, n); rarr(inh, a_fv + 1, n); rarrc(inh, a_ferr + 1, n);
    rarr(inh, a_tb + 1, n); rarrc(inh, a_tp + 1, n); rarrc(inh, a_terr + 1, n);
    rarr(inh, a_lb + 1, n); rarrc(inh, a_lp + 1, n); rarrc(inh, a_lerr + 1, n);
    rarr(inh, a_v + 1, n); rarr(inh, a_b + 1, n); rarrc(inh, a_p + 1, n); rarr(inh, a_c + 1, n);
    rarrc(inh, a_s + 1, n); rarrc(inh, a_verr + 1, n); rarr(inh, a_fvar + 1, n); rarr(inh, a_fer + 1, n);
    rarr(inh, a_tv + 1, n); rarrc(inh, a_ts + 1, n); rarrc(inh, a_haz + 1, n); rarr(inh, a_esc + 1, n);
    rarrc(inh, a_eerr + 1, n);
    n = rb(inh);
    if (n >= TERR_MAX) fail("y1cc: too many errors in one expression (TERR_MAX)");
    rarrc(inh, e_code + 1, n); rarr(inh, e_a1 + 1, n); rarr(inh, e_a2 + 1, n);
}
void copy(int n) { while (n) { wb(rb(inh)); n--; } }
void load_structs(void) {                           /* W.sym: the struct tags and sizes */
    int h;
    h = ropen(".sym");
    ri(h); ri(h);
    nstructs = ri(h);
    if (nstructs >= STRUCTS_MAX) fail("y1cc: too many structs (STRUCTS_MAX)");
    skip(h, 6);
    rarr(h, s_tag + 1, nstructs); rarr(h, s_size + 1, nstructs);
    io_close(h);
}
char rlen[] = {0, 0, 2, 3, 2, 0, 4, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0};   /* operand bytes of cc6's simple records */
void y1cc_main(void) {
    int c; int hk; int r; int r2; int sym; int when; int n; int i; int narrow;
    p_args();
    load_structs();
    inh = ropen(".se");
    wopen(".em");
    for (;;) {
        c = rb(inh);
        if (c == 256) break;
        if (c == R_ERROR) { rs(inh, ebuf, EBUF_MAX); io_fail(ebuf); }   /* cc6's deferred error: its turn now */
        if (c != R_HOLE) {
            wb(c);
            if (c == R_CODE) { wb(rb(inh)); r = rb(inh); wb(r); if (r == F_L) copy(2); }
            else if (c == R_FUNC) {
                copy(2); cur_name = ri(inh); cur_rbase = ri(inh); cur_rptr = rb(inh);
                wi(cur_name); wi(cur_rbase); wb(cur_rptr);
                nsym = 0; npark = 0;
            } else copy(rlen[c]);
            continue;
        }
        hk = rb(inh);
        r = ri(inh);
        if (hk == H_COND) { sym = ri(inh); when = rb(inh); read_tree(); gen_cond(r, sym, when); }
        else if (hk == H_EXPR) { read_tree(); gen_expr_stmt(r); }
        else if (hk == H_RET) {
            read_tree();
            gen_expr(r);
            if (cur_rbase == K_CHAR && cur_rptr == 0 && !is_narrow(r)) zext();
        } else if (hk == H_DECL) { r2 = ri(inh); read_tree(); gen_assign(r, r2, 0); }
        else {                                      /* H_SWITCH: the value, then the dispatch (cc9) */
            sym = ri(inh); n = ri(inh);
            if (n >= CASES_MAX) fail("y1cc: too many cases in a switch");
            for (i = 0; i < n; i++) { cs_val[i] = ri(inh); cs_sym[i] = ri(inh); }
            read_tree();
            gen_expr(r);
            narrow = 0;
            if (n) narrow = is_narrow(r);           /* y1cc.c asks only when there are cases */
            wb(R_MACRO); wb(M_SWITCH); wb(narrow); wi(sym); wi(n);
            for (i = 0; i < n; i++) { wi(cs_val[i]); wi(cs_sym[i]); }
        }
    }
    io_close(inh);
    wclose();
}
