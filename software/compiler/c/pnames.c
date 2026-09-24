/* pnames.c - the names' text in memory, for the passes that make labels from them (cc3, cc4, cc5): W.nam loaded whole.
   NAMES_MAX / NAMEPOOL come from the pass's limits. */
char npool[NAMEPOOL];
int nm_off[NAMES_MAX];
int nnames;

void names_load(void);
char *nm_text(int id);

void names_load(void) {
    int h; int i; int n; int c;
    h = ropen(".nam");
    nnames = ri(h);
    if (nnames + 1 >= NAMES_MAX) fail("y1cc: too many names (NAMES_MAX)");
    n = 1;                                          /* offset 0 is "", the text of name 0 */
    npool[0] = 0;
    for (i = 1; i <= nnames; i++) {
        nm_off[i] = n;
        for (;;) {
            c = rb(h);
            if (n >= NAMEPOOL - 1) fail("y1cc: name pool full (NAMEPOOL)");
            if (c == 256) c = 0;
            npool[n] = c; n++;
            if (!c) break;
        }
    }
    io_close(h);
}
char *nm_text(int id) { return npool + nm_off[id]; }
