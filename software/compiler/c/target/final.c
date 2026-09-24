/* target/final.c - pass 9, the assembly text (cc9_final.c), as a Y1/OS program: its Y1/OS table sizes, the Y1/OS I/O layer,
   the pass. y1cc.py compiles it for tests/compiler/passes.py (its size against the program area), and the
   corpus (tests/compiler/corpus.py) has it: the passes compile themselves, identically to y1cc.py. */
#include "../ylim/final.h"
#include "../target_io.c"
#include "../cc9_final.c"
