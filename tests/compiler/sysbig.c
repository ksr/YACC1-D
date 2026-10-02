/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* sysbig.c (2026-09-25) - a sys() number over 31 is a compile error. */
void main() { sys(32); }
