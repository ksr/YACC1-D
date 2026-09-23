/* more.c - page the files named, or the console, 23 lines at a time.
     more FILE ...   after each 23 lines: --More-- and a key (conin, no echo): space = the next page,
                     Enter = one more line, q = quit
   Several names (globs, "-") are one stream. With no file the text AND the keys come from the console (Y1/OS has
   no pipes yet), so `more` alone is only a curiosity.
   Ported from P8X os/commands/more.c 2026-09-23, changes: the pager itself moved to lib_more.c (man and md share
   it); several names via lib_stdin.c; Enter is CR or LF. */
#include "../lib_stdin.c"
#include "../lib_more.c"
#include "y1lib.c"

void main() {
    char *a; int c;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: more [file ...]   page files (space=next, Enter=line, q=quit)"); return; }
    if (openarg(a) == 2) { notfound("more"); return; }
    while (!pgquit && (c = nextc()) != 65535) pgc(c);
}
