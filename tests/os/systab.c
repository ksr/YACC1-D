/* systab.c - tests/os/systab.session's program (2026-09-25): the OS fills SYSTAB2 ($4FC0, 32 entries) and copies its
   first 22 to SYSTAB ($0F14, what every program compiled before reads); a constant sys() number 0..21 goes through
   SYSTAB, 22..31 through SYSTAB2 (y1cc). Prints how many of 0..21 agree (and are set), which of 22..31 are set,
   and STDIO called through SYSTAB2's entry 21 with call() instead of sys(). run.py puts it on the disk as /SYSTAB. */
#include "../../os/lib_fs.c"
#include "y1lib.c"

void main() {
    int i, same;
    same = 0;
    for (i = 0; i <= SYS_OLD; i++) if (peekw(SYSTAB + 2 * i) && peekw(SYSTAB + 2 * i) == peekw(SYSTAB2 + 2 * i)) same++;
    putstr("0..21 in both tables: "); putnum(same); putchar(10);
    putstr("22..31 set:");
    for (i = SYS_OLD + 1; i < 32; i++) if (peekw(SYSTAB2 + 2 * i)) { putchar(' '); putnum(i); }
    putchar(10);
    call(peekw(SYSTAB2 + 2 * SYS_STDIO));
    putstr("STDIO through SYSTAB2: "); putnum(peekw(SYSRES)); putchar(10);
}
