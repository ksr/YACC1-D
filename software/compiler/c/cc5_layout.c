/* cc5_layout.c - pass 5 of the multi-pass y1cc (2026-09-24): the labels and the frames. y1cc.c's declare_global
   labels and layout_func for every live function, in source order: the label of each global, of each function and
   of each parameter and local (unique ignoring case), their types and sizes, each function's frame size, and the
   dropped functions. The locals come from the declaration list cc2 wrote into each function's W.ast record
   (collect_decls()'s order), so no function body is loaded.

     cc5 W          reads W.ast (twice: layout; the dropped definitions), W.s1, W.cg (live), W.typ, W.nam
                    writes W.sym (the symbol tables for cc6-cc8) and W.lab (the labels' owners, for cc9)

   A label is never kept as text here: y1cc.c's ulabel() makes it from its "want" ("g_" + name, "f_" + name,
   function + "_" + name) - sanitised, 29 characters, or 24 and "_n" when a label equal to it ignoring case exists -
   so remembering the owner and n is enough to make the text again, which is what the uniqueness check compares.
   W.sym  main(2) nglobals(2) nstructs(2) nmembers(2) nfuncs(2) nvars(2), then the tables a column at a time (ids
          1..; w = 2-byte words, b = bytes; variables 1..nglobals are the globals; the reach rows stay in W.cg):
            structs    tag(w) size(w) mfirst(w) nmembers(w)
            members    name(w) off(w) base(w) ptr(b) count(w)
            functions  name(w) rbase(w) rptr(b) nparams(w) body(w) live(b) vfirst(w) vn(w) frame(w) frame_err(w)
                       (frame = the bytes of its variables; frame_err: the base name of the first variable whose
                       size is unknown - frame_save reports it - else 0; 65535 for a base of 0)
            variables  name(w) base(w) ptr(b) count(w) slot(b) size(w) size_err(b)
   W.lab  nvars(2) nfuncs(2) ndropped(2), then the columns name(w) fn(w) n(b) of the variables, name(w) n(b)
          laidout(b) of the functions (plabel.c makes a label's text from them), and the name(w) of every dead
          function definition, in source order (its "; dropped (never called)" line)
   A variable of an unknown struct type is not an error here: y1cc.c reports it when it prints the DS line or saves
   the frame, which is cc6's and cc8's moment (size_err, frame_err). */
#include "pcommon.c"
#include "pnames.c"
#include "past.c"

int ty_b[TYPES_MAX];
int ty_p[TYPES_MAX];
int ty_c[TYPES_MAX];
int ntypes;

int s_tag[STRUCTS_MAX];
int s_size[STRUCTS_MAX];
int s_mfirst[STRUCTS_MAX];
int s_mn[STRUCTS_MAX];
int nstructs;
int m_name[MEMBERS_MAX];
int m_off[MEMBERS_MAX];
int m_base[MEMBERS_MAX];
char m_ptr[MEMBERS_MAX];
int m_cnt[MEMBERS_MAX];
int nmembers;

int f_name[FUNCS_MAX];
int f_rbase[FUNCS_MAX];
char f_rptr[FUNCS_MAX];
int f_np[FUNCS_MAX];
int f_body[FUNCS_MAX];
char f_live[FUNCS_MAX];
char f_ln[FUNCS_MAX];           /* its label's "_n" (0 = none) */
int f_vfirst[FUNCS_MAX];        /* 0 = not laid out */
int f_vn[FUNCS_MAX];
int nfuncs;

int v_name[VARS_MAX];
int v_base[VARS_MAX];
char v_ptr[VARS_MAX];
int v_cnt[VARS_MAX];
char v_slot[VARS_MAX];
char v_ln[VARS_MAX];            /* its label's "_n" */
int v_fn[VARS_MAX];             /* the function a parameter or local belongs to, 0 for a global */
int nvars;
int nglob;

int ul_own[ULABELS_MAX];        /* the labels made so far: their owners, a case-folded hash set */
int ul_next[ULABELS_MAX];
int ul_hash[HASH_SIZE];
int nul;

int size_err;                   /* v_size(): the base name of an unknown type, else 0 */
char wbuf[LINE_MAX];
char tbuf[LINE_MAX];
char cbuf[LINE_MAX];

#include "plabel.c"

void pass_fail(char *msg) { io_fail(msg); }
int st_of(int base);
int lhash(char *s);
int ul_find(char *s);
void ulabel(int own);
int size_of(int base, int ptr);
int v_size(int v);
int fn_of(int d);
void add_var(int fn, int name, int base, int ptr, int cnt, int slot);
void layout_func(int h, int fn);
void load_s1(void);
void write_sym(void);

int st_of(int base) {                               /* the struct a tag names (the last definition wins), or 0 */
    int s;
    if (!base) return 0;
    for (s = nstructs; s > 0; s--) if (s_tag[s] == base) return s;
    return 0;
}

/* ---- labels: y1cc.c ulabel(), with the text made again from the owner (plabel.c) when it is compared --------- */
int lhash(char *s) { int h; h = 0; while (*s) { h = (h * 31 + lower(*s & 255)) % HASH_SIZE; s++; } return h; }
int ul_find(char *s) {                              /* case-folded membership */
    int id; int i;
    for (id = ul_hash[lhash(s)]; id; id = ul_next[id]) {
        ltext(ul_own[id], wbuf);
        for (i = 0; s[i] && lower(s[i] & 255) == lower(wbuf[i] & 255); i++) {}
        if (s[i] == 0 && wbuf[i] == 0) return id;
    }
    return 0;
}
void ulabel(int own) {                              /* the want in tbuf, the candidate in cbuf (ul_find uses the rest) */
    int n; int h;
    lwant(own, tbuf);
    n = 0;
    for (;;) {
        lcand(tbuf, n, cbuf);
        if (!ul_find(cbuf)) break;
        n++;
        if (n > 255) fail("y1cc: too many labels alike");
    }
    if (own >= FOWN) f_ln[own - FOWN] = n; else v_ln[own] = n;
    if (nul + 1 >= ULABELS_MAX) fail("y1cc: too many labels (ULABELS_MAX)");
    nul++;
    h = lhash(cbuf);
    ul_own[nul] = own; ul_next[nul] = ul_hash[h]; ul_hash[h] = nul;
}

/* sizes: an unknown type is recorded (size_err) for the pass that meets it in y1cc.c's order */
int size_of(int base, int ptr) {
    if (ptr > 0 || base == K_INT) return 2;
    if (base == K_CHAR) return 1;
    if (st_of(base)) return s_size[st_of(base)];
    if (!size_err) size_err = base ? base : 65535;
    return 0;
}
int v_size(int v) {
    if (v_cnt[v]) return mul16(v_cnt[v], size_of(v_base[v], v_ptr[v]));
    if (v_ptr[v] == 0 && st_of(v_base[v])) return s_size[st_of(v_base[v])];
    if (v_slot[v]) return 2;
    return size_of(v_base[v], v_ptr[v]);
}

/* ---- frames: y1cc.c layout_func and collect_decls ---------------------------------------------------------------- */
void add_var(int fn, int name, int base, int ptr, int cnt, int slot) {
    if (nvars + 1 >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
    nvars++;
    v_name[nvars] = name; v_base[nvars] = base; v_ptr[nvars] = ptr; v_cnt[nvars] = cnt; v_slot[nvars] = slot;
    v_fn[nvars] = fn;
    ulabel(nvars);
    f_vn[fn]++;
}
void layout_func(int h, int fn) {                   /* the record's heads are loaded, its declaration list is next */
    int d; int p; int base; int ptr; int name; int k; int i; int dup; int t;
    d = rec_h;
    f_vfirst[fn] = nvars + 1; f_vn[fn] = 0;
    ulabel(FOWN + fn);
    for (p = nc[d]; p; p = nx[p]) {
        base = ty_b[na[p]]; ptr = ty_p[na[p]]; name = nb[p];
        if (ptr == 0 && st_of(base)) {
            e_start("y1cc: struct passed by value ("); e_s(nm_text(name)); e_s(") not supported"); e_go();
        }
        add_var(fn, name, base, ptr, 0, ptr == 0 && base == K_CHAR);
    }
    for (k = 0; k < rec_ndecl; k++) {               /* collect_decls: the first declaration of a name wins */
        name = ri(h); t = ri(h);
        dup = 0;
        for (i = 0; i < f_vn[fn]; i++) if (v_name[f_vfirst[fn] + i] == name) dup = 1;
        if (!dup) add_var(fn, name, ty_b[t], ty_p[t], ty_c[t], ty_p[t] == 0 && ty_b[t] == K_CHAR && !ty_c[t]);
    }
}

/* ---- the driver ------------------------------------------------------------------------------------------------- */
void load_s1(void) {
    int h; int i;
    h = ropen(".typ");
    ntypes = ri(h);
    if (ntypes >= TYPES_MAX) fail("y1cc: too many types (TYPES_MAX)");
    for (i = 1; i <= ntypes; i++) { ty_b[i] = ri(h); ty_p[i] = rb(h); ty_c[i] = ri(h); }
    io_close(h);
    h = ropen(".s1");
    nstructs = ri(h); nmembers = ri(h); nfuncs = ri(h); nglob = ri(h);
    if (nstructs >= STRUCTS_MAX) fail("y1cc: too many structs (STRUCTS_MAX)");
    if (nmembers >= MEMBERS_MAX) fail("y1cc: too many struct members (MEMBERS_MAX)");
    if (nfuncs >= FUNCS_MAX || nfuncs >= FOWN) fail("y1cc: too many functions (FUNCS_MAX)");
    if (nglob >= VARS_MAX) fail("y1cc: too many variables (VARS_MAX)");
    rarr(h, s_tag + 1, nstructs); rarr(h, s_size + 1, nstructs); rarr(h, s_mfirst + 1, nstructs);
    rarr(h, s_mn + 1, nstructs);
    rarr(h, m_name + 1, nmembers); rarr(h, m_off + 1, nmembers); rarr(h, m_base + 1, nmembers);
    rarrc(h, m_ptr + 1, nmembers); rarr(h, m_cnt + 1, nmembers);
    rarr(h, f_name + 1, nfuncs); rarr(h, f_rbase + 1, nfuncs); rarrc(h, f_rptr + 1, nfuncs);
    rarr(h, f_np + 1, nfuncs); rarr(h, f_body + 1, nfuncs);
    rarr(h, v_name + 1, nglob); rarr(h, v_base + 1, nglob); rarrc(h, v_ptr + 1, nglob); rarr(h, v_cnt + 1, nglob);
    io_close(h);
    h = ropen(".cg");                               /* the live functions (cc4_calls.c) */
    ri(h); ri(h);
    rarrc(h, f_live + 1, nfuncs);
    io_close(h);
    nvars = nglob;
    for (i = 1; i <= nglob; i++) ulabel(i);         /* y1cc.c declare_global: "g_" + name, in declaration order */
}
void write_sym(void) {
    int i; int k; int fb; int fe; int main_;
    main_ = 0;
    for (i = 1; i <= nfuncs; i++) if (f_name[i] == NM_MAIN) main_ = i;
    wopen(".sym");
    wi(main_); wi(nglob); wi(nstructs); wi(nmembers); wi(nfuncs); wi(nvars);
    warr(s_tag + 1, nstructs); warr(s_size + 1, nstructs); warr(s_mfirst + 1, nstructs); warr(s_mn + 1, nstructs);
    warr(m_name + 1, nmembers); warr(m_off + 1, nmembers); warr(m_base + 1, nmembers);
    warrc(m_ptr + 1, nmembers); warr(m_cnt + 1, nmembers);
    warr(f_name + 1, nfuncs); warr(f_rbase + 1, nfuncs); warrc(f_rptr + 1, nfuncs); warr(f_np + 1, nfuncs);
    warr(f_body + 1, nfuncs); warrc(f_live + 1, nfuncs); warr(f_vfirst + 1, nfuncs); warr(f_vn + 1, nfuncs);
    for (k = 0; k < 2; k++)                         /* frame_bytes(f), then the first unknown size in it */
        for (i = 1; i <= nfuncs; i++) {
            fb = 0; fe = 0;
            if (f_vfirst[i]) {
                for (main_ = 0; main_ < f_vn[i]; main_++) {
                    size_err = 0;
                    fb = (fb + v_size(f_vfirst[i] + main_)) & 65535;
                    if (size_err && !fe) fe = size_err;
                }
            }
            wi(k ? fe : fb);
        }
    warr(v_name + 1, nvars); warr(v_base + 1, nvars); warrc(v_ptr + 1, nvars); warr(v_cnt + 1, nvars);
    warrc(v_slot + 1, nvars);
    for (i = 1; i <= nvars; i++) { size_err = 0; wi(v_size(i)); }
    for (i = 1; i <= nvars; i++) { size_err = 0; v_size(i); wb(size_err != 0); }
    wclose();
}
int fn_of(int d) {                                  /* the function a record's N_FUNC node defines */
    int i;
    for (i = 1; i <= nfuncs; i++) if (f_name[i] == nb[d]) return i;
    return 0;
}
void y1cc_main(void) {
    int h; int i; int d; int r; int nd_;
    p_args();
    names_load();
    load_s1();
    h = ropen(".ast");                              /* the live functions, in source order */
    rec_ord = 0; nd_ = 0;
    while (rec_head(h)) {
        d = rec_ent[0];
        r = 0;
        if (rec_ne == 1 && nk[d] == N_FUNC) { r = fn_of(d); if (!f_live[r]) nd_++; }
        if (r && f_live[r] && f_body[r] == rec_ord) {
            skip(h, rec_ncall * 7); layout_func(h, r); skip(h, rec_blen);
        } else rec_skip(h);
    }
    io_close(h);
    write_sym();
    wopen(".lab");                                  /* the labels' owners (plabel.c makes the text) */
    wi(nvars); wi(nfuncs); wi(nd_);
    warr(v_name + 1, nvars); warr(v_fn + 1, nvars); warrc(v_ln + 1, nvars);
    warr(f_name + 1, nfuncs); warrc(f_ln + 1, nfuncs);
    for (i = 1; i <= nfuncs; i++) wb(f_vfirst[i] != 0);
    h = ropen(".ast");                              /* the dead definitions, in source order */
    rec_ord = 0;
    while (rec_head(h)) {
        d = rec_ent[0];
        if (rec_ne == 1 && nk[d] == N_FUNC && !f_live[fn_of(d)]) wi(nb[d]);
        rec_skip(h);
    }
    io_close(h);
    wclose();
}
