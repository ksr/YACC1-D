int fibs[25];
void putnum(int n) { char buf[6]; int i; i = 0; if (n == 0) { putchar('0'); return; }
    while (n) { buf[i] = '0' + n % 10; n = n / 10; i = i + 1; } while (i) { i = i - 1; putchar(buf[i]); } }
int gcd(int a, int b) { int t; while (b) { t = a % b; a = b; b = t; } return a; }
int digitsum(int n) { int s; s = 0; while (n) { s = s + n % 10; n = n / 10; } return s; }
void main() { int i;
    fibs[0] = 0; fibs[1] = 1;
    for (i = 2; i < 25; i = i + 1) fibs[i] = fibs[i - 1] + fibs[i - 2];
    for (i = 0; i < 25; i = i + 1) { putnum(fibs[i]); putchar(' '); }
    putchar('\n'); putnum(gcd(1071, 462)); putchar(' '); putnum(gcd(65535, 255)); putchar('\n');
    for (i = 1; i <= 12; i = i + 1) { putnum(i * i); putchar(':'); putnum(digitsum(i * i)); putchar(' '); }
    putchar('\n'); }
