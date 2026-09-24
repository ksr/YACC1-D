/* host16.c - a CHECK build of y1cc.c on the Mac with the YACC1's integer types: int is unsigned short and char is
   unsigned (-funsigned-char), the trick tests/compiler/host_shim.h plays for the test oracle. Arithmetic still
   happens in the host's int after the usual promotions, so this does not model every 16-bit wrap, but a value that
   does not fit 16 bits, a negative number kept in an int, or a signed char byte shows up as a different output.
   `make y1cc16`; tests/compiler/twin.py --16 runs the corpus through it. */
#define int unsigned short
#include "limits_host.h"
#include "y1cc.c"
