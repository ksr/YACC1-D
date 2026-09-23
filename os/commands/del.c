/* del.c - delete files: del name [name ...]
     del A.TXT /T/B.TXT   tombstone each file (the sectors come back with /BIN/PACK)
     del *.BAK            a glob deletes every matching file in that directory
   Files only: a directory is removed with the shell's rmdir.
   Ported from P8X os/commands/del.c 2026-09-23, changes: fdelete() (the P8X FRESOLVE + FDELETE and its carry
   test); globs are new (lib_globx.c); the message names the file. Replaces the shell's built-in del while
   /BIN/DEL exists. */
#include "../lib_globx.c"
#include "../lib_err.c"
#include "y1lib.c"
char name[64];
char gl[24 * GSLOT];

void del1(char *p) { if (!fdelete(p)) { eput2("del: not a file: ", p); } }

void main() {
    char *a; int n, i;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: del name|glob ...   delete file(s)"); return;
    }
    while (*a) {
        if (isglob(a)) {
            n = glob_expand(a, gl, 24);
            a = argword(a, name, 63);
            if (!n) { eput2("del: no match: ", name); continue; }
            for (i = 0; i < n; i++) del1(gl + i * GSLOT);
        } else {
            a = argword(a, name, 63);
            del1(name);
        }
    }
}
