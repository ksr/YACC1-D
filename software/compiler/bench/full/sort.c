#include "y1lib.c"
int a[32];
void bubble(int *v, char n) {
    char i, j; int t;
    for (i = 0; i < n - 1; i++)
        for (j = 0; j < n - 1 - i; j++)
            if (v[j] > v[j + 1]) { t = v[j]; v[j] = v[j + 1]; v[j + 1] = t; }
}
void main() {
    char i; int seed;
    seed = 12345;
    for (i = 0; i < 32; i++) { seed = seed * 75 + 74; seed %= 65521; a[i] = seed & 1023; }
    bubble(a, 32);
    for (i = 0; i < 32; i++) { putnum(a[i]); putchar(' '); }
    putchar('\n');
}
