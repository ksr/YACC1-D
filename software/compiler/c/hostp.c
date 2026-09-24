/* hostp.c - one pass of the multi-pass y1cc built for the Mac: the host table sizes, then the pass named by PASS
   (the Makefile: cc -DPASS='"cc1_lex.c"' hostp.c host_io.c -o cc1). */
#include "plim_host.h"
#include PASS
