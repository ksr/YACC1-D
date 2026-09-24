/* target_sec.c - the three output sections of y1cc.c on Y1/OS (split from target_io.c 2026-09-24, so that the passes,
   which write their files through io_wopen/io_wput/io_wclose, do not carry these buffers): section 0 (code) goes
   straight into the output file; sections 1 and 2 (data, uninitialised data) wait in RAM (TSEC bytes each) and are
   appended by io_finish, because Y1/OS allows one file open for writing at a time. Included by target.c only. */
#define TSEC 1024

char tsec1[TSEC];
char tsec2[TSEC];
int tn1;
int tn2;
int touth;

int io_create(char *path) { touth = fcreate(path, 0, 0); return touth != 0; }
void io_put(int s, int c) {
    if (s == 0) { fputc(touth, c); return; }
    if (s == 1) { if (tn1 >= TSEC) io_fail("y1cc: data section over TSEC"); tsec1[tn1] = c; tn1++; return; }
    if (tn2 >= TSEC) io_fail("y1cc: bss section over TSEC");
    tsec2[tn2] = c; tn2++;
}
int io_finish(void) {
    int i;
    for (i = 0; i < tn1; i++) fputc(touth, tsec1[i]);
    for (i = 0; i < tn2; i++) fputc(touth, tsec2[i]);
    fclose(touth);
    return 1;
}
