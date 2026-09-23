/* find.c - the paths of the entries whose names match: find pattern [dir]
     find .TXT        every file or directory under the current one whose name CONTAINS ".TXT" (as typed)
     find *.C         ... whose name matches the glob (* and ?, case folded: lib_glob.c)
     find MAN /       ... searching from / instead
   Prints absolute paths, depth first; up to 8 levels (lib_walk.c).
   Ported from P8X os/commands/find.c 2026-09-23, changes: the iterative lib_walk.c for the recursive walk()
   (pre-order: a directory's contents follow it); an optional start directory; absolute paths from lib_apath.c. */
#include "../lib_walk.c"
#include "../lib_glob.c"
#include "../lib_err.c"
#include "y1lib.c"
char pat[64], full[WFLEN];
int isg;

int contains(char *h, char *n) {
    int i, j;
    for (i = 0; h[i]; i++) {
        for (j = 0; n[j] && h[i + j] == n[j]; j++) ;
        if (!n[j]) return 1;
    }
    return 0;
}

void main() {
    char *a; int i;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: find pattern [dir]   paths whose name matches (glob if * or ?, else a substring)"); return;
    }
    isg = 0;
    for (i = 0; *a && *a != ' ' && i < 63; a++) { if (*a == '*' || *a == '?') isg = 1; pat[i++] = *a; }
    pat[i] = 0;
    while (*a && *a != ' ') a++;
    while (*a == ' ') a++;
    if (!walk_open(a)) { eputs("find: not a directory"); return; }
    while (walk_next()) {
        if (isg ? gmatch(pat, wname) : contains(wname, pat)) { walk_full(full); puts(full); }
    }
    if (wtrunc) eputs("find: deeper than 8 levels, not all searched");
}
