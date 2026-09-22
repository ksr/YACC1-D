/* bigconst.c - an integer literal over 65535 is a compile error, not a silent truncation (int is 16-bit) */
void main() { int x; x = 65537; }
