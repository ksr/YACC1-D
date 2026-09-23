/* cp.c - copy a file (2026-09-23): the P8X `cp` shape on the Y1/OS API. Keeps the load and exec addresses, so a
   copied /BIN program still runs.
     cp SRC DST */
#include "../lib_fs.c"
#include "y1lib.c"
char buf[512];
char src[64], dst[64], ent[32];

void main() {
    int in, out, n, total; char *a;
    a = argstr();
    a = argword(a, src, 63);
    a = argword(a, dst, 63);
    if (!*src || !*dst) { puts("usage: cp src dst"); return; }
    if (!fresolve(src, ent) || !ent_isfile(ent)) { puts("cp: source not found"); return; }
    in = fopen(src);
    if (!in) { puts("cp: cannot open source"); return; }
    out = fcreate(dst, ent_load(ent), ent_exec(ent));
    if (!out) { fclose(in); puts("cp: cannot create destination"); return; }
    total = 0;
    while ((n = fread(in, buf))) {
        if (fwrite(out, buf, n) != n) { puts("cp: write error"); break; }
        total += n;
    }
    fclose(in);
    if (!fclose(out)) { puts("cp: close error"); return; }
    putstr("copied "); putnum(total); puts(" bytes");
}
