#include "y1lib.c"
int fibs[25];
int gcd(int a, int b) { int t; while (b) { t = a % b; a = b; b = t; } return a; }
int digitsum(int n) { int s; s = 0; while (n) { s += n % 10; n /= 10; } return s; }
void main() {
    char i;
    fibs[0] = 0; fibs[1] = 1;
    for (i = 2; i < 25; i++) fibs[i] = fibs[i - 1] + fibs[i - 2];
    for (i = 0; i < 25; i++) { putnum(fibs[i]); putchar(' '); }
    putchar('\n'); putnum(gcd(1071, 462)); putchar(' '); putnum(gcd(65535, 255)); putchar('\n');
    for (i = 1; i <= 12; i++) { putnum(i * i); putchar(':'); putnum(digitsum(i * i)); putchar(' '); }
    putchar('\n');
}
