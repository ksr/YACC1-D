/* syscall2.c (2026-09-25) - sys() numbers 22..31: y1cc takes them through SYSTAB2 ($4FC0, the 32-entry table Y1/OS
   keeps in its RAM; SYSTAB at $0F14 holds only 0..21, ARGBUF follows it). The program fills both tables as the OS
   does at boot and calls through each: a constant 0..21 still reads SYSTAB, 22..31 read SYSTAB2.
   no-oracle: fixed RAM addresses and the machine's JSRUR. */
#include "y1lib.c"
#define SYSARG0 0x0F06
#define SYSARG1 0x0F08
#define SYSRES  0x0F0C
#define SYSTAB  0x0F14
#define SYSTAB2 0x4FC0

void h_old() { pokew(SYSRES, 1000 + peekw(SYSARG0)); }
void h_22() { pokew(SYSRES, 2200 + peekw(SYSARG0) + peekw(SYSARG1)); }
void h_31() { pokew(SYSRES, 3100); }

void main() {
    pokew(SYSTAB + 2 * 5, funcaddr(h_old));
    pokew(SYSTAB2 + 2 * 5, 0);                      /* a constant 5 must not read SYSTAB2 */
    pokew(SYSTAB2 + 2 * 22, funcaddr(h_22));
    pokew(SYSTAB2 + 2 * 31, funcaddr(h_31));
    putnum(sys(5, 7)); putchar(10);                 /* 1007 */
    putnum(sys(22, 3, 4)); putchar(10);             /* 2207 */
    putnum(sys(31)); putchar(10);                   /* 3100 */
    putnum(sys(22, sys(5, 1), sys(31))); putchar(10);  /* 2200 + 1001 + 3100 = 6301 */
}
