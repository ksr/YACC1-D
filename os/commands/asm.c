/* asm.c - the native YACC1 assembler, /BIN/ASM (2026-09-25): RC/asm's source dialect (software/assembler, the
   assembler y1cc's output and the firmware are written for) on the machine, and byte for byte what the host
   assembler makes of the same source.
     asm [-h] SRC [OUT]
       SRC   the source; a name without '.' gets ".ASM" (asm HELLO reads HELLO.ASM)
       OUT   a program file (the default: SRC without its extension): the bytes from the first address written to
             the last, gaps as zeros, load = that first address, exec = END's address (else the load address) -
             what `run` and the shell's NAME lookup take; the code must go up in address (no ORG back)
       -h    OUT is Intel hex instead (default: SRC's name + ".IMG"), the text the host's `asm SRC -d=yacc1` writes
             with -h: 16-byte records, a new record at every ORG and DS, the end record :00000001ff
   Errors go to the screen with the line number and the line ("asm: 12: undefined label: LOOP2"), and assembling
   goes on to the end of the pass; after any error OUT is deleted (an older file of that name too). The summary
   ("OUT: N bytes, N labels, load AAAA exec AAAA") goes to stdout.
   The instruction table is os/asm_optab.c, generated from software/assembler/yacc1.def by tools/gen_y1_optab.py.
   Copied from RC/asm (asm.c, asmcmds.c, support.c; the functions are named below), quirks included: lines read
   254 bytes at a time; upper-cased outside single quotes; the comment from the first ';' outside quotes; the label
   before the first ':' outside quotes (any text, 29 characters at most); the instruction matched against the
   .def patterns in their order (the first word literally, then \B a byte, \W a word, \L/\M a DB/DW list,
   {regs}/{ports} a class name as a prefix); expressions evaluated by RC/asm's token algorithm in 32 bits - '.0'/'.1'
   first, then '* /', then one leading '+'/'-' (whose minus RC/asm loses), then '+ -', then '&' and '!' (or), each
   level left to right, the innermost parentheses first; a label defined later is 1 in pass 1.
   Not supported (an error here): MACRO/ENDM, PUBLIC, EXTERN, LIB PROC/ENDP, INCLUDE more than two deep, '/' on
   values beyond 16 bits, an EQU value outside -65535..65535, a label or a byte past $FFFF. RC/asm stores those or
   carries on; nothing in the tree (y1cc's output, the firmware, the OS) uses them.
   Limits: the symbol table is POOL bytes, 5 + the name's length a label (the biggest compiler pass, cc8: 1,383
   labels in 16,925 bytes since 2026-09-25, when its buffered I/O added 57); 45 tokens an expression, 32
   characters a token; files up to 16M (Y1/OS positions are 24-bit since 2026-09-25; 16-bit, so 64K, before). OUT is written through Y1/OS's one write handle, so asm cannot run under a > redirect or in a pipe.
   Size (2026-09-25): 13,186 bytes of image + 19,569 of data (the pool 17,088) = 32,755 of the 32,768 of $5000-$CFFF
   (the pool was 16,640 until cc8 outgrew it the same day).
   Host build: tests/asm/host_asm.c compiles this file on the Mac against a Y1/OS syscall emulator (host_sys.c);
   tests/asm/run.py compares it with RC/asm over the tree's corpus. y1cc subset: no recursion, int unsigned. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "../asm_optab.c"

#define POOL 17088        /* symbol table bytes: what the 32K program area leaves, with a margin */
#define NHASH 256         /* its chain heads */
#define NT 48             /* expression token records (RC/asm has 1024) */

char raw[256];            /* the line as read (RC/asm readline: INCLUDE's file name, the error messages) */
char ln[256];             /* the same upper-cased and cut (RC/asm buffer/labl/command) */
char *cmd;                /* the instruction, trimmed */
int llen;                 /* the label: ln[0..llen) (0: none) */
char sbuf[512];           /* the source's sector */
char *sp, *se;
int fh, lnum, fdep;       /* the file being read, its line number, 0 = the source, 1..2 INCLUDEs */
int sfh[3], slnum[3];     /* the outer files meanwhile */
char srcn[64], outn[64];
int pass, errs, lnerr, stop, hexo, toerr;
int alo, ahi;             /* the address: 32 bits, as RC/asm's word */
int first, fset, start, sset;   /* the first byte's address (pass 1), END's */
int oh;                   /* the output */
char obuf[64];
int on;
char orow[16];            /* the Intel-hex record being built (RC/asm outRow) */
int ocnt, oaddr, fpos, nbytes;
char *listp;              /* \L / \M: the list */
char av[16];              /* the arguments matched: high word, low word, 4 bytes each */
char *ap;
int xh, xl, yh, yl;       /* 32-bit accumulator and operand */
char pool[POOL];          /* labels: next(2) value(2) len|flags(1) name; 0 ends a chain */
int ptop = 1;
int nsym, lasth, curlab;
int heads[NHASH];
char tk[NT * 6];          /* tokens: type ('C' text, 'N' number, 0 never used), first character, high, low word */
int tcount, cur;
char tbuf[34];            /* the token being read */
int tl;

/* ---- text output ---- */
void oc(char c) { if (toerr) eputc(c); else putchar(c); }
void ostr(char *s) { while (*s) oc(*s++); }
void odec(int n) {
    char b[6], *p;
    p = b;
    while (1) { *p++ = '0' + n % 10; n = n / 10; if (!n) break; }
    while (p != b) oc(*--p);
}
int hexd(int d) { return d < 10 ? '0' + d : 'a' + d - 10; }
void ohex(int n) { oc(hexd(n >> 12)); oc(hexd((n >> 8) & 15)); oc(hexd((n >> 4) & 15)); oc(hexd(n & 15)); }
void scpy(char *d, char *s) { while ((*d++ = *s++)) ; }

/* ---- errors: one per line, "asm: LINE: message[: what]" and the instruction ---- */
void err(char *m, char *what) {
    char *s;
    if (lnerr) return;
    lnerr = 1; errs++; toerr = 1;
    ostr("asm: ");
    if (fdep) ostr("INCLUDE ");
    odec(lnum); ostr(": "); ostr(m);
    if (what) { ostr(": "); ostr(what); }
    ostr("\n  ");
    for (s = raw; (*s >= 32 && *s < 128) || *s == 9; s++) oc(*s);
    oc(10);
    toerr = 0;
}
void fatal(char *m, char *what) { err(m, what); stop = 1; }

int isws(char c) { return c <= 32 || c >= 128; }         /* RC/asm: c <= ' ' on a signed char */
int isctl(char c) { return c < 32 || c >= 128; }         /* RC/asm: c < ' ' on a signed char */
int pfx(char *s, char *p) { while (*p) if (*s++ != *p++) return 0; return 1; }
int same(char *a, char *b, int n) { while (n) { if (*a++ != *b++) return 0; n--; } return 1; }

/* ---- 32-bit arithmetic on xh:xl and yh:yl ---- */
void add32() { int t; t = xl; xl = xl + yl; xh = xh + yh; if (xl < t) xh++; }
void neg32() { xl = ~xl; xh = ~xh; if (!++xl) xh++; }
void sub32() { int b; b = xl < yl; xl = xl - yl; xh = xh - yh - b; }
void mul32() {                               /* x = x * y mod 2^32 */
    int ah, al, bh, bl;
    ah = xh; al = xl; bh = yh; bl = yl; xh = xl = 0;
    while (bh || bl) {
        if (bl & 1) { yh = ah; yl = al; add32(); }
        ah = (ah << 1) | (al >> 15); al = al << 1;
        bl = (bl >> 1) | (bh << 15); bh = bh >> 1;
    }
}
int div16() {                                /* x = x / y, rounded towards 0 as C's int division; 1 = error */
    int sn;
    sn = 0;
    if (xh) { if (xh != 65535 || !xl) return 2; neg32(); sn = 1; }
    if (yh) { if (yh != 65535 || !yl) return 2; yl = 0 - yl; yh = 0; sn = !sn; }
    if (!yl) return 1;
    xl = xl / yl;
    if (sn) neg32();
    return 0;
}
void digit(int base, int d) {                /* x = x * base + d */
    if (!xh && xl < 4096) xl = base == 16 ? xl << 4 : (xl << 3) + (xl << 1);
    else { yh = 0; yl = base; mul32(); }
    yh = 0; yl = d; add32();
}

/* ---- the symbol table ---- */
int hash(char *s, int n, int h) {             /* h = h*5 + c from the seed h; the two bytes XORed */
    while (n) { h = h * 4 + h + *s++; n--; }
    return h ^ (h >> 8);
}
int symfind(char *s, int n) {                /* the label's record, 0 = none; leaves lasth for deflabel */
    int o; char *p;
    lasth = hash(s, n, 0) & (NHASH - 1);
    o = heads[lasth];
    while (o) {
        p = pool + o;
        if ((p[4] & 31) == n && same(p + 5, s, n)) return o;
        o = peekw(p);
    }
    return 0;
}
void symset(int o) {                         /* value = xh:xl, whose high word must be 0 or 65535 */
    char *p;
    p = pool + o;
    if (xh && xh != 65535) { err("value out of range", 0); return; }
    pokew(p + 2, xl);
    p[4] = (p[4] & 31) | (xh ? 32 : 0);
}
void symget(int o) { char *p; p = pool + o; xl = peekw(p + 2); xh = p[4] & 32 ? 65535 : 0; }
void deflabel() {                            /* RC/asm make_label (pass 1): this line's label = the address */
    char *p, *s; int n;
    n = llen; ln[n] = 0;
    if (symfind(ln, n)) { err("duplicate label", ln); return; }
    if (n > 29) { fatal("label over 29 characters", ln); return; }
    if (ahi) { fatal("label past $FFFF", ln); return; }
    if (ptop + n + 5 > POOL) { fatal("symbol table full", 0); return; }
    p = pool + ptop;
    pokew(p, heads[lasth]); heads[lasth] = curlab = ptop;
    pokew(p + 2, alo); p[4] = n;
    ptop = ptop + n + 5; nsym++;
    s = ln; p = p + 5;
    while (n) { *p++ = *s++; n--; }
}

/* ---- expressions: RC/asm get_num, buildTokens, process_tokens ----
   Tokens are 6-byte records copied and shifted exactly as RC/asm's tokens[] are, stale records beyond tokenCount
   included, so an expression reads the same leftovers as there. */
char *tp(int i) { return tk + i * 4 + i + i; }
void tkend() {                               /* the token in tbuf is complete: RC/asm's conversion loop */
    char c, h, *s; int o;
    tbuf[tl] = 0;
    c = tbuf[0];
    s = tp(cur); s[0] = 'C'; s[1] = c;
    xh = xl = 0;
    if (c == 39 || c == 34) {                /* a quoted character, signed */
        xl = tbuf[1];
        if (xl >= 128) { xh = 65535; xl = xl | 65280; }
    } else if ((c | 32) >= 'a' && (c | 32) <= 'z') {
        if (tl < 30 && (o = symfind(tbuf, tl))) symget(o);
        else if (pass == 1) xl = 1;
        else err("undefined label", tbuf);
    } else if (c >= '0') {                   /* a number: hex if an H is in it (every hex digit counts), else atoi */
        h = 0;
        for (s = tbuf; *s; s++) if ((*s | 32) == 'h') h = 1;
        for (s = tbuf; (c = *s); s++) {
            if (c >= '0' && c <= '9') digit(h ? 16 : 10, c - '0');
            else if (!h) break;
            else if ((c | 32) >= 'a' && (c | 32) <= 'f') digit(16, (c | 32) - 87);
        }
    } else if (c == '$') { xh = ahi; xl = alo; }
    else return;
    s = tp(cur); s[0] = 'N'; pokew(s + 2, xh); pokew(s + 4, xl);
}
int newtk() {
    cur = tcount++; tl = 0;
    if (tcount > NT - 3) { err("expression too long", 0); return 1; }
    return 0;
}
int addc(char c) {
    if (tl > 31) { err("token too long", 0); return 1; }
    tbuf[tl++] = c;
    return 0;
}
char opmap[] = {0, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1};   /* ' '..'/': RC/asm's operators + - * / $ ( ) . ! & */
int buildtk(char *s, char *e) {              /* 1 = error */
    char q, c;
    tcount = 1; cur = tl = q = 0;
    while (s != e) {
        c = *s++;
        if (q) {
            if (addc(c)) return 1;
            if (c == q) { q = 0; tkend(); if (newtk()) return 1; }
        } else if (c == 34 || c == 39) { q = c; if (addc(c)) return 1; }
        else if (c > 32 && c < 48 && opmap[c - 32]) {
            if (tl) { tkend(); if (newtk()) return 1; }
            addc(c); tkend(); if (newtk()) return 1;
        } else if (c > 32 && c < 128) { if (addc(c)) return 1; }
    }
    if (tl) tkend(); else tcount--;
    return 0;
}
int isc(int i, char ch) { char *p; p = tp(i); return p[0] == 'C' && p[1] == ch; }
void tkdel(int i, int k) {                   /* RC/asm: for (j = i; j < tokenCount; j++) tokens[j] = tokens[j+k] */
    char *d, *s, *e;
    d = tp(i); s = tp(i + k); e = tp(tcount + k);
    while (s < e) *d++ = *s++;
    tcount = tcount - k;
}
int apply(char op) {                          /* x = x op y; 1 = error */
    int sn;
    if (op == '*') mul32();
    else if (op == '+') add32();
    else if (op == '-') sub32();
    else if (op == '&') { xh = xh & yh; xl = xl & yl; }
    else if (op == '!') { xh = xh | yh; xl = xl | yl; }
    else if (op == '.') {                    /* .0 the low byte, .1 x / 256 (C's int division) */
        if (yh || yl > 1) return 1;
        if (!yl) { xh = 0; xl = xl & 255; return 0; }
        sn = xh >> 15;
        if (sn) neg32();
        xl = (xl >> 8) | (xh << 8); xh = xh >> 8;
        if (sn) neg32();
    } else if ((sn = div16())) { err(sn == 1 ? "division by zero" : "'/' beyond 16 bits", 0); return 1; }
    return 0;
}
/* one level of RC/asm process_tokens(start, end), ex = end + 1: the operators a and b, left to right. ex does not
   shrink as tokens go, so the scan can read tokens that slid in from beyond the range, as there. */
int level(int st, int ex, char a, char b) {
    int i; char *p;
    i = st;
    while (i < ex) {
        p = tp(i);
        if (p[0] == 'C' && (p[1] == a || p[1] == b)) {
            if (!i || i + 1 == tcount || tcount < 3) return 1;   /* (tcount < 3: RC/asm's count would go negative) */
            if (*(p - 6) != 'N' || p[6] != 'N') return 1;
            xh = peekw(p - 4); xl = peekw(p - 2); yh = peekw(p + 8); yl = peekw(p + 10);
            if (apply(p[1])) return 1;
            pokew(p - 4, xh); pokew(p - 2, xl);
            tkdel(i, 2);
        } else i++;
    }
    return 0;
}
int process(int st, int ex) {
    char *p, *d, *s, *e, c;
    if (level(st, ex, '.', '.') || level(st, ex, '*', '/')) return 1;
    p = tp(st);
    if (p[0] == 'C' && (p[1] == '+' || p[1] == '-')) {   /* a leading sign: dropped; '-' negates the token at ex */
        if (p[6] != 'N' || !tcount) return 1;
        c = p[1];
        d = p; s = p + 6; e = tp(ex + 1);
        while (s < e) *d++ = *s++;
        tcount--;
        if (c == '-') {
            p = tp(ex);
            if (p[0] == 'N') { xh = peekw(p + 2); xl = peekw(p + 4); neg32(); pokew(p + 2, xh); pokew(p + 4, xl); }
            else p[1] = 256 - p[1];
        }
    }
    return level(st, ex, '+', '-') || level(st, ex, '&', '!');
}
void getnum(char *s, char *e) {              /* the value of the text s..e in xh:xl; 0 after an error */
    int i, j;
    if (buildtk(s, e)) { xh = xl = 0; return; }
    if (tcount == 1 && tk[0] == 'N') { xh = peekw(tk + 2); xl = peekw(tk + 4); return; }   /* (what the rest makes of it) */
    while (1) {                              /* the first ')' and the nearest '(' before it */
        for (i = 0; i < tcount && !isc(i, ')'); i++) ;
        if (i == tcount) break;
        for (j = i + 1; j && !isc(j - 1, '('); j--) ;
        if (!j) break;
        j--;
        tkdel(i, 1); tkdel(j, 1);
        if (process(j, i - 1)) { tcount = 0; break; }
    }
    if (tcount && !process(0, tcount) && tcount == 1) { xh = peekw(tk + 2); xl = peekw(tk + 4); return; }
    err("bad expression", 0);
    xh = xl = 0;
}

/* ---- output ---- */
void oput(char c) {
    obuf[on++] = c;
    if (on == 64) { if (fwrite(oh, obuf, 64) != 64) fatal("write failed (disk full, or 16M)", 0); on = 0; }
}
void ohexb(int b) { oput(hexd((b >> 4) & 15)); oput(hexd(b & 15)); }
void flush() {                               /* RC/asm write_line (pass 2, -h): the pending record */
    char *p; int ck;
    if (pass != 2 || !hexo) return;
    if (ocnt) {
        oput(':'); ohexb(ocnt); ohexb(oaddr >> 8); ohexb(oaddr); ohexb(0);
        ck = ocnt + oaddr + (oaddr >> 8);
        for (p = orow; p != orow + ocnt; p++) { ohexb(*p); ck = ck + *p; }
        ohexb(0 - ck); oput(10);
    }
    ocnt = 0; oaddr = alo;
}
void wbyte(char b) {                          /* RC/asm write_byte */
    if (pass == 2) {
        if (ahi) { err("code past $FFFF", 0); return; }
        nbytes++;
        if (hexo) orow[ocnt++] = b;
        else if (alo < fpos) err("addresses go down: use -h", 0);
        else { while (fpos != alo) { oput(0); fpos++; } oput(b); fpos++; }
    } else if (!fset) { first = alo; fset = 1; }
    if (!++alo) ahi++;
    if (ocnt == 16) flush();
}

/* ---- matching: RC/asm Class_Match, WildMatch ---- */
void putarg() { pokew(ap, xh); pokew(ap + 2, xl); ap = ap + 4; }
int clsmatch(int k, char *d) {               /* the first entry of class k that d starts with: its length, 0 = none */
    char *p, *v, n;
    p = op_cn[k]; v = op_cv[k];
    while ((n = *p)) {
        if (same(d, p + 1, n)) { xh = 0; xl = *v; putarg(); return n; }
        p = p + n + 1; v++;
    }
    return 0;
}
int inrange(int byte) {                      /* RC/asm: abs((int)v) < 256 (\B) or 65536 (\W) */
    if (!xh) return !byte || xl < 256;
    if (xh == 65535) return byte ? xl > 65280 : xl != 0;
    return xh == 32768 && !xl;               /* abs(INT_MIN) is negative */
}
int match(char *p, char *d) {                /* the pattern's operand shape p against d, the text after the first word */
    char b, q, c, *s; int n;
    ap = av;
    while (1) {
        b = *p++;
        if (!b) return !*d;
        if (b == 1) {                        /* white space */
            if (!*d || !isws(*d)) return 0;
            while (*d && isws(*d)) d++;
        } else if (b >= 8 && b < 16) {       /* a class */
            if (!(n = clsmatch(b - 8, d))) return 0;
            d = d + n;
        } else if (b == 4 || b == 5) {       /* \B, \W: up to a ',' or ' ' outside quotes */
            s = d; q = 0;
            while ((c = *d) && (q || (c != ',' && c != ' '))) {
                if (c == q) q = 0; else if (c == 34 || c == 39) q = c;
                d++;
            }
            if (d == s) return 0;
            getnum(s, d);
            if (!inrange(b == 4)) return 0;
            putarg();
        } else if (b == 6 || b == 7) {       /* \L, \M: the rest */
            listp = d;
            while (*d) d++;
            ap = ap + 4;
        } else if (*d++ != b) return 0;
    }
}

/* ---- the operations of the matched pattern: RC/asm Translate ---- */
void listout(int w) {                        /* DB (w = 0) / DW items: "text", 'text' or an expression */
    char *s, *t, q, c;
    s = listp;
    while (1) {
        t = s; q = 0;
        while ((c = *t) && (q || c != ',')) {
            if (c == q) q = 0; else if (!q && (c == 34 || c == 39)) q = c;
            t++;
        }
        if (t != s) {
            if (*s == 34 || *s == 39) {
                q = *s++;
                while (s != t && *s != q) { if (w) wbyte(*s >= 128 ? 255 : 0); wbyte(*s++); }
            } else {
                getnum(s, t);
                if (w) wbyte(xl >> 8);
                wbyte(xl & 255);
            }
        }
        if (!*t) return;
        s = t + 1;
    }
}
void equ() {                                 /* this line's label = xh:xl */
    int o;
    if (pass == 1) { if (curlab) symset(curlab); return; }
    if (!llen) { err("no label", 0); return; }
    if ((o = symfind(ln, llen))) symset(o);
}
void run(char *p, int n) {                   /* the operations (tools/gen_y1_optab.py): B is b */
    char op, b, *a; int v, vh;
    b = 0;
    while (n) {
        op = *p++; n--;
        if (op == 1) { wbyte(b); b = 0; continue; }              /* write B */
        if (op == 208) { b = *p++; n--; continue; }              /* B = n */
        a = av + (op & 3) * 4; vh = peekw(a); v = peekw(a + 2);
        switch (op & 240) {
        case 16: b = b + b; b = b + b; b = b + b; b = b + b + (op & 15); break;   /* a hex digit */
        case 32: b = v; break;                                   /* \n, lo(n) */
        case 48: b = v >> 8; break;                              /* hi(n) */
        case 64: b = b | v; break;                               /* |n */
        case 80: v = v + v; v = v + v; v = v + v; b = b | (v + v); break;         /* |n<4 */
        case 96: b = b & *p++; n--; break;                       /* &mm */
        case 112: listout(op & 8); break;                        /* DB, DW list */
        case 128: ahi = vh; alo = v; flush(); break;             /* ORG */
        case 144: xh = ahi; xl = alo; yh = vh; yl = v; add32(); ahi = xh; alo = xl; flush(); break;   /* DS */
        case 160: start = v; sset = 1; break;                    /* END */
        case 176: xh = vh; xl = v; equ(); break;                 /* EQU */
        default: err("not supported", 0);                        /* PUBLIC, EXTERN, LIB */
        }
    }
}
void asmcmd() {                              /* RC/asm asm_cmd: the first pattern that matches is done */
    char *s, *r, *p; int n, np;
    if (!*cmd) return;
    for (s = cmd; *s && !isws(*s); s++) ;
    n = s - cmd;
    np = hash(cmd, n, OPSEED) & 63;
    r = np < 32 ? op_h0[np] : op_h1[np - 32];
    while (*r) {                             /* the records of the mnemonic's hash chain */
        p = r;
        while (*p) p++;                      /* p at the name's end */
        np = p[1]; p = p + 2;
        if (p - r == n + 2 && same(r, cmd, n)) {
            while (np) {
                r = p;
                while (*p) p++;
                if (match(r, s)) { run(p + 2, p[1]); return; }
                p = p + 2 + p[1];
                np--;
            }
            break;
        }
        while (np) { while (*p) p++; p = p + 2 + p[1]; np--; }  /* skip the record */
        r = p;
    }
    if (pfx(cmd, "ENDM") && !cmd[4]) err("not supported", 0);
    else if (pass == 2) err("invalid instruction", 0);
}

/* ---- the source ---- */
int getln() {                                /* the next line: 0 at the end of the file, 2 = an INCLUDE line */
    char *p, *r, *pe, *e, *t, c, q, m; int n;
    p = ln; r = raw; pe = ln + 254; q = m = 0; e = t = 0;
    while (p != pe) {                        /* fgets(raw, 255): up to 254 bytes, through the line feed; and */
        if (fdep) { if ((n = fgetc(fh)) == 65535) break; c = n; }        /* at once into ln: */
        else {
            if (sp == se) { if (!(n = fread(fh, sbuf))) break; sp = sbuf; se = sbuf + n; }
            c = *sp++;
        }
        *r++ = c;
        if (c >= 'a') { if (c <= 'z' && !m) c = c - 32; }     /* makeupper: upper case outside single quotes */
        else if (c == 39) m = !m;
        *p++ = c;
        if (c <= ';') {                      /* (above ';' nothing below matters: 2026-09-25, a third of asm's time) */
            if (!e) {                        /* parse: the comment (';') and the label (':') outside quotes */
                if (!c) e = p - 1;
                else if (c == 34 || c == 39) q = q == c ? 0 : c;
                else if (!q) { if (c == ';') e = p - 1; else if (c == ':' && !t) t = p - 1; }
            }
            if (c == 10) break;
        }
    }
    *p = *r = 0;
    if (p == ln) return 0;
    if (!e) e = p;
    llen = 0; p = ln;
    if (t) { llen = t - ln; p = t + 1; }
    while (p < e && (*p <= 32 || *p >= 128)) p++;           /* trim */
    cmd = p;
    *e = 0;
    while (e > cmd && isws(*(e - 1))) *--e = 0;
    return pfx(cmd, "INCLUDE") ? 2 : 1;
}
void include() {                             /* RC/asm: the file is the line's text after its first word */
    char *s, *n; int h;
    for (s = raw; *s == ' '; s++) ;
    while (*s && *s != ' ') s++;
    while (*s == ' ') s++;
    for (n = s; *s && !isctl(*s); s++) ;
    *s = 0;
    if (fdep == 2) { fatal("INCLUDE too deep", n); return; }
    if (!(h = fopen(n))) { fatal("cannot open", n); return; }
    sfh[fdep] = fh; slnum[fdep] = lnum;
    fdep++; fh = h; lnum = 0;
}
int popf() {                                 /* the end of a file: back to the outer one; 1 = it was the source */
    fclose(fh);
    if (!fdep) return 1;
    fdep--; fh = sfh[fdep]; lnum = slnum[fdep];
    return 0;
}
int runpass(int p) {                         /* 1 = the source cannot be opened */
    char c;
    pass = p; alo = ahi = fdep = lnum = 0; sp = se = sbuf;
    if (!(fh = fopen(srcn))) return 1;
    while (!stop) {
        if (!(c = getln())) { if (popf()) return 0; continue; }
        lnum++; lnerr = 0;
        if (c == 2) { include(); continue; }
        if (pfx(cmd, "MACRO")) { fatal("not supported", 0); continue; }
        curlab = 0;
        if (pass == 1 && llen) { deflabel(); if (stop) continue; }
        asmcmd();
    }
    while (!popf()) ;
    return 0;
}

void main() {
    char *a, *s, *dot;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] | 32) == 'h' && a[2] <= ' ') { hexo = 1; a = a + 2; }
    a = argword(a, srcn, 58);
    argword(a, outn, 63);
    if (!srcn[0] || srcn[0] == '-') {
        puts("usage: asm [-h] SRC [OUT]");
        return;
    }
    dot = 0;
    for (s = srcn; *s; s++) { if (*s == '.') dot = s; if (*s == '/') dot = 0; }
    if (!dot) { dot = s; scpy(s, ".ASM"); }
    if (!outn[0]) {
        s = outn; a = srcn;
        while (a != dot) *s++ = *a++;
        scpy(s, hexo ? ".IMG" : "");
    }
    if (runpass(1)) { errs = 1; eput2("asm: cannot open ", srcn); return; }
    if (!errs) {
        if (!(oh = fcreate(outn, first, sset ? start : first))) { errs = 1; eput2("asm: cannot create ", outn); return; }
        fpos = first;
        runpass(2);
        flush();
        if (hexo) for (s = ":00000001ff\n"; *s; s++) oput(*s);
        if (on && fwrite(oh, obuf, on) != on) fatal("write failed (disk full, or 16M)", 0);
        fclose(oh);
        if (errs) fdelete(outn);
    }
    if (errs) {
        toerr = 1; ostr("asm: "); odec(errs); ostr(errs == 1 ? " error" : " errors");
        if (oh) { ostr(", no "); ostr(outn); }
        oc(10); return;
    }
    ostr(outn); ostr(": "); odec(nbytes); ostr(" bytes, "); odec(nsym); ostr(" labels");
    if (fset) { ostr(", load "); ohex(first); ostr(" exec "); ohex(sset ? start : first); }
    oc(10);
}
