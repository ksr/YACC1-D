/* lib_globx.c - expand a filename glob into the list of matching files (Y1/OS, 2026-09-23).
     glob_expand(pat, out, maxn) -> count
       pat    the pattern word (ends at NUL or space), e.g. "*.C" (the current directory) or "/MAN/C*"
       out    maxn slots of GSLOT (64) bytes; slot i = the directory part of pat + the matched name, NUL-ended,
              so it opens the way the bare word would (a relative prefix stays relative to the current directory)
       maxn   the slot count; matches past it are dropped
     isglob(w)  1 when the word w (ends at NUL or space) holds * or ?
   Only FILES match (not directories, not . and ..), in directory order. Uses one directory handle, closed again
   before returning. Needs lib_glob.c (gmatch) and lib_fs.c (opendir, readdir, ent_*), both included here.
   Ported from P8X os/commands/lib_globx.c 2026-09-23, changes: opendir/readdir/fclose on a handle of its own
   instead of FOPENDIR/SYS_OPENCWD + FNEXT + SYS_DIRENTRY, so the FSDIRBUF page juggling is gone (every Y1/OS
   handle owns its buffer); names come from ent_name(). */
#include "lib_fs.c"
#include "lib_glob.c"
#define GSLOT 64

int isglob(char *w) {
    while (*w && *w != ' ') { if (*w == '*' || *w == '?') return 1; w++; }
    return 0;
}

int glob_expand(char *pat, char *out, int maxn) {
    char gdir[GSLOT], gleaf[16], gnm[13], gent[32];
    int i, n, last, cnt, h; char *o;
    n = 0; last = 65535;
    while (pat[n] && pat[n] != ' ') { if (pat[n] == '/') last = n; n++; }
    gdir[0] = 0;
    i = 0;
    if (last != 65535) {                         /* the directory part, trailing '/' included */
        if (last > GSLOT - 14) return 0;         /* dir + a 12-character name + NUL must fit a slot */
        for (i = 0; i <= last; i++) gdir[i] = pat[i];
        gdir[i] = 0;
    }
    n -= i; if (n > 15) n = 15;                  /* the leaf pattern (longer can match no 12-char name) */
    pat += i;
    for (i = 0; i < n; i++) gleaf[i] = pat[i];
    gleaf[n] = 0;
    h = opendir(gdir);                           /* "" = the current directory */
    if (!h) return 0;
    cnt = 0;
    while (cnt < maxn && readdir(h, gent)) {
        if (!ent_isfile(gent)) continue;
        ent_name(gent, gnm);
        if (!gmatch(gleaf, gnm)) continue;
        o = out + cnt * GSLOT;
        strcpy(o, gdir); strcpy(o + strlen(gdir), gnm);
        cnt++;
    }
    fclose(h);
    return cnt;
}
