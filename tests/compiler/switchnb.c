/* switchnb.c - the switch test compiled with --no-brur: every switch is a compare chain (for the machine until
   its microcode has BRUR). Same expected output as switch.c.   no-oracle */
// y1cc: --no-brur
#include "switch.c"
