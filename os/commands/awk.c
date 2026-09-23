/* awk.c - a small awk: one rule over the fields of each line.
     awk [-F c] '[/re/] [{print items}]' [file ...]
   pattern  /regex/ (lib_regex.c: . * + ? ^ $) or none = every line; a pattern with no action prints the line
   action   { print items } or {} = print $0
   items    $0 (the line), $1..$N and $NF (fields), NF, NR, "strings"; separated by commas (a space is printed
            between items) or spaces
   Fields split on runs of spaces/tabs, or on each c with -F c. The program is one argument in ' or " quotes (awk
   strips them: the shell does not); the files after it (globs, "-") are one stream, or the console.
   Ported from P8X os/commands/awk.c 2026-09-23, changes: several input names via lib_stdin.c; the iterative
   lib_regex.c; putnum() from y1lib.c for pnum; y1cc syntax. Still one rule, print only: no BEGIN/END, printf or
   expressions. */
#include "../lib_stdin.c"
#include "../lib_regex.c"
#include "y1lib.c"
#define NFMAX 40
char line[256], re[80], act[120], prog[128];
int fstart[NFMAX], flen[NFMAX], nf, nr, sepc, hasre;

int readrec() {                                 /* the next record into line (CR dropped); 0 = end of input */
    int c, i;
    c = nextc();
    if (c == 65535) return 0;
    i = 0;
    while (c != 65535 && c != 10) { if (c != 13 && i < 255) line[i++] = c; c = nextc(); }
    line[i] = 0;
    return 1;
}

void field(int st, int end) { if (nf < NFMAX) { fstart[nf] = st; flen[nf] = end - st; nf++; } }

void split() {
    int i, st;
    nf = 0; i = 0;
    if (!sepc) {
        while (line[i]) {
            while (line[i] == ' ' || line[i] == 9) i++;
            if (!line[i]) break;
            st = i;
            while (line[i] && line[i] != ' ' && line[i] != 9) i++;
            field(st, i);
        }
        return;
    }
    st = 0;
    while (1) {
        if (!line[i]) { field(st, i); return; }
        if (line[i] == sepc) { field(st, i); st = i + 1; }
        i++;
    }
}

void pfield(int fi) {
    int i;
    if (!fi) { putstr(line); return; }
    if (fi <= nf) for (i = 0; i < flen[fi - 1]; i++) putchar(line[fstart[fi - 1] + i]);
}

void run_action() {
    char *a; int first, fi;
    a = act;
    while (*a == ' ') a++;
    if (!*a) { puts(line); return; }
    if (a[0] == 'p' && a[1] == 'r' && a[2] == 'i' && a[3] == 'n' && a[4] == 't') a += 5;
    first = 1;
    while (*a) {
        while (*a == ' ') a++;
        if (*a == ',') { a++; while (*a == ' ') a++; }
        if (!*a) break;
        if (!first) putchar(' ');
        first = 0;
        if (*a == '"') {
            a++;
            while (*a && *a != '"') putchar(*a++);
            if (*a == '"') a++;
        } else if (*a == '$') {
            a++;
            if (a[0] == 'N' && a[1] == 'F') { a += 2; pfield(nf); }
            else { fi = 0; while (*a >= '0' && *a <= '9') fi = fi * 10 + *a++ - '0'; pfield(fi); }
        } else if (a[0] == 'N' && a[1] == 'R') { a += 2; putnum(nr); }
        else if (a[0] == 'N' && a[1] == 'F') { a += 2; putnum(nf); }
        else a++;                               /* anything else is skipped (as the P8X awk) */
    }
    if (first) putstr(line);                    /* print with no items = $0 */
    putchar(10);
}

void parse_prog(char *p) {
    int i;
    hasre = 0; re[0] = 0; act[0] = 0;
    while (*p == ' ') p++;
    if (*p == '/') {
        p++;
        for (i = 0; *p && *p != '/'; p++) if (i < 79) re[i++] = *p;
        re[i] = 0; hasre = 1;
        if (*p == '/') p++;
    }
    while (*p == ' ') p++;
    if (*p == '{') {
        p++;
        for (i = 0; *p && *p != '}'; p++) if (i < 119) act[i++] = *p;
        act[i] = 0;
    }
}

void main() {
    char *a; int i, q;
    a = argstr();
    sepc = 0;
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: awk [-F c] '[/re/]{print items}' [file ...]   items: $0 $N $NF NF NR \"str\""); return;
    }
    if (a[0] == '-' && a[1] == 'F') {
        a += 2;
        while (*a == ' ') a++;
        sepc = *a;
        if (*a) a++;
        while (*a == ' ') a++;
    }
    i = 0;
    if (*a == 39 || *a == '"') {
        q = *a++;
        while (*a && *a != q) { if (i < 127) prog[i++] = *a; a++; }
        if (*a == q) a++;
    } else while (*a && *a != ' ') { if (i < 127) prog[i++] = *a; a++; }
    prog[i] = 0;
    parse_prog(prog);
    if (openarg(a) == 2) { notfound("awk"); return; }
    sepfiles = 1;
    nr = 0;
    while (readrec()) {
        nr++;
        split();
        if (!hasre || match(re, line)) run_action();
    }
}
