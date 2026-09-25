/* target_rd.c - the source-file reads of io.h on Y1/OS (2026-09-25, from target_io.c): one Y1/OS handle per open
   file. Included by the passes that are not the lexer (target/NAME.c); the lexer, which nests #includes, has
   target_inc.c instead. */
int io_open(char *path) { return fopen(path); }
int io_getc(int h) {
    int c;
    c = fgetc(h);
    if (c == 65535) return 256;
    return c;
}
void io_close(int h) { fclose(h); }
