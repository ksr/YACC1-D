/* recurse.c - recursion works since 2026-09-24, but a recursive function's locals live in static slots: passing
   the address of one into a call that can re-enter the function is rejected (expected error in recurse.err) */
int walk(int *depth, int n) { int here; here = n; if (n == 0) return *depth; return walk(&here, n - 1); }
void main() { int d; d = 0; walk(&d, 5); }
