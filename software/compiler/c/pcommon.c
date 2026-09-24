/* pcommon.c - what every pass of the multi-pass y1cc shares (2026-09-24): string and number helpers, the error
   message buffer, and the intermediate files (bytes, 16-bit big-endian words, NUL-terminated strings) over io.h.
   In the y1cc subset, like y1cc.c (whose rules it keeps: every value 0..65535, bytes from char arrays masked with
   & 255, every local declared at the top of its function). Each pass defines pass_fail(msg): stop with msg now
   (io_fail), or leave it in its output file for a later pass to raise at the right moment (a deferred error). */
#include "io.h"
#include "pdefs.h"

void pass_fail(char *msg);
int s_len(char *s);
int s_eq(char *a, char *b);
int s_starts(char *s, char *p);
int s_cmp(char *a, char *b);
void bcat(char *buf, char *s);
void bchr(char *buf, int c);
void bnum(char *buf, int n);
int is_alpha(int c);
int is_digit(int c);
int is_alnum(int c);
int lower(int c);
int mul16(int a, int b);
void fail(char *msg);
void e_start(char *s);
void e_s(char *s);
void e_q(char *s);
void e_n(int n);
void e_go(void);
void wpath(char *ext);
int ropen(char *ext);
int rb(int h);
int ri(int h);
void rs(int h, char *buf, int max);
void wopen(char *ext);
void wb(int c);
void wi(int v);
void ws(char *s);
void wclose(void);
void rarr(int h, int *a, int n);
void rarrc(int h, char *a, int n);
void warr(int *a, int n);
void warrc(char *a, int n);
void skip(int h, int n);
void nm_fetch(int id, char *buf);
void p_args(void);

char ebuf[EBUF_MAX];            /* the message being built */
char enbuf[12];
char wdir[LINE_MAX];            /* the work prefix: every intermediate file is wdir + an extension */
char wpbuf[LINE_MAX];

int s_len(char *s) { int n; n = 0; while (s[n]) n++; return n; }
int s_eq(char *a, char *b) { while (*a && *a == *b) { a++; b++; } return *a == *b; }
int s_starts(char *s, char *p) { while (*p) { if (*s != *p) return 0; s++; p++; } return 1; }
int s_cmp(char *a, char *b) {                       /* 0 equal, 1 a < b, 2 a > b (byte order, as Python sorts) */
    while (*a && *a == *b) { a++; b++; }
    if ((*a & 255) == (*b & 255)) return 0;
    if ((*a & 255) < (*b & 255)) return 1;
    return 2;
}
void bcat(char *buf, char *s) {
    int n;
    n = s_len(buf);
    while (*s) { if (n >= LINE_MAX - 1) fail("y1cc: line too long"); buf[n] = *s; n++; s++; }
    buf[n] = 0;
}
void bchr(char *buf, int c) {
    int n;
    n = s_len(buf);
    if (n >= LINE_MAX - 1) fail("y1cc: line too long");
    buf[n] = c; buf[n + 1] = 0;
}
void bnum(char *buf, int n) {                       /* decimal, n >= 0 */
    char d[8]; int k;
    k = 0;
    if (n == 0) { bchr(buf, '0'); return; }
    while (n > 0) { d[k] = '0' + n % 10; k++; n = n / 10; }
    while (k > 0) { k--; bchr(buf, d[k]); }
}
int is_alpha(int c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }
int is_digit(int c) { return c >= '0' && c <= '9'; }
int is_alnum(int c) { return is_alpha(c) || is_digit(c); }
int lower(int c) { if (c >= 'A' && c <= 'Z') return c + 32; return c; }
int mul16(int a, int b) {                           /* a * b mod 65536 without a 32-bit overflow on the host */
    return (a * (b & 255) + ((a * (b >> 8)) & 255) * 256) & 65535;
}

void fail(char *msg) { pass_fail(msg); }
void e_start(char *s) { ebuf[0] = 0; e_s(s); }
void e_s(char *s) {                                 /* append, silently cut at EBUF_MAX */
    int n;
    n = s_len(ebuf);
    while (*s && n < EBUF_MAX - 1) { ebuf[n] = *s; n++; s++; }
    ebuf[n] = 0;
}
void e_q(char *s) { e_s("'"); e_s(s); e_s("'"); }  /* Python's repr() of a plain name */
void e_n(int n) { enbuf[0] = 0; bnum(enbuf, n); e_s(enbuf); }
void e_go(void) { pass_fail(ebuf); }

/* ---- the intermediate files --------------------------------------------------------------------------------- */
void p_args(void) { io_arg(0, wdir, LINE_MAX); }    /* every pass: the first word is the work prefix */
void wpath(char *ext) { wpbuf[0] = 0; bcat(wpbuf, wdir); bcat(wpbuf, ext); }
int ropen(char *ext) {
    int h;
    wpath(ext);
    h = io_open(wpbuf);
    if (!h) { e_start("y1cc: cannot read "); e_s(wpbuf); io_fail(ebuf); }
    return h;
}
int rb(int h) { return io_getc(h); }                /* 0..255, 256 at the end */
int ri(int h) { int a; a = io_getc(h) & 255; return (a << 8) | (io_getc(h) & 255); }
void rs(int h, char *buf, int max) {                /* a NUL-terminated string, cut at max - 1 */
    int n; int c;
    n = 0;
    for (;;) {
        c = io_getc(h);
        if (c == 0 || c == 256) break;
        if (n < max - 1) { buf[n] = c; n++; }
    }
    buf[n] = 0;
}
void wopen(char *ext) {
    wpath(ext);
    if (!io_wopen(wpbuf)) { e_start("y1cc: cannot write "); e_s(wpbuf); io_fail(ebuf); }
}
void wb(int c) { io_wput(c & 255); }
void wi(int v) { io_wput((v >> 8) & 255); io_wput(v & 255); }
void ws(char *s) { while (*s) { io_wput(*s & 255); s++; } io_wput(0); }
void wclose(void) { io_wclose(); }
/* whole columns: n words / bytes of a table (the tables go through the files a column at a time: one call per
   column is much less code than a statement per field) */
void rarr(int h, int *a, int n) { int i; for (i = 0; i < n; i++) a[i] = ri(h); }
void rarrc(int h, char *a, int n) { int i; for (i = 0; i < n; i++) a[i] = rb(h); }
void warr(int *a, int n) { int i; for (i = 0; i < n; i++) wi(a[i]); }
void warrc(char *a, int n) { int i; for (i = 0; i < n; i++) wb(a[i]); }
void skip(int h, int n) { while (n) { rb(h); n--; } }

/* the text of name id (1..) from the .nam file, for an error message: the passes after cc2 keep no name text */
void nm_fetch(int id, char *buf) {
    int h; int i;
    buf[0] = 0;
    if (!id) return;
    h = ropen(".nam");
    ri(h);
    for (i = 1; i < id; i++) rs(h, buf, ID_MAX);
    rs(h, buf, ID_MAX);
    io_close(h);
}
