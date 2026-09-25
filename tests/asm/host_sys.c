/* host_sys.c - the Y1/OS syscalls /BIN/ASM uses, emulated on the Mac for host_asm.c (2026-09-25): OPEN READ GETC
   CLOSE CREATE WRITE PUTC DELETE with Y1/OS's results (handles 1..4, one of them writing; 65535 at the end of a
   file; 0 for "cannot"), bios(CHAROUT) to stderr, argstr() = the command line after the program name. Unlike Y1/OS
   a file may be over 64K (the corpus has 250K compiler passes); set Y1_64K=1 to refuse those as the OS does.
   After the run the exit status is 1 if the assembler counted errors, and the load/exec of the file it created is
   printed to stderr as "host_sys: created NAME load XXXX exec XXXX" (Y1/OS keeps them in the directory entry).
   POSIX calls only: the other translation unit defines fopen, fread... (lib_fs.c) with Y1/OS meanings. */
#include <stdarg.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <sys/stat.h>

typedef unsigned short W;
void asm_main(void);
extern W errs;

#define NH 5
static int hfd[NH];                 /* 0 = free; the POSIX fd + 1 */
static int hmode[NH];               /* 1 read, 2 write */
static unsigned char hbuf[NH][512];
static int hn[NH], hp[NH];
static long hsize[NH];
static char hname[NH][256];
static W hload[NH], hexec[NH];
static char tail[128];

static void say(const char *s) { ssize_t r = write(2, s, strlen(s)); (void)r; }

static int getb(int h) {            /* the next byte of read handle h, -1 at the end */
    if (hp[h] == hn[h]) {
        ssize_t r = read(hfd[h] - 1, hbuf[h], 512);
        hn[h] = r > 0 ? (int)r : 0; hp[h] = 0;
        if (!hn[h]) return -1;
    }
    return hbuf[h][hp[h]++];
}

int sys(long n, ...) {
    va_list ap; int h, fd, i; char *p; W r = 0; struct stat st;
    va_start(ap, n);
    switch (n) {
    case 0:                         /* OPEN path */
        p = va_arg(ap, char *);
        for (h = 1; h < NH && hfd[h]; h++) ;
        if (h == NH) break;
        if (stat(p, &st) || !S_ISREG(st.st_mode)) break;
        if (getenv("Y1_64K") && st.st_size > 65535) break;
        fd = open(p, O_RDONLY);
        if (fd < 0) break;
        hfd[h] = fd + 1; hmode[h] = 1; hn[h] = hp[h] = 0; r = (W)h;
        break;
    case 1:                         /* READ h, buf: the next sector's worth */
        h = va_arg(ap, int); p = va_arg(ap, char *);
        if (h < 1 || h >= NH || hmode[h] != 1) break;
        for (i = 0; i < 512; i++) { int c = getb(h); if (c < 0) break; p[i] = (char)c; }
        r = (W)i;
        break;
    case 2:                         /* GETC h */
        h = va_arg(ap, int);
        if (h < 1 || h >= NH || hmode[h] != 1) { r = 65535; break; }
        i = getb(h); r = i < 0 ? 65535 : (W)i;
        break;
    case 3:                         /* CLOSE h */
        h = va_arg(ap, int);
        if (h < 1 || h >= NH || !hfd[h]) break;
        close(hfd[h] - 1);
        if (hmode[h] == 2) {
            char m[400]; static const char hx[] = "0123456789ABCDEF"; char a[5], b[5];
            for (i = 0; i < 4; i++) { a[i] = hx[(hload[h] >> (12 - 4 * i)) & 15]; b[i] = hx[(hexec[h] >> (12 - 4 * i)) & 15]; }
            a[4] = b[4] = 0;
            strcpy(m, "host_sys: created "); strcat(m, hname[h]); strcat(m, " load "); strcat(m, a);
            strcat(m, " exec "); strcat(m, b); strcat(m, "\n"); say(m);
        }
        hfd[h] = 0; hmode[h] = 0; r = 1;
        break;
    case 4:                         /* CREATE path, load, exec */
        p = va_arg(ap, char *);
        for (h = 1; h < NH; h++) if (hmode[h] == 2) goto done;
        for (h = 1; h < NH && hfd[h]; h++) ;
        if (h == NH) break;
        fd = open(p, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd < 0) break;
        hfd[h] = fd + 1; hmode[h] = 2; hsize[h] = 0;
        strncpy(hname[h], p, 255);
        hload[h] = (W)va_arg(ap, int); hexec[h] = (W)va_arg(ap, int); r = (W)h;
        break;
    case 5:                         /* WRITE h, buf, n */
        h = va_arg(ap, int); p = va_arg(ap, char *); i = va_arg(ap, int);
        if (h < 1 || h >= NH || hmode[h] != 2) break;
        if (getenv("Y1_64K") && hsize[h] + i > 65535) i = (int)(65535 - hsize[h]);
        if (write(hfd[h] - 1, p, (size_t)i) != i) break;
        hsize[h] += i; r = (W)i;
        break;
    case 6:                         /* PUTC h, c */
        h = va_arg(ap, int); i = va_arg(ap, int);
        if (h < 1 || h >= NH || hmode[h] != 2) break;
        { char c = (char)i; if (write(hfd[h] - 1, &c, 1) == 1) { hsize[h]++; r = 1; } }
        break;
    case 7:                         /* DELETE path */
        p = va_arg(ap, char *);
        r = unlink(p) == 0;
        break;
    default:
        say("host_sys: syscall not emulated\n"); exit(2);
    }
done:
    va_end(ap);
    return r;
}

int bios(int addr, int r7, int acc) {       /* only CHAROUT ($FFC4): the raw console = stderr */
    char c = (char)acc; ssize_t w;
    (void)r7;
    if (addr != 0xFFC4) { say("host_sys: bios call not emulated\n"); exit(2); }
    w = write(2, &c, 1); (void)w;
    return 0;
}

char *argstr(void) { return tail; }
int peekw(char *p) { return ((unsigned char)p[0] << 8) | (unsigned char)p[1]; }
void pokew(char *p, int v) { p[0] = (char)(v >> 8); p[1] = (char)v; }

int main(int argc, char **argv) {
    int i; size_t n = 0;
    for (i = 1; i < argc; i++) {
        size_t k = strlen(argv[i]);
        if (n + k + 2 > sizeof tail) { say("host_sys: command line over 127 characters\n"); return 2; }
        if (i > 1) tail[n++] = ' ';
        memcpy(tail + n, argv[i], k); n += k;
    }
    tail[n] = 0;
    asm_main();
    return errs ? 1 : 0;
}
