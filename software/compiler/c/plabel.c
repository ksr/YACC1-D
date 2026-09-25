/* plabel.c - the text of a variable's or function's label, made again from its owner (cc5_layout.c, cc9_final.c).
   y1cc.c's ulabel(want) gives the want - "g_" + name for a global, "f_" + name for a function, function + "_" +
   name for a parameter or local - sanitised (a character that is not a letter, digit or '_' becomes '_', a leading
   digit gets a '_'), cut to 29 characters, or to 24 and "_n" when n labels equal to it ignoring case came first.
   So the owner and n are all a pass keeps; the text costs no memory. The pass declares, before including this:
   pnames.c (the names' text), v_name[] v_fn[] (the function a parameter or local belongs to, 0 = a global) v_ln[]
   (its n), f_name[] f_ln[]. */
#define FOWN 32768                                  /* a label's owner: variable v, or FOWN + function f */
char lwbuf[LINE_MAX];
char lqbuf[LINE_MAX];

void lwant(int own, char *buf);
void lcand(char *want, int n, char *out);
void ltext(int own, char *buf);

void lwant(int own, char *buf) {                    /* the text y1cc.c asked ulabel() for */
    buf[0] = 0;
    if (own >= FOWN) { bcat(buf, "f_"); bcat(buf, nm_text(f_name[own - FOWN])); return; }
    if (v_fn[own]) { bcat(buf, nm_text(f_name[v_fn[own]])); bchr(buf, '_'); }
    else bcat(buf, "g_");
    bcat(buf, nm_text(v_name[own]));
}
void lcand(char *want, int n, char *out) {          /* sanitised; want[:29], or want[:24] + "_n" */
    int i; int k; int c; char *q;
    q = lqbuf;                                      /* (a pointer, not bchr per character: 2026-09-25) */
    if (!want[0] || is_digit(want[0])) { *q = '_'; q++; }
    while (*want) {
        c = *want & 255;
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_')) c = '_';
        if (q >= lqbuf + LINE_MAX - 1) fail("y1cc: line too long");
        *q = c; q++; want++;
    }
    *q = 0;
    k = n ? LABEL_MAX - 5 : LABEL_MAX;
    for (i = 0; i < k && lqbuf[i]; i++) out[i] = lqbuf[i];
    out[i] = 0;
    if (n) { bchr(out, '_'); bnum(out, n); }
}
void ltext(int own, char *buf) {                    /* the label's text (buf is not lwbuf or lqbuf) */
    lwant(own, lwbuf);
    lcand(lwbuf, own >= FOWN ? f_ln[own - FOWN] & 255 : v_ln[own] & 255, buf);
}
