/* lib_stdin.c - "the files named, else the console" input for the /BIN filters (Y1/OS, 2026-09-23).
     openarg(tail) -> 0 no file named (the console), 1 ready, 2 a name was not found (gbad points at it)
       tail   the rest of the command line: every word is a file, a glob (expanded, lib_globx.c), or "-" for the
              console; up to GMAX (24) names in all, read one after the other as ONE stream
     nextc()  the next byte of that stream, 65535 at its end. The console is conin(): no echo, Ctrl-D ends it.
     sepfiles set it to 1 before the first nextc() to make every file end with a line feed (a line tool must not
              glue the last line of one file to the first of the next); leave it 0 for byte-exact tools (cat, wc)
     curname  the name of the file being read ("-" for the console): grep's "name:" prefix
     gnf      how many names openarg found
     notfound(cmd)  prints "cmd: not found: WORD" after openarg returned 2
   One read handle is open at a time (opened as the stream reaches the file, closed at its end).
   Ported from P8X os/commands/lib_stdin.c 2026-09-23, changes: all the words of the tail, not just the first;
   "-" = the console; sepfiles and curname are new; Y1/OS fopen/fgetc (relative names resolve in the OS, so the
   P8X absolute-path building is gone; so are RDBUF, FRESOLVE and the & 256 carry tests); the console is conin()
   with its 65535 at Ctrl-D (P8X getchar()/SYS_GETC, which could be a < redirect: Y1/OS has no redirection yet). */
#include "lib_globx.c"
#define GMAX 24
char gfiles[GMAX * GSLOT];
int gnf, gidx, ginh, glast, sepfiles;
char *curname, *gbad;
char gent1[32];

int openarg(char *a) {
    int n, i; char *o;
    gnf = 0; gidx = 0; ginh = 0; glast = 10; gbad = 0; curname = "-";
    while (*a == ' ') a++;
    if (!*a) { strcpy(gfiles, "-"); gnf = 1; return 0; }
    while (*a && gnf < GMAX) {
        if (isglob(a)) {
            n = glob_expand(a, gfiles + gnf * GSLOT, GMAX - gnf);
            if (!n) { gbad = a; return 2; }
            gnf += n;
        } else {
            o = gfiles + gnf * GSLOT;
            for (i = 0; a[i] && a[i] != ' ' && i < GSLOT - 1; i++) o[i] = a[i];
            o[i] = 0;
            if (strcmp(o, "-") && (!fresolve(o, gent1) || !ent_isfile(gent1))) { gbad = a; return 2; }
            gnf++;
        }
        while (*a && *a != ' ') a++;
        while (*a == ' ') a++;
    }
    return 1;
}

int nextc() {
    int c;
    while (1) {
        if (ginh == 65535) {                     /* the console */
            c = conin();
            if (c != 65535) return c;
            ginh = 0;
        } else if (ginh) {
            c = fgetc(ginh);
            if (c != 65535) { glast = c; return c; }
            fclose(ginh); ginh = 0;
            if (sepfiles && glast != 10) { glast = 10; return 10; }
        }
        if (gidx >= gnf) return 65535;
        curname = gfiles + gidx * GSLOT; gidx++; glast = 10;
        if (curname[0] == '-' && curname[1] == 0) ginh = 65535;
        else ginh = fopen(curname);              /* checked by openarg; a vanished file just reads as empty */
    }
}

void notfound(char *cmd) {                       /* "cmd: not found: WORD" for the word openarg stopped at */
    char *p;
    for (p = cmd; *p; p++) putchar(*p);
    for (p = ": not found: "; *p; p++) putchar(*p);
    for (p = gbad; *p && *p != ' '; p++) putchar(*p);
    putchar(10);
}
