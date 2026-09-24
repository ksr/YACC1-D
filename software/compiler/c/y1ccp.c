/* y1ccp.c - the host driver of the multi-pass y1cc (2026-09-24): the same command line as y1cc.py and y1cc, runs
   the nine passes cc1..cc9 (beside this program) in a temporary directory, stops at the first that fails (that
   pass has printed the message), and removes the intermediate files (kept with Y1CCP_KEEP=dir). Named y1ccpX it
   runs ccN_X: y1ccp16 the 16-bit check builds cc1_16..cc9_16, y1ccpt and y1ccps the builds tests/compiler/passes.py
   makes (the Y1/OS table sizes; the stack probes). Host C, not the subset: on Y1/OS the passes are run one by one.

     y1ccp prog.c [-o prog.asm] [--org N] [--boot] [--vector] [--no-brur] [--os] [-l] */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

static char dir[4096], work[4096], tmp[4096], suffix[64];

static int run(int pass, int argc, char **argv) {
    char prog[4200];
    char *av[64];
    int n = 0, i, st;
    pid_t pid;
    snprintf(prog, sizeof prog, "%s/cc%d%s", dir, pass, suffix);
    av[n++] = prog;
    av[n++] = work;
    if (pass == 1) for (i = 1; i < argc && n < 62; i++) av[n++] = argv[i];
    av[n] = 0;
    fflush(stdout);
    pid = fork();
    if (pid == 0) { execv(prog, av); perror(prog); _exit(127); }
    if (pid < 0 || waitpid(pid, &st, 0) < 0) return 1;
    return !WIFEXITED(st) || WEXITSTATUS(st) != 0;
}

static void cleanup(void) {
    static const char *ext[] = {".opt", ".tok", ".nam", ".lit", ".ast", ".typ", ".dat", ".s1", ".cg", ".sym",
                                ".lab", ".st", ".se", ".em", 0};
    char p[4200];
    int i;
    if (getenv("Y1CCP_KEEP")) return;
    for (i = 0; ext[i]; i++) { snprintf(p, sizeof p, "%s%s", work, ext[i]); unlink(p); }
    rmdir(tmp);
}

int main(int argc, char **argv) {
    const char *keep = getenv("Y1CCP_KEEP");
    const char *me = argv[0], *base, *v;
    char *slash;
    int pass;
    snprintf(dir, sizeof dir, "%s", me);
    slash = strrchr(dir, '/');
    if (slash) *slash = 0; else strcpy(dir, ".");
    base = strrchr(me, '/') ? strrchr(me, '/') + 1 : me;          /* y1ccpX runs ccN_X: y1ccp16 the 16-bit builds, */
    v = strstr(base, "y1ccp");                                     /* y1ccpt those with the Y1/OS table sizes,      */
    if (v && v[5]) snprintf(suffix, sizeof suffix, "_%s", v + 5); /* y1ccps the stack probes (tests/compiler/passes.py) */
    if (keep) snprintf(tmp, sizeof tmp, "%s", keep);
    else {
        snprintf(tmp, sizeof tmp, "%s/y1ccp.XXXXXX", getenv("TMPDIR") ? getenv("TMPDIR") : "/tmp");
        if (!mkdtemp(tmp)) { perror("y1ccp: mkdtemp"); return 1; }
    }
    snprintf(work, sizeof work, "%s/w", tmp);
    for (pass = 1; pass <= 9; pass++)
        if (run(pass, argc, argv)) { cleanup(); return 1; }
    cleanup();
    return 0;
}
