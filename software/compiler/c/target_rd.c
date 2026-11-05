/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* target_rd.c - the source-file reads of io.h on Y1/OS (2026-09-25, from target_io.c): one Y1/OS handle per open
   file. Included by the passes that are not the lexer (target/NAME.c); the lexer, which nests #includes, has
   target_inc.c instead.
   Buffered (2026-09-25): one buffer, iob, IO_RB bytes, filled by READN; it belongs to the handle rh that was read
   first while it had no owner, until that handle is closed. io_getc (target_io.c) takes rc bytes at rp and calls
   io_slow to refill; another handle read meanwhile goes byte by byte (GETC). A pass reads one file at a time: a
   second is only read on the way to an error message (nm_fetch, e_tok), opened, read and closed with no read of the
   first in between, so rc waits in rc1 from that io_open to its io_close and io_getc reaches io_slow for it (io_getc
   does not look at the handle, 2026-11-05). io_skip moves through the buffer a block at a time (the passes skip
   whole function bodies in W.ast). */
char iob[IO_RB];
char rc1;
int io_open(char *path) {
    if (rh) { rc1 = rc; rc = 0; }
    return fopen(path);
}
int io_slow(int h) {
    int n;
    if (h != rh) {
        if (rh) { n = fgetc(h); if (n == 65535) return 256; return n; }    /* the buffer is another handle's */
        rh = h;
    }
    n = freadn(h, iob, IO_RB);
    if (!n) return 256;
    rp = iob + 1; rc = n - 1;
    return iob[0];
}
void io_skip(int h, int n) {    /* (2026-09-25) n bytes read past: through the buffer, a block at a time */
    int k;
    while (n) {
        k = rc;
        if (!k) { io_getc(h); n--; }
        else { if (k > n) k = n; rp = rp + k; rc = rc - k; n = n - k; }
    }
}
void io_close(int h) {
    fclose(h);
    if (h == rh) { rh = 0; rc = 0; } else { rc = rc1; rc1 = 0; }
}
