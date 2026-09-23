/* sed.c - substitute on every line: sed s/re/new/[g] [file ...]
     sed s/foo/bar/ FILE     the first "foo" of each line becomes "bar"
     sed s/o+/0/g FILE       every match (regex: . * + ? ^ $, lib_regex.c)
     sed s/x/y/              the console up to Ctrl-D
   Only the s command. The replacement is literal; the match replaced is the shortest (* is not greedy); an empty
   match is skipped. Lines and output are cut at 255 characters. Several names (globs, "-") are one stream.
   Ported from P8X os/commands/sed.c 2026-09-23, changes: the iterative lib_regex.c; several names via
   lib_stdin.c; the length of a match is rend - start (y1cc pointers subtract as ints). */
#include "../lib_rdline.c"
#include "../lib_regex.c"
#include "../lib_err.c"
#include "y1lib.c"
char pat[64], rep[64], line[256], out[256];
int anchored;
char *rpat;

int re_at(int i) {                              /* the length of a match at line[i], 0 = none here */
    if (anchored && i) return 0;
    if (!matchhere(rpat, line + i)) return 0;
    return rend - (line + i);
}

void main() {
    char *a; int global, mlen, i, j, n, done;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: sed s/re/new/[g] [file ...]   substitute (regex: . * + ? ^ $)"); return;
    }
    if (a[0] != 's' || a[1] != '/') { eputs("sed: only s/re/new/[g]"); return; }
    a += 2;
    for (i = 0; *a && *a != '/' && i < 63; ) pat[i++] = *a++;
    pat[i] = 0;
    anchored = pat[0] == '^';
    rpat = anchored ? pat + 1 : pat;
    if (*a != '/') { eputs("sed: bad s/// (no second /)"); return; }
    a++;
    for (j = 0; *a && *a != '/' && j < 63; ) rep[j++] = *a++;
    rep[j] = 0;
    global = 0;
    if (*a == '/') { a++; if (*a == 'g' || *a == 'G') { global = 1; a++; } }
    if (openarg(a) == 2) { notfound("sed"); return; }
    sepfiles = 1;
    while (readline(line)) {
        n = 0; i = 0; done = 0;
        while (line[i]) {
            mlen = (global || !done) ? re_at(i) : 0;
            if (mlen) {
                for (j = 0; rep[j] && n < 255; j++) out[n++] = rep[j];
                i += mlen;
                if (!global) done = 1;
            } else {
                if (n < 255) out[n++] = line[i];
                i++;
            }
        }
        out[n] = 0;
        puts(out);
    }
}
