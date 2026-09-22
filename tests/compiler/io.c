/* io.c - the machine builtins: peek/poke/peekw/pokew on RAM, outp to the console port, sizeof.  no-oracle */
#include "y1lib.c"

int w;
char b;

void main() {
    int a;
    a = 0x7000;
    poke(a, 0x41); poke(a + 1, 0x42); poke(a + 2, 0);
    putnum(peek(a)); putchar(' '); putnum(peek(0x7001)); putchar('\n');     /* 65 66 */
    puts(a);                                                                  /* AB (a char* by value) */
    pokew(0x7010, 0x1234);
    puthex(peekw(0x7010)); putchar(' '); puthex2(peek(0x7010)); puthex2(peek(0x7011)); putchar('\n');  /* 1234 1234 */
    pokew(0x7010, peekw(0x7010) + 1); puthex(peekw(0x7010)); putchar('\n');   /* 1235 */
    w = 0xBEEF; a = &w; puthex(peekw(a)); putchar('\n');                      /* BEEF: words are big-endian */
    b = 7; a = &b; putnum(peek(a)); putchar('\n');                            /* 7 */
    outp(2, 'O'); outp(2, 'K'); b = '!'; outp(2, b); outp(2, b + 1); outp(2, 10);   /* OK!" */
    putnum(sizeof(int)); putnum(sizeof(char)); putnum(sizeof(w)); putnum(sizeof(b)); putchar('\n');   /* 2121 */
    puthex(0xFFFF - 0x0FFF); putchar('\n');                                   /* F000 */
}
