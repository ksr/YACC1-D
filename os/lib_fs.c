/* lib_fs.c - the Y1/OS file API for programs (2026-09-23): C wrappers around the syscalls, for /BIN commands.
   #include "../lib_fs.c" (it includes lib_abi.c itself: the numbers, the RAM addresses). Each wrapper is one
   sys() call (y1cc: the arguments go to SYSARG0..2, the OS handler in SYSTAB is JSRURed, SYSRES comes back), so a
   command written against these names never sees an address; unused wrappers cost nothing (y1cc drops them).

   Results are full 16-bit words: a handle (1..4) or 0, 1/0 for done/cannot, a count, or a byte with 65535 for
   "none": fgetc() at the end of the file, conin() on Ctrl-D / end of input. There is no carry bit to test.

   Reading:   h = fopen(path); while ((c = fgetc(h)) != 65535) ...; fclose(h);      byte-wise through the OS buffer
              while ((n = fread(h, buf512))) ...                                     whole sectors into your buffer
   Writing:   h = fcreate(path, load, exec); fputc(h, c) / fwrite(h, buf, n) / fputs(h, s); fclose(h) registers it
              (one file may be open for writing at a time, and a shell > or pipe is one; a same-named file is
              replaced when the new one is closed)
   Names:     fdelete(path)  fmkdir(path)  frmdir(path)  frename(path, newname)  chdir(path)  getcwd(buf)
   Entries:   h = opendir(path); while (readdir(h, ent32)) { ent_len(ent) ... }; fclose(h)
              fresolve(path, ent32) -> 1 found; fentry(ent32) copies the entry the last call found
   Console:   conin() the next byte of STDIN without echo: the shell's < file or pipe, else the console (65535 at
              the end / Ctrl-D: filters end there); constat() 1 when one is waiting. DATA comes from conin().
              keyin() a KEY: always the keyboard, never redirected (65535 at Ctrl-D): --More--, vi, dump, examine.
              stdio() bit 0: stdin redirected, bit 1: stdout redirected (the pager does not page into a file).
              Output is putchar/puts (y1cc --os: the CONOUT syscall, redirected by the shell); a diagnostic that must
              reach the screen even under > or | is eputs() from lib_err.c.
   Paths are as the shell takes them: absolute /A/B or relative to the current directory, names 1..12 characters,
   case-sensitive; "" is the current directory for opendir/fresolve. */
#include "lib_abi.c"

int fopen(char *path) { return sys(SYS_OPEN, path); }
int fread(int h, char *buf) { return sys(SYS_READ, h, buf); }
int fgetc(int h) { return sys(SYS_GETC, h); }
int fclose(int h) { return sys(SYS_CLOSE, h); }
int fcreate(char *path, int load, int exec) { return sys(SYS_CREATE, path, load, exec); }
int fwrite(int h, char *buf, int n) { return sys(SYS_WRITE, h, buf, n); }
int fputc(int h, int c) { return sys(SYS_PUTC, h, c); }
int fdelete(char *path) { return sys(SYS_DELETE, path); }
int fmkdir(char *path) { return sys(SYS_MKDIR, path); }
int frmdir(char *path) { return sys(SYS_RMDIR, path); }
int opendir(char *path) { return sys(SYS_OPENDIR, path); }
int readdir(int h, char *ent) { return sys(SYS_READDIR, h, ent); }
int fresolve(char *path, char *ent) { return sys(SYS_RESOLVE, path, ent); }
int getcwd(char *buf) { return sys(SYS_GETCWD, buf); }
int chdir(char *path) { return sys(SYS_CHDIR, path); }
int frename(char *path, char *newname) { return sys(SYS_RENAME, path, newname); }
int fentry(char *ent) { return sys(SYS_ENTRY, ent); }
int conin() { return sys(SYS_CONIN); }
int constat() { return sys(SYS_CONST); }
int keyin() { return sys(SYS_KEYIN); }
int stdio() { return sys(SYS_STDIO); }
void osexit(int status) { sys(SYS_EXIT, status); }                 /* 2026-09-25: never returns */
int osexec(char *path, char *args) { return sys(SYS_EXEC, path, args); }   /* returns only when path cannot run */
int fseek(int h, int hi, int lo) { return sys(SYS_SEEK, h, hi, lo); }     /* 24-bit position hi:lo; 1 done */

int fputs(int h, char *s) {                 /* a string (no newline added); returns the bytes written */
    int n;
    n = 0;
    while (*s) { if (!fputc(h, *s++)) return n; n++; }
    return n;
}

/* the 32-byte P8XFS v2 directory entry (little-endian fields): name[12] start[4] length[4] load[2] exec[2] flags */
int ent_isfile(char *e) { return e[24] == 1; }
int ent_isdir(char *e) { return e[24] == 2; }
int ent_lba(char *e) { return e[12] | (e[13] << 8); }
int ent_len(char *e) { return e[16] | (e[17] << 8); }     /* the low 16 bits; e[18] counts 64K multiples (bits
                                                               16-23: Y1/OS files are up to 16M - 1 since 2026-09-25) */
int ent_lenx(char *e) { return e[18]; }                   /* bits 16-23 of the length (2026-09-25) */
int ent_load(char *e) { return e[20] | (e[21] << 8); }
int ent_exec(char *e) { return e[22] | (e[23] << 8); }
void ent_name(char *e, char *out) {         /* the name without its space padding, NUL-terminated (13 bytes) */
    int n;
    n = 12;
    while (n && e[n - 1] == ' ') n--;
    out[n] = 0;
    while (n) { n--; out[n] = e[n]; }
}

char *argword(char *a, char *out, int max) { /* the next word of a command tail -> out (NUL-terminated); returns the rest */
    int n;
    while (*a == ' ') a++;
    n = 0;
    while (*a && *a != ' ') { if (n < max) out[n++] = *a; a++; }
    out[n] = 0;
    while (*a == ' ') a++;
    return a;
}
