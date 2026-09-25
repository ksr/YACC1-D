/* target/emit.c - pass 8, the expression code generator (cc8_emit.c), as a Y1/OS program: its Y1/OS table sizes, the Y1/OS I/O layer,
   the pass. os/Makefile builds it for the disk (/LIB/CC/CCn: the native compiler, 2026-09-25), y1cc.py compiles it
   for tests/compiler/passes.py, and the corpus (tests/compiler/corpus.py) has it: the passes compile themselves,
   identically to y1cc.py. */
#include "../ylim/emit.h"
char *io_next_pass = "/LIB/CC/CC9";                  /* the pass EXECed when this one is done (target_io.c) */
#include "../target_io.c"
#include "../target_rd.c"
#include "../cc8_emit.c"
