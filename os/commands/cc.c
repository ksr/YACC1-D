/* cc.c - the native C compiler's command (2026-09-25): y1cc on the machine.
     cc prog.c [-o prog.asm] [--org N] [--boot] [--vector] [--no-brur] [--os] [--xisa] [--stack N] [-l]
   The options are y1cc's (software/compiler/README.md); the assembly goes to prog.asm (or -o), which /BIN/ASM then
   turns into a program: `cc HELLO.C -o HELLO.ASM --org 0x5000 --os`, `asm HELLO.ASM`, `HELLO`.
   The compiler is nine programs, /LIB/CC/CC1 .. CC9 (the passes of software/compiler/c, each built with its stack at
   the top of the program area); this command runs the first with the work prefix CCW and the command line, and
   each pass EXECs the next (SYS_EXEC: the next one replaces it, with the work prefix as its command line), so the
   nine run as one command, inside a > redirect too; a pass that finds an error prints it and EXITs (STATUS 1), and
   the chain stops there. The work files CCW.OPT .. CCW.EM (14 of them) are written in the current directory and
   stay there (the next compile replaces them; Y1/OS reclaims the space of replaced files only with pack).
   The runtime helpers' text is /LIB/Y1CCRT.TXT; #include "name" looks beside the including file, then in /LIB. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "y1lib.c"
char line[128];

void main() {
    char *a; int n;
    a = argstr();
    if (!*a) {
        eputs("usage: cc prog.c [-o prog.asm] [--org N] [--boot] [--os] [--xisa] [--stack N] [--no-brur] [--vector] [-l]");
        return;
    }
    strcpy(line, "CCW ");
    n = strlen(a);
    if (n > 122) { eputs("cc: the command line is too long"); return; }
    strcpy(line + 4, a);
    osexec("/LIB/CC/CC1", line);
    eputs("cc: cannot run /LIB/CC/CC1");
}
