/* target_io.c - io.h for Y1/OS (2026-09-24), in the y1cc subset: the file syscalls through os/lib_fs.c. Every pass
   of the native compiler is built with it (target/NAME.c), and y1cc.c is compiled with it for the self-compile proof
   (target.c). First run 2026-09-25 (tests/native/run.py). Its choices:
   - the command line is the tail argstr() hands a program, split into words at spaces;
   - #include "name" looks beside the including file, then in /LIB (the name upper-cased, as the Makefiles put files
     on a disk: #include "y1lib.c" finds /LIB/Y1LIB.C); cc9 reads the runtime text from /LIB/Y1CCRT.TXT;
   - the source files are read through io_open/io_getc/io_close, which are NOT here: target_rd.c has the plain ones
     (each a handle) and target_inc.c those of the lexer, which nests #includes deeper than Y1/OS's handles allow;
     each target/NAME.c includes one of them;
   - the three output sections of y1cc.c (io_create/io_put/io_finish) are in target_sec.c, which only target.c
     includes (the passes write their files with io_wopen/io_wput/io_wclose and would only carry its buffers);
   - there is no clock, so the header's date is 0000-00-00 00:00;
   - a pass that is done EXECs the next one (2026-09-25): target/NAME.c names it in io_next_pass ("/LIB/CC/CC2" ...,
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
void io_lib(char *name, char *out, int max) {      /* /LIB/NAME: upper case, as the Makefiles put files on a disk */
    int i; int j; int c;
    out[0] = '/'; out[1] = 'L'; out[2] = 'I'; out[3] = 'B'; out[4] = '/';
    i = 5;
    for (j = 0; name[j] && i < max - 1; j++) {
        c = name[j];
        if (c >= 'a' && c <= 'z') c = c - 32;
        out[i] = c; i++;
    }
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
void io_fail(char *msg) { eputs(msg); osexit(1); }        /* on the screen; the chain stops (STATUS 1) */
void io_out(int c) { putchar(c); }
int twh;
int io_wopen(char *path) { twh = fcreate(path, 0, 0); return twh != 0; }
void io_wput(int c) { fputc(twh, c); }
void io_wclose(void) { fclose(twh); twh = 0; }
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
