/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* write.c - the desktop's text editor on the video card V4 (2026-11-20; os/lib_wm.c, BACKLOG.md "The P8X's desktop
   on this machine", step 6; after the P8X's write.c, written again for this machine's window kernel).
     write [file]      edit the file (default /write.txt; a new one if it is not there)
   The text in a window of 78 x 22 cells, the cursor an inverted cell. Keys (the video card's PS/2 keyboard):
     a printable character  inserted at the cursor          Enter      a new line
     Backspace              the character before it out     Delete     the character under it out
     the arrows             the cursor; Home / End the line's start / end; Page Up / Page Down 21 lines
     Ctrl-S                 save (Save in the menu bar)     Ctrl-Q     quit (Quit in the menu bar), without saving
   A press in the text puts the cursor there. The menu bar says "edited" after a change and "saved" after a save.
   A line longer than 78 characters shows its first 78. The text is at most 4,000 characters.
   Drawing: a key redraws the line from the cursor on (a character is about 120 instructions; the rest of the row is
   a fill), a new line or a joined line the rows below, a scroll the window's 22 rows. */
#include "../lib_fs.c"
#include "../lib_wk.c"
#include "../lib_wm.c"

#define BMAX 4000
#define VROWS 22
#define VCOLS 78

char buf[4001];
int blen, cur, top, edited;
char fpath[64];
char row[80];

int slen(char *s) { int i; i = 0; while (s[i]) i++; return i; }
void scpy(char *d, char *s) { while (*s) { *d = *s; d++; s++; } *d = 0; }

void load() {
    int h, n;
    blen = 0;
    h = fopen(fpath);
    if (!h) return;
    n = freadn(h, buf, 256);
    while (n) {
        blen = blen + n;
        if (blen > BMAX - 256) n = 0;
        else n = freadn(h, buf + blen, 256);
    }
    fclose(h);
}

int lstart(int p) { while (p > 0 && buf[p - 1] != 10) p--; return p; }
int lend(int p) { while (p < blen && buf[p] != 10) p++; return p; }
/* the start of line n (0 the first) */
int linepos(int n) {
    int p;
    p = 0;
    while (n && p < blen) { if (buf[p] == 10) n--; p++; }
    if (n) return BMAX + 1;                  /* no such line */
    return p;
}
int lineof(int p) { int i, n; n = 0; for (i = 0; i < p; i++) if (buf[i] == 10) n++; return n; }

/* the cursor's place in the window: its row (VROWS when it is not in view) and column */
int crow() { int r; r = lineof(cur); if (r < top || r >= top + VROWS) return VROWS; return r - top; }
int ccol() { return cur - lstart(cur); }

void flip() {                             /* the cursor's cell inverted */
    int r, c;
    r = crow(); c = ccol();
    if (r < VROWS && c < VCOLS) wk_inv(wm_x[0] + 1 + c, wm_y[0] + 1 + r, 1, 1);
}

/* row r of the window from column c on: the text, then paper */
void drawrow(int r, int c) {
    int p, e, n;
    n = 0;
    p = linepos(top + r);
    if (p <= blen) {
        e = lend(p);
        p = p + c;
        while (p < e && c + n < VCOLS) { row[n] = buf[p]; p++; n++; }
    }
    row[n] = 0;
    if (n) wm_text(r, c, row);
    if (c + n < VCOLS) wk_fill(wm_x[0] + 1 + c + n, wm_y[0] + 1 + r, VCOLS - c - n, 1, 0xFF, 0xFF);
}

void rows(int from) { int r; for (r = from; r < VROWS; r++) drawrow(r, 0); }

void content() { wm_cur = 0; rows(0); flip(); }

void status() { wk_text(68, 0, 0xFF, edited ? "edited " : "saved  "); }

/* the cursor moved (or the text changed above from): into view, and drawn */
void show(int from) {
    int l;
    l = lineof(cur);
    if (l < top) { top = l; from = 0; }
    else if (l >= top + VROWS) { top = l - VROWS + 1; from = 0; }
    if (from < VROWS) rows(from);
    flip();
}

void setedit() { if (!edited) { edited = 1; status(); } }

void ins(int ch) {
    int i, r, c;
    if (blen >= BMAX) return;
    for (i = blen; i > cur; i--) buf[i] = buf[i - 1];
    buf[cur] = ch; blen++;
    r = crow(); c = ccol();
    cur++;
    setedit();
    if (ch == 10 || r == VROWS) { show(r); return; }
    drawrow(r, c);
    show(VROWS);
}

void del(int at) {                       /* the character at `at` out; the cursor to `at` */
    int i, r, c, nl;
    if (at >= blen) return;
    nl = buf[at] == 10;
    for (i = at; i < blen - 1; i++) buf[i] = buf[i + 1];
    blen--;
    cur = at;
    setedit();
    r = crow(); c = ccol();
    if (nl || r == VROWS) { show(r); return; }
    drawrow(r, c);
    show(VROWS);
}

void move(int to) { flip(); cur = to; show(VROWS); }

void vert(int lines, int down) {
    int c, l, p;
    c = ccol(); l = lineof(cur);
    if (down) l = l + lines;
    else if (l < lines) l = 0; else l = l - lines;
    p = linepos(l);
    if (p > blen) p = lstart(blen);
    if (p + c > lend(p)) c = lend(p) - p;
    move(p + c);
}

void save() {
    int h, p, n;
    h = fcreate(fpath, 0, 0);
    if (!h) return;
    p = 0;
    while (p < blen) { n = blen - p; if (n > 256) n = 256; fwrite(h, buf + p, n); p = p + n; }
    fclose(h);
    edited = 0;
    status();
}

void main() {
    char *a;
    int e, k, esc, p, l;
    a = argstr();
    while (*a == ' ') a++;
    if (*a) scpy(fpath, a); else scpy(fpath, "/write.txt");
    load();
    cur = 0; top = 0; edited = 0;
    if (!wm_start("YACC1   Save   Quit")) { puts("write: no /lib/wmk"); return; }
    wm_open(0, 1, 80, 24, fpath, funcaddr(content), 1);
    wm_cur = 0;
    status();
    esc = 0;
    while (1) {
        e = wm_event();
        if (e == WM_KEY) {
            k = wk_key();
            wk_hide();
            if (esc == 1) { if (k == '[') esc = 2; else esc = 0; }
            else if (esc == 2) {
                esc = 0;
                if (k == 'A') vert(1, 0);
                else if (k == 'B') vert(1, 1);
                else if (k == 'C') { if (cur < blen) move(cur + 1); }
                else if (k == 'D') { if (cur > 0) move(cur - 1); }
                else if (k == 'H') move(lstart(cur));
                else if (k == 'F') move(lend(cur));
                else if (k == '5' || k == '6') esc = k;    /* the ~ follows */
            }
            else if (esc == '5' || esc == '6') { if (esc == '5') vert(VROWS - 1, 0); else vert(VROWS - 1, 1); esc = 0; }
            else if (k == 27) esc = 1;
            else if (k == 17) break;                       /* Ctrl-Q */
            else if (k == 19) save();                      /* Ctrl-S */
            else if (k == 13 || k == 10) ins(10);
            else if (k == 8) { if (cur > 0) del(cur - 1); }
            else if (k == 127) del(cur);
            else if (k >= 32 && k < 127) ins(k);
            wk_show();
        } else if (e == WM_MENU) {
            if (wm_col >= 9 && wm_col <= 12) { wk_hide(); save(); wk_show(); }
            else if (wm_col >= 16 && wm_col <= 19) break;
        } else if (e == WM_CLICK) {
            l = top + wm_cy;
            p = linepos(l);
            if (p > blen) p = lstart(blen);
            if (p + wm_cx > lend(p)) p = lend(p); else p = p + wm_cx;
            wk_hide(); move(p); wk_show();
        }
    }
    wm_stop();
}
