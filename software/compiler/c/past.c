/* past.c - reading W.ast (cc2_parse.c has the format) for cc3..cc6: one top-level record at a time, into node
   arrays with the record's own ids 1..n. rec_head() loads the heads (nodes 1..h: everything but a function's
   body); then either rec_body() (the lists skipped, the body loaded) or rec_skip() (the lists and the body
   skipped), or the pass reads the call list (rec_ncall entries of 7 bytes) and the declaration list (rec_ndecl
   entries of 4 bytes) itself and skips rec_blen bytes of body. NODES_MAX / ENTRIES_MAX come from the limits. */
char nk[NODES_MAX];
int na[NODES_MAX];
int nb[NODES_MAX];
int nc[NODES_MAX];
int nd[NODES_MAX];
int nx[NODES_MAX];
int rec_n;                      /* nodes in the record */
int rec_h;                      /* heads: 1..rec_h */
int rec_ncall;                  /* a function's call list and declaration list */
int rec_ndecl;
int rec_blen;                   /* bytes of the body nodes */
int rec_ne;
int rec_ent[ENTRIES_MAX];       /* the top-level nodes, in source order */
int rec_ord;                    /* the record's ordinal, 1.. (a function definition is named by it) */

int rec_head(int h);
void rec_body(int h);
void rec_skip(int h);
void rec_node(int h, int i);

void rec_node(int h, int i) {
    int m;
    nk[i] = rb(h);
    m = rb(h);
    na[i] = 0; nb[i] = 0; nc[i] = 0; nd[i] = 0; nx[i] = 0;
    if (m & 1) na[i] = ri(h);
    if (m & 2) nb[i] = ri(h);
    if (m & 4) nc[i] = ri(h);
    if (m & 8) nd[i] = ri(h);
    if (m & 16) nx[i] = ri(h);
}
int rec_head(int h) {                               /* 1 with the heads loaded, 0 at the end of W.ast */
    int i;
    if (rb(h) != 1) return 0;
    rec_n = ri(h); rec_h = ri(h); rec_ncall = ri(h); rec_ndecl = ri(h); rec_blen = ri(h); rec_ne = ri(h);
    if (rec_ne > ENTRIES_MAX) fail("y1cc: too many declarators (ENTRIES_MAX)");
    for (i = 0; i < rec_ne; i++) rec_ent[i] = ri(h);
    if (rec_h >= NODES_MAX) fail("y1cc: declaration too big (NODES_MAX)");
    for (i = 1; i <= rec_h; i++) rec_node(h, i);
    rec_ord++;
    nk[0] = 0; na[0] = 0; nb[0] = 0; nc[0] = 0; nd[0] = 0; nx[0] = 0;
    return 1;
}
void rec_body(int h) {
    int i;
    io_skip(h, rec_ncall * 7); io_skip(h, rec_ndecl * 4);
    if (rec_n >= NODES_MAX) fail("y1cc: function too big (NODES_MAX)");
    for (i = rec_h + 1; i <= rec_n; i++) rec_node(h, i);
}
void rec_skip(int h) { io_skip(h, rec_ncall * 7); io_skip(h, rec_ndecl * 4); io_skip(h, rec_blen); }
