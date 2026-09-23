/* pack.c - compact the volume: pack
     pack        slide every live file and directory extent down over the dead sectors (deleted and replaced
                 files, the pipes' temp files, copied >> appends, removed directories), then lower the free pointer
     pack -h     usage
   New in Y1/OS 2026-09-23 (the P8X PACK was a shell built-in in p8xos.asm; this is a /BIN program so the OS image
   does not grow). It works on raw sectors, CFREAD/CFWRITE through the ROM (as y1os.c's cfread() does), because
   the syscalls hide where an entry sits; it uses the OS only for STDIO, GETCWD and CHDIR.

   The algorithm:
   1. The boot block ('P8', version 2) gives the free pointer. The tree is walked from the root without recursion
      (y1cc has none): the record table IS the work list. The root is scanned, each live entry (a file or a
      directory, not '.'/'..', not a $FF tombstone) becomes a record - its start LBA, its sectors, the record of
      the directory holding it (NOPAR = the root) and its byte position in that directory's extent - and then
      every directory record, in table order, is scanned in turn and appends its own entries (breadth first).
   2. The records are sorted by start LBA and checked: every extent at or above DATA_LBA (37, the sector after the
      root's 4-sector extent, p8xfs.py's DATA_V2), none overlapping the one before it, none past the free pointer.
      A volume that fails is left alone (run `p8xfs.py fsck` on the host): nothing is written before this point.
   3. In that order each extent slides down to `next`, the lowest free sector (next starts at DATA_LBA and grows
      by each extent's size), sector by sector through one 512-byte buffer, lowest sector first.
      WHY THIS NEVER OVERWRITES DATA NOT YET MOVED: extents are taken in increasing start order and do not
      overlap, so every extent still to come starts at or above the end of the current one, and next <= the
      current start (next = DATA_LBA + the sizes of the extents already placed, all of which lay below it). The
      copy writes sectors next .. next+n-1, all below start+n: each is a hole, a sector an earlier extent has
      already left, or a sector of this same extent that was already read (sector j is written at next+j <
      start+j, after sectors 0..j of the source were read). Nothing at or above start+n is ever written.
   4. After the copy the extent's directory entry gets the new start LBA. It is found where its directory is AT
      THAT MOMENT: the record keeps its directory's record index, not an LBA, and the directory's start is updated
      when the directory moves, so a file whose directory moved earlier is found in the directory's NEW extent
      (the copy carried the entry there), and a directory moved later carries the already-updated entry along.
      A moved directory also gets its own '.' fixed and the '..' of each direct subdirectory (wherever that
      subdirectory is at the moment). Every directory, moved or not, then has '.' and '..' checked against the
      table and rewritten if they differ: that is also what repairs a pack interrupted between those writes.
   5. The boot block gets the new free pointer, and the current directory is re-entered by its path (GETCWD
      before, CHDIR after): the OS keeps the current directory's LBA, which may have moved. The OS keeps the
      free pointer in RAM too; the shell re-reads it from the boot block after every program (y1os.c run_prog,
      2026-09-23), so the next file lands at the new free pointer.
   Refused while stdin or stdout is redirected (STDIO): a > or pipe file is a write handle growing at the old free
   pointer and a < file a read handle on an extent that may move. The shell's redirect files are the only handles
   open when a command starts (it closes whatever a program left open, and its built-ins close their own), so
   STDIO = 0 means no handle is open, the OS's write handle included.
   Tombstones stay in the directories (the OS reuses a $FF slot for the next entry, so no space is lost there).
   A power loss or reset in the middle is covered in the man page (os/man/pack): no journal. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"

#define ROOT_LBA 33
#define ROOT_SECS 4
#define DATA_LBA 37             /* the first data sector: right after the root directory's extent */
#define MAXR 800                /* live files + directories on the volume */
#define NOPAR 65535             /* r_par of an entry in the root directory */

char buf[512];                  /* the one sector buffer: boot block, directory sectors, the copy */
char cwd[64];
int r_start[MAXR];              /* the extent's start LBA (kept current as it moves) */
int r_nsec[MAXR];               /* its sectors */
int r_par[MAXR];                /* the record of the directory holding its entry, NOPAR = the root */
int r_pos[MAXR];                /* the entry's byte offset in that directory's extent (sector = r_pos >> 9) */
char r_dir[MAXR];               /* 1: a directory */
int ord[MAXR];                  /* record indices sorted by start LBA */
int nr, nfiles, ndirs;

int cf(int lba, int w) {        /* sector lba <-> buf; 1 ok, 0 error (said so) */
    int e;
    poke(CFLBA0, lba); poke(CFLBA1, lba >> 8); poke(CFLBA2, 0);
    if (w) e = bios(CFWRITE, buf, 0); else e = bios(CFREAD, buf, 0);
    if (!e) return 1;
    eputs(w ? "pack: CF write error, stopped (see man pack)" : "pack: CF read error, stopped");
    return 0;
}

int le16(int o) { return buf[o] | (buf[o + 1] << 8); }
void put16(int o, int v) { buf[o] = v; buf[o + 1] = v >> 8; }
int dirlba(int p) { return p == NOPAR ? ROOT_LBA : r_start[p]; }

/* append the live entries of directory record d (NOPAR = the root) to the table; 0 = cannot (said why) */
int scan(int d) {
    int lba, n, s, o, len, i; char f;
    lba = dirlba(d); n = d == NOPAR ? ROOT_SECS : r_nsec[d];
    for (s = 0; s < n; s++) {
        if (!cf(lba + s, 0)) return 0;
        for (o = 0; o < 512; o += 32) {
            f = buf[o + 24];
            if (f == 0) return 1;                                   /* the end mark */
            if (f != 1 && f != 2) continue;                         /* $FF tombstone */
            if (buf[o] == '.' && (buf[o + 1] == ' ' || (buf[o + 1] == '.' && buf[o + 2] == ' '))) continue;
            if (nr == MAXR) { eputs("pack: more than 800 files and directories"); return 0; }
            if (buf[o + 14] || buf[o + 15] || buf[o + 19]) { eputs("pack: an entry past LBA 65535 or 16M"); return 0; }
            i = nr++;
            r_start[i] = le16(o + 12);
            len = le16(o + 16);
            len = (len >> 9) + ((len & 511) != 0) + buf[o + 18] * 128;    /* ceil(length / 512), byte 18 = x64K */
            r_nsec[i] = len ? len : 1;                              /* an empty file still holds one sector */
            r_par[i] = d; r_pos[i] = (s << 9) + o; r_dir[i] = f == 2;
            if (r_start[i] < DATA_LBA) { eputs("pack: an entry below the data area"); return 0; }
        }
    }
    return 1;
}

/* the dot entry at byte o (0 = '.', 32 = '..') of the directory whose first sector is lba <- v; 1 ok */
int setdot(int lba, int o, int v) {
    if (!cf(lba, 0)) return 0;
    if (buf[o] != '.' || buf[o + 24] != 2 || le16(o + 12) == v) return 1;   /* not a dot entry, or already right */
    put16(o + 12, v);
    return cf(lba, 1);
}

int fixdots(int i) {            /* directory record i: '.' = itself, '..' = its parent, where they are now */
    return setdot(r_start[i], 0, r_start[i]) && setdot(r_start[i], 32, dirlba(r_par[i]));
}

int move(int i, int to) {       /* extent i -> LBA to (below it); then its entry and the dot entries; 1 ok */
    int s, n, from, lba, o, c;
    from = r_start[i]; n = r_nsec[i];
    for (s = 0; s < n; s++) if (!cf(from + s, 0) || !cf(to + s, 1)) return 0;     /* lowest sector first */
    lba = dirlba(r_par[i]) + (r_pos[i] >> 9); o = r_pos[i] & 511;  /* the entry, in its directory as it is now */
    if (!cf(lba, 0)) return 0;
    put16(o + 12, to);                                              /* bytes 14-15 are already 0 (scan checked) */
    if (!cf(lba, 1)) return 0;
    r_start[i] = to;                                                /* entries inside it are found here from now */
    if (!r_dir[i]) { nfiles++; return 1; }
    ndirs++;
    for (c = 0; c < nr; c++)                                        /* its subdirectories' '..' */
        if (r_par[c] == i && r_dir[c] && !setdot(r_start[c], 32, to)) return 0;
    return 1;
}

void main() {
    char *a; int i, j, k, v, key, next, ofree;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) {
        puts("usage: pack   compact the volume: reclaim the sectors of deleted and replaced files"); return;
    }
    if (stdio()) { eputs("pack: not with < > >> or a pipe (a redirect file is open)"); return; }
    if (!cf(0, 0)) return;
    if (buf[0] != 'P' || buf[1] != '8' || buf[2] != 2) { eputs("pack: not a P8XFS v2 volume"); return; }
    ofree = le16(4);
    getcwd(cwd);

    /* 1. the tree, breadth first: the table is the queue */
    nr = 0;
    if (!scan(NOPAR)) return;
    for (i = 0; i < nr; i++) if (r_dir[i] && !scan(i)) return;

    /* 2. sort by start LBA (insertion sort, the table is small) and check the layout before writing anything */
    for (i = 0; i < nr; i++) {
        v = i; key = r_start[i]; j = i;
        while (j && r_start[ord[j - 1]] > key) { ord[j] = ord[j - 1]; j--; }
        ord[j] = v;
    }
    next = DATA_LBA;
    for (k = 0; k < nr; k++) {
        i = ord[k];
        if (r_start[i] < next || r_start[i] + r_nsec[i] > ofree || r_start[i] + r_nsec[i] < r_start[i]) {
            eputs("pack: extents overlap or pass the free pointer: nothing changed (p8xfs.py fsck)"); return;
        }
        next = r_start[i] + r_nsec[i];
    }

    /* 3.-4. slide each extent down to next, in start order */
    next = DATA_LBA; nfiles = 0; ndirs = 0;
    for (k = 0; k < nr; k++) {
        i = ord[k];
        if (r_start[i] != next && !move(i, next)) return;
        if (r_dir[i] && !fixdots(i)) return;
        next += r_nsec[i];
    }

    /* 5. the free pointer, the current directory */
    if (next != ofree) {
        if (!cf(0, 0)) return;
        put16(4, next);
        if (!cf(0, 1)) return;
    }
    if (chdir(cwd) != 1) { chdir("/"); eputs("pack: the current directory is gone, now /"); }
    putstr("pack: "); putnum(ofree - next); putstr(" sectors reclaimed, free pointer ");
    putnum(next); putstr(" (was "); putnum(ofree); puts(")");
    putstr("pack: "); putnum(nfiles); putstr(" files and "); putnum(ndirs); puts(" directories moved");
}
