/* ylim/emit.h - the Y1/OS table sizes of cc8_emit.c (the expression code generator) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define STRUCTS_MAX  16
#define TREE_MAX     40
#define TERR_MAX     24
#define PARK_MAX     32
#define CASES_MAX    64
#define LINE_MAX     128
#define ID_MAX       64
#define EBUF_MAX     256
