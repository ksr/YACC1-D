/* recurse.c - recursion is rejected at compile time (static frames): expected error in recurse.err */
int fact(int n) { if (n < 2) return 1; return n * fact(n - 1); }
void main() { fact(5); }
