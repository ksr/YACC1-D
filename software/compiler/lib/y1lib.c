/* y1lib.c - a tiny library for y1cc programs (2026-09-22). Included textually: #include "y1lib.c"
   Functions main() never calls are dropped by the compiler, so including it costs nothing unused.
   int is 16-bit unsigned, char 8-bit unsigned; console output goes through putchar(). */

void putstr(char *s) { while (*s) putchar(*s++); }          /* no newline (puts adds one) */

void putnum(int n) {                                         /* unsigned decimal */
    char buf[6];
    int i;
    i = 0;
    if (n == 0) { putchar('0'); return; }
    while (n) { buf[i] = '0' + n % 10; n = n / 10; i++; }
    while (i) { i--; putchar(buf[i]); }
}

void puthex2(int n) {                                        /* two hex digits */
    char d;
    d = (n >> 4) & 15; putchar(d < 10 ? '0' + d : 'A' + d - 10);
    d = n & 15;        putchar(d < 10 ? '0' + d : 'A' + d - 10);
}

void puthex(int n) { puthex2(n >> 8); puthex2(n); }          /* four hex digits */

int strlen(char *s) { int n; n = 0; while (s[n]) n++; return n; }

int strcmp(char *a, char *b) {                               /* 0 equal, 1 a>b, 65535 a<b (unsigned bytes) */
    while (*a && *a == *b) { a++; b++; }
    if (*a == *b) return 0;
    return *a > *b ? 1 : 65535;
}

char *strcpy(char *d, char *s) { char *r; r = d; while ((*d++ = *s++)) ; return r; }

void memset(char *p, int v, int n) { while (n) { *p++ = v; n--; } }
