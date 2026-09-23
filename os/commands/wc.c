/* wc.c - count lines, words and bytes: "lines words bytes" of the files named, or of the console.
     wc FILE ...    the files (globs expand; "-" = the console) counted as one stream: one line of totals
     wc             the console up to Ctrl-D
   A line is an LF; a word is a run of anything but space, tab, CR, LF. Counts are 32-bit (lib_num.c).
   Ported from P8X os/commands/wc.c 2026-09-23 (it replaces the v0.1 wc, which took one file), changes: several
   names via lib_stdin.c; 32-bit counters as two ints (the P8X 24-bit byte arrays); the console is conin(). */
#include "../lib_stdin.c"
#include "../lib_num.c"
#include "y1lib.c"
int lines[2], words[2], bytes[2];

void main() {
    char *a; int c, inword;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: wc [file|glob|-] ...   count lines words bytes"); return; }
    if (openarg(a) == 2) { notfound("wc"); return; }
    inword = 0;
    while ((c = nextc()) != 65535) {
        inc32(bytes);
        if (c == 10) inc32(lines);
        if (c == ' ' || c == 9 || c == 10 || c == 13) inword = 0;
        else if (!inword) { inword = 1; inc32(words); }
    }
    put32(lines[0], lines[1], 0); putchar(' ');
    put32(words[0], words[1], 0); putchar(' ');
    put32(bytes[0], bytes[1], 0); putchar(10);
}
