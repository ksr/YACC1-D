/* cat2.c - print files through the OS file API (2026-09-23): the first command written with lib_fs.c.
     cat2 PATH [PATH...]   each file, sector-wise (fopen / fread / fclose)
     cat2                  no argument: copy the console to the output until Ctrl-D (conin), the filter shape
   The shell's own `cat` walks the same OS code, so the two must print the same. */
#include "../lib_fs.c"
#include "y1lib.c"
char buf[512];
char name[64];

void catfile(char *path) {
    int h, n, i;
    h = fopen(path);
    if (!h) { putstr("cat2: not found: "); puts(path); return; }
    while ((n = fread(h, buf))) for (i = 0; i < n; i++) putchar(buf[i]);
    fclose(h);
}

void main() {
    char *a; int c;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a) {
        while ((c = conin()) != 65535) putchar(c);
        return;
    }
    while (*a) { a = argword(a, name, 63); catfile(name); }
}
