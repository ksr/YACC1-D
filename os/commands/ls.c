/* ls.c - list a directory through the OS file API (2026-09-23): opendir / readdir and the entry accessors.
     ls [PATH]   name, <DIR> or the size, the load address of a program, then the count ('.' and '..' skipped) */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
char ent[32];
char nm[13];

void main() {
    int h, n; char *a;
    a = argstr();
    while (*a == ' ') a++;
    if (*a && !fresolve(a, ent)) { eputs("ls: not found"); return; }
    h = opendir(a);
    if (!h) { eputs("ls: not a directory"); return; }
    n = 0;
    while (readdir(h, ent)) {
        ent_name(ent, nm);
        if (nm[0] == '.') continue;
        putstr(nm); putchar(' ');
        if (ent_isdir(ent)) putstr("<DIR>");
        else { putnum(ent_len(ent)); if (ent_load(ent)) { putstr("  @"); puthex(ent_load(ent)); } }
        putchar(10); n++;
    }
    fclose(h);
    putnum(n); puts(" entries");
}
