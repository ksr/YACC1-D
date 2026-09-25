/* pdefs.h - the numbers shared by the passes of the multi-pass y1cc (2026-09-24; software/compiler/README.md,
   "The passes"). #define lines only (y1cc's preprocessor has nothing else). The first half is y1cc.c's: token kinds,
   predefined names, operators, AST node kinds, label kinds, runtime helpers, the machine. The second half is the
   intermediate files: record codes, instruction mnemonics and operand forms, macros, holes, deferred messages. */

/* ---- token kinds (y1cc.c) -------------------------------------------------------------------------------------- */
#define T_EOF 0
#define T_NUM 1
#define T_ID 2
#define T_KW 3
#define T_STR 4
#define T_OP 5
#define T_LINE 8                /* token file only: the line of the following tokens */

/* ---- predefined names: interned first, in this order ----------------------------------------------------------- */
#define K_INT 1
#define K_CHAR 2
#define K_VOID 3
#define K_STRUCT 4
#define K_UNION 5
#define K_UNSIGNED 6
#define K_CONST 7
#define K_STATIC 8
#define K_IF 9
#define K_ELSE 10
#define K_WHILE 11
#define K_FOR 12
#define K_RETURN 13
#define K_BREAK 14
#define K_CONTINUE 15
#define K_SIZEOF 16
#define K_SWITCH 17
#define K_CASE 18
#define K_DEFAULT 19
#define KW_LAST 19
#define NM_MAIN 20
#define B_GETCHAR 21
#define B_PEEK 22
#define B_PEEKW 23
#define B_INP 24
#define B_BIOS 25
#define B_PUTCHAR 26
#define B_PUTS 27
#define B_POKE 28
#define B_POKEW 29
#define B_OUTP 30
#define B_HALT 31
#define B_CALL 32
#define B_ARGSTR 33
#define B_SYS 34
#define B_FUNCADDR 35
#define NM_PREDEF 35

/* ---- operators, in y1cc.py's PUNCT order --------------------------------------------------------------------- */
#define O_SHLEQ 1
#define O_SHREQ 2
#define O_EQ 3
#define O_NE 4
#define O_LE 5
#define O_GE 6
#define O_SHL 7
#define O_SHR 8
#define O_ANDAND 9
#define O_OROR 10
#define O_ARROW 11
#define O_INC 12
#define O_DEC 13
#define O_ADDEQ 14
#define O_SUBEQ 15
#define O_MULEQ 16
#define O_DIVEQ 17
#define O_MODEQ 18
#define O_ANDEQ 19
#define O_OREQ 20
#define O_XOREQ 21
#define O_LBRACE 22
#define O_RBRACE 23
#define O_LPAREN 24
#define O_RPAREN 25
#define O_LBRACK 26
#define O_RBRACK 27
#define O_SEMI 28
#define O_COMMA 29
#define O_ASSIGN 30
#define O_DOT 31
#define O_QUEST 32
#define O_COLON 33
#define O_PLUS 34
#define O_MINUS 35
#define O_STAR 36
#define O_SLASH 37
#define O_PERCENT 38
#define O_LT 39
#define O_GT 40
#define O_NOT 41
#define O_AMP 42
#define O_BAR 43
#define O_CARET 44
#define O_TILDE 45
#define O_LAST 45

/* ---- AST node kinds -------------------------------------------------------------------------------------------- */
#define N_NUM 1
#define N_STR 2
#define N_ID 3
#define N_UNARY 4
#define N_PREINC 5
#define N_POSTINC 6
#define N_SIZEOFT 7
#define N_SIZEOFE 8
#define N_CALL 9
#define N_INDEX 10
#define N_MEMBER 11
#define N_ARROW 12
#define N_ASSIGN 13
#define N_COND 14
#define N_LOGOR 15
#define N_LOGAND 16
#define N_BIN 17
#define N_BLOCK 20
#define N_DECL 21
#define N_IF 22
#define N_WHILE 23
#define N_FOR 24
#define N_RETURN 25
#define N_SWITCH 26
#define N_CASE 27
#define N_DEFAULT 28
#define N_BREAK 29
#define N_CONTINUE 30
#define N_EMPTY 31
#define N_EXPR 32
#define N_LABEL 33
#define N_STRUCTDEF 40
#define N_MEMBERDEF 41
#define N_PROTO 42
#define N_FUNC 43
#define N_PARAM 44
#define N_GVAR 45
#define N_INITLIST 50
#define N_INITSTR 51
#define N_INITADDR 52
#define N_INITNUM 53

/* ---- label kinds: y1cc.py's lbl() prefixes ---------------------------------------------------------------------- */
#define LK_F 1
#define LK_E 2
#define LK_T 3
#define LK_S 4
#define LK_ELSE 5
#define LK_END 6
#define LK_TOP 7
#define LK_NEXT 8
#define LK_SW 9
#define LK_C 10
#define LK_D 11
#define LK_A 12
#define LK_O 13
#define LK_Z 14
#define LK_ZG 15
#define LK_ZD 16
#define LK_STR 17

/* ---- runtime helpers (emitted in this order when used) ------------------------------------------------------ */
#define RT_SUB 0
#define RT_MUL 1
#define RT_DIVMOD 2
#define RT_SHL 3
#define RT_SHR 4
#define RT_PUTC 5
#define RT_GETC 6
#define RT_PUTS 7
#define RT_FSAVE 8
#define RT_FREST 9
#define RT_COUNT 10

/* ---- the machine ------------------------------------------------------------------------------------------------ */
#define ORG_DEFAULT 12288
#define STACK_TOP 3839
#define MONITOR_RESTART 61440
#define ARGBUF 3904
#define SYSARG 3846
#define SYSRES 3852
#define SYSTAB 3860
#define SYS_CONIN 17
#define SYS_CONOUT 19
#define SYSOLD 21               /* entries 0..21 at SYSTAB; 22..31 at SYSTAB2 = $4FC0 (2026-09-25) */
#define SYSTAB2 20416
#define SYSMAX 31
#define BIOS_CHAROUT 65476
#define BIOS_UARTIN 65512
#define LABEL_MAX 29
#define FRAME_INLINE 8
#define WORD_MAX 32             /* cc9's peephole: the first word of a line, compared with mnemonics only */

/* ---- options (the .opt file) ------------------------------------------------------------------------------------ */
#define OPT_BOOT 1
#define OPT_VECTOR 2
#define OPT_BRUR 4
#define OPT_OS 8
#define OPT_LIST 16
#define OPT_XISA 32             /* --xisa (2026-09-24): LDZ/STZ + the page, ADDIW, SHL16 */

/* ---- stream records (.dat from cc3, .st from cc6, .se from cc7, .em from cc8): one byte, then the operands ----- */
#define R_CODE 1                /* mn form operands: an instruction line (through the peephole) */
#define R_LDEF 2                /* sym: the line "Lxx:" */
#define R_ALLOC 3               /* sym kind: a generated label is made (numbered in stream order by cc9) */
#define R_FLABEL 4              /* fn: the line "f_name:" */
#define R_TEXT 5                /* section text\0: a finished line (section 1 data, 2 bss) */
#define R_DSVAR 6               /* v size: bss "label: DS size" */
#define R_DATALAB 7             /* v: data "label:" */
#define R_DWVAR 8               /* v: data "        DW label" */
#define R_DWSTR 9               /* lit: data "        DW sN" */
#define R_STRUSE 10             /* lit: y1cc.py string(): the literal's label and data at its first use */
#define R_DBLIT 11              /* lit count: data, a char array initialised from a string (zero-padded to count) */
#define R_NEED 12               /* h: runtime helper h is used */
#define R_MACRO 13              /* m operands: an instruction sequence cc9 expands (below) */
#define R_RETIF 14              /* compile_func: RET unless the last code line was RET */
#define R_FUNC 15               /* fn name rbase rptr: a function starts (its -l count, cc7/cc8 context) */
#define R_FEND 16               /* the function ends */
#define R_HOLE 17               /* hk operands tree: expression code cc8 fills in (cc7 adds the attributes) */
#define R_ERROR 18              /* msg\0: a deferred compile error; nothing follows */

/* ---- instruction mnemonics (R_CODE) ------------------------------------------------------------------------------ */
#define MN_LDR 1
#define MN_STR 2
#define MN_MVIW 3
#define MN_MVRLA 4
#define MN_MVRHA 5
#define MN_MVARL 6
#define MN_MVARH 7
#define MN_MVAT 8
#define MN_MVTA 9
#define MN_LDAI 10
#define MN_LDTI 11
#define MN_LDA 12
#define MN_STA 13
#define MN_LDT 14
#define MN_LDAVR 15
#define MN_STAVR 16
#define MN_INCR 17
#define MN_DECR 18
#define MN_ADDI 19
#define MN_ADDIC 20
#define MN_ADDT 21
#define MN_ADDTC 22
#define MN_ANDI 23
#define MN_ORI 24
#define MN_XORI 25
#define MN_ANDT 26
#define MN_ORT 27
#define MN_XORT 28
#define MN_INVA 29
#define MN_CSHL 30
#define MN_CSHR 31
#define MN_PUSHR 32
#define MN_POPR 33
#define MN_PUSH 34
#define MN_POP 35
#define MN_MOVRR 36
#define MN_JSR 37
#define MN_JSRUR 38
#define MN_RET 39
#define MN_BR 40
#define MN_BRZ 41
#define MN_BRNZ 42
#define MN_BREQ 43
#define MN_BRNEQ 44
#define MN_BRLT 45
#define MN_BRGT 46
#define MN_BRUR 47
#define MN_INP 48
#define MN_OUTA 49
#define MN_HALT 50
#define MN_ORG 51
#define MN_SUBT 52
#define MN_SUBI 53
#define MN_BRDEV 54
#define MN_ADDIW 55             /* --xisa (cc8's load_address_r4: ADDIW R4,k) */
#define MN_LAST 55

/* operand forms (R_CODE mn form ...) */
#define F_0 0                   /* "        MN" */
#define F_R 1                   /* reg(1) */
#define F_N 2                   /* num(2) */
#define F_L 3                   /* sym(2): a generated label */
#define F_A 4                   /* address */
#define F_RN 5                  /* reg num */
#define F_RL 6                  /* reg sym */
#define F_RR 7                  /* reg reg */
#define F_RA 8                  /* reg address */
#define F_P 9                   /* port(1) */

/* an address operand: kind(1) id(2) nterms(1) term...: the label, then "+term" for each term (kept as written:
   y1cc.py appends "+k" per member/index step, so g_s+2+4 is not folded to g_s+6). A term is 32 bits, high word(2)
   then low word(2): a constant index times the element size is printed whole, as y1cc.py prints it (g_a+131070
   for a[-1] of an int array, the assembler wraps it) */
#define A_VAR 1                 /* id = variable: its label */
#define A_STR 2                 /* id = literal: "s" + its label number */
#define A_FUNC 3                /* id = function: its label */
#define A_RT 4                  /* id = runtime helper: its name */
#define ATERMS_MAX 8

/* macros (R_MACRO m ...), expanded by cc9 exactly as y1cc.c's functions of the same name. M_ADDR4, M_LOGR4, M_LOGK,
   M_SHR1 and M_NOT are no longer written (2026-09-24: cc8 writes their instructions itself, to make room in cc9) */
#define M_ADDK 1                /* k(2): add_const */
#define M_ADDA 2                /* address: add_const_text */
#define M_ADDR4 3               /* add_r4 */
#define M_LOGR4 4               /* op(1): logic_r4 */
#define M_LOGK 5                /* op(1) k(2): logic_const */
#define M_SHL1 6
#define M_SHR1 7
#define M_SCALE 8               /* esz(2): scale_r3 */
#define M_DEREF 9               /* size(1): deref_r3 (1 or 2) */
#define M_NOT 10                /* not_r3 */
#define M_BREL 11               /* rel(1) sym(2) lomode(1) lok(2): branch_rel */
#define M_FSAVE 12              /* v(2) bytes(2): frame_save */
#define M_FREST 13              /* v(2) bytes(2): frame_restore */
#define M_BSSCLR 14             /* emit_bss_clear */
#define M_SWITCH 15             /* narrow(1) miss(2) ncs(2) (val(2) sym(2))...: gen_switch's dispatch */
#define M_ZP 16                 /* --xisa: MVIW R6,zpage when the page is used (zreload: an entry, after bios/call/sys) */

/* holes (R_HOLE hk ...): expression code; the tree follows (cc6: nodes; cc7: nodes + attributes) */
#define H_EXPR 1                /* root(2): gen_expr_stmt */
#define H_COND 2                /* root(2) sym(2) when(1): gen_cond */
#define H_RET 3                 /* root(2): gen_expr + the char return's high byte (the RET is a record of its own) */
#define H_DECL 4                /* lhs(2) rhs(2): gen_assign(lhs, rhs, 0) */
#define H_SWITCH 5              /* root(2) miss(2) ncs(2) (val(2) sym(2))...: gen_expr, then the dispatch */

/* symbols of generated labels: cc6 numbers its own from 1, cc8 from SYM7 (cc9 maps both to the program's numbers) */
#define SYM7 32768

/* poisoned attributes: cc7 records the error an analysis would raise, cc8 raises it when it asks (below) */
#define E_UNDECL 1              /* a1 = name, a2 = function name: "undeclared identifier 'x' (in f)" */
#define E_NOTSTRUCT 2           /* a1 = tag: "not a struct/union: 'T'" */
#define E_NOMEMBER 3            /* a1 = tag, a2 = member */
#define E_CALLUNDECL 4          /* a1 = name */
#define E_DEREF 5               /* "dereference of a non-pointer" */
#define E_INDEX 6               /* "index of a non-pointer" */
#define E_NOTLVAL 7             /* a1 = node kind */
#define E_UNKTYPE 8             /* a1 = base name (0: '') */
