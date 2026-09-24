/* target/emit.c - pass 8, the expression code generator (cc8_emit.c), as a Y1/OS program: its Y1/OS table sizes, the Y1/OS I/O layer,
   the pass. y1cc.py compiles it for tests/compiler/passes.py (its size against the program area), and the
   corpus (tests/compiler/corpus.py) has it: the passes compile themselves, identically to y1cc.py. */
#include "../ylim/emit.h"
#include "../target_io.c"
#include "../cc8_emit.c"
