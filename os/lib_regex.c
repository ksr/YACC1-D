/* lib_regex.c - the basic regular expressions of grep, sed and awk (Y1/OS, 2026-09-23).
     .        any single character
     c* c+ c? zero or more / one or more / zero or one of the character (or '.') before it
     ^        anchors to the start of the line (only as the first character: match() handles it)
     $        anchors to the end of the line (only as the last character)
   everything else is a literal (no classes, no escapes, no alternation).
     matchhere(re, t)  1 when re matches a PREFIX of t; the global rend then points just past the match
     match(re, t)      1 when re matches anywhere in t (a leading ^ tries only the start)
   * and + try the fewest repetitions first, ? tries one before none: the P8X semantics, which decide what sed
   replaces (the shortest match).
   Ported from P8X os/commands/lib_regex.c 2026-09-23, changes: the P8X matchhere was self-recursive (on the rest
   of the pattern and on every quantifier alternative); y1cc rejects recursion, so it is now a loop with an explicit
   backtrack stack. A quantifier leaves one choice point (its pattern position, the text position of the next
   try, the kind); a mismatch pops the newest one and resumes there: for * and + with one more repetition (the
   point goes back on the stack), for ? with none. At most one point per quantifier is live, so RSTK (32) covers
   any 63-character pattern; past that the extra alternatives are dropped (a possible miss, never a crash). */
#define RSTK 32
char *rend;
int rs_re[RSTK], rs_t[RSTK];
char rs_k[RSTK];                        /* 1 = * or + (one more repetition next), 2 = ? (none next) */
int rsn;

void rpush(char *re, char *t, int k) {
    if (rsn < RSTK) { rs_re[rsn] = re; rs_t[rsn] = t; rs_k[rsn] = k; rsn++; }
}

int matchhere(char *re, char *t) {
    int c, ok;
    rsn = 0;
    while (1) {
        c = re[0]; ok = 1;
        if (c && re[1] == '*') { rpush(re, t, 1); re += 2; continue; }
        if (c && re[1] == '+') {
            if (*t && (*t == c || c == '.')) { t++; rpush(re, t, 1); re += 2; continue; }
            ok = 0;
        } else if (c && re[1] == '?') {
            if (*t && (*t == c || c == '.')) { rpush(re, t, 2); t++; }
            re += 2; continue;
        } else if (c == 0) { rend = t; return 1; }
        else if (c == '$' && re[1] == 0) { if (*t == 0) { rend = t; return 1; } ok = 0; }
        else if (*t && (c == '.' || c == *t)) { re++; t++; continue; }
        else ok = 0;
        if (ok) continue;
        while (1) {                     /* backtrack to the newest choice point that still has an alternative */
            if (rsn == 0) return 0;
            rsn--; re = rs_re[rsn]; t = rs_t[rsn];
            if (rs_k[rsn] == 2) { re += 2; break; }          /* c? : now with none */
            c = re[0];
            if (*t && (*t == c || c == '.')) { t++; rpush(re, t, 1); re += 2; break; }
        }
    }
}

int match(char *re, char *t) {
    if (re[0] == '^') return matchhere(re + 1, t);
    while (1) {
        if (matchhere(re, t)) return 1;
        if (*t == 0) return 0;
        t++;
    }
}
