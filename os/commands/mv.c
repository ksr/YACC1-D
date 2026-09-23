/* mv.c - move or rename files: mv src dst
     mv OLD.TXT NEW.TXT    rename in place (the directory entry is renamed: nothing is copied)
     mv A.TXT /T           into a directory: /T/A.TXT
     mv A.TXT /T/B.TXT     to another directory: copied (load/exec kept) and the source deleted
     mv *.TMP /T           a glob: every matching file into the directory /T
     mv DIR NEWNAME        a directory is renamed in place; it cannot move to another directory
   An existing file of the target name is replaced. mv X X is refused (it would delete the only copy).
   Ported from P8X os/commands/mv.c 2026-09-23, changes: a move within one directory is Y1/OS's RENAME syscall
   (P8XFS on the P8X had no rename, so mv was always copy + delete); a move across directories is still copy +
   delete, now keeping the load/exec addresses; directories can be renamed; "into a directory" works for one
   file too (the P8X only for globs); lib_apath.c's normalised paths decide "same file" and "same directory". */
#include "../lib_globx.c"
#include "../lib_apath.c"
#include "../lib_err.c"
#include "y1lib.c"
char srcw[64], dstw[64], src[APLEN], dst[APLEN], tgt[APLEN], ent[32], buf[512];
char gl[24 * GSLOT];

char *leafof(char *p) { char *l; l = p; while (*p) { if (*p == '/') l = p + 1; p++; } return l; }

int samedir(char *a, char *b) {                 /* absolute paths: is everything before the last '/' equal? */
    int la, lb;
    la = leafof(a) - a; lb = leafof(b) - b;
    if (la != lb) return 0;
    while (la) { la--; if (a[la] != b[la]) return 0; }
    return 1;
}

int copy1(char *s, char *d) {                   /* copy file s to d keeping load/exec; 1 ok */
    int in, out, n, ok;
    if (!fresolve(s, ent)) return 0;
    in = fopen(s);
    if (!in) return 0;
    out = fcreate(d, ent_load(ent), ent_exec(ent));
    if (!out) { fclose(in); return 0; }
    ok = 1;
    while ((n = fread(in, buf))) if (fwrite(out, buf, n) != n) { ok = 0; break; }
    fclose(in);
    if (!fclose(out)) ok = 0;
    return ok;
}

void move1(char *sw, int intodir) {             /* move the word sw to dst (or into the directory dst) */
    abspath(src, sw);
    if (!fresolve(src, ent)) { eput2("mv: not found: ", sw); return; }
    if (intodir) {
        strcpy(tgt, dst);
        if (strlen(tgt) > 1) strcpy(tgt + strlen(tgt), "/");
        strcpy(tgt + strlen(tgt), leafof(src));
    } else strcpy(tgt, dst);
    if (!strcmp(src, tgt)) { eput2("mv: same file: ", sw); return; }
    if (samedir(src, tgt)) {
        if (fresolve(tgt, ent)) {               /* the new name is taken: a file is replaced */
            if (!ent_isfile(ent) || !fdelete(tgt)) { eput2("mv: cannot replace ", tgt); return; }
        }
        if (!frename(src, leafof(tgt))) { eput2("mv: cannot rename ", sw); }
        return;
    }
    fresolve(src, ent);
    if (!ent_isfile(ent)) { eput2("mv: a directory moves only within its directory: ", sw); return; }
    if (!copy1(src, tgt)) { eput2("mv: cannot copy to ", tgt); return; }
    fdelete(src);
}

void main() {
    char *a; int n, i, into;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: mv src dst   move/rename a file (or a glob into a directory)"); return;
    }
    n = isglob(a) ? glob_expand(a, gl, 24) : 65535;
    a = argword(a, srcw, 63);
    a = argword(a, dstw, 63);
    if (!*dstw) { eputs("usage: mv src dst"); return; }
    abspath(dst, dstw);
    into = fresolve(dst, ent) && ent_isdir(ent);
    if (n == 65535) { move1(srcw, into); return; }
    if (!into) { eputs("mv: the target of a glob must be a directory"); return; }
    if (!n) { eput2("mv: no match: ", srcw); return; }
    for (i = 0; i < n; i++) move1(gl + i * GSLOT, 1);
}
