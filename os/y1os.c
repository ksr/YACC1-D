/* y1os.c - Y1/OS v0 (2026-09-22): a RAM-resident shell over a P8XFS v2 volume, for the YACC1.
   Loaded from the CompactFlash card (LBA 1.., OSCNT sectors) to $1000 by the monitor's O command, which JSRURs it;
   `exit` returns to the monitor. Written in C for y1cc (static frames: nothing here recurses; paths are walked
   iteratively). Console and sectors come from the ROM's BIOS vectors (lib_abi.c); the filesystem lives here.

   Shell:  dir [path]   cd path   pwd   cat path   load path   run path [args]   help   exit
           anything else: run /BIN/<name> (then <name> in the current directory) with the rest of the line as args.
   Paths: absolute /A/B or relative, '.' and '..' are the directory's own entries. Names are case-sensitive, as the
   host tool writes them (tools/p8xfs.py). Programs are compiled with `y1cc --org 0x5000` and put with
   `--load 0x5000 --exec 0x5000`; they return with RET (main returns) and find their arguments with argstr(). */
#include "lib_abi.c"
#include "y1lib.c"

#define SEC 512
#define ENT 32
#define ROOT_LBA 33
#define ROOT_SECS 4
#define F_END 0
#define F_FILE 1
#define F_DIR 2
#define F_DEL 255

char sbuf[512];                 /* the sector buffer */
char line[80];                  /* the command line */
char cwdpath[64];               /* the current path, for the prompt */
int cwd_lba, cwd_secs;          /* the current directory's extent */
int rlba, rsecs;                /* the directory resolve() is scanning */
/* the entry the last lookup found */
char e_name[13];
int e_lba, e_secs, e_len, e_lenhi, e_load, e_exec;
char e_flags;
int oscnt;

int cfread(int lba, char *buf) {
    poke(CFLBA0, lba); poke(CFLBA1, lba >> 8); poke(CFLBA2, 0);
    return bios(CFREAD, buf, 0);
}

char getch() { return bios(UARTIN, 0, 0); }

void crlf() { putchar(10); }

/* ---- directory entries ------------------------------------------------------------------------------------ */
void take_entry(int o) {        /* the e_* globals <- the 32-byte entry at sbuf[o] */
    int i;
    for (i = 0; i < 12; i++) e_name[i] = sbuf[o + i];
    e_name[12] = 0;
    e_lba = sbuf[o + 12] | (sbuf[o + 13] << 8);
    e_len = sbuf[o + 16] | (sbuf[o + 17] << 8);
    e_lenhi = sbuf[o + 18];
    e_load = sbuf[o + 20] | (sbuf[o + 21] << 8);
    e_exec = sbuf[o + 22] | (sbuf[o + 23] << 8);
    e_flags = sbuf[o + 24];
    e_secs = (e_len + 511) / 512 + e_lenhi * 128;
    if (e_secs == 0) e_secs = 1;
}

int name_is(int o, char *nm, int n) {   /* does the entry at sbuf[o] carry the n-char name nm (space padded)? */
    int i;
    for (i = 0; i < 12; i++) {
        if (i < n) { if (sbuf[o + i] != nm[i]) return 0; }
        else if (sbuf[o + i] != ' ') return 0;
    }
    return 1;
}

/* find nm (n chars) in the directory extent (dlba, dsecs); fills e_* and returns 1, or 0 */
int find_in(int dlba, int dsecs, char *nm, int n) {
    int s, o;
    for (s = 0; s < dsecs; s++) {
        if (cfread(dlba + s, sbuf)) { puts("CF read error"); return 0; }
        for (o = 0; o < 512; o += ENT) {
            if (sbuf[o + 24] == F_END) return 0;
            if (sbuf[o + 24] == F_DEL) continue;
            if (name_is(o, nm, n)) { take_entry(o); return 1; }
        }
    }
    return 0;
}

/* resolve a path: the final entry in e_*, its directory in rlba/rsecs. Returns 1 found, 0 not found. */
int resolve(char *path) {
    int i, n; char *p;
    p = path;
    if (*p == '/') { rlba = ROOT_LBA; rsecs = ROOT_SECS; p++; }
    else { rlba = cwd_lba; rsecs = cwd_secs; }
    if (*p == 0) {                          /* "/" or "" : the directory itself */
        rlba = rlba; e_lba = rlba; e_secs = rsecs; e_flags = F_DIR; e_len = rsecs * 512; e_lenhi = 0;
        strcpy(e_name, "."); return 1;
    }
    while (*p) {
        n = 0;
        while (p[n] && p[n] != '/') n++;
        if (n > 12) { puts("name too long"); return 0; }
        if (!find_in(rlba, rsecs, p, n)) return 0;
        p += n;
        if (*p == '/') {
            p++;
            if (*p == 0) break;             /* trailing slash */
            if (e_flags != F_DIR) { puts("not a directory"); return 0; }
            rlba = e_lba; rsecs = e_secs;
        }
    }
    return 1;
}

/* ---- commands ------------------------------------------------------------------------------------------- */
void cmd_dir(char *path) {
    int dlba, dsecs, s, o, i, files;
    if (*path) {
        if (!resolve(path)) { puts("not found"); return; }
        if (e_flags != F_DIR) { puts("not a directory"); return; }
        dlba = e_lba; dsecs = e_secs;
    } else { dlba = cwd_lba; dsecs = cwd_secs; }
    files = 0;
    for (s = 0; s < dsecs; s++) {
        if (cfread(dlba + s, sbuf)) { puts("CF read error"); return; }
        for (o = 0; o < 512; o += ENT) {
            if (sbuf[o + 24] == F_END) { s = dsecs; break; }
            if (sbuf[o + 24] == F_DEL) continue;
            take_entry(o);
            for (i = 0; i < 12; i++) putchar(e_name[i]);
            putchar(' ');
            if (e_flags == F_DIR) putstr("<DIR>");
            else { if (e_lenhi) { putnum(e_lenhi); putstr("x64K+"); } putnum(e_len); }
            if (e_flags == F_FILE && e_load) { putstr("  @"); puthex(e_load); }
            crlf(); files++;
        }
    }
    putnum(files); puts(" entries");
}

void path_pop() {                       /* cwdpath: drop the last component */
    int n;
    n = strlen(cwdpath);
    while (n > 1 && cwdpath[n - 1] != '/') n--;
    if (n > 1) n--;                     /* keep "/" alone */
    cwdpath[n] = 0;
}

void path_push(char *nm, int n) {       /* cwdpath += "/" + nm */
    int l, i;
    l = strlen(cwdpath);
    if (l + n + 2 > 62) return;
    if (l > 1) cwdpath[l++] = '/';
    for (i = 0; i < n; i++) cwdpath[l++] = nm[i];
    cwdpath[l] = 0;
}

void cmd_cd(char *path) {
    int n, dlba, dsecs; char *p;
    p = path;
    if (*p == '/') { dlba = ROOT_LBA; dsecs = ROOT_SECS; strcpy(cwdpath, "/"); p++; }
    else { dlba = cwd_lba; dsecs = cwd_secs; }
    while (*p) {
        n = 0;
        while (p[n] && p[n] != '/') n++;
        if (n == 0) { p++; continue; }
        if (!find_in(dlba, dsecs, p, n)) { puts("not found"); return; }
        if (e_flags != F_DIR) { puts("not a directory"); return; }
        if (n == 2 && p[0] == '.' && p[1] == '.') path_pop();
        else if (!(n == 1 && p[0] == '.')) path_push(p, n);
        dlba = e_lba; dsecs = e_secs;
        p += n;
    }
    cwd_lba = dlba; cwd_secs = dsecs;
}

int open_file(char *path) {             /* resolve a FILE; 1 ok */
    if (!resolve(path)) { puts("not found"); return 0; }
    if (e_flags != F_DIR) return 1;
    puts("is a directory"); return 0;
}

void cmd_cat(char *path) {
    int s, o, left;
    if (!open_file(path)) return;
    if (e_lenhi) { puts("too big"); return; }
    left = e_len;
    for (s = 0; left; s++) {
        if (cfread(e_lba + s, sbuf)) { puts("CF read error"); return; }
        for (o = 0; o < 512 && left; o++) { putchar(sbuf[o]); left--; }
    }
}

int load_file(char *path) {             /* file -> its load address; 1 ok */
    int s, n; char *dst;
    if (!open_file(path)) return 0;
    if (e_lenhi || e_load < TPA || e_load + e_len > TPATOP || e_load + e_len < e_load) { puts("bad load address or size"); return 0; }
    dst = e_load;
    for (s = 0; s < e_secs; s++) {
        if (cfread(e_lba + s, dst)) { puts("CF read error"); return 0; }
        dst += 512;
    }
    return 1;
}

void cmd_load(char *path) {
    if (!load_file(path)) return;
    putstr("loaded "); putnum(e_len); putstr(" bytes at $"); puthex(e_load); crlf();
}

void run_prog(char *args) {             /* e_* = the program (already loaded): args -> ARGBUF, call it */
    char *a; int i;
    a = ARGBUF;
    for (i = 0; i < 63 && args[i]; i++) a[i] = args[i];
    a[i] = 0;
    call(e_exec);
}

void cmd_run(char *rest) {              /* run path [args] */
    char *args;
    args = rest;
    while (*args && *args != ' ') args++;
    if (*args) { *args = 0; args++; }
    while (*args == ' ') args++;
    if (!load_file(rest)) return;
    run_prog(args);
}

int try_bin(char *name, char *args) {   /* /BIN/name, then name in the current directory */
    char p[20]; int n;
    n = strlen(name);
    if (n > 12) return 0;
    strcpy(p, "/BIN/"); strcpy(p + 5, name);
    if (resolve(p) && e_flags == F_FILE) { if (load_file(p)) run_prog(args); return 1; }
    if (resolve(name) && e_flags == F_FILE) { if (load_file(name)) run_prog(args); return 1; }
    return 0;
}

void cmd_help() {
    puts("Y1/OS: dir [path]  cd path  pwd  cat path  load path  run path [args]  help  exit");
    puts("       or the name of a program in /BIN (or here), followed by its arguments");
}

/* ---- the shell --------------------------------------------------------------------------------------------- */
int readline() {
    int n; char c;
    n = 0;
    while (1) {
        c = getch();
        if (c == 10 || c == 13 || c == 0) break;
        if (c == 8 || c == 127) { if (n) { n--; putstr("\b \b"); } continue; }
        if (n < 78) line[n++] = c;
    }
    line[n] = 0;
    return n;
}

void lower(char *s) { while (*s) { if (*s >= 'A' && *s <= 'Z') *s += 32; s++; } }

void main() {
    char *cmd, *rest; int n;
    cwd_lba = ROOT_LBA; cwd_secs = ROOT_SECS; strcpy(cwdpath, "/");
    oscnt = peek(OSBASE + 3);
    puts("Y1/OS v0 (2026-09-22)  P8XFS v2");
    while (1) {
        putstr(cwdpath); putstr("> ");
        n = readline();
        crlf();
        cmd = line;
        while (*cmd == ' ') cmd++;
        if (*cmd == 0) continue;
        rest = cmd;
        while (*rest && *rest != ' ') rest++;
        if (*rest) { *rest = 0; rest++; }
        while (*rest == ' ') rest++;
        lower(cmd);
        if (strcmp(cmd, "exit") == 0) { puts("bye"); return; }
        if (strcmp(cmd, "dir") == 0) cmd_dir(rest);
        else if (strcmp(cmd, "cd") == 0) cmd_cd(rest);
        else if (strcmp(cmd, "pwd") == 0) puts(cwdpath);
        else if (strcmp(cmd, "cat") == 0 || strcmp(cmd, "type") == 0) cmd_cat(rest);
        else if (strcmp(cmd, "load") == 0) cmd_load(rest);
        else if (strcmp(cmd, "run") == 0) cmd_run(rest);
        else if (strcmp(cmd, "help") == 0 || strcmp(cmd, "?") == 0) cmd_help();
        else if (!try_bin(cmd, rest)) puts("what?");
    }
}
