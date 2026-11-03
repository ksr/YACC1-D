/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* hello.c - the first /bin program: prints a line and its arguments */
#include "../lib_abi.c"
#include "y1lib.c"
void main() {
    puts("hello from /bin/hello");
    if (*argstr()) { putstr("args: "); puts(argstr()); }
}
