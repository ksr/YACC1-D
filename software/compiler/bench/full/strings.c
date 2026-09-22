#include "y1lib.c"
char buf[40];
void reverse(char *s) { char *e, t; e = s + strlen(s) - 1; while (s < e) { t = *s; *s++ = *e; *e-- = t; } }
void upper(char *s) { for (; *s; s++) if (*s >= 'a' && *s <= 'z') *s -= 32; }
void main() {
    int n;
    strcpy(buf, "hello, world"); puts(buf); reverse(buf); puts(buf); upper(buf); puts(buf);
    if (strcmp(buf, "DLROW ,OLLEH") == 0) puts("equal");
    if (strcmp("abc", "abd") == 65535) puts("less");
    n = strlen(buf); putchar('0' + n / 10); putchar('0' + n % 10); putchar('\n');
}
