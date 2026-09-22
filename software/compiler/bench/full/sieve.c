/* sieve, written for y1cc: library putnum, ++/+=, break, char-sized flags and a char loop counter */
#include "y1lib.c"
#define N 200
char flags[N];
void main() {
    char i; int j, count;
    for (i = 0; i < N; i++) flags[i] = 1;
    count = 0;
    for (i = 2; i < N; i++) {
        if (!flags[i]) continue;
        count++; putnum(i); putchar(' ');
        for (j = i + i; j < N; j += i) flags[j] = 0;
    }
    putchar('\n'); putnum(count); putchar('\n');
}
