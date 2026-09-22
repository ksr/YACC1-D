/* hello.c - the first /BIN program: prints a line and its arguments */
#include "../lib_abi.c"
#include "y1lib.c"
void main() {
    puts("hello from /BIN/HELLO");
    if (*argstr()) { putstr("args: "); puts(argstr()); }
}
