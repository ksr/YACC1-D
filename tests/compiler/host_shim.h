/* host_shim.h - lets the host C compiler act as an ORACLE for the y1cc test programs (run.py --oracle):
   int becomes 16-bit unsigned, char is unsigned (-funsigned-char), the console builtins map to stdio.
   Programs that touch the machine (peek/poke/inp/outp/bios) are excluded from the oracle (they say so). */
#include <stdio.h>
#include <stdlib.h>
static int y1_getc(void) { int c = fgetc(stdin); return c < 0 ? 0 : c; }
static void y1_puts(const char *s) { fputs(s, stdout); fputc('\n', stdout); }
#define int unsigned short
#define getchar() y1_getc()
#define puts(s) y1_puts(s)
#define putchar(c) fputc((unsigned char)(c), stdout)
#define halt() exit(0)
