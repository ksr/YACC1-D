/* target/final.c - pass 9, the assembly text (cc9_final.c), as a Y1/OS program: its Y1/OS table sizes, the Y1/OS I/O layer,
   the pass. os/Makefile builds it for the disk (/LIB/CC/CCn: the native compiler, 2026-09-25), y1cc.py compiles it
   for tests/compiler/passes.py, and the corpus (tests/compiler/corpus.py) has it: the passes compile themselves,
   identically to y1cc.py. */
#include "../ylim/final.h"
char *io_next_pass = "";                              /* the last pass: back to the shell */
#include "../target_io.c"
#include "../target_rd.c"
#include "../cc9_final.c"
