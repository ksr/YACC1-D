/* diff.c - the lines that differ between two files: diff file1 file2
     prints the lines only in file1 as "< line" and then those only in file2 as "> line"; nothing when equal
   It skips the common leading and trailing lines and reports the block between them: one changed, inserted or
   deleted block is exact, several changes come out as one block spanning them (not a minimal LCS diff).
   Each file is held in memory: up to 150 lines of up to 79 characters (CR dropped, longer lines cut; a longer
   file is compared on its first 150 lines, with a warning).
   Ported from P8X os/commands/diff.c 2026-09-23, changes: 150 lines per file instead of 96 (2 x 12,000 bytes in
   the 32K program area); fopen/fgetc through lib_fs.c (relative names need no abspath); the warning is new. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
#define NL 150
#define W 80
char alines[NL * W], blines[NL * W];
char n1[64], n2[64];
int big;

int loadlines(char *name, char *buf) {          /* the file's lines into buf; the count, 65535 = not found */
    int h, n, col, c;
    h = fopen(name);
    if (!h) return 65535;
    n = 0; col = 0;
    while ((c = fgetc(h)) != 65535) {
        if (n >= NL) { big = 1; break; }
        if (c == 10) { buf[n * W + col] = 0; n++; col = 0; }
        else if (c != 13 && col < W - 1) buf[n * W + col++] = c;
    }
    if (col && n < NL) { buf[n * W + col] = 0; n++; }
    fclose(h);
    return n;
}

void emit(char *tag, char *buf, int i) { putstr(tag); puts(buf + i * W); }

void main() {
    char *a; int na, nb, p, sa, sb, i;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: diff file1 file2   show differing lines (< file1, > file2)"); return;
    }
    a = argword(a, n1, 63);
    a = argword(a, n2, 63);
    if (!*n2) { eputs("usage: diff file1 file2"); return; }
    big = 0;
    na = loadlines(n1, alines);
    if (na == 65535) { eputs("diff: file1 not found"); return; }
    nb = loadlines(n2, blines);
    if (nb == 65535) { eputs("diff: file2 not found"); return; }
    p = 0;
    while (p < na && p < nb && !strcmp(alines + p * W, blines + p * W)) p++;
    sa = na; sb = nb;
    while (sa > p && sb > p && !strcmp(alines + (sa - 1) * W, blines + (sb - 1) * W)) { sa--; sb--; }
    for (i = p; i < sa; i++) emit("< ", alines, i);
    for (i = p; i < sb; i++) emit("> ", blines, i);
    if (big) eputs("diff: only the first 150 lines were compared");
}
