/* tree.c - the directory tree, depth first and indented: tree [dir]
     tree        everything under the current directory: two spaces per level, a '/' after a directory
     tree /BIN   under that directory
   Up to 8 levels (lib_walk.c): a deeper directory is shown but not entered, and a note says so at the end.
   Ported from P8X os/commands/tree.c 2026-09-23, changes: the recursive walk() is the iterative lib_walk.c (y1cc
   has no recursion), so the order is true pre-order (a directory's contents right under it; the P8X listed a
   whole level before any subdirectory because the BIOS FNEXT cursor was global); an optional start directory. */
#include "../lib_walk.c"
#include "../lib_err.c"
#include "y1lib.c"

void main() {
    char *a; int i;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: tree [dir]   the directory tree, indented"); return; }
    if (!walk_open(a)) { eputs("tree: not a directory"); return; }
    while (walk_next()) {
        for (i = 0; i < wlev; i++) putstr("  ");
        putstr(wname);
        if (wdown) putchar('/');
        putchar(10);
    }
    if (wtrunc) eputs("tree: deeper than 8 levels, not all shown");
}
