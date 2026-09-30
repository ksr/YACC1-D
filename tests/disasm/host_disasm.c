/* host_disasm.c - /BIN/DISASM (os/commands/disasm.c) built for the Mac, for tests/disasm/run.py (2026-09-29).
   The same source as the Y1/OS program with the YACC1's integer types (int = unsigned short, char unsigned by
   -funsigned-char: the trick tests/asm/host_asm.c plays) and the y1cc builtins and syscalls it uses supplied by
   host_sys.c, so the corpus runs through the very code the machine runs.
   Build (run.py does it): cc -O1 -funsigned-char -fno-builtin -o build/disasm host_disasm.c host_sys.c
   This translation unit must not include <stdio.h>: lib_fs.c defines fopen(), fread() ... with Y1/OS meanings. */
int putchar(int c);
int puts(const char *s);
int sys(long n, ...);                     /* declared before int becomes unsigned short: real ints across the call */
int bios(int addr, int r7, int acc);
char *argstr(void);
int peek(int a);
#define int unsigned short
#define main disasm_main
#include "../../os/commands/disasm.c"
