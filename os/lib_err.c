/* lib_err.c - eputs(s): an error message and a line feed on the console; eput2(s, t): s then t, one message
   (Y1/OS, 2026-09-23).
   Today it is putstr + LF, because Y1/OS has no output redirection: stdout IS the console. It stays a function of
   its own so that when the shell gets `>` (BACKLOG) the diagnostics of every command move to the raw console in
   one place, as the P8X eputs() does (a "not found" must never land in an output file or a pipe).
   Ported from P8X os/commands/lib_err.c 2026-09-23, changes: no PUTS/CONOUT BIOS calls (see above). */
void eputs(char *s) { while (*s) putchar(*s++); putchar(10); }
void eput2(char *s, char *t) { while (*s) putchar(*s++); eputs(t); }   /* "cmd: what: " + a name, one message */
