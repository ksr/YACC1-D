/* arith.c - 16-bit arithmetic through the runtime helpers and the inline sequences */
#include "y1lib.c"

int a, b;

void show(char *name, int v) { putstr(name); putchar('='); putnum(v); putchar(' '); puthex(v); putchar('\n'); }

void main() {
    int x, y;
    a = 1000; b = 300;
    show("a+b", a + b);
    show("a-b", a - b);
    show("b-a", b - a);          /* wraps: 64836 */
    show("a*b", a * b);          /* 300000 mod 65536 = 37856 */
    show("a/b", a / b);
    show("a%b", a % b);
    show("a/7", a / 7);
    show("a%7", a % 7);
    show("a/8", a / 8);
    show("a%8", a % 8);
    show("a/256", a / 256);
    show("b*2", b * 2);
    show("b*4", b * 4);
    show("b*256", b * 256);
    show("a<<3", a << 3);
    show("a>>3", a >> 3);
    show("a<<8", a << 8);
    show("a>>8", a >> 8);
    show("a<<b/30", a << b / 30);  /* a << 10 */
    show("a>>b/30", a >> b / 30);
    show("a&b", a & b);
    show("a|b", a | b);
    show("a^b", a ^ b);
    show("~a", ~a);
    show("-a", -a);
    show("a+1", a + 1);
    show("a-1", a - 1);
    show("a+255", a + 255);
    show("a+256", a + 256);
    show("a-1000", a - 1000);
    show("65535+1", a - 1000 + 65535 + 1);
    x = 65535; y = 1;
    show("x+y", x + y);
    show("x*x", x * x);          /* 1 */
    show("x/y", x / y);
    show("x/3", x / 3);
    show("x%1000", x % 1000);
    show("0/5", 0 / 5 + y - 1);
    x = 12345;
    show("x/10", x / 10);
    show("x%10", x % 10);
    show("(x+y)*2-3", (x + y) * 2 - 3);
    show("1+2*3", 1 + 2 * 3);
    x = 7; y = 2;
    show("x*y+x/y", x * y + x / y);
    x += 5; show("x+=5", x);
    x -= 2; show("x-=2", x);
    x *= 3; show("x*=3", x);
    x /= 4; show("x/=4", x);
    x %= 5; show("x%=5", x);
    x <<= 4; show("x<<=4", x);
    x >>= 1; show("x>>=1", x);
    x |= 1; show("x|=1", x);
    x &= 6; show("x&=6", x);
    x ^= 255; show("x^=255", x);
    x++; ++x; show("x++ ++x", x);
    x--; --x; show("x-- --x", x);
    y = x++; show("y=x++", y); show("x", x);
    y = ++x; show("y=++x", y); show("x", x);
}
