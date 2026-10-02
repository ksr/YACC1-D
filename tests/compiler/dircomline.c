/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* dircomline.c - the line numbers after a #define whose comment goes on over two more lines (2026-09-25,
   dircomment.c): the error below is on line 11 (expected error in dircomline.err; 6 before the four-line
   authorship header of 2026-10-02) */
#define A 5     /* a comment
                   over
                   three lines */
void main() { putchar(A) }
