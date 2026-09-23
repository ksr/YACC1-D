/* uniq.c - drop adjacent repeated lines: the files named, or the console.
     uniq FILE ...    each line unless it equals the one before (sort first to drop every repeat)
   Lines are cut at 255 characters (lib_rdline.c).
   Ported from P8X os/commands/uniq.c 2026-09-23, changes: strcmp() from y1lib.c for lib_streq; strcpy for the
   copy loop; several names via lib_stdin.c. */
#include "../lib_rdline.c"
#include "y1lib.c"
char cur[256], prev[256];

void main() {
    char *a; int first;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: uniq [file ...]   collapse adjacent duplicate lines"); return; }
    if (openarg(a) == 2) { notfound("uniq"); return; }
    sepfiles = 1;
    first = 1;
    while (readline(cur)) {
        if (first || strcmp(cur, prev)) puts(cur);
        strcpy(prev, cur);
        first = 0;
    }
}
