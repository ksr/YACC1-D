/* cat.c - print files, or copy the console to the output: the plain filter.
     cat FILE ...     each file in turn (globs such as *.TXT or /MAN/C* expand to the matching files)
     cat A - B        "-" is the console: A, then what is typed up to Ctrl-D, then B
     cat              the console up to Ctrl-D
   Byte-exact: nothing is added or dropped. Up to 24 names (after glob expansion) per command.
   Ported from P8X os/commands/cat.c 2026-09-23, changes: several files and globs in any mix and "-" for the console
   come from lib_stdin.c (the P8X cat parsed its own words and read the console with getchar); no FSDIRBUF page
   juggling (every Y1/OS handle has its own buffer); fopen/fgetc through lib_fs.c. Replaces the v0.1 test command
   cat2 (sector reads) and, while /BIN/CAT exists, the shell's built-in cat (still there as `type`). */
#include "../lib_stdin.c"
#include "y1lib.c"

void main() {
    char *a; int c;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: cat [file|glob|-] ...   print files, or the console"); return; }
    if (openarg(a) == 2) { notfound("cat"); return; }
    while ((c = nextc()) != 65535) putchar(c);
}
