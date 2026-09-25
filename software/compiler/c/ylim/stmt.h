/* ylim/stmt.h - the Y1/OS table sizes of cc6_stmt.c (the statements) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define FUNCS_MAX    200
#define VARS_MAX     380
#define NODES_MAX    920
#define ENTRIES_MAX  64
#define TREE_MAX     40
#define LOOPS_MAX    12
#define CASES_MAX    64
#define LINE_MAX     128
#define ID_MAX       64
#define EBUF_MAX     256
