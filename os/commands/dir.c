/* dir.c - list a directory, sorted: dir [-R] [-S] [path|glob]
     dir              the current directory, by name
     dir /BIN         a directory by path;  dir FILE  that one file's line
     dir *.TXT        the entries matching a glob (* and ?, case folded), here or in dir/*.X
     dir -S           largest first (directories count as 0), ties by name
     dir -R           the directory, then every directory below it (depth first, up to 8 levels) as a block of
                      its own under a "/PATH:" header, the glob filtering every level
   Each line: the size right-justified in 7 columns (blank for a directory), two spaces, the name ('/' after a
   directory), and "@AAAA" = the load address of a file that has one. Up to 64 entries per directory are sorted
   (a fresh directory holds 62); the rest are dropped with a note. Sizes are 32-bit (lib_num.c).
   Ported from P8X os/commands/dir.c 2026-09-23, changes: the recursive walk() is lib_walk.c and -R prints
   ls -R style blocks with a header each (the P8X interleaved indented levels, streaming a level before its
   subdirectories because the FNEXT cursor was global); the load-address column of the Y1/OS built-in dir is
   added; opendir/readdir handles for FOPENDIR/SYS_OPENCWD/FNEXT/SYS_DIRENTRY/FSDIRBUF; a sort index of chars
   stays. Replaces the shell's built-in dir while /BIN/DIR exists. */
#include "../lib_walk.c"
#include "../lib_globx.c"
#include "../lib_num.c"
#include "../lib_err.c"
#include "y1lib.c"
#define NE 64
char enam[NE * 13], eisd[NE], eidx[NE], ehi[NE];
int elen[NE], eload[NE];
int ecnt, szmode, lost;
char gpat[16], tnm[13], ent[32], dbuf[APLEN], full[WFLEN];

int before(int a, int b) {                      /* entry a sorts before entry b */
    int ha, hb, la, lb;
    if (szmode) {
        ha = eisd[a] ? 0 : ehi[a]; hb = eisd[b] ? 0 : ehi[b];
        if (ha != hb) return ha > hb;
        la = eisd[a] ? 0 : elen[a]; lb = eisd[b] ? 0 : elen[b];
        if (la != lb) return la > lb;
    }
    return strcmp(enam + a * 13, enam + b * 13) == 65535;
}

int collect(char *path) {                       /* the entries of a directory, sorted into eidx; 0 = not a dir */
    int h, k, i, j, t;
    h = opendir(path);
    if (!h) return 0;
    k = 0;
    while (readdir(h, ent)) {
        ent_name(ent, tnm);
        if (tnm[0] == '.' && (!tnm[1] || (tnm[1] == '.' && !tnm[2]))) continue;
        if (gpat[0] && !gmatch(gpat, tnm)) continue;
        if (k >= NE) { lost = 1; continue; }
        strcpy(enam + k * 13, tnm);
        eisd[k] = ent_isdir(ent); elen[k] = ent_len(ent); ehi[k] = ent[18]; eload[k] = ent_load(ent);
        k++;
    }
    fclose(h);
    ecnt = k;
    for (i = 0; i < k; i++) {                   /* insertion sort of the index */
        t = i; j = i;
        while (j && before(t, eidx[j - 1])) { eidx[j] = eidx[j - 1]; j--; }
        eidx[j] = t;
    }
    return 1;
}

void show(int m) {
    if (eisd[m]) putstr("       "); else put32(ehi[m], elen[m], 7);
    putstr("  ");
    putstr(enam + m * 13);
    if (eisd[m]) putchar('/');
    else if (eload[m]) { putstr("  @"); puthex(eload[m]); }
    putchar(10);
}

void listing() { int i; for (i = 0; i < ecnt; i++) show(eidx[i]); }

void main() {
    char *a, *w; int rec, i, last, n;
    a = argstr();
    rec = 0; szmode = 0; lost = 0; gpat[0] = 0;
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) {
        puts("usage: dir [-R] [-S] [path|glob]   list a directory sorted; -S by size; -R the tree"); return;
    }
    while (a[0] == '-' && (a[1] == 'R' || a[1] == 'r' || a[1] == 'S' || a[1] == 's')) {
        if (a[1] == 'R' || a[1] == 'r') rec = 1; else szmode = 1;
        a += 2;
        while (*a == ' ') a++;
    }
    n = 0; last = 65535;                        /* the path word: its last '/' */
    for (w = a; *w && *w != ' '; w++) { if (*w == '/') last = n; n++; }
    for (i = 0; i < n && i < APLEN - 1; i++) dbuf[i] = a[i];
    dbuf[i] = 0;
    if (isglob(a)) {                            /* dir part + pattern */
        i = last == 65535 ? 0 : last + 1;
        strcpy(gpat, ""); if (n - i < 16) { strcpy(gpat, dbuf + i); }
        if (!gpat[0]) strcpy(gpat, "?????????????");  /* an over-long pattern: 13 characters match no name */
        dbuf[i] = 0;
    } else if (n && (!fresolve(dbuf, ent) || !ent_isdir(ent))) {
        if (!fresolve(dbuf, ent)) { eputs("dir: not found"); return; }
        ent_name(ent, enam); eisd[0] = 0;         /* a file: its own line, from its entry */ elen[0] = ent_len(ent); ehi[0] = ent[18]; eload[0] = ent_load(ent);
        show(0);
        return;
    }
    if (!collect(dbuf)) { eputs("dir: not found"); return; }
    listing();
    if (rec) {
        if (!walk_open(dbuf)) return;
        while (walk_next()) {
            if (!wdown) continue;
            walk_full(full);
            collect(full);
            putchar(10); putstr(full); puts(":");
            listing();
        }
        if (wtrunc) eputs("dir: deeper than 8 levels, not all shown");
    }
    if (lost) eputs("dir: over 64 entries in a directory, the rest not shown");
}
