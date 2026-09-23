/* cp.c - copy files, or a directory tree: cp [-r] src dst
     cp A.TXT B.TXT       a copy of the file (its load and exec addresses kept, so a copied program runs)
     cp A.TXT /T          into a directory: /T/A.TXT
     cp *.TXT /T          a glob: every matching file into the directory /T
     cp -r /SRC /DST      the directory /SRC and everything below it (up to 8 levels) as /DST, which is made if
                          it does not exist; files are replaced, directories reused
   Quiet when it works; copying a file onto itself or a tree into itself is refused.
   Ported from P8X os/commands/cp.c 2026-09-23 (it replaces the v0.1 cp, one file, which printed the byte
   count), changes: the recursive copy_tree() is the iterative lib_walk.c, whose single directory handle leaves
   room for the read and the write handle of each copy (the P8X recorded each level's entries before recursing,
   because FNEXT was global); load/exec are kept (the P8X wrote 0/0); a single file can go into a directory;
   sector-wise fread/fwrite instead of FGETB/FPUTB. */
#include "../lib_globx.c"
#include "../lib_walk.c"
#include "../lib_err.c"
#include "y1lib.c"
char srcw[64], dstw[64], src[APLEN], dst[APLEN], tgt[WFLEN + APLEN], full[WFLEN], ent[32], buf[512];
char gl[24 * GSLOT];
int bad;

int isdir(char *p) { return fresolve(p, ent) && ent_isdir(ent); }

void copy1(char *s, char *d) {                  /* copy file s to d keeping load/exec (both absolute) */
    int in, out, n;
    if (!strcmp(s, d)) { eput2("cp: same file: ", s); bad = 1; return; }
    if (!fresolve(s, ent) || !ent_isfile(ent)) { eput2("cp: not a file: ", s); bad = 1; return; }
    in = fopen(s);
    if (!in) { eput2("cp: cannot open ", s); bad = 1; return; }
    out = fcreate(d, ent_load(ent), ent_exec(ent));
    if (!out) { fclose(in); eput2("cp: cannot create ", d); bad = 1; return; }
    while ((n = fread(in, buf))) if (fwrite(out, buf, n) != n) { eput2("cp: write error: ", d); bad = 1; break; }
    fclose(in);
    if (!fclose(out)) { eput2("cp: cannot close ", d); bad = 1; }
}

void into(char *d, char *s) {                   /* tgt = d + "/" + the last component of s */
    char *l; int n;
    l = s; while (*s) { if (*s == '/') l = s + 1; s++; }
    strcpy(tgt, d); n = strlen(tgt);
    if (n > 1) tgt[n++] = '/';
    strcpy(tgt + n, l);
}

void tree() {                                   /* cp -r src dst (both absolute; src a directory) */
    int n;
    n = strlen(src);
    if (!strcmp(src, dst) || (!strncmp(dst, src, n) && (dst[n] == '/' || n == 1))) { eputs("cp: cannot copy a directory into itself"); return; }
    if (!isdir(dst) && !fmkdir(dst)) { eput2("cp: cannot make ", dst); return; }
    if (!walk_open(src)) return;
    while (walk_next()) {
        walk_full(full);
        strcpy(tgt, dst); strcpy(tgt + strlen(tgt), full + n);   /* dst + the part below src */
        if (wdown) {
            if (!isdir(tgt) && !fmkdir(tgt)) { eput2("cp: cannot make ", tgt); wdown = 0; bad = 1; }
        } else copy1(full, tgt);
    }
    if (wtrunc) eputs("cp: deeper than 8 levels, not all copied");
}

int strncmp(char *a, char *b, int n) { while (n && *a && *a == *b) { a++; b++; n--; } return n && *a != *b; }

void main() {
    char *a; int n, i, rec;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) {
        puts("usage: cp [-r] src dst   copy a file or glob (into a directory), -r a directory tree"); return;
    }
    rec = 0;
    if (a[0] == '-' && (a[1] == 'r' || a[1] == 'R')) { rec = 1; a += 2; while (*a == ' ') a++; }
    n = isglob(a) ? glob_expand(a, gl, 24) : 65535;
    a = argword(a, srcw, 63);
    a = argword(a, dstw, 63);
    if (!*dstw) { eputs("usage: cp [-r] src dst"); return; }
    abspath(dst, dstw);
    bad = 0;
    if (n != 65535) {                           /* a glob: files into a directory */
        if (!isdir(dst)) { eputs("cp: the target of a glob must be a directory"); return; }
        if (!n) { eput2("cp: no match: ", srcw); return; }
        for (i = 0; i < n; i++) { abspath(src, gl + i * GSLOT); into(dst, src); copy1(src, tgt); }
        return;
    }
    abspath(src, srcw);
    if (!fresolve(src, ent)) { eput2("cp: not found: ", srcw); return; }
    if (ent_isdir(ent)) {
        if (!rec) { eput2("cp: a directory (use -r): ", srcw); return; }
        tree();
        return;
    }
    if (isdir(dst)) { into(dst, src); copy1(src, tgt); }
    else copy1(src, dst);                       /* (dst is absolute too: copy1 refuses cp X X) */
}
