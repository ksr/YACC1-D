/* limits_y1.h - the table sizes of y1cc.c as a Y1/OS program (target.c, compiled by y1cc.py for the size report and
   the road to a native compiler; software/compiler/README.md). Sized for what a pass of a native compiler could keep
   in the 32K program area next to its code, not for compiling big programs: the whole-program AST (NODES_MAX) is
   what a multi-pass split would move to the disk. With these numbers the tables and buffers take about 41K (make
   target): a native pass would carry only the tables its part of the work needs. */
#define NAMES_MAX 400
#define NAMEPOOL 3000
#define HASH_SIZE 127
#define STRPOOL 1500
#define LITS_MAX 120
#define STRLIT_MAX 256
#define TYPES_MAX 48
#define NODES_MAX 800
#define INCL_DEPTH 4
#define PATHPOOL 300
#define INCLS_MAX 8
#define VARS_MAX 250
#define FUNCS_MAX 80
#define REACH_ROW 10
#define REACH_BYTES 800
#define STRUCTS_MAX 8
#define MEMBERS_MAX 48
#define LABELPOOL 2000
#define ULABELS_MAX 330
#define LKIND_MAX 300
#define LOOPS_MAX 12
#define PEND_MAX 4             /* peephole: pending BR lines (256 bytes each) */
#define PARK_MAX 32             /* arguments waiting on the stack, all calls being generated */
#define CASES_MAX 64            /* cases of one switch */
#define EBUF_MAX 300            /* an error message */
