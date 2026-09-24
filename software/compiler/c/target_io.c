/* target_io.c - io.h for Y1/OS (2026-09-24), in the y1cc subset: the file syscalls through os/lib_fs.c.
   Compiled into target.c with y1cc.py --os for the self-compile proof and the size report. NOT RUN on the machine
   yet (the compiler does not fit the 32K program area; software/compiler/README.md, "The road to native"), so this
   is the shape of the port rather than a tested layer. Its choices:
   - the command line is the tail argstr() hands a program, split into words at spaces;
   - #include "name" looks beside the including file, then in /LIB;
   - section 0 (code) goes straight into the output file; sections 1 and 2 (data, uninitialised data) wait in RAM
     (TSEC bytes each) and are appended by io_finish: Y1/OS allows one file open for writing at a time;
   - there is no clock, so the header's date is 0000-00-00 00:00;
   - io_fail prints the message and HALTs: there is no exit syscall yet to return to the shell from deep inside. */
#include "../../../os/lib_fs.c"

#define TSEC 1024

char targs[128];
char tsec1[TSEC];
char tsec2[TSEC];
int tn1;
int tn2;
int touth;

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
int io_find(char *name, char *from, char *out, int max) {
    int i; int n; int j;
    n = 0;
    for (i = 0; from[i]; i++) if (from[i] == '/') n = i + 1;
    if (name[0] != '/') { for (i = 0; i < n && i < max - 1; i++) out[i] = from[i]; } else i = 0;
    for (j = 0; name[j] && i < max - 1; j++) { out[i] = name[j]; i++; }
    out[i] = 0;
    if (fresolve(out, 0)) return 1;
    out[0] = '/'; out[1] = 'L'; out[2] = 'I'; out[3] = 'B'; out[4] = '/';
    i = 5;
    for (j = 0; name[j] && i < max - 1; j++) { out[i] = name[j]; i++; }
    out[i] = 0;
    return fresolve(out, 0);
}
int io_create(char *path) { touth = fcreate(path, 0, 0); return touth != 0; }
void io_fail(char *msg) { puts(msg); halt(); }
void io_put(int s, int c) {
    if (s == 0) { fputc(touth, c); return; }
    if (s == 1) { if (tn1 >= TSEC) io_fail("y1cc: data section over TSEC"); tsec1[tn1] = c; tn1++; return; }
    if (tn2 >= TSEC) io_fail("y1cc: bss section over TSEC");
    tsec2[tn2] = c; tn2++;
}
int io_finish(void) {
    int i;
    for (i = 0; i < tn1; i++) fputc(touth, tsec1[i]);
    for (i = 0; i < tn2; i++) fputc(touth, tsec2[i]);
    fclose(touth);
    return 1;
}
void io_out(int c) { putchar(c); }
void io_date(char *buf) {
    char *d; int i;
    d = "0000-00-00 00:00";
    for (i = 0; d[i]; i++) buf[i] = d[i];
    buf[i] = 0;
}
