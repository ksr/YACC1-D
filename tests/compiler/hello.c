/* hello.c - the first program: puts, putchar, a string walked with a pointer */
char *greeting = "Hello, YACC1!";

void main() {
    char *p;
    puts(greeting);
    p = "abc";
    while (*p) { putchar(*p); putchar(' '); p++; }
    putchar('\n');
    puts("done");
}
