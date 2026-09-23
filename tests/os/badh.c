/* badh.c - tests/os/badhandle.session's program (2026-09-23): write and read through handles that are not open for
   that, and show that every call is refused and nothing is written: PUTC/WRITE on 0 (with no write open: that used to
   write $0200 and then the boot block), on a read, a directory, a closed and out-of-range handles; GETC/READ/READDIR on
   0, a write handle and out-of-range ones; the 16 bytes at $0200 are compared before and after. run.py compiles it
   (y1cc --os) and puts it on the session's disk as /BADH; the host checks then prove the volume intact. */
#include "../../os/lib_fs.c"
#include "y1lib.c"
char buf[512];
char keep[16];

void pr(char *s, int v) { putstr(s); putchar(' '); putnum(v); putchar(10); }

int putmany(int h, int n) {             /* n PUTCs through h: how many were accepted */
    int i, r;
    r = 0;
    for (i = 0; i < n; i++) r = r + fputc(h, 65 + (i & 15));
    return r;
}

void main() {
    int i, same, hr, hd, hw, hc;
    for (i = 0; i < 16; i++) keep[i] = peek(512 + i);
    for (i = 0; i < 512; i++) buf[i] = 90;
    pr("putc 0 x600", putmany(0, 600));
    pr("write 0 600", fwrite(0, buf, 600));
    hr = fopen("/README.TXT"); hd = opendir("/");
    pr("putc read", putmany(hr, 600)); pr("write read", fwrite(hr, buf, 600));
    pr("putc dir", putmany(hd, 600)); pr("write dir", fwrite(hd, buf, 600));
    pr("putc 5", fputc(5, 65)); pr("putc 255", fputc(255, 65)); pr("putc 256", fputc(256, 65));
    pr("putc 65535", fputc(65535, 65)); pr("write 65535", fwrite(65535, buf, 10));
    hw = fcreate("/BADH.TXT", 0, 0);
    pr("create", hw != 0);
    pr("putc other", fputc(hr, 65)); pr("putc w", putmany(hw, 3));
    pr("getc w", fgetc(hw)); pr("read w", fread(hw, buf)); pr("readdir w", readdir(hw, buf));
    pr("getc 0", fgetc(0)); pr("getc 5", fgetc(5)); pr("getc 65535", fgetc(65535)); pr("getc dir", fgetc(hd));
    pr("read 0", fread(0, buf)); pr("read 9", fread(9, buf)); pr("readdir read", readdir(hr, buf));
    pr("close w", fclose(hw)); hc = hw;
    pr("putc closed", putmany(hc, 600)); pr("write closed", fwrite(hc, buf, 600)); pr("getc closed", fgetc(hc));
    fclose(hr); fclose(hd);
    pr("putc 0 again", putmany(0, 600));
    same = 1;
    for (i = 0; i < 16; i++) if (peek(512 + i) != keep[i]) same = 0;
    pr("0200 untouched", same);
}
