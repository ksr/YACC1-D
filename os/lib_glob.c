/* lib_glob.c - filename wildcard match for /BIN commands (Y1/OS, 2026-09-23).
     gmatch(p, s)   1 when the pattern p matches the WHOLE name s, else 0
   `*` matches any run of characters (none included), `?` exactly one; any other character matches itself with
   the case folded (so `*.txt` finds README.TXT: Y1/OS names are case-sensitive, a pattern is not).
   Ported from P8X os/commands/lib_glob.c 2026-09-23, changes: the P8X gmatch recursed on every suffix after a
   `*`, which y1cc rejects (static frames, no recursion); this is the classic iterative match with one backtrack
   point: remember where the last `*` was and how much of s it has eaten, and on a mismatch let it eat one more
   character. Same results, no stack. */

int gfold(int c) { return c >= 'a' && c <= 'z' ? c - 32 : c; }

int gmatch(char *p, char *s) {
    char *star, *ss;
    star = 0; ss = 0;
    while (*s) {
        if (*p == '*') { p++; star = p; ss = s; continue; }       /* * eats nothing for now */
        if (*p && (*p == '?' || gfold(*p) == gfold(*s))) { p++; s++; continue; }
        if (!star) return 0;                                      /* no * to fall back on */
        ss++; s = ss; p = star;                                   /* the last * eats one more character */
    }
    while (*p == '*') p++;                                        /* trailing *s match the empty rest */
    return *p == 0;
}
