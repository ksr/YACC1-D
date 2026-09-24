/* rmutual.c - mutual recursion (2026-09-24): even/odd, a three-function cycle, a cycle entered from two places,
   and a non-recursive helper called from inside a cycle (its frame needs no saving). */
#include "y1lib.c"

int is_odd(int n);
int is_even(int n) { if (n == 0) return 1; return is_odd(n - 1); }
int is_odd(int n) { if (n == 0) return 0; return is_even(n - 1); }

/* a -> b -> c -> a, each with its own local that must survive the round trip */
int ca(int n);
int cc(int n) { int k; k = n * 3; if (n == 0) return 1; return ca(n - 1) + k - k; }
int cb(int n) { int k; k = n + 100; if (n == 0) return 2; return cc(n - 1) + (k - 100 - n); }
int ca(int n) { int k; k = n; if (n == 0) return 3; return cb(n - 1) * 1 + k - n; }

int twice(int x) { return x + x; }          /* not recursive: called from inside the cycle */

/* Hofstadter female/male sequences: F(n) = n - M(F(n-1)), M(n) = n - F(M(n-1)) */
int hm(int n);
int hf(int n) { if (n == 0) return 1; return n - hm(hf(n - 1)); }
int hm(int n) { if (n == 0) return 0; return n - hf(hm(n - 1)); }

int step(int n);
int walk(int n) {                           /* recursion through a helper that is itself in the cycle */
    int t;
    if (n == 0) return 0;
    t = twice(n);
    return t + step(n);
}
int step(int n) { return walk(n - 1); }

void main() {
    int i;
    putstr("even:"); for (i = 0; i < 12; i++) { putchar(' '); putnum(is_even(i)); } putchar(10);
    putstr("odd 49:"); putnum(is_odd(49)); putstr(" even 50:"); putnum(is_even(50)); putchar(10);
    putstr("cycle:"); for (i = 0; i < 10; i++) { putchar(' '); putnum(ca(i)); } putchar(10);
    putstr("F:"); for (i = 0; i < 16; i++) { putchar(' '); putnum(hf(i)); } putchar(10);
    putstr("M:"); for (i = 0; i < 16; i++) { putchar(' '); putnum(hm(i)); } putchar(10);
    putstr("walk(20)="); putnum(walk(20)); putchar(10);
}
