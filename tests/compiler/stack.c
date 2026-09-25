/* stack.c (2026-09-25) - y1cc --stack ADDR: main moves the stack to ADDR and puts the caller's SP back on every
   return. The recursion below pushes its frames on the new stack; the word main saved (the boot stub's SP after
   its JSR, $0EFD) is the first thing on it, at ADDR-1..ADDR; the deepest point reached is found by the $A5 fill
   below it; the early return from main (argument 1 is never given here: the fallthrough path is the tested one,
   the early one is compiled) goes through the same epilogue. If the SP were not restored, main's RET would pop a
   word of the new stack and the program would never reach the boot stub's HALT.
   no-oracle (peek) */
// y1cc: --stack 0xC7FF
#include "y1lib.c"

int depth(int n, int acc) {
    int here;
    if (n == 0) return acc;
    here = n + acc;
    return depth(n - 1, here) + 1;
}

void main() {
    int a; int low;
    a = 0xC000;
    while (a < 0xC700) { poke(a, 0xA5); a++; }
    if (peek(0xC800) == 0x77) return;
    putstr("saved SP "); puthex2(peek(0xC7FF)); puthex2(peek(0xC7FE)); putchar(10);
    putstr("depth "); putnum(depth(40, 0)); putchar(10);
    low = 0xC000;
    while (low < 0xC700 && peek(low) == 0xA5) low++;
    putstr("stack used below $C700: "); putnum(0xC700 - low); putchar(10);
    putstr("back"); putchar(10);
}
