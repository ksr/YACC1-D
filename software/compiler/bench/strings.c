char buf[40];
int strlen(char *s) { int n; n = 0; while (s[n]) n = n + 1; return n; }
int strcmp(char *a, char *b) { while (*a && *a == *b) { a = a + 1; b = b + 1; } if (*a == *b) return 0; if (*a > *b) return 1; return 65535; }
char *strcpy(char *d, char *s) { char *r; r = d; while (*s) { *d = *s; d = d + 1; s = s + 1; } *d = 0; return r; }
void reverse(char *s) { int i; int j; char t; i = 0; j = strlen(s) - 1; while (i < j) { t = s[i]; s[i] = s[j]; s[j] = t; i = i + 1; j = j - 1; } }
void upper(char *s) { while (*s) { if (*s >= 'a' && *s <= 'z') *s = *s - 32; s = s + 1; } }
void main() { strcpy(buf, "hello, world"); puts(buf); reverse(buf); puts(buf); upper(buf); puts(buf);
    if (strcmp(buf, "DLROW ,OLLEH") == 0) puts("equal"); if (strcmp("abc", "abd") == 65535) puts("less");
    putchar('0' + strlen(buf) / 10); putchar('0' + strlen(buf) % 10); putchar('\n'); }
