/* host_asm.c - /BIN/ASM (os/commands/asm.c) built for the Mac, for tests/asm/run.py (2026-09-25).
   The same source as the Y1/OS program, with the YACC1's integer types (int = unsigned short here, char unsigned by
   -funsigned-char: the trick software/compiler/c/host16.c plays) and the y1cc builtins it uses - sys(), bios(),
   argstr(), peekw(), pokew(), putchar(), puts() - supplied by host_sys.c, which emulates the Y1/OS file syscalls
   over the Mac's files. So the corpus runs through the very code the machine runs, file API calls included.
   Build (run.py does it): cc -O1 -funsigned-char -fno-builtin -o build/asm host_asm.c host_sys.c
   This translation unit must not include <stdio.h>: lib_fs.c defines fopen(), fread() ... with Y1/OS meanings, and
   host_sys.c uses only POSIX calls (open, read, write), never those names. */
int putchar(int c);
int puts(const char *s);
int sys(long n, ...);                     /* declared before int becomes unsigned short: real ints across the call */
int bios(int addr, int r7, int acc);
char *argstr(void);
int peekw(char *p);
void pokew(char *p, int v);
#define int unsigned short
#define main asm_main
#include "../../os/commands/asm.c"
