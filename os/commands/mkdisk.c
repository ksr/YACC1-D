/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* mkdisk.c - make a new disk on the second drive: mkdisk [-f] [kernel] (2026-11-05)
     mkdisk           the kernel /lib/y1os and every file and directory of this disk go to drive 1
     mkdisk y1os      that kernel instead (a program file with load and exec $1000, as for sysgen)
     mkdisk -f        write over a drive that already holds a volume
   Drive 1 is the IDE slave beside the running disk: on the emulators the image of -C. The command drives it itself
   through P8/P9, device bit set in the drive/head register, between the OS's calls: the ROM selects drive 0 again
   before each of its own transfers, and the running disk is only read. The new volume is what p8xfs.py create, boot,
   mkdir and put make: the kernel at LBA 1 (OSCNT sectors, 32 at most), the root directory at LBA 33 (4 sectors), then
   files and directories from LBA 37 up, each directory keeping its size (the /src ones are big), each entry its
   load and exec address. Deleted files are not copied, so nothing needs packing; neither are the work files of a
   build (ccw.*, make.sh). LBA 0 is written last: until then the drive has no volume on it. To boot the new disk it
   must become drive 0 (the ROM's O boots no other): swap the images or the cards. A failure ends with status 1. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
#define OS_LOAD 0x1000
#define OS_MAX 32
#define ROOT_LBA 33
#define ROOT_SECS 4
#define DATA_LBA 37
#define TAB 20000               /* the entries of the directories being copied, 32 bytes each (a stack) */

char buf[512], ent[32], nm[13], kern[64], word[64];
char path[64];
char tab[TAB];
int ttop, fp, nfiles, ndirs;

void fail(char *s) { eputs(s); osexit(1); }

/* ---- drive 1, through P8/P9 ---- */
void reg(int r, int v) { outp(8, r); outp(9, v); }
int status() { outp(8, 7); return inp(9); }
void idle() {                   /* BSY gone */
    int n;
    for (n = 0; n < 60000; n++) if (!(status() & 0x80)) return;
    fail("mkdisk: drive 1 does not answer");
}
void drq() {                    /* BSY gone and DRQ up */
    int n, s;
    for (n = 0; n < 60000; n++) {
        s = status();
        if (s & 0x80) continue;
        if (s & 1) fail("mkdisk: drive 1 reports an error");
        if (s & 8) return;
    }
    fail("mkdisk: drive 1 does not answer");
}
void cmd(int lba, int c) {
    idle();
    reg(6, 0xF0); reg(3, lba); reg(4, lba >> 8); reg(5, 0); reg(2, 1); reg(7, c);
    drq();
    outp(8, 0);
}
void wsec(int lba) {            /* buf -> a sector of drive 1 */
    int i;
    cmd(lba, 0x30);
    for (i = 0; i < 512; i++) outp(9, buf[i]);
    idle();
}
void rsec(int lba) {            /* a sector of drive 1 -> buf */
    int i;
    cmd(lba, 0x20);
    for (i = 0; i < 512; i++) buf[i] = inp(9);
}
void zero() { memset(buf, 0, 512); }

/* ---- the new volume ---- */
void put16(int o, int v) { buf[o] = v; buf[o + 1] = v >> 8; }
void dotent(int o, char *n, int lba, int secs) {    /* "." or ".." at buf[o] */
    int i;
    for (i = 0; i < 12; i++) { buf[o + i] = *n ? *n : ' '; if (*n) n++; }
    put16(o + 12, lba); put16(o + 16, secs << 9); buf[o + 24] = 2;
}
void newdir(int lba, int secs, int plba, int psecs) {
    int i;
    zero();
    for (i = 1; i < secs; i++) wsec(lba + i);
    dotent(0, ".", lba, secs); dotent(32, "..", plba, psecs);
    wsec(lba);
}
void addent(int dlba, int k, char *e, int lba) {    /* the entry e, its start now lba, as slot k of a directory */
    int s, o, i;
    s = dlba + (k >> 4); o = (k & 15) << 5;
    rsec(s);
    for (i = 0; i < 32; i++) buf[o + i] = e[i];
    put16(o + 12, lba); put16(o + 14, 0);
    wsec(s);
}
int workfile(char *n) {         /* a build's leftovers */
    return strcmp(n, "make.sh") == 0 || (n[0] == 'c' && n[1] == 'c' && n[2] == 'w' && n[3] == '.');
}
void copyfile(char *e) {        /* path[] from the running disk, at fp */
    int h, k, i;
    h = fopen(path);
    if (!h) fail("mkdisk: cannot read a file");
    while ((k = fread(h, buf))) {
        for (i = k; i < 512; i++) buf[i] = 0;
        wsec(fp);
        fp++;
        if (!fp) fail("mkdisk: past LBA 65535");
    }
    fclose(h);
    nfiles++;
}

void copydir(int dlba, int dsecs) {  /* the directory path[] -> the new extent at dlba. The entries are read first:
                                        the OS has four handles and the tree is deeper than that */
    int h, n, i, k, save, lba, secs, plen; char *e;
    save = ttop; n = 0;
    h = opendir(path[0] ? path : "/");
    if (!h) fail("mkdisk: cannot read a directory");
    while (readdir(h, ent)) {
        ent_name(ent, nm);
        if (nm[0] == '.' || workfile(nm)) continue;
        if (ttop + 32 > TAB) fail("mkdisk: too many entries");
        for (i = 0; i < 32; i++) tab[ttop + i] = ent[i];
        ttop += 32; n++;
    }
    fclose(h);
    plen = strlen(path);
    k = 2;
    for (i = 0; i < n; i++) {
        e = tab + save + i * 32;
        ent_name(e, nm);
        if (plen + strlen(nm) + 2 > 63) fail("mkdisk: a path over 62 characters");
        path[plen] = '/'; strcpy(path + plen + 1, nm);
        lba = fp;
        if (ent_isdir(e)) {
            secs = ent_len(e) >> 9;
            if (fp + secs < fp) fail("mkdisk: past LBA 65535");
            fp += secs;
            newdir(lba, secs, dlba, dsecs);
            addent(dlba, k, e, lba);
            ndirs++;
            puts(path);
            copydir(lba, secs);
        } else {
            copyfile(e);
            addent(dlba, k, e, lba);
        }
        k++;
        path[plen] = 0;
    }
    ttop = save;
}

void main() {
    char *a; int force, h, n, s, k, i;
    a = argstr();
    force = 0;
    strcpy(kern, "/lib/y1os");
    while (*a) {
        a = argword(a, word, 63);
        if (!word[0]) break;
        if (word[0] == '-' && word[1] == 'f') force = 1;
        else if (word[0] == '-') fail("usage: mkdisk [-f] [kernel]   a new disk on drive 1: the kernel, then this disk's files");
        else strcpy(kern, word);
    }
    if (!fresolve(kern, ent) || !ent_isfile(ent)) fail("mkdisk: no kernel");
    if (ent_load(ent) != OS_LOAD || ent_exec(ent) != OS_LOAD) fail("mkdisk: not a kernel: load and exec must be $1000");
    if (ent_lenx(ent) || !ent_len(ent) || ent_len(ent) > OS_MAX * 512) fail("mkdisk: not a kernel: 1 to 32 sectors");
    n = (ent_len(ent) + 511) >> 9;
    reg(6, 0xF0);
    if (status() == 255) fail("mkdisk: no drive 1");
    idle();
    reg(6, 0xF0); reg(1, 1); reg(7, 0xEF);              /* SET FEATURES: 8-bit transfers, as the ROM for drive 0 */
    idle();
    rsec(0);
    if (buf[0] == 'P' && buf[1] == '8' && !force) fail("mkdisk: drive 1 holds a volume (-f writes over it)");
    zero();
    wsec(0);                    /* no volume until the end */
    h = fopen(kern);
    if (!h) fail("mkdisk: cannot read the kernel");
    for (s = 1; s <= n; s++) {
        k = fread(h, buf);
        for (i = k; i < 512; i++) buf[i] = 0;
        wsec(s);
    }
    fclose(h);
    newdir(ROOT_LBA, ROOT_SECS, ROOT_LBA, ROOT_SECS);
    fp = DATA_LBA;
    path[0] = 0;
    copydir(ROOT_LBA, ROOT_SECS);
    zero();                     /* the boot block, last: 'P8', version 2, OSCNT, the free pointer */
    buf[0] = 'P'; buf[1] = '8'; buf[2] = 2; buf[3] = n;
    put16(4, fp);
    wsec(0);
    reg(6, 0xE0);
    putstr("mkdisk: "); putnum(n); putstr(" sectors of kernel, "); putnum(nfiles); putstr(" files, ");
    putnum(ndirs); putstr(" directories, free pointer "); putnum(fp); putchar(10);
}
