/* grep.c - print the lines that match a regular expression: grep [-r] regex [file ...]
     grep ^al FILE        lines of FILE that start with "al" (regex: . * + ? ^ $, lib_regex.c)
     grep x.*y *.TXT      every matching file; with more than one file each line is prefixed "NAME:"
     grep be.a            the console up to Ctrl-D
     grep -r alpha [dir]  every file under the current directory (or dir), depth first, up to 8 levels:
                          "PATH:line" for each match
   The regex is the first word (no quotes are needed or stripped: a space ends it); lines are cut at 255
   characters; each file ends a line.
   Ported from P8X os/commands/grep.c 2026-09-23, changes: the recursive collect() of -r is lib_walk.c, and the
   files are searched as the walk finds them (the P8X gathered at most 36 paths first, because opening a file
   mid-walk clobbered the global FNEXT cursor); -r takes a start directory; several file names (not just one
   file or glob) via lib_stdin.c, with the NAME: prefix when there are several; the iterative lib_regex.c. */
#include "../lib_rdline.c"
#include "../lib_regex.c"
#include "../lib_walk.c"
#include "../lib_err.c"
#include "y1lib.c"
char re[64], line[256], full[WFLEN];

void grep_stream(int pfx) {                     /* the open lib_stdin stream; pfx = print "name:" first */
    while (readline(line)) {
        if (!match(re, line)) continue;
        if (pfx) { putstr(curname); putchar(':'); }
        puts(line);
    }
}

void main() {
    char *a; int i, rec;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: grep [-r] regex [file ...|dir]   lines matching regex (. * + ? ^ $); -r searches a tree"); return;
    }
    rec = 0;
    if (a[0] == '-' && a[1] == 'r') { rec = 1; a += 2; while (*a == ' ') a++; }
    for (i = 0; *a && *a != ' ' && i < 63; ) re[i++] = *a++;
    re[i] = 0;
    if (!re[0]) { eputs("usage: grep [-r] regex [file ...|dir]"); return; }
    while (*a && *a != ' ') a++;
    while (*a == ' ') a++;
    sepfiles = 1;
    if (!rec) {
        if (openarg(a) == 2) { notfound("grep"); return; }
        grep_stream(gnf > 1);
        return;
    }
    if (!walk_open(a)) { eputs("grep: not a directory"); return; }
    while (walk_next()) {
        if (!ent_isfile(went)) continue;
        walk_full(full);
        if (strlen(full) >= GSLOT) continue;    /* a path too long for lib_stdin's slot */
        strcpy(gfiles, full); gnf = 1; gidx = 0; ginh = 0;    /* one-file stream for nextc() */
        grep_stream(1);
    }
    if (wtrunc) eputs("grep: deeper than 8 levels, not all searched");
}
