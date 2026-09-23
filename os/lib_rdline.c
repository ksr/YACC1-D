/* lib_rdline.c - read one line of the input (Y1/OS, 2026-09-23).
     readline(buf)  the next line into buf (LF ends it and is not stored, CR is dropped, 255 characters kept, the
                    rest of a longer line read and dropped), NUL-terminated; 1 = a line, 0 = the input had ended
   buf must hold 256 bytes. Reads through nextc() from lib_stdin.c (included here).
   Ported from P8X os/commands/lib_rdline.c 2026-09-23, unchanged but for the #include. */
#include "lib_stdin.c"

int readline(char *buf) {
    int n, c;
    n = 0;
    c = nextc();
    if (c == 65535) return 0;
    while (c != 65535 && c != 10) {
        if (c != 13 && n < 255) buf[n++] = c;
        c = nextc();
    }
    buf[n] = 0;
    return 1;
}
