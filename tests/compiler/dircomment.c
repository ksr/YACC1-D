/* dircomment.c - comments on preprocessor lines (2026-09-25): a block comment that starts on a #define or #include
   line and goes on over the next lines is one space, and the directive ends at the newline after it (until then the
   next lines were lexed as code: os/lib_abi.c's '$' was a "bad character"); a // comment ends a directive; inside
   quotes neither is a comment. The line numbers after such a directive stay right (dircomline.c). */
#include "y1lib.c"  /* an #include's comment
                       over two lines: $ @ ` */
#define A 5     /* the value, then a comment over two lines,
                   with what the lexer refuses in code: $ @ ` */
#define B /* a comment before the value */ 7
#define C 9     // a line comment /* that starts no block comment
#define D '/'   /* a quoted slash, and a comment over
                   two lines */
#define E '"'   /* a quoted double quote, then a comment
                   over two lines "with a quote */
#define F 11

void main() {
    putnum(A); putchar(' '); putnum(B); putchar(' '); putnum(C); putchar(' ');
    putchar(D); putchar(' '); putchar(E); putchar(' '); putnum(F); putchar('\n');
}
