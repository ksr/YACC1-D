int a[32];
void putnum(int n) { char buf[6]; int i; i = 0; if (n == 0) { putchar('0'); return; }
    while (n) { buf[i] = '0' + n % 10; n = n / 10; i = i + 1; } while (i) { i = i - 1; putchar(buf[i]); } }
void bubble(int *v, int n) { int i; int j; int t; for (i = 0; i < n - 1; i = i + 1) for (j = 0; j < n - 1 - i; j = j + 1)
    if (v[j] > v[j + 1]) { t = v[j]; v[j] = v[j + 1]; v[j + 1] = t; } }
void main() { int i; int seed; seed = 12345;
    for (i = 0; i < 32; i = i + 1) { seed = seed * 75 + 74; seed = seed % 65521; a[i] = seed & 1023; }
    bubble(a, 32);
    for (i = 0; i < 32; i = i + 1) { putnum(a[i]); putchar(' '); } putchar('\n'); }
