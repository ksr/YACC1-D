/* ylim/layout.h - the Y1/OS table sizes of cc5_layout.c (the labels and frames) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define NAMES_MAX    400
#define NAMEPOOL     2600
#define HASH_SIZE    251
#define TYPES_MAX    48
#define STRUCTS_MAX  16
#define MEMBERS_MAX  64
#define FUNCS_MAX    170
#define VARS_MAX     380
#define ULABELS_MAX  560
#define NODES_MAX    128
#define ENTRIES_MAX  64
#define LINE_MAX     128
#define ID_MAX       64
#define EBUF_MAX     256
