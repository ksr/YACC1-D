/* vi.c - a minimal modal VT100 screen editor for Y1/OS (2026-09-23): the P8X /bin/vi, ported to y1cc and the
   Y1/OS file API (os/commands/VI-PORT-NOTES.md has what changed and why).
     vi NAME          edit NAME (a new, empty buffer when it does not exist)

   Needs a VT100/ANSI terminal on the serial console (the cursor is driven with ESC [ r ; c H, ESC [ 2 J, ESC [ K).
   Keys come raw, without echo, through keyin() (the ROM's UARTINNE via the KEYIN syscall: always the keyboard,
   never a < file or a pipe, 2026-09-23); output is putchar().

   Model (P8X): the file is a flat buffer of fixed-width line slots, line i at line[i*80 .. i*80+79], NUL-terminated
   (y1cc has no 2-D arrays). The cursor is (cy, cx); `top` is the first line on the screen, which maps 1:1 onto the
   terminal: a cursor move only repositions, a character edit repaints one row, a line insert/delete or a scroll
   repaints the screen (23 text rows + the status/command row 24).

   NORMAL:  h j k l (and the arrow keys) move   0 $ line start / end   G last line
            i a A  insert before / after the cursor / at the line end   o open a line below
            x  delete a character   d d  delete the line   u  undo the last change (single level)
            / pat  search forward (literal, wraps once)   n  repeat   Ctrl-L  repaint
            :w [name]  :wq [name]  :x [name]  :q  :q!
   INSERT:  printable characters insert; Enter splits the line; Backspace/DEL deletes left; Esc -> NORMAL.
   End of console input (keyin() = 65535: Ctrl-D, or the emulators' end of stdin): Esc in INSERT, `:q` in NORMAL;
   sixteen in a row abandon the edit, so a scripted run can never spin for ever.

   Limits: MAXL lines of up to 79 characters (longer lines and lines past MAXL are cut on load, and the status row
   says [cut]); a line grows to 78 characters in INSERT. Files are written with LF line ends, load/exec 0.
   y1cc: no recursion (P8X's recursive outn() is y1lib's iterative putnum()), int is unsigned. */
#include "../lib_fs.c"
#include "y1lib.c"

#define W     80                /* bytes per line slot */
#define MAXL  320               /* line slots: MAXL * W = 25,600 bytes of buffer; the image + data end at $CD8F */
#define ROWS  23                /* text rows on the screen; row 24 is the status / command row */

char line[MAXL * W];            /* flat; line i at line[i*80..] */
char path[64];                  /* the file being edited */
char wname[64];                 /* the name given to :w / :wq / :x */
char cmd[40];                   /* ':' command-line text */
char pat[40];                   /* last '/' search pattern */
char usave[W];                  /* undo: one saved line */
char note[64];                  /* a message for the status row, shown once */
int  nlines;                    /* lines in the buffer (>= 1) */
int  cy, cx;                    /* cursor line index / column */
int  top;                       /* first visible line index */
int  mode;                      /* 0 NORMAL, 1 INSERT */
int  dirty;                     /* unsaved changes */
int  done;                      /* set to quit */
int  havepat;                   /* a search pattern has been entered */
int  cut;                       /* load() had to drop characters or lines */
int  hasnote;                   /* note[] waits to be shown */
/* single-level undo, op-based (one saved line, not a second buffer):
   uop 0 none, 1 restore line[uy] = usave, 2 delete the line at uy (undo 'o'), 3 insert usave at uy (undo 'dd') */
int  uop, uy, ux;

/* ---- terminal primitives ------------------------------------------------------------------------------------- */
int rawkey() { return keyin(); }                        /* one key, no echo; 65535 = end of input (Ctrl-D) */
void esc() { putchar(27); putchar('['); }               /* CSI */
void gotoxy(int r, int c) { esc(); putnum(r); putchar(';'); putnum(c); putchar('H'); }   /* 1-based */
void clrscr() { esc(); putchar('2'); putchar('J'); }
void clreol() { esc(); putchar('K'); }

void setnote(char *s) { strcpy(note, s); hasnote = 1; }
void addnote(char *s) {                                 /* append, keeping note[] terminated inside its 64 bytes */
    int n;
    n = strlen(note);
    while (*s && n < 62) note[n++] = *s++;
    note[n] = 0;
}
void addnum(int v) {                                    /* append an unsigned decimal */
    char b[7]; int i;
    i = 6; b[6] = 0;
    while (1) { b[--i] = '0' + v % 10; v = v / 10; if (!v) break; }
    addnote(b + i);
}

/* ---- the flat line buffer ------------------------------------------------------------------------------------ */
char *lp(int i) { return line + (i << 6) + (i << 4); }  /* &line[i*80] without a runtime multiply */
int llen(int i) { return strlen(lp(i)); }
void copyline(int dst, int src) {                       /* line[dst] = line[src] */
    char *d, *s;
    d = lp(dst); s = lp(src);
    while ((*d++ = *s++)) ;
}
void openslot(int y) {                                  /* shift lines y..nlines-1 down one; slot y is then free */
    int i;
    i = nlines;
    while (i > y) { copyline(i, i - 1); i--; }
    nlines++;
}

/* ---- file load / save ---------------------------------------------------------------------------------------- */
int load(char *p) {                                     /* read p into the buffer; 1 = not found (new, empty) */
    int h, c, col; char *q;
    nlines = 0; cx = 0; cy = 0; top = 0; cut = 0;
    h = fopen(p);
    if (!h) { nlines = 1; line[0] = 0; return 1; }
    col = 0; q = line;
    while ((c = fgetc(h)) != 65535) {
        if (c == 10) {                                  /* LF ends a line */
            q[col] = 0; col = 0;
            if (++nlines >= MAXL) {                     /* full: anything after this is lost */
                if (fgetc(h) != 65535) cut = 1;
                fclose(h);
                return 0;
            }
            q = lp(nlines);
        } else if (c != 13) {                           /* CR dropped */
            if (col < W - 1) q[col++] = c; else cut = 1;
        }
    }
    fclose(h);
    q[col] = 0;                                         /* a last line without its LF, or the empty file */
    if (col || !nlines) nlines++;
    return 0;
}

int save(char *p) {                                     /* write every line + LF to p; 1 ok, 0 failed (note set) */
    int h, i, n, ok; char *q;
    h = fcreate(p, 0, 0);
    if (!h) { setnote("?cannot create "); addnote(p); return 0; }
    ok = 1;
    for (i = 0; i < nlines && ok; i++) {
        q = lp(i); n = strlen(q);
        if (n && fwrite(h, q, n) != n) ok = 0;
        if (!fputc(h, 10)) ok = 0;
    }
    if (!fclose(h)) ok = 0;
    if (!ok) { setnote("?write error on "); addnote(p); return 0; }
    setnote("\""); addnote(p); addnote("\" "); addnum(nlines); addnote(" lines written");
    return 1;
}

/* ---- redraw -------------------------------------------------------------------------------------------------- */
void drawrow(int r) {                                   /* screen text row r (0-based) */
    int li;
    gotoxy(r + 1, 1);
    li = top + r;
    if (li < nlines) putstr(lp(li)); else putchar('~');
    clreol();
}
void status() {                                         /* row 24: a pending note, else mode + name + flags */
    gotoxy(24, 1);
    if (hasnote) { putstr(note); hasnote = 0; }
    else {
        if (mode == 1) putstr("-- INSERT --  "); else putstr("              ");
        putstr(path);
        if (dirty) putstr(" [+]");
        if (cut) putstr(" [cut]");
    }
    clreol();
}
void placecur() { gotoxy(cy - top + 1, cx + 1); }
void redraw() {
    int r;
    clrscr();
    for (r = 0; r < ROWS; r++) drawrow(r);
    status();
    placecur();
}
int scroll() {                                          /* keep the cursor on the screen; 1 if top moved */
    if (cy < top) { top = cy; return 1; }
    if (cy > top + ROWS - 1) { top = cy - (ROWS - 1); return 1; }
    return 0;
}
void showmsg(char *s) { setnote(s); status(); placecur(); }

/* ---- editing ------------------------------------------------------------------------------------------------- */
void clampx() { int n; n = llen(cy); if (cx > n) cx = n; }
void inschar(int c) {                                   /* insert c at (cy, cx) */
    char *b; int n, j;
    b = lp(cy);
    n = strlen(b);
    if (n >= W - 2) return;
    for (j = n; j > cx; j--) b[j] = b[j - 1];           /* open a gap at cx */
    b[cx] = c;
    b[n + 1] = 0;
    cx++;
    dirty = 1;
}
void delchar() {                                        /* delete the character under the cursor */
    char *b;
    b = lp(cy) + cx;
    if (!*b) return;
    while ((b[0] = b[1])) b++;
    dirty = 1;
}
void opendown() {                                       /* an empty line after cy */
    if (nlines >= MAXL) return;
    openslot(cy + 1);
    lp(cy + 1)[0] = 0;
    cy++; cx = 0; dirty = 1;
}
void delline() {                                        /* delete line cy */
    int i;
    if (nlines <= 1) { line[0] = 0; cx = 0; dirty = 1; return; }
    for (i = cy; i < nlines - 1; i++) copyline(i, i + 1);
    nlines--;
    if (cy >= nlines) cy = nlines - 1;
    cx = 0; dirty = 1;
}
void splitline() {                                      /* Enter in INSERT: break the line at cx */
    char *b;
    if (nlines >= MAXL) return;
    openslot(cy + 1);
    b = lp(cy);
    strcpy(lp(cy + 1), b + cx);
    b[cx] = 0;
    cy++; cx = 0; dirty = 1;
}

/* ---- the command / search row -------------------------------------------------------------------------------- */
int readrow(int lead, char *buf) {                      /* read row-24 text after `lead`; 1 = entered, 0 = Esc */
    int k, c;
    gotoxy(24, 1); putchar(lead); clreol();
    k = 0;
    while (1) {
        c = rawkey();
        if (c == 13 || c == 10) break;
        if (c == 27 || c == 65535) return 0;            /* Esc (or end of input) cancels */
        if (c == 8 || c == 127) {
            if (k) { k--; putchar(8); putchar(' '); putchar(8); }
        } else if (c >= 32 && c < 127 && k < 38) { buf[k++] = c; putchar(c); }
    }
    buf[k] = 0;
    return 1;
}

void docmd() {                                          /* ':' w [name]  wq [name]  x [name]  q  q! */
    char *t; int k, same;
    if (!readrow(':', cmd)) return;
    wname[0] = 0;
    for (k = 0; cmd[k] && cmd[k] != ' '; k++) ;
    if (cmd[k]) { cmd[k] = 0; argword(cmd + k + 1, wname, 63); }
    t = wname[0] ? wname : path;
    same = !wname[0] || !strcmp(wname, path);           /* writing the buffer's own file clears [+] */
    if (!strcmp(cmd, "q")) {
        if (!dirty) done = 1; else setnote("no write since change (:q! to force)");
    } else if (!strcmp(cmd, "q!")) done = 1;
    else if (!strcmp(cmd, "w")) { if (save(t) && same) dirty = 0; }
    else if (!strcmp(cmd, "wq") || !strcmp(cmd, "x")) { if (save(t)) done = 1; }
    else setnote("?unknown command");
}

/* ---- undo (single level) ------------------------------------------------------------------------------------- */
void saveline() { strcpy(usave, lp(cy)); }
void snap1() { saveline(); uop = 1; uy = cy; ux = cx; }  /* a restore-this-line checkpoint */
void undo() {
    int t;
    if (!uop) { showmsg("nothing to undo"); return; }
    t = uop; uop = 0;
    if (t == 1) { strcpy(lp(uy), usave); cy = uy; cx = ux; clampx(); }
    else if (t == 2) { cy = uy; delline(); }                    /* undo an 'o' */
    else if (t == 3 && nlines < MAXL) { openslot(uy); strcpy(lp(uy), usave); cy = uy; cx = 0; }  /* undo a 'dd' */
    dirty = 1;
    scroll();
    redraw();
}

/* ---- search (literal substring, forward, wraps once) --------------------------------------------------------- */
int matchat(char *s) {
    char *p;
    p = pat;
    while (*p && *s == *p) { s++; p++; }
    return !*p;
}
int findfrom(int sy, int sx) {                          /* first match at or after (sy, sx); moves the cursor */
    int i, j; char *b;
    for (i = sy; i < nlines; i++) {
        b = lp(i);
        j = (i == sy) ? sx : 0;
        if (j > strlen(b)) continue;
        for (; b[j]; j++) if (matchat(b + j)) { cy = i; cx = j; return 1; }
    }
    return 0;
}
int search() { return findfrom(cy, cx + 1) || findfrom(0, 0); }
void dosearch() {
    if (search()) { scroll(); redraw(); }
    else { redraw(); showmsg("pattern not found"); }
}
void vmove() { clampx(); if (scroll()) redraw(); else placecur(); }   /* after a j / k / G */

void main() {
    char *a; int k, pend, ek, eofs;

    a = argstr();
    while (*a == ' ') a++;
    if (!*a || (*a == '-' && (a[1] == 'h' || a[1] == 'H'))) {
        puts("usage: vi name   modal VT100 screen editor (:wq or :x to save and quit)");
        return;
    }
    argword(a, path, 63);

    if (load(path)) setnote("[new file]");
    mode = 0; dirty = 0; done = 0; uop = 0; havepat = 0;
    pend = 0; ek = 0; eofs = 0;
    redraw();

    while (!done) {
        k = rawkey();
        if (k == 65535) {                               /* end of input */
            if (++eofs >= 16) break;                    /* the input is gone for good: abandon */
            if (mode == 1) k = 27;
            else {
                if (!dirty) done = 1; else showmsg("no write since change (:q! to force)");
                continue;
            }
        } else eofs = 0;
        if (ek == 1) {                                  /* after Esc: '[' starts an arrow-key sequence */
            ek = 0;
            if (k == '[') { ek = 2; continue; }
        } else if (ek == 2) {                           /* Esc [ A/B/C/D = up/down/right/left */
            ek = 0;
            if (k == 'A') k = 'k'; else if (k == 'B') k = 'j'; else if (k == 'C') k = 'l';
            else if (k == 'D') k = 'h'; else continue;
        }
        if (mode == 1) {                                /* ---- INSERT ---- */
            if (k == 27) {
                mode = 0; ek = 1;
                if (cx > 0) cx--;
                status(); placecur();
            } else if (k == 13 || k == 10) {
                uop = 0;                                /* a split cannot be single-line undone */
                splitline();
                scroll();
                redraw();
            } else if (k == 8 || k == 127) {
                if (cx > 0) { cx--; delchar(); drawrow(cy - top); placecur(); }
            } else if (k >= 32 && k < 127) {
                inschar(k); drawrow(cy - top); placecur();
            }
            continue;
        }
        /* ---- NORMAL ---- */
        if (pend) {                                     /* the second key of a 'd' */
            pend = 0;
            if (k == 'd') { saveline(); uop = 3; uy = cy; delline(); scroll(); redraw(); }
            continue;                                   /* any other key cancels the 'd' */
        }
        switch (k) {
        case 27: ek = 1; break;
        case 12: redraw(); break;                       /* Ctrl-L */
        case 'h': if (cx > 0) { cx--; placecur(); } break;
        case 'l': if (cx + 1 < llen(cy)) { cx++; placecur(); } break;
        case 'j': if (cy + 1 < nlines) { cy++; vmove(); } break;
        case 'k': if (cy > 0) { cy--; vmove(); } break;
        case '0': cx = 0; placecur(); break;
        case '$': cx = llen(cy); if (cx > 0) cx--; placecur(); break;
        case 'G': cy = nlines - 1; vmove(); break;
        case 'i': snap1(); mode = 1; status(); placecur(); break;
        case 'a': snap1(); if (llen(cy) > 0) cx++; clampx(); mode = 1; status(); placecur(); break;
        case 'A': snap1(); cx = llen(cy); mode = 1; status(); placecur(); break;
        case 'o':
            if (nlines >= MAXL) { showmsg("buffer full"); break; }
            uop = 2; uy = cy + 1; opendown(); mode = 1; scroll(); redraw(); break;
        case 'x': snap1(); delchar(); clampx(); drawrow(cy - top); placecur(); break;
        case 'd': pend = 1; break;
        case 'u': undo(); break;
        case '/':
            if (readrow('/', cmd)) {
                if (cmd[0]) { strcpy(pat, cmd); havepat = 1; }    /* an empty '/' repeats the last pattern */
                if (havepat) { dosearch(); break; }
            }
            redraw(); break;
        case 'n': if (havepat) dosearch(); break;
        case ':': docmd(); if (!done) redraw(); break;
        }
    }
    clrscr();
    gotoxy(1, 1);
}
