/* plim_host.h - the table sizes of the passes on the Mac (hostp.c, host16p.c): big enough for the whole corpus and
   for y1cc.c compiling itself; generic names, each pass uses the ones it has tables for (software/compiler/README.md,
   "The passes"; the Y1/OS sizes, one file per pass, are in ylim/). Every overflow is a clean "y1cc: too many ...
   (NAME)" error. */
#define NAMES_MAX 4000          /* names (identifiers, keywords, tags, #define names) */
#define NAMEPOOL 32000          /* their text */
#define HASH_SIZE 1024          /* hash chains of names, literals, labels (a power of two: h & (HASH_SIZE - 1)) */
#define STRPOOL 32000           /* string literal bytes (each distinct literal once) */
#define LITS_MAX 2000           /* distinct string literals */
#define STRLIT_MAX 1024         /* bytes in one string literal */
#define TYPES_MAX 400           /* distinct (base, pointer, count) types */
#define NODES_MAX 8000          /* AST nodes of one top-level declaration (a function with its body) */
#define ENTRIES_MAX 256         /* declarators of one top-level declaration */
#define INCL_DEPTH 8            /* #include nesting */
#define PATHPOOL 4000           /* the paths of the open and included files */
#define INCLS_MAX 64            /* distinct #included files */
#define VARS_MAX 3000           /* globals, parameters and locals */
#define GLOBS_MAX 3000          /* globals (cc7's name lookup) */
#define FUNCS_MAX 512           /* functions (definitions and prototypes) */
#define REACH_ROW 64            /* bytes of one row of the reach bit matrix: FUNCS_MAX / 8 */
#define REACH_BYTES 32832       /* (FUNCS_MAX + 1) * REACH_ROW */
#define STRUCTS_MAX 64          /* struct/union definitions */
#define MEMBERS_MAX 512         /* their members */
#define ULABELS_MAX 4000        /* labels of globals, functions, parameters and locals */
#define LKIND_MAX 2000          /* generated labels in one function */
#define LOOPS_MAX 64            /* nested loops and switches */
#define PEND_MAX 16             /* peephole: pending BR lines (256 bytes each) */
#define PARK_MAX 256            /* arguments waiting on the stack, all calls being generated */
#define CASES_MAX 512           /* cases of one switch */
#define EBUF_MAX 2048           /* an error message */
#define TREE_MAX 512            /* nodes of one expression (with the ++/-- rewrites) */
#define TERR_MAX 250            /* distinct analysis errors in one expression */
#define DROPS_MAX 512           /* dropped (never called) function definitions */
#define LINE_MAX 256            /* a line of assembly, a label, a path */
#define DIR_MAX 512             /* a preprocessor line */
#define ID_MAX 128              /* an identifier */
