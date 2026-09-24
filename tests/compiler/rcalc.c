/* rcalc.c - a recursive-descent expression evaluator (2026-09-24): expr -> term -> factor -> ( expr ), the shape of
   the parser a self-hosting compiler needs. Unsigned 16-bit, like int. Grammar:
     expr   = term { ('+' | '-') term }
     term   = unary { ('*' | '/' | '%') unary }
     unary  = '-' unary | factor
     factor = number | '(' expr ')' | name '(' expr ')'   with name = sq (square) or max2 ... */
#include "y1lib.c"

char *p;                    /* the cursor, global: every activation shares it */
int errs;

void skip() { while (*p == ' ') p++; }

int expr();

int number() {
    int v; v = 0;
    while (*p >= '0' && *p <= '9') { v = v * 10 + (*p - '0'); p++; }
    return v;
}

int factor() {
    int v; char name[6]; int n;
    skip();
    if (*p == '(') { p++; v = expr(); skip(); if (*p == ')') p++; else errs++; return v; }
    if (*p >= '0' && *p <= '9') return number();
    n = 0;
    while (*p >= 'a' && *p <= 'z' && n < 5) { name[n] = *p; n++; p++; }
    name[n] = 0;
    skip();
    if (*p != '(') { errs++; return 0; }
    p++; v = expr(); skip();
    if (*p == ')') p++; else errs++;
    if (strcmp(name, "sq") == 0) return v * v;
    if (strcmp(name, "neg") == 0) return 0 - v;
    errs++; return 0;
}

int unary() {
    skip();
    if (*p == '-') { p++; return 0 - unary(); }
    return factor();
}

int term() {
    int v; int r; char op;
    v = unary();
    for (;;) {
        skip(); op = *p;
        if (op != '*' && op != '/' && op != '%') return v;
        p++; r = unary();
        if (op == '*') v = v * r;
        else if (r == 0) errs++;
        else if (op == '/') v = v / r;
        else v = v % r;
    }
    return v;
}

int expr() {
    int v; char op;
    v = term();
    for (;;) {
        skip(); op = *p;
        if (op == '+') { p++; v = v + term(); }
        else if (op == '-') { p++; v = v - term(); }
        else return v;
    }
    return v;
}

void eval(char *s) {
    int v;
    p = s; errs = 0;
    v = expr();
    putstr(s); putstr(" = "); putnum(v);
    if (errs || *p != 0) putstr("  (error)");
    putchar(10);
}

void main() {
    eval("1 + 2 * 3");
    eval("(1 + 2) * 3");
    eval("100 / 7 % 4 + 2 * (3 + 4 * (5 - 1))");
    eval("sq(3) + sq(sq(2))");
    eval("((((((((((((42))))))))))))");
    eval("2 * (3 + (4 * (5 + (6 * (7 + (8 * (9 + 1)))))))");
    eval("10 - neg(5) - -3");
    eval("65535 + 2");
    eval("sq(256)");
    eval("1 + (2 * 3");
    eval("7 / (3 - 3)");
}
