/* target/layout.c - pass 5, the labels and frames (cc5_layout.c), as a Y1/OS program: its Y1/OS table sizes, the Y1/OS I/O layer,
   the pass. os/Makefile builds it for the disk (/LIB/CC/CCn: the native compiler, 2026-09-25), y1cc.py compiles it
   for tests/compiler/passes.py, and the corpus (tests/compiler/corpus.py) has it: the passes compile themselves,
   identically to y1cc.py. */
#include "../ylim/layout.h"
char *io_next_pass = "/LIB/CC/CC6";                  /* the pass EXECed when this one is done (target_io.c) */
#include "../target_io.c"
#include "../target_rd.c"
#include "../cc5_layout.c"
