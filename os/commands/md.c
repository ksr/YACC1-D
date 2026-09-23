/* md.c - render a Markdown file on the console, a screen at a time.
     md FILE.MD       styled with ANSI SGR escapes: bold headings (h1/h2 underlined), dim code, wrapped prose
     md -p FILE.MD    plain: the same layout without escapes (dumb terminals, tests)
     md               the documents in /DOCS
   A name that is not found as given is looked for in /DOCS (so `md OS.MD` reads /DOCS/OS.MD).
   The subset, one classification per line: # headings; - * + and 1. list items (hanging indent); > quotes;
   ``` code fences (verbatim, indented, dim); |tables| (buffered, columns measured and aligned, the ---- row drawn
   as dashes); --- rules; prose word-wrapped at 78 columns, consecutive lines joined into one paragraph. Inline: **bold**, `code`, [text](url) -> text (url).
   Anything else passes through as prose: rendering never fails. Lines are cut at 238 characters, tables at 20
   rows of 178 and 10 columns.
   The pager is lib_more.c: --More-- after 23 lines, space = page, Enter = line, q = quit.
   Ported from P8X os/commands/md.c 2026-09-23, changes: the pager is the shared lib_more.c (the P8X md had its
   own at 22 lines with a reverse-video prompt; every character goes through pgc() so the line count sees
   everything); fopen/fgetc on a handle for FRESOLVE/FOPEN/FGETB; the /DOCS fallback and the listing are new;
   a block-local `int u` that shadowed a `char *u` became uc (y1cc keeps one static slot per name); consecutive
   prose lines (and a list item's indented continuation lines) now flow into ONE paragraph, as Markdown means them
   (the P8X md rendered every source line as a paragraph of its own, which broke the hard-wrapped Y1 documents). */
#include "../lib_fs.c"
#include "../lib_more.c"
#include "../lib_err.c"
#include "y1lib.c"
char path[64], dpath[72];
char lin[240];                  /* one raw source line                  */
char wrd[160];                  /* one word being assembled             */
char tbf[3600];                 /* table buffer: up to 20 rows x 180    */
int  tbw[10];                   /* table column widths (<= 10 columns)  */
int  mdh;                       /* the file's read handle               */
char dent[32], dnm[13];

void listdocs() {
    int h;
    h = opendir("/DOCS");
    if (!h) return;
    while (readdir(h, dent)) { ent_name(dent, dnm); if (dnm[0] != '.') { putstr("  "); puts(dnm); } }
    fclose(h);
}

int ansi;                       /* 1 = emit SGR escapes                 */
int infen;                      /* inside a ``` fence                   */
int tbn;                        /* buffered table rows                  */
int ateof;                      /* input exhausted                      */
int inpara;                     /* a prose/list paragraph is open       */
int pind;                       /* its hanging indent                   */
int col;                        /* visible column while wrapping        */
int bold;                       /* inline state, carried across wraps   */
int dim;

/* ---- console helpers ---------------------------------------------------- */

int esc(char *s) {              /* one SGR sequence, ansi mode only */
    if (ansi == 0) { return 0; }
    pgc(27); pgc('[');
    while (*s != 0) { pgc(*s); s = s + 1; }
    pgc('m');
    return 0;
}

int attrs() {                   /* (re)assert the current inline attrs */
    esc("0");
    if (bold) { esc("1"); }
    if (dim)  { esc("2"); }
    return 0;
}

void nl() { pgc(10); }

int spaces(int n) {
    while (n) { pgc(32); n = n - 1; }
    return 0;
}

/* ---- input -------------------------------------------------------------- */

/* rdln: next source line into lin (CR and LF stripped, tabs -> spaces,
 * capped at 238). Returns 1 if a line was read, 0 at end of file. */
int rdln() {
    int c, i;
    if (ateof) return 0;
    i = 0;
    c = fgetc(mdh);
    if (c == 65535) { ateof = 1; return 0; }
    while (c != 65535 && c != 10) {
        if (c == 9) c = 32;
        if (c != 13 && i < 238) lin[i++] = c;
        c = fgetc(mdh);
    }
    if (c == 65535) ateof = 1;
    lin[i] = 0;
    return 1;
}

/* ---- inline emission with wrapping -------------------------------------- */

/* emitw: print the assembled word (wrd, visible width vw), wrapping to a
 * fresh line at `ind` columns first if it will not fit in 78. */
int emitw(int vw, int ind) {
    char *p;
    if (col + vw > 78 && col > ind) {
        nl();
        spaces(ind);
        col = ind;
        if (bold || dim) { attrs(); }
    }
    p = wrd;
    while (*p != 0) { pgc(*p); p = p + 1; }
    col = col + vw;
    return 0;
}

/* flow: render s as wrapped prose from the current position. Inline marks
 * (** ` [](...)) become attributes; ind is the hanging indent. */
int flow(char *s, int ind) {
    int wi; int vw; int sp;
    wi = 0; vw = 0;
    while (*s != 0 && pgquit == 0) {
        sp = 0;
        if (*s == 32) { sp = 1; }
        else if (*s == '*' && *(s + 1) == '*') {
            wrd[wi] = 0;
            if (wi) { emitw(vw, ind); wi = 0; vw = 0; }
            bold = 1 - bold;
            if (bold) { esc("1"); } else { attrs(); }
            s = s + 2;
        }
        else if (*s == '`') {
            wrd[wi] = 0;
            if (wi) { emitw(vw, ind); wi = 0; vw = 0; }
            dim = 1 - dim;
            if (dim) { esc("2"); } else { attrs(); }
            s = s + 1;
        }
        else if (*s == '[') {
            /* [text](url) -> text (url); anything else: literal '[' */
            char *t; int ok;
            t = s + 1; ok = 0;
            while (*t != 0 && *t != ']') { t = t + 1; }
            if (*t == ']' && *(t + 1) == '(') { ok = 1; }
            if (ok) {
                s = s + 1;
                while (*s != ']') {          /* the text, worded out */
                    if (*s == 32) {
                        wrd[wi] = 0; emitw(vw, ind);
                        wrd[0] = 32; wrd[1] = 0; emitw(1, ind);
                        wi = 0; vw = 0;
                    } else if (wi < 156) {
                        wrd[wi] = *s; wi = wi + 1; vw = vw + 1;
                    }
                    s = s + 1;
                }
                s = s + 2;                   /* past "](" */
                if (wi < 155) { wrd[wi] = 32; wrd[wi+1] = '('; wi = wi + 2; vw = vw + 2; }
                while (*s != 0 && *s != ')') {
                    if (wi < 156) { wrd[wi] = *s; wi = wi + 1; vw = vw + 1; }
                    s = s + 1;
                }
                if (*s == ')') { s = s + 1; }
                if (wi < 156) { wrd[wi] = ')'; wi = wi + 1; vw = vw + 1; }
            } else {
                if (wi < 156) { wrd[wi] = '['; wi = wi + 1; vw = vw + 1; }
                s = s + 1;
            }
        }
        else {
            if (wi < 156) { wrd[wi] = *s; wi = wi + 1; vw = vw + 1; }
            s = s + 1;
        }
        if (sp) {
            wrd[wi] = 0;
            if (wi) { emitw(vw, ind); }
            wi = 0; vw = 0;
            if (col < 78) {
                wrd[0] = 32; wrd[1] = 0;
                if (col > ind) { emitw(1, ind); }
            }
            s = s + 1;
        }
    }
    wrd[wi] = 0;
    if (wi) { emitw(vw, ind); }
    return 0;
}

/* para: one classified body line rendered as flowed text. pre is the
 * printed prefix, ind the hanging indent for continuations. */
int para(char *pre, char *s, int ind) {
    spaces(0);
    col = 0;
    while (*pre != 0) { pgc(*pre); col = col + 1; pre = pre + 1; }
    bold = 0; dim = 0;
    flow(s, ind);
    inpara = 1; pind = ind;             /* the next prose line continues it */
    return 0;
}

int endpara() {                 /* close an open paragraph: attributes off, newline */
    if (inpara) { attrs(); nl(); inpara = 0; }
    return 0;
}

/* ---- tables ------------------------------------------------------------- */

/* cellw: measure/emit one row from the buffer. When put=0 just record
 * column widths; when put=1 print the row padded to tbw[]. A separator
 * row (cells of ---) prints as dashes. */
int cellw(char *r, int put) {
    int ci; int w; int sep; int j;
    ci = 0;
    if (*r == '|') { r = r + 1; }
    while (*r != 0 && ci < 10) {
        char *c; int n;
        while (*r == 32) { r = r + 1; }
        c = r; n = 0; sep = 1;
        while (*r != 0 && *r != '|') {
            if (*r != 32 && *r != '-' && *r != ':') { sep = 0; }
            r = r + 1;
        }
        n = r - c;
        while (n && *(c + n - 1) == 32) { n = n - 1; }   /* rtrim */
        if (put == 0) {
            if (sep == 0 && n > tbw[ci]) { tbw[ci] = n; }
        } else {
            w = tbw[ci];
            if (ci == 0) { pgc(32); pgc(32); }
            if (sep) {
                j = 0;
                while (j < w) { pgc('-'); j = j + 1; }
            } else {
                j = 0;
                while (j < n) { pgc(*(c + j)); j = j + 1; }
                while (j < w) { pgc(32); j = j + 1; }
            }
            pgc(32); pgc(32);
        }
        ci = ci + 1;
        if (*r == '|') { r = r + 1; }
    }
    if (put) { nl(); }
    return 0;
}

int tflush() {                  /* measure all buffered rows, emit aligned */
    int r;
    if (tbn == 0) { return 0; }
    r = 0;
    while (r < 10) { tbw[r] = 0; r = r + 1; }
    r = 0;
    while (r < tbn) { cellw(tbf + r * 180, 0); r = r + 1; }
    r = 0;
    while (r < tbn && pgquit == 0) { cellw(tbf + r * 180, 1); r = r + 1; }
    tbn = 0;
    return 0;
}

/* ---- line classification ------------------------------------------------ */

int starts(char *s, char *p) {
    while (*p != 0) {
        if (*s != *p) { return 0; }
        s = s + 1; p = p + 1;
    }
    return 1;
}

int hrule(char *s) {            /* ---, ***, ___ alone on the line */
    int n; int c;
    c = *s;
    if (c != '-' && c != '*' && c != '_') { return 0; }
    n = 0;
    while (*s == c || *s == 32) { if (*s == c) { n = n + 1; } s = s + 1; }
    if (*s == 0 && n >= 3) { return 1; }
    return 0;
}

int render() {                  /* the whole file, line by line */
    int i; int lvl; char *s; char *t; char *u; int ind; char *t0;
    while (rdln() && pgquit == 0) {
        s = lin;
        t0 = s;                                       /* fences and tables may be indented (inside a list) */
        while (*t0 == 32) { t0 = t0 + 1; }
        if (infen || starts(t0, "```")) {             /* code fences */
            if (starts(t0, "```")) {
                endpara(); tflush();
                infen = 1 - infen;
                if (infen == 0) { nl(); }
            } else {
                col = 0;
                esc("2");
                pgc(32); pgc(32);
                while (*s != 0) { pgc(*s); s = s + 1; }
                esc("0");
                nl();
            }
        }
        else if (*t0 == '|') {                        /* table rows buffer */
            endpara();
            s = t0;
            if (tbn < 20) {
                i = 0;
                while (*s != 0 && i < 178) { *(tbf + tbn * 180 + i) = *s; s = s + 1; i = i + 1; }
                *(tbf + tbn * 180 + i) = 0;
                tbn = tbn + 1;
            }
        }
        else if (*s == '#') {                         /* headings */
            endpara(); tflush();
            lvl = 0;
            while (*s == '#') { lvl = lvl + 1; s = s + 1; }
            while (*s == 32) { s = s + 1; }
            nl();
            col = 0;
            if (lvl <= 2) { esc("1"); esc("4"); } else { esc("1"); }
            i = 0;
            while (*s != 0) {                     /* marks stripped */
                if (*s != '*' && *s != 96) { pgc(*s); i = i + 1; }
                s = s + 1;
            }
            esc("0");
            nl();
            if (ansi == 0) {                          /* plain: underline row */
                int uc;
                uc = '-';
                if (lvl == 1) { uc = '='; }
                col = 0;
                while (i) { pgc(uc); i = i - 1; }
                nl();
            }
        }
        else if (hrule(s)) {
            endpara(); tflush();
            col = 0;
            i = 0;
            while (i < 78) { pgc('-'); i = i + 1; }
            nl();
        }
        else if (starts(s, "> ")) {
            endpara(); tflush();
            para("  | ", s + 2, 4);
        }
        else if (*s == '>' && *(s + 1) == 0) {
            endpara(); tflush();
            para("  | ", s + 1, 4);
        }
        else {                                        /* lists then prose */
            t = s; ind = 0;
            while (*t == 32) { t = t + 1; ind = ind + 1; }
            if ((*t == '-' || *t == '*' || *t == '+') && *(t + 1) == 32) {
                endpara(); tflush();
                spaces(0);
                col = 0;
                spaces(ind + 2); col = ind + 2;
                pgc('-'); pgc(32); col = col + 2;
                bold = 0; dim = 0;
                flow(t + 2, ind + 4);
                inpara = 1; pind = ind + 4;
            }
            else if (*t >= '0' && *t <= '9') {
                u = t;
                while (*u >= '0' && *u <= '9') { u = u + 1; }
                if (*u == '.' && *(u + 1) == 32) {
                    endpara(); tflush();
                    col = 0;
                    spaces(ind + 2); col = ind + 2;
                    while (t <= u) { pgc(*t); t = t + 1; col = col + 1; }
                    pgc(32); col = col + 1;
                    bold = 0; dim = 0;
                    flow(u + 2, ind + 5);
                    inpara = 1; pind = ind + 5;
                } else if (inpara) {
                    if (col > pind) { wrd[0] = 32; wrd[1] = 0; emitw(1, pind); }
                    flow(t, pind);
                } else {
                    endpara(); tflush();
                    para("", s, 0);
                }
            }
            else if (*s == 0) { endpara(); tflush(); nl(); }     /* blank line */
            else if (inpara) {                        /* a continuation line: same paragraph */
                while (*s == 32) { s = s + 1; }
                if (col > pind) { wrd[0] = 32; wrd[1] = 0; emitw(1, pind); }
                flow(s, pind);
            }
            else { endpara(); tflush(); para("", s, 0); }
        }
    }
    endpara(); tflush();
    return 0;
}

/* ---- entry -------------------------------------------------------------- */

void main() {
    char *ap;
    ap = argstr();
    while (*ap == 32) { ap = ap + 1; }
    ansi = 1;
    if (*ap == '-' && *(ap + 1) == 'p') {
        ansi = 0;
        ap = ap + 2;
        while (*ap == 32) { ap = ap + 1; }
    }
    if (*ap == 0 || (*ap == '-' && (*(ap + 1) == 'h' || *(ap + 1) == 'H'))) {
        puts("usage: md [-p] FILE.MD    render markdown (-p: no ANSI styling); md with no file lists /DOCS");
        if (*ap == 0) listdocs();
        return;
    }
    argword(ap, path, 63);
    mdh = fopen(path);
    if (!mdh && path[0] != '/') { strcpy(dpath, "/DOCS/"); strcpy(dpath + 6, path); mdh = fopen(dpath); }
    if (!mdh) { eputs("md: not found"); return; }
    infen = 0; tbn = 0; ateof = 0; inpara = 0;
    render();
    fclose(mdh);
}
