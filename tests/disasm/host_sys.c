/* host_sys.c - the Y1/OS syscalls and y1cc builtins /BIN/DISASM uses, emulated on the Mac for host_disasm.c
   (2026-09-29): OPEN GETC CLOSE ENTRY SEEK with Y1/OS's results, bios(CHAROUT) to stderr, peek() from a 64K memory,
   argstr() = the command line after the program name.
     Y1_LOAD=hex        the load address the directory entry of an opened file gives (default 5000; Y1/OS keeps it
                        in the entry, a Mac file has none)
     Y1_MEM=path@hex    memory for -m: the file's bytes from that address (the rest 0)
   POSIX calls only: the other translation unit defines fopen, fread... (lib_fs.c) with Y1/OS meanings. */
#include <stdarg.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <sys/stat.h>

typedef unsigned short W;
void disasm_main(void);

static unsigned char memory[65536];
static int hfd[5];                  /* 0 = free; the POSIX fd + 1 */
static long hsize[5];
static unsigned char lastent[32];
static char tail[128];

static void say(const char *s) { ssize_t r = write(2, s, strlen(s)); (void)r; }

int sys(long n, ...) {
    va_list ap; int h, fd, i; char *p; W r = 0; struct stat st; unsigned char c; long load;
    va_start(ap, n);
    switch (n) {
    case 0:                         /* OPEN path */
        p = va_arg(ap, char *);
        for (h = 1; h < 5 && hfd[h]; h++) ;
        if (h == 5 || stat(p, &st) || !S_ISREG(st.st_mode) || st.st_size > 0xFFFFFF) break;
        fd = open(p, O_RDONLY);
        if (fd < 0) break;
        hfd[h] = fd + 1; hsize[h] = st.st_size; r = (W)h;
        load = getenv("Y1_LOAD") ? strtol(getenv("Y1_LOAD"), 0, 16) : 0x5000;
        memset(lastent, 0, 32);
        lastent[16] = st.st_size & 255; lastent[17] = (st.st_size >> 8) & 255; lastent[18] = (st.st_size >> 16) & 255;
        lastent[20] = load & 255; lastent[21] = (load >> 8) & 255;
        lastent[22] = load & 255; lastent[23] = (load >> 8) & 255;
        lastent[24] = 1;
        break;
    case 2:                         /* GETC h */
        h = va_arg(ap, int);
        if (h < 1 || h > 4 || !hfd[h] || read(hfd[h] - 1, &c, 1) != 1) { r = 65535; break; }
        r = c;
        break;
    case 3:                         /* CLOSE h */
        h = va_arg(ap, int);
        if (h < 1 || h > 4 || !hfd[h]) break;
        close(hfd[h] - 1); hfd[h] = 0; r = 1;
        break;
    case 16:                        /* ENTRY buf */
        p = va_arg(ap, char *);
        memcpy(p, lastent, 32); r = 1;
        break;
    case 24:                        /* SEEK h, hi, lo */
        h = va_arg(ap, int); i = va_arg(ap, int); fd = va_arg(ap, int);
        if (h < 1 || h > 4 || !hfd[h] || ((long)i << 16 | fd) > hsize[h]) break;
        lseek(hfd[h] - 1, (long)i << 16 | fd, SEEK_SET); r = 1;
        break;
    default:
        say("host_sys: syscall not emulated\n"); exit(2);
    }
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

int peek(int a) { return memory[a & 0xFFFF]; }
char *argstr(void) { return tail; }

int main(int argc, char **argv) {
    int i; size_t n = 0; char *m = getenv("Y1_MEM");
    if (m && strchr(m, '@')) {
        char path[1024]; long at = strtol(strchr(m, '@') + 1, 0, 16); int fd; ssize_t k;
        strncpy(path, m, sizeof path - 1); path[sizeof path - 1] = 0; *strchr(path, '@') = 0;
        fd = open(path, O_RDONLY);
        if (fd < 0) { say("host_sys: Y1_MEM file not found\n"); return 2; }
        k = read(fd, memory + at, (size_t)(65536 - at)); (void)k; close(fd);
    }
    for (i = 1; i < argc; i++) {
        size_t k = strlen(argv[i]);
        if (n + k + 2 > sizeof tail) { say("host_sys: command line over 127 characters\n"); return 2; }
        if (i > 1) tail[n++] = ' ';
        memcpy(tail + n, argv[i], k); n += k;
    }
    tail[n] = 0;
    disasm_main();
    return 0;
}
