/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* lib_wm.c - windows on the video card V4 (2026-11-20; BACKLOG.md, "The P8X's desktop on this machine", step 4),
   over the window kernel (lib_wk.c, os/wm/wmk.asm). Windows stand on the cell grid (8 x 16 dots); row 0 is the
   menu bar, rows 1-24 the desktop.

   The windows are a list, the first the bottom one. A window is its cells (x, y, w, h), a title, a tag the program
   chooses, and a content function (funcaddr(f), or 0): the library draws the paper, the striped title bar with
   the close box and the title, and the frame, then calls the content function with wm_cur set to the window's
   place in the list (wm_text() writes in it). Nothing under a window is kept: what a window uncovers is painted
   again from the list - the desktop's grey, then from the bottom up every window that overlaps the uncovered cells
   or one already painted again. So a content function must draw the same each time.
   The mouse, as the original Macintosh's: a press in a window that is not the front one brings it to the front
   (and a press in its title bar drags it as well); in the front one, the close box closes it, the title bar
   drags it - an outline of the window follows the pointer, a cell at a time, and the window is drawn at its new
   place when the button is let go - and a press in the content comes back to the program.
     wm_start(menu)        the kernel loaded and started, the desktop and the menu bar (its text); 0 = no /lib/wmk
     wm_open(x, y, w, h, title, fn, tag)   a window in front, drawn; -> its place, or WM_MAX (six at most)
     wm_event()            the kernel's next event, the window's part done here -> WM_NONE, WM_KEY (wk_key()),
                           WM_MENU (wm_col: the column), WM_CLICK (wm_win, wm_cx, wm_cy: the cell in its content),
                           WM_CLOSE (wm_tag_closed). Never waits.
     wm_front()            the tag of the front window, or 0
     wm_stop()             the text screen back
   Needs lib_fs.c and lib_wk.c included before it. */

#define WM_MAX    6
#define WM_NONE   0
#define WM_KEY    1
#define WM_MENU   5
#define WM_CLICK  6
#define WM_CLOSE  7

int wm_x[WM_MAX], wm_y[WM_MAX], wm_w[WM_MAX], wm_h[WM_MAX], wm_t[WM_MAX], wm_fn[WM_MAX], wm_tg[WM_MAX], wm_mk[WM_MAX];
int wm_n, wm_cur, wm_col, wm_win, wm_cx, wm_cy, wm_tag_closed;

char wm_buf[81];

/* the content of window wm_cur: a string at its content's row r, column c, cut at the window's right edge (what is
   drawn outside a window would not be painted again) */
void wm_text(int r, int c, char *s) {
    int n, room;
    room = wm_w[wm_cur] - 2;
    if (c >= room || r >= wm_h[wm_cur] - 2) return;
    room = room - c;
    n = 0;
    while (s[n] && n < room) { wm_buf[n] = s[n]; n++; }
    wm_buf[n] = 0;
    wk_text(wm_x[wm_cur] + 1 + c, wm_y[wm_cur] + 1 + r, 0xFF, wm_buf);
}

int wm_len(char *s) { int n; n = 0; while (s[n]) n++; return n; }

void wm_draw(int i) {
    int x, y, w, h, n;
    x = wm_x[i]; y = wm_y[i]; w = wm_w[i]; h = wm_h[i];
    wk_fill(x, y, w, h, 0xFF, 0xFF);
    wk_fill(x, y, w, 1, 0xFF, 0x00);
    wk_frame(x, y, w, h);
    wk_fill(x + 1, y, 1, 1, 0xFF, 0xFF);
    wk_frame(x + 1, y, 1, 1);
    n = wm_len(wm_t[i]);
    x = x + ((w - n - 2) >> 1);
    wk_text(x, y, 0xFF, " "); wk_text(x + 1, y, 0xFF, wm_t[i]); wk_text(x + 1 + n, y, 0xFF, " ");
    if (wm_fn[i]) { wm_cur = i; call(wm_fn[i]); }
}

/* do window i and the cells x, y, w, h overlap? */
int wm_meets(int i, int x, int y, int w, int h) {
    if (wm_x[i] >= x + w || x >= wm_x[i] + wm_w[i]) return 0;
    if (wm_y[i] >= y + h || y >= wm_y[i] + wm_h[i]) return 0;
    return 1;
}

/* the cells x, y, w, h uncovered: the grey, then every window that meets them or one painted again, bottom up */
void wm_repaint(int x, int y, int w, int h) {
    int j, k, again;
    wk_fill(x, y, w, h, 0xAA, 0x55);
    for (j = 0; j < wm_n; j++) {
        again = wm_meets(j, x, y, w, h);
        for (k = 0; k < j && !again; k++)
            if (wm_mk[k] && wm_meets(j, wm_x[k], wm_y[k], wm_w[k], wm_h[k])) again = 1;
        wm_mk[j] = again;
        if (again) wm_draw(j);
    }
}

/* window i to the front (the end of the list) */
void wm_raise(int i) {
    int a, b, c, d, t, f, g;
    a = wm_x[i]; b = wm_y[i]; c = wm_w[i]; d = wm_h[i]; t = wm_t[i]; f = wm_fn[i]; g = wm_tg[i];
    while (i < wm_n - 1) {
        wm_x[i] = wm_x[i + 1]; wm_y[i] = wm_y[i + 1]; wm_w[i] = wm_w[i + 1]; wm_h[i] = wm_h[i + 1];
        wm_t[i] = wm_t[i + 1]; wm_fn[i] = wm_fn[i + 1]; wm_tg[i] = wm_tg[i + 1];
        i++;
    }
    wm_x[i] = a; wm_y[i] = b; wm_w[i] = c; wm_h[i] = d; wm_t[i] = t; wm_fn[i] = f; wm_tg[i] = g;
}

int wm_start(char *menu) {
    if (!wk_load()) return 0;
    wk_init();
    wk_fill(0, 0, 80, 1, 0xFF, 0xFF);
    wk_frame(0, 0, 80, 1);
    wk_text(1, 0, 0xFF, menu);
    wk_fill(0, 1, 80, 24, 0xAA, 0x55);
    wm_n = 0;
    wk_show();
    return 1;
}

void wm_stop() { wk_done(); }

int wm_open(int x, int y, int w, int h, char *title, int fn, int tag) {
    if (wm_n == WM_MAX) return WM_MAX;
    wm_x[wm_n] = x; wm_y[wm_n] = y; wm_w[wm_n] = w; wm_h[wm_n] = h;
    wm_t[wm_n] = title; wm_fn[wm_n] = fn; wm_tg[wm_n] = tag;
    wm_n++;
    wk_hide(); wm_draw(wm_n - 1); wk_show();
    return wm_n - 1;
}

int wm_front() { if (wm_n) return wm_tg[wm_n - 1]; return 0; }

/* the front window's title bar pressed at cell (cx, cy): its outline follows the pointer until the button is let go */
void wm_drag(int cx, int cy) {
    int i, dx, dy, nx, ny, px, py, e;
    i = wm_n - 1;
    dx = cx - wm_x[i]; dy = cy - wm_y[i];
    nx = wm_x[i]; ny = wm_y[i];
    wk_hide(); wk_xframe(nx, ny, wm_w[i], wm_h[i]); wk_show();
    while (1) {
        e = wk_event();
        if (e == 4 && !(wk_buttons() & 1)) break;
        if (e == 2) {
            px = (wk_mx() + 1) >> 3; py = (wk_my() + 1) >> 4;
            if (px < dx) px = 0; else px = px - dx;
            if (px + wm_w[i] > 80) px = 80 - wm_w[i];
            if (py < dy + 1) py = 1; else py = py - dy;
            if (py + wm_h[i] > 25) py = 25 - wm_h[i];
            if (px != nx || py != ny) {
                wk_hide();
                wk_xframe(nx, ny, wm_w[i], wm_h[i]);
                nx = px; ny = py;
                wk_xframe(nx, ny, wm_w[i], wm_h[i]);
                wk_show();
            }
        }
    }
    wk_hide();
    wk_xframe(nx, ny, wm_w[i], wm_h[i]);
    if (nx != wm_x[i] || ny != wm_y[i]) {
        px = wm_x[i]; py = wm_y[i];
        wm_x[i] = nx; wm_y[i] = ny;
        wm_n--;                                   /* the others first, the moved one last, in front */
        wm_repaint(px, py, wm_w[i], wm_h[i]);
        wm_n++;
        wm_draw(i);
    }
    wk_show();
}

int wm_event() {
    int e, cx, cy, i, j, x, y, w, h;
    e = wk_event();
    if (e == 1) return WM_KEY;
    if (e != 3 || !(wk_down() & 1)) return WM_NONE;
    cx = (wk_mx() + 1) >> 3; cy = (wk_my() + 1) >> 4;      /* the arrow's tip */
    if (cy == 0) { wm_col = cx; return WM_MENU; }
    i = WM_MAX;                                            /* (int is unsigned in y1cc: no -1 here) */
    for (j = 0; j < wm_n; j++) if (wm_meets(j, cx, cy, 1, 1)) i = j;
    if (i == WM_MAX) return WM_NONE;
    if (i != wm_n - 1) {                                   /* to the front; from its title bar it is dragged too */
        wm_raise(i); i = wm_n - 1;
        wk_hide(); wm_draw(i); wk_show();
        if (cy == wm_y[i] && cx != wm_x[i] + 1) wm_drag(cx, cy);
        return WM_NONE;
    }
    if (cy == wm_y[i]) {
        if (cx == wm_x[i] + 1) {                           /* the close box */
            x = wm_x[i]; y = wm_y[i]; w = wm_w[i]; h = wm_h[i];
            wm_tag_closed = wm_tg[i];
            wm_n--;
            wk_hide(); wm_repaint(x, y, w, h); wk_show();
            return WM_CLOSE;
        }
        wm_drag(cx, cy);
        return WM_NONE;
    }
    wm_win = i; wm_cx = cx - wm_x[i] - 1; wm_cy = cy - wm_y[i] - 1;
    return WM_CLICK;
}
