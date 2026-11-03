/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* shx.c - tests/os/sh.session's program (2026-11-03): EXEC of a script.
     shx PATH     EXEC PATH: a NAME.SH, which the shell runs after this command; "exec failed" if EXEC returns */
#include "../../os/lib_fs.c"
#include "y1lib.c"
char arg[64];

void main() {
    argword(argstr(), arg, 63);
    osexec(arg, 0);
    puts("exec failed");
}
