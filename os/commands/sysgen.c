/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* sysgen.c - install a kernel in the boot sectors: sysgen FILE (2026-11-05)
     sysgen y1os      FILE (a program file with load and exec $1000, as `asm y1os.asm y1os` writes) to LBA 1.. on
                      raw sectors, each read back, then OSCNT (boot block byte 3): what p8xfs.py boot does on the Mac.
   The running OS is in memory and goes on; the new one starts at the next O. The kernel area is LBA 1..32, reserved in
   every volume, so no file moves. There is one copy of the kernel: a failure half way leaves a card that does not
   boot (write the kernel again from the Mac: docs/procedures/CF-CARD.md), so the checks all come first, and OSCNT
   changes last. Every failure ends with status 1 (a running script stops). */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
#define OS_LOAD 0x1000
#define OS_MAX 32

char buf[512], chk[512], path[64], ent[32];

void fail(char *s) { eputs(s); osexit(1); }

void lba(int n) { poke(CFLBA0, n); poke(CFLBA1, n >> 8); poke(CFLBA2, 0); }
int rd(int n, char *p) { lba(n); return !bios(CFREAD, p, 0); }
int wr(int n, char *p) { lba(n); return !bios(CFWRITE, p, 0); }

void main() {
    char *a; int h, n, s, i, k;
    a = argstr();
    while (*a == ' ') a++;
    if (!*a || *a == '-') fail("usage: sysgen file   install a kernel (load and exec $1000) in the boot sectors");
    argword(a, path, 63);
    if (!fresolve(path, ent) || !ent_isfile(ent)) fail("sysgen: not found");
    if (ent_load(ent) != OS_LOAD || ent_exec(ent) != OS_LOAD) fail("sysgen: not a kernel: load and exec must be $1000");
    if (!ent_len(ent) && !ent_lenx(ent)) fail("sysgen: an empty file");
    if (ent_lenx(ent) || ent_len(ent) > OS_MAX * 512) fail("sysgen: over 32 sectors");
    n = (ent_len(ent) + 511) >> 9;
    if (!rd(0, buf) || buf[0] != 'P' || buf[1] != '8') fail("sysgen: no P8XFS boot block");
    h = fopen(path);
    if (!h) fail("sysgen: cannot read the file");
    for (s = 1; s <= n; s++) {
        k = fread(h, buf);
        for (i = k; i < 512; i++) buf[i] = 0;
        if (!wr(s, buf) || !rd(s, chk)) fail("sysgen: CF error: the kernel on the card is damaged");
        for (i = 0; i < 512; i++) if (buf[i] != chk[i]) fail("sysgen: read back differs: the kernel on the card is damaged");
    }
    fclose(h);
    if (!rd(0, buf)) fail("sysgen: CF error on the boot block");
    buf[3] = n;
    if (!wr(0, buf)) fail("sysgen: CF error on the boot block");
    putstr("sysgen: "); putnum(n); puts(" sectors installed, for the next O");
}
