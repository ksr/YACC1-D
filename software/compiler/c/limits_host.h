/* limits_host.h - the table sizes of y1cc.c on the Mac (host.c). Big enough for the whole corpus AND for y1cc.c
   compiling itself (tests/compiler/twin.py); every overflow is a clean "y1cc: too many ..." error naming the limit.
   The count of each table's entries; the bytes in brackets are what the table costs on the YACC1 (2-byte ints). */
#define NAMES_MAX 4000          /* identifiers, keywords, tags, #define names      [5 ints + 1 byte each: 44K] */
#define NAMEPOOL 32000          /* their text                                     [32K] */
#define HASH_SIZE 1021          /* hash chains of names, literals, labels         [6K] */
#define STRPOOL 32000           /* string literal bytes (each distinct literal once) [32K] */
#define LITS_MAX 2000           /* distinct string literals                       [16K] */
#define STRLIT_MAX 1024         /* bytes in one string literal */
#define TYPES_MAX 400           /* distinct (base, pointer, count) types          [2.4K] */
#define NODES_MAX 40000         /* AST nodes of the whole program                 [480K: the host only] */
#define INCL_DEPTH 8            /* #include nesting */
#define PATHPOOL 4000           /* the paths of the open and included files */
#define INCLS_MAX 64            /* distinct #included files */
#define VARS_MAX 3000           /* globals, parameters and locals                 [33K] */
#define FUNCS_MAX 512           /* functions (definitions and prototypes)          [11K] */
#define REACH_ROW 64            /* bytes of one row of the reach bit matrix: FUNCS_MAX / 8 */
#define REACH_BYTES 32768       /* FUNCS_MAX * REACH_ROW                            [32K] */
#define STRUCTS_MAX 64          /* struct/union definitions */
#define MEMBERS_MAX 512         /* their members */
#define LABELPOOL 40000         /* text of the global, function and variable labels [40K] */
#define ULABELS_MAX 4000        /* those labels                                   [16K] */
#define LKIND_MAX 2000          /* generated labels in one function */
#define LOOPS_MAX 64            /* nested loops and switches */
#define PEND_MAX 16             /* peephole: pending BR lines (256 bytes each) */
#define PARK_MAX 256             /* arguments waiting on the stack, all calls being generated */
#define CASES_MAX 512            /* cases of one switch */
#define EBUF_MAX 2048            /* an error message */
