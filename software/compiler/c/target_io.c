/* target_io.c - io.h for Y1/OS (2026-09-24), in the y1cc subset: the file syscalls through os/lib_fs.c.
   Compiled into target.c with y1cc.py --os for the self-compile proof and the size report. NOT RUN on the machine
   yet (the compiler does not fit the 32K program area; software/compiler/README.md, "The road to native"), so this
   is the shape of the port rather than a tested layer. Its choices:
   - the command line is the tail argstr() hands a program, split into words at spaces;
   - #include "name" looks beside the including file, then in /LIB;
   - the three output sections of y1cc.c (io_create/io_put/io_finish) are in target_sec.c, which only target.c
     includes (the passes write their files with io_wopen/io_wput/io_wclose and would only carry its buffers);
   - there is no clock, so the header's date is 0000-00-00 00:00;
   - io_fail prints the message and HALTs: there is no exit syscall yet to return to the shell from deep inside. */
#include "../../../os/lib_fs.c"

char targs[128];

void y1cc_main(void);

void main() { y1cc_main(); }

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
int io_open(char *path) { return fopen(path); }
int io_getc(int h) {
    int c;
    c = fgetc(h);
    if (c == 65535) return 256;
    return c;
}
void io_close(int h) { fclose(h); }
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
void io_fail(char *msg) { puts(msg); halt(); }
void io_out(int c) { putchar(c); }
int twh;
int io_wopen(char *path) { twh = fcreate(path, 0, 0); return twh != 0; }
void io_wput(int c) { fputc(twh, c); }
void io_wclose(void) { fclose(twh); twh = 0; }
void io_done(void) { if (twh) io_wclose(); halt(); }    /* no exit syscall yet (BACKLOG): stop the machine */
void io_date(char *buf) {
    char *d; int i;
    d = "0000-00-00 00:00";
    for (i = 0; d[i]; i++) buf[i] = d[i];
    buf[i] = 0;
}
