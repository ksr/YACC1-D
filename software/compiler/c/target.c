/* target.c - y1cc.c as a Y1/OS program: the target table sizes, the Y1/OS I/O layer, the compiler. This is the file
   y1cc.py compiles to prove that y1cc.c is written in the subset (tests/compiler/corpus.py "self"; the Makefile's
   `make target` assembles it and reports its size against the 32K program area). Not run on the machine yet. */
#include "limits_y1.h"
#include "target_io.c"
#include "y1cc.c"
