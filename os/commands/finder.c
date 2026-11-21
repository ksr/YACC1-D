/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* finder.c - the desktop's file browser for the video card V4 (2026-11-20; os/lib_wm.c, BACKLOG.md "The P8X's desktop
   on this machine", step 5; after the P8X's finder.c, written again for this machine's window kernel).
     finder [-w] [dir]     the directory dir (default /) in a window on the desktop
   A row a file: its name, its size (dir for a directory), what it is - folder, program (loaded at $5000), script
   (.sh) or file. A press on a row selects it; a press on the selected row opens it, and so do Enter and the menu
   bar's Open: a folder is listed in the window; a program runs, a script runs, another file opens in write (the
   editor) - and then the finder comes back. The menu bar's Up (and Backspace) goes to the folder above, Quit (and q) ends it.
   The arrows move the selection; the list scrolls with it.
   How a program runs and the finder comes back: the finder writes the script /finder.sh - the program, then
   "finder -w dir" (after write: "finder dir") - ends, and EXECs it. -w first waits for a key, so what the program
   printed can be read on the text screen. The window kernel (/lib/wmk) is loaded again when a program has overwritten it. */
#include "../lib_fs.c"
#include "../lib_wk.c"
#include "../lib_wm.c"

#define NMAX 64
#define ROWS 21                    /* the window's content: a heading and 21 rows */

char path[64];
char ent[32];
char nm[13];
char names[832];                   /* NMAX names of 13 bytes */
int sizes[NMAX], kinds[NMAX];      /* kinds: 0 file, 1 folder, 2 program, 3 script, 4 the folder above */
int n, top, sel;
char line[48];
char script[160];

char *kindname(int k) {
    if (k == 1) return "folder";
    if (k == 2) return "program";
    if (k == 3) return "script";
    if (k == 4) return "(up)";
    return "file";
}

int slen(char *s) { int i; i = 0; while (s[i]) i++; return i; }
void scpy(char *d, char *s) { while (*s) { *d = *s; d++; s++; } *d = 0; }
void scat(char *d, char *s) { scpy(d + slen(d), s); }

/* the directory at path into names / sizes / kinds; ".." first unless it is / */
void readlist() {
    int h, k, l;
    n = 0; top = 0; sel = NMAX;
    if (path[1]) { scpy(names, ".."); sizes[0] = 0; kinds[0] = 4; n = 1; }
    h = opendir(path);
    if (!h) return;
    while (n < NMAX && readdir(h, ent)) {
        ent_name(ent, nm);
        if (nm[0] == '.') continue;
        scpy(names + n * 13, nm);
        sizes[n] = ent_len(ent);
        l = slen(nm);
        if (ent_isdir(ent)) k = 1;
        else if (ent_load(ent) == 0x5000) k = 2;
        else if (l > 3 && nm[l - 3] == '.' && nm[l - 2] == 's' && nm[l - 1] == 'h') k = 3;
        else k = 0;
        kinds[n] = k;
        n++;
    }
    fclose(h);
}

/* row i of the list as text: the name in 13, the size in 6, two blanks, the kind */
void rowtext(int i) {
    int k, v, d;
    char num[8];
    for (k = 0; k < 47; k++) line[k] = ' ';
    line[47] = 0;
    scpy(line, names + i * 13); line[slen(line)] = ' ';
    if (kinds[i] == 1 || kinds[i] == 4) { line[16] = 'd'; line[17] = 'i'; line[18] = 'r'; }
    else if (kinds[i] != 4) {
        v = sizes[i]; d = 0;
        num[0] = '0' + v % 10; v = v / 10; d = 1;
        while (v) { num[d] = '0' + v % 10; v = v / 10; d++; }
        k = 18;
        while (d) { d--; line[k - d] = num[d]; }
    }
    scpy(line + 21, kindname(kinds[i]));
}

void listing() {
    int r;
    wm_text(0, 1, "Name           Size  Kind");
    for (r = 0; r < ROWS - 1 && top + r < n; r++) { rowtext(top + r); wm_text(r + 1, 1, line); }
    if (sel < n && sel >= top && sel < top + ROWS - 1) wk_inv(wm_x[wm_cur] + 1, wm_y[wm_cur] + 2 + sel - top, wm_w[wm_cur] - 2, 1);
}

/* the window again: its title (the path) and its content */
void redraw() { wk_hide(); wm_draw(wm_n - 1); wk_show(); }

void select(int i) {
    int w, x, y;
    w = wm_n - 1; x = wm_x[w] + 1;
    wk_hide();
    if (sel < n && sel >= top && sel < top + ROWS - 1) wk_inv(x, wm_y[w] + 2 + sel - top, wm_w[w] - 2, 1);
    sel = i;
    if (sel < top) top = sel;
    else if (sel >= top + ROWS - 1) top = sel - ROWS + 2;
    else { wk_inv(x, wm_y[w] + 2 + sel - top, wm_w[w] - 2, 1); wk_show(); return; }
    wm_draw(w);                       /* scrolled: the whole list again */
    wk_show();
}

void up() {
    int i;
    if (!path[1]) return;
    i = slen(path) - 1;
    while (i > 0 && path[i] != '/') i--;
    if (i == 0) i = 1;
    path[i] = 0;
    readlist(); redraw();
}

/* the script that runs cmd and then the finder in this folder again (-w: after a key): /finder.sh, EXECed */
void runit(char *cmd, int wait) {
    int h;
    scpy(script, "-"); scat(script, cmd); scat(script, "\nfinder ");   /* - : it may fail, the finder comes back */
    if (wait) scat(script, "-w ");
    scat(script, path); scat(script, "\n");
    h = fcreate("/finder.sh", 0, 0);
    if (!h) return;
    fputs(h, script); fclose(h);
    wm_stop();
    osexec("/finder.sh", 0);
}

void open() {
    char full[64];
    if (sel >= n) return;
    if (kinds[sel] == 4) { up(); return; }
    scpy(full, path); if (path[1]) scat(full, "/"); scat(full, names + sel * 13);
    if (kinds[sel] == 1) { scpy(path, full); readlist(); redraw(); return; }
    if (kinds[sel] == 0) { scpy(line, "write "); scat(line, full); runit(line, 0); return; }
    runit(full, 1);
}

void main() {
    char *a;
    int e, k, esc;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && a[1] == 'w') {
        a = a + 2; while (*a == ' ') a++;
        puts("-- a key: back to the desktop --");
        conin();
    }
    if (*a) scpy(path, a); else scpy(path, "/");
    readlist();
    if (!wm_start("YACC1   Open   Up   Quit")) { puts("finder: no /lib/wmk"); return; }
    wm_open(2, 1, 50, 24, path, funcaddr(listing), 1);
    esc = 0;
    while (1) {
        e = wm_event();
        if (e == WM_KEY) {
            k = wk_key();
            if (esc == 1) { if (k == '[') esc = 2; else esc = 0; continue; }
            if (esc == 2) {
                esc = 0;
                if (k == 'A' && sel < n && sel > 0) select(sel - 1);
                else if (k == 'B') { if (sel >= n) { if (n) select(0); } else if (sel + 1 < n) select(sel + 1); }
                continue;
            }
            if (k == 27) esc = 1;
            else if (k == 'q' || k == 'Q') break;
            else if (k == 13 || k == 10) open();
            else if (k == 8 || k == 127) up();
        } else if (e == WM_MENU) {
            if (wm_col >= 9 && wm_col <= 12) open();
            else if (wm_col >= 16 && wm_col <= 17) up();
            else if (wm_col >= 21 && wm_col <= 24) break;
        } else if (e == WM_CLICK) {
            if (wm_cy >= 1 && top + wm_cy - 1 < n) {
                if (top + wm_cy - 1 == sel) open();
                else select(top + wm_cy - 1);
            }
        }
    }
    wm_stop();
}
