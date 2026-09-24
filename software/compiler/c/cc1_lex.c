/* cc1_lex.c - pass 1 of the multi-pass y1cc (2026-09-24): the command line, the preprocessor and the lexer.
   y1cc.c's y1cc_main (options) and lexer, unchanged in what they accept and in their messages.

     cc1 W prog.c [-o prog.asm] [--org N] [--boot] [--vector] [--no-brur] [--os] [--xisa] [-l]

   Writes W.opt (the options for the later passes), W.tok (the token stream), W.nam (the names, id order) and W.lit
   (the string literals, id order). A lexer error stops the compile here: y1cc.py lexes the whole source before it
   parses, so its lexer errors come before any parse error (y1cc.c, which lexes as it parses, can report a parse
   error first: one of its documented differences, not this pass's).

   W.opt  src\0 out\0 org(2) flags(1)                         (flags: OPT_* in pdefs.h)
   W.tok  per token: kind(1) value(2); T_LINE(1) line(2) before a token on a new line; the last token is T_EOF
          (value 0)
   W.nam  count(2), then each name's text\0 (id 1 = "int": the predefined names first, then the identifiers in the
          order they first appear as tokens; a #define'd name is not one)
   W.lit  count(2), then each literal: length(2) bytes (distinct literals, id order) */
#include "pcommon.c"

char *optext[] = {"", "<<=", ">>=", "==", "!=", "<=", ">=", "<<", ">>", "&&", "||", "->", "++", "--",
                  "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "{", "}", "(", ")", "[", "]", ";", ",", "=",
                  ".", "?", ":", "+", "-", "*", "/", "%", "<", ">", "!", "&", "|", "^", "~"};
char *predef[] = {"", "int", "char", "void", "struct", "union", "unsigned", "const", "static", "if", "else",
                  "while", "for", "return", "break", "continue", "sizeof", "switch", "case", "default", "main",
                  "getchar", "peek", "peekw", "inp", "bios", "putchar", "puts", "poke", "pokew", "outp", "halt",
                  "call", "argstr", "sys", "funcaddr"};

/* names, interned: id 1.. */
char npool[NAMEPOOL];
int npn;
int nm_off[NAMES_MAX];
int nm_next[NAMES_MAX];
int nm_hash[HASH_SIZE];
int nnames;
char nm_mac[NAMES_MAX / 8 + 1]; /* bit id: a #define'd name */
int nm_macv[NAMES_MAX];          /* its value */
int nm_out[NAMES_MAX];           /* its id in W.nam, given when it is first written as a token: a macro name that
                                    never becomes a token costs the later passes nothing (0 = none yet) */
int nout;

/* string literals, interned: id 1.. */
char spool[STRPOOL];
int spn;
int lit_off[LITS_MAX];
int lit_len[LITS_MAX];
int lit_next[LITS_MAX];
int lit_hash[HASH_SIZE];
int nlits;

/* the stack of open files, each with a 4-byte lookahead */
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
char tbuf[LINE_MAX];
char wbuf[LINE_MAX];
char srcpath[LINE_MAX];
char outpath[LINE_MAX];
char argw[LINE_MAX];
int last_line;                  /* the line of the last token written */

int intern(char *s);
int lit_intern(char *buf, int n);
int parse_int0(char *s, int *ok);
int esc_val(int c);
int is_pyspace(int c);
void lx_push(char *path);
int lx_peek(int k);
void lx_adv(void);
void lx_err(char *msg);
void lx_err2(char *msg, char *arg);
void put_tok(int kind, int val, int line);
int lex_one(void);
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
int has_arg(char *w);
void write_tables(void);

void pass_fail(char *msg) { io_fail(msg); }

int is_pyspace(int c) { return c == ' ' || (c >= 9 && c <= 13) || (c >= 28 && c <= 31); }  /* str.split() */

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

/* ---- the lexer (y1cc.c) --------------------------------------------------------------------------------------- */
void lx_push(char *path) {
    int h; int i;
    h = io_open(path);
    if (!h) { e_start("y1cc: cannot open "); e_s(path); e_go(); }
    if (fdep || f_h[0]) {
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
    if (line != last_line) { wb(T_LINE); wi(line); last_line = line; }
    wb(kind); wi(val);
}
int lex_one(void) {                                 /* one token; 0 at the end of the source */
    int c; int c1;
    for (;;) {
        c = lx_peek(0);
        if (c == 256) {
            if (fdep > 0) { io_close(f_h[fdep]); fdep--; continue; }
            put_tok(T_EOF, 0, f_line[0]); return 0;
        }
        if (c == 10) { f_line[fdep]++; lx_adv(); continue; }
        if (c == ' ' || c == 9 || c == 13 || c == 12) { lx_adv(); continue; }
        if (c == '#') { lx_directive(); continue; }
        c1 = lx_peek(1);
        if (c == '/' && c1 == '/') { lx_linecomment(); continue; }
        if (c == '/' && c1 == '*') { lx_blockcomment(); continue; }
        if (is_alpha(c) || c == '_') { lx_ident(); return 1; }
        if (is_digit(c)) { lx_number(); return 1; }
        if (c == 39) { lx_char(); return 1; }
        if (c == '"') { lx_string(); return 1; }
        lx_punct(); return 1;
    }
    return 0;
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
        nm_mac[id >> 3] = nm_mac[id >> 3] | (1 << (id & 7)); nm_macv[id] = v;
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
    nm_mac[k >> 3] = nm_mac[k >> 3] | (1 << (k & 7)); nm_macv[k] = v;
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
    if (nm_mac[id >> 3] & (1 << (id & 7))) { put_tok(T_NUM, nm_macv[id], f_line[fdep]); return; }
    if (!nm_out[id]) { nout++; nm_out[id] = nout; }
    if (id <= KW_LAST) put_tok(T_KW, nm_out[id], f_line[fdep]);
    else put_tok(T_ID, nm_out[id], f_line[fdep]);
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

/* ---- the driver ------------------------------------------------------------------------------------------------- */
void write_tables(void) {                           /* W.nam (the names written as tokens, in their order) and W.lit */
    int i; int k;
    for (i = 1; i <= nnames; i++) nm_next[i] = 0;   /* (the hash chains are done with: the inverse of nm_out) */
    for (i = 1; i <= nnames; i++) if (nm_out[i]) nm_next[nm_out[i]] = i;
    wopen(".nam");
    wi(nout);
    for (i = 1; i <= nout; i++) ws(npool + nm_off[nm_next[i]]);
    wclose();
    wopen(".lit");
    wi(nlits);
    for (i = 1; i <= nlits; i++) {
        wi(lit_len[i]);
        for (k = 0; k < lit_len[i]; k++) wb(spool[lit_off[i] + k]);
    }
    wclose();
}
int has_arg(char *w) {                              /* the index + 1 of the first user word w, or 0 */
    int i; int n;
    n = io_argc();
    for (i = 1; i < n; i++) { io_arg(i, argw, LINE_MAX); if (s_eq(argw, w)) return i; }
    return 0;
}
void y1cc_main(void) {
    int i; int n; int ok; int dot; int sep; int org; int flags;
    p_args();
    for (i = 1; i <= NM_PREDEF; i++) { intern(predef[i]); nm_out[i] = i; }   /* their ids are fixed (pdefs.h) */
    nout = NM_PREDEF;
    n = io_argc() - 1;                              /* the user's words are 1..n (0 is the work prefix) */
    if (n > 0) io_arg(1, srcpath, LINE_MAX);
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
    if (i) { if (i >= n) fail("y1cc: -o needs a file name"); io_arg(i + 1, outpath, LINE_MAX); }
    org = ORG_DEFAULT;
    i = has_arg("--org");
    if (i) {
        if (i >= n) fail("y1cc: --org needs an address");
        io_arg(i + 1, argw, LINE_MAX);
        org = parse_int0(argw, &ok);
        if (!ok) fail("y1cc: --org: not a number");
    }
    flags = 0;
    if (has_arg("--boot")) flags = flags | OPT_BOOT;
    if (has_arg("--vector")) flags = flags | OPT_VECTOR;
    if (!has_arg("--no-brur")) flags = flags | OPT_BRUR;
    if (has_arg("--os")) flags = flags | OPT_OS;
    if (has_arg("-l")) flags = flags | OPT_LIST;
    if (has_arg("--xisa")) flags = flags | OPT_XISA;
    lx_push(srcpath);
    wopen(".opt");
    ws(srcpath); ws(outpath); wi(org); wb(flags);
    wclose();
    wopen(".tok");
    while (lex_one()) {}
    wclose();
    write_tables();
}
