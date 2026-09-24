/* rlocals.c - recursion with big frames (2026-09-24): local arrays and structs in recursive functions (frames over
   8 bytes go through rt_fsave/rt_frest), an odd-sized frame, pointers to a local passed to a NON-recursive helper
   (allowed: the helper cannot re-enter), a global pointer walk, and tower of Hanoi. */
#include "y1lib.c"

struct pt { int x; int y; char tag; };

/* fills its own local array, recurses, then checks the array survived the deeper calls */
int layers(int n) {
    int a[6]; int i; int s;
    char name[5];
    struct pt p;
    if (n == 0) return 0;
    for (i = 0; i < 6; i++) a[i] = n * 10 + i;
    name[0] = 'a' + n; name[1] = 0;
    p.x = n; p.y = n * n; p.tag = 'A' + n;
    s = layers(n - 1);
    for (i = 0; i < 6; i++) if (a[i] != n * 10 + i) return 60000;
    if (name[0] != 'a' + n || p.x != n || p.y != n * n || p.tag != 'A' + n) return 60001;
    return s + a[5] + p.y;
}

/* an odd frame: one char array of 3 (3 bytes) + an int (2) = 5 bytes, inline save of words and a byte */
int odd(char c) {
    char b[3]; int r;
    b[0] = c; b[1] = c + 1; b[2] = c + 2;
    if (c == 0) return 0;
    r = odd(c - 1);
    return r + b[0] + b[1] + b[2];
}

/* a pointer to a local handed to a helper outside the cycle */
void fill(char *d, int n) { int i; for (i = 0; i < n; i++) d[i] = '0' + i; d[n] = 0; }
int nest(int n) {
    char buf[8]; int len;
    if (n == 0) return 0;
    fill(buf, n > 6 ? 6 : n);
    len = strlen(buf);
    return len + nest(n - 1) + (strcmp(buf, "0123456") == 0);
}

/* tower of Hanoi: 4 parameters, the move list in a global buffer */
char moves[200]; int nmoves;
void hanoi(int n, char from, char to, char via) {
    if (n == 0) return;
    hanoi(n - 1, from, via, to);
    moves[nmoves] = from; moves[nmoves + 1] = to; nmoves = nmoves + 2;
    hanoi(n - 1, via, to, from);
}

/* reverse a string in place by recursion over a global cursor */
char text[20]; char *cur;
void rev(char *s) {
    char c;
    c = *s;
    if (c == 0) return;
    rev(s + 1);
    *cur = c; cur++;
}

void main() {
    int i; char out[20];
    putstr("layers(5)="); putnum(layers(5)); putchar(10);
    putstr("odd(20)="); putnum(odd(20)); putchar(10);
    putstr("nest(9)="); putnum(nest(9)); putchar(10);
    hanoi(4, 'A', 'C', 'B');
    putstr("hanoi(4): "); putnum(nmoves / 2); putstr(" moves:");
    for (i = 0; i < nmoves; i = i + 2) { putchar(' '); putchar(moves[i]); putchar(moves[i + 1]); }
    putchar(10);
    strcpy(text, "recursion!"); cur = out; rev(text); *cur = 0;
    putstr("rev: "); putstr(out); putchar(10);
}
