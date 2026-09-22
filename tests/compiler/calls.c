/* calls.c - parameters, nested calls, argument-evaluation hazards, char params/returns, globals across calls */
#include "y1lib.c"

int counter;

int add3(int a, int b, int c) { return a + b + c; }
int twice(int v) { return v * 2; }
int f(int a, int b) { return a * 10 + b; }
int g() { return f(1, 2); }                          /* g calls f: f(x, g()) must not lose x */
char nextc(char c) { return c + 1; }
char lower(char c) { if (c >= 'A' && c <= 'Z') return c + 32; return c; }
int bump() { counter++; return counter; }
void nothing() { }
int wide(char c) { return c * 300; }
void order(int a, int b, int c, int d) { putnum(a); putnum(b); putnum(c); putnum(d); putchar('\n'); }

void main() {
    int x;
    char ch;
    putnum(add3(1, 2, 3)); putchar('\n');                        /* 6 */
    putnum(add3(twice(1), twice(twice(2)), twice(twice(twice(3))))); putchar('\n');   /* 2+8+24 = 34 */
    putnum(f(7, g())); putchar('\n');                             /* 7*10 + 12 = 82 */
    putnum(f(g(), g())); putchar('\n');                           /* 12*10 + 12 = 132 */
    putnum(add3(bump(), bump(), bump())); putchar('\n');          /* 1+2+3 = 6 */
    putnum(counter); putchar('\n');                               /* 3 */
    ch = nextc('a'); putchar(ch); putchar(nextc(ch)); putchar(lower('Q')); putchar(lower('q')); putchar('\n');   /* bcqq */
    ch = 255; ch = nextc(ch); putnum(ch); putchar('\n');          /* 0 (char wraps) */
    putnum(wide(200)); putchar('\n');                             /* 60000 */
    x = wide(255) + nextc(1); putnum(x); putchar('\n');           /* 76500 mod 65536 = 10964, + 2 = 10966 */
    order(1, 2, 3, 4);
    order(bump(), bump(), bump(), bump());                        /* 4 5 6 7 */
    nothing();
    x = 5;
    x = add3(x, x + 1, x * 2); putnum(x); putchar('\n');          /* 21 */
    putnum(twice(twice(twice(twice(1))))); putchar('\n');         /* 16 */
}
