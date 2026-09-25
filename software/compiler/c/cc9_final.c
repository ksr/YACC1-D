/* cc9_final.c - pass 9 of the multi-pass y1cc (2026-09-24): the assembly text. It reads the global data stream
   (W.dat, cc3) and the code stream (W.em, cc8) three times, once per section of the output - code, data,
   uninitialised data - and on every reading numbers the generated labels in stream order (R_ALLOC, R_STRUSE and the
   macros' own labels: y1cc.c's lbl() order), so the three readings agree. It writes y1cc.c's text: the header, each
   instruction through the streaming peephole, the macros expanded by y1cc.c's add_const, branch_rel, frame_save,
   switch_table..., each string literal's data at its first use, the dropped functions, the runtime helpers used, the
   BSS bounds and the boot stub; then the -l summary.

     cc9 W          reads W.opt, W.dat, W.em, W.lab, W.nam, W.lit, W.sym (main), lib/y1ccrt.txt (the runtime);
                    writes the .asm file named in W.opt */
#include "pcommon.c"
#include "pnames.c"

char *mntext[] = {"", "LDR", "STR", "MVIW", "MVRLA", "MVRHA", "MVARL", "MVARH", "MVAT", "MVTA", "LDAI", "LDTI",
                  "LDA", "STA", "LDT", "LDAVR", "STAVR", "INCR", "DECR", "ADDI", "ADDIC", "ADDT", "ADDTC", "ANDI",
                  "ORI", "XORI", "ANDT", "ORT", "XORT", "INVA", "CSHL", "CSHR", "PUSHR", "POPR", "PUSH", "POP",
                  "MOVRR", "JSR", "JSRUR", "RET", "BR", "BRZ", "BRNZ", "BREQ", "BRNEQ", "BRLT", "BRGT", "BRUR",
                  "INP", "OUTA", "HALT", "ORG", "SUBT", "SUBI", "BRDEV", "ADDIW"};
char *lkname[] = {"", "Lf", "Le", "Lt", "Ls", "Lelse", "Lend", "Ltop", "Lnext", "Lsw", "Lc", "Ld", "La", "Lo",
                  "Lz", "Lzg", "Lzd", "s"};
char *rtname[] = {"rt_sub", "rt_mul", "rt_divmod", "rt_shl", "rt_shr", "rt_putc", "rt_getc", "rt_puts",
                  "rt_fsave", "rt_frest"};

/* the labels' owners (W.lab: plabel.c makes the text), the names, the literals (W.lit) */
int v_name[VARS_MAX];
int v_fn[VARS_MAX];
char v_ln[VARS_MAX];
int nvars;
int f_name[FUNCS_MAX];
char f_ln[FUNCS_MAX];
int nfuncs;
int ndrop;
int drop_nm[DROPS_MAX];         /* the dead definitions' names, in source order */
char labbuf[LINE_MAX];
#include "plabel.c"
char *vlab(int v) { ltext(v, labbuf); return labbuf; }
char *flab(int f) { ltext(FOWN + f, labbuf); return labbuf; }
char spool[STRPOOL];
int lit_off[LITS_MAX];
int lit_len[LITS_MAX];
int lit_lab[LITS_MAX];          /* its label number once used, else 0 */
int nlits;

char srcpath[LINE_MAX];
char outpath[LINE_MAX];
int opt_org;
int opt_flags;
int fmain;
int zused;                      /* --xisa: the page (W.zp from cc6): used, a bit per variable; zsec: 1 = the page's */
char zbits[VARS_MAX / 8 + 1];   /* DS lines are being written; ra_z: r_addr's operand was a page variable's label */
int zsec;
int ra_z;

int sec;                        /* the section being written: 0 code, 1 data, 2 bss */
int nl;                         /* the label numbers so far (y1cc.c's nl) */
int fbase;                      /* the first label number of the current function (y1cc.c's lbase) */
char lkind[LKIND_MAX];          /* the kind of each label of the current function */
int map5[LKIND_MAX];            /* symbol -> number: cc6's symbols 1.., cc8's SYM7+1.. */
int map7[LKIND_MAX];
char used[RT_COUNT];
int nlines;
int nraw;
int last_ret;
int fstart;                     /* -l: the functions in compile order, their raw line counts */
int corder[FUNCS_MAX];
int f_stat[FUNCS_MAX];
int ncorder;
int cur_fn;
int inh;

/* output: the line being built, data lines, the peephole's pending lines */
char lb[LINE_MAX];
char db[LINE_MAX];
char tbuf[LINE_MAX];
char pend[PEND_MAX * LINE_MAX];
int npend;
int dbn;
char pmn_1[WORD_MAX];           /* the peephole's two parsed lines (mn_arg): a = the last pending line (valid when */
char parg_1[LINE_MAX];          /* ptop_ok), b = the line arriving (valid for pp_push when pb_ok); a pushed line's */
char pmn_2[WORD_MAX];           /* words become a's by swapping the pointers (2026-09-25: each line was parsed three */
char parg_2[LINE_MAX];          /* times) */
char *pmn_a;
char *parg_a;
char *pmn_b;
char *parg_b;
int ptop_ok;
int pb_st;                      /* the arriving line, for pp_push: 0 not looked at, 1 an instruction (parsed), 2 not one */
int cs_val[CASES_MAX];
int cs_lab[CASES_MAX];

void pass_fail(char *msg) { io_fail(msg); }
int zp(int v) { return (zbits[v >> 3] >> (v & 7)) & 1; }
int is_pyspace(int c);
int skip_space(char *s, int i);
void blab(char *buf, int n);
int lbl(int kind);
int sym_num(int sym);
void sec_line(int s, char *t);
void data_line(char *t);
void bss_line(char *t);
void db_byte(int b);
void db_end(void);
int is_ins(char *l);
int mn_arg(char *l, char *mn, char *arg);
void code_line(char *b);
void peep(char *b);
void pp_push(char *b);
void pp_flush(void);
void L(char *mn);
void Lsp(void);
void Lr(int r);
void Lend(void);
void ins0(char *mn);
void insr(char *mn, int r);
void insn(char *mn, int n);
void insl(char *mn, int lab);
void inss(char *mn, char *s);
void insrn(char *mn, int r, int n);
void insrs(char *mn, int r, char *s);
void kadd(char *buf, int off);
void r_addr(char *buf);
void bnum32(char *buf, int hi, int lo);
void r_code(void);
void r_skip(void);
void add_const(int k);
void add_const_text(char *t);
void shl1(void);
void scale_r3(int esz);
void deref_r3(int sz);
void lo_load(int mode, int k);
void branch_rel(int rel, int label, int lomode, int lok);
void frame_save(int v, int n);
void frame_restore(int v, int n);
void emit_bss_clear(void);
void switch_dispatch(int narrow, int miss, int ncs);
void switch_table(int lo, int hi, int miss, int ncs);
void r_macro(void);
void string_data(int lit);
void stream(char *ext);
void emit_runtime(void);
void rs_line(int h, char *buf);
int rs_eof;
void load_all(void);
void out_s(char *s);
void out_n(int n);

int is_pyspace(int c) { return c == ' ' || (c >= 9 && c <= 13) || (c >= 28 && c <= 31); }  /* str.split() */
int skip_space(char *s, int i) { while (s[i] && is_pyspace(s[i] & 255)) i++; return i; }

/* ---- labels: numbered in stream order ------------------------------------------------------------------------ */
void blab(char *buf, int n) {                       /* a generated label: its prefix and number */
    if (n >= fbase) bcat(buf, lkname[lkind[n - fbase] & 255]); else bcat(buf, "s");
    bnum(buf, n);
}
int lbl(int kind) {
    nl++;
    if (nl >= fbase) {
        if (nl - fbase >= LKIND_MAX) fail("y1cc: too many labels in one function (LKIND_MAX)");
        lkind[nl - fbase] = kind;
    }
    return nl;
}
int sym_num(int sym) {                              /* the number of a cc6 / cc8 label symbol */
    if (sym >= SYM7) { if (sym - SYM7 >= LKIND_MAX) fail("y1cc: too many labels in one function (LKIND_MAX)"); return map7[sym - SYM7]; }
    if (sym >= LKIND_MAX) fail("y1cc: too many labels in one function (LKIND_MAX)");
    return map5[sym];
}

/* ---- output: sections, lines, the streaming peephole (y1cc.c) ------------------------------------------------ */
void sec_line(int s, char *t) {                     /* only the section being written reaches the file */
    if (s != sec) return;
    io_wputs(t);
    io_wput(10);
    nlines++;
}
void data_line(char *t) { sec_line(1, t); }
void bss_line(char *t) { sec_line(2, t); }
void db_byte(int b) {                               /* DB lines of 16 numbers (the assembler upper-cases text) */
    if (dbn == 0) { db[0] = 0; bcat(db, "        DB "); } else bchr(db, ',');
    bnum(db, b & 255);
    dbn++;
    if (dbn == 16) { data_line(db); dbn = 0; }
}
void db_end(void) { if (dbn) { data_line(db); dbn = 0; } }
int is_ins(char *l) { return s_starts(l, "        "); }
int mn_arg(char *l, char *mn, char *arg) {          /* y1cc.py parts(): l.strip().split(None, 1) */
    char *p; char *e; char *m; int c;               /* (pointers, and a space test only below '!': 2026-09-25) */
    p = l;
    while ((c = *p & 255) && c <= 32 && is_pyspace(c)) p++;
    m = mn;                                         /* (the word is only compared with mnemonics: cut it short) */
    while ((c = *p & 255) && (c > 32 || !is_pyspace(c))) { if (m < mn + WORD_MAX - 1) { *m = c; m++; } p++; }
    *m = 0;
    while ((c = *p & 255) && c <= 32 && is_pyspace(c)) p++;
    e = p; while (*e) e++;
    while (e > p && (*(e - 1) & 255) <= 32 && is_pyspace(*(e - 1) & 255)) e--;
    while (p < e) { *arg = *p; arg++; p++; }
    *arg = 0;
    return 1;
}
void code_line(char *b) {                           /* one line of code: counted raw, then through the peephole */
    if (sec) return;
    nraw++;
    last_ret = s_eq(b, "        RET");
    peep(b);
}
int lsk(char *m) {                                  /* the peephole's word loads and stores (above) */
    int k;
    if ((m[2] != 'R' && m[2] != 'Z') || m[3]) return 0;
    k = m[2] == 'Z' ? 3 : 1;
    if (m[0] == 'L' && m[1] == 'D') return k;
    if (m[0] == 'S' && m[1] == 'T') return k + 1;
    return 0;
}
char *pslot(int i) { char *p; p = pend; while (i) { p = p + LINE_MAX; i--; } return p; }   /* pending line i */
void peep(char *b) {
    char *a; int i; int ka; int kb;
    pb_st = 0;
    for (;;) {
        if (npend == 0) break;
        a = pslot(npend - 1);
        if (!ptop_ok) {                             /* (ptop_ok: the last pending line is an instruction, parsed) */
            if (!is_ins(a)) break;
            mn_arg(a, pmn_a, parg_a); ptop_ok = 1;
        }
        if (!pb_st) { pb_st = 2; if (is_ins(b)) { mn_arg(b, pmn_b, parg_b); pb_st = 1; } }
        if (pb_st == 1) {
            ka = lsk(pmn_a); kb = lsk(pmn_b);       /* LDR 1, STR 2, LDZ 3, STZ 4 (--xisa), other 0 */
            if ((kb & 1) && ka == kb + 1 && s_eq(parg_a, parg_b) && s_starts(parg_a, "R3,"))
                return;                             /* store then reload: drop the reload */
            if ((kb & 1) && ka && (ka + 1) / 2 == (kb + 1) / 2 && s_starts(parg_a, "R3,") &&
                s_starts(parg_b, "R4,") && s_eq(parg_b + 3, parg_a + 3)) {
                pb_st = 0;
                pp_push("        MOVRR R3,R4");
                return;
            }
            if (s_eq(pmn_a, "MOVRR") && s_eq(pmn_b, "MOVRR") && s_eq(parg_a, "R3,R4") && s_eq(parg_b, "R4,R3"))
                return;
            break;
        }
        if (s_eq(pmn_a, "BR")) {                    /* a jump to the next line */
            i = skip_space(b, 0);
            if (s_starts(b + i, parg_a) && b[i + s_len(parg_a)] == ':') { npend--; ptop_ok = 0; continue; }
        }
        break;
    }
    pp_push(b);
}
void pp_push(char *b) {
    int i; char *d; char *t; int ins;
    if (pb_st) ins = pb_st == 1;
    else { ins = is_ins(b); if (ins) mn_arg(b, pmn_b, parg_b); }
    pb_st = 0;
    if (!(ins && s_eq(pmn_b, "BR"))) pp_flush(); /* only a BR can still be removed by a later line */
    if (npend >= PEND_MAX) {                        /* never in practice: write the oldest */
        sec_line(0, pend);
        for (i = 1; i < npend; i++) {
            d = pslot(i - 1); t = pslot(i);
            while (*t) { *d = *t; d++; t++; }
            *d = 0;
        }
        npend--;
    }
    d = pslot(npend);
    while (*b) { *d = *b; d++; b++; }
    *d = 0;
    npend++;
    t = pmn_a; pmn_a = pmn_b; pmn_b = t;            /* its words are the new last pending line's */
    t = parg_a; parg_a = parg_b; parg_b = t;
    ptop_ok = ins;
}
void pp_flush(void) {
    int i;
    for (i = 0; i < npend; i++) sec_line(0, pslot(i));
    npend = 0;
}

/* instruction builders: "        MN args" */
/* (2026-09-25: they append at lp, the end of lb, instead of finding it again for every piece; lp catches up with
   what bcat/bchr added meanwhile, so the two can mix after L) */
char *lp;
void Ls(char *s) {
    while (*lp) lp++;
    while (*s) { if (lp >= lb + LINE_MAX - 1) fail("y1cc: line too long"); *lp = *s; lp++; s++; }
    *lp = 0;
}
void L(char *mn) { lb[0] = 0; lp = lb; Ls("        "); Ls(mn); }
void Lsp(void) { Ls(" "); }
void Lr(int r) { char t[3]; t[0] = 'R'; t[1] = '0' + r; t[2] = 0; Ls(t); }
void Ln(int n) { char d[8]; pnum(d, n); Ls(d); }
void Lend(void) { code_line(lb); }
void ins0(char *mn) { L(mn); Lend(); }
void insr(char *mn, int r) { L(mn); Lsp(); Lr(r); Lend(); }
void insn(char *mn, int n) { L(mn); Lsp(); Ln(n); Lend(); }
void insl(char *mn, int lab) { L(mn); Lsp(); blab(lb, lab); Lend(); }
void inss(char *mn, char *s) { L(mn); Lsp(); Ls(s); Lend(); }
void insrn(char *mn, int r, int n) { L(mn); Lsp(); Lr(r); Ls(","); Ln(n); Lend(); }
void insrs(char *mn, int r, char *s) { L(mn); Lsp(); Lr(r); Ls(","); Ls(s); Lend(); }
void label_def(int lab) { lb[0] = 0; blab(lb, lab); bchr(lb, ':'); code_line(lb); }
void kadd(char *buf, int off) { if (off) { bchr(buf, '+'); bnum(buf, off); } }

/* ---- R_CODE: an instruction record rendered as y1cc.c's text ------------------------------------------------- */
void r_addr(char *buf) {                            /* an address operand: label, then "+term"s */
    int k; int id; int n;
    k = rb(inh); id = ri(inh); n = rb(inh);
    ra_z = k == A_VAR && !n && zp(id);
    if (k == A_VAR) bcat(buf, vlab(id));
    else if (k == A_STR) { bchr(buf, 's'); bnum(buf, lit_lab[id]); }
    else if (k == A_FUNC) bcat(buf, flab(id));
    else bcat(buf, rtname[id]);
    while (n) { k = ri(inh); id = ri(inh); bchr(buf, '+'); bnum32(buf, k, id); n--; }
}
void bnum32(char *buf, int hi, int lo) {            /* hi:lo in decimal (long division by 10, a byte at a time) */
    char d[12]; int b[4]; int k; int i; int r; int nz;
    if (!hi) { bnum(buf, lo); return; }
    b[0] = hi >> 8; b[1] = hi & 255; b[2] = lo >> 8; b[3] = lo & 255;
    k = 0;
    for (;;) {
        r = 0; nz = 0;
        for (i = 0; i < 4; i++) { r = r * 256 + b[i]; b[i] = r / 10; r = r % 10; if (b[i]) nz = 1; }
        d[k] = '0' + r; k++;
        if (!nz) break;
    }
    while (k > 0) { k--; bchr(buf, d[k]); }
}
char fskip[] = {0, 1, 2, 2, 3, 3, 3, 2, 4, 1};       /* r_skip: an operand's bytes by format F_0..F_P (an address:
                                                       its kind and id, then the count of its terms) */
void r_skip(void) {                                 /* an R_CODE record read past (the data and BSS readings: code
                                                       lines are dropped there, and making their text took most of
                                                       cc9's time, 2026-09-25) */
    int f;
    rb(inh); f = rb(inh);
    io_skip(inh, fskip[f]);
    if (f == F_A || f == F_RA) io_skip(inh, rb(inh) << 2);
}
void r_code(void) {
    int mn; int f; int n;
    mn = rb(inh); f = rb(inh);
    L(mntext[mn]);
    if (f != F_0) Lsp();
    if (f == F_R) Lr(rb(inh));
    else if (f == F_N) bnum(lb, ri(inh));
    else if (f == F_L) blab(lb, sym_num(ri(inh)));
    else if (f == F_A) r_addr(lb);
    else if (f == F_RN) { Lr(rb(inh)); bchr(lb, ','); bnum(lb, ri(inh)); }
    else if (f == F_RL) { Lr(rb(inh)); bchr(lb, ','); blab(lb, sym_num(ri(inh))); }
    else if (f == F_RR) { Lr(rb(inh)); bchr(lb, ','); Lr(rb(inh)); }
    else if (f == F_RA) {
        Lr(rb(inh)); bchr(lb, ','); r_addr(lb);
        if (ra_z && mn <= MN_STR) {                 /* --xisa: a page variable: "        LDZ R3,(label).0" */
            lb[10] = 'Z'; tbuf[0] = 0; bcat(tbuf, lb + 15); lb[15] = 0; bchr(lb, '('); bcat(lb, tbuf); bcat(lb, ").0");
        }
    }
    else if (f == F_P) { n = rb(inh); bchr(lb, 'P'); bchr(lb, n < 10 ? '0' + n : 'A' + n - 10); }
    Lend();
}

/* ---- the macros: y1cc.c's functions of the same name ------------------------------------------------------------ */
void add_const(int k) {                             /* R3 += k (a number; masked) */
    int i;
    k = k & 65535;
    if (k == 0) return;
    if (k <= 3) { for (i = 0; i < k; i++) insr("INCR", 3); return; }
    if (k >= 65533) { for (i = 65535 - k + 1; i > 0; i--) insr("DECR", 3); return; }
    if (opt_flags & OPT_XISA) { insrn("ADDIW", 3, k); return; }
    if ((k & 255) == 0) { insr("MVRHA", 3); insn("ADDI", k >> 8); insr("MVARH", 3); return; }
    insr("MVRLA", 3); insn("ADDI", k & 255); insr("MVARL", 3);
    insr("MVRHA", 3); insn("ADDIC", (k >> 8) & 255); insr("MVARH", 3);
}
void add_const_text(char *t) {                      /* R3 += a label expression */
    if (opt_flags & OPT_XISA) { insrs("ADDIW", 3, t); return; }
    insr("MVRLA", 3); L("ADDI"); Lsp(); bchr(lb, '('); bcat(lb, t); bcat(lb, ").0"); Lend(); insr("MVARL", 3);
    insr("MVRHA", 3); L("ADDIC"); Lsp(); bchr(lb, '('); bcat(lb, t); bcat(lb, ").1"); Lend(); insr("MVARH", 3);
}
void shl1(void) {                                   /* R3 <<= 1 (R3 += R3) */
    if (opt_flags & OPT_XISA) { insr("SHL16", 3); return; }
    insr("MVRLA", 3); ins0("MVAT"); ins0("ADDT"); insr("MVARL", 3);
    insr("MVRHA", 3); ins0("MVAT"); ins0("ADDTC"); insr("MVARH", 3);
}
void scale_r3(int esz) {                            /* R3 *= esz (element size) */
    if (esz == 1) return;
    if (esz == 2) { shl1(); return; }
    if (esz == 4) { shl1(); shl1(); return; }
    insrn("MVIW", 4, esz); used[RT_MUL] = 1; inss("JSR", "rt_mul");
}
void deref_r3(int sz) {                             /* R3 = *(R3), a word or a byte (cc8 checked the size) */
    if (sz == 2) {
        insr("LDAVR", 3); ins0("MVAT"); insr("INCR", 3); insr("LDAVR", 3);
        insr("MVARL", 3); ins0("MVTA"); insr("MVARH", 3);
    } else {
        insr("LDAVR", 3); insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3);
    }
}
void lo_load(int mode, int k) {                     /* the low bytes of a two-level compare: ACC = L.lo, TMP = R.lo */
    if (mode == 2) { insr("MVRLA", 4); ins0("MVAT"); insr("MVRLA", 3); }
    else { insr("MVRLA", 3); insn("LDTI", k & 255); }
}
/* After ACC = L.hi (or L for bytes) and TMP = R.hi: jump to label when L rel R. lomode 0: byte operands (one
   compare); 1: R is the constant lok; 2: R is in R4. */
void branch_rel(int rel, int label, int lomode, int lok) {
    int skip;
    if (lomode == 0) {
        if (rel == O_EQ) insl("BREQ", label);
        else if (rel == O_NE) insl("BRNEQ", label);
        else if (rel == O_LT) insl("BRLT", label);
        else if (rel == O_GT) insl("BRGT", label);
        else {
            skip = lbl(LK_S);
            insl(rel == O_LE ? "BRGT" : "BRLT", skip); insl("BR", label); label_def(skip);
        }
        return;
    }
    skip = lbl(LK_S);
    if (rel == O_EQ) { insl("BRNEQ", skip); lo_load(lomode, lok); insl("BREQ", label); }
    else if (rel == O_NE) { insl("BRNEQ", label); lo_load(lomode, lok); insl("BRNEQ", label); }
    else if (rel == O_LT || rel == O_LE) {
        insl("BRLT", label); insl("BRNEQ", skip); lo_load(lomode, lok);
        if (rel == O_LT) insl("BRLT", label);
        else { insl("BRGT", skip); insl("BR", label); }
    } else {
        insl("BRGT", label); insl("BRNEQ", skip); lo_load(lomode, lok);
        if (rel == O_GT) insl("BRGT", label);
        else { insl("BRLT", skip); insl("BR", label); }
    }
    label_def(skip);
}
void zldst(char *mn, int v) {                       /* frame_save/restore: LDR/STR R4,tbuf, LDZ/STZ in the page */
    if (!zp(v)) { insrs(mn, 4, tbuf); return; }
    L(mn[0] == 'L' ? "LDZ" : "STZ"); bcat(lb, " R4,("); bcat(lb, tbuf); bcat(lb, ").0"); Lend();
}
void frame_save(int v, int n) {                     /* push a frame of n bytes at v's label; R4 inline, or rt_fsave */
    int off;
    if (n <= FRAME_INLINE) {
        for (off = 0; off + 1 < n; off = off + 2) {
            tbuf[0] = 0; bcat(tbuf, vlab(v)); kadd(tbuf, off); zldst("LDR", v); insr("PUSHR", 4);
        }
        if (n & 1) { tbuf[0] = 0; bcat(tbuf, vlab(v)); kadd(tbuf, n - 1); inss("LDA", tbuf); ins0("PUSH"); }
        return;
    }
    insrs("MVIW", 5, vlab(v)); insrn("MVIW", 6, n); used[RT_FSAVE] = 1; inss("JSR", "rt_fsave");
}
void frame_restore(int v, int n) {                  /* pop it back; R3 (the result) is not touched */
    int off;
    if (n <= FRAME_INLINE) {
        if (n & 1) { ins0("POP"); tbuf[0] = 0; bcat(tbuf, vlab(v)); kadd(tbuf, n - 1); inss("STA", tbuf); }
        off = n & 65534;
        while (off > 0) {
            off = off - 2;
            insr("POPR", 4); tbuf[0] = 0; bcat(tbuf, vlab(v)); kadd(tbuf, off); zldst("STR", v);
        }
        return;
    }
    tbuf[0] = 0; bcat(tbuf, vlab(v)); kadd(tbuf, n - 1);
    insrs("MVIW", 5, tbuf); insrn("MVIW", 6, n); used[RT_FREST] = 1; inss("JSR", "rt_frest");
}
void emit_bss_clear(void) {                         /* main clears every DS slot (bss_start..bss_end): 20 bytes */
    int loop; int go; int done;
    loop = lbl(LK_Z); go = lbl(LK_ZG); done = lbl(LK_ZD);
    insrs("MVIW", 3, "bss_start");
    label_def(loop); insr("MVRHA", 3); inss("LDTI", "(bss_end).1"); insl("BRNEQ", go);
    insr("MVRLA", 3); inss("LDTI", "(bss_end).0"); insl("BREQ", done);
    label_def(go); insn("LDAI", 0); insr("STAVR", 3); insr("INCR", 3); insl("BR", loop);
    label_def(done);
}
void switch_dispatch(int narrow, int miss, int ncs) {    /* y1cc.c gen_switch after gen_expr(e) */
    int lo; int hi; int i; int byte_cases; int chain; int table; int skip; int v;
    if (ncs) {
        lo = cs_val[0]; hi = cs_val[0];
        for (i = 1; i < ncs; i++) { if (cs_val[i] < lo) lo = cs_val[i]; if (cs_val[i] > hi) hi = cs_val[i]; }
        byte_cases = hi <= 255;
        if (byte_cases) chain = 3 + 5 * ncs + (narrow ? 0 : 4);
        else chain = 13 * ncs + 3;
        if (hi - lo > 30000) table = 65535; else table = 49 + 2 * (hi - lo + 1);
        if ((opt_flags & OPT_BRUR) && table < chain) switch_table(lo, hi, miss, ncs);
        else if (byte_cases) {
            if (!narrow) { insr("MVRHA", 3); insl("BRNZ", miss); }
            insr("MVRLA", 3);
            for (i = 0; i < ncs; i++) { insn("LDTI", cs_val[i]); insl("BREQ", cs_lab[i]); }
            insl("BR", miss);
        } else {
            for (i = 0; i < ncs; i++) {
                skip = lbl(LK_S); v = cs_val[i];
                insr("MVRHA", 3); insn("LDTI", v >> 8); insl("BRNEQ", skip);
                insr("MVRLA", 3); insn("LDTI", v & 255); insl("BREQ", cs_lab[i]);
                label_def(skip);
            }
            insl("BR", miss);
        }
    } else insl("BR", miss);
}
void switch_table(int lo, int hi, int miss, int ncs) {   /* R3 - lo, range check, BRUR through a table of addresses */
    int tab; int n; int v; int i; int k; int lab;
    tab = lbl(LK_T); n = hi - lo + 1;
    add_const(65535 - lo + 1);
    insr("MVRHA", 3); insn("LDTI", n >> 8);
    branch_rel(O_GE, miss, 1, n);
    shl1();
    tbuf[0] = 0; blab(tbuf, tab); add_const_text(tbuf);
    deref_r3(2);
    insr("BRUR", 3);
    db[0] = 0; blab(db, tab); bchr(db, ':'); data_line(db);
    for (k = 0; k < n; k++) {                       /* (y1cc.c counts v from lo to hi: hi = 65535 would not end here) */
        v = lo + k;
        lab = miss;
        for (i = 0; i < ncs; i++) if (cs_val[i] == v) lab = cs_lab[i];
        db[0] = 0; bcat(db, "        DW "); blab(db, lab); data_line(db);
    }
}
void r_macro(void) {
    int m; int a; int b; int c; int d; int i;
    m = rb(inh);
    if (m == M_ADDK) add_const(ri(inh));
    else if (m == M_ADDA) { tbuf[0] = 0; r_addr(tbuf); add_const_text(tbuf); }
    else if (m == M_SHL1) shl1();
    else if (m == M_SCALE) scale_r3(ri(inh));
    else if (m == M_DEREF) deref_r3(rb(inh));
    else if (m == M_BREL) { a = rb(inh); b = sym_num(ri(inh)); c = rb(inh); d = ri(inh); branch_rel(a, b, c, d); }
    else if (m == M_FSAVE) { a = ri(inh); frame_save(a, ri(inh)); }
    else if (m == M_FREST) { a = ri(inh); frame_restore(a, ri(inh)); }
    else if (m == M_BSSCLR) emit_bss_clear();
    else if (m == M_ZP) { if (zused) insrs("MVIW", 6, "zpage"); }
    else {                                          /* M_SWITCH */
        a = rb(inh); b = sym_num(ri(inh)); c = ri(inh);
        if (c > CASES_MAX) fail("y1cc: too many cases in a switch (CASES_MAX)");
        for (i = 0; i < c; i++) { cs_val[i] = ri(inh); cs_lab[i] = sym_num(ri(inh)); }
        switch_dispatch(a, b, c);
    }
}

/* ---- the streams ------------------------------------------------------------------------------------------------ */
void string_data(int lit) {                         /* y1cc.py string(): the literal's label and bytes, once */
    int i;
    if (lit_lab[lit]) return;
    lit_lab[lit] = lbl(LK_STR);
    db[0] = 0; bchr(db, 's'); bnum(db, lit_lab[lit]); bchr(db, ':'); data_line(db);
    for (i = 0; i < lit_len[lit]; i++) db_byte(spool[lit_off[lit] + i] & 255);
    db_byte(0);
    db_end();
}
void stream(char *ext) {                            /* one reading of W.dat or W.em for section sec */
    int c; int a; int b; int i; int n;
    inh = ropen(ext);
    for (;;) {
        c = rb(inh);
        if (c == 256) break;
        if (c == R_CODE) { if (sec) r_skip(); else r_code(); }     /* code text only for the code section */
        else if (c == R_LDEF) { a = ri(inh); if (!sec) label_def(sym_num(a)); }
        else if (c == R_ALLOC) {
            a = ri(inh); b = rb(inh);
            n = lbl(b);
            if (a >= SYM7) { if (a - SYM7 >= LKIND_MAX) fail("y1cc: too many labels in one function (LKIND_MAX)"); map7[a - SYM7] = n; }
            else { if (a >= LKIND_MAX) fail("y1cc: too many labels in one function (LKIND_MAX)"); map5[a] = n; }
        } else if (c == R_FLABEL) { a = ri(inh); if (!sec) { lb[0] = 0; bcat(lb, flab(a)); bchr(lb, ':'); code_line(lb); } }
        else if (c == R_TEXT) { a = rb(inh); rs(inh, lb, LINE_MAX); sec_line(a, lb); }
        else if (c == R_DSVAR) {
            a = ri(inh); b = ri(inh);
            if (zp(a) == zsec) { db[0] = 0; bcat(db, vlab(a)); bcat(db, ": DS "); bnum(db, b); bss_line(db); }
        } else if (c == R_DATALAB) { db[0] = 0; bcat(db, vlab(ri(inh))); bchr(db, ':'); data_line(db); }
        else if (c == R_DWVAR) { db[0] = 0; bcat(db, "        DW "); bcat(db, vlab(ri(inh))); data_line(db); }
        else if (c == R_DWSTR) { db[0] = 0; bcat(db, "        DW s"); bnum(db, lit_lab[ri(inh)]); data_line(db); }
        else if (c == R_STRUSE) string_data(ri(inh));
        else if (c == R_DBLIT) {
            a = ri(inh); n = ri(inh);
            for (i = 0; i < n; i++) db_byte(i < lit_len[a] ? spool[lit_off[a] + i] & 255 : 0);
            db_end();
        } else if (c == R_NEED) used[rb(inh)] = 1;
        else if (c == R_MACRO) r_macro();
        else if (c == R_RETIF) { if (!sec && !last_ret) ins0("RET"); }
        else if (c == R_FUNC) {
            cur_fn = ri(inh); ri(inh); ri(inh); rb(inh);
            fbase = nl + 1; fstart = nraw;
        } else if (c == R_FEND) {
            if (sec == 0) {
                if (ncorder >= FUNCS_MAX) fail("y1cc: too many functions (FUNCS_MAX)");
                corder[ncorder] = cur_fn; f_stat[ncorder] = nraw - fstart; ncorder++;
            }
        } else fail("y1cc: internal: a bad record in the stream");
    }
    io_close(inh);
}

/* ---- the runtime: y1cc.c emit_runtime's text, from lib/y1ccrt.txt (the helpers used, in its order) ----------- */
void emit_runtime(void) {
    int h; int i; int k; int on; int c;
    io_lib("y1ccrt.txt", tbuf, LINE_MAX);
    h = io_open(tbuf);
    if (!h) { e_start("y1cc: cannot read "); e_s(tbuf); e_go(); }
    on = 0;
    for (;;) {
        rs_line(h, lb);
        if (!lb[0] && rs_eof) break;
        if (lb[0] == '@') {                         /* @rt_name[+o|-o|+x|-x]: a section this program wants? */
            c = 0;
            for (i = 1; lb[i]; i++) if (lb[i] == '+' || lb[i] == '-') c = i;
            k = 0;
            if (c) { k = (opt_flags & (lb[c + 1] == 'o' ? OPT_OS : OPT_XISA)) != 0; if (lb[c] == '-') k = !k; lb[c] = 0; }
            on = 0;
            for (i = 0; i < RT_COUNT; i++) if (s_eq(lb + 1, rtname[i])) on = used[i];
            if (c && !k) on = 0;
            if (on) { db[0] = 0; bcat(db, "; runtime "); bcat(db, lb + 1); sec_line(0, db); }
            continue;
        }
        if (on && lb[0] == '%') { if (zused) sec_line(0, lb + 1); }   /* a line for programs with the page */
        else if (on) sec_line(0, lb);
    }
    io_close(h);
}
void rs_line(int h, char *buf) {                    /* a line without its newline; rs_eof at the end of the file */
    int n; int c;
    n = 0; rs_eof = 0;
    for (;;) {
        c = io_getc(h);
        if (c == 256) { rs_eof = 1; break; }
        if (c == 10) break;
        if (n < LINE_MAX - 1) { buf[n] = c; n++; }
    }
    buf[n] = 0;
}

/* ---- the driver ------------------------------------------------------------------------------------------------- */
void load_all(void) {
    int h; int i; int k; int n;
    h = ropen(".opt");
    rs(h, srcpath, LINE_MAX); rs(h, outpath, LINE_MAX); opt_org = ri(h); opt_flags = rb(h);
    io_close(h);
    h = ropen(".sym");
    fmain = ri(h);
    io_close(h);
    names_load();
    h = ropen(".lab");                              /* the labels' owners (cc5_layout.c) */
    nvars = ri(h); nfuncs = ri(h); ndrop = ri(h);
    if (nvars >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
    if (nfuncs >= FUNCS_MAX) fail("y1cc: too many functions (FUNCS_MAX)");
    if (ndrop >= DROPS_MAX) fail("y1cc: too many dropped functions (DROPS_MAX)");
    rarr(h, v_name + 1, nvars); rarr(h, v_fn + 1, nvars); rarrc(h, v_ln + 1, nvars);
    rarr(h, f_name + 1, nfuncs); rarrc(h, f_ln + 1, nfuncs); io_skip(h, nfuncs);
    rarr(h, drop_nm, ndrop);
    io_close(h);
    if (opt_flags & OPT_XISA) { h = ropen(".zp"); zused = rb(h); rarrc(h, zbits, nvars / 8 + 1); io_close(h); }
    h = ropen(".lit");
    nlits = ri(h);
    if (nlits >= LITS_MAX) fail("y1cc: too many string literals (LITS_MAX)");
    k = 0;
    for (i = 1; i <= nlits; i++) {
        n = ri(h); lit_off[i] = k; lit_len[i] = n;
        if (k + n >= STRPOOL) fail("y1cc: string pool full (STRPOOL)");
        while (n) { spool[k] = rb(h); k++; n--; }
    }
    io_close(h);
}
void out_s(char *s) { while (*s) { io_out(*s & 255); s++; } }
void out_n(int n) { tbuf[0] = 0; bnum(tbuf, n); out_s(tbuf); }
void y1cc_main(void) {
    int i; int r; int p;
    p_args();
    pmn_a = pmn_1; parg_a = parg_1; pmn_b = pmn_2; parg_b = parg_2;
    load_all();
    if (!io_wopen(outpath)) { e_start("y1cc: cannot write "); e_s(outpath); e_go(); }
    for (sec = 0; sec < 3; sec++) {
        nl = 0; fbase = 65535; dbn = 0; npend = 0;
        for (i = 1; i <= nlits; i++) lit_lab[i] = 0;
        if (sec == 0) {                             /* the header */
            io_date(tbuf);
            lb[0] = 0; bcat(lb, "; y1cc: ");
            r = 0; for (p = 0; srcpath[p]; p++) if (srcpath[p] == '/') r = p + 1;
            bcat(lb, srcpath + r); bcat(lb, "  ("); bcat(lb, tbuf); bchr(lb, ')'); code_line(lb);
            code_line("; R3 = expression accumulator, R4 = operand, R5-R7 runtime scratch, R2 never used (hardware IR)");
            insn("ORG", opt_org);
            if (opt_flags & OPT_VECTOR) {
                code_line("        DW start                ; vector for the 2021 monitor's G command (BRVR = PC <- [org])");
                lb[0] = 0; bcat(lb, "start:  JSR "); bcat(lb, flab(fmain)); code_line(lb);
                code_line("        BR 61440                 ; back to the monitor (restart)");   /* MONITOR_RESTART */
            }
        }
        if (sec == 2 && zused) {                    /* --xisa: the page first (zpad, before bss_start, aligned it) */
            bss_line("zpage:");
            zsec = 1; stream(".dat"); stream(".em"); zsec = 0;
        }
        stream(".dat");
        stream(".em");
        if (sec == 0) {
            fbase = 65535;
            for (i = 0; i < ndrop; i++) {
                lb[0] = 0; bcat(lb, "; dropped (never called): "); bcat(lb, nm_text(drop_nm[i])); code_line(lb);
            }
            pp_flush();
            emit_runtime();
        } else if (sec == 1) {
            if (zused) data_line("zpad: DS (256-(zpad).0)&255");
            data_line("bss_start:");
        }
        else {
            bss_line("bss_end: DS 1");              /* a byte so the label is a real address even for an empty BSS */
            if (opt_flags & OPT_BOOT) {
                bss_line("; boot stub for `emulator -x -f prog.img` / `y1ucemu -x -m -f prog.img`: release FORCE-ROM, stack, main, HALT");
                bss_line("        ORG 61440"); bss_line("        BR 61443");
                bss_line("        MVIW R1,3839");               /* STACK_TOP */
                db[0] = 0; bcat(db, "        JSR "); bcat(db, flab(fmain)); bss_line(db);
                bss_line("        HALT");
                bss_line("        END 61440");
            } else {
                db[0] = 0; bcat(db, "        END "); bnum(db, opt_org); bss_line(db);
            }
        }
    }
    io_wclose();
    if (opt_flags & OPT_LIST) {
        out_s("y1cc: "); out_s(srcpath); out_s(" -> "); out_s(outpath); out_s(": "); out_n(nlines);
        out_s(" lines; functions: ");
        for (i = 0; i < ncorder; i++) {
            if (i) out_s(", ");
            out_s(nm_text(f_name[corder[i]])); out_s(" "); out_n(f_stat[i]);
        }
        out_s("\n");
    }
}
