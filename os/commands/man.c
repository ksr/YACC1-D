/* man.c - show a manual page: man name  ->  the text of /MAN/NAME, a screen at a time.
     man cat      the page for cat (the name is upper-cased: the Makefile installs the pages as /MAN/CAT ...)
     man man      this command's own page
     man          the list of pages (the names in /MAN)
   The pager is lib_more.c: 23 lines, then --More-- and a key (conin): space = next page, Enter = one line, q = quit.
   Ported from P8X os/commands/man.c 2026-09-23, changes: /MAN instead of /man and the name upper-cased (Y1/OS
   names are case-sensitive, the command word is not); the page goes through the --More-- pager (the P8X streamed
   it whole); no argument lists the pages instead of printing usage; fopen/fgetc from lib_fs.c. */
#include "../lib_fs.c"
#include "../lib_more.c"
#include "../lib_err.c"
#include "y1lib.c"
char path[32], ent[32], nm[13];

void main() {
    char *a; int h, c, i, col;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: man [name]   show the manual page for a command"); return; }
    if (!*a) {                                  /* the index */
        h = opendir("/MAN");
        if (!h) { eputs("man: no /MAN directory"); return; }
        col = 0;
        while (!pgquit && readdir(h, ent)) {
            ent_name(ent, nm);
            if (nm[0] == '.' || !ent_isfile(ent)) continue;
            for (i = 0; nm[i]; i++) pgc(nm[i] >= 'A' && nm[i] <= 'Z' ? nm[i] + 32 : nm[i]);
            col++;
            if (col == 6) { pgc(10); col = 0; } else for (; i < 13; i++) pgc(' ');
        }
        if (col) pgc(10);
        fclose(h);
        return;
    }
    strcpy(path, "/MAN/");
    for (i = 5; *a && *a != ' ' && i < 17; a++) path[i++] = *a >= 'a' && *a <= 'z' ? *a - 32 : *a;
    path[i] = 0;
    h = fopen(path);
    if (!h) { eput2("no manual entry for ", path + 5); return; }
    while (!pgquit && (c = fgetc(h)) != 65535) pgc(c);
    fclose(h);
}
