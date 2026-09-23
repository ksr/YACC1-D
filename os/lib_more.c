/* lib_more.c - the --More-- pager shared by more, man and md (Y1/OS, 2026-09-23).
     pgc(c)    print c; after every PGLINES (23) line feeds show "--More--" and wait for a key (conin, no echo):
               space or any other key = the next page, Enter = one more line, q or Q = quit (pgquit = 1, and pgc prints
               nothing more), Ctrl-D (end of console input) = quit too
     pgs(s)    pgc() over a string
   A screen is 24 lines: 23 of text and the prompt line, which is wiped (CR, spaces, CR) after the key.
   pgquit     1 once the reader quit: stop producing output
   Ported from the P8X more.c prompt() 2026-09-23 (there it lived in more, and md had a copy of its own at 22
   lines); the Enter key is CR or LF here, since the emulators deliver a session's line ends as LF. */
#include "lib_fs.c"
#define PGLINES 23
int pgrows, pgquit;

void pgc(int c) {
    int k; char *m;
    if (pgquit) return;
    putchar(c);
    if (c != 10) return;
    pgrows++;
    if (pgrows < PGLINES) return;
    for (m = "--More--"; *m; m++) putchar(*m);
    k = conin();
    for (m = "\r        \r"; *m; m++) putchar(*m);
    if (k == 'q' || k == 'Q' || k == 65535) pgquit = 1;
    pgrows = (k == 13 || k == 10) ? PGLINES - 1 : 0;
}

void pgs(char *s) { while (*s) pgc(*s++); }
