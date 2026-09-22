/* structs.c (no-oracle: host struct padding and byte order differ) - struct/union members, pointers to structs, arrays of structs, nested member access */
#include "y1lib.c"

struct point { int x; int y; char tag; };
struct box { struct point lo; struct point hi; char name[8]; };
union both { int w; char b[2]; };

struct point pts[4];
struct box bx;
union both u;

void move(struct point *p, int dx, int dy) { p->x += dx; p->y += dy; p->tag++; }

int area(struct box *b) { return (b->hi.x - b->lo.x) * (b->hi.y - b->lo.y); }

void main() {
    struct point q;
    struct point *pp;
    int i;
    q.x = 3; q.y = 4; q.tag = 'a';
    move(&q, 10, 20);
    putnum(q.x); putchar(' '); putnum(q.y); putchar(' '); putchar(q.tag); putchar('\n');   /* 13 24 b */
    for (i = 0; i < 4; i++) { pts[i].x = i; pts[i].y = i * i; pts[i].tag = 'A' + i; }
    for (i = 0; i < 4; i++) move(&pts[i], 100, 200);
    for (i = 0; i < 4; i++) { putnum(pts[i].x); putchar('/'); putnum(pts[i].y); putchar(pts[i].tag); putchar(' '); }
    putchar('\n');
    pp = pts + 2;
    putnum(pp->x); putchar(' '); putnum((pp + 1)->y); putchar(' '); putnum(pp[1].x); putchar('\n');   /* 102 209 103 */
    bx.lo.x = 10; bx.lo.y = 10; bx.hi.x = 30; bx.hi.y = 15;
    strcpy(bx.name, "box1");
    putnum(area(&bx)); putchar(' '); puts(bx.name);                     /* 100 box1 */
    u.w = 0x1234;
    puthex2(u.b[0]); puthex2(u.b[1]); putchar('\n');                    /* 1234 (big-endian words) */
    u.b[0] = 0xAB;
    puthex(u.w); putchar('\n');                                         /* AB34 */
    putnum(sizeof(struct point)); putchar(' '); putnum(sizeof(struct box)); putchar(' '); putnum(sizeof(pts)); putchar('\n');   /* 5 18 20 */
}
