/* sort.c - sort lines in ascending byte order: the files named, or the console.
     sort FILE ...    the lines of all of them, sorted, one stream (globs, "-" = the console)
   Holds up to 200 lines of up to 79 characters (longer lines are cut, extra lines dropped with a warning at the
   end); CR is dropped, each file ends a line.
   Ported from P8X os/commands/sort.c 2026-09-23, changes: 200 lines instead of 128 (the Y1 program area is
   32K); an insertion sort of an index array instead of a selection sort that swapped the 80-byte slots; several
   names via lib_stdin.c; says so when lines were dropped. */
#include "../lib_stdin.c"
#include "../lib_err.c"
#include "y1lib.c"
#define NL 200
#define W 80
char lines[NL * W];
int idx[NL];

int lless(char *x, char *y) {                   /* 1 when x sorts before y */
    while (*x && *x == *y) { x++; y++; }
    return *x < *y;
}

void main() {
    char *a; int c, col, n, i, j, t, lost;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: sort [file ...]   sort lines ascending (files or the console)"); return; }
    if (openarg(a) == 2) { notfound("sort"); return; }
    sepfiles = 1;
    n = 0; col = 0; lost = 0;
    while ((c = nextc()) != 65535) {
        if (n >= NL) { if (c == 10) lost = 1; continue; }
        if (c == 10) { lines[n * W + col] = 0; n++; col = 0; }
        else if (c != 13 && col < W - 1) lines[n * W + col++] = c;
    }
    if (col && n < NL) { lines[n * W + col] = 0; n++; }
    for (i = 0; i < n; i++) {                   /* insertion sort of the index (stable) */
        t = idx[i] = i;
        j = i;
        while (j && lless(lines + t * W, lines + idx[j - 1] * W)) { idx[j] = idx[j - 1]; j--; }
        idx[j] = t;
    }
    for (i = 0; i < n; i++) puts(lines + idx[i] * W);
    if (lost) eputs("sort: more than 200 lines, the rest dropped");
}
