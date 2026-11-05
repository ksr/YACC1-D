/*
 * Author: Claude (Anthropic), 2026 - ported from Ken Rother's P8X project
 */

/* help.c - the Y1/OS command reference: the shell's built-ins and the /bin programs, one line each.
     help       the list (man NAME for the page of any of them)
   Ported from P8X os/commands/help.c 2026-09-23, changes: the text is rewritten for Y1/OS (no /d1, graphics,
   kermit, make, sh; the built-ins are Y1/OS's; redirection and pipes since the same evening: man shell; pack added 2026-09-23;
   asm and cc 2026-09-25, video 2026-09-25, kermit 2026-09-26, asmc 2026-09-26, disasm 2026-09-29, sh and make
   2026-11-03, mkdir -s the same day). 
   The text is os/help.txt, /lib/help.txt on the disk, since 2026-11-05: as string literals it was over pass 1's string
   pool, so the native compiler could not build help. Keep it in step with os/README.md. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"

void main() {
    int h, c;
    h = fopen("/lib/help.txt");
    if (!h) { eputs("help: no /lib/help.txt"); osexit(1); }
    while ((c = fgetc(h)) != 65535) putchar(c);
    fclose(h);
}
