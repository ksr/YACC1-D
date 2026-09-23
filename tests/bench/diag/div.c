/* div.c - bench diagnostic (2026-09-23): arith.c hung on the machine in putnum(64836) (b-a), while putnum(700)
   worked. Prints every step in hex only (puthex needs no division), one line at a time, so a hang shows where. */
#include "y1lib.c"

void pr(char *s, int v) { putstr(s); puthex(v); putchar(10); }

void main() {
    int x, q, r;
    pr("A 64836=", 64836);
    x = 64836;
    q = x / 10; pr("B 64836/10=", q);
    r = x % 10; pr("C 64836%10=", r);
    x = 32768; pr("D 32768/10=", x / 10);
    x = 32767; pr("E 32767/10=", x / 10);
    x = 40000; pr("F 40000/10=", x / 10);
    x = 700;   pr("G 700/10=", x / 10);
    x = 65535; pr("H 65535/7=", x / 7);
    x = 32768; pr("I 32768>>1=", x >> 1);
    x = 16384; pr("J 16384<<1=", x << 1);
    x = 64836; pr("K 64836>>3=", x >> 3);
    x = 300; q = 1000; pr("L 300-1000=", x - q);
    x = 50000; q = 20000; pr("M 50000+20000=", x + q);
    x = 300; q = 7; pr("N 300*7=", x * q);
    x = 40000; q = 3; pr("O 40000*3=", x * q);
    putstr("END"); putchar(10);
}
