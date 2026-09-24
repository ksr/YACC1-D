/* ylim/calls.h - the Y1/OS table sizes of cc4_calls.c (the call graph) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define NAMES_MAX    400
#define NAMEPOOL     2600
#define FUNCS_MAX    170
#define REACH_ROW    22
#define REACH_BYTES  3762
#define NODES_MAX    128
#define ENTRIES_MAX  64
#define LINE_MAX     128
#define ID_MAX       64
#define EBUF_MAX     256
