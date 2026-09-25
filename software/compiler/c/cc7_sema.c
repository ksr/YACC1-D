/* cc7_sema.c - pass 7 of the multi-pass y1cc (2026-09-24): the expression analysis. For every hole in W.st it
   works out what y1cc.c's code generator would ask about each node of the tree - the constant value (fold), the
   type (type_of), the lvalue type (type_lval), the variable a name is (vinfo), the member a .m / ->m is
   (struct_member), sizeof, and for calls the callee, the recursion case, the argument hazards and escapes - and
   writes them beside the node, so that cc8 needs no symbol table.

     cc7 W          reads W.st, W.sym, W.cg (the reach rows), W.lit (the lengths); writes W.se

   An analysis that fails does not stop this pass: the error it would raise is recorded (a "poisoned" attribute,
   code + two names, pdefs.h E_*) and cc8 raises it only if and when its code generator asks for that attribute,
   which is the moment y1cc.c would have failed. Every analysis below is y1cc.c's with that one change: after each
   call that can fail, `if (aerr) return`.

   A hole in W.se: R_HOLE hk operands (as in W.st), n(2), then columns of the nodes 1..n (b = bytes, w = words):
     the node: kind(b) a b c d x (w), as in W.st
     fold ok(b) value(w) err(b); type_of base(w) ptr(b) err(b); type_lval base(w) ptr(b) err(b)
     v(w) b(w) p(b) c(w) s(b) verr(b) fvar(w) ferr(w), by the node's kind:
       N_ID             v = the variable (vinfo), b p c = its base, pointer depth, count; s = char slot
       N_MEMBER/ARROW   v = offset, b p c = base, pointer depth, count (struct_member(member_tag(e), m))
       N_SIZEOF*        v = the size
       N_CALL           v = the function (funcaddr(): the named one, when it is defined), b = its parameter
                        count, p = defined (laid out), c = its frame bytes, s = 1 a call inside a recursive
                        cycle + 2 it returns char, fvar = its first variable, ferr = frame_err (W.sym)
       verr = the error of v (vinfo, struct_member, sizeof)
     tv(w) ts(b) haz(b) esc(w) eerr(b), for a call's argument: the parameter it is stored in (and whether that is a
       char slot), whether it waits on the stack, escapes() (the local whose address it carries) and its error
   then nerr(b) and the error columns code(b) a1(w) a2(w). N_PREINC/N_POSTINC get nd = a new N_BIN (op, lvalue, 1),
   the node y1cc.c's gen_expr creates for them. cc8_emit.c has the same arrays. */
#include "pcommon.c"

#define W_ANYCALL 2
#define W_REACH 3
#define W_MENTION 4

int fn_hash[64];                /* name -> function, name -> global: hash chains (a table per name would cost 2 */
int fn_next[FUNCS_MAX];         /* bytes for every name of the program; structs are few and are searched) */
int gl_hash[64];
int gl_next[GLOBS_MAX];
int s_tag[STRUCTS_MAX];
int lit_len[LITS_MAX];
int nlits;

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

int f_name[FUNCS_MAX];
int f_rbase[FUNCS_MAX];
char f_rptr[FUNCS_MAX];
int f_np[FUNCS_MAX];
int f_body[FUNCS_MAX];
char f_live[FUNCS_MAX];
int f_vfirst[FUNCS_MAX];
int f_vn[FUNCS_MAX];
int f_frame[FUNCS_MAX];
int f_ferr[FUNCS_MAX];
int nfuncs;
char rbits[REACH_BYTES];

int v_name[VARS_MAX];
int v_base[VARS_MAX];
char v_ptr[VARS_MAX];
int v_cnt[VARS_MAX];
char v_slot[VARS_MAX];
int nvars;

/* the tree and its attributes */
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
int a_v[TREE_MAX];              /* by kind (above) */
int a_b[TREE_MAX];
char a_p[TREE_MAX];
int a_c[TREE_MAX];
char a_s[TREE_MAX];
char a_verr[TREE_MAX];
int a_fvar[TREE_MAX];
int a_fer[TREE_MAX];
int a_tv[TREE_MAX];             /* a call's argument: the parameter slot it is stored in */
char a_ts[TREE_MAX];
char a_haz[TREE_MAX];           /*   it waits on the stack (a later argument can run the callee / a sys()) */
int a_esc[TREE_MAX];            /*   escapes(): the local whose address it carries */
char a_eerr[TREE_MAX];
char e_code[TERR_MAX];
int e_a1[TERR_MAX];
int e_a2[TERR_MAX];
int nterr;

int cur_fn;
int cur_vfirst;
int cur_vn;
int aerr;                       /* the poisoned result of the analysis in progress: an error index, 0 = fine */
int fv;
int tb;
int tp;
int sm_off;
int sm_base;
int sm_ptr;
int sm_cnt;
int wmode;
int wname;
int wfn;                        /* W_REACH: the function wname names */
int wfound;
int inh;

void pass_fail(char *msg) { io_fail(msg); }
int mkerr(int code, int a1, int a2);
int fn_of(int name);
int glob_of(int name);
int st_of(int tag);
int local_var(int name);
int vinfo(int name);
void struct_member(int tag, int mname);
int member_tag(int e);
int builtin_type(int name);
void type_of(int e);
void type_lval(int e);
int dec_ptr(int p);
int size_of(int base, int ptr);
int fold(int e);
int fold_bin(int op, int l, int r);
int is_array(int e);
int sizeof_expr(int e);
int local_root(int x);
int escapes(int e);
int bit(int f, int g);
void walk(int n);
void walk_list(int n);
int reaches(int callee, int n);
int any_call(int n);
int mentions(int n, int name);
int nth_arg(int e, int i);
void analyse(void);
void call_info(int e);
void copy(int n);
void load_sym(void);

int mkerr(int code, int a1, int a2) {              /* the index of error (code, a1, a2), each distinct one once */
    int i;
    for (i = 1; i <= nterr; i++) if (e_code[i] == code && e_a1[i] == a1 && e_a2[i] == a2) return i;
    if (nterr + 1 >= TERR_MAX) fail("y1cc: too many errors in one expression (TERR_MAX)");
    nterr++;
    e_code[nterr] = code; e_a1[nterr] = a1; e_a2[nterr] = a2;
    return nterr;
}

/* ---- symbols and types (y1cc.c), poisoned instead of fatal ---------------------------------------------------- */
int local_var(int name) {
    int i;
    for (i = 0; i < cur_vn; i++) if (v_name[cur_vfirst + i] == name) return cur_vfirst + i;
    return 0;
}
int vinfo(int name) {
    int v;
    v = local_var(name);
    if (v) return v;
    v = glob_of(name);
    if (v) return v;
    aerr = mkerr(E_UNDECL, name, f_name[cur_fn]);
    return 0;
}
void struct_member(int tag, int mname) {            /* -> sm_off, sm_base, sm_ptr, sm_cnt */
    int s; int i; int m;
    s = st_of(tag);
    if (!s) { aerr = mkerr(E_NOTSTRUCT, tag, 0); return; }
    m = 0;
    for (i = 0; i < s_mn[s]; i++) if (m_name[s_mfirst[s] + i] == mname) m = s_mfirst[s] + i;   /* the last wins */
    if (!m) { aerr = mkerr(E_NOMEMBER, tag, mname); return; }
    sm_off = m_off[m]; sm_base = m_base[m]; sm_ptr = m_ptr[m]; sm_cnt = m_cnt[m];
}
int member_tag(int e) {
    if (nk[e] == N_MEMBER) type_lval(na[e]); else type_of(na[e]);
    return tb;
}
int builtin_type(int name) {                        /* y1cc.py BUILTIN_TYPES: 1 with tb/tp set, or 0 */
    if (name == B_GETCHAR || name == B_PEEK || name == B_PEEKW || name == B_INP || name == B_BIOS ||
        name == B_CALL || name == B_SYS || name == B_FUNCADDR) { tb = K_INT; tp = 0; return 1; }
    if (name == B_PUTCHAR || name == B_PUTS || name == B_POKE || name == B_POKEW || name == B_OUTP ||
        name == B_HALT) { tb = K_VOID; tp = 0; return 1; }
    if (name == B_ARGSTR) { tb = K_CHAR; tp = 1; return 1; }
    return 0;
}
int dec_ptr(int p) { if (p > 0) return p - 1; return 0; }
void type_of(int e) {                               /* -> tb, tp: the type of e's VALUE (arrays decay) */
    int k; int v; int op; int lb_; int lp; int rb; int rp; int t;
    k = nk[e];
    if (k == N_NUM) { tb = K_INT; tp = 0; return; }
    if (k == N_MEMBER || k == N_ARROW) {
        t = member_tag(e); if (aerr) return;
        struct_member(t, nb[e]); if (aerr) return;
        tb = sm_base; tp = sm_cnt ? sm_ptr + 1 : sm_ptr;
        return;
    }
    if (k == N_STR) { tb = K_CHAR; tp = 1; return; }
    if (k == N_ID) {
        v = vinfo(na[e]); if (aerr) return;
        tb = v_base[v]; tp = v_cnt[v] ? v_ptr[v] + 1 : v_ptr[v];
        return;
    }
    if (k == N_UNARY) {
        op = na[e];
        if (op == O_AMP) { type_lval(nb[e]); if (aerr) return; tp++; return; }
        if (op == O_STAR) { type_of(nb[e]); if (aerr) return; tp = dec_ptr(tp); return; }
        tb = K_INT; tp = 0; return;
    }
    if (k == N_INDEX) { type_of(na[e]); if (aerr) return; tp = dec_ptr(tp); return; }
    if (k == N_ASSIGN) { type_lval(na[e]); return; }
    if (k == N_PREINC || k == N_POSTINC) { type_lval(nb[e]); return; }
    if (k == N_COND) { type_of(nb[e]); return; }
    if (k == N_CALL) {
        if (builtin_type(na[e])) return;
        v = fn_of(na[e]);
        if (!v) { aerr = mkerr(E_CALLUNDECL, na[e], 0); return; }
        tb = f_rbase[v]; tp = f_rptr[v];
        return;
    }
    if (k == N_BIN) {
        op = na[e];
        if (op == O_PLUS || op == O_MINUS) {
            type_of(nb[e]); if (aerr) return;
            lb_ = tb; lp = tp;
            type_of(nc[e]); if (aerr) return;
            rb = tb; rp = tp;
            if (lp > 0) { tb = lb_; tp = lp; return; }
            if (rp > 0 && op == O_PLUS) { tb = rb; tp = rp; return; }
        }
        tb = K_INT; tp = 0; return;
    }
    tb = K_INT; tp = 0;
}
void type_lval(int e) {                             /* -> tb, tp: the type as an lvalue (no array decay) */
    int k; int v; int t;
    k = nk[e];
    if (k == N_ID) { v = vinfo(na[e]); if (aerr) return; tb = v_base[v]; tp = v_ptr[v]; return; }
    if (k == N_UNARY && na[e] == O_STAR) {
        type_of(nb[e]); if (aerr) return;
        if (tp < 1) { aerr = mkerr(E_DEREF, 0, 0); return; }
        tp--; return;
    }
    if (k == N_INDEX) {
        type_of(na[e]); if (aerr) return;
        if (tp < 1) { aerr = mkerr(E_INDEX, 0, 0); return; }
        tp--; return;
    }
    if (k == N_MEMBER || k == N_ARROW) {
        t = member_tag(e); if (aerr) return;
        struct_member(t, nb[e]); if (aerr) return;
        tb = sm_base; tp = sm_ptr; return;
    }
    aerr = mkerr(E_NOTLVAL, k, 0);
}
int size_of(int base, int ptr) {
    if (ptr > 0 || base == K_INT) return 2;
    if (base == K_CHAR) return 1;
    if (st_of(base)) return s_size[st_of(base)];
    aerr = mkerr(E_UNKTYPE, base, 0);
    return 0;
}
int fold(int e) {                                   /* 1 with the value (mod 2^16) in fv, or 0 */
    int k; int v; int op;
    k = nk[e];
    if (k == N_NUM) { fv = na[e] & 65535; return 1; }
    if (k == N_UNARY) {
        op = na[e];
        if (op != O_MINUS && op != O_TILDE && op != O_NOT) return 0;
        if (!fold(nb[e])) return 0;
        v = fv;
        if (op == O_MINUS) fv = (65535 - v + 1) & 65535;
        else if (op == O_TILDE) fv = 65535 - v;
        else fv = v == 0;
        return 1;
    }
    if (k == N_BIN) return fold_bin(na[e], nb[e], nc[e]);
    if (k == N_SIZEOFT) { fv = size_of(na[e], nb[e]); if (aerr) return 0; return 1; }
    if (k == N_COND) {
        if (!fold(na[e])) return 0;
        if (fv) return fold(nb[e]);
        return fold(nc[e]);
    }
    return 0;
}
int fold_bin(int op, int l, int r) {
    int a; int b; int oka; int okb; int x;
    oka = fold(l); if (aerr) return 0;
    a = fv;
    okb = fold(r); if (aerr) return 0;
    b = fv;
    if (!oka || !okb) return 0;
    if ((op == O_SLASH || op == O_PERCENT) && b == 0) return 0;
    x = 0;
    if (op == O_PLUS) x = a + b;
    else if (op == O_MINUS) x = a + 65535 - b + 1;
    else if (op == O_STAR) x = mul16(a, b);
    else if (op == O_SLASH) x = a / b;
    else if (op == O_PERCENT) x = a % b;
    else if (op == O_AMP) x = a & b;
    else if (op == O_BAR) x = a | b;
    else if (op == O_CARET) x = a ^ b;
    else if (op == O_SHL) x = (a << (b & 15)) & 65535;
    else if (op == O_SHR) x = a >> (b & 15);
    else if (op == O_EQ) x = a == b;
    else if (op == O_NE) x = a != b;
    else if (op == O_LT) x = a < b;
    else if (op == O_GT) x = a > b;
    else if (op == O_LE) x = a <= b;
    else if (op == O_GE) x = a >= b;
    fv = x & 65535;
    return 1;
}
int is_array(int e) {                               /* e is an array object (not a pointer variable) */
    int v; int t;
    if (nk[e] == N_ID) { v = vinfo(na[e]); if (aerr) return 0; return v_cnt[v] > 0; }
    if (nk[e] == N_MEMBER || nk[e] == N_ARROW) {
        t = member_tag(e); if (aerr) return 0;
        struct_member(t, nb[e]); if (aerr) return 0;
        return sm_cnt > 0;
    }
    return 0;
}
int sizeof_expr(int e) {
    int x; int v; int n; int t;
    if (nk[e] == N_SIZEOFT) return size_of(na[e], nb[e]);
    x = na[e];
    if (nk[x] == N_ID) {
        v = vinfo(na[x]); if (aerr) return 0;
        if (v_cnt[v]) { n = size_of(v_base[v], v_ptr[v]); if (aerr) return 0; return mul16(v_cnt[v], n); }
        return size_of(v_base[v], v_ptr[v]);
    }
    if (nk[x] == N_STR) return lit_len[na[x]] + 1;
    t = is_array(x); if (aerr) return 0;
    if (t) {
        t = member_tag(x); if (aerr) return 0;
        struct_member(t, nb[x]); if (aerr) return 0;
        n = size_of(sm_base, sm_ptr); if (aerr) return 0;
        return mul16(sm_cnt, n);
    }
    type_of(x); if (aerr) return 0;
    return size_of(tb, tp);
}
int local_root(int x) {                             /* the local whose storage the lvalue x lies in, or 0 */
    int t;
    if (nk[x] == N_ID) return local_var(na[x]) ? na[x] : 0;
    if (nk[x] == N_MEMBER) return local_root(na[x]);
    if (nk[x] == N_INDEX) { t = is_array(na[x]); if (aerr) return 0; if (t) return local_root(na[x]); }
    return 0;
}
int escapes(int e) {                                /* a local whose ADDRESS the value of e may carry */
    int k; int r;
    k = nk[e];
    if (k == N_UNARY && na[e] == O_AMP) return local_root(nb[e]);
    if (k == N_ID || k == N_MEMBER || k == N_INDEX) { r = is_array(e); if (aerr) return 0; if (r) return local_root(e); }
    if (k == N_BIN && (na[e] == O_PLUS || na[e] == O_MINUS)) {
        r = escapes(nb[e]); if (aerr) return 0;
        if (r) return r;
        return escapes(nc[e]);
    }
    if (k == N_COND) { r = escapes(nb[e]); if (aerr) return 0; if (r) return r; return escapes(nc[e]); }
    if (k == N_ASSIGN) return escapes(nb[e]);
    return 0;
}

/* ---- the call graph over the tree (y1cc.c walk: W_REACH, W_ANYCALL, W_MENTION) ------------------------------ */
int bit(int f, int g) { return (rbits[f * REACH_ROW + (g >> 3)] & (1 << (g & 7))) != 0; }
int fn_of(int name) { int f; for (f = fn_hash[name & 63]; f; f = fn_next[f]) if (f_name[f] == name) return f; return 0; }
int glob_of(int name) { int v; for (v = gl_hash[name & 63]; v; v = gl_next[v]) if (v_name[v] == name) return v; return 0; }
int st_of(int tag) {                                /* the struct a tag names (the last definition wins), or 0 */
    int s;
    if (!tag) return 0;
    for (s = nstructs; s > 0; s--) if (s_tag[s] == tag) return s;
    return 0;
}
void walk_list(int n) { while (n) { walk(n); n = nx[n]; } }
void walk(int n) {
    int k; int c; int f;
    if (!n) return;
    k = nk[n];
    if (k == N_CALL) {
        c = na[n];
        if (wmode == W_ANYCALL) wfound = 1;
        else if (wmode == W_REACH) {
            f = fn_of(c);
            if (c == wname || (f && f_body[f] && wfn && bit(f, wfn))) wfound = 1;
        }
        walk_list(nb[n]);
        return;
    }
    if (k == N_ID) { if (wmode == W_MENTION && na[n] == wname) wfound = 1; return; }
    if (k == N_UNARY || k == N_PREINC || k == N_POSTINC) { walk(nb[n]); return; }
    if (k == N_SIZEOFE || k == N_MEMBER || k == N_ARROW) { walk(na[n]); return; }
    if (k == N_INDEX || k == N_ASSIGN || k == N_LOGOR || k == N_LOGAND) { walk(na[n]); walk(nb[n]); return; }
    if (k == N_COND) { walk(na[n]); walk(nb[n]); walk(nc[n]); return; }
    if (k == N_BIN) { walk(nb[n]); walk(nc[n]); return; }
}
int reaches(int callee, int n) { wmode = W_REACH; wname = callee; wfn = fn_of(callee); wfound = 0; walk(n); return wfound; }
int any_call(int n) { wmode = W_ANYCALL; wfound = 0; walk(n); return wfound; }
int mentions(int n, int name) { wmode = W_MENTION; wname = name; wfound = 0; walk(n); return wfound; }
int nth_arg(int e, int i) { int a; a = nb[e]; while (i && a) { a = nx[a]; i--; } return a; }

/* ---- the attributes of every node ------------------------------------------------------------------------------- */
void call_info(int e) {                             /* gen_call's analysis: the call's and its arguments' attributes */
    int name; int fn; int rec; int a; int i; int v; int later; int hazard; int pn;
    name = na[e]; fn = fn_of(name);
    a_s[e] = 2 * (fn && f_rbase[fn] == K_CHAR && f_rptr[fn] == 0);   /* is_narrow() of the call */
    if (name == B_FUNCADDR) {                       /* funcaddr(f): f when it names a defined (live) function */
        a = nb[e];
        if (nc[e] == 1 && nk[a] == N_ID) { v = fn_of(na[a]); if (v && f_live[v]) a_v[e] = v; }
        return;
    }
    if (name == B_SYS) {                            /* a later argument that calls anything could run a sys() itself */
        a = nb[e];
        if (!a) return;
        for (a = nx[a]; a; a = nx[a])
            for (later = nx[a]; later; later = nx[later]) if (!a_haz[a] && any_call(later)) a_haz[a] = 1;
        return;
    }
    if (!fn) return;
    rec = f_body[fn] && bit(fn, cur_fn);
    a_v[e] = fn; a_b[e] = f_np[fn]; a_p[e] = f_live[fn]; a_c[e] = f_frame[fn]; a_s[e] = a_s[e] | rec;
    a_fvar[e] = f_vfirst[fn]; a_fer[e] = f_ferr[fn];
    if (!f_live[fn]) return;                        /* gen_call stops with an error before the arguments */
    i = 0;
    for (a = nb[e]; a; a = nx[a]) {
        if (rec) { aerr = 0; a_esc[a] = escapes(a); a_eerr[a] = aerr; }
        v = f_vfirst[fn] + i;
        if (i < f_vn[fn]) { a_tv[a] = v; a_ts[a] = v_slot[v]; }
        hazard = 0;
        for (later = nx[a]; later; later = nx[later]) if (!hazard && reaches(name, later)) hazard = 1;
        if (rec && fn == cur_fn && !hazard && i < f_vn[fn]) {   /* a self-call: the store overwrites our own parameter */
            pn = v_name[v];
            for (later = nx[a]; later; later = nx[later]) if (!hazard && mentions(later, pn)) hazard = 1;
        }
        a_haz[a] = hazard;
        i++;
    }
}
void analyse(void) {
    int e; int k; int t; int v;
    for (e = 0; e <= tn; e++) {
        a_v[e] = 0; a_b[e] = 0; a_p[e] = 0; a_c[e] = 0; a_s[e] = 0; a_verr[e] = 0; a_fvar[e] = 0; a_fer[e] = 0;
        a_tv[e] = 0; a_ts[e] = 0; a_haz[e] = 0; a_esc[e] = 0; a_eerr[e] = 0;
    }
    for (e = 1; e <= tn; e++) {
        k = nk[e];
        aerr = 0; t = fold(e); a_fok[e] = t && !aerr; a_fv[e] = fv; a_ferr[e] = aerr;
        aerr = 0; type_of(e); a_tb[e] = tb; a_tp[e] = tp; a_terr[e] = aerr;
        aerr = 0; type_lval(e); a_lb[e] = tb; a_lp[e] = tp; a_lerr[e] = aerr;
        aerr = 0;
        if (k == N_ID) {
            v = vinfo(na[e]);
            a_v[e] = v; a_b[e] = v_base[v]; a_p[e] = v_ptr[v]; a_c[e] = v_cnt[v]; a_s[e] = v_slot[v];
        } else if (k == N_MEMBER || k == N_ARROW) {
            t = member_tag(e);
            if (!aerr) struct_member(t, nb[e]);
            if (!aerr) { a_v[e] = sm_off; a_b[e] = sm_base; a_p[e] = sm_ptr; a_c[e] = sm_cnt; }
        } else if (k == N_SIZEOFT || k == N_SIZEOFE) a_v[e] = sizeof_expr(e);
        a_verr[e] = aerr;
    }
    for (e = 1; e <= tn; e++) if (nk[e] == N_CALL) call_info(e);
}

/* ---- the stream -------------------------------------------------------------------------------------------------- */
char rlen[] = {0, 0, 2, 3, 2, 0, 4, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0};   /* operand bytes of cc6's simple records */
char flen[] = {0, 1, 2, 2, 0, 3, 3, 2, 0, 1};       /* operand bytes of cc6's R_CODE forms (F_A, F_RA: never) */
void copy(int n) { while (n) { wb(rb(inh)); n--; } }
void y1cc_main(void) {
    int c; int hk; int n; int e; int k; int b; int one;
    p_args();
    load_sym();
    inh = ropen(".st");
    wopen(".se");
    for (;;) {
        c = rb(inh);
        if (c == 256) break;
        wb(c);
        if (c == R_ERROR) { rs(inh, ebuf, EBUF_MAX); ws(ebuf); break; }
        if (c == R_FUNC) {
            cur_fn = ri(inh); wi(cur_fn); copy(5);
            cur_vfirst = f_vfirst[cur_fn]; cur_vn = f_vn[cur_fn];
            continue;
        }
        if (c == R_CODE) { wb(rb(inh)); k = rb(inh); wb(k); copy(flen[k]); continue; }
        if (c != R_HOLE) { copy(rlen[c]); continue; }
        hk = rb(inh); wb(hk);
        if (hk == H_COND) copy(5);
        else if (hk == H_DECL) copy(4);
        else if (hk == H_SWITCH) { copy(4); n = ri(inh); wi(n); copy(n * 4); }
        else copy(2);
        n = ri(inh);
        if (n + 1 >= TREE_MAX) fail("y1cc: expression too big (TREE_MAX)");
        tn = n; nterr = 0;
        rarrc(inh, nk + 1, n); rarr(inh, na + 1, n); rarr(inh, nb + 1, n); rarr(inh, nc + 1, n);
        rarr(inh, nd + 1, n); rarr(inh, nx + 1, n);
        nk[0] = 0; na[0] = 0; nb[0] = 0; nc[0] = 0; nd[0] = 0; nx[0] = 0;
        for (e = 1; e <= n; e++) {                  /* ++x, x++: the BIN node y1cc.c's gen_expr would make */
            k = nk[e];
            if (k == N_PREINC || k == N_POSTINC) {
                if (tn + 3 >= TREE_MAX) fail("y1cc: expression too big (TREE_MAX)");
                tn++; one = tn;
                nk[one] = N_NUM; na[one] = 1; nb[one] = 0; nc[one] = 0; nd[one] = 0; nx[one] = 0;
                tn++; b = tn;
                nk[b] = N_BIN; na[b] = na[e] == O_INC ? O_PLUS : O_MINUS; nb[b] = nb[e]; nc[b] = one;
                nd[b] = 0; nx[b] = 0;
                nd[e] = b;
            }
        }
        analyse();
        n = tn;
        wi(n);
        warrc(nk + 1, n); warr(na + 1, n); warr(nb + 1, n); warr(nc + 1, n); warr(nd + 1, n); warr(nx + 1, n);
        warrc(a_fok + 1, n); warr(a_fv + 1, n); warrc(a_ferr + 1, n);
        warr(a_tb + 1, n); warrc(a_tp + 1, n); warrc(a_terr + 1, n);
        warr(a_lb + 1, n); warrc(a_lp + 1, n); warrc(a_lerr + 1, n);
        warr(a_v + 1, n); warr(a_b + 1, n); warrc(a_p + 1, n); warr(a_c + 1, n); warrc(a_s + 1, n);
        warrc(a_verr + 1, n); warr(a_fvar + 1, n); warr(a_fer + 1, n);
        warr(a_tv + 1, n); warrc(a_ts + 1, n); warrc(a_haz + 1, n); warr(a_esc + 1, n); warrc(a_eerr + 1, n);
        wb(nterr);
        warrc(e_code + 1, nterr); warr(e_a1 + 1, nterr); warr(e_a2 + 1, nterr);
    }
    io_close(inh);
    wclose();
}
void load_sym(void) {                               /* W.sym (cc5_layout.c), W.cg's reach rows, W.lit's lengths */
    int h; int i; int k; int n; int ng;
    h = ropen(".lit");
    nlits = ri(h);
    if (nlits >= LITS_MAX) fail("y1cc: too many string literals (LITS_MAX)");
    for (i = 1; i <= nlits; i++) { n = ri(h); lit_len[i] = n; skip(h, n); }
    io_close(h);
    h = ropen(".cg");                               /* the reach rows (cc4_calls.c) */
    nfuncs = ri(h); n = ri(h);
    if (nfuncs >= FUNCS_MAX || n > REACH_ROW || (nfuncs + 1) * REACH_ROW > REACH_BYTES)
        fail("y1cc: too many functions (FUNCS_MAX, REACH_ROW, REACH_BYTES)");
    skip(h, nfuncs);
    for (i = 1; i <= nfuncs; i++) rarrc(h, rbits + i * REACH_ROW, n);
    io_close(h);
    h = ropen(".sym");
    ri(h); ng = ri(h);                              /* the globals: variables 1..ng */
    nstructs = ri(h); nmembers = ri(h); nfuncs = ri(h); nvars = ri(h);
    if (nstructs >= STRUCTS_MAX) fail("y1cc: too many structs (STRUCTS_MAX)");
    if (nmembers >= MEMBERS_MAX) fail("y1cc: too many struct members (MEMBERS_MAX)");
    if (nvars >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
    if (ng >= GLOBS_MAX) fail("y1cc: too many globals (GLOBS_MAX)");
    rarr(h, s_tag + 1, nstructs); rarr(h, s_size + 1, nstructs); rarr(h, s_mfirst + 1, nstructs);
    rarr(h, s_mn + 1, nstructs);
    rarr(h, m_name + 1, nmembers); rarr(h, m_off + 1, nmembers); rarr(h, m_base + 1, nmembers);
    rarrc(h, m_ptr + 1, nmembers); rarr(h, m_cnt + 1, nmembers);
    k = nfuncs;
    rarr(h, f_name + 1, k); rarr(h, f_rbase + 1, k); rarrc(h, f_rptr + 1, k); rarr(h, f_np + 1, k);
    rarr(h, f_body + 1, k); rarrc(h, f_live + 1, k); rarr(h, f_vfirst + 1, k); rarr(h, f_vn + 1, k);
    rarr(h, f_frame + 1, k); rarr(h, f_ferr + 1, k);
    k = nvars;
    rarr(h, v_name + 1, k); rarr(h, v_base + 1, k); rarrc(h, v_ptr + 1, k); rarr(h, v_cnt + 1, k);
    rarrc(h, v_slot + 1, k);
    io_close(h);
    for (i = nfuncs; i > 0; i--) { k = f_name[i] & 63; fn_next[i] = fn_hash[k]; fn_hash[k] = i; }
    for (i = ng; i > 0; i--) { k = v_name[i] & 63; gl_next[i] = gl_hash[k]; gl_hash[k] = i; }
}
