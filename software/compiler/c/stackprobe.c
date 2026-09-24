/* stackprobe.c - how deep a pass's stack goes on the YACC1, measured by running the pass on the Mac (2026-09-24,
   tests/compiler/passes.py). Host C only. The pass is compiled with -finstrument-functions, so every function entry
   and exit calls the two hooks below; they keep a shadow of the YACC1 stack: entering g from f adds the bytes the
   YACC1 code of f has on the stack at its call of g (pushed operands, parked arguments, a recursive callee's saved
   frame) plus the return address, from a table passes.py measured in the pass's y1cc assembly ($Y1STACK_TABLE):
     F name local      a function and the most its own code (and anything it calls that is not measured here:
                       runtime helpers, the Y1/OS I/O layer, syscalls) adds below its entry
     E caller callee n  the bytes on the stack below caller's entry while callee runs, return address included
   At exit the deepest point is appended to $Y1STACK_OUT as "pass depth unknown-edges". */
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NI __attribute__((no_instrument_function))
#ifndef PROBE_NAME
#define PROBE_NAME "pass"
#endif
#define NF 2048
#define NE 16384
#define DEPTH 100000

static char *fname[NF];
static int flocal[NF], nf;
static int ekey[NE], eval_[NE];
static void *acache_a[NF * 2];
static int acache_f[NF * 2];
static int stk_f[DEPTH], stk_w[DEPTH], sp;
static long cur, deepest;
static int unknown, ready;
static char passname[256];

NI static int fidx(const char *n) {
    int i;
    for (i = 0; i < nf; i++) if (strcmp(fname[i], n) == 0) return i;
    return -1;
}
NI static int eget(int a, int b) {
    int k = a * NF + b + 1, h = (unsigned)k % NE;
    while (ekey[h]) { if (ekey[h] == k) return eval_[h]; h = (h + 1) % NE; }
    return -1;
}
NI static void eput(int a, int b, int v) {
    int k = a * NF + b + 1, h = (unsigned)k % NE;
    while (ekey[h] && ekey[h] != k) h = (h + 1) % NE;
    ekey[h] = k; eval_[h] = v;
}
NI static void done(void) {
    FILE *f;
    const char *out = getenv("Y1STACK_OUT");
    if (!out || !ready) return;
    f = fopen(out, "a");
    if (f) { fprintf(f, "%s %ld %d\n", passname, deepest, unknown); fclose(f); }
}
NI static void load(void) {
    char line[512], a[256], b[256], t[1024];
    int n;
    const char *dir = getenv("Y1STACK_TABLE_DIR");
    FILE *f;
    ready = -1;
    if (!dir) return;
    snprintf(t, sizeof t, "%s/%s.txt", dir, PROBE_NAME);
    if (!(f = fopen(t, "r"))) return;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "P %255s", a) == 1) strcpy(passname, a);
        else if (sscanf(line, "F %255s %d", a, &n) == 2 && nf < NF) { fname[nf] = strdup(a); flocal[nf++] = n; }
        else if (sscanf(line, "E %255s %255s %d", a, b, &n) == 3) {
            int i = fidx(a), j = fidx(b);
            if (i >= 0 && j >= 0) eput(i, j, n);
        }
    }
    fclose(f);
    ready = 1;
    atexit(done);
}
NI static int func_of(void *addr) {
    Dl_info di;
    int h = (int)(((unsigned long)addr >> 4) % (NF * 2));
    while (acache_a[h] && acache_a[h] != addr) h = (h + 1) % (NF * 2);
    if (acache_a[h]) return acache_f[h];
    acache_a[h] = addr;
    acache_f[h] = (dladdr(addr, &di) && di.dli_sname) ? fidx(di.dli_sname[0] == '_' ? di.dli_sname + 1 : di.dli_sname) : -1;
    if (acache_f[h] < 0 && dladdr(addr, &di) && di.dli_sname) acache_f[h] = fidx(di.dli_sname);
    return acache_f[h];
}

NI void __cyg_profile_func_enter(void *fn, void *site) {
    int g, f, w;
    (void)site;
    if (!ready) load();
    if (ready < 0 || sp >= DEPTH) return;
    g = func_of(fn);
    f = sp ? stk_f[sp - 1] : -1;
    if (g < 0) w = 0;                               /* not a YACC1 function (the host's own) */
    else if (f < 0) w = eget(fidx("main"), g) >= 0 ? eget(fidx("main"), g) + 2 : 4;   /* the OS's JSRUR to main */
    else if ((w = eget(f, g)) < 0) { unknown++; w = 2; }
    cur += w;
    stk_f[sp] = g >= 0 ? g : f; stk_w[sp] = w; sp++;
    if (g >= 0 && cur + flocal[g] > deepest) deepest = cur + flocal[g];
}
NI void __cyg_profile_func_exit(void *fn, void *site) {
    (void)fn; (void)site;
    if (ready < 0 || sp <= 0) return;
    sp--;
    cur -= stk_w[sp];
}
