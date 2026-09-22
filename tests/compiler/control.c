/* control.c - conditions and loops: every relation, both byte and word operands, && || !, break/continue */
#include "y1lib.c"

int g;
char c;

void rel(char *name, int a, int b) {
    putstr(name); putchar(':');
    if (a < b) putchar('<'); else putchar('.');
    if (a > b) putchar('>'); else putchar('.');
    if (a <= b) putchar('l'); else putchar('.');
    if (a >= b) putchar('g'); else putchar('.');
    if (a == b) putchar('='); else putchar('.');
    if (a != b) putchar('#'); else putchar('.');
    if (!(a < b)) putchar('N'); else putchar('.');
    putchar('\n');
}

void main() {
    int i, n;
    rel("1,2", 1, 2);
    rel("2,1", 2, 1);
    rel("5,5", 5, 5);
    rel("255,256", 255, 256);
    rel("256,255", 256, 255);
    rel("0x1234,0x1234", 0x1234, 0x1234);
    rel("0x1200,0x12FF", 0x1200, 0x12FF);
    rel("0x12FF,0x1200", 0x12FF, 0x1200);
    rel("65535,0", 65535, 0);
    rel("0,65535", 0, 65535);
    rel("300,20", 300, 20);
    /* constants on the right, on the left, and byte compares */
    g = 100;
    if (g < 200) puts("g<200");
    if (g > 50) puts("g>50");
    if (g == 100) puts("g==100");
    if (g != 100) puts("BAD"); else puts("g!=100 false");
    if (100 == g) puts("100==g");
    if (99 < g) puts("99<g");
    if (g <= 100 && g >= 100) puts("g<=100&&g>=100");
    if (g < 100 || g > 99) puts("g<100||g>99");
    if (g < 100 || g > 100) puts("BAD"); else puts("neither");
    if (!g) puts("BAD"); else puts("g true");
    if (g && c == 0) puts("g&&c==0");
    c = 200;
    if (c > 100) puts("c>100");
    if (c < 250) puts("c<250");
    if (c == 200) puts("c==200");
    if (c != 200) puts("BAD"); else puts("c!=200 false");
    if (c) puts("c true");
    if (c > g) puts("c>g");
    if (c + 100 > g + 100) puts("c+100>g+100");
    if (g + 200 > c) puts("g+200>c");
    if (c * 2 == 400) puts("c*2==400");
    if ((g & 4) == 4) puts("g&4");
    if (g & 3) puts("BAD"); else puts("g&3 zero");
    if (g - 100) puts("BAD"); else puts("g-100 zero");
    if (g - 99) puts("g-99 nonzero");
    /* loops */
    n = 0;
    for (i = 0; i < 10; i++) { if (i == 3) continue; if (i == 8) break; n += i; }
    putnum(n); putchar('\n');            /* 0+1+2+4+5+6+7 = 25 */
    i = 0; n = 0;
    while (1) { i++; if (i > 100) break; if (i % 2) continue; n += i; }
    putnum(n); putchar('\n');            /* even numbers 2..100 = 2550 */
    for (i = 10; i; i--) putnum(i);
    putchar('\n');
    n = 0;
    for (i = 0; i < 300; i += 50) n++;
    putnum(n); putchar('\n');            /* 6 */
    n = 0;
    for (i = 65530; i != 4; i++) n++;   /* wraps through 0 */
    putnum(n); putchar('\n');            /* 10 */
    i = 5;
    while (i) { n = n * 2 + i; i--; }
    putnum(n); putchar('\n');
    if (i == 0) if (n > 100) puts("nested if"); else puts("BAD");
    for (i = 0; i < 3; i++) for (n = 0; n < 2; n++) { putnum(i); putnum(n); putchar(' '); }
    putchar('\n');
}
