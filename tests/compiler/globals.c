/* globals.c - initialised globals of every shape, pointers to them, #define, static/const/unsigned spellings */
#include "y1lib.c"

#define LIMIT 5
#define CH 'Q'

int gi = 1234;
char gcv = 'z';
unsigned int gu = 0xFFFF;
const int gk = 77;
static int gs = 9;
int *gp = &gi;
char *gstr = "text";
int arr[LIMIT] = {1, 2, 3};             /* tail zero-filled */
char cs[4] = "ab";                      /* padded */
int tab[] = {0x100, 0x200, 0x300};
char *strs[] = {"x", "yy", "zzz"};
int neg = -1;
int expr = LIMIT * 2 + 1;

void decls();

void main() {
    int *p;
    int i;
    putnum(gi); putchar(' '); putchar(gcv); putchar(' '); putnum(gu); putchar(' '); putnum(gk); putchar(' '); putnum(gs); putchar('\n');
    *gp = 4321; putnum(gi); putchar('\n');
    puts(gstr);
    for (i = 0; i < LIMIT; i++) { putnum(arr[i]); putchar(' '); }
    putchar('\n');
    puts(cs); putnum(cs[2]); putnum(cs[3]); putchar('\n');
    for (i = 0; i < 3; i++) { puthex(tab[i]); putchar(' '); puts(strs[i]); }
    putnum(neg); putchar(' '); putnum(expr); putchar(' '); putchar(CH); putchar('\n');
    p = tab; p++; putnum(*p); putchar(' '); p += 1; putnum(*p); putchar(' '); putnum(p - tab); putchar('\n');   /* 512 768 2 */
    p = &arr[4]; *p = 99; putnum(arr[4]); putchar('\n');
    gu++; putnum(gu); putchar(10);
    decls();
}
/* 2026-09-22: several declarators with different pointer depths (int *p, q; char *a, b, *c) */
int *dp, dq, *dr;
void decls() { char *a, b, *c; int *ip, iq; a = "xy"; b = 'B'; c = a + 1; ip = &iq; iq = 7; dp = &dq; dq = 3; dr = dp;
    putchar(*a); putchar(b); putchar(*c); putnum(*ip); putnum(*dr); putchar('\n'); }
