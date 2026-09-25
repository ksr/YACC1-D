/* target_rd.c - the source-file reads of io.h on Y1/OS (2026-09-25, from target_io.c): one Y1/OS handle per open
   file. Included by the passes that are not the lexer (target/NAME.c); the lexer, which nests #includes, has
   target_inc.c instead.
   Buffered (2026-09-25): one buffer, iob, IO_RB bytes, filled by READN; it belongs to the handle rh that was read
   first while it had no owner, until that handle is closed. io_getc (target_io.c) takes rh's bytes from rp..re and
   calls io_slow to refill; another handle read meanwhile goes byte by byte (GETC). A pass reads one file at a time:
   a second is only read on the way to an error message (nm_fetch). io_skip moves through the buffer a block at a
   time (the passes skip whole function bodies in W.ast). */
char iob[IO_RB];
int io_open(char *path) { return fopen(path); }
int io_slow(int h) {
    int n;
    if (h != rh) {
        if (rh) { n = fgetc(h); if (n == 65535) return 256; return n; }    /* the buffer is another handle's */
        rh = h;
    }
    n = freadn(h, iob, IO_RB);
    rp = iob; re = iob + n;
    if (!n) return 256;
    rp = iob + 1;
    return iob[0];
}
void io_skip(int h, int n) {    /* (2026-09-25) n bytes read past: through the buffer, a block at a time */
    int k;
    while (n) {
        k = re - rp;
        if (h != rh || !k) { io_getc(h); n--; }
        else { if (k > n) k = n; rp = rp + k; n = n - k; }
    }
}
void io_close(int h) {
    fclose(h);
    if (h == rh) { rh = 0; rp = re; }
}
