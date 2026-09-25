/* ylim/lex.h - the Y1/OS table sizes of cc1_lex.c (the lexer) (software/compiler/README.md, "The passes": sizes).
   Each overflow is a clean "y1cc: too many ... (NAME)" error; tests/compiler/passes.py measures what fits. */
#define NAMES_MAX    760
#define NAMEPOOL     5400
#define HASH_SIZE    128           /* a power of two (2026-09-25: h & (HASH_SIZE - 1), not a division) */
#define STRPOOL      1800
#define LITS_MAX     160
#define STRLIT_MAX   160
#define INCL_DEPTH   8
#define PATHPOOL     400
#define INCLS_MAX    16
#define LINE_MAX     128
#define DIR_MAX      256
#define ID_MAX       64
#define EBUF_MAX     256
#define IO_RB        64            /* target_io.c (2026-09-25): the bytes read ahead (one buffer), */
#define IO_WB        64            /* and for the file being written */
