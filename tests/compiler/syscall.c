/* syscall.c - the sys() and funcaddr() builtins (2026-09-23): what Y1/OS does at boot (fill SYSTAB with
   funcaddr(handler)) and what a /BIN command does (sys(n, a, b, c) -> SYSRES), in one stand-alone program.
   no-oracle: SYSTAB/SYSARG/SYSRES are fixed RAM addresses ($0F14 / $0F06.. / $0F0C) and JSRUR is the machine's. */
#include "y1lib.c"
#define SYSARG0 0x0F06
#define SYSARG1 0x0F08
#define SYSARG2 0x0F0A
#define SYSRES  0x0F0C
#define SYSTAB  0x0F14
#define S_ADD 0
#define S_SUB3 1
#define S_STRLEN 2
#define S_CONST 21

int calls;
void h_add() { calls++; pokew(SYSRES, peekw(SYSARG0) + peekw(SYSARG1)); }          /* sys(0, a, b) = a + b */
void h_sub3() { calls++; pokew(SYSRES, peekw(SYSARG0) - peekw(SYSARG1) - peekw(SYSARG2)); }
void h_strlen() { calls++; pokew(SYSRES, strlen(peekw(SYSARG0))); }
void h_const() { calls++; pokew(SYSRES, 4660); }                                    /* no arguments: $1234 */
int never_called_directly() { return 7; }

int twice(int x) { return sys(S_ADD, x, x); }                                       /* a function that uses sys() */

void main() {
    int n, r;
    pokew(SYSTAB + 2 * S_ADD, funcaddr(h_add));
    pokew(SYSTAB + 2 * S_SUB3, funcaddr(h_sub3));
    pokew(SYSTAB + 2 * S_STRLEN, funcaddr(h_strlen));
    pokew(SYSTAB + 2 * S_CONST, funcaddr(h_const));
    putnum(sys(S_ADD, 40, 2)); putchar(10);                     /* 42 */
    putnum(sys(S_SUB3, 1000, 300, 58)); putchar(10);            /* 642 */
    putnum(sys(S_STRLEN, "hello")); putchar(10);                /* 5 */
    putnum(sys(S_CONST)); putchar(10);                          /* 4660 */
    n = 1; putnum(sys(n, 10, 3, 2)); putchar(10);               /* computed number: 5 */
    n = 21; putnum(sys(n)); putchar(10);                        /* 4660 (the last slot) */
    /* an argument that itself calls sys(): the earlier arguments must survive (parked on the stack) */
    putnum(sys(S_ADD, 100, sys(S_ADD, 20, 3))); putchar(10);    /* 123 */
    putnum(sys(S_SUB3, 500, twice(7), sys(S_STRLEN, "abc"))); putchar(10);   /* 500-14-3 = 483 */
    r = sys(S_ADD, sys(S_ADD, 1, 2), sys(S_ADD, 3, 4)); putnum(r); putchar(10);   /* 10 */
    putnum(funcaddr(never_called_directly) != 0); putchar(10);  /* 1: the function is in the image */
    putnum(calls); putchar(10);                                 /* 14 handler calls */
}
