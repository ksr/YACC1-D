/* rfact.c - recursion (2026-09-24): self-recursive functions with int and char parameters and locals, recursion
   depth 50, a recursive call inside an expression (n * fact(n - 1)), two recursive calls in one expression (fib),
   and a recursive call inside the arguments of another (ackermann: the earlier argument waits on the stack). */
#include "y1lib.c"

int fact(int n) { if (n < 2) return 1; return n * fact(n - 1); }

int fib(int n) { if (n < 2) return n; return fib(n - 1) + fib(n - 2); }

int ack(int m, int n) {
    if (m == 0) return n + 1;
    if (n == 0) return ack(m - 1, 1);
    return ack(m - 1, ack(m, n - 1));
}

/* depth: a local that must survive every deeper call */
int sumto(int n) {
    int here;
    if (n == 0) return 0;
    here = n * 2;
    return sumto(n - 1) + here - n;        /* = n + sumto(n - 1) */
}

/* char parameter and char local: the slots keep their zero high byte through save/restore */
char depthc;
int countdown(char c, int acc) {
    char next;
    if (c == 0) return acc;
    next = c - 1;
    if (next > depthc) depthc = next;
    acc = countdown(next, acc + c);
    if (next != c - 1) return 9999;        /* the local came back intact */
    return acc;
}

/* the result of the recursive call is the value of a statement expression, not only a return */
int power(int b, int e) {
    int half;
    if (e == 0) return 1;
    half = power(b, e / 2);
    if (e % 2) return half * half * b;
    return half * half;
}

void main() {
    int i;
    putstr("fact:"); for (i = 0; i < 9; i++) { putchar(' '); putnum(fact(i)); } putchar(10);
    putstr("fib:");  for (i = 0; i < 15; i++) { putchar(' '); putnum(fib(i)); } putchar(10);
    putstr("ack(2,3)="); putnum(ack(2, 3)); putstr(" ack(1,5)="); putnum(ack(1, 5)); putchar(10);
    putstr("sumto(50)="); putnum(sumto(50)); putchar(10);
    putstr("countdown(50)="); putnum(countdown(50, 0)); putstr(" max="); putnum(depthc); putchar(10);
    putstr("power(3,9)="); putnum(power(3, 9)); putstr(" power(2,15)="); putnum(power(2, 15)); putchar(10);
    putstr("nested: "); putnum(fact(fact(3))); putchar(' '); putnum(fib(fib(7))); putchar(10);
}
