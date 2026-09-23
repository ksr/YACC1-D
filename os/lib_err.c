/* lib_err.c - eputs(s): an error message and a line feed on the RAW console; eput2(s, t): s then t, one message
   (Y1/OS, 2026-09-23).
   Since the shell has redirection and pipes (2026-09-23) putchar is the CONOUT syscall, which follows stdout into a
   > file or a pipe; eputs() writes through the ROM's CHAROUT vector instead, so a "not found" is seen on the screen
   and never lands in an output file or the next command's input, as the P8X eputs() does (stderr, in effect).
   Ported from P8X os/commands/lib_err.c 2026-09-23, changes: the BIOS call is bios(CHAROUT, 0, c), one byte. */
#include "lib_abi.c"
void eputc(int c) { bios(CHAROUT, 0, c); }
void eputs(char *s) { while (*s) eputc(*s++); eputc(10); }
void eput2(char *s, char *t) { while (*s) eputc(*s++); eputs(t); }   /* "cmd: what: " + a name, one message */
