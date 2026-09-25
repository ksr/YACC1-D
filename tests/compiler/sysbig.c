/* sysbig.c (2026-09-25) - a sys() number over 31 is a compile error. */
void main() { sys(32); }
