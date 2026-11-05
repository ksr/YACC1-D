/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* target_io.c - io.h for Y1/OS (2026-09-24), in the y1cc subset: the file syscalls through os/lib_fs.c. Every pass
   of the native compiler is built with it (target/NAME.c), and y1cc.c is compiled with it for the self-compile proof
   (target.c). First run 2026-09-25 (tests/native/run.py). Its choices:
   - the command line is the tail argstr() hands a program, split into words at spaces;
   - #include "name" looks beside the including file, then in /lib (the name as written: #include "y1lib.c" finds
     /lib/y1lib.c; until 2026-11-03 upper-cased, /LIB/Y1LIB.C); cc9 reads the runtime text from /lib/y1ccrt.txt;
   - the source files are read through io_open/io_getc/io_close: io_getc is here, the rest is NOT: target_rd.c has
     the plain ones (each a handle) and target_inc.c those of the lexer, which nests #includes deeper than Y1/OS's
     handles allow; each target/NAME.c includes one of them;
   - buffered (2026-09-25): io_getc takes the next byte from the buffer of the handle read last (rh: rc bytes at rp)
     and calls io_slow (target_rd.c / target_inc.c) only to switch handles or to refill, with the syscall READN (up
     to IO_RB bytes, never past a sector); io_wput collects IO_WB bytes for one WRITE. A syscall per byte (GETC, PUTC)
     was most of a compile's time. IO_RB and IO_WB are in each pass's ylim/NAME.h, at most 128 (RAM: 4 * IO_RB +
     IO_WB bytes; the output and every open file are the same bytes as before);
   - counted (2026-11-05): io_getc was 840 clocks a byte, most of them comparing h with rh and rp with an end pointer
     (16 bits, two loads each). rc and wc, one byte each, are the bytes left, so the fast path tests one byte and
     does not look at h: rc is non-zero only for the handle being read, because a switch of file empties it first
     (io_open and io_close, in target_rd.c and target_inc.c). ri and wi live here and move a word whole with
     peekw/pokew: words are big-endian in memory and in the work files;
   - the three output sections of y1cc.c (io_create/io_put/io_finish) are in target_sec.c, which only target.c
     includes (the passes write their files with io_wopen/io_wput/io_wclose and would only carry its buffers);
   - there is no clock, so the header's date is 0000-00-00 00:00;
   - a pass that is done EXECs the next one (2026-09-25): target/NAME.c names it in io_next_pass ("/lib/cc/cc2" ...,
     "" for the last), and the next pass gets the work prefix, this pass's first word, as its whole command line;
     io_fail prints its message on the screen (lib_err.c: never into a > file) and EXITs with status 1, which ends
     the chain; io_done (a pass that deferred an error to a later pass) goes on to the next pass like a normal end. */
#include "../../../os/lib_fs.c"
#include "../../../os/lib_err.c"

char targs[128];

void y1cc_main(void);

void io_next(void);

void main() { y1cc_main(); io_next(); }

int io_argc(void) {
    char *a; int n;
    n = 0;
    a = argstr();
    for (;;) {
        a = argword(a, targs, 127);
        if (!targs[0]) return n;
        n++;
    }
    return n;
}
void io_arg(int i, char *buf, int max) {
    char *a;
    a = argstr();
    a = argword(a, targs, 127);
    while (i) { a = argword(a, targs, 127); i--; }
    for (i = 0; i < max - 1 && targs[i]; i++) buf[i] = targs[i];
    buf[i] = 0;
}
void io_lib(char *name, char *out, int max) {      /* /lib/name, the name as written (2026-11-03: names on a disk
                                                       are lower case; /LIB/NAME upper-cased before) */
    int i; int j;
    out[0] = '/'; out[1] = 'l'; out[2] = 'i'; out[3] = 'b'; out[4] = '/';
    i = 5;
    for (j = 0; name[j] && i < max - 1; j++) { out[i] = name[j]; i++; }
    out[i] = 0;
}
int io_find(char *name, char *from, char *out, int max) {
    int i; int n; int j;
    n = 0;
    for (i = 0; from[i]; i++) if (from[i] == '/') n = i + 1;
    if (name[0] != '/') { for (i = 0; i < n && i < max - 1; i++) out[i] = from[i]; } else i = 0;
    for (j = 0; name[j] && i < max - 1; j++) { out[i] = name[j]; i++; }
    out[i] = 0;
    if (fresolve(out, 0)) return 1;
    io_lib(name, out, max);
    return fresolve(out, 0);
}
int rh;                                             /* the reads: the handle read last (io_slow's number), */
char *rp;                                           /* its next byte in the buffer, */
char rc;                                            /* and how many it has left there */
int io_slow(int h);
int io_getc(int h) {
    if (rc) { rc = rc - 1; rp++; return rp[-1]; }
    return io_slow(h);
}
int ri(int h) {                                     /* a word; a word split across a refill goes by bytes */
    char *p; int a;
    if (rc & 254) { rc = rc - 2; p = rp; rp = p + 2; return peekw(p); }
    a = io_getc(h) & 255;
    return (a << 8) | (io_getc(h) & 255);
}
int twh;                                            /* the writes: the one file open for writing, */
char twb[IO_WB];                                    /* its bytes not written yet: twb..wp-1 */
char *wp;
char wc;                                            /* the room left in twb */
void io_wflush(void) { if (wp != twb) fwrite(twh, twb, wp - twb); wp = twb; wc = IO_WB; }
void io_fail(char *msg) { if (twh) io_wflush(); eputs(msg); osexit(1); }   /* on the screen; the chain stops
                                                    (STATUS 1); EXIT closes the file with every byte written */
void io_out(int c) { putchar(c); }
char *twpath;                                       /* the file being written, for io_wclose's message */
int io_wopen(char *path) { twpath = path; twh = fcreate(path, 0, 0); wp = twb; wc = IO_WB; return twh != 0; }
void io_wput(int c) { *wp = c; wp++; wc = wc - 1; if (!wc) io_wflush(); }
void wi(int v) {                                    /* a word; the last three bytes of the buffer go by bytes, */
    if (wc & 252) { wc = wc - 2; pokew(wp, v); wp = wp + 2; return; }    /* so that a full buffer is always written */
    io_wput(v >> 8);
    io_wput(v);
}
void io_wputs(char *s) {
    char *p; char *e;
    p = wp; e = twb + IO_WB;
    while (*s) { *p = *s; p++; s++; if (p == e) { wp = p; io_wflush(); p = wp; } }
    wp = p;
    wc = e - p;
}
void io_wclose(void) {                              /* 2026-11-03: CLOSE registers the file, and fails when the
                                                       directory has no free slot (CREATE does not look); the
                                                       message reuses the passes' own literal (LITS_MAX) */
    io_wflush();
    if (!fclose(twh)) { twh = 0; eput2("y1cc: cannot write ", twpath); osexit(1); }
    twh = 0;
}
void io_next(void) {                                /* the next pass, with the work prefix; the last returns */
    if (!io_next_pass[0]) return;
    argword(argstr(), targs, 127);
    osexec(io_next_pass, targs);
    eput2("y1cc: cannot run ", io_next_pass);
    osexit(1);
}
void io_done(void) { if (twh) io_wclose(); io_next(); osexit(0); }
void io_date(char *buf) {
    char *d; int i;
    d = "0000-00-00 00:00";
    for (i = 0; d[i]; i++) buf[i] = d[i];
    buf[i] = 0;
}
