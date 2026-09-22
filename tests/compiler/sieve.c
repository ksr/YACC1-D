/* sieve.c - primes below 200 (the classic), plus a little string work */
#include "y1lib.c"

#define N 200
char flags[N];

void main() {
    int i, j, count;
    char line[40];
    for (i = 0; i < N; i++) flags[i] = 1;
    count = 0;
    for (i = 2; i < N; i++) {
        if (flags[i]) {
            count++;
            putnum(i); putchar(' ');
            for (j = i + i; j < N; j += i) flags[j] = 0;
        }
    }
    putchar('\n');
    putstr("count="); putnum(count); putchar('\n');
    strcpy(line, "primes: ");
    putnum(strlen(line)); putchar('\n');
    if (strcmp(line, "primes: ") == 0) puts("strcmp equal");
    if (strcmp(line, "primes!") == 1) puts("strcmp greater");
    if (strcmp("abc", "abd") == 65535) puts("strcmp less");
}
