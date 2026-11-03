/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* make.c - build targets from a Makefile: make [-n] [-B] [-f file] [target ...] (2026-11-03)
     make            the first rule's target          make NAME     that target (several: each in turn)
     -n              print the recipe lines, run nothing
     -B              build every target reached, as if none existed
     -f file         read file instead of Makefile (in the current directory)
   A Makefile is lines of three kinds (blank lines and lines starting with # are skipped):
     NAME = text       a variable; $(NAME) anywhere after it is the text (one level: the text is not expanded)
     target: prereq... a rule: its target, and what must be made (or exist) first
     <TAB>command      the rule's recipe, the lines right below it: ordinary shell lines
   In prerequisites and recipes $(NAME) is a variable, $@ the target, $< the first prerequisite, $$ a '$'.
   Y1/OS keeps no file dates, so a target is built when it does not exist, when a prerequisite was built in this
   run, or with -B; a prerequisite with no rule must exist. A target with no recipe (all:) is made when any of its
   prerequisites is. To rebuild one after editing its source: make -B NAME (or del NAME, then make NAME).
   make runs nothing itself: the recipe lines of every target to build, in order, go into MAKE.SH in the current
   directory, and make EXECs it; the shell runs it as a script (sh), each line echoed, and the first command that
   fails stops it. An error in the Makefile, a missing prerequisite or a cycle: the message, nothing run, status 1. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"

#define TEXT 12000              /* the Makefile, its lines NUL-terminated in place */
#define NLINE 600
#define NRULE 150
#define NVAR 40
#define PBUF 3000               /* the expanded prerequisite lists of the rules being made (a stack) */
#define NONE 65535
char text[TEXT];
char *ln[NLINE];
int nln;
char *rtgt[NRULE], *rpre[NRULE];
int rline[NRULE], rcnt[NRULE];
char rstate[NRULE];             /* 0 not seen, 1 being made (a cycle if met again), 2 up to date, 3 built */
int nrule;
char *vname[NVAR], *vval[NVAR];
int nvar;
char pb[PBUF];
int ptop;
char out[132];                  /* an expanded recipe line: the shell takes 128 characters */
char file[64] = "Makefile";
char word[64];
char ent[32];
char nflag, bflag;
int hs;                         /* MAKE.SH's handle, 0 until the first recipe line */

void fail(char *s, char *t) { eput2(s, t); if (hs) { fclose(hs); fdelete("MAKE.SH"); } osexit(1); }

void estr(char *s) { while (*s) eputc(*s++); }
void edec(int n) { if (n >= 10) edec(n / 10); eputc('0' + n % 10); }

void failn(char *s, int n) {    /* a Makefile error at line n */
    estr("make: "); estr(file); estr(" line "); edec(n + 1); estr(": "); eputs(s);
    if (hs) { fclose(hs); fdelete("MAKE.SH"); }
    osexit(1);
}

char *trim(char *s) {           /* skip leading spaces and tabs; cut trailing ones in place */
    char *e;
    while (*s == ' ' || *s == 9) s++;
    e = s + strlen(s);
    while (e != s && (e[-1] == ' ' || e[-1] == 9)) e--;
    *e = 0;
    return s;
}

void load() {                   /* the Makefile -> text[], ln[] */
    int h, c, n;
    h = fopen(file);
    if (!h) fail("make: cannot read ", file);
    n = 0; nln = 0; ln[0] = text;
    while ((c = fgetc(h)) != 65535) {
        if (n >= TEXT - 2) { fclose(h); fail("make: too big: ", file); }
        if (c == 13) continue;
        if (c == 10) {
            text[n++] = 0;
            if (++nln >= NLINE) { fclose(h); fail("make: too many lines: ", file); }
            ln[nln] = text + n;
        } else text[n++] = c;
    }
    fclose(h);
    text[n] = 0;
    if (ln[nln][0]) nln++;      /* a last line without LF */
}

int find(char *t) {             /* the rule for target t, NONE */
    int i;
    for (i = 0; i < nrule; i++) if (strcmp(rtgt[i], t) == 0) return i;
    return NONE;
}

void parse() {                  /* ln[] -> the variables and the rules */
    int i; char *s, *p, *q;
    nrule = 0; nvar = 0;
    for (i = 0; i < nln; i++) {
        s = ln[i];
        if (s[0] == 9) {        /* a recipe line: it belongs to the rule just above */
            if (!nrule || rline[nrule - 1] + rcnt[nrule - 1] != i) failn("a recipe line without a rule", i);
            rcnt[nrule - 1]++;
            continue;
        }
        s = trim(s);
        if (!*s || *s == '#') continue;
        for (p = s; *p && *p != ':' && *p != '='; p++) ;
        if (*p == '=') {        /* NAME = text */
            if (nvar == NVAR) failn("too many variables", i);
            *p = 0;
            vname[nvar] = trim(s); vval[nvar] = trim(p + 1);
            nvar++;
        } else if (*p == ':') { /* target: prereqs */
            if (nrule == NRULE) failn("too many rules", i);
            *p = 0;
            rpre[nrule] = trim(p + 1);
            q = trim(s);
            for (p = q; *p; p++) if (*p == ' ' || *p == 9) failn("one target a rule", i);
            if (!*q) failn("no target", i);
            if (find(q) != NONE) failn("a second rule for the same target", i);
            rtgt[nrule] = q; rline[nrule] = i + 1; rcnt[nrule] = 0;
            nrule++;
        } else failn("not a rule, a variable or a recipe", i);
    }
}

char *var(char *s, int n) {     /* the variable named by the n characters at s, "" if there is none */
    int i, k;
    for (i = nvar; i > 0; i--) {
        for (k = 0; k < n && vname[i - 1][k] == s[k]; k++) ;
        if (k == n && !vname[i - 1][n]) return vval[i - 1];
    }
    return "";
}

int expand(char *s, char *d, int max, char *tgt, char *first) {   /* s -> d with $(NAME) $@ $< $$; its length,
                                                                       NONE when over max */
    int n, k; char *v;
    n = 0;
    while (*s) {
        v = 0;
        if (*s == '$') {
            s++;
            if (*s == '@') { v = tgt; s++; }
            else if (*s == '<') { v = first; s++; }
            else if (*s == '(') {
                for (k = 1; s[k] && s[k] != ')'; k++) ;
                v = var(s + 1, k - 1);
                s += s[k] ? k + 1 : k;
            } else if (*s == '$') { v = "$"; s++; }
            else v = "$";       /* a '$' before anything else stays */
        }
        if (v) { while (*v) { if (n >= max) return NONE; d[n++] = *v++; } }
        else { if (n >= max) return NONE; d[n++] = *s++; }
    }
    d[n] = 0;
    return n;
}

void emit(char *s) {            /* a recipe line: printed (-n), else into MAKE.SH */
    if (nflag) { puts(s); return; }
    if (!hs) {
        hs = fcreate("MAKE.SH", 0, 0);
        if (!hs) fail("make: cannot write ", "MAKE.SH (inside > or a pipe?)");
    }
    fputs(hs, s); fputc(hs, 10);
}

int make(char *t) {             /* 1 up to date, 2 built (its recipe emitted); errors end the program */
    int r, i, n, any, save; char *p, *w, *first;
    r = find(t);
    if (r == NONE) {
        if (fresolve(t, ent)) return 1;
        fail("make: no rule to make ", t);
    }
    if (rstate[r] == 1) fail("make: a cycle at ", t);
    if (rstate[r]) return rstate[r] - 1;
    rstate[r] = 1;
    save = ptop; p = pb + ptop;
    n = expand(rpre[r], p, PBUF - ptop - 1, t, "");
    if (n == NONE) fail("make: prerequisites too long: ", t);
    ptop += n + 1;
    any = 0; first = ""; w = p;
    while (1) {                 /* each prerequisite, NUL-terminated in place */
        while (*w == ' ' || *w == 9) w++;
        if (!*w) break;
        p = w;
        while (*w && *w != ' ' && *w != 9) w++;
        if (*w) *w++ = 0;
        if (!*first) first = p;
        if (make(p) == 2) any = 1;
    }
    any = bflag || any || !fresolve(t, ent);
    if (any) for (i = 0; i < rcnt[r]; i++) {
        if (expand(trim(ln[rline[r] + i]), out, 128, t, first) == NONE) fail("make: a recipe line over 128: ", t);
        emit(out);
    }
    ptop = save;
    rstate[r] = any ? 3 : 2;
    return any ? 2 : 1;
}

void main() {
    char *a; int k, n;
    a = argstr();
    n = 0;
    while (1) {                 /* the options */
        while (*a == ' ') a++;
        if (*a != '-') break;
        a = argword(a, word, 63);
        if (word[1] == 'n') nflag = 1;
        else if (word[1] == 'B') bflag = 1;
        else if (word[1] == 'f') a = argword(a, file, 63);
        else { puts("usage: make [-n] [-B] [-f file] [target ...]"); osexit(1); }
    }
    load();
    parse();
    if (!nrule) fail("make: no rules in ", file);
    while (1) {                 /* each target named, else the first rule's */
        while (*a == ' ') a++;
        if (*a) a = argword(a, word, 63);
        else if (n) break;
        else strcpy(word, rtgt[0]);
        n++;
        k = make(word);
        if (k == 1 && find(word) != NONE) { putstr("make: "); putstr(word); puts(" is up to date"); }
    }
    if (!hs) { if (!nflag && k == 2) puts("make: nothing to do"); return; }
    fclose(hs);
    osexec("MAKE.SH", 0);
    eputs("make: cannot run MAKE.SH");
    osexit(1);
}
