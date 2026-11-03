/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* mkdir.c - make a directory: mkdir [-s N] path (2026-11-03)
     mkdir path        4 sectors, 62 entries: the MKDIR syscall, the same as the shell's built-in mkdir
     mkdir -s N path   N sectors, 1..64: 16 entries a sector, less "." and ".." (-s 16: 254, -s 64: 1022)
   A directory's size is fixed when it is made (P8XFS keeps it in the directory's entry and in its "." entry), and
   the OS and its MKDIR syscall always make 4 sectors. With -s this program writes the directory itself on raw
   sectors (CFREAD/CFWRITE through the ROM), as /BIN/PACK does and the kernel's fs_mkdir would: the parent's first
   free slot (an end-of-directory or deleted entry), the new extent at the volume's free pointer ("." and ".." in
   its first sector, the rest zeros), then the free pointer raised by N, and the entry written last, so an
   interruption leaves at worst unused sectors above an unchanged directory. The shell re-reads the free pointer
   after every program (y1os.c run_prog), as it does after pack. Refused with stdout redirected: a > file or a pipe
   is a file growing at the same free pointer. "cannot mkdir" and status 1 on any failure (a running script stops);
   the shell's built-in mkdir stays for a card with no /BIN yet. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
#define F_DIR 2
#define F_DEL 255

char buf[512];
char path[64], parent[64], leaf[16], ent[32];

int cf(int lba, int w) {        /* sector lba <-> buf; 1 ok */
    poke(CFLBA0, lba); poke(CFLBA1, lba >> 8); poke(CFLBA2, 0);
    if (w) return !bios(CFWRITE, buf, 0);       /* (bios() takes a constant address) */
    return !bios(CFREAD, buf, 0);
}

void put16(int o, int v) { buf[o] = v; buf[o + 1] = v >> 8; }

void entry(int o, char *nm, int lba, int secs) {   /* a directory's entry at buf[o]: name, start, length, flags */
    int i;
    for (i = 0; i < 32; i++) buf[o + i] = 0;
    for (i = 0; i < 12; i++) { buf[o + i] = *nm ? *nm : ' '; if (*nm) nm++; }
    put16(o + 12, lba); put16(o + 16, secs << 9); buf[o + 24] = F_DIR;
}

void fail() { eputs("cannot mkdir"); osexit(1); }

void main() {
    char *a; int n, i, k, plba, psecs, s, o, slba, sofs, nl;
    a = argstr();
    while (*a == ' ') a++;
    n = 0;
    if (a[0] == '-' && a[1] == 's') {
        a = argword(a, path, 63);
        a = argword(a, path, 63);
        for (i = 0; path[i] >= '0' && path[i] <= '9'; i++) n = n * 10 + path[i] - '0';
        if (path[i] || !n || n > 64) { eputs("usage: mkdir [-s sectors] path   (1..64 sectors, 16 entries each)"); osexit(1); }
    }
    argword(a, path, 63);
    if (!path[0] || (a[0] == '-' && !n)) { eputs("usage: mkdir [-s sectors] path   (1..64 sectors, 16 entries each)"); osexit(1); }
    if (!n) { if (!fmkdir(path)) fail(); return; }  /* the 4-sector directory: the syscall */
    if (stdio() & 2) { eputs("mkdir: -s not with > or a pipe (a file is growing at the free pointer)"); osexit(1); }
    k = 65535;                  /* the parent's path and the leaf */
    for (i = 0; path[i]; i++) if (path[i] == '/') k = i;
    if (k == 65535) { parent[0] = 0; strcpy(leaf, path); }
    else {
        for (i = 0; i < k; i++) parent[i] = path[i];
        parent[k] = 0;
        if (!k) strcpy(parent, "/");                    /* "/NAME": the root */
        if (strlen(path + k + 1) > 12) fail();
        strcpy(leaf, path + k + 1);
    }
    if (!leaf[0] || strlen(leaf) > 12 || (leaf[0] == '.' && (!leaf[1] || (leaf[1] == '.' && !leaf[2])))) fail();
    if (fresolve(path, ent)) fail();                    /* exists */
    if (!fresolve(parent, ent) || !ent_isdir(ent)) fail();
    plba = ent_lba(ent); psecs = ent_len(ent) >> 9;
    slba = 0;                   /* the first free slot: its sector and offset */
    for (s = 0; s < psecs && !slba; s++) {
        if (!cf(plba + s, 0)) fail();
        for (o = 0; o < 512; o += 32) if (buf[o + 24] == 0 || buf[o + 24] == F_DEL) { slba = plba + s; sofs = o; break; }
    }
    if (!slba) fail();                                  /* the parent is full */
    if (!cf(0, 0) || buf[0] != 'P' || buf[1] != '8') fail();
    nl = buf[4] | (buf[5] << 8);                        /* the free pointer */
    if (nl + n < nl) fail();                            /* past LBA 65535 */
    for (i = 0; i < 512; i++) buf[i] = 0;               /* the extent: zeros, then "." and ".." in its first sector */
    for (i = 1; i < n; i++) if (!cf(nl + i, 1)) fail();
    entry(0, ".", nl, n); entry(32, "..", plba, psecs);
    if (!cf(nl, 1)) fail();
    if (!cf(0, 0)) fail();                              /* the free pointer raised over it */
    put16(4, nl + n);
    if (!cf(0, 1)) fail();
    if (!cf(slba, 0)) fail();                           /* and the entry, last */
    entry(sofs, leaf, nl, n);
    if (!cf(slba, 1)) fail();
}
