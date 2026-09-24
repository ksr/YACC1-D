/* y1cc.c - the C twin of y1cc.py (2026-09-24): a C compiler for the YACC1, written in the C subset y1cc accepts.

   It produces the same assembly as software/compiler/y1cc.py, byte for byte (tests/compiler/twin.py compiles the
   whole corpus with both); y1cc.py stays the reference and the bootstrap. The structure follows y1cc.py function
   by function (the names are the same where C allows), so a change to one is easy to carry to the other.

   It is written for three compilers at once:
     cc -std=c89 -Wall -Wextra -pedantic   on the Mac (host.c + host_io.c: the Makefile), no warnings
     y1cc.py                               the self-compile proof (target.c + target_io.c: Y1/OS file syscalls)
     y1cc.c itself                         the road to a native compiler (software/compiler/README.md)
   so it keeps to the intersection: int is 16-bit UNSIGNED on the YACC1 and 32-bit signed on the Mac, char is
   unsigned there and signed here. Every value stays within 0..65535 (no negative numbers, no -1 sentinels: "none"
   is 0, arithmetic that can wrap is masked with & 65535, products go through mul16), bytes read back from char
   arrays are masked with & 255, no long, no casts, no function pointers, no goto, no struct by value, no do/while,
   no #if, fixed tables sized by #define (limits_host.h / limits_y1.h), and every local variable is declared at the
   top of its function (y1cc does not see declarations inside a switch body). Recursion is the recursion y1cc has
   since 2026-09-24: no address of a local is passed into a recursive call (every buffer that crosses a call is a
   global). All I/O goes through io.h.

   Memory model: the whole program's AST is kept (y1cc.py needs the call graph before generating any code); the
   lexer streams its input (a 4-byte lookahead per open file) and the peephole optimiser streams its output (it
   keeps only the pending BR lines), so there is no whole-file buffer. The limits are in the limits_*.h files. */
#include "io.h"

/* ---- token kinds ---------------------------------------------------------------------------------------- */
#define T_EOF 0
#define T_NUM 1
#define T_ID 2
#define T_KW 3
#define T_STR 4
#define T_OP 5

/* ---- predefined names: interned first, in this order (keywords, then main and the builtins) ------------- */
#define K_INT 1
#define K_CHAR 2
#define K_VOID 3
#define K_STRUCT 4
#define K_UNION 5
#define K_UNSIGNED 6
#define K_CONST 7
#define K_STATIC 8
#define K_IF 9
#define K_ELSE 10
#define K_WHILE 11
#define K_FOR 12
#define K_RETURN 13
#define K_BREAK 14
#define K_CONTINUE 15
#define K_SIZEOF 16
#define K_SWITCH 17
#define K_CASE 18
#define K_DEFAULT 19
#define KW_LAST 19
#define NM_MAIN 20
#define B_GETCHAR 21
#define B_PEEK 22
#define B_PEEKW 23
#define B_INP 24
#define B_BIOS 25
#define B_PUTCHAR 26
#define B_PUTS 27
#define B_POKE 28
#define B_POKEW 29
#define B_OUTP 30
#define B_HALT 31
#define B_CALL 32
#define B_ARGSTR 33
#define B_SYS 34
#define B_FUNCADDR 35
#define NM_PREDEF 35

/* ---- operators, in y1cc.py's PUNCT order (the lexer tries them in this order) ----------------------------- */
#define O_SHLEQ 1
#define O_SHREQ 2
#define O_EQ 3
#define O_NE 4
#define O_LE 5
#define O_GE 6
#define O_SHL 7
#define O_SHR 8
#define O_ANDAND 9
#define O_OROR 10
#define O_ARROW 11
#define O_INC 12
#define O_DEC 13
#define O_ADDEQ 14
#define O_SUBEQ 15
#define O_MULEQ 16
#define O_DIVEQ 17
#define O_MODEQ 18
#define O_ANDEQ 19
#define O_OREQ 20
#define O_XOREQ 21
#define O_LBRACE 22
#define O_RBRACE 23
#define O_LPAREN 24
#define O_RPAREN 25
#define O_LBRACK 26
#define O_RBRACK 27
#define O_SEMI 28
#define O_COMMA 29
#define O_ASSIGN 30
#define O_DOT 31
#define O_QUEST 32
#define O_COLON 33
#define O_PLUS 34
#define O_MINUS 35
#define O_STAR 36
#define O_SLASH 37
#define O_PERCENT 38
#define O_LT 39
#define O_GT 40
#define O_NOT 41
#define O_AMP 42
#define O_BAR 43
#define O_CARET 44
#define O_TILDE 45
#define O_LAST 45

/* ---- AST node kinds (y1cc.py's tuples) -------------------------------------------------------------------- */
#define N_NUM 1
#define N_STR 2
#define N_ID 3
#define N_UNARY 4
#define N_PREINC 5
#define N_POSTINC 6
#define N_SIZEOFT 7
#define N_SIZEOFE 8
#define N_CALL 9
#define N_INDEX 10
#define N_MEMBER 11
#define N_ARROW 12
#define N_ASSIGN 13
#define N_COND 14
#define N_LOGOR 15
#define N_LOGAND 16
#define N_BIN 17
#define N_BLOCK 20
#define N_DECL 21
#define N_IF 22
#define N_WHILE 23
#define N_FOR 24
#define N_RETURN 25
#define N_SWITCH 26
#define N_CASE 27
#define N_DEFAULT 28
#define N_BREAK 29
#define N_CONTINUE 30
#define N_EMPTY 31
#define N_EXPR 32
#define N_LABEL 33
#define N_STRUCTDEF 40
#define N_MEMBERDEF 41
#define N_PROTO 42
#define N_FUNC 43
#define N_PARAM 44
#define N_GVAR 45
#define N_INITLIST 50
#define N_INITSTR 51
#define N_INITADDR 52
#define N_INITNUM 53

/* ---- label kinds: y1cc.py's lbl() prefixes ------------------------------------------------------------------ */
#define LK_F 1
#define LK_E 2
#define LK_T 3
#define LK_S 4
#define LK_ELSE 5
#define LK_END 6
#define LK_TOP 7
#define LK_NEXT 8
#define LK_SW 9
#define LK_C 10
#define LK_D 11
#define LK_A 12
#define LK_O 13
#define LK_Z 14
#define LK_ZG 15
#define LK_ZD 16
#define LK_STR 17
#define LBASE_NONE 65535

/* ---- runtime helpers (emitted in this order when used) ---------------------------------------------------- */
#define RT_SUB 0
#define RT_MUL 1
#define RT_DIVMOD 2
#define RT_SHL 3
#define RT_SHR 4
#define RT_PUTC 5
#define RT_GETC 6
#define RT_PUTS 7
#define RT_FSAVE 8
#define RT_FREST 9
#define RT_COUNT 10

/* ---- the machine (y1cc.py's constants) ---------------------------------------------------------------------- */
#define ORG_DEFAULT 12288
#define STACK_TOP 3839
#define MONITOR_RESTART 61440
#define ARGBUF 3904
#define SYSARG 3846
#define SYSRES 3852
#define SYSTAB 3860
#define SYS_CONIN 17
#define SYS_CONOUT 19
#define SYSMAX 21
#define BIOS_CHAROUT 65476
#define BIOS_UARTIN 65512
#define LABEL_MAX 29
#define FRAME_INLINE 8

/* line buffers (the table limits, and PEND_MAX PARK_MAX CASES_MAX EBUF_MAX, are in limits_*.h) */
#define LINE_MAX 256
#define DIR_MAX 512
#define ID_MAX 128

/* ---- tables ------------------------------------------------------------------------------------------------ */
char *optext[] = {"", "<<=", ">>=", "==", "!=", "<=", ">=", "<<", ">>", "&&", "||", "->", "++", "--",
                  "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "{", "}", "(", ")", "[", "]", ";", ",", "=",
                  ".", "?", ":", "+", "-", "*", "/", "%", "<", ">", "!", "&", "|", "^", "~"};
char *predef[] = {"", "int", "char", "void", "struct", "union", "unsigned", "const", "static", "if", "else",
                  "while", "for", "return", "break", "continue", "sizeof", "switch", "case", "default", "main",
                  "getchar", "peek", "peekw", "inp", "bios", "putchar", "puts", "poke", "pokew", "outp", "halt",
                  "call", "argstr", "sys", "funcaddr"};
char *lkname[] = {"", "Lf", "Le", "Lt", "Ls", "Lelse", "Lend", "Ltop", "Lnext", "Lsw", "Lc", "Ld", "La", "Lo",
                  "Lz", "Lzg", "Lzd", "s"};
char *rtname[] = {"rt_sub", "rt_mul", "rt_divmod", "rt_shl", "rt_shr", "rt_putc", "rt_getc", "rt_puts",
                  "rt_fsave", "rt_frest"};
char *kindname[] = {"", "num", "str", "id", "unary", "preinc", "postinc", "sizeoft", "sizeofe", "call", "index",
                    "member", "arrow", "assign", "cond", "logor", "logand", "bin"};

/* names (identifiers, keywords, struct tags, #define names), interned: id 1.. */
char npool[NAMEPOOL];
int npn;
int nm_off[NAMES_MAX];
int nm_next[NAMES_MAX];
int nm_hash[HASH_SIZE];
int nnames;
char nm_mac[NAMES_MAX];         /* 1: a #define'd name */
int nm_macv[NAMES_MAX];         /* its value (masked to 16 bits) */
int nm_glob[NAMES_MAX];         /* global variable (var index) */
int nm_fn[NAMES_MAX];           /* function (fn index) */
int nm_st[NAMES_MAX];           /* struct/union (struct index) */

/* string literals, interned: id 1.. (y1cc.py keys its strings by their bytes) */
char spool[STRPOOL];
int spn;
int lit_off[LITS_MAX];
int lit_len[LITS_MAX];
int lit_next[LITS_MAX];
int lit_lab[LITS_MAX];          /* its label number once string() has emitted it, else 0 */
int lit_hash[HASH_SIZE];
int nlits;

/* types (base name, pointer depth, array count), interned: id 1.. */
int ty_b[TYPES_MAX];
int ty_p[TYPES_MAX];
int ty_c[TYPES_MAX];
int ntypes;

/* the AST: node 0 is "none"; nx links the elements of a list */
int nk[NODES_MAX];
int na[NODES_MAX];
int nb[NODES_MAX];
int nc[NODES_MAX];
int nd[NODES_MAX];
int nx[NODES_MAX];
int nn;
int prog_first;
int prog_last;

/* the lexer: a stack of open files, each with a small lookahead */
int fdep;
int f_h[INCL_DEPTH];
int f_line[INCL_DEPTH];
int f_la[INCL_DEPTH * 4];
int f_nla[INCL_DEPTH];
int f_path[INCL_DEPTH];
char ppool[PATHPOOL];
int ppn;
int incl_off[INCLS_MAX];
int nincl;
char dirbuf[DIR_MAX];
char idbuf[ID_MAX];
char pbuf[LINE_MAX];
char p2buf[LINE_MAX];
char sbuf[STRLIT_MAX];

/* the token ring: the parser looks at most 2 tokens ahead and 1 back */
int tk_kind[8];
int tk_val[8];
int tk_line[8];
int tk_have;
int ti;

/* variables: 1.. */
int v_lab[VARS_MAX];            /* offset of the label text in lpool */
int v_base[VARS_MAX];
int v_ptr[VARS_MAX];
int v_cnt[VARS_MAX];
char v_slot[VARS_MAX];
int v_zc[VARS_MAX];              /* --xisa: how often the variable is named in the live bodies */
char v_zp[VARS_MAX];             /* --xisa: the variable is in the page (LDZ/STZ) */
int v_name[VARS_MAX];
int nvars;

/* functions: 1.. */
int f_name[FUNCS_MAX];
int f_rbase[FUNCS_MAX];
int f_rptr[FUNCS_MAX];
int f_np[FUNCS_MAX];            /* parameter count (from the last definition or prototype) */
int f_body[FUNCS_MAX];          /* the N_FUNC node of the definition, 0 = none */
int f_lab[FUNCS_MAX];           /* label text offset, 0 = not laid out */
int f_vfirst[FUNCS_MAX];
int f_vn[FUNCS_MAX];
int f_npar[FUNCS_MAX];
char f_live[FUNCS_MAX];
char f_root[FUNCS_MAX];          /* main and the functions named in funcaddr() (the program's entries) */
int f_stat[FUNCS_MAX];
int nfuncs;
int corder[FUNCS_MAX];          /* the compile order, for -l */
int ncorder;
char rbits[REACH_BYTES];        /* reach[f] as a bit row of REACH_ROW bytes */

/* structs/unions: 1.., members 1.. */
int s_size[STRUCTS_MAX];
int s_mfirst[STRUCTS_MAX];
int s_mn[STRUCTS_MAX];
int nstructs;
int m_name[MEMBERS_MAX];
int m_off[MEMBERS_MAX];
int m_base[MEMBERS_MAX];
int m_ptr[MEMBERS_MAX];
int m_cnt[MEMBERS_MAX];
int nmembers;

/* user labels (globals, functions, variables): their text, and a case-folded hash set (the assembler folds case) */
char lpool[LABELPOOL];
int lpn;
int ul_off[ULABELS_MAX];
int ul_next[ULABELS_MAX];
char ul_zp[ULABELS_MAX];         /* --xisa: this label is a page variable's */
int ul_hash[HASH_SIZE];
int nul;

/* generated labels: numbers 1.. and the prefix of each one made in the current function */
int nl;
int lbase;
char lkind[LKIND_MAX];

/* output: the line being built, the address being built, data lines, the peephole's pending lines */
char lb[LINE_MAX];
char abuf[LINE_MAX];
char db[LINE_MAX];
char wbuf[LINE_MAX];
char ebuf[EBUF_MAX];
char tbuf[LINE_MAX];
char pend[PEND_MAX * LINE_MAX];
int npend;
int dbn;
int nlines;
int nraw;
int last_ret;
char used[RT_COUNT];

/* results of the functions that return two or more values */
int fv;                         /* fold() */
int tb;                         /* type_of(), type_lval(): the base */
int tp;                         /* and the pointer depth */
int sm_off;                     /* struct_member() */
int sm_base;
int sm_ptr;
int sm_cnt;
int sl_base;                    /* static_lval(): the address is in abuf */
int sl_ptr;
int sl_slot;
int bs_a;                       /* binscale() */
int bs_b;
int bs_scale;
int bp_base;                    /* base_and_ptr() */
int bp_ptr;

/* code generation state */
int opt_org;
int opt_boot;
int opt_vector;
int opt_brur;
int opt_os;
int opt_list;
int opt_xisa;
int zused;                       /* --xisa: the page holds at least one variable */
int cur_fn;
int cur_vfirst;
int cur_vn;
int lp_brk[LOOPS_MAX];
int lp_cont[LOOPS_MAX];
int lp_n;
int park[PARK_MAX];
int npark;
int cs_val[CASES_MAX];
int cs_lab[CASES_MAX];
int ncs;
int sw_def;
int wmode;                      /* walk(): what to look for */
int wname;
int wfound;
int wfrom;
int wlist[FUNCS_MAX];
int nwlist;
char srcpath[LINE_MAX];
char outpath[LINE_MAX];
char argw[LINE_MAX];

#define W_DIRECT 1
#define W_ANYCALL 2
#define W_REACH 3
#define W_MENTION 4
#define W_FADDR 5
#define W_LIST 6
#define W_ZCOUNT 7

/* ---- prototypes ------------------------------------------------------------------------------------------------ */
void y1cc_main(void);
int s_len(char *s);
int s_eq(char *a, char *b);
int s_starts(char *s, char *p);
int s_cmp(char *a, char *b);
void bcat(char *buf, char *s);
void bchr(char *buf, int c);
void bnum(char *buf, int n);
void blab(char *buf, int n);
int is_alpha(int c);
int is_digit(int c);
int is_alnum(int c);
int is_pyspace(int c);
int lower(int c);
int mul16(int a, int b);
void fail(char *msg);
void e_start(char *s);
void e_s(char *s);
void e_q(char *s);
void e_n(int n);
void e_go(void);
char *nm_text(int id);
int intern(char *s);
int lit_intern(char *buf, int n);
int type_id(int base, int ptr, int cnt);
int new_node(int k, int a, int b, int c, int d);
void prog_add(int n);
int parse_int0(char *s, int *ok);
int esc_val(int c);
void lx_push(char *path);
int lx_peek(int k);
void lx_adv(void);
void lx_err(char *msg);
void lx_err2(char *msg, char *arg);
void put_tok(int kind, int val, int line);
void lex_one(void);
void lx_directive(void);
void lx_linecomment(void);
void lx_blockcomment(void);
void lx_ident(void);
void lx_number(void);
void lx_char(void);
void lx_string(void);
void lx_punct(void);
int split_word(char *s, int i, char *out);
int skip_space(char *s, int i);
void need_tok(int i);
int tk(int d);
int tv(int d);
int is_op(int d, int op);
int is_kw(int d, int kw);
void perr(char *msg);
void perr_tok(char *pre, int d);
void e_tok(int d);
void eat(int op);
int accept(int op);
int accept_kw(int kw);
int is_type_start(void);
void program(void);
void base_and_ptr(void);
int struct_def(void);
int const_expr(void);
void toplevel(void);
int initializer(void);
int param(void);
int block(void);
int stmt(void);
int expr(void);
int assign(void);
int logic_or(void);
int logic_and(void);
int binary(int lvl);
int in_level(int lvl, int op);
int unary(void);
int postfix(void);
int primary(void);
int fold(int e);
int fold_bin(int op, int l, int r);
int size_of(int base, int ptr);
int dec_ptr(int p);
void need(int h);
int lbl(int kind);
int ulabel(char *want);
void code_line(char *b);
void peep(char *b);
int is_ins(char *l);
void pp_push(char *b);
void pp_flush(void);
void sec_line(int s, char *t);
void data_line(char *t);
void bss_line(char *t);
void db_byte(int b);
void db_end(void);
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
void insrl(char *mn, int r, int lab);
void insrr(char *mn, int a, int b);
void insrs(char *mn, int r, char *s);
void label_def(int lab);
int vinfo(int name);
int local_var(int name);
void var_label(int v, char *buf);
int v_size(int v);
void struct_member(int tag, int mname);
int member_tag(int e);
int builtin_type(int name);
void type_of(int e);
void type_lval(int e);
int is_char(int e);
int static_addr(int e);
void kadd(int off);
int is_array(int e);
int static_lval(int e);
int is_narrow(int e);
int simple_byte(int e);
void byte_src(int e);
void gen_byte_acc(int e);
void load_static(int reg, int base, int ptr, int slot);
void ldst(char *mn, int reg);
void zreload(void);
void zpage_plan(void);
void zbss(int page);
int zsz(int v);
void store_static_r3(int base, int ptr, int slot, int narrow);
int is_leaf(int e);
void gen_leaf(int reg, int e);
int sizeof_expr(int e);
void add_const(int k);
void add_const_text(char *t);
void add_r4(void);
char *logic_mn(int op);
char *logici_mn(int op);
void logic_r4(int op);
void logic_const(int op, int k);
void shl1(void);
void shr1(void);
void scale_r3(int esz);
void gen_address(int e);
void deref_r3(int base, int ptr);
void gen_expr(int e);
void not_r3(void);
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
void lo_load(int mode, int k);
void branch_rel(int rel, int label, int lomode, int lok);
void gen_relcond(int rel, int a, int b, int label, int when);
void gen_cond(int e, int label, int when);
int port(int e);
void gen_call(int e);
int nth_arg(int e, int i);
int reaches(int callee, int n);
int any_call(int n);
int mentions(int n, int name);
void walk(int n);
void walk_list(int n);
int bit(int f, int g);
void set_bit(int f, int g);
void frame_save(int f);
void frame_restore(int f);
int local_root(int x);
int escapes(int e);
void gen_stmt(int s);
void gen_expr_stmt(int e);
void gen_switch(int e, int body);
void relabel(int first);
void switch_table(int lo, int hi, int miss);
int string_lab(int lit);
void collect_decls(int s, int fn);
void layout_func(int fn);
void compile_func(int fn);
void emit_bss_clear(void);
void declare_global(int g);
void emit_globals(void);
void const_data(int g, int pass);
void data_word_num(int v);
void data_word_lab(int lab);
void data_word_text(char *t);
int addr_of(int name);
void register_struct(int d);
void build_reach(void);
void gen_program(void);
void emit_runtime(void);
void rt(char *t);
void rtn(char *pre, int n);
void zrt(void);
void out_s(char *s);
void out_n(int n);

/* ---- small utilities -------------------------------------------------------------------------------------------- */
int s_len(char *s) { int n; n = 0; while (s[n]) n++; return n; }
int s_eq(char *a, char *b) { while (*a && *a == *b) { a++; b++; } return *a == *b; }
int s_starts(char *s, char *p) { while (*p) { if (*s != *p) return 0; s++; p++; } return 1; }
int s_cmp(char *a, char *b) {                       /* 0 equal, 1 a < b, 2 a > b (byte order, as Python sorts) */
    while (*a && *a == *b) { a++; b++; }
    if ((*a & 255) == (*b & 255)) return 0;
    if ((*a & 255) < (*b & 255)) return 1;
    return 2;
}
void bcat(char *buf, char *s) {
    int n;
    n = s_len(buf);
    while (*s) { if (n >= LINE_MAX - 1) fail("y1cc: line too long"); buf[n] = *s; n++; s++; }
    buf[n] = 0;
}
void bchr(char *buf, int c) {
    int n;
    n = s_len(buf);
    if (n >= LINE_MAX - 1) fail("y1cc: line too long");
    buf[n] = c; buf[n + 1] = 0;
}
void bnum(char *buf, int n) {                       /* decimal, n >= 0 */
    char d[8]; int k;
    k = 0;
    if (n == 0) { bchr(buf, '0'); return; }
    while (n > 0) { d[k] = '0' + n % 10; k++; n = n / 10; }
    while (k > 0) { k--; bchr(buf, d[k]); }
}
void blab(char *buf, int n) {                       /* a generated label: its prefix and number */
    if (n >= lbase) bcat(buf, lkname[lkind[n - lbase] & 255]); else bcat(buf, "s");
    bnum(buf, n);
}
int is_alpha(int c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }
int is_digit(int c) { return c >= '0' && c <= '9'; }
int is_alnum(int c) { return is_alpha(c) || is_digit(c); }
int is_pyspace(int c) { return c == ' ' || (c >= 9 && c <= 13) || (c >= 28 && c <= 31); }  /* str.split() */
int lower(int c) { if (c >= 'A' && c <= 'Z') return c + 32; return c; }
int mul16(int a, int b) {                           /* a * b mod 65536 without a 32-bit overflow on the host */
    return (a * (b & 255) + ((a * (b >> 8)) & 255) * 256) & 65535;
}

void fail(char *msg) { io_fail(msg); }
void e_start(char *s) { ebuf[0] = 0; e_s(s); }
void e_s(char *s) {                                 /* append, silently cut at EBUF_MAX */
    int n;
    n = s_len(ebuf);
    while (*s && n < EBUF_MAX - 1) { ebuf[n] = *s; n++; s++; }
    ebuf[n] = 0;
}
void e_q(char *s) { e_s("'"); e_s(s); e_s("'"); }  /* Python's repr() of a plain name */
char enbuf[12];
void e_n(int n) { enbuf[0] = 0; bnum(enbuf, n); e_s(enbuf); }
void e_go(void) { io_fail(ebuf); }

/* ---- names, literals, types, nodes ----------------------------------------------------------------------------- */
char *nm_text(int id) { return npool + nm_off[id]; }
int intern(char *s) {
    int h; int i; int id; char *p;
    h = 0;
    for (p = s; *p; p++) h = (h * 31 + (*p & 255)) % HASH_SIZE;
    for (id = nm_hash[h]; id; id = nm_next[id]) if (s_eq(npool + nm_off[id], s)) return id;
    if (nnames + 1 >= NAMES_MAX) fail("y1cc: too many names (NAMES_MAX)");
    nnames++; id = nnames;
    nm_off[id] = npn;
    for (i = 0; s[i]; i++) {
        if (npn >= NAMEPOOL - 1) fail("y1cc: name pool full (NAMEPOOL)");
        npool[npn] = s[i]; npn++;
    }
    npool[npn] = 0; npn++;
    nm_next[id] = nm_hash[h]; nm_hash[h] = id;
    return id;
}
int lit_intern(char *buf, int n) {
    int h; int i; int id; int same;
    h = n % HASH_SIZE;
    for (i = 0; i < n; i++) h = (h * 31 + (buf[i] & 255)) % HASH_SIZE;
    for (id = lit_hash[h]; id; id = lit_next[id]) {
        if (lit_len[id] == n) {
            same = 1;
            for (i = 0; i < n; i++) if ((spool[lit_off[id] + i] & 255) != (buf[i] & 255)) same = 0;
            if (same) return id;
        }
    }
    if (nlits + 1 >= LITS_MAX) fail("y1cc: too many string literals (LITS_MAX)");
    if (spn + n >= STRPOOL) fail("y1cc: string pool full (STRPOOL)");
    nlits++; id = nlits;
    lit_off[id] = spn; lit_len[id] = n;
    for (i = 0; i < n; i++) { spool[spn] = buf[i]; spn++; }
    lit_next[id] = lit_hash[h]; lit_hash[h] = id;
    return id;
}
int type_id(int base, int ptr, int cnt) {
    int i;
    for (i = 1; i <= ntypes; i++) if (ty_b[i] == base && ty_p[i] == ptr && ty_c[i] == cnt) return i;
    if (ntypes + 1 >= TYPES_MAX) fail("y1cc: too many types (TYPES_MAX)");
    ntypes++;
    ty_b[ntypes] = base; ty_p[ntypes] = ptr; ty_c[ntypes] = cnt;
    return ntypes;
}
int new_node(int k, int a, int b, int c, int d) {
    if (nn + 1 >= NODES_MAX) fail("y1cc: program too big (NODES_MAX)");
    nn++;
    nk[nn] = k; na[nn] = a; nb[nn] = b; nc[nn] = c; nd[nn] = d; nx[nn] = 0;
    return nn;
}
void prog_add(int n) {
    if (prog_last) nx[prog_last] = n; else prog_first = n;
    prog_last = n;
}

/* Python's int(s, 0): an optional sign, 0x/0o/0b or decimal (no leading zeros but "0...0"), underscores between
   digits; *ok = 0 when s is not such a number. The value is masked to 16 bits (a #define can be negative). */
int parse_int0(char *s, int *ok) {
    int neg; int base; int v; int d; int nd_; int c; int allzero;
    *ok = 0; neg = 0; v = 0; nd_ = 0; allzero = 1;
    if (*s == '+' || *s == '-') { neg = *s == '-'; s++; }
    base = 10;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) { base = 16; s = s + 2; }
    else if (s[0] == '0' && (s[1] == 'o' || s[1] == 'O')) { base = 8; s = s + 2; }
    else if (s[0] == '0' && (s[1] == 'b' || s[1] == 'B')) { base = 2; s = s + 2; }
    if (base != 10 && *s == '_') s++;
    for (;;) {
        c = *s;
        if (c == 0) break;
        if (c == '_' && nd_ && s[1] && s[1] != '_') { s++; continue; }
        d = 99;
        if (is_digit(c)) d = c - '0';
        else if (c >= 'a' && c <= 'f') d = c - 'a' + 10;
        else if (c >= 'A' && c <= 'F') d = c - 'A' + 10;
        if (d >= base) return 0;
        if (d) allzero = 0;
        v = (mul16(v, base) + d) & 65535;
        nd_++;
        s++;
    }
    if (nd_ == 0) return 0;
    if (base == 10 && nd_ > 1 && !allzero && *(s - nd_) == '0') return 0;
    *ok = 1;
    if (neg) v = (65535 - v + 1) & 65535;
    return v;
}

int esc_val(int c) {                                /* y1cc.py's ESC table; 256 = not an escape */
    if (c == 'n') return 10;
    if (c == 'r') return 13;
    if (c == 't') return 9;
    if (c == '0') return 0;
    if (c == 92) return 92;
    if (c == 39) return 39;
    if (c == '"') return 34;
    if (c == 'a') return 7;
    if (c == 'b') return 8;
    if (c == 'f') return 12;
    if (c == 'e') return 27;
    return 256;
}

/* ---- the lexer ----------------------------------------------------------------------------------------------- */
void lx_push(char *path) {
    int h; int i;
    h = io_open(path);
    if (!h) { e_start("y1cc: cannot open "); e_s(path); e_go(); }
    if (tk_have || fdep || f_h[0]) {
        if (fdep + 1 >= INCL_DEPTH) fail("y1cc: #include nested too deep (INCL_DEPTH)");
        fdep++;
    }
    f_h[fdep] = h; f_line[fdep] = 1; f_nla[fdep] = 0; f_path[fdep] = ppn;
    for (i = 0; path[i]; i++) {
        if (ppn >= PATHPOOL - 1) fail("y1cc: path pool full (PATHPOOL)");
        ppool[ppn] = path[i]; ppn++;
    }
    ppool[ppn] = 0; ppn++;
}
int lx_peek(int k) {                                /* the byte k ahead in the current file; 256 = its end */
    int b;
    b = fdep * 4;
    while (f_nla[fdep] <= k) { f_la[b + f_nla[fdep]] = io_getc(f_h[fdep]); f_nla[fdep]++; }
    return f_la[b + k];
}
void lx_adv(void) {
    int b; int i;
    lx_peek(0);
    b = fdep * 4;
    for (i = 1; i < f_nla[fdep]; i++) f_la[b + i - 1] = f_la[b + i];
    f_nla[fdep]--;
}
void lx_err(char *msg) {                            /* y1cc.py: "y1cc: path:line: msg" */
    e_start("y1cc: "); e_s(ppool + f_path[fdep]); e_s(":"); e_n(f_line[fdep]); e_s(": "); e_s(msg); e_go();
}
void lx_err2(char *msg, char *arg) {
    e_start("y1cc: "); e_s(ppool + f_path[fdep]); e_s(":"); e_n(f_line[fdep]); e_s(": "); e_s(msg); e_s(arg); e_go();
}
void put_tok(int kind, int val, int line) {
    int s;
    s = tk_have & 7;
    tk_kind[s] = kind; tk_val[s] = val; tk_line[s] = line;
    tk_have++;
}
void lex_one(void) {
    int c; int c1;
    for (;;) {
        c = lx_peek(0);
        if (c == 256) {
            if (fdep > 0) { io_close(f_h[fdep]); fdep--; continue; }
            put_tok(T_EOF, 0, f_line[0]); return;
        }
        if (c == 10) { f_line[fdep]++; lx_adv(); continue; }
        if (c == ' ' || c == 9 || c == 13 || c == 12) { lx_adv(); continue; }
        if (c == '#') { lx_directive(); continue; }
        c1 = lx_peek(1);
        if (c == '/' && c1 == '/') { lx_linecomment(); continue; }
        if (c == '/' && c1 == '*') { lx_blockcomment(); continue; }
        if (is_alpha(c) || c == '_') { lx_ident(); return; }
        if (is_digit(c)) { lx_number(); return; }
        if (c == 39) { lx_char(); return; }
        if (c == '"') { lx_string(); return; }
        lx_punct(); return;
    }
}
int skip_space(char *s, int i) { while (s[i] && is_pyspace(s[i] & 255)) i++; return i; }
int split_word(char *s, int i, char *out) {         /* the whitespace-free word at s[i..] into out; returns its end */
    int n;
    n = 0;
    while (s[i] && !is_pyspace(s[i] & 255)) {
        if (n >= LINE_MAX - 1) fail("y1cc: word too long");
        out[n] = s[i]; n++; i++;
    }
    out[n] = 0;
    return i;
}
void lx_directive(void) {                           /* a preprocessor line: #define, #include; others ignored */
    int n; int c; int i; int j; int ok; int v; int id; int k; int found;
    n = 0;
    for (;;) {
        c = lx_peek(0);
        if (c == 256 || c == 10) break;
        if (n >= DIR_MAX - 1) lx_err("preprocessor line too long");
        dirbuf[n] = c; n++;
        lx_adv();
    }
    dirbuf[n] = 0;
    i = skip_space(dirbuf, 0);
    i = split_word(dirbuf, i, wbuf);                /* parts[0] */
    j = skip_space(dirbuf, i);
    if (s_eq(wbuf, "#define")) {
        if (!dirbuf[j]) return;
        k = split_word(dirbuf, j, pbuf);            /* parts[1] */
        k = skip_space(dirbuf, k);
        if (!dirbuf[k]) return;                     /* no value: ignored, as y1cc.py does */
        split_word(dirbuf, k, p2buf);               /* parts[2].split()[0] */
        v = parse_int0(p2buf, &ok);
        if (!ok) {
            if (s_len(p2buf) == 3 && p2buf[0] == 39 && p2buf[2] == 39) { v = p2buf[1] & 255; ok = 1; }
        }
        if (!ok) {
            e_start("y1cc: "); e_s(ppool + f_path[fdep]); e_s(":"); e_n(f_line[fdep]); e_s(": #define ");
            e_s(pbuf); e_s(": value "); e_q(p2buf); e_s(" is not an integer"); e_go();
        }
        id = intern(pbuf);
        nm_mac[id] = 1; nm_macv[id] = v;
        return;
    }
    if (s_eq(wbuf, "#include")) {
        if (!dirbuf[j]) return;
        k = split_word(dirbuf, j, pbuf);            /* parts[1] */
        k = skip_space(dirbuf, k);
        if (dirbuf[k]) { bcat(pbuf, " "); bcat(pbuf, dirbuf + k); }    /* parts[1] + " " + parts[2] */
        if (pbuf[0] != '"' || pbuf[1] == '"' || pbuf[1] == 0) lx_err("#include wants a \"file\"");
        for (k = 1; pbuf[k] && pbuf[k] != '"'; k++) p2buf[k - 1] = pbuf[k];
        if (pbuf[k] != '"') lx_err("#include wants a \"file\"");
        p2buf[k - 1] = 0;
        if (!io_find(p2buf, ppool + f_path[fdep], tbuf, LINE_MAX)) {
            e_start("y1cc: "); e_s(ppool + f_path[fdep]); e_s(": cannot find #include \""); e_s(p2buf); e_s("\"");
            e_go();
        }
        found = 0;
        for (k = 0; k < nincl; k++) if (s_eq(ppool + incl_off[k], tbuf)) found = 1;
        if (found) return;                          /* each file once */
        if (nincl >= INCLS_MAX) fail("y1cc: too many #include files (INCLS_MAX)");
        lx_push(tbuf);
        incl_off[nincl] = f_path[fdep]; nincl++;
    }
}
void lx_linecomment(void) {                         /* // ... ; "//#define NAME value" (p8cc style) is honoured */
    int n; int c; int i; int k; int ok; int v;
    lx_adv(); lx_adv();
    n = 0;
    for (;;) {
        c = lx_peek(0);
        if (c == 256 || c == 10) break;
        if (n < DIR_MAX - 1) { dirbuf[n] = c; n++; }
        lx_adv();
    }
    dirbuf[n] = 0;
    i = skip_space(dirbuf, 0);
    if (!s_starts(dirbuf + i, "#define")) return;
    i = split_word(dirbuf, i, wbuf);
    i = skip_space(dirbuf, i);
    if (!dirbuf[i]) return;
    k = split_word(dirbuf, i, pbuf);
    k = skip_space(dirbuf, k);
    if (!dirbuf[k]) return;
    split_word(dirbuf, k, p2buf);
    v = parse_int0(p2buf, &ok);
    if (!ok) {
        e_start("y1cc: "); e_s(ppool + f_path[fdep]); e_s(":"); e_n(f_line[fdep]); e_s(": //#define ");
        e_s(pbuf); e_s(": not an integer"); e_go();
    }
    k = intern(pbuf);
    nm_mac[k] = 1; nm_macv[k] = v;
}
void lx_blockcomment(void) {
    int c; int lines;
    lx_adv(); lx_adv();
    lines = 0;
    for (;;) {
        c = lx_peek(0);
        if (c == 256) lx_err("unterminated comment");
        if (c == '*' && lx_peek(1) == '/') { lx_adv(); lx_adv(); break; }
        if (c == 10) lines++;
        lx_adv();
    }
    f_line[fdep] = f_line[fdep] + lines;
}
void lx_ident(void) {
    int n; int c; int id;
    n = 0;
    for (;;) {
        c = lx_peek(0);
        if (!(is_alnum(c) || c == '_')) break;
        if (n >= ID_MAX - 1) lx_err("identifier too long");
        idbuf[n] = c; n++;
        lx_adv();
    }
    idbuf[n] = 0;
    id = intern(idbuf);
    if (nm_mac[id]) put_tok(T_NUM, nm_macv[id], f_line[fdep]);
    else if (id <= KW_LAST) put_tok(T_KW, id, f_line[fdep]);
    else put_tok(T_ID, id, f_line[fdep]);
}
void lx_number(void) {
    int n; int c; int v; int d; int big;
    n = 0; v = 0; big = 0;
    if (lx_peek(0) == '0' && (lx_peek(1) == 'x' || lx_peek(1) == 'X')) {
        idbuf[0] = '0'; idbuf[1] = lx_peek(1); n = 2;
        lx_adv(); lx_adv();
        for (;;) {
            c = lx_peek(0);
            d = 99;
            if (is_digit(c)) d = c - '0';
            else if (c >= 'a' && c <= 'f') d = c - 'a' + 10;
            else if (c >= 'A' && c <= 'F') d = c - 'A' + 10;
            if (d == 99) break;
            if (v > 4095) big = 1; else v = v * 16 + d;
            if (n < ID_MAX - 1) { idbuf[n] = c; n++; }
            lx_adv();
        }
        if (n == 2) lx_err("bad hex constant");
    } else {
        for (;;) {
            c = lx_peek(0);
            if (!is_digit(c)) break;
            d = c - '0';
            if (v > 6553 || (v == 6553 && d > 5)) big = 1; else v = v * 10 + d;
            if (n < ID_MAX - 1) { idbuf[n] = c; n++; }
            lx_adv();
        }
    }
    idbuf[n] = 0;
    if (big) {                                      /* int is 16-bit: no silent truncation */
        e_start("y1cc: "); e_s(ppool + f_path[fdep]); e_s(":"); e_n(f_line[fdep]); e_s(": integer constant ");
        e_s(idbuf); e_s(" does not fit 16 bits"); e_go();
    }
    put_tok(T_NUM, v, f_line[fdep]);
}
void lx_char(void) {                                /* 'c' or '\e': 3 or 4 characters, as y1cc.py counts them */
    int c; int v;
    c = lx_peek(1);
    if (c == 92) {
        v = esc_val(lx_peek(2));
        if (v == 256) { tbuf[0] = 92; tbuf[1] = lx_peek(2); tbuf[2] = 0; lx_err2("bad escape ", tbuf); }
        put_tok(T_NUM, v, f_line[fdep]);
        lx_adv(); lx_adv(); lx_adv(); lx_adv();
        return;
    }
    put_tok(T_NUM, c & 255, f_line[fdep]);
    lx_adv(); lx_adv(); lx_adv();
}
void lx_string(void) {
    int n; int c; int v;
    lx_adv();
    n = 0;
    for (;;) {
        c = lx_peek(0);
        if (c == 256) lx_err("unterminated string");
        if (c == '"') { lx_adv(); break; }
        if (n >= STRLIT_MAX) lx_err("string literal too long (STRLIT_MAX)");
        if (c == 92) {
            v = esc_val(lx_peek(1));
            if (v == 256) { tbuf[0] = 92; tbuf[1] = lx_peek(1); tbuf[2] = 0; lx_err2("bad escape ", tbuf); }
            sbuf[n] = v; n++;
            lx_adv(); lx_adv();
        } else {
            sbuf[n] = c; n++;
            lx_adv();
        }
    }
    put_tok(T_STR, lit_intern(sbuf, n), f_line[fdep]);
}
void lx_punct(void) {
    int op; char *t; int k; int ok;
    for (op = 1; op <= O_LAST; op++) {
        t = optext[op];
        ok = 1;
        for (k = 0; t[k]; k++) if (lx_peek(k) != (t[k] & 255)) ok = 0;
        if (ok) {
            put_tok(T_OP, op, f_line[fdep]);
            for (k = 0; t[k]; k++) lx_adv();
            return;
        }
    }
    tbuf[0] = 39; tbuf[1] = lx_peek(0); tbuf[2] = 39; tbuf[3] = 0;
    lx_err2("bad character ", tbuf);
}

/* ---- the parser -> AST (y1cc.py's class P) --------------------------------------------------------------------- */
void need_tok(int i) { while (tk_have <= i) lex_one(); }
int tk(int d) { need_tok(ti + d); return tk_kind[(ti + d) & 7]; }
int tv(int d) { need_tok(ti + d); return tk_val[(ti + d) & 7]; }
int is_op(int d, int op) { return tk(d) == T_OP && tv(d) == op; }
int is_kw(int d, int kw) { return tk(d) == T_KW && tv(d) == kw; }
void perr(char *msg) {                              /* "y1cc: line N: msg" */
    need_tok(ti);
    e_start("y1cc: line "); e_n(tk_line[ti & 7]); e_s(": "); e_s(msg); e_go();
}
void e_tok(int d) {                                 /* Python's repr() of a token's value */
    int k; int v; int i;
    k = tk(d); v = tv(d);
    if (k == T_EOF) { e_s("None"); return; }
    if (k == T_NUM) { e_n(v); return; }
    if (k == T_OP) { e_q(optext[v]); return; }
    if (k == T_STR) {
        e_s("[");
        for (i = 0; i < lit_len[v]; i++) { if (i) e_s(", "); e_n(spool[lit_off[v] + i] & 255); }
        e_s("]");
        return;
    }
    e_q(nm_text(v));
}
void perr_tok(char *pre, int d) {
    need_tok(ti);
    e_start("y1cc: line "); e_n(tk_line[ti & 7]); e_s(": "); e_s(pre); e_tok(d); e_go();
}
void eat(int op) {
    if (!is_op(0, op)) {
        need_tok(ti);
        e_start("y1cc: line "); e_n(tk_line[ti & 7]); e_s(": expected "); e_q(optext[op]); e_s(", got ");
        e_tok(0); e_go();
    }
    ti++;
}
int accept(int op) { if (is_op(0, op)) { ti++; return 1; } return 0; }
int accept_kw(int kw) { if (is_kw(0, kw)) { ti++; return 1; } return 0; }
int is_type_start(void) {
    int v;
    if (tk(0) != T_KW) return 0;
    v = tv(0);
    return v == K_INT || v == K_CHAR || v == K_VOID || v == K_STRUCT || v == K_UNION || v == K_UNSIGNED ||
           v == K_CONST || v == K_STATIC;
}

void program(void) { while (tk(0) != T_EOF) toplevel(); }

void base_and_ptr(void) {                           /* -> bp_base, bp_ptr */
    int base; int ptr;
    while (is_kw(0, K_CONST) || is_kw(0, K_STATIC) || is_kw(0, K_UNSIGNED)) ti++;
    if (is_kw(0, K_STRUCT) || is_kw(0, K_UNION)) {
        ti++;
        base = tv(0); ti++;
        if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected struct/union tag");
    } else if (is_kw(0, K_INT) || is_kw(0, K_CHAR) || is_kw(0, K_VOID)) {
        base = tv(0); ti++;
    } else if (tk_kind[(ti + 7) & 7] == T_KW && tk_val[(ti + 7) & 7] == K_UNSIGNED && ti > 0) {
        base = K_INT;                                /* bare `unsigned` */
    } else {
        perr("expected a type");
        base = 0;
    }
    ptr = 0;
    for (;;) {
        if (accept(O_STAR)) ptr++;
        else if (is_kw(0, K_CONST)) ti++;
        else break;
    }
    bp_base = base; bp_ptr = ptr;
}
int tok_name(int d) {                               /* the name id of an id/keyword token (y1cc.py: next()[1]) */
    if (tk(d) == T_ID || tk(d) == T_KW) return tv(d);
    return 0;
}
int struct_def(void) {                              /* struct/union T { ... }; */
    int kind; int tag; int first; int last; int m; int base; int ptr; int nm; int count;
    kind = is_kw(0, K_UNION) ? 2 : 1; ti++;
    tag = tok_name(0); ti++;
    eat(O_LBRACE);
    first = 0; last = 0;
    while (!is_op(0, O_RBRACE)) {
        base_and_ptr(); base = bp_base; ptr = bp_ptr;
        nm = tok_name(0); ti++;
        count = 0;
        if (accept(O_LBRACK)) { count = const_expr(); eat(O_RBRACK); }
        eat(O_SEMI);
        m = new_node(N_MEMBERDEF, type_id(base, ptr, count), nm, 0, 0);
        if (last) nx[last] = m; else first = m;
        last = m;
    }
    eat(O_RBRACE); eat(O_SEMI);
    return new_node(N_STRUCTDEF, kind, tag, first, 0);
}
int const_expr(void) {
    int e;
    e = expr();
    if (!fold(e)) perr("constant expression expected");
    return fv;
}
void toplevel(void) {
    int base; int ptr; int name; int first; int last; int p; int arr; int count; int init; int flags;
    if ((is_kw(0, K_STRUCT) || is_kw(0, K_UNION)) && is_op(2, O_LBRACE)) { prog_add(struct_def()); return; }
    base_and_ptr(); base = bp_base; ptr = bp_ptr;
    name = tv(0); ti++;
    if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected name");
    if (accept(O_LPAREN)) {
        first = 0; last = 0;
        if (is_kw(0, K_VOID) && is_op(1, O_RPAREN)) ti++;
        else if (!is_op(0, O_RPAREN)) {
            first = param(); last = first;
            while (accept(O_COMMA)) { p = param(); nx[last] = p; last = p; }
        }
        eat(O_RPAREN);
        if (accept(O_SEMI)) { prog_add(new_node(N_PROTO, type_id(base, ptr, 0), name, first, 0)); return; }
        p = new_node(N_FUNC, type_id(base, ptr, 0), name, first, 0);
        nd[p] = block();
        prog_add(p);
        return;
    }
    for (;;) {                                      /* int a, *b, c[3]; */
        arr = 0; count = 0; flags = 0;
        if (accept(O_LBRACK)) {
            arr = 1;
            if (is_op(0, O_RBRACK)) flags = 2; else count = const_expr();
            eat(O_RBRACK);
        }
        init = 0;
        if (accept(O_ASSIGN)) init = initializer();
        prog_add(new_node(N_GVAR, type_id(base, ptr, count), name, init, arr | flags));
        if (!accept(O_COMMA)) break;
        ptr = 0;                                    /* a new declarator starts from the base type (int *p, q) */
        while (accept(O_STAR)) ptr++;
        name = tok_name(0); ti++;
    }
    eat(O_SEMI);
}
int initializer(void) {                             /* constant global initializer */
    int first; int last; int it; int nm;
    if (accept(O_LBRACE)) {
        first = 0; last = 0;
        if (!is_op(0, O_RBRACE)) {
            first = initializer(); last = first;
            while (accept(O_COMMA)) {
                if (is_op(0, O_RBRACE)) break;
                it = initializer(); nx[last] = it; last = it;
            }
        }
        eat(O_RBRACE);
        return new_node(N_INITLIST, first, 0, 0, 0);
    }
    if (tk(0) == T_STR) { it = tv(0); ti++; return new_node(N_INITSTR, it, 0, 0, 0); }
    if (accept(O_AMP)) {
        nm = tv(0); ti++;
        if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected a name after &");
        return new_node(N_INITADDR, nm, 0, 0, 0);
    }
    if (tk(0) == T_ID && (is_op(1, O_COMMA) || is_op(1, O_SEMI) || is_op(1, O_RBRACE))) {
        nm = tv(0); ti++;                           /* an array's address */
        return new_node(N_INITADDR, nm, 0, 0, 0);
    }
    it = expr();
    if (!fold(it)) perr("non-constant global initializer");
    return new_node(N_INITNUM, fv, 0, 0, 0);
}
int param(void) {
    int base; int ptr; int nm;
    base_and_ptr(); base = bp_base; ptr = bp_ptr;
    nm = tv(0); ti++;
    if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected parameter name");
    if (accept(O_LBRACK)) { eat(O_RBRACK); ptr++; }  /* T a[] as a parameter = pointer */
    return new_node(N_PARAM, type_id(base, ptr, 0), nm, 0, 0);
}
int block(void) {
    int first; int last; int s;
    eat(O_LBRACE);
    first = 0; last = 0;
    while (!is_op(0, O_RBRACE)) {
        s = stmt();
        if (last) nx[last] = s; else first = s;
        last = s;
    }
    eat(O_RBRACE);
    return new_node(N_BLOCK, first, 0, 0, 0);
}
int stmt(void) {
    int base; int ptr; int p; int name; int count; int init; int first; int last; int d; int c; int t; int e;
    int i; int post;
    if (is_op(0, O_LBRACE)) return block();
    if (is_type_start()) {
        base_and_ptr(); base = bp_base; ptr = bp_ptr;   /* the stars consumed here belong to the FIRST declarator */
        first = 0; last = 0;
        for (;;) {
            p = ptr; ptr = 0;                       /* later declarators start from the base type (int *p, q) */
            while (accept(O_STAR)) p++;
            name = tok_name(0); ti++;
            count = 0;
            if (accept(O_LBRACK)) { count = const_expr(); eat(O_RBRACK); }
            init = 0;
            if (accept(O_ASSIGN)) init = expr();
            d = new_node(N_DECL, type_id(base, p, count), name, init, 0);
            if (last) nx[last] = d; else first = d;
            last = d;
            if (!accept(O_COMMA)) break;
        }
        eat(O_SEMI);
        if (first == last) return first;
        return new_node(N_BLOCK, first, 0, 0, 0);
    }
    if (is_kw(0, K_IF)) {
        ti++; eat(O_LPAREN); c = expr(); eat(O_RPAREN);
        t = stmt(); e = 0;
        if (accept_kw(K_ELSE)) e = stmt();
        return new_node(N_IF, c, t, e, 0);
    }
    if (is_kw(0, K_WHILE)) {
        ti++; eat(O_LPAREN); c = expr(); eat(O_RPAREN);
        return new_node(N_WHILE, c, stmt(), 0, 0);
    }
    if (is_kw(0, K_FOR)) {
        ti++; eat(O_LPAREN);
        i = 0; if (!is_op(0, O_SEMI)) i = expr();
        eat(O_SEMI);
        c = 0; if (!is_op(0, O_SEMI)) c = expr();
        eat(O_SEMI);
        post = 0; if (!is_op(0, O_RPAREN)) post = expr();
        eat(O_RPAREN);
        t = stmt();
        return new_node(N_FOR, i, c, post, t);
    }
    if (is_kw(0, K_RETURN)) {
        ti++; e = 0;
        if (!is_op(0, O_SEMI)) e = expr();
        eat(O_SEMI);
        return new_node(N_RETURN, e, 0, 0, 0);
    }
    if (is_kw(0, K_SWITCH)) {
        ti++; eat(O_LPAREN); e = expr(); eat(O_RPAREN);
        if (!is_op(0, O_LBRACE)) perr("switch body must be a { block }");
        return new_node(N_SWITCH, e, block(), 0, 0);
    }
    if (is_kw(0, K_CASE)) { ti++; c = const_expr(); eat(O_COLON); return new_node(N_CASE, c, 0, 0, 0); }
    if (is_kw(0, K_DEFAULT)) { ti++; eat(O_COLON); return new_node(N_DEFAULT, 0, 0, 0, 0); }
    if (is_kw(0, K_BREAK)) { ti++; eat(O_SEMI); return new_node(N_BREAK, 0, 0, 0, 0); }
    if (is_kw(0, K_CONTINUE)) { ti++; eat(O_SEMI); return new_node(N_CONTINUE, 0, 0, 0, 0); }
    if (is_op(0, O_SEMI)) { ti++; return new_node(N_EMPTY, 0, 0, 0, 0); }
    e = expr(); eat(O_SEMI);
    return new_node(N_EXPR, e, 0, 0, 0);
}
int expr(void) { return assign(); }
int assign_op(int op) {                             /* x op= e  ->  the binary operator */
    if (op == O_ADDEQ) return O_PLUS;
    if (op == O_SUBEQ) return O_MINUS;
    if (op == O_MULEQ) return O_STAR;
    if (op == O_DIVEQ) return O_SLASH;
    if (op == O_MODEQ) return O_PERCENT;
    if (op == O_ANDEQ) return O_AMP;
    if (op == O_OREQ) return O_BAR;
    if (op == O_XOREQ) return O_CARET;
    if (op == O_SHLEQ) return O_SHL;
    if (op == O_SHREQ) return O_SHR;
    return 0;
}
int assign(void) {
    int left; int a; int b; int op;
    left = logic_or();
    if (is_op(0, O_QUEST)) {                        /* c ? a : b */
        ti++; a = assign(); eat(O_COLON); b = assign();
        return new_node(N_COND, left, a, b, 0);
    }
    if (is_op(0, O_ASSIGN)) { ti++; a = assign(); return new_node(N_ASSIGN, left, a, 0, 0); }
    if (tk(0) == T_OP && assign_op(tv(0))) {        /* x op= e  ->  x = x op e (lvalue evaluated twice) */
        op = assign_op(tv(0)); ti++;
        a = assign();
        return new_node(N_ASSIGN, left, new_node(N_BIN, op, left, a, 0), 0, 0);
    }
    return left;
}
int logic_or(void) {
    int left; int r;
    left = logic_and();
    while (is_op(0, O_OROR)) { ti++; r = logic_and(); left = new_node(N_LOGOR, left, r, 0, 0); }
    return left;
}
int logic_and(void) {
    int left; int r;
    left = binary(0);
    while (is_op(0, O_ANDAND)) { ti++; r = binary(0); left = new_node(N_LOGAND, left, r, 0, 0); }
    return left;
}
int in_level(int lvl, int op) {                     /* y1cc.py's LEVELS */
    if (lvl == 0) return op == O_BAR;
    if (lvl == 1) return op == O_CARET;
    if (lvl == 2) return op == O_AMP;
    if (lvl == 3) return op == O_EQ || op == O_NE;
    if (lvl == 4) return op == O_LT || op == O_GT || op == O_LE || op == O_GE;
    if (lvl == 5) return op == O_SHL || op == O_SHR;
    if (lvl == 6) return op == O_PLUS || op == O_MINUS;
    return op == O_STAR || op == O_SLASH || op == O_PERCENT;
}
int binary(int lvl) {
    int left; int op; int r;
    if (lvl >= 8) return unary();
    left = binary(lvl + 1);
    while (tk(0) == T_OP && in_level(lvl, tv(0))) {
        op = tv(0); ti++;
        r = binary(lvl + 1);
        left = new_node(N_BIN, op, left, r, 0);
    }
    return left;
}
int unary(void) {
    int op; int e; int v;
    if (tk(0) == T_OP) {
        op = tv(0);
        if (op == O_MINUS || op == O_NOT || op == O_AMP || op == O_STAR || op == O_TILDE) {
            ti++; e = unary(); return new_node(N_UNARY, op, e, 0, 0);
        }
        if (op == O_INC || op == O_DEC) { ti++; e = unary(); return new_node(N_PREINC, op, e, 0, 0); }
    }
    if (is_kw(0, K_SIZEOF)) {
        ti++;
        if (is_op(0, O_LPAREN) && tk(1) == T_KW) {
            v = tv(1);
            if (v == K_INT || v == K_CHAR || v == K_STRUCT || v == K_UNION || v == K_UNSIGNED) {
                ti++; base_and_ptr(); eat(O_RPAREN);
                return new_node(N_SIZEOFT, bp_base, bp_ptr, 0, 0);
            }
        }
        e = unary();
        return new_node(N_SIZEOFE, e, 0, 0, 0);
    }
    return postfix();
}
int postfix(void) {
    int e; int first; int last; int a; int n; int m;
    e = primary();
    for (;;) {
        if (is_op(0, O_LPAREN)) {
            ti++; first = 0; last = 0; n = 0;
            if (!is_op(0, O_RPAREN)) {
                first = expr(); last = first; n = 1;
                while (accept(O_COMMA)) { a = expr(); nx[last] = a; last = a; n++; }
            }
            eat(O_RPAREN);
            if (nk[e] != N_ID) perr("call of non-function");
            e = new_node(N_CALL, na[e], first, n, 0);
        } else if (is_op(0, O_LBRACK)) {
            ti++; a = expr(); eat(O_RBRACK);
            e = new_node(N_INDEX, e, a, 0, 0);
        } else if (is_op(0, O_DOT)) {
            ti++; m = tok_name(0); ti++;
            e = new_node(N_MEMBER, e, m, 0, 0);
        } else if (is_op(0, O_ARROW)) {
            ti++; m = tok_name(0); ti++;
            e = new_node(N_ARROW, e, m, 0, 0);
        } else if (is_op(0, O_INC) || is_op(0, O_DEC)) {
            m = tv(0); ti++;
            e = new_node(N_POSTINC, m, e, 0, 0);
        } else {
            return e;
        }
    }
    return e;
}
int primary(void) {
    int k; int v; int e;
    k = tk(0); v = tv(0);
    if (k == T_NUM) { ti++; return new_node(N_NUM, v, 0, 0, 0); }
    if (k == T_STR) { ti++; return new_node(N_STR, v, 0, 0, 0); }
    if (k == T_ID) { ti++; return new_node(N_ID, v, 0, 0, 0); }
    if (k == T_OP && v == O_LPAREN) { ti++; e = expr(); eat(O_RPAREN); return e; }
    perr_tok("unexpected ", 0);
    return 0;
}

/* ---- constant folding ---------------------------------------------------------------------------------------- */
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
    if (k == N_SIZEOFT) { fv = size_of(na[e], nb[e]); return 1; }
    if (k == N_COND) {
        if (!fold(na[e])) return 0;
        if (fv) return fold(nb[e]);
        return fold(nc[e]);
    }
    return 0;
}
int fold_bin(int op, int l, int r) {
    int a; int b; int oka; int okb; int x;
    oka = fold(l); a = fv;
    okb = fold(r); b = fv;
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

/* ---- types --------------------------------------------------------------------------------------------------- */
int size_of(int base, int ptr) {
    if (ptr > 0 || base == K_INT) return 2;
    if (base == K_CHAR) return 1;
    if (base && nm_st[base]) return s_size[nm_st[base]];
    e_start("y1cc: unknown type "); e_q(base ? nm_text(base) : ""); e_go();
    return 0;
}
int dec_ptr(int p) { if (p > 0) return p - 1; return 0; }   /* y1cc.py goes to -1 here; only non-pointers get it */

/* ---- labels ---------------------------------------------------------------------------------------------------- */
void need(int h) { used[h] = 1; }
int lbl(int kind) {                                 /* a fresh generated label: prefix + running number */
    nl++;
    if (nl >= lbase) {
        if (nl - lbase >= LKIND_MAX) fail("y1cc: too many labels in one function (LKIND_MAX)");
        lkind[nl - lbase] = kind;
    }
    return nl;
}
int ul_find(char *s) {                              /* case-folded membership in the user-label set */
    int h; int id; int i; char *p;
    h = 0;
    for (p = s; *p; p++) h = (h * 31 + lower(*p & 255)) % HASH_SIZE;
    for (id = ul_hash[h]; id; id = ul_next[id]) {
        p = lpool + ul_off[id];
        for (i = 0; s[i] && lower(s[i] & 255) == lower(p[i] & 255); i++) {}
        if (s[i] == 0 && p[i] == 0) return id;
    }
    return 0;
}
int ulabel(char *want) {                            /* y1cc.py label(): sanitised, <= 29 chars, unique ignoring case */
    int i; int n; int h; int id; int off; char *p;
    tbuf[0] = 0;
    if (!want[0] || is_digit(want[0])) bchr(tbuf, '_');
    for (i = 0; want[i]; i++) {
        if (is_alnum(want[i]) || want[i] == '_') bchr(tbuf, want[i]); else bchr(tbuf, '_');
    }
    for (i = 0; i < LABEL_MAX && tbuf[i]; i++) pbuf[i] = tbuf[i];
    pbuf[i] = 0;                                    /* cand = s[:29] */
    n = 0;
    while (ul_find(pbuf)) {
        n++;
        for (i = 0; i < LABEL_MAX - 5 && tbuf[i]; i++) pbuf[i] = tbuf[i];
        pbuf[i] = 0;                                /* base = s[:24] */
        bchr(pbuf, '_'); bnum(pbuf, n);
    }
    if (nul + 1 >= ULABELS_MAX) fail("y1cc: too many labels (ULABELS_MAX)");
    if (lpn + s_len(pbuf) + 1 >= LABELPOOL) fail("y1cc: label pool full (LABELPOOL)");
    nul++; id = nul;
    off = lpn;
    for (i = 0; pbuf[i]; i++) { lpool[lpn] = pbuf[i]; lpn++; }
    lpool[lpn] = 0; lpn++;
    ul_off[id] = off;
    h = 0;
    for (p = pbuf; *p; p++) h = (h * 31 + lower(*p & 255)) % HASH_SIZE;
    ul_next[id] = ul_hash[h]; ul_hash[h] = id;
    return off;
}

/* ---- output: sections, lines, the streaming peephole -------------------------------------------------------- */
void sec_line(int s, char *t) {
    while (*t) { io_put(s, *t & 255); t++; }
    io_put(s, 10);
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
    int i; int n; int e;
    i = skip_space(l, 0);
    n = 0;
    while (l[i] && !is_pyspace(l[i] & 255)) { mn[n] = l[i]; n++; i++; }
    mn[n] = 0;
    i = skip_space(l, i);
    e = s_len(l);
    while (e > i && is_pyspace(l[e - 1] & 255)) e--;
    n = 0;
    while (i < e) { arg[n] = l[i]; n++; i++; }
    arg[n] = 0;
    return 1;
}
char pmn_a[LINE_MAX];
char parg_a[LINE_MAX];
char pmn_b[LINE_MAX];
char parg_b[LINE_MAX];
void code_line(char *b) {                           /* one line of code: counted raw, then through the peephole */
    nraw++;
    last_ret = s_eq(b, "        RET");
    peep(b);
}
void peep(char *b) {
    char *a; int i;
    for (;;) {
        if (npend == 0) break;
        a = pend + (npend - 1) * LINE_MAX;
        if (!is_ins(a)) break;
        mn_arg(a, pmn_a, parg_a);
        if (is_ins(b)) {
            mn_arg(b, pmn_b, parg_b);
            if (((s_eq(pmn_a, "STR") && s_eq(pmn_b, "LDR")) || (s_eq(pmn_a, "STZ") && s_eq(pmn_b, "LDZ"))) &&
                s_eq(parg_a, parg_b) && s_starts(parg_a, "R3,"))
                return;                             /* store then reload: drop the reload */
            if ((((s_eq(pmn_a, "STR") || s_eq(pmn_a, "LDR")) && s_eq(pmn_b, "LDR")) ||
                 ((s_eq(pmn_a, "STZ") || s_eq(pmn_a, "LDZ")) && s_eq(pmn_b, "LDZ"))) && s_starts(parg_a, "R3,") &&
                s_starts(parg_b, "R4,") && s_eq(parg_b + 3, parg_a + 3)) {
                pp_push("        MOVRR R3,R4");
                return;
            }
            if (s_eq(pmn_a, "MOVRR") && s_eq(pmn_b, "MOVRR") && s_eq(parg_a, "R3,R4") && s_eq(parg_b, "R4,R3"))
                return;
            break;
        }
        if (s_eq(pmn_a, "BR")) {                    /* a jump to the next line */
            i = skip_space(b, 0);
            if (s_starts(b + i, parg_a) && b[i + s_len(parg_a)] == ':') { npend--; continue; }
        }
        break;
    }
    pp_push(b);
}
void pp_push(char *b) {
    int i; int n; char *d;
    mn_arg(b, pmn_b, parg_b);
    if (!(is_ins(b) && s_eq(pmn_b, "BR"))) pp_flush(); /* only a BR can still be removed by a later line */
    if (npend >= PEND_MAX) {                        /* never in practice: write the oldest */
        sec_line(0, pend);
        for (i = 1; i < npend; i++) {
            d = pend + (i - 1) * LINE_MAX;
            for (n = 0; pend[i * LINE_MAX + n]; n++) d[n] = pend[i * LINE_MAX + n];
            d[n] = 0;
        }
        npend--;
    }
    d = pend + npend * LINE_MAX;
    i = 0;
    while (b[i]) { d[i] = b[i]; i++; }
    d[i] = 0;
    npend++;
}
void pp_flush(void) {
    int i;
    for (i = 0; i < npend; i++) sec_line(0, pend + i * LINE_MAX);
    npend = 0;
}

/* instruction builders: "        MN args" */
void L(char *mn) { lb[0] = 0; bcat(lb, "        "); bcat(lb, mn); }
void Lsp(void) { bchr(lb, ' '); }
void Lr(int r) { bchr(lb, 'R'); bchr(lb, '0' + r); }
void Lend(void) { code_line(lb); }
void ins0(char *mn) { L(mn); Lend(); }
void insr(char *mn, int r) { L(mn); Lsp(); Lr(r); Lend(); }
void insn(char *mn, int n) { L(mn); Lsp(); bnum(lb, n); Lend(); }
void insl(char *mn, int lab) { L(mn); Lsp(); blab(lb, lab); Lend(); }
void inss(char *mn, char *s) { L(mn); Lsp(); bcat(lb, s); Lend(); }
void insrn(char *mn, int r, int n) { L(mn); Lsp(); Lr(r); bchr(lb, ','); bnum(lb, n); Lend(); }
void insrl(char *mn, int r, int lab) { L(mn); Lsp(); Lr(r); bchr(lb, ','); blab(lb, lab); Lend(); }
void insrr(char *mn, int a, int b) { L(mn); Lsp(); Lr(a); bchr(lb, ','); Lr(b); Lend(); }
void insrs(char *mn, int r, char *s) { L(mn); Lsp(); Lr(r); bchr(lb, ','); bcat(lb, s); Lend(); }
void label_def(int lab) { lb[0] = 0; blab(lb, lab); bchr(lb, ':'); code_line(lb); }

/* ---- symbols and types (y1cc.py vinfo, struct_member, typeof...) ------------------------------------------------ */
int local_var(int name) {                           /* the current function's variable of that name, or 0 */
    int i;
    for (i = 0; i < cur_vn; i++) if (v_name[cur_vfirst + i] == name) return cur_vfirst + i;
    return 0;
}
int vinfo(int name) {
    int v;
    v = local_var(name);
    if (v) return v;
    if (nm_glob[name]) return nm_glob[name];
    e_start("y1cc: undeclared identifier "); e_q(nm_text(name)); e_s(" (in "); e_s(nm_text(f_name[cur_fn]));
    e_s(")"); e_go();
    return 0;
}
void var_label(int v, char *buf) { buf[0] = 0; bcat(buf, lpool + v_lab[v]); }
int v_size(int v) {                                 /* bytes the variable occupies */
    if (v_cnt[v]) return v_cnt[v] * size_of(v_base[v], v_ptr[v]);
    if (v_ptr[v] == 0 && nm_st[v_base[v]]) return s_size[nm_st[v_base[v]]];
    if (v_slot[v]) return 2;
    return size_of(v_base[v], v_ptr[v]);
}
void struct_member(int tag, int mname) {            /* -> sm_off, sm_base, sm_ptr, sm_cnt */
    int s; int i; int m;
    s = tag ? nm_st[tag] : 0;
    if (!s) { e_start("y1cc: not a struct/union: "); e_q(tag ? nm_text(tag) : ""); e_go(); }
    m = 0;
    for (i = 0; i < s_mn[s]; i++) if (m_name[s_mfirst[s] + i] == mname) m = s_mfirst[s] + i;   /* the last wins */
    if (!m) { e_start("y1cc: "); e_q(nm_text(tag)); e_s(" has no member "); e_q(mname ? nm_text(mname) : ""); e_go(); }
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
void type_of(int e) {                               /* -> tb, tp: the type of e's VALUE (arrays decay) */
    int k; int v; int op; int lb_; int lp; int rb; int rp;
    k = nk[e];
    if (k == N_NUM) { tb = K_INT; tp = 0; return; }
    if (k == N_MEMBER || k == N_ARROW) {
        struct_member(member_tag(e), nb[e]);
        tb = sm_base; tp = sm_cnt ? sm_ptr + 1 : sm_ptr;
        return;
    }
    if (k == N_STR) { tb = K_CHAR; tp = 1; return; }
    if (k == N_ID) {
        v = vinfo(na[e]);
        tb = v_base[v]; tp = v_cnt[v] ? v_ptr[v] + 1 : v_ptr[v];
        return;
    }
    if (k == N_UNARY) {
        op = na[e];
        if (op == O_AMP) { type_lval(nb[e]); tp++; return; }
        if (op == O_STAR) { type_of(nb[e]); tp = dec_ptr(tp); return; }
        tb = K_INT; tp = 0; return;
    }
    if (k == N_INDEX) { type_of(na[e]); tp = dec_ptr(tp); return; }
    if (k == N_ASSIGN) { type_lval(na[e]); return; }
    if (k == N_PREINC || k == N_POSTINC) { type_lval(nb[e]); return; }
    if (k == N_COND) { type_of(nb[e]); return; }
    if (k == N_CALL) {
        if (builtin_type(na[e])) return;
        if (!nm_fn[na[e]]) { e_start("y1cc: call of undeclared function "); e_q(nm_text(na[e])); e_go(); }
        tb = f_rbase[nm_fn[na[e]]]; tp = f_rptr[nm_fn[na[e]]];
        return;
    }
    if (k == N_BIN) {
        op = na[e];
        if (op == O_PLUS || op == O_MINUS) {
            type_of(nb[e]); lb_ = tb; lp = tp;
            type_of(nc[e]); rb = tb; rp = tp;
            if (lp > 0) { tb = lb_; tp = lp; return; }
            if (rp > 0 && op == O_PLUS) { tb = rb; tp = rp; return; }
        }
        tb = K_INT; tp = 0; return;
    }
    tb = K_INT; tp = 0;
}
void type_lval(int e) {                             /* -> tb, tp: the type as an lvalue (no array decay) */
    int k; int v;
    k = nk[e];
    if (k == N_ID) { v = vinfo(na[e]); tb = v_base[v]; tp = v_ptr[v]; return; }
    if (k == N_UNARY && na[e] == O_STAR) {
        type_of(nb[e]);
        if (tp < 1) fail("y1cc: dereference of a non-pointer");
        tp--; return;
    }
    if (k == N_INDEX) {
        type_of(na[e]);
        if (tp < 1) fail("y1cc: index of a non-pointer");
        tp--; return;
    }
    if (k == N_MEMBER || k == N_ARROW) {
        struct_member(member_tag(e), nb[e]);
        tb = sm_base; tp = sm_ptr; return;
    }
    e_start("y1cc: not an lvalue: "); e_q(k <= N_BIN ? kindname[k] : "?"); e_go();
}
int is_char(int e) { type_of(e); return tb == K_CHAR && tp == 0; }

/* ---- static addresses: the assembler expression, in abuf ---------------------------------------------------------- */
void kadd(int off) { if (off) { bchr(abuf, '+'); bnum(abuf, off); } }
int static_addr(int e) {                            /* 1 when &e is a link-time constant (text in abuf) */
    int k; int i; int b; int bt; int bp;
    k = nk[e];
    if (k == N_ID) { var_label(vinfo(na[e]), abuf); return 1; }
    if (k == N_STR) { i = string_lab(na[e]); abuf[0] = 0; blab(abuf, i); return 1; }
    if (k == N_MEMBER) {
        if (!static_addr(na[e])) return 0;
        struct_member(member_tag(e), nb[e]);        /* (member_tag and struct_member leave abuf alone) */
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
        kadd(i * size_of(bt, dec_ptr(bp)));
        return 1;
    }
    return 0;
}
int is_array(int e) {                               /* e is an array object (not a pointer variable) */
    if (nk[e] == N_ID) return v_cnt[vinfo(na[e])] > 0;
    if (nk[e] == N_MEMBER || nk[e] == N_ARROW) { struct_member(member_tag(e), nb[e]); return sm_cnt > 0; }
    return 0;
}
int static_lval(int e) {                            /* a scalar lvalue at a constant address: 1, abuf/sl_* set */
    int v;
    if (nk[e] == N_ID) {
        v = vinfo(na[e]);
        if (v_cnt[v]) return 0;
        var_label(v, abuf); sl_base = v_base[v]; sl_ptr = v_ptr[v]; sl_slot = v_slot[v];
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

/* ---- narrow (8-bit) values ---------------------------------------------------------------------------------------- */
int is_narrow(int e) {                              /* e's value fits a byte and is available as one */
    int k; int n;
    k = nk[e];
    if (k == N_NUM) return na[e] <= 255;
    if (k == N_CALL) {
        n = na[e];
        if (n == B_GETCHAR || n == B_PEEK || n == B_INP || n == B_BIOS) return 1;
        return nm_fn[n] && f_rbase[nm_fn[n]] == K_CHAR && f_rptr[nm_fn[n]] == 0;
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
void byte_src(int e) {                              /* abuf = the operand of a static char byte */
    static_lval(e);
    if (sl_slot) kadd(1);
}
void gen_byte_acc(int e) {
    int k;
    k = nk[e];
    if (k == N_NUM) { insn("LDAI", na[e] & 255); return; }
    if (simple_byte(e)) { byte_src(e); inss("LDA", abuf); return; }
    if (k == N_UNARY && na[e] == O_STAR) { gen_expr(nb[e]); insr("LDAVR", 3); return; }
    if (k == N_INDEX || k == N_MEMBER || k == N_ARROW) { gen_address(e); insr("LDAVR", 3); return; }
    gen_expr(e); insr("MVRLA", 3);
}

/* ---- loads / stores of static variables (the address is in abuf) --------------------------------------------- */
void ldst(char *mn, int reg) {                      /* LDR/STR reg,abuf - LDZ/STZ reg,(abuf).0 for a page variable */
    int id;
    id = opt_xisa ? ul_find(abuf) : 0;
    if (id && ul_zp[id]) {
        L(mn[0] == 'L' ? "LDZ" : "STZ"); Lsp(); Lr(reg); bcat(lb, ",("); bcat(lb, abuf); bcat(lb, ").0"); Lend();
        return;
    }
    insrs(mn, reg, abuf);
}
void zreload(void) { if (zused) insrs("MVIW", 6, "zpage"); }   /* R6 = the page again after code that is not ours */
void load_static(int reg, int base, int ptr, int slot) {
    if (slot || size_of(base, ptr) == 2) { ldst("LDR", reg); return; }
    if (size_of(base, ptr) != 1) fail("y1cc: struct/union used as a value");
    inss("LDA", abuf); insr("MVARL", reg); insn("LDAI", 0); insr("MVARH", reg);
}
void store_static_r3(int base, int ptr, int slot, int narrow) {
    if (size_of(base, ptr) == 2) { ldst("STR", 3); return; }
    if (size_of(base, ptr) != 1) fail("y1cc: whole struct/array assignment not supported");
    if (slot) {
        if (!narrow) { insn("LDAI", 0); insr("MVARH", 3); }
        ldst("STR", 3);
    } else {
        insr("MVRLA", 3); inss("STA", abuf);
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
    int k; int i;
    k = nk[e];
    if (k == N_NUM) { insrn("MVIW", reg, na[e] & 65535); return; }
    if (k == N_STR) { i = string_lab(na[e]); insrl("MVIW", reg, i); return; }
    if (k == N_SIZEOFT || k == N_SIZEOFE) { insrn("MVIW", reg, sizeof_expr(e)); return; }
    if (k == N_UNARY) { static_addr(nb[e]); insrs("MVIW", reg, abuf); return; }
    if (is_array(e)) { static_addr(e); insrs("MVIW", reg, abuf); return; }
    if (!static_lval(e)) fail("y1cc: internal: leaf");
    load_static(reg, sl_base, sl_ptr, sl_slot);
}
int sizeof_expr(int e) {
    int x; int v;
    if (nk[e] == N_SIZEOFT) return size_of(na[e], nb[e]);
    x = na[e];
    if (nk[x] == N_ID) {
        v = vinfo(na[x]);
        if (v_cnt[v]) return v_cnt[v] * size_of(v_base[v], v_ptr[v]);
        return size_of(v_base[v], v_ptr[v]);
    }
    if (nk[x] == N_STR) return lit_len[na[x]] + 1;
    if (is_array(x)) { struct_member(member_tag(x), nb[x]); return sm_cnt * size_of(sm_base, sm_ptr); }
    type_of(x);
    return size_of(tb, tp);
}

/* ---- 16-bit operations on R3 ------------------------------------------------------------------------------------ */
void add_const(int k) {                             /* R3 += k (a number; masked) */
    int i;
    k = k & 65535;
    if (k == 0) return;
    if (k <= 3) { for (i = 0; i < k; i++) insr("INCR", 3); return; }
    if (k >= 65533) { for (i = 65535 - k + 1; i > 0; i--) insr("DECR", 3); return; }
    if (opt_xisa) { insrn("ADDIW", 3, k); return; }
    if ((k & 255) == 0) { insr("MVRHA", 3); insn("ADDI", k >> 8); insr("MVARH", 3); return; }
    insr("MVRLA", 3); insn("ADDI", k & 255); insr("MVARL", 3);
    insr("MVRHA", 3); insn("ADDIC", (k >> 8) & 255); insr("MVARH", 3);
}
void add_const_text(char *t) {                      /* R3 += a label expression */
    if (opt_xisa) { insrs("ADDIW", 3, t); return; }
    insr("MVRLA", 3); L("ADDI"); Lsp(); bchr(lb, '('); bcat(lb, t); bcat(lb, ").0"); Lend(); insr("MVARL", 3);
    insr("MVRHA", 3); L("ADDIC"); Lsp(); bchr(lb, '('); bcat(lb, t); bcat(lb, ").1"); Lend(); insr("MVARH", 3);
}
void add_r4(void) {                                 /* R3 += R4 (the monitor's do_add16 idiom) */
    insr("MVRLA", 4); ins0("MVAT"); insr("MVRLA", 3); ins0("ADDT"); insr("MVARL", 3);
    insr("MVRHA", 4); ins0("MVAT"); insr("MVRHA", 3); ins0("ADDTC"); insr("MVARH", 3);
}
char *logic_mn(int op) { if (op == O_AMP) return "ANDT"; if (op == O_BAR) return "ORT"; return "XORT"; }
char *logici_mn(int op) { if (op == O_AMP) return "ANDI"; if (op == O_BAR) return "ORI"; return "XORI"; }
void logic_r4(int op) {                             /* R3 = R3 op R4 */
    insr("MVRLA", 4); ins0("MVAT"); insr("MVRLA", 3); ins0(logic_mn(op)); insr("MVARL", 3);
    insr("MVRHA", 4); ins0("MVAT"); insr("MVRHA", 3); ins0(logic_mn(op)); insr("MVARH", 3);
}
void logic_const(int op, int k) {                   /* R3 = R3 op k */
    int lo; int hi; int ident;
    lo = k & 255; hi = (k >> 8) & 255;
    ident = op == O_AMP ? 255 : 0;                  /* the byte value that leaves a byte unchanged */
    if (lo != ident) { insr("MVRLA", 3); insn(logici_mn(op), lo); insr("MVARL", 3); }
    if (hi != ident) { insr("MVRHA", 3); insn(logici_mn(op), hi); insr("MVARH", 3); }
}
void shl1(void) {                                   /* R3 <<= 1 (R3 += R3) */
    if (opt_xisa) { insr("SHL16", 3); return; }
    insr("MVRLA", 3); ins0("MVAT"); ins0("ADDT"); insr("MVARL", 3);
    insr("MVRHA", 3); ins0("MVAT"); ins0("ADDTC"); insr("MVARH", 3);
}
void shr1(void) {                                   /* R3 >>= 1 (carry cleared, then rotate high and low through it) */
    insn("LDAI", 0); ins0("CSHL");
    insr("MVRHA", 3); ins0("CSHR"); insr("MVARH", 3);
    insr("MVRLA", 3); ins0("CSHR"); insr("MVARL", 3);
}
void scale_r3(int esz) {                            /* R3 *= esz (element size) */
    if (esz == 1) return;
    if (esz == 2) { shl1(); return; }
    if (esz == 4) { shl1(); shl1(); return; }
    insrn("MVIW", 4, esz); need(RT_MUL); inss("JSR", "rt_mul");
}

/* ---- addresses (lvalues): address in R3 ---------------------------------------------------------------------- */
void gen_address(int e) {
    int k; int b; int i; int bt; int bp; int esz; int ki;
    k = nk[e];
    if (static_addr(e)) { insrs("MVIW", 3, abuf); return; }
    if (k == N_UNARY && na[e] == O_STAR) { gen_expr(nb[e]); return; }
    if (k == N_MEMBER) {
        gen_address(na[e]); struct_member(member_tag(e), nb[e]); add_const(sm_off); return;
    }
    if (k == N_ARROW) {
        gen_expr(na[e]); struct_member(member_tag(e), nb[e]); add_const(sm_off); return;
    }
    if (k == N_INDEX) {
        b = na[e]; i = nb[e];
        type_of(b); bt = tb; bp = tp;
        esz = size_of(bt, dec_ptr(bp));
        if (fold(i)) {                              /* base + constant */
            ki = fv;
            gen_expr(b); add_const(mul16(ki, esz)); return;
        }
        gen_expr(i); scale_r3(esz);
        if (is_array(b) && static_addr(b)) { tbuf[0] = 0; bcat(tbuf, abuf); add_const_text(tbuf); return; }
        if (is_leaf(b)) { gen_leaf(4, b); add_r4(); return; }
        insr("PUSHR", 3); gen_expr(b); insr("POPR", 4); add_r4(); return;
    }
    e_start("y1cc: not an lvalue: "); e_q(k <= N_BIN ? kindname[k] : "?"); e_go();
}
void deref_r3(int base, int ptr) {                  /* R3 = *(R3) of type (base, ptr) */
    int sz;
    sz = size_of(base, ptr);
    if (sz == 2) {
        insr("LDAVR", 3); ins0("MVAT"); insr("INCR", 3); insr("LDAVR", 3);
        insr("MVARL", 3); ins0("MVTA"); insr("MVARH", 3);
    } else if (sz == 1) {
        insr("LDAVR", 3); insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3);
    } else fail("y1cc: struct/union used as a value");
}

/* ---- expressions: result in R3 ------------------------------------------------------------------------------------ */
void gen_expr(int e) {
    int k; int op; int v; int no; int end; int lv; int bt; int bp; int esz; int t;
    k = nk[e];
    if (k == N_NUM) { insrn("MVIW", 3, na[e] & 65535); return; }
    if (k == N_STR) { t = string_lab(na[e]); insrl("MVIW", 3, t); return; }
    if (k == N_SIZEOFT || k == N_SIZEOFE) { insrn("MVIW", 3, sizeof_expr(e)); return; }
    if (k == N_ID) {
        v = vinfo(na[e]);
        var_label(v, abuf);
        if (v_cnt[v]) insrs("MVIW", 3, abuf);       /* array -> its address */
        else load_static(3, v_base[v], v_ptr[v], v_slot[v]);
        return;
    }
    if (k == N_UNARY) {
        op = na[e];
        if (op == O_AMP) { gen_address(nb[e]); return; }
        if (op == O_STAR) { gen_expr(nb[e]); type_lval(e); deref_r3(tb, tp); return; }
        if (op == O_NOT) { materialize(e); return; }
        if (op == O_TILDE) { gen_expr(nb[e]); not_r3(); return; }
        if (fold(e)) { insrn("MVIW", 3, fv); return; }
        gen_expr(nb[e]); not_r3(); insr("INCR", 3);
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
        gen_cond(na[e], no, 0); gen_expr(nb[e]); insl("BR", end);
        label_def(no); gen_expr(nc[e]); label_def(end);
        return;
    }
    if (k == N_LOGAND || k == N_LOGOR) { materialize(e); return; }
    if (k == N_BIN) { gen_bin(e); return; }
    if (k == N_CALL) { gen_call(e); return; }
    if (k == N_PREINC) {
        gen_assign(nb[e], new_node(N_BIN, na[e] == O_INC ? O_PLUS : O_MINUS, nb[e], new_node(N_NUM, 1, 0, 0, 0), 0), 1);
        return;
    }
    if (k == N_POSTINC) {                           /* value = the OLD value; the variable gets old +- 1 */
        lv = nb[e];
        op = na[e] == O_INC ? O_PLUS : O_MINUS;
        if (static_lval(lv) && size_of(sl_base, sl_ptr) == 2) {   /* a word at a fixed address: old kept in R4 */
            gen_expr(lv); insrr("MOVRR", 3, 4);
            type_of(lv); bt = tb; bp = tp;
            esz = bp ? size_of(bt, dec_ptr(bp)) : 1;
            add_const(op == O_PLUS ? esz : 65535 - esz + 1);
            static_lval(lv);                        /* (gen_expr used abuf: the address again) */
            ldst("STR", 3); insrr("MOVRR", 4, 3);
        } else {
            gen_expr(lv); insr("PUSHR", 3);
            gen_assign(lv, new_node(N_BIN, op, lv, new_node(N_NUM, 1, 0, 0, 0), 0), 0);
            insr("POPR", 3);
        }
        return;
    }
    fail("y1cc: cannot generate expr");
}
void not_r3(void) {                                 /* R3 = ~R3 */
    insr("MVRLA", 3); ins0("INVA"); insr("MVARL", 3);
    insr("MVRHA", 3); ins0("INVA"); insr("MVARH", 3);
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
            gen_byte_acc(rhs); static_lval(lhs); inss("STA", abuf); return;
        }
        gen_expr(rhs);
        static_lval(lhs);
        store_static_r3(base, ptr, slot, narrow);
        if (want && sz == 1 && !narrow) { insn("LDAI", 0); insr("MVARH", 3); }   /* the value is the stored byte */
        return;
    }
    /* through a computed address: value in R3, address in R4 (or the other way round for a leaf value) */
    if (sz == 1 && simple_byte(rhs)) {              /* byte store: address -> R3, byte -> ACC */
        gen_address(lhs); gen_byte_acc(rhs); insr("STAVR", 3);
        if (want) { insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3); }
        return;
    }
    if (is_leaf(rhs)) {                             /* address in R3, value in R4 */
        gen_address(lhs); gen_leaf(4, rhs);
        if (sz == 2) {
            insr("MVRHA", 4); insr("STAVR", 3); insr("INCR", 3);
            insr("MVRLA", 4); insr("STAVR", 3);
        } else { insr("MVRLA", 4); insr("STAVR", 3); }
        if (want) insrr("MOVRR", 4, 3);
        return;
    }
    if (simple_address(lhs)) { gen_expr(rhs); load_address_r4(lhs); }   /* value in R3, address in R4 */
    else { gen_address(lhs); insr("PUSHR", 3); gen_expr(rhs); insr("POPR", 4); }
    if (sz == 2) {
        insr("MVRHA", 3); insr("STAVR", 4); insr("INCR", 4);
        insr("MVRLA", 3); insr("STAVR", 4);
    } else {
        insr("MVRLA", 3); insr("STAVR", 4);
        if (want && !narrow) { insn("LDAI", 0); insr("MVARH", 3); }
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
        gen_leaf(4, na[lhs]); struct_member(member_tag(lhs), nb[lhs]); off = sm_off;
    } else {
        type_of(na[lhs]); bt = tb; bp = tp;
        gen_leaf(4, na[lhs]);
        fold(nb[lhs]);
        off = mul16(fv, size_of(bt, dec_ptr(bp)));
    }
    off = off & 65535;
    if (off == 0) return;
    if (off <= 3) { for (i = 0; i < off; i++) insr("INCR", 4); return; }
    if (opt_xisa) { insrn("ADDIW", 4, off); return; }
    insr("MVRLA", 4); insn("ADDI", off & 255); insr("MVARL", 4);
    insr("MVRHA", 4); insn("ADDIC", off >> 8); insr("MVARH", 4);
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
    else if (is_leaf(a)) { gen_expr(b); insrr("MOVRR", 3, 4); gen_leaf(3, a); }
    else { gen_expr(b); insr("PUSHR", 3); gen_expr(a); insr("POPR", 4); }
}
void gen_bin(int e) {
    int op; int a; int b; int scale; int kb; int hkb; int ka; int hka; int lt; int lp; int esz; int t; int sh; int i;
    op = na[e]; a = nb[e]; b = nc[e];
    if (fold_bin(op, a, b)) { insrn("MVIW", 3, fv); return; }
    if (is_relop(op)) { materialize(e); return; }
    if (op == O_MINUS) {
        type_of(a); lt = tb; lp = tp;
        if (lp > 0) {
            type_of(b);
            if (tp > 0) {                           /* pointer - pointer = element count */
                esz = size_of(lt, lp - 1);
                operands(op, a, b); need(RT_SUB); inss("JSR", "rt_sub");
                if (esz == 2) shr1();
                else if (esz != 1) { insrn("MVIW", 4, esz); need(RT_DIVMOD); inss("JSR", "rt_divmod"); }
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
            add_const(op == O_PLUS ? t : 65535 - t + 1);
            return;
        }
        if (scale != 1) {                           /* pointer +- int: scale the int first */
            gen_expr(b); scale_r3(scale);
            if (op == O_PLUS) {
                if (is_leaf(a)) { gen_leaf(4, a); add_r4(); return; }
                insr("PUSHR", 3); gen_expr(a); insr("POPR", 4); add_r4(); return;
            }
            insrr("MOVRR", 3, 4);
            if (is_leaf(a)) gen_leaf(3, a);
            else { insr("PUSHR", 4); gen_expr(a); insr("POPR", 4); }
            need(RT_SUB); inss("JSR", "rt_sub"); return;
        }
        if (op == O_PLUS) {
            if (fold(a)) { ka = fv; gen_expr(b); add_const(ka); return; }
        }
        operands(op, a, b);
        if (op == O_PLUS) add_r4(); else { need(RT_SUB); inss("JSR", "rt_sub"); }
        return;
    }
    if (op == O_AMP || op == O_BAR || op == O_CARET) {
        if (hkb) { gen_expr(a); logic_const(op, kb); return; }
        if (fold(a)) { ka = fv; gen_expr(b); logic_const(op, ka); return; }
        operands(op, a, b); logic_r4(op); return;
    }
    if (op == O_STAR) {
        hka = fold(a); ka = fv;
        if (!hkb && hka) { t = a; a = b; b = t; kb = ka; hkb = 1; }
        if (hkb) {
            if (kb == 0) { gen_expr(a); insrn("MVIW", 3, 0); return; }
            if (kb == 1) { gen_expr(a); return; }
            if (kb == 2 || kb == 4 || kb == 8) {
                gen_expr(a);
                shl1();
                if (kb >= 4) shl1();
                if (kb == 8) shl1();
                return;
            }
            if (kb == 256) {
                gen_expr(a); insr("MVRLA", 3); insr("MVARH", 3); insn("LDAI", 0); insr("MVARL", 3); return;
            }
        }
        operands(op, a, b); need(RT_MUL); inss("JSR", "rt_mul"); return;
    }
    if (op == O_SLASH || op == O_PERCENT) {
        if (hkb && kb > 0 && (kb & (kb - 1)) == 0) {   /* power of two */
            sh = 0;
            for (t = kb; t > 1; t = t >> 1) sh++;
            gen_expr(a);
            if (op == O_PERCENT) { logic_const(O_AMP, kb - 1); return; }
            if (sh == 8) { insr("MVRHA", 3); insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3); return; }
            if (sh <= 3) { for (i = 0; i < sh; i++) shr1(); return; }
            insrn("MVIW", 4, sh); need(RT_SHR); inss("JSR", "rt_shr"); return;
        }
        operands(op, a, b); need(RT_DIVMOD); inss("JSR", "rt_divmod");
        if (op == O_PERCENT) insrr("MOVRR", 5, 3);
        return;
    }
    if (op == O_SHL || op == O_SHR) {
        if (hkb) {
            gen_expr(a);
            if (kb == 0) return;
            if (kb >= 16) { insrn("MVIW", 3, 0); return; }
            if (kb == 8) {
                if (op == O_SHL) { insr("MVRLA", 3); insr("MVARH", 3); insn("LDAI", 0); insr("MVARL", 3); }
                else { insr("MVRHA", 3); insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3); }
                return;
            }
            if (kb <= 3) { for (i = 0; i < kb; i++) { if (op == O_SHL) shl1(); else shr1(); } return; }
            insrn("MVIW", 4, kb);
        } else operands(op, a, b);
        if (op == O_SHL) { need(RT_SHL); inss("JSR", "rt_shl"); }
        else { need(RT_SHR); inss("JSR", "rt_shr"); }
        return;
    }
    fail("y1cc: operator not supported");
}

/* ---- conditions -------------------------------------------------------------------------------------------------- */
void materialize(int e) {                           /* a condition as a 0/1 VALUE in R3 */
    int t; int end;
    t = lbl(LK_T); end = lbl(LK_E);
    gen_cond(e, t, 1);
    insrn("MVIW", 3, 0); insl("BR", end);
    label_def(t); insrn("MVIW", 3, 1); label_def(end);
}
int neg_rel(int rel) {
    if (rel == O_LT) return O_GE;
    if (rel == O_GE) return O_LT;
    if (rel == O_GT) return O_LE;
    if (rel == O_LE) return O_GT;
    if (rel == O_EQ) return O_NE;
    return O_EQ;
}
void lo_load(int mode, int k) {                     /* the low bytes of a two-level compare: ACC = L.lo, TMP = R.lo */
    if (mode == 2) { insr("MVRLA", 4); ins0("MVAT"); insr("MVRLA", 3); }
    else { insr("MVRLA", 3); insn("LDTI", k & 255); }
}
/* After ACC = L.hi (or L for bytes) and TMP = R.hi: jump to label when L rel R. lomode 0: byte operands (one
   compare); 1: R is the constant lok; 2: R is in R4 (y1cc.py passes the low-byte loader as a lambda). */
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
void gen_relcond(int rel, int a, int b, int label, int when) {
    int hka; int ka; int hkb; int kb; int t;
    if (!when) rel = neg_rel(rel);
    hka = fold(a); ka = fv;
    hkb = fold(b); kb = fv;
    if (is_narrow(a) && is_narrow(b) && !(hka && hkb)) {   /* two bytes: one compare (ACC = a, TMP = b) */
        if (hkb) { gen_byte_acc(a); insn("LDTI", kb & 255); }
        else if (simple_byte(b)) { gen_byte_acc(a); byte_src(b); inss("LDT", abuf); }
        else if (simple_byte(a)) { gen_byte_acc(b); ins0("MVAT"); gen_byte_acc(a); }
        else { gen_byte_acc(a); ins0("PUSH"); gen_byte_acc(b); ins0("MVAT"); ins0("POP"); }
        branch_rel(rel, label, 0, 0);
        return;
    }
    /* 16 bits: L in R3, R in R4 or a constant; high bytes first, low bytes only when they are equal */
    if (!hkb && hka && (rel == O_EQ || rel == O_NE)) { t = a; a = b; b = t; kb = ka; hkb = 1; }
    if (hkb && kb == 0 && (rel == O_EQ || rel == O_NE)) {   /* x == 0 / x != 0: OR the bytes, one branch */
        gen_expr(a);
        insr("MVRLA", 3); ins0("MVAT"); insr("MVRHA", 3); ins0("ORT");
        insl(rel == O_EQ ? "BRZ" : "BRNZ", label);
        return;
    }
    if (hkb) {
        gen_expr(a);
        insr("MVRHA", 3); insn("LDTI", (kb >> 8) & 255);
        branch_rel(rel, label, 1, kb);
        return;
    }
    operands(rel, a, b);
    insr("MVRHA", 4); ins0("MVAT"); insr("MVRHA", 3);
    branch_rel(rel, label, 2, 0);
}
void gen_cond(int e, int label, int when) {         /* jump to label if (truth of e) == when, else fall through */
    int k; int f; int t; char *j;
    k = nk[e];
    if (fold(e)) { if ((fv != 0) == (when != 0)) insl("BR", label); return; }
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
    j = when ? "BRNZ" : "BRZ";
    if (is_narrow(e)) { gen_byte_acc(e); insl(j, label); return; }   /* a byte: load it and test */
    if (k == N_BIN && na[e] == O_AMP && fold(nc[e]) && fv <= 255) {  /* (x & mask8) */
        t = fv;
        gen_expr(nb[e]); insr("MVRLA", 3); insn("ANDI", t); insl(j, label); return;
    }
    gen_expr(e);
    insr("MVRLA", 3); ins0("MVAT"); insr("MVRHA", 3); ins0("ORT"); insl(j, label);
}

/* ---- the call graph ------------------------------------------------------------------------------------------------ */
int bit(int f, int g) { return (rbits[f * REACH_ROW + (g >> 3)] & (1 << (g & 7))) != 0; }
void set_bit(int f, int g) { rbits[f * REACH_ROW + (g >> 3)] = rbits[f * REACH_ROW + (g >> 3)] | (1 << (g & 7)); }
void walk_list(int n) { while (n) { walk(n); n = nx[n]; } }
void walk(int n) {                                  /* y1cc.py calls_in(), funcaddrs_in(), mentions() in one walker */
    int k; int c; int f; int i; int a;
    if (!n) return;
    k = nk[n];
    if (k == N_CALL) {
        c = na[n];
        f = nm_fn[c];
        if (wmode == W_DIRECT) { if (f && f_body[f]) set_bit(wfrom, f); }
        else if (wmode == W_ANYCALL) wfound = 1;
        else if (wmode == W_REACH) {
            if (c == wname || (f && f_body[f] && nm_fn[wname] && bit(f, nm_fn[wname]))) wfound = 1;
        } else if (wmode == W_FADDR && c == B_FUNCADDR) {
            a = nb[n];
            if (nc[n] != 1 || nk[a] != N_ID) fail("y1cc: funcaddr() wants the name of a function");
            f = nm_fn[na[a]];
            if (!f || !f_body[f]) { e_start("y1cc: funcaddr("); e_s(nm_text(na[a])); e_s("): no such function"); e_go(); }
            f_live[f] = 1; f_root[f] = 1;
        } else if (wmode == W_LIST) {
            if (f && f_body[f]) {
                for (i = 0; i < nwlist; i++) if (wlist[i] == f) f = 0;
                if (f) { wlist[nwlist] = f; nwlist++; }
            }
        }
        walk_list(nb[n]);
        return;
    }
    if (k == N_ID) {
        if (wmode == W_MENTION && na[n] == wname) wfound = 1;
        if (wmode == W_ZCOUNT) { c = local_var(na[n]); if (!c) c = nm_glob[na[n]]; if (c) v_zc[c]++; }
        return;
    }
    if (k == N_UNARY || k == N_PREINC || k == N_POSTINC) { walk(nb[n]); return; }
    if (k == N_SIZEOFE || k == N_MEMBER || k == N_ARROW || k == N_RETURN || k == N_EXPR) { walk(na[n]); return; }
    if (k == N_INDEX || k == N_ASSIGN || k == N_LOGOR || k == N_LOGAND || k == N_WHILE || k == N_SWITCH) {
        walk(na[n]); walk(nb[n]); return;
    }
    if (k == N_COND || k == N_IF) { walk(na[n]); walk(nb[n]); walk(nc[n]); return; }
    if (k == N_BIN) { walk(nb[n]); walk(nc[n]); return; }
    if (k == N_BLOCK) { walk_list(na[n]); return; }
    if (k == N_DECL) { walk(nc[n]); return; }
    if (k == N_FOR) { walk(na[n]); walk(nb[n]); walk(nc[n]); walk(nd[n]); return; }
}
int reaches(int callee, int n) {                    /* does evaluating n call something that can run callee? */
    wmode = W_REACH; wname = callee; wfound = 0; walk(n); return wfound;
}
int any_call(int n) { wmode = W_ANYCALL; wfound = 0; walk(n); return wfound; }
int mentions(int n, int name) { wmode = W_MENTION; wname = name; wfound = 0; walk(n); return wfound; }

/* ---- calls ------------------------------------------------------------------------------------------------------- */
int port(int e) {
    if (!fold(e) || fv > 15) fail("y1cc: port must be a constant 0..15");
    return fv;
}
int nth_arg(int e, int i) { int a; a = nb[e]; while (i && a) { a = nx[a]; i--; } return a; }
void gen_call(int e) {
    int name; int nargs; int a; int b; int c; int i; int n; int hn; int fn; int rec; int v; int hazard; int base;
    int later; int pn;
    name = na[e]; nargs = nc[e];
    if (name == B_PUTCHAR) {
        a = nth_arg(e, 0);
        if (is_narrow(a)) gen_byte_acc(a); else { gen_expr(a); insr("MVRLA", 3); }
        need(RT_PUTC); inss("JSR", "rt_putc"); return;
    }
    if (name == B_GETCHAR) {
        need(RT_GETC); inss("JSR", "rt_getc");
        insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3); return;
    }
    if (name == B_PUTS) {
        gen_expr(nth_arg(e, 0)); need(RT_PUTS); need(RT_PUTC); inss("JSR", "rt_puts"); return;
    }
    if (name == B_PEEK) { gen_expr(nth_arg(e, 0)); deref_r3(K_CHAR, 0); return; }
    if (name == B_PEEKW) { gen_expr(nth_arg(e, 0)); deref_r3(K_INT, 0); return; }
    if (name == B_POKE || name == B_POKEW) {        /* memory at addr = value (byte / big-endian word) */
        a = nth_arg(e, 0); b = nth_arg(e, 1);
        if (name == B_POKE && simple_byte(b)) { gen_expr(a); gen_byte_acc(b); insr("STAVR", 3); return; }
        if (is_leaf(a)) { gen_expr(b); gen_leaf(4, a); }
        else { gen_expr(a); insr("PUSHR", 3); gen_expr(b); insr("POPR", 4); }
        if (name == B_POKEW) { insr("MVRHA", 3); insr("STAVR", 4); insr("INCR", 4); }
        insr("MVRLA", 3); insr("STAVR", 4); return;
    }
    if (name == B_INP) {
        n = port(nth_arg(e, 0));
        L("INP"); Lsp(); bchr(lb, 'P'); bchr(lb, n < 10 ? '0' + n : 'A' + n - 10); Lend();
        insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3); return;
    }
    if (name == B_OUTP) {                           /* always OUTA: the emulator's console (port 2) ignores OUTI */
        b = nth_arg(e, 1);
        if (is_narrow(b)) gen_byte_acc(b); else { gen_expr(b); insr("MVRLA", 3); }
        n = port(nth_arg(e, 0));
        L("OUTA"); Lsp(); bchr(lb, 'P'); bchr(lb, n < 10 ? '0' + n : 'A' + n - 10); Lend();
        return;
    }
    if (name == B_HALT) { ins0("HALT"); return; }
    if (name == B_CALL) {                           /* call(addr): JSRUR to a computed address; R3 = what it returns */
        gen_expr(nth_arg(e, 0)); insrr("MOVRR", 3, 7); insr("JSRUR", 7); zreload(); return;
    }
    if (name == B_ARGSTR) { insrn("MVIW", 3, ARGBUF); return; }
    if (name == B_SYS) {                            /* sys(n, a, b, c): Y1/OS syscall n through SYSTAB */
        if (nargs < 1 || nargs > 4) fail("y1cc: sys() takes 1 to 4 arguments (the number, then up to three)");
        a = nth_arg(e, 0);
        hn = fold(a); n = fv;
        if (hn && n > SYSMAX) { e_start("y1cc: sys() number must be 0.."); e_n(SYSMAX); e_go(); }
        if (!hn) { gen_expr(a); shl1(); add_const(SYSTAB); insr("PUSHR", 3); }
        base = npark;
        i = 0;
        for (c = nx[a]; c; c = nx[c]) {            /* a later argument that calls anything could run a sys() itself */
            hazard = 0;
            for (later = nx[c]; later; later = nx[later]) if (!hazard && any_call(later)) hazard = 1;
            gen_expr(c);
            if (hazard) {
                insr("PUSHR", 3);
                if (npark >= PARK_MAX) fail("y1cc: too many parked arguments");
                park[npark] = i; npark++;
            } else insrn("STR", 3, SYSARG + 2 * i);
            i++;
        }
        while (npark > base) { npark--; insr("POPR", 4); insrn("STR", 4, SYSARG + 2 * park[npark]); }
        if (hn) insrn("LDR", 7, SYSTAB + 2 * n);
        else {
            insr("POPR", 3); insr("LDAVR", 3); ins0("MVAT"); insr("INCR", 3);
            insr("LDAVR", 3); insr("MVARL", 7); ins0("MVTA"); insr("MVARH", 7);
        }
        insr("JSRUR", 7); zreload(); insrn("LDR", 3, SYSRES); return;
    }
    if (name == B_FUNCADDR) {                       /* funcaddr(f): the address of function f, as an int */
        a = nth_arg(e, 0);
        if (nargs != 1 || nk[a] != N_ID || !nm_fn[na[a]] || !f_lab[nm_fn[na[a]]]) {
            e_start("y1cc: funcaddr() wants the name of a defined function (in "); e_s(nm_text(f_name[cur_fn]));
            e_s(")"); e_go();
        }
        insrs("MVIW", 3, lpool + f_lab[nm_fn[na[a]]]); return;
    }
    if (name == B_BIOS) {                           /* bios(addr, r7, acc) -> ACC */
        if (!fold(nth_arg(e, 0))) fail("y1cc: bios() address must be a constant");
        n = fv;
        gen_expr(nth_arg(e, 1)); insrr("MOVRR", 3, 7);
        c = nth_arg(e, 2);
        if (is_narrow(c)) gen_byte_acc(c); else { gen_expr(c); insr("MVRLA", 3); }
        insn("JSR", n); zreload(); insr("MVARL", 3); insn("LDAI", 0); insr("MVARH", 3); return;
    }
    fn = nm_fn[name];
    if (!fn) { e_start("y1cc: call of undeclared function "); e_q(nm_text(name)); e_go(); }
    if (nargs != f_np[fn]) {
        e_start("y1cc: "); e_s(nm_text(name)); e_s("() takes "); e_n(f_np[fn]); e_s(" argument(s), "); e_n(nargs);
        e_s(" given"); e_go();
    }
    if (!f_lab[fn]) { e_start("y1cc: "); e_s(nm_text(name)); e_s("() has no definition"); e_go(); }
    rec = f_body[fn] && bit(fn, cur_fn);            /* a call inside a recursive cycle (the callee can reach us) */
    if (rec) {
        for (a = nb[e]; a; a = nx[a]) {
            v = escapes(a);
            if (v) {
                e_start("y1cc: "); e_s(nm_text(f_name[cur_fn])); e_s("(): the address of local "); e_q(nm_text(v));
                e_s(" is passed to "); e_s(nm_text(name)); e_s("(), which can re-enter "); e_s(nm_text(f_name[cur_fn]));
                e_s("() (a recursive function's locals live in static slots): use a global"); e_go();
            }
        }
        frame_save(fn);
    }
    base = npark;
    i = 0;
    for (a = nb[e]; a; a = nx[a]) {
        v = f_vfirst[fn] + i;
        hazard = 0;
        for (later = nx[a]; later; later = nx[later]) if (!hazard && reaches(name, later)) hazard = 1;
        if (rec && fn == cur_fn && !hazard) {       /* a self-call: this store overwrites the caller's own parameter */
            pn = v_name[v];
            for (later = nx[a]; later; later = nx[later]) if (!hazard && mentions(later, pn)) hazard = 1;
        }
        gen_expr(a);
        if (v_slot[v] && !is_narrow(a)) { insn("LDAI", 0); insr("MVARH", 3); }
        if (hazard) {
            insr("PUSHR", 3);
            if (npark >= PARK_MAX) fail("y1cc: too many parked arguments");
            park[npark] = v; npark++;
        } else { abuf[0] = 0; bcat(abuf, lpool + v_lab[v]); ldst("STR", 3); }
        i++;
    }
    while (npark > base) { npark--; insr("POPR", 4); abuf[0] = 0; bcat(abuf, lpool + v_lab[park[npark]]); ldst("STR", 4); }
    inss("JSR", lpool + f_lab[fn]);
    if (rec) frame_restore(fn);
}

/* ---- recursion: save / restore a callee's static frame around a call inside its recursive cycle ----------------- */
int frame_bytes(int f) { int i; int n; n = 0; for (i = 0; i < f_vn[f]; i++) n = n + v_size(f_vfirst[f] + i); return n; }
void frame_save(int f) {                            /* push f's whole frame; R4 inline, or R5-R7 in rt_fsave */
    int n; int off; char *lab;
    n = frame_bytes(f);
    if (!n) return;
    lab = lpool + v_lab[f_vfirst[f]];
    if (n <= FRAME_INLINE) {
        for (off = 0; off + 1 < n; off = off + 2) {
            abuf[0] = 0; bcat(abuf, lab); kadd(off);
            if (v_zp[f_vfirst[f]]) { L("LDZ"); bcat(lb, " R4,("); bcat(lb, abuf); bcat(lb, ").0"); Lend(); }
            else insrs("LDR", 4, abuf);
            insr("PUSHR", 4);
        }
        if (n & 1) { abuf[0] = 0; bcat(abuf, lab); kadd(n - 1); inss("LDA", abuf); ins0("PUSH"); }
        return;
    }
    insrs("MVIW", 5, lab); insrn("MVIW", 6, n); need(RT_FSAVE); inss("JSR", "rt_fsave");
}
void frame_restore(int f) {                         /* pop f's frame back; R3 (the result) is not touched */
    int n; int off; char *lab;
    n = frame_bytes(f);
    if (!n) return;
    lab = lpool + v_lab[f_vfirst[f]];
    if (n <= FRAME_INLINE) {
        if (n & 1) { ins0("POP"); abuf[0] = 0; bcat(abuf, lab); kadd(n - 1); inss("STA", abuf); }
        off = n & 65534;
        while (off > 0) {
            off = off - 2;
            insr("POPR", 4); abuf[0] = 0; bcat(abuf, lab); kadd(off);
            if (v_zp[f_vfirst[f]]) { L("STZ"); bcat(lb, " R4,("); bcat(lb, abuf); bcat(lb, ").0"); Lend(); }
            else insrs("STR", 4, abuf);
        }
        return;
    }
    abuf[0] = 0; bcat(abuf, lab); kadd(n - 1);
    insrs("MVIW", 5, abuf); insrn("MVIW", 6, n); need(RT_FREST); inss("JSR", "rt_frest");
}
int local_root(int x) {                             /* the local whose storage the lvalue x lies in, or 0 */
    if (nk[x] == N_ID) return local_var(na[x]) ? na[x] : 0;
    if (nk[x] == N_MEMBER) return local_root(na[x]);
    if (nk[x] == N_INDEX && is_array(na[x])) return local_root(na[x]);
    return 0;
}
int escapes(int e) {                                /* a local whose ADDRESS the value of e may carry */
    int k; int r;
    k = nk[e];
    if (k == N_UNARY && na[e] == O_AMP) return local_root(nb[e]);
    if ((k == N_ID || k == N_MEMBER || k == N_INDEX) && is_array(e)) return local_root(e);
    if (k == N_BIN && (na[e] == O_PLUS || na[e] == O_MINUS)) { r = escapes(nb[e]); if (r) return r; return escapes(nc[e]); }
    if (k == N_COND) { r = escapes(nb[e]); if (r) return r; return escapes(nc[e]); }
    if (k == N_ASSIGN) return escapes(nb[e]);
    return 0;
}

/* ---- statements -------------------------------------------------------------------------------------------------- */
void gen_expr_stmt(int e) {
    if (nk[e] == N_ASSIGN) gen_assign(na[e], nb[e], 0);
    else if (nk[e] == N_PREINC || nk[e] == N_POSTINC)
        gen_assign(nb[e], new_node(N_BIN, na[e] == O_INC ? O_PLUS : O_MINUS, nb[e], new_node(N_NUM, 1, 0, 0, 0), 0), 0);
    else gen_expr(e);
}
void gen_stmt(int s) {
    int k; int m; int els; int end; int top; int cont; int i;
    k = nk[s];
    if (k == N_BLOCK) { for (m = na[s]; m; m = nx[m]) gen_stmt(m); return; }
    if (k == N_DECL) { if (nc[s]) gen_assign(new_node(N_ID, nb[s], 0, 0, 0), nc[s], 0); return; }
    if (k == N_EXPR) { gen_expr_stmt(na[s]); return; }
    if (k == N_EMPTY) return;
    if (k == N_RETURN) {
        if (na[s]) {
            gen_expr(na[s]);
            if (f_rbase[cur_fn] == K_CHAR && f_rptr[cur_fn] == 0 && !is_narrow(na[s])) { insn("LDAI", 0); insr("MVARH", 3); }
        }
        ins0("RET");
        return;
    }
    if (k == N_IF) {
        els = lbl(LK_ELSE); end = lbl(LK_END);
        gen_cond(na[s], nc[s] ? els : end, 0);
        gen_stmt(nb[s]);
        if (nc[s]) { insl("BR", end); label_def(els); gen_stmt(nc[s]); }
        label_def(end);
        return;
    }
    if (k == N_WHILE) {
        top = lbl(LK_TOP); end = lbl(LK_END);
        label_def(top); gen_cond(na[s], end, 0);
        if (lp_n >= LOOPS_MAX) fail("y1cc: loops nested too deep (LOOPS_MAX)");
        lp_brk[lp_n] = end; lp_cont[lp_n] = top; lp_n++;
        gen_stmt(nb[s]);
        lp_n--;
        insl("BR", top); label_def(end);
        return;
    }
    if (k == N_FOR) {
        top = lbl(LK_TOP); end = lbl(LK_END); cont = lbl(LK_NEXT);
        if (na[s]) gen_expr_stmt(na[s]);
        label_def(top);
        if (nb[s]) gen_cond(nb[s], end, 0);
        if (lp_n >= LOOPS_MAX) fail("y1cc: loops nested too deep (LOOPS_MAX)");
        lp_brk[lp_n] = end; lp_cont[lp_n] = cont; lp_n++;
        gen_stmt(nd[s]);
        lp_n--;
        label_def(cont);
        if (nc[s]) gen_expr_stmt(nc[s]);
        insl("BR", top); label_def(end);
        return;
    }
    if (k == N_BREAK) {
        if (!lp_n) fail("y1cc: break outside a loop or switch");
        insl("BR", lp_brk[lp_n - 1]);
        return;
    }
    if (k == N_CONTINUE) {
        i = lp_n;
        while (i > 0 && !lp_cont[i - 1]) i--;
        if (!i) fail("y1cc: continue outside a loop");
        insl("BR", lp_cont[i - 1]);
        return;
    }
    if (k == N_SWITCH) { gen_switch(na[s], nb[s]); return; }
    if (k == N_LABEL) { label_def(na[s]); return; }
    if (k == N_CASE || k == N_DEFAULT) fail("y1cc: case/default outside a switch (or nested inside a statement)");
    fail("y1cc: cannot generate stmt");
}

/* ---- switch: a BRUR jump table when it is smaller than the compare chain ----------------------------------------- */
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
    int end; int miss; int lo; int hi; int i; int byte_cases; int chain; int table; int narrow; int skip; int v;
    end = lbl(LK_SW);
    ncs = 0; sw_def = 0;
    relabel(na[body]);
    miss = sw_def ? sw_def : end;
    gen_expr(e);
    if (ncs) {
        lo = cs_val[0]; hi = cs_val[0];
        for (i = 1; i < ncs; i++) { if (cs_val[i] < lo) lo = cs_val[i]; if (cs_val[i] > hi) hi = cs_val[i]; }
        byte_cases = hi <= 255;
        narrow = is_narrow(e);
        if (byte_cases) chain = 3 + 5 * ncs + (narrow ? 0 : 4);
        else chain = 13 * ncs + 3;
        if (hi - lo > 30000) table = 65535; else table = 49 + 2 * (hi - lo + 1);
        if (opt_brur && table < chain) switch_table(lo, hi, miss);
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
    if (lp_n >= LOOPS_MAX) fail("y1cc: loops nested too deep (LOOPS_MAX)");
    lp_brk[lp_n] = end; lp_cont[lp_n] = 0; lp_n++;
    gen_stmt(body);
    lp_n--;
    label_def(end);
}
void switch_table(int lo, int hi, int miss) {       /* R3 - lo, range check, BRUR through a table of addresses */
    int tab; int n; int v; int i; int lab;
    tab = lbl(LK_T); n = hi - lo + 1;
    add_const(65535 - lo + 1);
    insr("MVRHA", 3); insn("LDTI", n >> 8);
    branch_rel(O_GE, miss, 1, n);
    shl1();
    tbuf[0] = 0; blab(tbuf, tab); add_const_text(tbuf);
    deref_r3(K_INT, 0);
    insr("BRUR", 3);
    db[0] = 0; blab(db, tab); bchr(db, ':'); data_line(db);
    for (v = lo; v <= hi; v++) {
        lab = miss;
        for (i = 0; i < ncs; i++) if (cs_val[i] == v) lab = cs_lab[i];
        db[0] = 0; bcat(db, "        DW "); blab(db, lab); data_line(db);
    }
}

/* ---- strings, data ---------------------------------------------------------------------------------------------- */
int string_lab(int lit) {                           /* y1cc.py string(): the label of a literal, emitted once */
    int lab; int i;
    if (lit_lab[lit]) return lit_lab[lit];
    lab = lbl(LK_STR); lit_lab[lit] = lab;
    db[0] = 0; bchr(db, 's'); bnum(db, lab); bchr(db, ':'); data_line(db);
    for (i = 0; i < lit_len[lit]; i++) db_byte(spool[lit_off[lit] + i] & 255);
    db_byte(0);
    db_end();
    return lab;
}
void collect_decls(int s, int fn) {                 /* every local (first declaration of a name wins) */
    int k; int m; int base; int ptr; int cnt; int name; int i; int dup;
    if (!s) return;
    k = nk[s];
    if (k == N_DECL) {
        name = nb[s];
        dup = 0;
        for (i = 0; i < f_vn[fn]; i++) if (v_name[f_vfirst[fn] + i] == name) dup = 1;
        if (dup) return;
        base = ty_b[na[s]]; ptr = ty_p[na[s]]; cnt = ty_c[na[s]];
        wbuf[0] = 0; bcat(wbuf, nm_text(f_name[fn])); bchr(wbuf, '_'); bcat(wbuf, nm_text(name));
        if (nvars + 1 >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
        nvars++;
        v_lab[nvars] = ulabel(wbuf); v_base[nvars] = base; v_ptr[nvars] = ptr; v_cnt[nvars] = cnt;
        v_slot[nvars] = ptr == 0 && base == K_CHAR && !cnt; v_name[nvars] = name;
        f_vn[fn]++;
        return;
    }
    if (k == N_BLOCK) { for (m = na[s]; m; m = nx[m]) collect_decls(m, fn); return; }
    if (k == N_IF) { collect_decls(nb[s], fn); collect_decls(nc[s], fn); return; }
    if (k == N_WHILE) { collect_decls(nb[s], fn); return; }
    if (k == N_FOR) { collect_decls(nd[s], fn); return; }
}
void layout_func(int fn) {                          /* fixed slots for the parameters and every local of a function */
    int d; int p; int base; int ptr; int name;
    d = f_body[fn];
    wbuf[0] = 0; bcat(wbuf, "f_"); bcat(wbuf, nm_text(f_name[fn]));
    f_lab[fn] = ulabel(wbuf);
    f_vfirst[fn] = nvars + 1; f_vn[fn] = 0; f_npar[fn] = 0;
    for (p = nc[d]; p; p = nx[p]) {
        base = ty_b[na[p]]; ptr = ty_p[na[p]]; name = nb[p];
        if (ptr == 0 && nm_st[base]) {
            e_start("y1cc: struct passed by value ("); e_s(nm_text(name)); e_s(") not supported"); e_go();
        }
        wbuf[0] = 0; bcat(wbuf, nm_text(f_name[fn])); bchr(wbuf, '_'); bcat(wbuf, nm_text(name));
        if (nvars + 1 >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
        nvars++;
        v_lab[nvars] = ulabel(wbuf); v_base[nvars] = base; v_ptr[nvars] = ptr; v_cnt[nvars] = 0;
        v_slot[nvars] = ptr == 0 && base == K_CHAR; v_name[nvars] = name;
        f_vn[fn]++; f_npar[fn]++;
    }
    collect_decls(nd[d], fn);
}
void compile_func(int fn) {
    int start; int i; int mark;
    cur_fn = fn; cur_vfirst = f_vfirst[fn]; cur_vn = f_vn[fn]; lp_n = 0;
    mark = nn;
    lbase = nl + 1;
    start = nraw;
    lb[0] = 0; bcat(lb, lpool + f_lab[fn]); bchr(lb, ':'); code_line(lb);
    if (f_root[fn]) zreload();                 /* --xisa: main and the funcaddr() entries set the page register */
    if (f_name[fn] == NM_MAIN) emit_bss_clear();
    gen_stmt(nd[f_body[fn]]);
    if (!last_ret) ins0("RET");
    for (i = 0; i < f_vn[fn]; i++) {
        if (v_zp[f_vfirst[fn] + i]) continue;       /* --xisa: the page's variables come at the end of the BSS */
        db[0] = 0; bcat(db, lpool + v_lab[f_vfirst[fn] + i]); bcat(db, ": DS "); bnum(db, v_size(f_vfirst[fn] + i));
        bss_line(db);
    }
    f_stat[fn] = nraw - start;
    corder[ncorder] = fn; ncorder++;
    nn = mark;                                      /* the nodes made while generating are not needed any more */
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
    wbuf[0] = 0; bcat(wbuf, "g_"); bcat(wbuf, nm_text(name));
    if (nvars + 1 >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
    nvars++;
    v_lab[nvars] = ulabel(wbuf); v_base[nvars] = base; v_ptr[nvars] = ptr; v_cnt[nvars] = arr ? count : 0;
    v_slot[nvars] = 0; v_name[nvars] = name;
    nm_glob[name] = nvars;
}
void emit_globals(void) {                           /* after every global has its label (initializers may point at any) */
    int g; int v;
    for (g = prog_first; g; g = nx[g]) {
        if (nk[g] != N_GVAR) continue;
        v = nm_glob[nb[g]];
        if (!nc[g]) {
            db[0] = 0; bcat(db, lpool + v_lab[v]); bcat(db, ": DS "); bnum(db, v_size(v));
            if (!opt_xisa) bss_line(db);            /* --xisa: written after the page plan (zpage_plan) */
            continue;
        }
        const_data(g, 0);                           /* y1cc.py makes the strings first, then the label and the lines */
        db[0] = 0; bcat(db, lpool + v_lab[v]); bchr(db, ':'); data_line(db);
        const_data(g, 1);
    }
}
void data_word_num(int v) { db[0] = 0; bcat(db, "        DW "); bnum(db, v & 65535); data_line(db); }
void data_word_lab(int lab) { db[0] = 0; bcat(db, "        DW "); blab(db, lab); data_line(db); }
void data_word_text(char *t) { db[0] = 0; bcat(db, "        DW "); bcat(db, t); data_line(db); }
int addr_of(int name) {
    if (!nm_glob[name]) { e_start("y1cc: initializer names unknown global "); e_q(nm_text(name)); e_go(); }
    return nm_glob[name];
}
void const_data(int g, int pass) {                  /* pass 0: make the strings; pass 1: the data lines */
    int t; int base; int ptr; int arr; int count; int init; int esz; int v; int i; int n; int it; int items; int lab;
    t = na[g]; base = ty_b[t]; ptr = ty_p[t]; init = nc[g]; arr = nd[g] & 1;
    v = nm_glob[nb[g]]; count = v_cnt[v];
    esz = size_of(base, ptr);
    if (!arr) {
        if (nk[init] == N_INITSTR) {
            if (ptr == 0) fail("y1cc: string initializer for a non-pointer");
            lab = string_lab(na[init]);
            if (pass) data_word_lab(lab);
        } else if (nk[init] == N_INITADDR) {
            if (!pass) return;
            if (esz != 2) fail("y1cc: address initializer for a non-pointer");
            data_word_text(lpool + v_lab[addr_of(na[init])]);
        } else if (nk[init] == N_INITNUM) {
            if (!pass) return;
            if (esz == 2) data_word_num(na[init]);
            else { db_byte(na[init]); db_end(); }
        } else if (pass) fail("y1cc: brace initializer for a scalar");
        return;
    }
    if (base == K_CHAR && ptr == 0 && nk[init] == N_INITSTR) {
        if (!pass) return;
        n = lit_len[na[init]];
        for (i = 0; i < count; i++) db_byte(i < n ? spool[lit_off[na[init]] + i] & 255 : 0);
        db_end();
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
                lab = string_lab(na[it]);
                if (pass) { db_end(); data_word_lab(lab); }
            } else if (pass) { db_end(); data_word_text(lpool + v_lab[addr_of(na[it])]); }
        } else if (nk[it] == N_INITNUM) {
            if (pass) { if (esz == 2) data_word_num(na[it]); else db_byte(na[it]); }
        } else fail("y1cc: nested brace initializer not supported");
    }
    if (!pass) return;
    db_end();
    n = mul16(count - items, esz);                  /* REAL zeros in the image: DS would leave RAM as it powers up */
    for (i = 0; i < n; i++) db_byte(0);
    db_end();
}
void register_struct(int d) {
    int s; int off; int size; int m; int sz; int t; int un; int k;
    un = na[d] == 2;
    if (nstructs + 1 >= STRUCTS_MAX) fail("y1cc: too many structs (STRUCTS_MAX)");
    nstructs++; s = nstructs;
    s_mfirst[s] = nmembers + 1; s_mn[s] = 0;
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

/* ---- the call graph: reachability (for recursion, dead functions and argument hazards) -------------------------- */
void build_reach(void) {
    int f; int g; int k; int i; int j; int t;
    for (f = 1; f <= nfuncs; f++) if (f_body[f]) { wmode = W_DIRECT; wfrom = f; walk(nd[f_body[f]]); }
    for (k = 1; k <= nfuncs; k++)                   /* Warshall: reach = the transitive closure of the direct calls */
        for (i = 1; i <= nfuncs; i++)
            if (bit(i, k)) for (j = 0; j < REACH_ROW; j++) rbits[i * REACH_ROW + j] = rbits[i * REACH_ROW + j] | rbits[k * REACH_ROW + j];
    f = nm_fn[NM_MAIN];
    if (bit(f, f)) {                                /* main cannot be part of a cycle */
        nwlist = 0; wmode = W_LIST; walk(nd[f_body[f]]);
        for (i = 0; i < nwlist; i++)                /* sorted by name, as y1cc.py prints them */
            for (j = i + 1; j < nwlist; j++)
                if (s_cmp(nm_text(f_name[wlist[j]]), nm_text(f_name[wlist[i]])) == 1) { t = wlist[i]; wlist[i] = wlist[j]; wlist[j] = t; }
        e_start("y1cc: main() can call itself (via ");
        k = 0;
        for (i = 0; i < nwlist; i++) {
            g = wlist[i];
            if (g == f || bit(g, f)) { if (k) e_s(", "); e_s(nm_text(f_name[g])); k = 1; }
        }
        e_s("): main cannot be recursive"); e_go();
    }
}
void gen_program(void) {
    int d; int f; int t; int p; int n; int r;
    for (d = prog_first; d; d = nx[d]) if (nk[d] == N_STRUCTDEF) register_struct(d);
    for (d = prog_first; d; d = nx[d]) {
        if (nk[d] != N_FUNC && nk[d] != N_PROTO) continue;
        f = nm_fn[nb[d]];
        if (!f) {
            if (nfuncs + 1 >= FUNCS_MAX) fail("y1cc: too many functions (FUNCS_MAX)");
            nfuncs++; f = nfuncs; f_name[f] = nb[d]; nm_fn[nb[d]] = f;
        }
        t = na[d]; f_rbase[f] = ty_b[t]; f_rptr[f] = ty_p[t];
        n = 0; for (p = nc[d]; p; p = nx[p]) n++;
        f_np[f] = n;
        if (nk[d] == N_FUNC) f_body[f] = d;
    }
    for (d = prog_first; d; d = nx[d]) if (nk[d] == N_GVAR) declare_global(d);
    emit_globals();
    f = nm_fn[NM_MAIN];
    if (!f || !f_body[f]) fail("y1cc: no main()");
    build_reach();
    f_live[f] = 1; f_root[f] = 1;                   /* roots: main and every function named in funcaddr() */
    for (r = 1; r <= nfuncs; r++) if (f_body[r]) { wmode = W_FADDR; walk(nd[f_body[r]]); }
    for (r = 1; r <= nfuncs; r++) if (f_live[r] && f_body[r]) for (t = 1; t <= nfuncs; t++) if (bit(r, t)) f_live[t] = 2;
    for (d = prog_first; d; d = nx[d]) if (nk[d] == N_FUNC && f_live[nm_fn[nb[d]]] && f_body[nm_fn[nb[d]]] == d) layout_func(nm_fn[nb[d]]);
    if (opt_xisa) {                                 /* the page first in the BSS (zpad precedes bss_start: not cleared) */
        zpage_plan();
        if (zused) { bss_line("zpage:"); zbss(1); }
        zbss(0);
    }
    io_date(tbuf);                                  /* the header */
    lb[0] = 0; bcat(lb, "; y1cc: ");
    r = 0; for (p = 0; srcpath[p]; p++) if (srcpath[p] == '/') r = p + 1;
    bcat(lb, srcpath + r); bcat(lb, "  ("); bcat(lb, tbuf); bchr(lb, ')'); code_line(lb);
    lb[0] = 0; bcat(lb, "; R3 = expression accumulator, R4 = operand, R5-R7 runtime scratch, R2 never used (hardware IR)");
    code_line(lb);
    insn("ORG", opt_org);
    if (opt_vector) {
        lb[0] = 0; bcat(lb, "        DW start                ; vector for the 2021 monitor's G command (BRVR = PC <- [org])");
        code_line(lb);
        lb[0] = 0; bcat(lb, "start:  JSR "); bcat(lb, lpool + f_lab[f]); code_line(lb);
        lb[0] = 0; bcat(lb, "        BR "); bnum(lb, MONITOR_RESTART); bcat(lb, "                 ; back to the monitor (restart)");
        code_line(lb);
    }
    compile_func(f);                                /* main first, then the other live functions in source order */
    for (d = prog_first; d; d = nx[d])
        if (nk[d] == N_FUNC && nb[d] != NM_MAIN && f_live[nm_fn[nb[d]]] && f_body[nm_fn[nb[d]]] == d) compile_func(nm_fn[nb[d]]);
    lbase = LBASE_NONE;
    for (d = prog_first; d; d = nx[d])
        if (nk[d] == N_FUNC && !f_live[nm_fn[nb[d]]]) {
            lb[0] = 0; bcat(lb, "; dropped (never called): "); bcat(lb, nm_text(nb[d])); code_line(lb);
        }
    pp_flush();
    emit_runtime();
    if (zused) data_line("zpad: DS (256-(zpad).0)&255");
    data_line("bss_start:");
    bss_line("bss_end: DS 1");                      /* a byte so the label is a real address even for an empty BSS */
    if (opt_boot) {
        bss_line("; boot stub for `emulator -x -f prog.img` / `y1ucemu -x -m -f prog.img`: release FORCE-ROM, stack, main, HALT");
        db[0] = 0; bcat(db, "        ORG "); bnum(db, 61440); bss_line(db);
        db[0] = 0; bcat(db, "        BR "); bnum(db, 61443); bss_line(db);
        db[0] = 0; bcat(db, "        MVIW R1,"); bnum(db, STACK_TOP); bss_line(db);
        db[0] = 0; bcat(db, "        JSR "); bcat(db, lpool + f_lab[f]); bss_line(db);
        bss_line("        HALT");
        db[0] = 0; bcat(db, "        END "); bnum(db, 61440); bss_line(db);
    } else {
        db[0] = 0; bcat(db, "        END "); bnum(db, opt_org); bss_line(db);
    }
}

/* ---- --xisa: the page (y1cc.py zpage_plan: the same candidates, weights and greedy order) ------------------------ */
int u_first[VARS_MAX];                              /* a candidate: its first variable, how many, the function if a */
int u_n[VARS_MAX];                                  /* whole recursive frame (else 0), size, weight, density, state */
int u_fn[VARS_MAX];
int u_size[VARS_MAX];
int u_w[VARS_MAX];
int u_d[VARS_MAX];
char u_done[VARS_MAX];
int nunits;
int zsz(int v) {                                    /* v_size, 0 for an unknown type (no error here) */
    if (v_ptr[v] == 0 && v_base[v] != K_INT && v_base[v] != K_CHAR && !(v_base[v] && nm_st[v_base[v]])) return 0;
    return v_size(v);
}
void z_unit(int first, int n, int fn) {
    int i; int size; int w;
    size = 0; w = 0;
    for (i = 0; i < n; i++) { size = size + zsz(first + i); w = (w + v_zc[first + i]) & 65535; }
    u_first[nunits] = first; u_n[nunits] = n; u_fn[nunits] = fn; u_size[nunits] = size; u_w[nunits] = w;
    u_d[nunits] = w / ((size + 1) / 2); u_done[nunits] = 0;
    nunits++;
}
void zpage_plan(void) {
    int d; int f; int i; int n; int v; int best; int used; int first; int bad;
    for (i = 0; i < 2; i++)                         /* the counts: main first, then source order (compile order) */
        for (d = prog_first; d; d = nx[d]) {
            if (nk[d] != N_FUNC) continue;
            f = nm_fn[nb[d]];
            if (!f_live[f] || f_body[f] != d || (i == 0) != (nb[d] == NM_MAIN)) continue;
            cur_vfirst = f_vfirst[f]; cur_vn = f_vn[f];
            wmode = W_ZCOUNT; walk(nd[d]);
        }
    nunits = 0;
    for (d = prog_first; d; d = nx[d])              /* the candidates, in BSS order: the uninitialised globals */
        if (nk[d] == N_GVAR && !nc[d]) { v = nm_glob[nb[d]]; if (zsz(v) == 2) z_unit(v, 1, 0); }
    for (i = 0; i < 2; i++)                         /* then the frames in compile order */
        for (d = prog_first; d; d = nx[d]) {
            if (nk[d] != N_FUNC) continue;
            f = nm_fn[nb[d]];
            if (!f_live[f] || f_body[f] != d || (i == 0) != (nb[d] == NM_MAIN)) continue;
            first = f_vfirst[f];
            if (bit(f, f)) {                        /* a recursive function: its whole frame, 1..256 bytes */
                n = 0; bad = 0;                     /* (a variable of unknown size keeps the frame out) */
                for (v = 0; v < f_vn[f] && n <= 256; v++) { n = n + zsz(first + v); if (!zsz(first + v)) bad = 1; }
                if (n > 0 && n <= 256 && !bad) z_unit(first, f_vn[f], f);
            } else
                for (v = 0; v < f_vn[f]; v++) if (zsz(first + v) == 2) z_unit(first + v, 1, 0);
        }
    used = 0;
    for (;;) {                                      /* the densest first (ties: the earlier), if it still fits */
        best = nunits;
        for (i = 0; i < nunits; i++)
            if (!u_done[i] && u_w[i] && (best == nunits || u_d[i] > u_d[best])) best = i;
        if (best == nunits) break;
        u_done[best] = 1;
        if (used + u_size[best] <= 256) {
            used = used + u_size[best];
            for (i = 0; i < u_n[best]; i++) {
                v = u_first[best] + i;
                v_zp[v] = 1; zused = 1;
                ul_zp[ul_find(lpool + v_lab[v])] = 1;
            }
        }
    }
}
void zbss(int page) {                               /* the DS lines of the globals (page 0) or of the page (page 1) */
    int d; int v; int i; int k; int f;
    for (d = prog_first; d; d = nx[d]) {
        if (nk[d] != N_GVAR || nc[d]) continue;
        v = nm_glob[nb[d]];
        if (v_zp[v] != page) continue;
        db[0] = 0; bcat(db, lpool + v_lab[v]); bcat(db, ": DS "); bnum(db, v_size(v)); bss_line(db);
    }
    if (!page) return;
    for (k = 0; k < 2; k++)                         /* the frames' page variables in compile order */
        for (d = prog_first; d; d = nx[d]) {
            if (nk[d] != N_FUNC) continue;
            f = nm_fn[nb[d]];
            if (!f_live[f] || f_body[f] != d || (k == 0) != (nb[d] == NM_MAIN)) continue;
            for (i = 0; i < f_vn[f]; i++) {
                v = f_vfirst[f] + i;
                if (!v_zp[v]) continue;
                db[0] = 0; bcat(db, lpool + v_lab[v]); bcat(db, ": DS "); bnum(db, v_size(v)); bss_line(db);
            }
        }
}

/* ---- the runtime (y1cc.py emit_runtime: the same text) ---------------------------------------------------------- */
void rt(char *t) { sec_line(0, t); }
void rtn(char *pre, int n) { db[0] = 0; bcat(db, pre); bnum(db, n); sec_line(0, db); }
void zrt(void) { if (zused) rt("        MVIW R6,zpage"); }
void emit_runtime(void) {
    int h;
    for (h = 0; h < RT_COUNT; h++) {
        if (!used[h]) continue;
        db[0] = 0; bcat(db, "; runtime "); bcat(db, rtname[h]); sec_line(0, db);
        if (h == RT_SUB) {
            rt("rt_sub: MVRHA R4"); rt("        INVA"); rt("        MVARH R4"); rt("        MVRLA R4"); rt("        INVA");
            rt("        MVAT"); rt("        LDAI 255"); rt("        ADDI 1");
            rt("        MVRLA R3"); rt("        ADDTC"); rt("        MVARL R3"); rt("        MVRHA R4"); rt("        MVAT");
            rt("        MVRHA R3"); rt("        ADDTC"); rt("        MVARH R3"); rt("        RET");
        } else if (h == RT_MUL && opt_xisa) {        /* --xisa: SHL16 where nothing reads the carry */
            rt("rt_mul: MVIW R5,0");
            rt("rt_mul_l: MVRLA R4"); rt("        MVAT"); rt("        MVRHA R4"); rt("        ORT"); rt("        BRZ rt_mul_d");
            rt("        MVRLA R4"); rt("        ANDI 1"); rt("        BRZ rt_mul_s");
            rt("        MVRLA R3"); rt("        MVAT"); rt("        MVRLA R5"); rt("        ADDT"); rt("        MVARL R5");
            rt("        MVRHA R3"); rt("        MVAT"); rt("        MVRHA R5"); rt("        ADDTC"); rt("        MVARH R5");
            rt("rt_mul_s: SHL16 R3");
            rt("        LDAI 0"); rt("        CSHL"); rt("        MVRHA R4"); rt("        CSHR"); rt("        MVARH R4");
            rt("        MVRLA R4"); rt("        CSHR"); rt("        MVARL R4"); rt("        BR rt_mul_l");
            rt("rt_mul_d: MOVRR R5,R3"); rt("        RET");
        } else if (h == RT_MUL) {
            rt("rt_mul: MVIW R5,0");
            rt("rt_mul_l: MVRLA R4"); rt("        MVAT"); rt("        MVRHA R4"); rt("        ORT"); rt("        BRZ rt_mul_d");
            rt("        MVRLA R4"); rt("        ANDI 1"); rt("        BRZ rt_mul_s");
            rt("        MVRLA R3"); rt("        MVAT"); rt("        MVRLA R5"); rt("        ADDT"); rt("        MVARL R5");
            rt("        MVRHA R3"); rt("        MVAT"); rt("        MVRHA R5"); rt("        ADDTC"); rt("        MVARH R5");
            rt("rt_mul_s: MVRLA R3"); rt("        MVAT"); rt("        ADDT"); rt("        MVARL R3");
            rt("        MVRHA R3"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARH R3");
            rt("        LDAI 0"); rt("        CSHL"); rt("        MVRHA R4"); rt("        CSHR"); rt("        MVARH R4");
            rt("        MVRLA R4"); rt("        CSHR"); rt("        MVARL R4"); rt("        BR rt_mul_l");
            rt("rt_mul_d: MOVRR R5,R3"); rt("        RET");
        } else if (h == RT_DIVMOD && opt_xisa) {     /* --xisa: the remainder in R5 (R6 is the page register) */
            rt("rt_divmod: MVIW R5,0"); rt("        MVIW R7,16");
            rt("rt_dm_l: MVRLA R3"); rt("        MVAT"); rt("        ADDT"); rt("        MVARL R3");
            rt("        MVRHA R3"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARH R3");
            rt("        MVRLA R5"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARL R5");
            rt("        MVRHA R5"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARH R5");
            rt("        MVRHA R4"); rt("        MVAT"); rt("        MVRHA R5");
            rt("        BRLT rt_dm_n"); rt("        BRNEQ rt_dm_y");
            rt("        MVRLA R4"); rt("        MVAT"); rt("        MVRLA R5"); rt("        BRLT rt_dm_n");
            rt("rt_dm_y: MVRLA R4"); rt("        MVAT"); rt("        MVRLA R5"); rt("        BRLT rt_dm_b");
            rt("        SUBT"); rt("        MVARL R5"); rt("        MVRHA R4"); rt("        MVAT"); rt("        MVRHA R5");
            rt("        SUBT"); rt("        MVARH R5"); rt("        INCR R3"); rt("        BR rt_dm_n");
            rt("rt_dm_b: SUBT"); rt("        MVARL R5"); rt("        MVRHA R4"); rt("        MVAT"); rt("        MVRHA R5");
            rt("        SUBT"); rt("        SUBI 1"); rt("        MVARH R5"); rt("        INCR R3");
            rt("rt_dm_n: DECR R7"); rt("        MVRLA R7"); rt("        BRNZ rt_dm_l");
            rt("        RET");
        } else if (h == RT_DIVMOD) {
            rt("rt_divmod: MVIW R6,0"); rt("        MVIW R7,16");
            rt("rt_dm_l: MVRLA R3"); rt("        MVAT"); rt("        ADDT"); rt("        MVARL R3");
            rt("        MVRHA R3"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARH R3");
            rt("        MVRLA R6"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARL R6");
            rt("        MVRHA R6"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARH R6");
            rt("        MVRHA R4"); rt("        MVAT"); rt("        MVRHA R6");
            rt("        BRLT rt_dm_n"); rt("        BRNEQ rt_dm_y");
            rt("        MVRLA R4"); rt("        MVAT"); rt("        MVRLA R6"); rt("        BRLT rt_dm_n");
            rt("rt_dm_y: MVRLA R4"); rt("        MVAT"); rt("        MVRLA R6"); rt("        BRLT rt_dm_b");
            rt("        SUBT"); rt("        MVARL R6"); rt("        MVRHA R4"); rt("        MVAT"); rt("        MVRHA R6");
            rt("        SUBT"); rt("        MVARH R6"); rt("        INCR R3"); rt("        BR rt_dm_n");
            rt("rt_dm_b: SUBT"); rt("        MVARL R6"); rt("        MVRHA R4"); rt("        MVAT"); rt("        MVRHA R6");
            rt("        SUBT"); rt("        SUBI 1"); rt("        MVARH R6"); rt("        INCR R3");
            rt("rt_dm_n: DECR R7"); rt("        MVRLA R7"); rt("        BRNZ rt_dm_l");
            rt("        MOVRR R6,R5"); rt("        RET");
        } else if (h == RT_SHL && opt_xisa) {
            rt("rt_shl: MVRLA R4"); rt("        BRZ rt_shl_d"); rt("rt_shl_l: SHL16 R3");
            rt("        DECR R4"); rt("        MVRLA R4"); rt("        BRNZ rt_shl_l"); rt("rt_shl_d: RET");
        } else if (h == RT_SHL) {
            rt("rt_shl: MVRLA R4"); rt("        BRZ rt_shl_d");
            rt("rt_shl_l: MVRLA R3"); rt("        MVAT"); rt("        ADDT"); rt("        MVARL R3");
            rt("        MVRHA R3"); rt("        MVAT"); rt("        ADDTC"); rt("        MVARH R3");
            rt("        DECR R4"); rt("        MVRLA R4"); rt("        BRNZ rt_shl_l"); rt("rt_shl_d: RET");
        } else if (h == RT_SHR) {
            rt("rt_shr: MVRLA R4"); rt("        BRZ rt_shr_d");
            rt("rt_shr_l: LDAI 0"); rt("        CSHL"); rt("        MVRHA R3"); rt("        CSHR"); rt("        MVARH R3");
            rt("        MVRLA R3"); rt("        CSHR"); rt("        MVARL R3");
            rt("        DECR R4"); rt("        MVRLA R4"); rt("        BRNZ rt_shr_l"); rt("rt_shr_d: RET");
        } else if (h == RT_PUTC) {
            if (opt_os) {
                rt("rt_putc: PUSHR R3"); rt("        PUSHR R4"); rt("        MVARL R3"); rt("        LDAI 0");
                rt("        MVARH R3"); rtn("        STR R3,", SYSARG); rtn("        LDR R7,", SYSTAB + 2 * SYS_CONOUT);
                rt("        JSRUR R7"); zrt(); rt("        POPR R4"); rt("        POPR R3"); rt("        RET");
            } else {
                rt("rt_putc: BRDEV rt_putc_h"); rt("        OUTA P2"); rt("        RET");
                rtn("rt_putc_h: JSR ", BIOS_CHAROUT); zrt(); rt("        RET");
            }
        } else if (h == RT_GETC) {
            if (opt_os) {
                rt("rt_getc: PUSHR R3"); rt("        PUSHR R4"); rtn("        LDR R7,", SYSTAB + 2 * SYS_CONIN);
                rt("        JSRUR R7"); zrt(); rtn("        LDR R5,", SYSRES); rt("        POPR R4"); rt("        POPR R3");
                rt("        MVRHA R5"); rt("        BRNZ rt_getc_e"); rt("        MVRLA R5"); rt("        RET");
                rt("rt_getc_e: LDAI 0"); rt("        RET");
            } else {
                rt("rt_getc: BRDEV rt_getc_h"); rt("        INP P2"); rt("        RET");
                rtn("rt_getc_h: JSR ", BIOS_UARTIN); zrt(); rt("        RET");
            }
        } else if (h == RT_PUTS) {
            rt("rt_puts: LDAVR R3"); rt("        BRZ rt_puts_d"); rt("        JSR rt_putc"); rt("        INCR R3");
            rt("        BR rt_puts"); rt("rt_puts_d: LDAI 10"); rt("        JSR rt_putc"); rt("        RET");
        } else if (h == RT_FSAVE) {
            rt("rt_fsave: POPR R7"); rt("rt_fsave_l: LDAVR R5"); rt("        PUSH"); rt("        INCR R5"); rt("        DECR R6");
            rt("        MVRLA R6"); rt("        MVAT"); rt("        MVRHA R6"); rt("        ORT"); rt("        BRNZ rt_fsave_l");
            zrt(); rt("        PUSHR R7"); rt("        RET");
        } else if (h == RT_FREST) {
            rt("rt_frest: POPR R7"); rt("rt_frest_l: POP"); rt("        STAVR R5"); rt("        DECR R5"); rt("        DECR R6");
            rt("        MVRLA R6"); rt("        MVAT"); rt("        MVRHA R6"); rt("        ORT"); rt("        BRNZ rt_frest_l");
            zrt(); rt("        PUSHR R7"); rt("        RET");
        }
    }
}

/* ---- the driver ---------------------------------------------------------------------------------------------------- */
void out_s(char *s) { while (*s) { io_out(*s & 255); s++; } }
void out_n(int n) { tbuf[0] = 0; bnum(tbuf, n); out_s(tbuf); }
int has_arg(char *w) {                              /* the index + 1 of the first command-line word w, or 0 */
    int i; int n;
    n = io_argc();
    for (i = 0; i < n; i++) { io_arg(i, argw, LINE_MAX); if (s_eq(argw, w)) return i + 1; }
    return 0;
}
void y1cc_main(void) {
    int i; int n; int ok; int dot; int sep;
    for (i = 1; i <= NM_PREDEF; i++) intern(predef[i]);
    lpn = 1;                                        /* label offset 0 means "none" (f_lab) */
    n = io_argc();
    if (n > 0) io_arg(0, srcpath, LINE_MAX);
    if (n == 0 || srcpath[0] == '-')
        fail("usage: y1cc prog.c [-o prog.asm] [--org 0x3000] [--boot] [--vector] [--no-brur] [--os] [--xisa] [-l]");
    sep = 0; dot = 0;                               /* os.path.splitext: the extension of the last path element */
    for (i = 0; srcpath[i]; i++) { if (srcpath[i] == '/') sep = i + 1; }
    for (i = sep; srcpath[i]; i++) if (srcpath[i] == '.') dot = i;
    if (dot) { for (i = sep; i < dot && srcpath[i] == '.'; i++) {} if (i == dot) dot = 0; }
    outpath[0] = 0;
    if (dot) { for (i = 0; i < dot; i++) outpath[i] = srcpath[i]; outpath[dot] = 0; } else bcat(outpath, srcpath);
    bcat(outpath, ".asm");
    i = has_arg("-o");
    if (i) { if (i >= n) fail("y1cc: -o needs a file name"); io_arg(i, outpath, LINE_MAX); }
    opt_org = ORG_DEFAULT;
    i = has_arg("--org");
    if (i) {
        if (i >= n) fail("y1cc: --org needs an address");
        io_arg(i, argw, LINE_MAX);
        opt_org = parse_int0(argw, &ok);
        if (!ok) fail("y1cc: --org: not a number");
    }
    opt_boot = has_arg("--boot") != 0;
    opt_vector = has_arg("--vector") != 0;
    opt_brur = has_arg("--no-brur") == 0;
    opt_os = has_arg("--os") != 0;
    opt_list = has_arg("-l") != 0;
    opt_xisa = has_arg("--xisa") != 0;
    lbase = LBASE_NONE;
    lx_push(srcpath);
    program();
    if (!io_create(outpath)) { e_start("y1cc: cannot write "); e_s(outpath); e_go(); }
    gen_program();
    if (!io_finish()) { e_start("y1cc: cannot write "); e_s(outpath); e_go(); }
    if (opt_list) {
        out_s("y1cc: "); out_s(srcpath); out_s(" -> "); out_s(outpath); out_s(": "); out_n(nlines);
        out_s(" lines; functions: ");
        for (i = 0; i < ncorder; i++) {
            if (i) out_s(", ");
            out_s(nm_text(f_name[corder[i]])); out_s(" "); out_n(f_stat[corder[i]]);
        }
        out_s("\n");
    }
}
