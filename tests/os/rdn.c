/* rdn.c - tests/os/rdn.session (2026-09-27): READN's contract in the patterns that mix it with everything else, so
   that a stale sector buffer, position or count shows. Every file it writes holds a seeded pattern, byte i =
   (lo ^ (lo >> 8) ^ hi * 37 ^ seed) & 255 for i = hi * 65536 + lo, so bytes of another file (or of another place in
   the same one) never pass for the right ones. Every READN's count is checked against the contract (os/README.md):
   exactly min(n, the rest of the position's sector, the rest of the file); 0 at the end, for n = 0 and for anything
   but a read handle.
     rdn w PATH SEED K    K * 1024 + 13 bytes through WRITE in pieces of 1, 13, 511, 512, 513, 1000, 7 and 0 bytes;
                          then (the same program, the handle just closed) opened again and read back with READN
     rdn r PATH SEED      READN in sizes 1, 7, 100, 300, 512, 600, 2, 511, 1000 in turn, a GETC after every fifth
     rdn k PATH SEED      SEEK to boundaries, into sectors, around 64K, to the end and past it, each followed by READNs,
                          a GETC and a READ (which gives the whole sector that holds the position, from its start)
     rdn 2 A SA B SB      two handles on two files read in turn with READN, then A SEEKed into its sector 0 and
                          closed, and B opened on its handle (whose buffer still holds A's sector 0) and read from 0,
                          SEEKed to a boundary, read
     rdn e PATH SEED      the zero results: n = 0, handles 0, 5 and 255, a write handle, a directory handle, the end
   Each mode prints one line, "... ok" or the first thing that differs. run.py compiles it (y1cc --os) as /RDN. */
#include "../../os/lib_fs.c"
#include "../../os/lib_num.c"
#include "y1lib.c"
char buf[1100];
char ent[32];
char path[64];
char path2[64];
char word[16];
int sizes[9];
int sd, hi, lo, h37;                    /* the seed; the position hi:lo the next byte checked has; h37 = hi * 37 */
int lenx, len;                          /* the file's length, bits 16-23 : 0-15 */
int bad, calls;                         /* the first difference printed; READNs made */
int shi[2], slo[2], ssd[2], slen[2], slenx[2];     /* mode 2: the two streams' states */

void at(int x, int p) { hi = x; lo = p; h37 = hi * 37; }

void where() { putstr(" at "); put32(hi, lo, 0); putchar(10); }

void fail(char *what) {                 /* the first difference only */
    if (bad) return;
    bad = 1;
    putstr("rdn: "); putstr(what); where();
}

void check(int c) {                     /* the next byte of the file against the pattern */
    if (c != ((lo ^ (lo >> 8) ^ h37 ^ sd) & 255)) fail("wrong byte");
    lo++;
    if (!lo) { hi++; h37 = hi * 37; }
}

void fill(int m) {                      /* the next m pattern bytes -> buf */
    int i;
    for (i = 0; i < m; i++) {
        buf[i] = lo ^ (lo >> 8) ^ h37 ^ sd;
        lo++;
        if (!lo) { hi++; h37 = hi * 37; }
    }
}

int want(int n) {                       /* what READN(n) must give at hi:lo: min(n, rest of sector, rest of file) */
    int k;
    if (hi > lenx || (hi == lenx && lo >= len)) return 0;
    k = 512 - (lo & 511);
    if (((hi << 7) | (lo >> 9)) == ((lenx << 7) | (len >> 9))) k = len - lo;   /* the last sector */
    if (k > n) k = n;
    return k;
}

int rn(int h, int n) {                  /* READN(h, buf, n), its count and bytes checked; the count */
    int got, w, i;
    w = want(n);
    got = freadn(h, buf, n);
    calls++;
    if (got != w) {
        if (!bad) { bad = 1; putstr("rdn: READN("); putnum(n); putstr(") gave "); putnum(got);
                    putstr(", not "); putnum(w); where(); }
        if (got > 1024) got = 0;
    }
    for (i = 0; i < got; i++) check(buf[i]);
    return got;
}

void gc(int h) {                        /* GETC, checked */
    int c;
    c = fgetc(h);
    if (want(1) == 0) { if (c != 65535) fail("GETC past the end"); return; }
    if (c == 65535) { fail("GETC at the end too early"); return; }
    check(c);
}

int num(char *s) { int k; k = 0; while (*s) { k = k * 10 + *s - '0'; s++; } return k; }

int length(char *p) {                   /* the file's length -> lenx:len; 0 when there is no such file */
    if (!fresolve(p, ent) || !ent_isfile(ent)) return 0;
    len = ent_len(ent); lenx = ent_lenx(ent);
    return 1;
}

int readall(int h) {                    /* READN to the end from hi:lo in the sizes, a GETC after every fifth */
    int i;
    i = 0;
    for (;;) {
        if (!rn(h, sizes[i % 9])) break;
        i++;
        if (i % 5 == 0) gc(h);
        if (bad) return 0;
    }
    if (hi != lenx || lo != len) fail("READN stopped early");
    return !bad;
}

void seekto(int h, int x, int p) {      /* SEEK, checked against the length: a refused SEEK leaves the position */
    int r, ok;
    ok = x < lenx || (x == lenx && p <= len);
    r = fseek(h, x, p);
    if (r != ok) { if (!bad) { bad = 1; putstr("rdn: SEEK gave "); putnum(r); putstr(" for "); put32(x, p, 0);
                               putchar(10); } return; }
    if (ok) at(x, p);
}

void rd(int h) {                        /* READ: the sector holding the position from its start, to its end (or the
                                           file's); the position moves to the next sector */
    int got, w, i, s;
    s = (hi << 7) | (lo >> 9);
    w = 0;
    if (want(1)) {
        w = 512;
        if (s == ((lenx << 7) | (len >> 9))) w = len & 511;
    }
    got = fread(h, buf);
    if (got != w) { if (!bad) { bad = 1; putstr("rdn: READ gave "); putnum(got); putstr(", not "); putnum(w);
                                where(); } return; }
    if (!w) return;
    at(s >> 7, s << 9);
    for (i = 0; i < got; i++) check(buf[i]);
}

void main() {
    char *a; int h, h2, k, n, i, m;
    sizes[0] = 1; sizes[1] = 7; sizes[2] = 100; sizes[3] = 300; sizes[4] = 512; sizes[5] = 600; sizes[6] = 2;
    sizes[7] = 511; sizes[8] = 1000;
    a = argword(argstr(), word, 15);
    a = argword(a, path, 63);
    a = argword(a, path2, 15); sd = num(path2);
    if (word[0] == 'w') {
        argword(a, path2, 15); k = num(path2);
        h = fcreate(path, 0, 0);
        if (!h) { puts("rdn: cannot create"); return; }
        sizes[0] = 1; sizes[1] = 13; sizes[2] = 511; sizes[3] = 512; sizes[4] = 513; sizes[5] = 1000;
        sizes[6] = 7; sizes[7] = 0;
        n = k; m = 13; i = 0;           /* n:m = the bytes left, in 1K and bytes */
        at(0, 0);
        for (;;) {
            k = sizes[i % 8]; i++;
            if (!n && k > m) k = m;
            fill(k);
            if (fwrite(h, buf, k) != k) { puts("rdn: write refused"); fclose(h); return; }
            if (!n && k == m) break;
            while (k) { if (!m) { n--; m = 1024; } m--; k--; }
        }
        if (!fclose(h)) { puts("rdn: close failed"); return; }
        sizes[0] = 1; sizes[1] = 7; sizes[2] = 100; sizes[3] = 300; sizes[4] = 512; sizes[5] = 600;
        sizes[6] = 2; sizes[7] = 511;
        if (!length(path)) { puts("rdn: not written"); return; }
        h2 = fopen(path);
        if (h2 != h) { putstr("rdn: reopened as "); putnum(h2); putstr(", written as "); putnum(h); putchar(10); }
        at(0, 0);
        readall(h2);
        fclose(h2);
        putstr("rdn w: "); put32(lenx, len, 0); putstr(" bytes");
        if (!bad) putstr(", read back ok");
        putchar(10);
        return;
    }
    if (word[0] == '2') {
        a = argword(a, path2, 63);
        argword(a, word, 15);
        for (i = 0; i < 2; i++) {       /* stream 0 = A, 1 = B: their lengths and seeds */
            if (!length(i ? path2 : path)) { puts("rdn: no such file"); return; }
            slen[i] = len; slenx[i] = lenx; shi[i] = 0; slo[i] = 0;
            ssd[i] = i ? num(word) : sd;
        }
        h = fopen(path); h2 = fopen(path2);
        if (!h || !h2) { puts("rdn: cannot open"); return; }
        k = 0;                          /* turns: A, B, A, B ... with the sizes, until both are at their ends */
        for (;;) {
            m = 0;
            for (i = 0; i < 2; i++) {
                hi = shi[i]; lo = slo[i]; h37 = hi * 37; sd = ssd[i]; len = slen[i]; lenx = slenx[i];
                m = m + rn(i ? h2 : h, sizes[k % 9]);
                shi[i] = hi; slo[i] = lo;
                k++;
            }
            if (!m || bad) break;
        }
        sd = ssd[0]; len = slen[0]; lenx = slenx[0];
        seekto(h, 0, 5); rn(h, 10);     /* A's sector 0 in the handle's buffer */
        fclose(h);
        h = fopen(path2);               /* B on A's handle: its buffer holds A's sector 0, B starts in its own 0 */
        hi = 0; lo = 0; h37 = 0; sd = ssd[1]; len = slen[1]; lenx = slenx[1];
        rn(h, 300); rn(h, 212); rn(h, 5);
        seekto(h, 0, 0); rn(h, 40);     /* a boundary SEEK loads nothing: the next READN must */
        seekto(h, 0, 1024); rn(h, 1); gc(h);
        fclose(h);
        fclose(h2);
        putstr("rdn 2: "); putnum(calls); putstr(" READNs");
        if (!bad) putstr(", ok");
        putchar(10);
        return;
    }
    if (!length(path)) { puts("rdn: no such file"); return; }
    h = fopen(path);
    if (!h) { puts("rdn: cannot open"); return; }
    at(0, 0);
    if (word[0] == 'r') {
        readall(h);
        putstr("rdn r: "); put32(hi, lo, 0); putstr(" bytes in "); putnum(calls); putstr(" READNs");
    } else if (word[0] == 'k') {
        rn(h, 700); rn(h, 10);          /* sector 1 in the buffer */
        seekto(h, 0, 0); rn(h, 3); rn(h, 600);                 /* back to a boundary: sector 0 again */
        seekto(h, 0, 700); rn(h, 1); rn(h, 600); rn(h, 600);   /* into sector 1 */
        seekto(h, 0, 511); rn(h, 600); gc(h); rn(h, 2);        /* a sector's last byte */
        seekto(h, 0, 513); rd(h); rn(h, 9);                   /* READ after a SEEK into a sector */
        seekto(h, 0, 1000); rn(h, 5); rd(h); rn(h, 512);      /* READ after a READN inside a sector */
        seekto(h, 0, 1536); rd(h); gc(h); rn(h, 511); rn(h, 1);
        seekto(h, 0, 65535); rn(h, 600); rn(h, 600);          /* the 64K boundary */
        seekto(h, 0, 65024); rn(h, 1000); rn(h, 1000);
        seekto(h, 1, 0); rn(h, 1); seekto(h, 0, 65535); rn(h, 1); rn(h, 1);
        seekto(h, 1, 1); gc(h); rn(h, 600);
        seekto(h, lenx, len - 1); rn(h, 600); rn(h, 600); gc(h);               /* the last byte, the end */
        seekto(h, lenx, len - 700); rn(h, 1000); rn(h, 1000); rn(h, 1000); rd(h);
        seekto(h, lenx, len); rn(h, 5); gc(h); rd(h);
        seekto(h, 0, 2000); seekto(h, lenx, len + 1); rn(h, 100);             /* refused: the position stays */
        seekto(h, lenx + 1, 0); rn(h, 100);
        seekto(h, 0, 2);
        for (i = 0; i < 40; i++) { rn(h, sizes[i % 9]); if (i % 3 == 0) gc(h); }
        putstr("rdn k: "); putnum(calls); putstr(" READNs after SEEKs");
    } else if (word[0] == 'e') {
        rn(h, 0); rn(h, 5);
        n = 0;
        n = n + freadn(0, buf, 10) + freadn(5, buf, 10) + freadn(255, buf, 10);
        h2 = fcreate("/RDN.TMP", 0, 0);
        n = n + freadn(h2, buf, 10);
        fclose(h2); fdelete("/RDN.TMP");
        h2 = opendir("/");
        n = n + freadn(h2, buf, 10);
        fclose(h2);
        seekto(h, lenx, len); rn(h, 10); rn(h, 0);
        fclose(h);
        n = n + freadn(h, buf, 10);      /* closed */
        if (n) fail("a READN that should give 0 did not");
        putstr("rdn e: the zero cases");
    }
    fclose(h);
    if (!bad) putstr(", ok");
    putchar(10);
}
