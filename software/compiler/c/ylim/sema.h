/* ylim/sema.h - the Y1/OS table sizes of cc7_sema.c (the expression analysis) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define LITS_MAX     160
#define STRUCTS_MAX  16
#define MEMBERS_MAX  64
#define FUNCS_MAX    200
#define REACH_ROW    25
#define REACH_BYTES  5025
#define VARS_MAX     400
#define GLOBS_MAX    128
#define TREE_MAX     40
#define TERR_MAX     24
#define LINE_MAX     128
#define ID_MAX       64
#define EBUF_MAX     256
#define IO_RB        128           /* target_io.c (2026-09-25): the bytes read ahead (one buffer), */
#define IO_WB        128           /* and for the file being written */
