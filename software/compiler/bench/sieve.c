/* primes below 200: common subset of p8cc and y1cc (no ++ += ?: switch #include) */
char flags[200];
void putnum(int n) { char buf[6]; int i; i = 0; if (n == 0) { putchar('0'); return; }
    while (n) { buf[i] = '0' + n % 10; n = n / 10; i = i + 1; } while (i) { i = i - 1; putchar(buf[i]); } }
void main() { int i; int j; int count;
    for (i = 0; i < 200; i = i + 1) flags[i] = 1;
    count = 0;
    for (i = 2; i < 200; i = i + 1) { if (flags[i]) { count = count + 1; putnum(i); putchar(' ');
        for (j = i + i; j < 200; j = j + i) flags[j] = 0; } }
    putchar('\n'); putnum(count); putchar('\n'); }
