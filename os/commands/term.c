/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* term.c - a command line in a window on the video card V4 (2026-11-20; os/lib_wm.c, BACKLOG.md "The P8X's desktop
   on this machine", step 6; after the P8X's term.c, written again for this machine).
     term          the window: what was typed and printed so far (/term.log), and a prompt
   Type a command line and Enter: it runs with its output to a file and comes back in the window. How: term writes
   the script /term.sh - the line with " > /term.out" (unless it has a > of its own), then "term -r" - ends, and
   EXECs it; term -r adds /term.out to /term.log and shows the window again. So cd changes the folder of the next
   prompt, and a pipe works (its last command's output is caught). The keys: characters, Backspace, Enter (the
   video card's PS/2 keyboard). `clear` empties the log; `bye`, Quit in the menu bar or Ctrl-Q ends term.
   Since 2026-11-20 the line in the script starts with - (it may fail: the script goes on to term -r) and term sets
   ERRTO ($4FFE) before it EXECs the script, so the shell's and the programs' messages go into /term.out with the
   output; term -r clears it. A program that reads the keyboard reads it with its output in the file. /term.log
   keeps its last 2,000 characters when it passes 4,000. */
#include "../lib_fs.c"
#include "../lib_wk.c"
#include "../lib_wm.c"

#define LMAX 4000
#define VROWS 22
#define VCOLS 78

char log[4001];
int llen;
char cwd[64];
char cmd[72];
int clen;
char row[80];
char tmp[256];

int slen(char *s) { int i; i = 0; while (s[i]) i++; return i; }
void scpy(char *d, char *s) { while (*s) { *d = *s; d++; s++; } *d = 0; }
void scat(char *d, char *s) { scpy(d + slen(d), s); }

void readlog() {
    int h, n;
    llen = 0;
    h = fopen("/term.log");
    if (!h) return;
    n = freadn(h, log, 256);
    while (n) {
        llen = llen + n;
        if (llen > LMAX - 256) n = 0;
        else n = freadn(h, log + llen, 256);
    }
    fclose(h);
}

void writelog() {
    int h, p, n;
    h = fcreate("/term.log", 0, 0);
    if (!h) return;
    p = 0;
    while (p < llen) { n = llen - p; if (n > 256) n = 256; fwrite(h, log + p, n); p = p + n; }
    fclose(h);
}

void addlog(char *s, int n) {
    int i, k;
    if (llen + n > LMAX) {                     /* keep the last 2,000 characters, from a line's start */
        k = llen - 2000;
        while (k < llen && log[k - 1] != 10) k++;
        for (i = k; i < llen; i++) log[i - k] = log[i];
        llen = llen - k;
    }
    if (n > LMAX - llen) n = LMAX - llen;
    for (i = 0; i < n; i++) log[llen + i] = s[i];
    llen = llen + n;
}

/* /term.out added to the log (and then deleted) */
void addout() {
    int h, n;
    h = fopen("/term.out");
    if (!h) return;
    n = freadn(h, tmp, 256);
    while (n) { addlog(tmp, n); n = freadn(h, tmp, 256); }
    fclose(h);
    fdelete("/term.out");
    if (llen && log[llen - 1] != 10) addlog("\n", 1);
}

/* the window: the log's last lines, then the prompt and what is typed; the cursor after it */
int prow;                                  /* the prompt's row */
void content() {
    int p, n, r, k, lines;
    lines = 0;
    for (p = 0; p < llen; p++) if (log[p] == 10) lines++;
    n = lines;                                 /* the first line shown: VROWS - 1 lines above the prompt */
    if (n > VROWS - 1) n = n - (VROWS - 1); else n = 0;
    p = 0;
    while (n) { if (log[p] == 10) n--; p++; }
    r = 0;
    while (p < llen) {
        k = 0;
        while (p < llen && log[p] != 10) { if (k < VCOLS) { row[k] = log[p]; k++; } p++; }
        p++;
        row[k] = 0;
        if (k) wm_text(r, 0, row);
        r++;
    }
    prow = r;
    scpy(row, cwd); scat(row, "> "); scat(row, cmd);
    wm_text(prow, 0, row);
    k = slen(row);
    if (k < VCOLS) wk_inv(wm_x[0] + 1 + k, wm_y[0] + 1 + prow, 1, 1);
}

int plen() { return slen(cwd) + 2 + clen; }

void run() {
    int h, i, redir;
    if (clen == 0) return;
    scpy(tmp, cwd); scat(tmp, "> "); scat(tmp, cmd); scat(tmp, "\n");
    addlog(tmp, slen(tmp));
    if (slen(cmd) == 5 && cmd[0] == 'c' && cmd[1] == 'l' && cmd[2] == 'e' && cmd[3] == 'a' && cmd[4] == 'r') {
        llen = 0; writelog(); clen = 0; cmd[0] = 0;
        wk_hide(); wm_draw(0); wk_show();
        return;
    }
    writelog();
    redir = 0;
    for (i = 0; i < clen; i++) if (cmd[i] == '>') redir = 1;
    scpy(tmp, "-"); scat(tmp, cmd);         /* the - : a command that fails does not stop the script */
    if (!redir) scat(tmp, " > /term.out");
    scat(tmp, "\nterm -r\n");
    h = fcreate("/term.sh", 0, 0);
    if (!h) return;
    fputs(h, tmp); fclose(h);
    wm_stop();
    poke(ERRTO, 1);                           /* the messages go with the output, into /term.out */
    osexec("/term.sh", 0);
}

void main() {
    char *a;
    int e, k, esc, x, y;
    a = argstr();
    while (*a == ' ') a++;
    poke(ERRTO, 0);
    readlog();
    if (a[0] == '-' && a[1] == 'r') { addout(); writelog(); }
    getcwd(cwd);
    clen = 0; cmd[0] = 0;
    if (!wm_start("YACC1   Quit")) { puts("term: no /lib/wmk"); return; }
    wm_open(0, 1, 80, 24, "Terminal", funcaddr(content), 1);
    wm_cur = 0;
    esc = 0;
    while (1) {
        e = wm_event();
        if (e == WM_KEY) {
            k = wk_key();
            if (esc) { esc--; if (esc == 1 && k != '[') esc = 0; continue; }
            x = wm_x[0] + 1 + plen(); y = wm_y[0] + 1 + prow;
            if (k == 27) esc = 2;
            else if (k == 17) break;
            else if (k == 13 || k == 10) {
                if (clen == 3 && cmd[0] == 'b' && cmd[1] == 'y' && cmd[2] == 'e') break;
                run();
            } else if (k == 8 || k == 127) {
                if (clen) {
                    wk_hide();
                    if (plen() < VCOLS) wk_inv(x, y, 1, 1);
                    clen--; cmd[clen] = 0;
                    wk_text(x - 1, y, 0xFF, " ");
                    wk_inv(x - 1, y, 1, 1);
                    wk_show();
                }
            } else if (k >= 32 && k < 127 && clen < 70 && plen() < VCOLS - 1) {
                wk_hide();
                cmd[clen] = k; clen++; cmd[clen] = 0;
                row[0] = k; row[1] = 0;
                wk_text(x, y, 0xFF, row);
                wk_inv(x + 1, y, 1, 1);
                wk_show();
            }
        } else if (e == WM_MENU) {
            if (wm_col >= 9 && wm_col <= 12) break;
        }
    }
    wm_stop();
}
