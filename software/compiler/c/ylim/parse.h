/* ylim/parse.h - the Y1/OS table sizes of cc2_parse.c (the parser) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define NODES_MAX    920
#define TYPES_MAX    48
#define ENTRIES_MAX  64
#define LINE_MAX     128
#define ID_MAX       64
#define EBUF_MAX     256
#define IO_RB        128           /* target_io.c (2026-09-25): the bytes read ahead (one buffer), */
#define IO_WB        128           /* and for the file being written */
