/* rmain.c - main cannot be recursive (it clears the BSS on entry and the boot stub/monitor call it once): expected
   error in rmain.err */
int helper(int n);
void main() { helper(3); }
int helper(int n) { if (n) main(); return n; }
