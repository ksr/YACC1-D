/* pwd.c - print the current directory.
     pwd        the path, e.g. /BIN
     pwd -h     usage
   Ported from P8X os/commands/pwd.c 2026-09-23, changes: getcwd() (SYS_GETCWD) from lib_fs.c; the buffer is the
   OS's 64 bytes. Replaces the shell's built-in pwd while /BIN/PWD exists (the shell runs /BIN first). */
#include "../lib_fs.c"
#include "y1lib.c"
char buf[64];

void main() {
    char *a;
    a = argstr();
    while (*a == ' ') a++;
    if (a[0] == '-' && (a[1] == 'h' || a[1] == 'H')) { puts("usage: pwd   print the working directory path"); return; }
    getcwd(buf);
    puts(buf);
}
