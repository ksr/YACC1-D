/* host16p.c - the 16-bit check build of a pass (as host16.c for y1cc.c): int is unsigned short and char unsigned
   (-funsigned-char), the YACC1's integer types, on the Mac. */
#define int unsigned short
#include "plim_host.h"
#include PASS
