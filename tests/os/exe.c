/* exe.c - tests/os/exec.session's program (2026-09-25): the syscalls EXIT, EXEC and SEEK.
     exe x N      print N, then EXIT(N) from three calls deep (main's RET never runs)
     exe c N      print "chain N"; then EXEC /EXE "c N-1" while N > 0: a chain of N + 1 programs in one command
     exe b        EXEC refused: a missing file, a directory, a file that does not fit $5000-$CFFF (/BIG.TXT: 20000
                  bytes to load at $C000), a 64-character path; each returns 0
     exe s        print STATUS ($0F0E), the status the program before left
     exe f        SEEK on /README.TXT: to 5 (inside the first sector), to 150, to its end (156), past it (refused),
                  on a directory handle (refused); the bytes read after each
   run.py compiles it twice (y1cc --os): /EXE, and /EXES with --stack 0xCFFF (EXIT from a program on its own stack). */
#include "../../os/lib_fs.c"
#include "y1lib.c"
char arg[16];
char next[16];

void deep(int n, int k) { if (k) deep(n, k - 1); else osexit(n); }

void show(int h, int n) {                   /* n bytes from h, as characters */
    int c;
    while (n && (c = fgetc(h)) != 65535) { putchar(c); n--; }
    putchar(10);
}

void main() {
    char *a; int n, i, h;
    a = argword(argstr(), arg, 15);
    argword(a, next, 15);
    n = 0;
    for (i = 0; next[i]; i++) n = n * 10 + next[i] - '0';
    if (arg[0] == 'x') { putstr("exit "); putnum(n); putchar(10); deep(n, 3); puts("not here"); }
    else if (arg[0] == 'c') {
        putstr("chain "); putnum(n); putchar(10);
        if (n) {
            next[0] = 'c'; next[1] = ' '; next[2] = '0' + n - 1; next[3] = 0;
            osexec("/EXE", next);
            puts("exec failed");
        }
    } else if (arg[0] == 'b') {
        putnum(osexec("/NOPE", "")); putnum(osexec("/BIN", "")); putnum(osexec("/BIG.TXT", ""));
        putnum(osexec("/A234567890/B234567890/C234567890/D234567890/E234567890/F2345678", "")); putchar(10);
    } else if (arg[0] == 's') { putstr("status "); putnum(peekw(STATUS)); putchar(10); }
    else if (arg[0] == 'f') {
        h = fopen("/README.TXT");
        putnum(fseek(h, 0, 5)); putchar(' '); show(h, 10);
        putnum(fseek(h, 0, 150)); putchar(' '); show(h, 10);
        putnum(fseek(h, 0, 156)); putchar(' '); show(h, 10);
        putnum(fseek(h, 0, 157)); putnum(fseek(h, 1, 0)); putchar(10);
        fclose(h);
        h = opendir("/");
        putnum(fseek(h, 0, 0)); putchar(10);
        fclose(h);
    }
}
