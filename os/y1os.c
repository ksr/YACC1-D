/* y1os.c - Y1/OS v0.1 (2026-09-23; v0 2026-09-22): a RAM-resident shell and file layer over a P8XFS v2 volume, for
   the YACC1. Loaded from the CompactFlash card (LBA 1.., OSCNT sectors) to $1000 by the monitor's O command, which
   JSRURs it; `exit` returns to the monitor. Written in C for y1cc (static frames: nothing here recurses; paths are
   walked iteratively). Console and sectors come from the ROM's BIOS vectors (lib_abi.c); the filesystem lives here.

   Shell:  dir [path]  cd path  pwd  cat path  load path  run path [args]  save path addr len  del path
           mkdir path  rmdir path  ren path newname  help  exit
           anything else: run /BIN/<name> (then <name> in the current directory) with the rest of the line as args.
   Paths: absolute /A/B or relative, '.' and '..' are the directory's own entries. Names are case-sensitive, as the
   host tool writes them (tools/p8xfs.py), 1..12 characters, stored space-padded. Programs are compiled with
   `y1cc --org 0x5000` and put with `--load 0x5000 --exec 0x5000`; they return with RET (main returns) and find
   their arguments with argstr().

   The file API (2026-09-23): the fs_* functions below are the OS's own file layer; the shell's commands use them
   and nothing else. Programs reach the same functions through the syscall table: at boot main() writes the address
   of each h_* handler into SYSTAB ($0F14 + 2n, lib_abi.c SYS_n) with funcaddr(); y1cc's sys(n, a, b, c) puts the
   arguments in SYSARG0..2 ($0F06..), JSRURs the entry, and returns SYSRES ($0F0C): always a full 16-bit word,
   1/0 for yes/no, a handle or 0, a count, a byte or 65535 for none / end of file; os/lib_fs.c wraps that as
   fopen()/fgetc()/... Handles are 1..NH, each with its own 512-byte buffer and position: a read handle streams a
   file byte-wise (GETC) or sector-wise (READ, straight into the caller's buffer); a directory handle hands out the
   live 32-byte entries (READDIR); ONE write handle at a time appends at the volume's free pointer (boot block byte
   4, LE16) and CLOSE registers the file (name, start, length, load, exec) in the first free directory slot and
   moves the free pointer - as tools/p8xfs.py does, so the host tool reads what the OS wrote and vice versa.
   Directory entries are the 32-byte P8XFS v2 records, little-endian on disk (le16()/put16() assemble them
   byte-wise; the YACC1's own words are big-endian, which never matters here). Files over 64K cannot be opened
   (16-bit positions). A file a program leaves open is closed by the shell when the program returns. The console
   syscalls CONIN (no echo, through the ROM's UARTINNE vector added the same day) and CONST let a program read
   its input the way the P8X filters do. */
#include "lib_abi.c"
#include "y1lib.c"

#define SEC 512
#define ENT 32
#define ROOT_LBA 33
#define ROOT_SECS 4
#define DIR_SECS 4              /* a new directory's extent, as p8xfs.py mkdir makes it (62 entries) */
#define F_END 0
#define F_FILE 1
#define F_DIR 2
#define F_DEL 255
#define NH 4                    /* handles 1..NH */
#define M_FREE 0
#define M_READ 1
#define M_WRITE 2
#define M_DIR 3
#define NOSEC 65535             /* h_cur: nothing loaded */

char sbuf[512];                 /* the OS's own sector buffer: directory scans, the boot block */
char hbufs[2048];               /* the handles' sector buffers, 512 each: hb(h) */
char line[130];                 /* the command line (up to 128 characters; the tail goes to ARGBUF, ARGMAX) */
char cwdpath[64];               /* the current path, for the prompt and GETCWD */
char pbuf[64];                  /* a working copy of a path (parent_of, fs_chdir) */
int cwd_lba, cwd_secs;          /* the current directory's extent */
int rlba, rsecs;                /* the directory resolve() is scanning */
int p_lba, p_secs;              /* parent_of(): the directory that holds the leaf */
char *leaf;                     /* parent_of(): the last path component, NUL-terminated (inside pbuf) */
int free_lba;                   /* the volume's free-sector pointer (boot block bytes 4-5), kept in step on disk */
/* the entry the last lookup found */
int e_lba, e_secs, e_len, e_lenhi, e_load, e_exec;
char e_flags;
int e_slba, e_off;              /* where it sits on disk: sector LBA and byte offset (0/0 = no slot: the root itself) */
char e_raw[32];                 /* the record as read (its name space-padded at 0..11; ENTRY/RESOLVE copy it out)   */
/* the handle table */
char h_mode[5];
int h_lba[5], h_len[5], h_pos[5], h_cur[5];   /* start LBA; length (dir: extent bytes); position; sector in hb(h) */
int wh;                         /* the write handle in use, 0 none: CREATE/MKDIR allocate at free_lba, so one at a time */
int w_dlba, w_dsecs, w_load, w_exec;          /* the write handle's directory and header */
char w_name[13];
int oscnt;

int cfread(int lba, char *buf) {
    poke(CFLBA0, lba); poke(CFLBA1, lba >> 8); poke(CFLBA2, 0);
    return bios(CFREAD, buf, 0);
}
int cfwrite(int lba, char *buf) {
    poke(CFLBA0, lba); poke(CFLBA1, lba >> 8); poke(CFLBA2, 0);
    return bios(CFWRITE, buf, 0);
}
char *hb(int h) { return hbufs + ((h - 1) << 9); }
int le16(char *p) { return p[0] | (p[1] << 8); }
void put16(char *p, int v) { p[0] = v; p[1] = v >> 8; }
char getch() { return bios(UARTIN, 0, 0); }
void crlf() { putchar(10); }

/* ---- directory entries ------------------------------------------------------------------------------------ */
void take_entry(int o) {        /* the e_* globals <- the 32-byte entry at sbuf[o] */
    int i;
    for (i = 0; i < 32; i++) e_raw[i] = sbuf[o + i];
    e_lba = le16(sbuf + o + 12);
    e_len = le16(sbuf + o + 16);
    e_lenhi = sbuf[o + 18];
    e_load = le16(sbuf + o + 20);
    e_exec = le16(sbuf + o + 22);
    e_flags = sbuf[o + 24];
    e_off = o;
    e_secs = (e_len + 511) / 512 + e_lenhi * 128;
    if (e_secs == 0) e_secs = 1;
}

void put_name(int o, char *nm) {    /* the name field of the entry at sbuf[o] <- nm, space-padded to 12 */
    int i;
    for (i = 0; i < 12; i++) { sbuf[o + i] = *nm ? *nm : ' '; if (*nm) nm++; }
}

/* write an entry into sbuf[o]: name (NUL-terminated), start, length (< 64K), load, exec, flags; the rest zero */
void set_entry(int o, char *nm, int start, int len, int load, int exec, int flags) {
    int i;
    put_name(o, nm);
    for (i = 12; i < 32; i++) sbuf[o + i] = 0;
    put16(sbuf + o + 12, start); put16(sbuf + o + 16, len);
    put16(sbuf + o + 20, load); put16(sbuf + o + 22, exec);
    sbuf[o + 24] = flags;
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
            if (name_is(o, nm, n)) { e_slba = dlba + s; take_entry(o); return 1; }
        }
    }
    return 0;
}

/* the first free slot ($00 end mark or $FF tombstone) of a directory extent: e_slba/e_off, its sector in sbuf; 0 full */
int find_slot(int dlba, int dsecs) {
    int s, o;
    for (s = 0; s < dsecs; s++) {
        if (cfread(dlba + s, sbuf)) return 0;
        for (o = 0; o < 512; o += ENT)
            if (sbuf[o + 24] == F_END || sbuf[o + 24] == F_DEL) { e_slba = dlba + s; e_off = o; return 1; }
    }
    return 0;
}

/* resolve a path: the final entry in e_*, its directory in rlba/rsecs. Returns 1 found, 0 not found.
   "" and "/" are the current / root directory themselves (no slot: e_slba = 0). */
int resolve(char *path) {
    int i, n; char *p;
    p = path;
    if (*p == '/') { rlba = ROOT_LBA; rsecs = ROOT_SECS; p++; }
    else { rlba = cwd_lba; rsecs = cwd_secs; }
    if (*p == 0) {
        e_lba = rlba; e_secs = rsecs; e_flags = F_DIR; e_len = rsecs * 512; e_lenhi = 0; e_load = e_exec = 0;
        e_slba = e_off = 0;
        for (i = 0; i < 32; i++) e_raw[i] = i < 12 ? ' ' : 0;
        e_raw[0] = '.'; put16(e_raw + 12, e_lba); put16(e_raw + 16, e_len); e_raw[24] = F_DIR;
        return 1;
    }
    while (*p) {
        n = 0;
        while (p[n] && p[n] != '/') n++;
        if (n > 12) return 0;
        if (!find_in(rlba, rsecs, p, n)) return 0;
        p += n;
        if (*p == '/') {
            p++;
            if (*p == 0) break;             /* trailing slash */
            if (e_flags != F_DIR) return 0;
            rlba = e_lba; rsecs = e_secs;
        }
    }
    return 1;
}

/* the directory that holds a path's last component -> p_lba/p_secs, the component -> leaf (1..12 chars, not . or ..) */
int parent_of(char *path) {
    int i, n, last;
    n = strlen(path);
    if (n == 0 || n > 62) return 0;
    strcpy(pbuf, path);
    last = 65535;
    for (i = 0; i < n; i++) if (pbuf[i] == '/') last = i;
    if (last == 65535) { leaf = pbuf; p_lba = cwd_lba; p_secs = cwd_secs; }
    else {
        leaf = pbuf + last + 1;
        if (last == 0) { p_lba = ROOT_LBA; p_secs = ROOT_SECS; }
        else {
            pbuf[last] = 0;
            if (!resolve(pbuf) || e_flags != F_DIR) return 0;
            p_lba = e_lba; p_secs = e_secs;
        }
    }
    n = strlen(leaf);
    if (n == 0 || n > 12) return 0;
    if (leaf[0] == '.' && (n == 1 || (n == 2 && leaf[1] == '.'))) return 0;
    return 1;
}

void tombstone() {              /* flag the entry at e_slba/e_off deleted */
    if (cfread(e_slba, sbuf)) return;
    sbuf[e_off + 24] = F_DEL;
    cfwrite(e_slba, sbuf);
}

void write_free() {             /* the boot block's free pointer <- free_lba */
    if (cfread(0, sbuf)) return;
    put16(sbuf + 4, free_lba);
    cfwrite(0, sbuf);
}

/* ---- the file layer: what the shell and the syscalls share ------------------------------------------------- */
int new_handle() {
    int h;
    for (h = 1; h <= NH; h++) if (h_mode[h] == M_FREE) return h;
    return 0;
}

int open_ent(int mode) {        /* a handle on the entry in e_* (a file for M_READ, a directory extent for M_DIR) */
    int h;
    h = new_handle();
    if (!h) return 0;
    h_mode[h] = mode; h_lba[h] = e_lba; h_pos[h] = 0; h_cur[h] = NOSEC;
    h_len[h] = mode == M_DIR ? e_secs << 9 : e_len;
    return h;
}

int fs_open(char *path) {
    if (!resolve(path) || e_flags != F_FILE || e_lenhi) return 0;
    return open_ent(M_READ);
}

int fs_opendir(char *path) {
    if (!resolve(path) || e_flags != F_DIR) return 0;
    return open_ent(M_DIR);
}

/* (the handle fields are copied into locals below: an indexed h_pos[h] costs y1cc ~25 bytes per access, a local 3) */
int mode_of(int h) { return h < 1 || h > NH ? M_FREE : h_mode[h]; }

/* the sector holding the position -> buf (512 bytes); returns the bytes of the file in it, 0 at the end.
   The position moves to the end of that sector: sector-wise and byte-wise reads mix only at sector boundaries. */
int fs_read(int h, char *buf) {
    int s, n, len, m;
    m = mode_of(h);
    if (m == M_FREE || m == M_WRITE) return 0;
    len = h_len[h];
    if (h_pos[h] >= len) return 0;
    s = h_pos[h] >> 9;
    if (cfread(h_lba[h] + s, buf)) return 0;
    s = s << 9;
    n = len - s;
    if (n > 512) n = 512;
    h_pos[h] = s + n;
    return n;
}

int fs_getc(int h) {            /* the next byte through the handle's own buffer; 65535 at the end */
    int s, pos; char *b;
    if (mode_of(h) != M_READ) return 65535;
    pos = h_pos[h];
    if (pos >= h_len[h]) return 65535;
    s = pos >> 9; b = hb(h);
    if (s != h_cur[h]) { if (cfread(h_lba[h] + s, b)) return 65535; h_cur[h] = s; }
    h_pos[h] = pos + 1;
    return b[pos & 511];
}

int fs_readdir(int h, char *buf) {  /* the next live entry (32 bytes) -> buf; 0 at the end */
    int s, o, i, pos, len; char *b;
    if (mode_of(h) != M_DIR) return 0;
    b = hb(h); pos = h_pos[h]; len = h_len[h];
    while (pos < len) {
        s = pos >> 9;
        if (s != h_cur[h]) { if (cfread(h_lba[h] + s, b)) return 0; h_cur[h] = s; }
        o = pos & 511;
        if (b[o + 24] == F_END) { h_pos[h] = len; return 0; }
        pos += ENT;
        if (b[o + 24] == F_DEL) continue;
        h_pos[h] = pos;
        for (i = 0; i < 32; i++) buf[i] = b[o + i];
        return 1;
    }
    h_pos[h] = pos;
    return 0;
}

/* a new file at the free pointer, replacing a same-named file (tombstoned now); the entry is written at close */
int fs_create(char *path, int load, int exec) {
    int h;
    if (wh || !parent_of(path)) return 0;
    if (find_in(p_lba, p_secs, leaf, strlen(leaf))) {
        if (e_flags != F_FILE) return 0;
        tombstone();
    }
    h = new_handle();
    if (!h) return 0;
    h_mode[h] = M_WRITE; h_lba[h] = free_lba; h_len[h] = 0; h_pos[h] = 0; h_cur[h] = 0;
    memset(hb(h), 0, 512);
    strcpy(w_name, leaf);
    w_dlba = p_lba; w_dsecs = p_secs; w_load = load; w_exec = exec;
    wh = h;
    return h;
}

int fs_putc(int h, int c) {     /* append a byte; a full buffer goes to the card when the next byte arrives */
    int o, pos; char *b;
    if (h != wh) return 0;
    pos = h_pos[h];
    if (pos == 65535) return 0;
    b = hb(h);
    o = pos & 511;
    if (o == 0 && pos) {
        if (cfwrite(h_lba[h] + h_cur[h], b)) return 0;
        h_cur[h] = h_cur[h] + 1;
        memset(b, 0, 512);
    }
    b[o] = c;
    h_pos[h] = pos + 1;
    return 1;
}

int fs_write(int h, char *buf, int n) {
    int i;
    for (i = 0; i < n; i++) if (!fs_putc(h, buf[i])) return i;
    return n;
}

int fs_close(int h) {           /* a write: flush the last sector, register the file, move the free pointer */
    int ok, lba, cur;
    ok = mode_of(h);
    if (ok == M_FREE) return 0;
    if (ok == M_WRITE) {        /* the buffer always holds the last (maybe partial, maybe empty) sector */
        ok = 0; lba = h_lba[h]; cur = h_cur[h];
        if (!cfwrite(lba + cur, hb(h)) && find_slot(w_dlba, w_dsecs)) {
            set_entry(e_off, w_name, lba, h_pos[h], w_load, w_exec, F_FILE);
            if (!cfwrite(e_slba, sbuf)) { free_lba = lba + cur + 1; write_free(); ok = 1; }
        }
        wh = 0;
    }
    h_mode[h] = M_FREE;
    return ok;
}

void close_all() { int h; for (h = 1; h <= NH; h++) if (h_mode[h]) fs_close(h); }

int fs_delete(char *path) {
    if (!resolve(path) || e_flags != F_FILE || e_slba == 0) return 0;
    tombstone();
    return 1;
}

int fs_mkdir(char *path) {      /* a DIR_SECS extent at the free pointer with '.' and '..', as p8xfs.py writes them */
    int i, nl;
    if (wh || !parent_of(path)) return 0;
    if (find_in(p_lba, p_secs, leaf, strlen(leaf))) return 0;
    if (!find_slot(p_lba, p_secs)) return 0;
    nl = free_lba;
    set_entry(e_off, leaf, nl, DIR_SECS * 512, 0, 0, F_DIR);
    if (cfwrite(e_slba, sbuf)) return 0;
    memset(sbuf, 0, 512);
    set_entry(0, ".", nl, DIR_SECS * 512, 0, 0, F_DIR);
    set_entry(ENT, "..", p_lba, p_secs * 512, 0, 0, F_DIR);
    if (cfwrite(nl, sbuf)) return 0;
    memset(sbuf, 0, 64);
    for (i = 1; i < DIR_SECS; i++) if (cfwrite(nl + i, sbuf)) return 0;
    free_lba = nl + DIR_SECS; write_free();
    return 1;
}

int fs_rmdir(char *path) {      /* an empty directory (only '.' and '..' live): tombstone its entry */
    int s, o, dlba, dsecs, slba, off;
    if (!resolve(path) || e_flags != F_DIR || e_slba == 0 || e_raw[0] == '.') return 0;
    dlba = e_lba; dsecs = e_secs; slba = e_slba; off = e_off;
    for (s = 0; s < dsecs; s++) {
        if (cfread(dlba + s, sbuf)) return 0;
        for (o = 0; o < 512; o += ENT) {
            if (sbuf[o + 24] == F_END) { s = dsecs; break; }
            if (sbuf[o + 24] == F_DEL) continue;
            if (!name_is(o, ".", 1) && !name_is(o, "..", 2)) return 0;
        }
    }
    e_slba = slba; e_off = off;
    tombstone();
    return 1;
}

int fs_resolve(char *path, char *buf) {     /* 1 found, with the 32-byte entry copied to buf (if not 0) */
    int i;
    if (!resolve(path)) return 0;
    if (buf) for (i = 0; i < 32; i++) buf[i] = e_raw[i];
    return 1;
}

int fs_getcwd(char *buf) { strcpy(buf, cwdpath); return strlen(buf); }

int fs_rename(char *path, char *newname) {  /* the entry keeps its slot and directory, only its name changes */
    int slba, off, dlba, dsecs, n, i;
    if (!resolve(path) || e_slba == 0 || e_raw[0] == '.') return 0;
    slba = e_slba; off = e_off; dlba = rlba; dsecs = rsecs;
    n = strlen(newname);
    if (n == 0 || n > 12 || newname[0] == '.') return 0;
    for (i = 0; i < n; i++) if (newname[i] == '/') return 0;
    if (find_in(dlba, dsecs, newname, n)) return 0;   /* the new name is taken */
    if (cfread(slba, sbuf)) return 0;
    put_name(off, newname);
    return cfwrite(slba, sbuf) == 0;
}

int fs_entry(char *buf) {       /* the entry the last lookup found (OPEN, OPENDIR, RESOLVE, CREATE's directory walk...) */
    int i;
    for (i = 0; i < 32; i++) buf[i] = e_raw[i];
    return 1;
}

int con_in() {                  /* a console byte without echo; 65535 on Ctrl-D and on NUL (the emulator's end of input) */
    int c;
    c = bios(UARTINNE, 0, 0);
    if (c == 4 || c == 0) return 65535;
    return c;
}
int con_st() { return bios(CONST, 0, 0); }

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

int fs_chdir(char *path) {              /* 1 ok, 0 not found, 2 not a directory; cwdpath follows the components */
    int n, dlba, dsecs, r; char *p;
    strcpy(pbuf, cwdpath);              /* to restore on failure */
    p = path; r = 1;
    if (*p == '/') { dlba = ROOT_LBA; dsecs = ROOT_SECS; strcpy(cwdpath, "/"); p++; }
    else { dlba = cwd_lba; dsecs = cwd_secs; }
    while (*p) {
        n = 0;
        while (p[n] && p[n] != '/') n++;
        if (n == 0) { p++; continue; }
        if (!find_in(dlba, dsecs, p, n)) { r = 0; break; }
        if (e_flags != F_DIR) { r = 2; break; }
        if (n == 2 && p[0] == '.' && p[1] == '.') path_pop();
        else if (!(n == 1 && p[0] == '.')) path_push(p, n);
        dlba = e_lba; dsecs = e_secs;
        p += n;
    }
    if (r != 1) { strcpy(cwdpath, pbuf); return r; }
    cwd_lba = dlba; cwd_secs = dsecs;
    return 1;
}

/* ---- the syscall handlers: SYSARGn in, SYSRES out (installed in SYSTAB by main) -------------------------- */
void h_open()    { pokew(SYSRES, fs_open(peekw(SYSARG0))); }
void h_read()    { pokew(SYSRES, fs_read(peekw(SYSARG0), peekw(SYSARG1))); }
void h_getc()    { pokew(SYSRES, fs_getc(peekw(SYSARG0))); }
void h_close()   { pokew(SYSRES, fs_close(peekw(SYSARG0))); }
void h_create()  { pokew(SYSRES, fs_create(peekw(SYSARG0), peekw(SYSARG1), peekw(SYSARG2))); }
void h_write()   { pokew(SYSRES, fs_write(peekw(SYSARG0), peekw(SYSARG1), peekw(SYSARG2))); }
void h_putc()    { pokew(SYSRES, fs_putc(peekw(SYSARG0), peekw(SYSARG1))); }
void h_delete()  { pokew(SYSRES, fs_delete(peekw(SYSARG0))); }
void h_mkdir()   { pokew(SYSRES, fs_mkdir(peekw(SYSARG0))); }
void h_rmdir()   { pokew(SYSRES, fs_rmdir(peekw(SYSARG0))); }
void h_opendir() { pokew(SYSRES, fs_opendir(peekw(SYSARG0))); }
void h_readdir() { pokew(SYSRES, fs_readdir(peekw(SYSARG0), peekw(SYSARG1))); }
void h_resolve() { pokew(SYSRES, fs_resolve(peekw(SYSARG0), peekw(SYSARG1))); }
void h_getcwd()  { pokew(SYSRES, fs_getcwd(peekw(SYSARG0))); }
void h_chdir()   { pokew(SYSRES, fs_chdir(peekw(SYSARG0))); }
void h_rename()  { pokew(SYSRES, fs_rename(peekw(SYSARG0), peekw(SYSARG1))); }
void h_entry()   { pokew(SYSRES, fs_entry(peekw(SYSARG0))); }
void h_conin()   { pokew(SYSRES, con_in()); }
void h_const()   { pokew(SYSRES, con_st()); }

void install() {                /* SYSTAB <- the handlers; programs reach them with sys(SYS_x, ...) */
    int n;
    pokew(SYSTAB + 2 * SYS_OPEN, funcaddr(h_open));
    pokew(SYSTAB + 2 * SYS_READ, funcaddr(h_read));
    pokew(SYSTAB + 2 * SYS_GETC, funcaddr(h_getc));
    pokew(SYSTAB + 2 * SYS_CLOSE, funcaddr(h_close));
    pokew(SYSTAB + 2 * SYS_CREATE, funcaddr(h_create));
    pokew(SYSTAB + 2 * SYS_WRITE, funcaddr(h_write));
    pokew(SYSTAB + 2 * SYS_PUTC, funcaddr(h_putc));
    pokew(SYSTAB + 2 * SYS_DELETE, funcaddr(h_delete));
    pokew(SYSTAB + 2 * SYS_MKDIR, funcaddr(h_mkdir));
    pokew(SYSTAB + 2 * SYS_RMDIR, funcaddr(h_rmdir));
    pokew(SYSTAB + 2 * SYS_OPENDIR, funcaddr(h_opendir));
    pokew(SYSTAB + 2 * SYS_READDIR, funcaddr(h_readdir));
    pokew(SYSTAB + 2 * SYS_RESOLVE, funcaddr(h_resolve));
    pokew(SYSTAB + 2 * SYS_GETCWD, funcaddr(h_getcwd));
    pokew(SYSTAB + 2 * SYS_CHDIR, funcaddr(h_chdir));
    pokew(SYSTAB + 2 * SYS_RENAME, funcaddr(h_rename));
    pokew(SYSTAB + 2 * SYS_ENTRY, funcaddr(h_entry));
    pokew(SYSTAB + 2 * SYS_CONIN, funcaddr(h_conin));
    pokew(SYSTAB + 2 * SYS_CONST, funcaddr(h_const));
    for (n = SYS_SPARE; n <= SYS_LAST; n++) pokew(SYSTAB + 2 * n, 0);
}

/* ---- commands ------------------------------------------------------------------------------------------- */
int dir_of(char *path) {                /* a directory handle for the shell, with the messages; 0 = said why */
    if (!resolve(path)) { puts("not found"); return 0; }
    if (e_flags != F_DIR) { puts("not a directory"); return 0; }
    return open_ent(M_DIR);
}

int file_of(char *path) {               /* a read handle for the shell */
    if (!resolve(path)) { puts("not found"); return 0; }
    if (e_flags != F_FILE) { puts("is a directory"); return 0; }
    if (e_lenhi) { puts("too big"); return 0; }
    return open_ent(M_READ);
}

void cmd_dir(char *path) {
    int h, i, files; char ent[32];
    h = dir_of(path);
    if (!h) return;
    files = 0;
    while (fs_readdir(h, ent)) {
        for (i = 0; i < 12; i++) putchar(ent[i]);
        putchar(' ');
        if (ent[24] == F_DIR) putstr("<DIR>");
        else { if (ent[18]) { putnum(ent[18]); putstr("x64K+"); } putnum(le16(ent + 16)); }
        if (ent[24] == F_FILE && le16(ent + 20)) { putstr("  @"); puthex(le16(ent + 20)); }
        crlf(); files++;
    }
    fs_close(h);
    putnum(files); puts(" entries");
}

void cmd_cd(char *path) {
    int r;
    r = fs_chdir(path);
    if (r == 0) puts("not found");
    else if (r == 2) puts("not a directory");
}

void cmd_cat(char *path) {
    int h, n, o;
    h = file_of(path);
    if (!h) return;
    while ((n = fs_read(h, sbuf))) for (o = 0; o < n; o++) putchar(sbuf[o]);
    fs_close(h);
}

int load_file(char *path) {             /* file -> its load address; 1 ok */
    int h; char *dst;
    h = file_of(path);
    if (!h) return 0;
    if (e_load < TPA || e_load + e_len > TPATOP || e_load + e_len < e_load) {
        fs_close(h); puts("bad load address or size"); return 0;
    }
    dst = e_load;
    while (fs_read(h, dst)) dst += 512;
    fs_close(h);
    return 1;
}

void cmd_load(char *path) {
    if (!load_file(path)) return;
    putstr("loaded "); putnum(e_len); putstr(" bytes at $"); puthex(e_load); crlf();
}

void run_prog(char *args) {             /* e_* = the program (already loaded): args -> ARGBUF, call it */
    char *a; int i;
    a = ARGBUF;
    for (i = 0; i < ARGMAX && args[i]; i++) a[i] = args[i];
    a[i] = 0;
    call(e_exec);
    close_all();                        /* what the program left open (a pending write is registered) */
}

char *word(char *s) {                   /* NUL-terminate the word at s, return what follows it */
    while (*s && *s != ' ') s++;
    if (*s) { *s = 0; s++; }
    while (*s == ' ') s++;
    return s;
}

void cmd_run(char *rest) {              /* run path [args] */
    char *args;
    args = word(rest);
    if (!load_file(rest)) return;
    run_prog(args);
}

int hexnum(char *s) {                   /* hex digits -> int (stops at the first other character) */
    int v; char c;
    v = 0;
    while (1) {
        c = *s++;
        if (c >= '0' && c <= '9') c -= '0';
        else if (c >= 'A' && c <= 'F') c -= 55;
        else if (c >= 'a' && c <= 'f') c -= 87;
        else return v;
        v = (v << 4) | c;
    }
}

void cmd_save(char *rest) {             /* save path addr len: memory -> a file with that load/exec address */
    char *a, *l; int h, addr, len;
    a = word(rest); l = word(a);
    if (!*a || !*l) { puts("usage: save path addr len (hex)"); return; }
    addr = hexnum(a); len = hexnum(l);
    h = fs_create(rest, addr, addr);
    if (!h) { puts("cannot create"); return; }
    a = addr;
    if (fs_write(h, a, len) != len || !fs_close(h)) { puts("write error"); return; }
    putstr("saved "); putnum(len); puts(" bytes");
}

void cmd_del(char *path) { if (!fs_delete(path)) puts("not a file"); }
void cmd_ren(char *rest) {              /* ren path newname */
    char *nm;
    nm = word(rest);
    if (!*nm) { puts("usage: ren path newname"); return; }
    if (!fs_rename(rest, nm)) puts("cannot rename");
}
void cmd_mkdir(char *path) { if (!fs_mkdir(path)) puts("cannot mkdir"); }
void cmd_rmdir(char *path) { if (!fs_rmdir(path)) puts("not an empty directory"); }

void upper(char *s) { while (*s) { if (*s >= 'a' && *s <= 'z') *s -= 32; s++; } }

int try_bin(char *name, char *args) {   /* /BIN/NAME (programs are upper case), then NAME in the current directory */
    char p[20]; int n;
    n = strlen(name);
    if (n > 12) return 0;
    upper(name);
    strcpy(p, "/BIN/"); strcpy(p + 5, name);
    if (resolve(p) && e_flags == F_FILE) { if (load_file(p)) run_prog(args); return 1; }
    if (resolve(name) && e_flags == F_FILE) { if (load_file(name)) run_prog(args); return 1; }
    return 0;
}

void cmd_help() {
    puts("Y1/OS: dir [path]  cd path  pwd  cat path  load path  run path [args]  help  exit");
    puts("       save path addr len (hex)  del path  ren path newname  mkdir path  rmdir path");
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
        if (n < 128) line[n++] = c;
    }
    line[n] = 0;
    return n;
}

void lower(char *s) { while (*s) { if (*s >= 'A' && *s <= 'Z') *s += 32; s++; } }

void main() {
    char *cmd, *rest; int n;
    cwd_lba = ROOT_LBA; cwd_secs = ROOT_SECS; strcpy(cwdpath, "/");
    wh = 0;
    for (n = 0; n <= NH; n++) h_mode[n] = M_FREE;
    install();
    if (cfread(0, sbuf)) { puts("CF read error"); return; }
    oscnt = sbuf[3]; free_lba = le16(sbuf + 4);
    puts("Y1/OS v0.1 (2026-09-23)  P8XFS v2");
    while (1) {
        putstr(cwdpath); putstr("> ");
        n = readline();
        crlf();
        cmd = line;
        while (*cmd == ' ') cmd++;
        if (*cmd == 0) continue;
        rest = word(cmd);
        lower(cmd);
        if (strcmp(cmd, "exit") == 0) { puts("bye"); return; }
        if (strcmp(cmd, "dir") == 0) cmd_dir(rest);
        else if (strcmp(cmd, "cd") == 0) cmd_cd(rest);
        else if (strcmp(cmd, "pwd") == 0) puts(cwdpath);
        else if (strcmp(cmd, "cat") == 0 || strcmp(cmd, "type") == 0) cmd_cat(rest);
        else if (strcmp(cmd, "load") == 0) cmd_load(rest);
        else if (strcmp(cmd, "run") == 0) cmd_run(rest);
        else if (strcmp(cmd, "save") == 0) cmd_save(rest);
        else if (strcmp(cmd, "del") == 0) cmd_del(rest);
        else if (strcmp(cmd, "ren") == 0) cmd_ren(rest);
        else if (strcmp(cmd, "mkdir") == 0) cmd_mkdir(rest);
        else if (strcmp(cmd, "rmdir") == 0) cmd_rmdir(rest);
        else if (strcmp(cmd, "help") == 0 || strcmp(cmd, "?") == 0) cmd_help();
        else if (!try_bin(cmd, rest)) puts("what?");
    }
}
