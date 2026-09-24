/* host_io.c - io.h on the Mac (2026-09-24): stdio, the command line, getcwd for canonical #include paths.
   This file is host C (it is never compiled by y1cc); y1cc.c reaches the outside world only through it.

   The library directory for #include "file" (after the directory of the including file) is software/compiler/lib:
   $Y1CC_LIB if set, else ../lib beside the executable (software/compiler/c/y1cc -> software/compiler/lib), the
   place y1cc.py finds relative to itself. Paths are made absolute and normalised (".", "..", "//") the way
   Python's os.path.abspath does, so both compilers recognise a file included twice under two spellings and print
   the same paths in their messages. The output sections are kept in memory and written by io_finish, so a failed
   compile leaves no file behind (y1cc.py writes its output only at the end, too). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "io.h"

void y1cc_main(void);

#define NFILES 16
#define PATHMAX 4096

static int g_argc;
static char **g_argv;
static FILE *files[NFILES];
static char *sec[3];
static size_t seclen[3];
static size_t seccap[3];
static char outname[PATHMAX];
static char libdir[PATHMAX];

int main(int argc, char **argv) {
    g_argc = argc;
    g_argv = argv;
    y1cc_main();
    return 0;
}

int io_argc(void) { return g_argc - 1; }

void io_arg(int i, char *buf, int max) {
    const char *s = (i >= 0 && i + 1 < g_argc) ? g_argv[i + 1] : "";
    strncpy(buf, s, (size_t)max - 1);
    buf[max - 1] = 0;
}

int io_open(char *path) {
    int h;
    for (h = 1; h < NFILES; h++)
        if (!files[h]) {
            files[h] = fopen(path, "rb");
            return files[h] ? h : 0;
        }
    return 0;
}

int io_getc(int h) {
    int c = fgetc(files[h]);
    return c == EOF ? 256 : c;
}

void io_close(int h) {
    if (h > 0 && h < NFILES && files[h]) { fclose(files[h]); files[h] = 0; }
}

/* os.path.abspath: join with the current directory, then normalise "." ".." and repeated slashes */
static void abspath(const char *p, char *out) {
    char tmp[PATHMAX];
    char *parts[PATHMAX / 2];
    int n = 0, i;
    char *s, *tok;
    if (p[0] == '/') snprintf(tmp, sizeof tmp, "%s", p);
    else {
        char cwd[PATHMAX];
        if (!getcwd(cwd, sizeof cwd)) strcpy(cwd, ".");
        snprintf(tmp, sizeof tmp, "%s/%s", cwd, p);
    }
    for (s = tmp; (tok = strtok(s, "/")) != 0; s = 0) {
        if (strcmp(tok, ".") == 0 || tok[0] == 0) continue;
        if (strcmp(tok, "..") == 0) { if (n > 0) n--; continue; }
        parts[n++] = tok;
    }
    out[0] = 0;
    for (i = 0; i < n; i++) { strcat(out, "/"); strcat(out, parts[i]); }
    if (n == 0) strcpy(out, "/");
}

static int exists(const char *p) {
    FILE *f = fopen(p, "rb");
    if (!f) return 0;
    fclose(f);
    return 1;
}

static void find_libdir(void) {
    const char *env = getenv("Y1CC_LIB");
    char exe[PATHMAX], *slash;
    if (libdir[0]) return;
    if (env && env[0]) { abspath(env, libdir); return; }
    abspath(g_argv[0], exe);
    slash = strrchr(exe, '/');
    if (slash) *slash = 0;
    strcat(exe, "/../lib");
    abspath(exe, libdir);
}

int io_find(char *name, char *from, char *out, int max) {
    char here[PATHMAX], cand[PATHMAX], full[PATHMAX], *slash;
    int pass;
    find_libdir();
    abspath(from, here);
    slash = strrchr(here, '/');
    if (slash) *slash = 0;
    for (pass = 0; pass < 2; pass++) {
        const char *dir = pass == 0 ? here : libdir;
        if (name[0] == '/') snprintf(cand, sizeof cand, "%s", name);
        else snprintf(cand, sizeof cand, "%s/%s", dir, name);
        if (exists(cand)) {
            abspath(cand, full);
            if ((int)strlen(full) >= max) return 0;
            strcpy(out, full);
            return 1;
        }
    }
    return 0;
}

void io_lib(char *name, char *out, int max) {
    char p[PATHMAX];
    find_libdir();
    snprintf(p, sizeof p, "%s/%s", libdir, name);
    strncpy(out, p, (size_t)max - 1);
    out[max - 1] = 0;
}

int io_create(char *path) {
    snprintf(outname, sizeof outname, "%s", path);
    return 1;
}

void io_put(int s, int c) {
    if (seclen[s] == seccap[s]) {
        seccap[s] = seccap[s] ? seccap[s] * 2 : 65536;
        sec[s] = realloc(sec[s], seccap[s]);
        if (!sec[s]) { fputs("y1cc: out of memory\n", stderr); exit(1); }
    }
    sec[s][seclen[s]++] = (char)c;
}

int io_finish(void) {
    FILE *f = fopen(outname, "wb");
    int s;
    if (!f) return 0;
    for (s = 0; s < 3; s++) if (seclen[s] && fwrite(sec[s], 1, seclen[s], f) != seclen[s]) { fclose(f); return 0; }
    return fclose(f) == 0;
}

void io_out(int c) { putchar(c); }

void io_fail(char *msg) {
    fflush(stdout);
    fputs(msg, stderr);
    fputc('\n', stderr);
    exit(1);
}

static FILE *wfile;

int io_wopen(char *path) {
    wfile = fopen(path, "wb");
    return wfile != 0;
}

void io_wput(int c) { fputc(c, wfile); }

void io_wclose(void) {
    if (wfile && fclose(wfile) != 0) { fputs("y1cc: cannot write an intermediate file\n", stderr); exit(1); }
    wfile = 0;
}

void io_done(void) {
    fflush(stdout);
    if (wfile) io_wclose();
    exit(0);
}

void io_date(char *buf) {
    time_t t = time(0);
    strftime(buf, 17, "%Y-%m-%d %H:%M", localtime(&t));
}
