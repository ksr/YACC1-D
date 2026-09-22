/* switch.c - switch/case/default: byte compare chain, 16-bit chain, dense jump table (BRUR), sparse cases,
   fall-through, break, default first/absent, switch inside a loop with continue, nested switches, char subject */
#include "y1lib.c"

char kind(int n) {                       /* dense 0..9 -> jump table when BRUR is allowed */
    switch (n) {
        case 0: return 'z';
        case 1: case 3: case 5: case 7: case 9: return 'o';
        case 2: case 4: case 6: case 8: return 'e';
        default: return '?';
    }
}

int wide(int v) {                        /* 16-bit sparse cases: compare chain */
    switch (v) {
        case 0x1234: return 1;
        case 0x1200: return 2;
        case 0x0034: return 3;
        case 65535: return 4;
        case 0: return 5;
    }
    return 0;
}

int dense16(int v) {                     /* dense but 16-bit values: table (with holes) */
    switch (v) {
        case 1000: return 10;
        case 1001: return 11;
        case 1002: return 12;
        case 1004: return 14;
        case 1005: return 15;
        case 1006: return 16;
        case 1007: return 17;
        case 1009: return 19;
        default: return 99;
    }
}

int fall(int n) {                        /* fall-through and break */
    int r;
    r = 0;
    switch (n) {
        case 1: r += 1;
        case 2: r += 2;
        case 3: r += 4; break;
        case 4: r += 8;
        default: r += 100;
        case 5: r += 16;
    }
    return r;
}

void main() {
    int i, n;
    char c, *p;
    for (i = 0; i < 12; i++) putchar(kind(i));
    putchar('\n');
    putnum(wide(0x1234)); putnum(wide(0x1200)); putnum(wide(0x34)); putnum(wide(65535)); putnum(wide(0)); putnum(wide(0x1235)); putchar('\n');
    for (i = 998; i < 1011; i++) { putnum(dense16(i)); putchar(' '); }
    putchar('\n');
    for (i = 0; i < 7; i++) { putnum(fall(i)); putchar(' '); }
    putchar('\n');
    /* a char subject, continue inside switch inside a loop, nested switch */
    n = 0; p = "hello, world! 123";
    while (*p) {
        c = *p++;
        switch (c) {
            case ' ': case ',': case '!': continue;
            case 'l':
                n += 10;
                switch (n & 3) { case 0: putchar('L'); break; case 2: putchar('l'); break; default: putchar('?'); }
                break;
            default:
                if (c >= '0' && c <= '9') { putchar('#'); break; }
                putchar(c);
        }
        n++;
    }
    putchar('\n'); putnum(n); putchar('\n');
    switch (3) { case 3: puts("const three"); }
    switch (n) { }
    switch (n) { default: puts("default only"); }
}
