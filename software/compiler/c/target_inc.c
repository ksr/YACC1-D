/* target_inc.c - the source-file reads of io.h for the lexer on Y1/OS (2026-09-25): #include nests deeper than
   Y1/OS's handles allow. Y1/OS has four handles and the lexer writes W.tok through one of them, so three files can be
   open for reading; a /BIN command's source nests five deep (cat.c, lib_stdin.c, lib_globx.c, lib_fs.c, lib_abi.c).
   So a handle here is virtual (1..TV_MAX, a stack: the lexer opens an #include inside the file it reads and closes
   files innermost first), and only the innermost TV_OPEN are real: opening one more closes the outermost that is
   still open (its path and the bytes read from it are kept), and reading a closed one opens it again and SEEKs to
   where it was. Included by target/lex.c and target.c instead of target_rd.c. */
int s_len(char *s);
#define TV_MAX 8
#define TV_OPEN 3
#define TV_POOL 320
int tv_h[TV_MAX + 1];           /* the real handle, 0 = closed for now */
int tv_hi[TV_MAX + 1];          /* bytes read, 24 bits: hi:lo */
int tv_lo[TV_MAX + 1];
int tv_off[TV_MAX + 1];         /* the path in tv_pool */
char tv_pool[TV_POOL];
int tv_n;                       /* files open (virtually) */
int tv_real;                    /* ... of which really */

void tv_room(void) {            /* a real handle free: close the outermost open one if TV_OPEN are */
    int i;
    if (tv_real < TV_OPEN) return;
    i = 1;
    while (!tv_h[i]) i++;
    fclose(tv_h[i]); tv_h[i] = 0; tv_real--;
}
int io_open(char *path) {
    int h; int i;
    if (tv_n >= TV_MAX) return 0;
    tv_room();
    h = fopen(path);
    if (!h) return 0;
    i = 0;
    if (tv_n) i = tv_off[tv_n] + s_len(tv_pool + tv_off[tv_n]) + 1;
    if (i + s_len(path) >= TV_POOL) { fclose(h); return 0; }
    tv_n++; tv_real++;
    tv_h[tv_n] = h; tv_hi[tv_n] = 0; tv_lo[tv_n] = 0; tv_off[tv_n] = i;
    while (*path) { tv_pool[i] = *path; i++; path++; }
    tv_pool[i] = 0;
    return tv_n;
}
int io_getc(int v) {
    int c;
    if (!tv_h[v]) {             /* closed for a deeper file: open it again where it was */
        tv_room();
        tv_h[v] = fopen(tv_pool + tv_off[v]);
        if (!tv_h[v] || !fseek(tv_h[v], tv_hi[v], tv_lo[v])) io_fail("y1cc: cannot reopen an #include");
        tv_real++;
    }
    c = fgetc(tv_h[v]);
    if (c == 65535) return 256;
    tv_lo[v]++;
    if (!tv_lo[v]) tv_hi[v]++;
    return c;
}
void io_close(int v) {          /* the innermost (the lexer closes a file when it ends) */
    if (tv_h[v]) { fclose(tv_h[v]); tv_real--; }
    tv_n = v - 1;
}
