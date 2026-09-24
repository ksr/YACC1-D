/* ylim/final.h - the Y1/OS table sizes of cc9_final.c (the assembly text) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define NAMES_MAX    400
#define NAMEPOOL     2600
#define VARS_MAX     380
#define FUNCS_MAX    170
#define DROPS_MAX    64
#define STRPOOL      1800
#define LITS_MAX     160
#define LKIND_MAX    200
#define PEND_MAX     4
#define CASES_MAX    64
#define LINE_MAX     128
#define ID_MAX       64
#define EBUF_MAX     256
