/* arrays.c - int and char arrays, global tables, pointer walks, index expressions, string tables */
#include "y1lib.c"

int table[] = {10, 20, 30, 40, 50};
char letters[] = "abcdef";
char *names[] = {"zero", "one", "two", "three"};
int grid[12];                       /* 3 rows of 4 */
char bytes[300];
int words[100];

int sum(int *p, int n) { int s; s = 0; while (n--) s += *p++; return s; }

void main() {
    int i, j;
    char *s;
    putnum(sum(table, 5)); putchar('\n');              /* 150 */
    table[2] = 300; table[4] += table[0];
    putnum(sum(table, 5)); putchar('\n');              /* 10+20+300+40+60 = 430 */
    for (i = 0; i < 5; i++) { putnum(table[i]); putchar(' '); }
    putchar('\n');
    puts(letters);
    for (i = 0; i < 6; i++) letters[i] = letters[i] - 32;   /* upper case */
    puts(letters);
    letters[0] = letters[5]; letters[5] = 'x';
    puts(letters);
    for (i = 0; i < 4; i++) puts(names[i]);
    s = names[3]; putnum(strlen(s)); putchar('\n');
    for (i = 0; i < 3; i++) for (j = 0; j < 4; j++) grid[i * 4 + j] = i * 10 + j;
    for (i = 0; i < 12; i++) { putnum(grid[i]); putchar(','); }
    putchar('\n');
    putnum(grid[2 * 4 + 3]); putchar('\n');             /* 23 */
    for (i = 0; i < 300; i++) bytes[i] = i;
    putnum(bytes[299]); putchar(' '); putnum(bytes[256]); putchar(' '); putnum(bytes[255]); putchar('\n');   /* 43 0 255 */
    for (i = 0; i < 100; i++) words[i] = i * i;
    putnum(words[99]); putchar(' '); putnum(words[50]); putchar('\n');   /* 9801 2500 */
    i = 0;
    for (j = 0; j < 100; j++) i += words[j];
    putnum(i); putchar('\n');                            /* 328350 mod 65536 = 742 */
    s = letters + 2;
    puts(s);
    s = s - 1;
    putchar(*s); putchar(s[1]); putchar(*(s + 2)); putchar('\n');
    memset(bytes, 'z', 5); bytes[5] = 0; puts(bytes);
}
