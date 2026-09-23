/* touch.c - create empty files that do not exist yet: touch name [name ...]
     touch A.TXT B.TXT   each missing name becomes a 0-byte file; an existing file (or directory) is left alone
   Y1/OS keeps no timestamps, so there is nothing to update on an existing file. No globs (a pattern could only
   match files that exist).
   Ported from P8X os/commands/touch.c 2026-09-23, changes: fresolve() for the existence test and
   fcreate()/fclose() for the empty file (the P8X FRESOLVE/FOPEN/FWOPEN/FCLOSE, where DST had to be resolved
   before FWOPEN because they shared a sector buffer); relative names need no abspath; a failure is reported. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
char name[64], ent[32];

void main() {
    char *a; int h;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (a[0] == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: touch name [name ...]   create empty file(s) if missing"); return;
    }
    while (*a) {
        a = argword(a, name, 63);
        if (fresolve(name, ent)) continue;
        h = fcreate(name, 0, 0);
        if (!h) { eput2("touch: cannot create ", name); continue; }
        fclose(h);
    }
}
