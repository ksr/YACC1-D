/*
 * Author: Claude (Anthropic), 2026 - ported from Ken Rother's P8X project
 */

/* basic.c - BASIC under Y1/OS (2026-11-09): an interpreter of 16-bit integers and short strings, run from the shell.
     basic            the prompt; BYE or Ctrl-D returns to the shell
     basic FILE       LOAD FILE, then the prompt
     basic -r FILE    LOAD FILE, RUN it, then back to the shell
   A line with a number is stored, one without runs at once. Statements PRINT LET IF/THEN FOR/TO/STEP NEXT GOTO
   GOSUB RETURN INPUT POKE REM END; commands RUN LIST NEW SAVE LOAD HELP BYE; data files OPEN name FOR INPUT|OUTPUT,
   PRINT#, INPUT#, EOF(n), CLOSE; functions ABS RND PEEK LEN ASC VAL CHR$ LEFT$ RIGHT$ MID$ STR$ (man basic).
   SAVE writes the program as text, as LIST shows it (one line a record, LF at the end), so a saved program can be
   read with cat, edited with vi and LOADed back; LOAD reads such a file line by line as if it were typed.
   Ctrl-C stops a running program ("BREAK IN n"): the check reads a waiting key before each line and keeps any
   other key for the next INPUT or prompt, but cannot give it back to the shell, so a key typed while `basic -r` runs
   is lost when the program ends. Typed input is echoed, input from a < file or a pipe is not.
   Ported from P8X basic/basic.c 2026-11-09, changes: the graphics statements and functions (LINE COLOR BOX CIRCLE
   CLS PIXELW PIXELR GTEXT RGB IMAGE GL GLRD, the GL verbs, TEXTON..GRAPHICSOFF) are gone with the device they drove;
   the console and the files go through lib_fs.c (putchar/conin/constat, fopen/fgetc/fcreate/fputc/fclose); SAVE and
   LOAD use text instead of the token image; program lines are inserted and deleted in place (no second copy of the
   program), so all of the program area holds lines; GOSUB and FOR nest 8 deep (3 before); Ctrl-C breaks; the tables
   are this program's own arrays; the banner says how many bytes the program area holds. */
#include "../lib_fs.c"
#include "y1lib.c"

#define NAMLEN 6
#define NVARS 32
#define SLEN 32
#define SVENT 40
#define NSVARS 16
#define GSMAX 8
#define FSMAX 8
#define PROGSZ 12288
/* tokens */
#define T_PRINT 128
#define T_LET 129
#define T_IF 130
#define T_THEN 131
#define T_FOR 132
#define T_TO 133
#define T_NEXT 134
#define T_GOTO 135
#define T_GOSUB 136
#define T_RETURN 137
#define T_INPUT 138
#define T_REM 139
#define T_END 140
#define T_RUN 141
#define T_LIST 142
#define T_NEW 143
#define T_ABS 144
#define T_RND 145
#define T_PEEK 146
#define T_POKE 147
#define T_STEP 148
#define T_BYE 149
#define T_HELP 150
#define T_SAVE 151
#define T_LOAD 152
#define T_CHRS 153
#define T_LEFTS 154
#define T_RIGHTS 155
#define T_MIDS 156
#define T_LEN 157
#define T_ASC 158
#define T_OPEN 159
#define T_CLOSE 160
#define T_OUTPUT 161
#define T_STRS 162
#define T_VAL 163
#define T_EOF 164
/* relation bits */
#define R_LT 1
#define R_EQ 2
#define R_GT 4

/* the keywords, as words in two strings (y1cc's native passes refuse a 200-element initialiser, NODES_MAX, and a
   string literal over 160 characters): the n-th word of the two is token 128 + n, the order of the T_ numbers above */
char *kwtab[] = { "PRINT LET IF THEN FOR TO NEXT GOTO GOSUB RETURN INPUT REM END RUN LIST NEW ABS RND PEEK POKE",
                  "STEP BYE HELP SAVE LOAD CHR$ LEFT$ RIGHT$ MID$ LEN ASC OPEN CLOSE OUTPUT STR$ VAL EOF" };
int pow10[] = { 10000, 1000, 100, 10, 1 };

char lbuf[100];             /* the input line */
char nmbuf[6];              /* a parsed name, upcased, space-padded */
int gstk[16];               /* GOSUB frames: line record, text pointer */
int fstk[40];               /* FOR frames: var index, limit, step, line record, text */
char vtab[256];             /* NVARS entries: name[6] value[2] */
char svtab[640];            /* NSVARS entries: name[6] [len][SLEN chars] + 1 */
char sacc[40];              /* string work buffers: [len][chars] */
char stmp[40];
char sarg[40];
char scmpb[40];
char pbuf[52];              /* a path */
char prog[PROGSZ];          /* the program: records num[2] text NUL, then num 0 */
char *tp;                   /* the parse cursor */
char *vt;
char *svt;
char *curline;              /* RUN: the current line record */
char *jumpaddr;
char *strsp;                /* STR$ sink */
int err;                    /* an error unwound the statement */
int running;
int endf;
int branchf;
int branchn;
int jumpf;
int gsp;
int fsp;
int varcnt;
int svarcnt;
int fmode;                  /* data file: 0 closed, 1 input, 2 output */
int fh;                     /* its handle */
int outfile;                /* PRINT# routing */
int lsave;                  /* SAVE: LIST's output goes to this handle */
int strsink;
int strsn;
int flook;
int flookc;
int seed;
int relm;
int rel;
int lnum;                   /* the entered line number */
int redir;                  /* stdin is a file or a pipe: no echo */
int eofin;                  /* Ctrl-D / the end of the input */
int pend;                   /* a key read by brk() that was not Ctrl-C (+256), 0 = none */

int stmtline();
int stmt();
int eval();
int expr();
int seval(char *dst);
int sterm(char *dst);
int synerr();
int recnum(char *p);
int prdecu(int v);

/* ---- console ---- */
int outc(int c) { if (lsave) fputc(lsave, c); else putchar(c); return 0; }
int crlf() { outc(10); return 0; }
int outs(char *s) { while (*s) { outc(*s); s = s + 1; } return 0; }
int putch(int c) {
    if (strsink) { *strsp = c; strsp = strsp + 1; strsn = strsn + 1; }
    else if (outfile) fputc(fh, c);
    else putchar(c);
    return 0;
}
int getline() {                          /* a line into lbuf; eofin at Ctrl-D or the end of a < file */
    int n; int c;
    n = 0;
    while (1) {
        c = getkey();
        if (c == 65535) { if (n == 0) eofin = 1; lbuf[n] = 0; if (!redir) crlf(); return 0; }
        c = c & 255;
        if (c == 10 || c == 13) { lbuf[n] = 0; if (!redir) crlf(); return 0; }
        if (c == 8 || c == 127) {
            if (n) { n = n - 1; if (!redir) { putchar(8); putchar(32); putchar(8); } }
        } else if (c >= 32 && n < 98) { if (!redir) putchar(c); lbuf[n] = c; n = n + 1; }
    }
}
int brk() {                              /* Ctrl-C typed while a program runs? Another key is kept for the next input */
    int c;
    if (redir || pend) return 0;
    if (!constat()) return 0;
    c = conin();
    if ((c & 255) != 3) { pend = c | 256; return 0; }
    outs("BREAK IN "); prdecu(recnum(curline)); crlf();
    return 1;
}
int getkey() {                           /* conin(), after a key brk() kept */
    int c;
    if (pend) { c = pend & 255; pend = 0; return c; }
    return conin();
}

/* ---- characters ---- */
int isdig(int c) { return c >= '0' && c <= '9'; }
int upch(int c) { if (c >= 'a' && c <= 'z') return c - 32; return c; }
int isletter(int c) { c = upch(c); return c >= 'A' && c <= 'Z'; }
int isalnum(int c) { return isdig(c) || isletter(c); }
int sgn(int a) { return a ^ 32768; }             /* bias for a signed compare */
int skipsp() { while (*tp == ' ') tp = tp + 1; return 0; }

/* ---- numbers ---- */
int prdecu(int v) {
    int i; int d; int lz;
    lz = 1; i = 0;
    while (i < 5) {
        d = 0;
        while (v >= pow10[i]) { v = v - pow10[i]; d = d + 1; }
        if (d || i == 4 || lz == 0) { putch(d + 48); lz = 0; }
        i = i + 1;
    }
    return 0;
}
int prlnum(int v) {                      /* a line number through outc (LIST, SAVE) */
    int i; int d; int lz;
    lz = 1; i = 0;
    while (i < 5) {
        d = 0;
        while (v >= pow10[i]) { v = v - pow10[i]; d = d + 1; }
        if (d || i == 4 || lz == 0) { outc(d + 48); lz = 0; }
        i = i + 1;
    }
    return 0;
}
int prdec(int v) { if (v & 32768) { putch('-'); v = 0 - v; } return prdecu(v); }
int parsedec() { int v; int c; v = 0; c = *tp; while (c >= '0' && c <= '9') { v = v + v; v = v + (v << 2) + (c - '0'); tp = tp + 1; c = *tp; } return v; }
int hexval(int c) {
    if (isdig(c)) return c - '0';
    c = upch(c);
    if (c >= 'A' && c <= 'F') return c - 55;
    return 65535;
}
int parsehex() { int v; int d; v = 0; while (1) { d = hexval(*tp); if (d == 65535) return v; v = (v << 4) | d; tp = tp + 1; } }

/* ---- errors: set err; every level returns through it ---- */
int synerr() {
    if (err) return 0;
    err = 1; outfile = 0; strsink = 0;
    if (running) { outs("?SYNTAX ERROR IN "); prdecu(recnum(curline)); crlf(); }
    else outs("?SYNTAX ERROR\n");
    return 0;
}
int msgerr(char *m) { err = 1; outfile = 0; strsink = 0; outs(m); return 0; }
int expect(int c) { skipsp(); if (*tp != c) return synerr(); tp = tp + 1; return 0; }

/* ---- keywords ---- */
int kwlen;
int kwmatch(char *s) {                   /* a keyword at s? -> token, kwlen */
    char *t; int j; int tok; int k;
    tok = 128; k = 0;
    while (k < 2) {
        t = kwtab[k];
        while (*t) {
            j = 0;
            while (t[j] && t[j] != ' ' && upch(s[j]) == t[j]) j = j + 1;
            if ((t[j] == 0 || t[j] == ' ') && !isalnum(s[j])) { kwlen = j; return tok; }   /* not a longer name (TOTAL) */
            while (*t && *t != ' ') t = t + 1;
            if (*t) t = t + 1;
            tok = tok + 1;
        }
        k = k + 1;
    }
    return 0;
}
int crunch() {                           /* keywords -> tokens, lbuf in place */
    char *r; char *w; int t;
    r = lbuf; w = lbuf;
    while (*r) {
        if (*r == '"') {
            *w = *r; w = w + 1; r = r + 1;
            while (*r && *r != '"') { *w = *r; w = w + 1; r = r + 1; }
            if (*r) { *w = *r; w = w + 1; r = r + 1; }
        } else if (isletter(*r)) {
            t = kwmatch(r);
            if (t) { *w = t; w = w + 1; r = r + kwlen; }
            else { *w = *r; w = w + 1; r = r + 1; }
        } else { *w = *r; w = w + 1; r = r + 1; }
    }
    *w = 0;
    return 0;
}
int prkw(int tok) {                      /* print the keyword of a token */
    char *t; int k;
    tok = tok - 128; k = 0;
    while (k < 2) {
        t = kwtab[k];
        while (tok && *t) { if (*t == ' ') tok = tok - 1; t = t + 1; }
        if (*t) { while (*t && *t != ' ') { outc(*t); t = t + 1; } return 0; }
        tok = tok - 1;                   /* the last word of a string has no space after it */
        k = k + 1;
    }
    return 0;
}

/* ---- entry-time structural check ---- */
int cklead() {                           /* may the token at tp start a statement? 1 = REM, -1 = no */
    int c;
    c = *tp & 255;
    if (c == 0) return 0;
    if (c == T_REM) return 1;
    if (c & 128) {
        if (c == T_THEN || c == T_TO || c == T_STEP || c == T_OUTPUT) return 65535;
        if (c >= T_ABS && c <= T_PEEK) return 65535;       /* ABS RND PEEK */
        if (c >= T_CHRS && c <= T_ASC) return 65535;       /* CHR$ LEFT$ RIGHT$ MID$ LEN ASC */
        if (c >= T_STRS && c <= T_EOF) return 65535;       /* STR$ VAL EOF */
        return 0;
    }
    if (isletter(c)) return 0;
    return 65535;
}
int ckbad() { outs("?SYNTAX ERROR\n"); return 1; }
int checkline() {                        /* 1 = rejected */
    int dep; int r; int more;
    tp = lbuf; skipsp();
    while (isdig(*tp)) tp = tp + 1;
    while (1) {
        dep = 0; skipsp();
        r = cklead();
        if (r == 65535) return ckbad();
        if (r == 1) return 0;
        more = 0;
        while (more == 0) {
            if (*tp == 0) { if (dep) return ckbad(); return 0; }
            if (*tp == '"') {
                tp = tp + 1;
                while (*tp != '"') { if (*tp == 0) return ckbad(); tp = tp + 1; }
            } else if (*tp == '(') dep = dep + 1;
            else if (*tp == ')') { if (dep == 0) return ckbad(); dep = dep - 1; }
            else if (*tp == ':') { if (dep) return ckbad(); more = 1; }
            tp = tp + 1;
        }
    }
}

/* ---- variables: vt entries name[6] value[2] ---- */
int parsename() {                        /* nmbuf <- the identifier at tp; 0 if none */
    int i; int c;
    c = upch(*tp);
    if (c < 'A' || c > 'Z') return 0;
    i = 0;
    while (i < NAMLEN) { nmbuf[i] = ' '; i = i + 1; }
    i = 0;
    while ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z')) {
        if (i < NAMLEN) { nmbuf[i] = c; i = i + 1; }
        tp = tp + 1; c = upch(*tp);
    }
    return 1;
}
int nameeq(char *e) { int k; k = 0; while (k < NAMLEN) { if (e[k] != nmbuf[k]) return 0; k = k + 1; } return 1; }
int varfind() {                          /* nmbuf -> index (created if new) */
    int i; int k; char *e;
    i = 0; e = vt;
    while (i < varcnt) { if (nameeq(e)) return i; i = i + 1; e = e + 8; }
    if (varcnt >= NVARS) { msgerr("?TOO MANY VARIABLES\n"); return 0; }
    k = 0; while (k < NAMLEN) { e[k] = nmbuf[k]; k = k + 1; }
    e[6] = 0; e[7] = 0;
    varcnt = varcnt + 1;
    return i;
}
int varget() { if (!parsename()) return 65535; return varfind(); }
int vget(int i) { char *e; e = vt + (i << 3) + 6; return ((e[0] & 255) << 8) | (e[1] & 255); }
int vset(int i, int v) { char *e; e = vt + (i << 3) + 6; e[0] = v >> 8; e[1] = v; return 0; }
char *svaddr(int i) { return svt + (i << 5) + (i << 3) + 6; }
int svarfind() {
    int i; int k; char *e;
    i = 0; e = svt;
    while (i < svarcnt) { if (nameeq(e)) return i; i = i + 1; e = e + SVENT; }
    if (svarcnt >= NSVARS) { msgerr("?TOO MANY STRINGS\n"); return 0; }
    k = 0; while (k < NAMLEN) { e[k] = nmbuf[k]; k = k + 1; }
    e[6] = 0;
    svarcnt = svarcnt + 1;
    return i;
}
int svarget() {                          /* NAME$ -> index, 65535 if not a string variable */
    if (!parsename()) return 65535;
    if (*tp != '$') return 65535;
    tp = tp + 1;
    return svarfind();
}
int speek() {                            /* does tp begin a string expression? (tp kept) */
    char *q; int c;
    while (*tp == ' ') tp = tp + 1;
    c = *tp & 255;
    if (c == '"' || c == T_CHRS || c == T_LEFTS || c == T_RIGHTS || c == T_MIDS || c == T_STRS) return 1;
    c = upch(c);
    if (c < 'A' || c > 'Z') return 0;
    q = tp + 1; c = upch(*q);
    while ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z')) { q = q + 1; c = upch(*q); }
    return c == '$';
}

/* ---- strings: [len][data] ---- */
int smove(char *src, char *dst) { int n; n = (*src & 255) + 1; while (n) { *dst = *src; dst = dst + 1; src = src + 1; n = n - 1; } return 0; }
int sapp(char *src, char *dst) {         /* append src onto dst, capped at SLEN */
    int n; int m; char *s;
    m = *dst & 255; n = *src & 255; s = src + 1;
    while (n && m < SLEN) { dst[m + 1] = *s; s = s + 1; m = m + 1; n = n - 1; }
    *dst = m;
    return 0;
}
int scpylit(char *dst) {                 /* "..." at tp -> dst */
    int n;
    tp = tp + 1; n = 0;
    while (*tp && *tp != '"') { if (n < SLEN) { dst[n + 1] = *tp; n = n + 1; } tp = tp + 1; }
    if (*tp) tp = tp + 1;
    *dst = n;
    return 0;
}
int sput(char *s) { int n; n = *s & 255; s = s + 1; while (n) { putch(*s); s = s + 1; n = n - 1; } return 0; }
int sarg_(char *dst) {                   /* a literal or a string variable -> dst */
    int i;
    skipsp();
    if (*tp == '"') return scpylit(dst);
    i = svarget(); if (i == 65535) return synerr();
    return smove(svaddr(i), dst);
}
int clampn(int v) { if (v & 32768) return 0; if (v > 255) return SLEN; return v; }
int substr(int si, int sj) {             /* stmp = sarg[si..si+sj) clamped */
    int l; int k;
    l = *sarg & 255;
    if (si >= l) { *stmp = 0; return 0; }
    if (sj > l - si) sj = l - si;
    k = 0; while (k < sj) { stmp[k + 1] = sarg[si + k + 1]; k = k + 1; }
    *stmp = sj;
    return 0;
}
int stmopen() {                          /* '(' string ',' number ; returns the number */
    tp = tp + 1;
    expect('('); if (err) return 0;
    sarg_(sarg); if (err) return 0;
    expect(','); if (err) return 0;
    return expr();
}
int sterm(char *dst) {
    int c; int n; int i; int l;
    skipsp(); c = *tp & 255;
    if (c == '"') return scpylit(dst);
    if (c == T_CHRS) {
        tp = tp + 1; expect('('); n = expr(); expect(')');
        dst[0] = 1; dst[1] = n; return 0;
    }
    if (c == T_STRS) {
        tp = tp + 1; expect('('); n = expr(); expect(')');
        strsp = dst + 1; strsn = 0; strsink = 1; prdec(n); strsink = 0;
        dst[0] = strsn; return 0;
    }
    if (c == T_LEFTS) {
        n = stmopen(); if (err) return 0;
        substr(0, clampn(n)); expect(')'); return smove(stmp, dst);
    }
    if (c == T_RIGHTS) {
        n = stmopen(); if (err) return 0;
        n = clampn(n); l = *sarg & 255;
        if (n >= l) substr(0, n); else substr(l - n, n);
        expect(')'); return smove(stmp, dst);
    }
    if (c == T_MIDS) {
        n = stmopen(); if (err) return 0;
        if (n & 32768) i = 0; else if (n > 255) i = SLEN; else if (n == 0) i = 0; else i = n - 1;
        skipsp();
        if (*tp == ',') { tp = tp + 1; n = clampn(expr()); } else n = SLEN;
        substr(i, n); expect(')'); return smove(stmp, dst);
    }
    i = svarget(); if (i == 65535) return synerr();
    return smove(svaddr(i), dst);
}
int seval(char *dst) {                   /* term { + term } -> dst (via sacc when dst != sacc) */
    *sacc = 0;
    sterm(stmp); if (err) return 0; sapp(stmp, sacc);
    skipsp();
    while (*tp == '+') {
        tp = tp + 1;
        sterm(stmp); if (err) return 0; sapp(stmp, sacc);
        skipsp();
    }
    if (dst != sacc) smove(sacc, dst);
    return 0;
}
int scmp() {                             /* rel = scmpb vs sacc */
    int la; int lb; int n; int k; int a; int b;
    la = *scmpb & 255; lb = *sacc & 255;
    n = la; if (lb < la) n = lb;
    k = 1;
    while (n) {
        a = scmpb[k] & 255; b = sacc[k] & 255;
        if (a < b) { rel = R_LT; return 0; }
        if (a > b) { rel = R_GT; return 0; }
        k = k + 1; n = n - 1;
    }
    if (la == lb) rel = R_EQ; else if (la < lb) rel = R_LT; else rel = R_GT;
    return 0;
}

/* ---- expressions ---- */
int relopp() {                           /* an operator at tp -> relm (0 if none) */
    while (*tp == ' ') tp = tp + 1;
    if (*tp == '=') { tp = tp + 1; relm = R_EQ; return 1; }
    if (*tp == '<') {
        tp = tp + 1;
        if (*tp == '=') { tp = tp + 1; relm = R_LT + R_EQ; return 1; }
        if (*tp == '>') { tp = tp + 1; relm = R_LT + R_GT; return 1; }
        relm = R_LT; return 1;
    }
    if (*tp == '>') {
        tp = tp + 1;
        if (*tp == '=') { tp = tp + 1; relm = R_GT + R_EQ; return 1; }
        relm = R_GT; return 1;
    }
    return 0;
}
int parget() { int v; expect('('); if (err) return 0; v = expr(); expect(')'); return v; }
int random_() { seed = seed * 25173 + 13849; return seed; }
int factor() {
    int c; int v; int i; char *save; int neg;
    while (*tp == ' ') tp = tp + 1; c = *tp & 255;
    if (c == '-') { tp = tp + 1; return 0 - factor(); }
    if (c == '+') { tp = tp + 1; return factor(); }
    if (c == '(') { tp = tp + 1; v = expr(); expect(')'); return v; }
    if (c == T_ABS) { tp = tp + 1; v = parget(); if (v & 32768) return 0 - v; return v; }
    if (c == T_PEEK) { tp = tp + 1; return peek(parget()); }
    if (c == T_RND) {
        tp = tp + 1; v = parget();
        if (v == 0) return 0;
        return (random_() % v) + 1;
    }
    if (c == T_LEN) { tp = tp + 1; expect('('); sarg_(sarg); expect(')'); return *sarg & 255; }
    if (c == T_ASC) { tp = tp + 1; expect('('); sarg_(sarg); expect(')'); if (*sarg == 0) return 0; return sarg[1] & 255; }
    if (c == T_VAL) {
        tp = tp + 1; expect('('); sarg_(sarg); expect(')'); if (err) return 0;
        sarg[(*sarg & 255) + 1] = 0;
        save = tp; tp = sarg + 1; skipsp(); neg = 0;
        if (*tp == '-') { neg = 1; tp = tp + 1; } else if (*tp == '+') tp = tp + 1;
        v = parsedec(); tp = save;
        if (neg) return 0 - v;
        return v;
    }
    if (c == T_EOF) { tp = tp + 1; parget(); if (fmode != 1) return 1; return flookc; }
    if (c >= '0' && c <= '9') {
        if (c == '0' && (tp[1] == 'x' || tp[1] == 'X')) { tp = tp + 2; return parsehex(); }
        return parsedec();
    }
    if (c & 128) { synerr(); return 0; }
    i = varget();
    if (i == 65535) { synerr(); return 0; }
    return vget(i);
}
int term() {
    int v; int c; int r;
    v = factor();
    while (1) {
        while (*tp == ' ') tp = tp + 1; c = *tp;
        if (c == '*') { tp = tp + 1; v = v * factor(); }
        else if (c == '/') { tp = tp + 1; r = factor(); if (r == 0) v = 0; else v = v / r; }
        else if (c == '%') { tp = tp + 1; r = factor(); if (r == 0) v = 0; else v = v % r; }
        else return v;
        if (err) return 0;
    }
}
int expr() {
    int v; int c;
    v = term();
    while (1) {
        while (*tp == ' ') tp = tp + 1; c = *tp;
        if (c == '+') { tp = tp + 1; v = v + term(); }
        else if (c == '-') { tp = tp + 1; v = v - term(); }
        else return v;
        if (err) return 0;
    }
}
int relresult() { if (rel & relm) return 1; return 0; }
int evalstr() {                          /* a string comparison -> 1/0 */
    seval(scmpb); if (err) return 0;
    if (!relopp()) { synerr(); return 0; }
    seval(sacc); if (err) return 0;
    scmp();
    return relresult();
}
int eval() {                             /* expr [relop expr] -> value / 1 / 0 */
    int l; int r;
    if (speek()) return evalstr();
    l = expr(); if (err) return 0;
    if (!relopp()) return l;
    r = expr(); if (err) return 0;
    if (sgn(l) < sgn(r)) rel = R_LT; else if (l == r) rel = R_EQ; else rel = R_GT;
    return relresult();
}

/* ---- program text: records num[2] (big-endian) text NUL; the end is num 0 ---- */
int recnum(char *p) { return ((p[0] & 255) << 8) | (p[1] & 255); }
int setrec(char *p, int n) { p[0] = n >> 8; p[1] = n; return 0; }
char *nextrec(char *p) { p = p + 2; while (*p) p = p + 1; return p + 1; }
int newprog() { prog[0] = 0; prog[1] = 0; varcnt = 0; svarcnt = 0; return 0; }
char *progend() { char *p; p = prog; while (recnum(p)) p = nextrec(p); return p; }   /* the end record */
char *findline(int n) {                  /* the record numbered n, 0 if none */
    char *p; int r;
    p = prog;
    while (1) {
        r = recnum(p);
        if (r == 0 || r > n) return 0;
        if (r == n) return p;
        p = nextrec(p);
    }
}
int edit(char *text) {                   /* insert / replace / delete line lnum, in place */
    char *p; char *e; char *s; char *d; int r; int n; int k;
    if (lnum == 0) return msgerr("?BAD LINE NUMBER\n");
    p = prog; r = recnum(p);
    while (r && r < lnum) { p = nextrec(p); r = recnum(p); }
    if (r == lnum) {                     /* the old line goes: the rest moves down over it */
        s = nextrec(p); d = p; e = progend() + 2;
        while (s < e) { *d = *s; d = d + 1; s = s + 1; }
    }
    if (*text == 0) return 0;            /* a number alone deletes */
    n = 0; while (text[n]) n = n + 1;
    n = n + 3;                           /* num[2] text NUL */
    e = progend() + 2;
    if (e + n > prog + PROGSZ) return msgerr("?OUT OF MEMORY\n");
    s = e; d = e + n;                    /* the rest moves up to make room */
    while (s > p) { s = s - 1; d = d - 1; *d = *s; }
    setrec(p, lnum);
    k = 0; while (text[k]) { p[k + 2] = text[k]; k = k + 1; }
    p[k + 2] = 0;
    return 0;
}
int prtext(char *p) { int c; while (*p) { c = *p & 255; if (c & 128) prkw(c); else outc(c); p = p + 1; } return 0; }
int list() {
    char *p; int r;
    p = prog;
    while (1) {
        r = recnum(p);
        if (r == 0) return 0;
        prlnum(r); outc(' '); prtext(p + 2); crlf();
        p = nextrec(p);
    }
}

/* ---- files ---- */
int getpath() {                          /* a string expression -> pbuf (NUL-terminated); 1 = ok */
    int n;
    seval(sacc); if (err) return 0;
    n = *sacc & 255; if (n > 50) n = 50;
    pbuf[n] = 0;
    while (n) { pbuf[n - 1] = sacc[n]; n = n - 1; }
    if (pbuf[0] == 0) { synerr(); return 0; }
    return 1;
}
int fprime() { int c; c = fgetc(fh); if (c == 65535) flookc = 1; else { flookc = 0; flook = c & 255; } return 0; }
int gnb() {                              /* the next input byte via the lookahead, 65535 at EOF */
    int c;
    if (flookc) return 65535;
    c = flook;
    fprime();
    return c;
}
int freadrec() {                         /* one record (up to LF or CR) -> sacc, NUL-terminated */
    int n; int c;
    n = 0; c = 0;
    while (c != 65535 && c != 10 && c != 13) {
        c = gnb();
        if (c != 65535 && c != 10 && c != 13 && n < SLEN) { sacc[n + 1] = c; n = n + 1; }
    }
    if (c == 13 && flookc == 0 && flook == 10) gnb();   /* CR LF is one end of line */
    sacc[n + 1] = 0; *sacc = n;
    return 0;
}
int fileclose() { if (fmode) fclose(fh); fmode = 0; outfile = 0; return 0; }
int st_save() {
    int h;
    tp = tp + 1;
    if (!getpath()) return 0;
    h = fcreate(pbuf, 0, 0);
    if (h == 0) return msgerr("?CANNOT SAVE\n");
    lsave = h; list(); lsave = 0;
    if (!fclose(h)) return msgerr("?CANNOT SAVE\n");
    outs("Saved\n");
    return 0;
}
int loadfile(char *path) {               /* NEW, then each line of the file as if typed; 1 = done */
    int h; int c; int n; int bad;
    h = fopen(path);
    if (h == 0) { outs("?NO FILE\n"); return 0; }
    newprog(); bad = 0;
    while (1) {
        n = 0;
        c = fgetc(h);
        while (c != 65535 && c != 10 && c != 13) { if (n < 98) { lbuf[n] = c; n = n + 1; } c = fgetc(h); }
        lbuf[n] = 0;
        if (n) {
            crunch();
            err = 0;
            if (checkline()) bad = bad + 1;
            else {
                tp = lbuf; skipsp();
                if (isdig(*tp)) { lnum = parsedec(); skipsp(); edit(tp); if (err) bad = bad + 1; }
                else if (*tp) { outs("?NO LINE NUMBER: "); outs(lbuf); crlf(); bad = bad + 1; }
            }
        }
        if (c == 65535) { fclose(h); err = 0; if (bad) return 0; return 1; }
    }
}
int st_load() {
    tp = tp + 1;
    if (!getpath()) return 0;
    if (loadfile(pbuf)) outs("Loaded\n");
    endf = 1;                            /* the line it came from is gone */
    return 0;
}
int st_open() {
    int c;
    tp = tp + 1;
    if (!getpath()) return 0;
    fileclose();
    skipsp();
    if ((*tp & 255) == T_FOR) { tp = tp + 1; skipsp(); }
    c = *tp & 255;
    if (c == T_OUTPUT) {
        tp = tp + 1;
        fh = fcreate(pbuf, 0, 0);
        if (fh == 0) return msgerr("?CANNOT OPEN\n");
        fmode = 2; return 0;
    }
    if (c != T_INPUT) return synerr();
    tp = tp + 1;
    fh = fopen(pbuf);
    if (fh == 0) return msgerr("?NO FILE\n");
    fmode = 1;
    return fprime();
}

/* ---- statements ---- */
int st_print() {
    int v;
    tp = tp + 1; skipsp();
    if (*tp == '#') {
        if (fmode != 2) return synerr();
        tp = tp + 1; outfile = 1; skipsp();
        if (*tp == ',') { tp = tp + 1; skipsp(); }      /* PRINT# 1, X as well as PRINT# X */
        if (*tp) {
            if (speek()) { seval(sacc); if (err) return 0; sput(sacc); }
            else { v = eval(); if (err) return 0; prdec(v); }
        }
        fputc(fh, 10); outfile = 0;
        return 0;
    }
    while (1) {
        skipsp();
        if (*tp == 0 || *tp == ':') return crlf();
        if (speek()) { seval(sacc); if (err) return 0; sput(sacc); }
        else { v = eval(); if (err) return 0; prdec(v); }
        skipsp();
        if (*tp == ';') tp = tp + 1;
        else if (*tp == ',') { tp = tp + 1; putch(' '); }
        else return crlf();
        skipsp();
        if (*tp == 0 || *tp == ':') return 0;
    }
}
int st_let() {
    int i; int v;
    if ((*tp & 255) == T_LET) { tp = tp + 1; skipsp(); }
    if (speek()) {
        i = svarget(); if (i == 65535) return synerr();
        expect('='); if (err) return 0;
        seval(sacc); if (err) return 0;
        return smove(sacc, svaddr(i));
    }
    i = varget(); if (i == 65535) return synerr();
    expect('='); if (err) return 0;
    v = eval(); if (err) return 0;
    return vset(i, v);
}
int st_gotoN() { branchn = parsedec(); branchf = 1; return 0; }
int st_if() {
    int v;
    tp = tp + 1;
    v = eval(); if (err) return 0;
    skipsp();
    if ((*tp & 255) != T_THEN) return synerr();
    tp = tp + 1;
    if (v == 0) { while (*tp) tp = tp + 1; return 0; }
    skipsp();
    if (isdig(*tp)) return st_gotoN();
    return stmtline();
}
int st_input() {
    int i; char *save; int n; int neg;
    tp = tp + 1; skipsp();
    if (*tp == '#') {
        if (fmode != 1) return synerr();
        tp = tp + 1; skipsp();
        if (*tp == ',') { tp = tp + 1; skipsp(); }
        if (speek()) {
            i = svarget(); if (i == 65535) return synerr();
            save = tp; freadrec(); tp = save;
            return smove(sacc, svaddr(i));
        }
        i = varget(); if (i == 65535) return synerr();
        save = tp; freadrec(); tp = sacc + 1; skipsp();
        neg = 0; if (*tp == '-') { neg = 1; tp = tp + 1; }
        n = parsedec(); if (neg) n = 0 - n;
        tp = save;
        return vset(i, n);
    }
    if (*tp == '"') {                    /* INPUT "prompt"; X */
        scpylit(sacc); sput(sacc); skipsp();
        if (*tp == ';' || *tp == ',') tp = tp + 1;
        skipsp();
    }
    if (speek()) {
        i = svarget(); if (i == 65535) return synerr();
        save = tp; putchar('?'); putchar(' '); getline();
        n = 0; while (lbuf[n] && n < SLEN) { sacc[n + 1] = lbuf[n]; n = n + 1; }
        *sacc = n; tp = save;
        return smove(sacc, svaddr(i));
    }
    i = varget(); if (i == 65535) return synerr();
    save = tp; putchar('?'); putchar(' '); getline();
    tp = lbuf; skipsp();
    neg = 0; if (*tp == '-') { neg = 1; tp = tp + 1; }
    n = parsedec(); if (neg) n = 0 - n;
    tp = save;
    return vset(i, n);
}
int st_poke() { int a; tp = tp + 1; a = eval(); expect(','); if (err) return 0; poke(a, eval()); return 0; }
int st_gosub() {
    tp = tp + 1; skipsp(); st_gotoN(); skipsp();
    if (*tp == ':') tp = tp + 1;
    if (gsp >= GSMAX) return msgerr("?GOSUB TOO DEEP\n");
    gstk[gsp + gsp] = curline; gstk[gsp + gsp + 1] = tp;
    gsp = gsp + 1;
    return 0;
}
int st_return() {
    tp = tp + 1;
    if (gsp == 0) return msgerr("?RETURN WITHOUT GOSUB\n");
    gsp = gsp - 1;
    curline = gstk[gsp + gsp]; jumpaddr = gstk[gsp + gsp + 1]; jumpf = 2;
    return 0;
}
int st_for() {
    int i; int v; int lim; int step; char *lr; char *tpp; int k;
    tp = tp + 1; skipsp();
    i = varget(); if (i == 65535) return synerr();
    expect('='); if (err) return 0;
    v = eval(); if (err) return 0;
    vset(i, v);
    skipsp();
    if ((*tp & 255) != T_TO) return synerr();
    tp = tp + 1;
    lim = eval(); if (err) return 0;
    step = 1; skipsp();
    if ((*tp & 255) == T_STEP) { tp = tp + 1; step = eval(); if (err) return 0; }
    skipsp();
    if (!running) return msgerr("?FOR ONLY IN A PROGRAM\n");
    if (*tp == ':') { lr = curline; tpp = tp + 1; }
    else { lr = nextrec(curline); tpp = lr + 2; }
    if (fsp >= FSMAX) return msgerr("?FOR TOO DEEP\n");
    k = (fsp << 2) + fsp;
    fstk[k] = i; fstk[k + 1] = lim; fstk[k + 2] = step; fstk[k + 3] = lr; fstk[k + 4] = tpp;
    fsp = fsp + 1;
    return 0;
}
int st_next() {
    int k; int v; int fin;
    tp = tp + 1; skipsp();
    if (isletter(*tp)) varget();
    if (fsp == 0) return msgerr("?NEXT WITHOUT FOR\n");
    k = ((fsp - 1) << 2) + (fsp - 1);
    v = vget(fstk[k]) + fstk[k + 2]; vset(fstk[k], v);
    if (v == fstk[k + 1]) fin = 0;
    else if (sgn(v) < sgn(fstk[k + 1])) fin = (fstk[k + 2] & 32768);   /* below: a DOWN loop is done */
    else fin = ((fstk[k + 2] & 32768) == 0);                            /* above: an UP loop is done */
    if (fin) { fsp = fsp - 1; return 0; }
    curline = fstk[k + 3]; jumpaddr = fstk[k + 4]; jumpf = 2;
    return 0;
}
int st_run() {
    char *p; int go; int inner;
    tp = tp + 1;
    gsp = 0; fsp = 0; fileclose(); running = 1;
    curline = prog; go = 1;
    while (go) {
        if (recnum(curline) == 0) go = 0;
        else if (brk()) go = 0;
        else {
            tp = curline + 2; inner = 1;
            while (inner) {
                branchf = 0; jumpf = 0; endf = 0;
                stmtline();
                if (err || endf) { go = 0; inner = 0; }
                else if (jumpf == 2) tp = jumpaddr;
                else {
                    if (branchf) {
                        p = findline(branchn);
                        if (p == 0) { outs("?UNDEF'D LINE "); prdecu(branchn); outs(" IN "); prdecu(recnum(curline)); crlf(); go = 0; }
                        else curline = p;
                    } else curline = nextrec(curline);
                    inner = 0;
                }
            }
        }
    }
    if (endf == 2) { endf = 2; return 0; }   /* BYE in a program */
    fileclose();
    running = 0;
    endf = 1;
    if (!err) outs("Ok\n");
    return 0;
}
int st_help() {
    tp = tp + 1;
    outs("STATEMENTS: PRINT LET IF/THEN FOR/TO/STEP NEXT GOTO GOSUB RETURN\n");
    outs("  INPUT [\"prompt\";] POKE REM END   several on a line with :\n");
    outs("COMMANDS: RUN LIST NEW SAVE \"f\" LOAD \"f\" HELP BYE (or Ctrl-D)\n");
    outs("FILES: OPEN \"f\" FOR OUTPUT|INPUT  PRINT# x  INPUT# x  EOF(1)  CLOSE\n");
    outs("FUNCTIONS: ABS(x) RND(n) PEEK(a) LEN ASC VAL CHR$ LEFT$ RIGHT$ MID$ STR$\n");
    outs("NUMBERS: integers -32768..32767, 0x1F hex  OPERATORS: + - * / %\n");
    outs("  = <> < > <= >=   STRINGS: A$ (up to 32 chars), + joins\n");
    outs("Ctrl-C stops a running program. man basic for more.\n");
    return 0;
}
int stmt() {
    int c;
    skipsp(); c = *tp & 255;
    if (c == 0) return 0;
    if (c == T_LET || isletter(c)) return st_let();
    if (c == T_PRINT) return st_print();
    if (c == T_IF) return st_if();
    if (c == T_FOR) return st_for();
    if (c == T_NEXT) return st_next();
    if (c == T_GOTO) { tp = tp + 1; skipsp(); return st_gotoN(); }
    if (c == T_GOSUB) return st_gosub();
    if (c == T_RETURN) return st_return();
    if (c == T_REM) { while (*tp) tp = tp + 1; return 0; }
    if (c == T_END) { tp = tp + 1; endf = 1; return 0; }
    if (c == T_INPUT) return st_input();
    if (c == T_POKE) return st_poke();
    if (c == T_RUN) return st_run();
    if (c == T_LIST) { tp = tp + 1; list(); return 0; }
    if (c == T_NEW) { tp = tp + 1; newprog(); endf = 1; return 0; }
    if (c == T_HELP) return st_help();
    if (c == T_SAVE) return st_save();
    if (c == T_LOAD) return st_load();
    if (c == T_OPEN) return st_open();
    if (c == T_CLOSE) { tp = tp + 1; return fileclose(); }
    if (c == T_BYE) { endf = 2; return 0; }
    return synerr();
}
int stmtline() {
    while (1) {
        stmt();
        if (err || endf || branchf || jumpf) return 0;
        skipsp();
        if (*tp == 0) return 0;
        if (*tp != ':') return synerr();
        tp = tp + 1;
    }
}

void main() {
    char *a; int runit; char name[52];
    vt = vtab; svt = svtab;
    newprog();
    fmode = 0; outfile = 0; strsink = 0; lsave = 0; seed = 44257; eofin = 0;
    redir = stdio() & 1;
    runit = 0;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'r' || a[1] == 'R') && a[2] == ' ') { runit = 1; a = a + 2; }
    else if (a[0] == '-') { puts("usage: basic [file] | basic -r file   (BYE or Ctrl-D: back to the shell)"); return; }
    a = argword(a, name, 50);
    if (name[0]) {
        if (!loadfile(name)) { if (runit) return; }
        else if (runit) { lbuf[0] = T_RUN; lbuf[1] = 0; tp = lbuf; err = 0; endf = 0; stmtline(); fileclose(); return; }
    } else if (runit) { puts("usage: basic -r file"); return; }
    outs("Y1 BASIC  "); prdecu(PROGSZ - 2); outs(" bytes for the program\n");
    while (1) {
        running = 0; err = 0; endf = 0; branchf = 0; jumpf = 0;
        outs("> ");
        getline();
        if (eofin) { fileclose(); return; }
        crunch();
        if (checkline() == 0) {
            tp = lbuf; skipsp();
            if (isdig(*tp)) {
                lnum = parsedec(); skipsp();
                edit(tp);
            } else if (*tp) {
                stmtline();
                if (endf == 2) { fileclose(); return; }   /* BYE */
                if (!err && (branchf || jumpf)) outs("?ONLY IN A PROGRAM\n");   /* GOTO, GOSUB, RETURN, NEXT */
            }
        }
    }
}
