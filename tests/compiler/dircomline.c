/* dircomline.c - the line numbers after a #define whose comment goes on over two more lines (2026-09-25,
   dircomment.c): the error below is on line 6 (expected error in dircomline.err) */
#define A 5     /* a comment
                   over
                   three lines */
void main() { putchar(A) }
