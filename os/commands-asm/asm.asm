; =====================================================================================================================
; asm.asm - /BIN/ASM, the native YACC1 assembler hand-written in YACC1 assembly (2026-09-26).
;
; The same program as os/commands/asm.c (/BIN/ASMC since 2026-09-26), which stays in the tree as THE SPECIFICATION:
; the same command line (asm [-h] SRC [OUT]), the same output files (a program file with its load and exec address,
; or Intel hex), the same messages on the same lines, the same exit behaviour, byte for byte the same output as asm.c
; and the host assembler RC/asm on every source (tests/asm/run.py). Every routine below names the C function it
; implements; where the C does something odd (RC/asm's quirks, which asm.c copies), this does it too. Any change of
; behaviour goes into both files.
;
; Built by os/Makefile with the host assembler (software/assembler, `asm asm -d=yacc1`, Intel hex, img2bin at $5000).
; The instruction table is asmtab.inc (INCLUDEd at the end), generated from software/assembler/yacc1.def by
; tools/gen_y1_optab.py together with asm.c's os/asm_optab.c: the same patterns and operations, laid out for this
; program (the formats are in the generator, render_asm).
;
; ---- conventions -----------------------------------------------------------------------------------------------
; R0 = PC, R1 = SP (the shell's stack: nothing here recurses; the deepest call chain is ~8 returns). R2 is NEVER used
;   (the machine's LDA/STA/LDR/STR/LDZ/STZ leave the operand address in it). R3..R7, ACC and TMP are scratch: a routine
;   may clobber all of them unless its comment says otherwise; state that must survive a call lives in the variables
;   at the end. The Y1/OS syscalls clobber R3..R7, ACC, TMP (os/y1os.asm); the ROM's CHAROUT preserves everything.
; Uses the --xisa instructions ADDIW and SHL16 (2026-09-24 microcode, as every native tool since then): pointer
;   arithmetic and the number conversion. Not LDZ/STZ (R6 is the translation-table pointer of the hot loops).
; 16-bit adds are ADDT/ADDI then ADDTC/ADDIC with nothing but moves, loads and stores between; nothing tests the carry
;   after a shift or a subtract; multi-byte shifts are CSHL/CSHR chains after an explicit clear (LDAI 0 / CSHL).
; Words in RAM are big-endian (LDR/STR order). Strings are in single quotes, which the assembler does not upper-case.
;
; ---- the speed (the C version's time went into reading lines, hashing and matching) ----------------------------
; - getln: the source is read a sector at a time with READ (straight into SDATA; after an INCLUDE, SEEK back to
;   the outer file's position and skip into its sector), and each line is scanned where it lies: a 0
;   byte (the sentinel) marks the end of the data read and the 254th byte of the line, so the loop tests nothing but
;   a translation table (XL0/XL1: upper case, and 0 for the characters parse() must see: NUL, LF, quotes, ':', ';').
;   A line that runs past the data is moved into the page before SDATA first, so the raw line (the error messages,
;   INCLUDE's file name) is always the bytes in the buffer from LINEST, LINELEN long. A comment is only scanned for
;   its line feed; leading blanks are skipped and put into ln only when the line has a label.
; - The tokenizer works in place in ln (its tokens are copied to TBUF only when one has a blank inside, rare: then
;   the whole expression is tokenized again as asm.c does it); the records are asm.c's, 8 bytes apart instead of 6.
; - Labels: a hash of 256 chains (h = rotl8(h) + c), each record `len|flags next value name` with the name stored
;   backwards, so that the compare starts at the end, where y1cc's labels differ.
; - Mnemonics: 64 chains with the generator's seed; output through a 64-byte buffer (as asm.c: the same write calls).
; =====================================================================================================================

        ORG 5000H

; ---- the ROM and the Y1/OS syscall interface (os/lib_abi.c) ----------------------------------------------------
B_CHAROUT:  EQU 0FFC4H          ; ACC -> the console, raw (preserves every register): the error messages
SYSARG0:    EQU 0F06H           ; the syscall arguments and result, big-endian words
SYSARG1:    EQU 0F08H
SYSARG2:    EQU 0F0AH
SYSRES:     EQU 0F0CH
ARGBUF:     EQU 0F40H           ; the command tail
SY_OPEN:    EQU 0F14H           ; SYSTAB + 2n: the handlers of OPEN (0), READ (1), CLOSE (3), CREATE (4), WRITE (5),
SY_READ:    EQU 0F16H           ;   DELETE (7), CONOUT (19)
SY_CLOSE:   EQU 0F1AH
SY_CREATE:  EQU 0F1CH
SY_WRITE:   EQU 0F1EH
SY_DELETE:  EQU 0F22H
SY_CONOUT:  EQU 0F3AH
SY_SEEK:    EQU 4FF0H           ; SYSTAB2 + 2n: SEEK (24)

; =====================================================================================================================
; main (asm.c main): the arguments, pass 1, the output file, pass 2, the summary.
; =====================================================================================================================
start:  JSR init
        MVIW R5,ARGBUF
st_sp:  LDAVR R5                ; a = argstr(), past the blanks
        LDTI 32
        BRNEQ st_h
        INCR R5
        BR st_sp
st_h:   LDTI 45                 ; -h and a blank or the end after it: Intel hex
        BRNEQ st_w
        MOVRR R5,R4
        INCR R4
        LDAVR R4
        ORI 32
        LDTI 104
        BRNEQ st_w
        INCR R4
        LDAVR R4
        LDTI 33
        BRLT st_hx
        BR st_w
st_hx:  LDAI 1
        STA HEXO
        MOVRR R4,R5
st_w:   MVIW R4,SRCN
        LDAI 58
        JSR argword
        MVIW R4,OUTN
        LDAI 63
        JSR argword
        LDA SRCN
        BRZ st_use
        LDTI 45
        BRNEQ st_ext
st_use: MVIW R3,S_USAGE         ; puts(): stdout and a line feed
        JSR ostr
        LDAI 10
        BR oc
st_ext: MVIW R5,SRCN            ; the last '.' after the last '/': none -> SRC gets .ASM
        MVIW R6,0
se_lp:  LDAVR R5
        BRZ se_e
        LDTI 46
        BRNEQ se_1
        MOVRR R5,R6
se_1:   LDTI 47
        BRNEQ se_2
        MVIW R6,0
se_2:   INCR R5
        BR se_lp
se_e:   MVRHA R6                ; (a pointer into SRCN is never below $5000)
        BRNZ se_d
        MOVRR R5,R6
        MOVRR R5,R4
        MVIW R3,S_DOTASM
        JSR scpy
se_d:   STR R6,DOTP
        LDA OUTN
        BRNZ st_p1
        MVIW R3,SRCN            ; OUT = SRC up to the dot (+ .IMG with -h)
        MVIW R4,OUTN
so_lp:  MVRLA R3
        MVAT
        MVRLA R6
        BRNEQ so_c
        MVRHA R3
        MVAT
        MVRHA R6
        BREQ so_e
so_c:   LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        BR so_lp
so_e:   LDIVR R4,0
        LDA HEXO
        BRZ st_p1
        MVIW R3,S_DOTIMG
        JSR scpy
st_p1:  LDAI 1
        JSR runpass
        BRZ st_o1
        MVIW R3,1               ; the source cannot be opened
        STR R3,ERRS
        MVIW R3,S_CANTOPEN
        MVIW R4,SRCN
        BR eput2
st_o1:  LDR R3,ERRS
        MVRLA R3
        BRNZ st_rep
        MVRHA R3
        BRNZ st_rep
        LDR R3,FIRST            ; OUT: load = the first byte's address, exec = END's (else the load address)
        STR R3,SYSARG1
        LDA SSET
        BRZ st_c1
        LDR R3,STARTA
st_c1:  STR R3,SYSARG2
        MVIW R3,OUTN
        STR R3,SYSARG0
        LDR R7,SY_CREATE
        JSRUR R7
        LDR R3,SYSRES
        STR R3,OH
        MVRLA R3
        BRNZ st_c2
        MVIW R3,1
        STR R3,ERRS
        MVIW R3,S_CANTMAKE
        MVIW R4,OUTN
        BR eput2
st_c2:  LDR R3,FIRST
        STR R3,FPOS
        LDAI 2
        JSR runpass
        JSR flush
        LDA HEXO
        BRZ st_c3
        MVIW R3,S_ENDREC        ; the end record
st_c4:  LDAVR R3
        BRZ st_c3
        JSR oput                ; (preserves R3)
        INCR R3
        BR st_c4
st_c3:  LDA OPTR+1              ; the rest of the buffer
        ANDI 63
        BRZ st_cl
        JSR owrite
st_cl:  LDR R3,OH
        STR R3,SYSARG0
        LDR R7,SY_CLOSE
        JSRUR R7
        LDR R3,ERRS
        MVRLA R3
        BRNZ st_del
        MVRHA R3
        BRZ st_sum
st_del: MVIW R3,OUTN            ; after an error OUT goes
        STR R3,SYSARG0
        LDR R7,SY_DELETE
        JSRUR R7
st_rep: LDAI 1                  ; "asm: N error(s)[, no OUT]"
        STA TOERR
        MVIW R3,S_ASM
        JSR ostr
        LDR R3,ERRS
        JSR odec
        MVIW R3,S_ERRORS
        LDR R4,ERRS
        MVRHA R4
        BRNZ sr_1
        MVRLA R4
        LDTI 1
        BRNEQ sr_1
        MVIW R3,S_ERROR
sr_1:   JSR ostr
        LDA OH+1
        BRZ sr_2
        MVIW R3,S_NO
        JSR ostr
        MVIW R3,OUTN
        JSR ostr
sr_2:   LDAI 10
        BR oc
st_sum: MVIW R3,OUTN            ; "OUT: N bytes, N labels[, load AAAA exec AAAA]"
        JSR ostr
        MVIW R3,S_COLSP
        JSR ostr
        LDR R3,NBYTES
        JSR odec
        MVIW R3,S_BYTES
        JSR ostr
        LDR R3,NSYM
        JSR odec
        MVIW R3,S_LABELS
        JSR ostr
        LDA FSET
        BRZ sr_2
        MVIW R3,S_LOAD
        JSR ostr
        LDR R3,FIRST
        JSR ohex
        MVIW R3,S_EXEC
        JSR ostr
        LDR R3,FIRST
        LDA SSET
        BRZ ss_1
        LDR R3,STARTA
ss_1:   JSR ohex
        BR sr_2

; argword (lib_fs.c): the next word of the tail at R5 -> R4 (ACC = the most characters kept), NUL-terminated;
; R5 -> past it and the blanks after it
argword: STA AW_MAX
aw_sp:  LDAVR R5
        LDTI 32
        BRNEQ aw_w
        INCR R5
        BR aw_sp
aw_w:   MVIW R3,0
aw_lp:  LDAVR R5
        BRZ aw_e
        LDTI 32
        BREQ aw_e
        LDA AW_MAX
        MVAT
        MVRLA R3
        BRLT aw_st
        BR aw_nx
aw_st:  LDAVR R5
        STAVR R4
        INCR R4
        INCR R3
aw_nx:  INCR R5
        BR aw_lp
aw_e:   LDIVR R4,0
aw_s2:  LDAVR R5
        LDTI 32
        BRNEQ rts
        INCR R5
        BR aw_s2

; scpy: the string at R3 -> R4 (with its NUL)
scpy:   LDAVR R3
        STAVR R4
        BRZ rts
        INCR R3
        INCR R4
        BR scpy
rts:    RET

; init: the variables zeroed (C's BSS), the three translation tables built
init:   MVIW R3,HEADH           ; the label chains, HEADH and HEADL
        MVIW R4,512
        JSR zero
        MVIW R3,ZBEG            ; every variable
        MVIW R4,ZLEN
        JSR zero
        MVIW R3,ZTOP            ; tokens, arguments, the buffers
        MVIW R4,ZTLEN
        JSR zero
        MVIW R3,XL0             ; XL0, XL1, TOKC: c -> c
in_id:  MVRLA R3
        STAVR R3
        INCR R3
        MVRHA R3
        LDTI (HEADH).1
        BRNEQ in_id
        MVIW R3,XL0+97          ; XL0: a..z -> A..Z (makeupper outside single quotes)
        MVIB R4,26
in_uc:  LDAVR R3
        SUBI 32
        STAVR R3
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ in_uc
        MVIW R3,XL0+10          ; XL0 and XL1: what getln must see -> 0 (and NUL is 0)
        LDIVR R3,0
        MVIW R3,XL0+34
        LDIVR R3,0
        MVIW R3,XL0+39
        LDIVR R3,0
        MVIW R3,XL0+58
        LDIVR R3,0
        MVIW R3,XL0+59
        LDIVR R3,0
        MVIW R3,XL1+10
        LDIVR R3,0
        MVIW R3,XL1+34
        LDIVR R3,0
        MVIW R3,XL1+39
        LDIVR R3,0
        MVIW R3,XL1+58
        LDIVR R3,0
        MVIW R3,XL1+59
        LDIVR R3,0
        MVIW R3,TOKC+1          ; TOKC: 1..32 and 128..255 -> 1 (skipped; isws), quotes -> 2, operators -> 3
in_t1:  LDIVR R3,1
        INCR R3
        MVRLA R3
        LDTI 33
        BRNEQ in_t1
        MVIW R3,TOKC+128
in_t2:  LDIVR R3,1
        INCR R3
        MVRLA R3
        BRNZ in_t2
        MVIW R3,TOKC+34
        LDIVR R3,2
        MVIW R3,TOKC+39
        LDIVR R3,2
        MVIW R3,TOKC+33         ; ! $ & ( ) * + - . /
        LDIVR R3,3
        MVIW R3,TOKC+36
        LDIVR R3,3
        MVIW R3,TOKC+38
        LDIVR R3,3
        MVIW R3,TOKC+40
        MVIB R4,4
in_t3:  LDIVR R3,3              ; ( ) * +
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ in_t3
        MVIW R3,TOKC+45
        MVIB R4,3
in_t4:  LDIVR R3,3              ; - . /
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ in_t4
        MVIW R3,OBUF
        STR R3,OPTR
        MVIW R3,POOL
        STR R3,PTOP
        RET

; zero: R4 bytes from R3 (R4 > 0)
zero:   LDIVR R3,0
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ zero
        MVRHA R4
        BRNZ zero
        RET

; =====================================================================================================================
; Text output (asm.c oc, ostr, odec, ohex; lib_err.c eput2). oc writes to the raw console while TOERR is set (the
; error messages: CHAROUT, past a > redirect), else to stdout (the CONOUT syscall: the summary, the usage).
; oc and ostr preserve R3..R6.
; =====================================================================================================================
oc:     STA OC_C
        LDA TOERR
        BRZ oc_so
        LDA OC_C
        BR B_CHAROUT
oc_so:  PUSHR R3
        PUSHR R4
        PUSHR R5
        PUSHR R6
        LDAI 0
        STA SYSARG0
        LDA OC_C
        STA SYSARG0+1
        LDR R7,SY_CONOUT
        JSRUR R7
        POPR R6
        POPR R5
        POPR R4
        POPR R3
        RET
ostr:   LDAVR R3
        BRZ rts
        JSR oc
        INCR R3
        BR ostr
; odec: R3 in decimal (at least one digit)
odec:   LDAI 0
        PUSH
od_lp:  JSR div10
        ADDI 48
        PUSH
        MVRLA R3
        BRNZ od_lp
        MVRHA R3
        BRNZ od_lp
od_pr:  POP
        BRZ rts
        JSR oc
        BR od_pr
; div10: R3 = R3 / 10, ACC = the remainder (R4, R5 clobbered)
div10:  MVIW R4,0
        MVIB R5,16
dv_lp:  MVRHA R3
        ANDI 128
        STA DV_B
        SHL16 R3
        SHL16 R4
        LDA DV_B
        BRZ dv_1
        INCR R4
dv_1:   MVRLA R4
        LDTI 10
        BRLT dv_2
        SUBI 10
        MVARL R4
        INCR R3
dv_2:   DECR R5
        MVRLA R5
        BRNZ dv_lp
        MVRLA R4
        RET
; ohex: R3 as four lower-case hex digits
ohex:   MVRHA R3
        JSR ohx2
        MVRLA R3
ohx2:   STA OX_B
        SHR
        SHR
        SHR
        SHR
        JSR hexd
        JSR oc
        LDA OX_B
        ANDI 15
        JSR hexd
        BR oc
hexd:   LDTI 10                 ; asm.c hexd: 0..15 -> '0'..'9', 'a'..'f'
        BRLT hx_d
        ADDI 39
hx_d:   ADDI 48
        RET
; eput2: the strings at R3 and R4 and a line feed, raw (lib_err.c)
eput2:  LDAVR R3
        BRZ ep_2
        JSR B_CHAROUT
        INCR R3
        BR eput2
ep_2:   LDAVR R4
        BRZ ep_3
        JSR B_CHAROUT
        INCR R4
        BR ep_2
ep_3:   LDAI 10
        BR B_CHAROUT

; =====================================================================================================================
; err (asm.c err, fatal): one message a line, "asm: [INCLUDE ]LINE: message[: what]", then the line as read (its
; printable part). R3 = the message, R4 = what (0: none). fatal also stops the pass.
; =====================================================================================================================
fatal:  JSR err
        LDAI 1
        STA STOP
        RET
err:    LDA LNERR
        BRNZ rts
        STR R3,ER_M
        STR R4,ER_W
        LDAI 1
        STA LNERR
        STA TOERR
        LDR R3,ERRS
        INCR R3
        STR R3,ERRS
        MVIW R3,S_ASM
        JSR ostr
        LDA FDEP
        BRZ er_1
        MVIW R3,S_INCSP
        JSR ostr
er_1:   LDR R3,LNUM
        JSR odec
        MVIW R3,S_COLSP
        JSR ostr
        LDR R3,ER_M
        JSR ostr
        LDA ER_W
        BRZ er_2
        MVIW R3,S_COLSP
        JSR ostr
        LDR R3,ER_W
        JSR ostr
er_2:   MVIW R3,S_NLSP
        JSR ostr
        LDR R3,LINEST           ; the raw line: a 0 after it meanwhile
        MOVRR R3,R4
        LDA LINELEN
        MVAT
        MVRLA R4
        ADDT
        MVARL R4
        MVRHA R4
        ADDIC 0
        MVARH R4
        STR R4,ER_E
        LDAVR R4
        STA ER_SV
        LDIVR R4,0
er_rl:  LDAVR R3
        LDTI 9
        BREQ er_pr
        LDTI 32
        BRLT er_rd
        LDTI 127
        BRGT er_rd
er_pr:  JSR oc
        INCR R3
        BR er_rl
er_rd:  LDR R4,ER_E
        LDA ER_SV
        STAVR R4
        LDAI 10
        JSR oc
        LDAI 0
        STA TOERR
        RET

; =====================================================================================================================
; runpass (asm.c runpass): pass ACC over the source. ACC = 1: the source cannot be opened.
; =====================================================================================================================
runpass: STA PASS
        MVIW R3,0
        STR R3,ALO
        STR R3,AHI
        STR R3,LNUM
        LDAI 0
        STA FDEP
        JSR gl_new
        MVIW R3,SRCN
        STR R3,SYSARG0
        LDR R7,SY_OPEN
        JSRUR R7
        LDR R3,SYSRES
        STR R3,FH
        MVRLA R3
        BRNZ rp_lp
        LDAI 1
        RET
rp_lp:  LDA STOP
        BRNZ rp_stp
        JSR getln
        BRNZ rp_ln
        JSR popf                ; the end of a file
        BRZ rp_lp
        LDAI 0
        RET
rp_ln:  STA RP_C
        LDR R3,LNUM
        INCR R3
        STR R3,LNUM
        LDAI 0
        STA LNERR
        LDA RP_C
        LDTI 2
        BRNEQ rp_1
        JSR include
        BR rp_lp
rp_1:   LDR R5,CMD              ; MACRO: not supported
        LDAVR R5
        LDTI 77
        BRNEQ rp_2
        MVIW R4,S_MACRO
        JSR pfx
        BRZ rp_2
        MVIW R3,S_NOTSUP
        MVIW R4,0
        JSR fatal
        BR rp_lp
rp_2:   MVIW R3,0
        STR R3,CURLAB
        LDA PASS
        LDTI 1
        BRNEQ rp_3
        LDA LLEN
        BRZ rp_3
        JSR deflabel
        LDA STOP
        BRNZ rp_lp
rp_3:   JSR asmcmd
        BR rp_lp
rp_stp: JSR popf
        BRZ rp_stp
        LDAI 0
        RET

; pfx (asm.c pfx): ACC = 1 when the string at R5 starts with the one at R4 (R4, R5 advance)
pfx:    LDAVR R4
        BRZ pf_y
        MVAT
        LDAVR R5
        BRNEQ pf_n
        INCR R4
        INCR R5
        BR pfx
pf_y:   LDAI 1
        RET
pf_n:   LDAI 0
        RET

; =====================================================================================================================
; The source (asm.c getln, include, popf). One buffer for every file: SPRE (256, the start of a line that ran past
; the data read) + SDATA (512, what READN gave) + a byte for the sentinel. GLP = the next byte, GL_END = the end of
; the data (a 0 there), NPOS = the file position after it (24 bits). An INCLUDE keeps the outer file's position of
; GLP and SEEKs back to it at the included file's end.
; =====================================================================================================================
gl_new: MVIW R3,SDATA           ; an empty buffer, position 0
        STR R3,GLP
        STR R3,GL_END
        LDIVR R3,0
        LDAI 0
        STA NPOS
        STA NPOS+1
        STA NPOS+2
        STA GL_LF
        RET

; getln: the next line -> ln (upper case outside single quotes, the comment cut), LLEN (the label: ln[0..LLEN)),
; CMD (the instruction, trimmed), LINEST/LINELEN (the raw line in the buffer). ACC = 0 at the end of the file, 1 a
; line, 2 an INCLUDE line. RC/asm reads 254 bytes at a time (fgets(buffer, 255)): a longer line is two.
getln:  LDR R4,GLP
        STR R4,LINEST
        JSR gl_lim
        LDAI 0
        STA GLQ
        STA GL_T
        LDTI 32                 ; the leading blanks: skipped, put into ln by gl_lab if there is a label
gl_ws:  LDAVR R4
        BRNEQ gl_wt
        INCR R4
        LDAVR R4
        BRNEQ gl_wt
        INCR R4
        BR gl_ws
gl_wt:  LDTI 9
        BRNEQ gl_w2
        INCR R4
        LDTI 32
        BR gl_ws
gl_w2:  LDA LINEST+1            ; ln goes on at the same offset
        MVAT
        MVRLA R4
        SUBT
        STA GL_LW
        MVIW R5,LN
        MVARL R5
        MVIW R6,XL0
gl_lp:  LDAVR R4                ; the loop: 8 instructions a byte
        INCR R4
        MVARL R6
        LDAVR R6
        BRZ gl_sp
        STAVR R5
        INCR R5
        BR gl_lp
gl_sp:  MOVRR R4,R7             ; a byte parse() must see
        DECR R7
        LDAVR R7
        BRZ gl_nul
        LDTI 10
        BREQ gl_eol
        LDTI 39
        BREQ gl_sq
        LDTI 34
        BREQ gl_dq
        LDTI 58
        BREQ gl_col
        LDA GLQ                ; ';' outside quotes: the comment
        BRZ gl_cm0
        LDAI 59
gl_st:  STAVR R5
        INCR R5
        BR gl_lp
gl_col: LDA GLQ                ; ':' outside quotes, the first: the label ends
        BRNZ gl_c2
        LDA GL_T
        BRNZ gl_c2
        MVRLA R5
        ADDI 1
        STA GL_T
gl_c2:  LDAI 58
        BR gl_st
gl_sq:  MVRHA R6                ; makeupper: single quotes switch the table
        XORI 1
        MVARH R6
        LDTI 39
        BR gl_q
gl_dq:  LDTI 34
gl_q:   LDA GLQ                ; parse: q = q == c ? 0 : c
        BREQ gl_q0
        MVTA
        BR gl_q1
gl_q0:  LDAI 0
gl_q1:  STA GLQ
        MVTA
        BR gl_st
gl_nul: JSR gl_sen              ; a 0: the sentinel, or a NUL in the text
        BRZ gl_cm0              ; a NUL: parse() ends the text there
        LDTI 2
        BREQ gl_lp              ; the buffer refilled: on
        BRLT gl_eol             ; the line ends (254 bytes, or the end of the file)
        LDAI 0                  ; the end of the file, nothing read
        STA LINELEN
        RET
gl_cm0: MVRLA R5                ; the comment: e = here, and only its line feed matters
        STA GL_E
gl_cmt: LDTI 10
gl_cl:  LDAVR R4
        INCR R4
        BRGT gl_cl
        BREQ gl_eoc
        BRNZ gl_cl
        JSR gl_sen
        BRZ gl_cmt
        LDTI 2
        BREQ gl_cmt
        BR gl_eoc
gl_eol: MVRLA R5                ; e = the end
        STA GL_E
gl_eoc: STR R4,GLP
        JSR gl_rst
        LDR R4,GLP
        LDA LINEST+1            ; LINELEN = GLP - LINEST (at most 254)
        MVAT
        MVRLA R4
        SUBT
        STA LINELEN
        LDA GL_T
        BRZ gl_nl
        SUBI 1                  ; the label: ln[0..t)
        STA LLEN
        JSR gl_lab
        LDA GL_T
        BR gl_p
gl_nl:  STA LLEN
        LDA GL_LW
gl_p:   MVIW R5,LN              ; trim the start (isws: <= ' ' or >= 128)
        MVARL R5
        MVIW R6,TOKC
        LDA GL_E
        MVAT
gl_tr:  MVRLA R5
        BREQ gl_trd
        LDAVR R5
        MVARL R6
        LDAVR R6
        ANDI 0FEH
        BRNZ gl_trd
        INCR R5
        BR gl_tr
gl_trd: STR R5,CMD
        MVIW R4,LN              ; *e = 0, and the end trimmed
        LDA GL_E
        MVARL R4
        LDIVR R4,0
gl_te:  MVRLA R4
        MVAT
        MVRLA R5
        BREQ gl_ted
        DECR R4
        LDAVR R4
        MVARL R6
        LDAVR R6
        ANDI 0FEH
        BRNZ gl_ted
        LDIVR R4,0
        BR gl_te
gl_ted: LDAVR R5                ; INCLUDE ...
        LDTI 73
        BRNEQ gl_r1
        MVIW R4,S_INCL
        JSR pfx
        BRZ gl_r1
        LDAI 2
        RET
gl_r1:  LDAI 1
        RET

; gl_lab: a line with a label: its leading blanks (not stored by getln) into ln[0..GL_LW) from the raw line
gl_lab: LDA GL_LW
        BRZ rts
        MVARL R5
        LDR R3,LINEST
        MVIW R4,LN
gb_lp:  LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        DECR R5
        MVRLA R5
        BRNZ gb_lp
        RET

; gl_lim: the sentinel of the 254-byte limit: a 0 at R4 + 254 unless the data ends before (preserves R4)
gl_lim: MOVRR R4,R3
        ADDIW R3,254
        LDR R7,GL_END
        MVRHA R7
        MVAT
        MVRHA R3
        BRLT gl_l1
        BRGT gl_l2
        MVRLA R7
        MVAT
        MVRLA R3
        BRLT gl_l1
gl_l2:  STR R7,GLLIM
        LDAI 0
        STA GL_LF
        RET
gl_l1:  STR R3,GLLIM
        LDAVR R3
        STA GL_LSV
        LDIVR R3,0
        LDAI 1
        STA GL_LF
        RET
; gl_rst: the byte under the limit's sentinel back (preserves R4, R5)
gl_rst: LDA GL_LF
        BRZ rts
        LDR R3,GLLIM
        LDA GL_LSV
        STAVR R3
        RET

; gl_sen: a 0 was read (R4 is past it). ACC = 0: a NUL in the text (nothing changed); else it was a sentinel and R4
; points at it again: 1 the line ends (its 254th byte; or the end of the file after some bytes), 2 the buffer was
; refilled (R4 = SDATA, the line so far moved into SPRE: go on reading), 3 the end of the file with nothing read.
; R5 and R6 are kept.
gl_sen: MOVRR R4,R7
        DECR R7
        LDR R3,GLLIM
        MVRLA R7
        MVAT
        MVRLA R3
        BRNEQ gs_nul
        MVRHA R7
        MVAT
        MVRHA R3
        BREQ gs_sen
gs_nul: LDAI 0
        RET
gs_sen: STR R5,GL_R5
        STR R6,GL_R6
        JSR gl_rst
        MOVRR R7,R4
        LDA LINEST+1            ; the line so far: R4 - LINEST
        MVAT
        MVRLA R4
        SUBT
        STA GL_N
        LDTI 254
        BRNEQ gs_ref
        LDAI 1                  ; 254 bytes: the line ends
        BR gs_ret
gs_ref: MVIW R5,SDATA           ; the line so far -> just before SDATA (ascending: the ranges may overlap)
        LDA GL_N
        BRZ gs_r0
        INVA
        ADDI 1
        MVARL R5
        LDAI (SDATA).1-1
        MVARH R5
gs_r0:  LDR R3,LINEST
        STR R5,LINEST
        LDA GL_N
        BRZ gs_rd
        MVARL R6
gs_mv:  LDAVR R3
        STAVR R5
        INCR R3
        INCR R5
        DECR R6
        MVRLA R6
        BRNZ gs_mv
gs_rd:  LDR R3,FH               ; READ(fh, SDATA): the sector that holds the position, from its start
        STR R3,SYSARG0
        MVIW R3,SDATA
        STR R3,SYSARG1
        LDR R7,SY_READ
        JSRUR R7
        LDR R3,SYSRES
        LDA NPOS+2              ; NPOS += n
        MVAT
        MVRLA R3
        ADDT
        STA NPOS+2
        LDA NPOS+1
        MVAT
        MVRHA R3
        ADDTC
        STA NPOS+1
        LDA NPOS
        ADDIC 0
        STA NPOS
        MOVRR R3,R4             ; GL_END = SDATA + n, a 0 there
        ADDIW R4,SDATA
        STR R4,GL_END
        LDIVR R4,0
        MVIW R4,SDATA
        MVRLA R3
        BRNZ gs_got
        MVRHA R3
        BRNZ gs_got
        LDA GL_N                ; nothing more: the end of the file
        BRZ gs_eof
        LDAI 1
        BR gs_ret
gs_eof: LDAI 3
        BR gs_ret
gs_got: LDR R4,GL_SKIP          ; after a SEEK into a sector: its first bytes are not the file's next ones
        MVRLA R4
        BRNZ gs_sk
        MVRHA R4
        BRZ gs_g2
gs_sk:  ADDIW R4,SDATA          ; (the line so far is empty then)
        STR R4,LINEST
        MVIW R4,0
        STR R4,GL_SKIP
gs_g2:  LDR R4,LINEST           ; the limit from the line's start again
        JSR gl_lim
        LDR R4,LINEST
        LDA GL_N
        BRNZ gs_g3
        MOVRR R4,R3             ; (an empty line so far: it starts where the data does)
        BR gs_g4
gs_g3:  MVIW R3,SDATA
gs_g4:  MOVRR R3,R4
        LDAI 2
gs_ret: LDR R5,GL_R5
        LDR R6,GL_R6
        RET

; include (asm.c include): the file named after the line's first word, from the raw line; two levels at most
include: LDR R3,LINEST          ; a 0 after the raw line (the buffer is read again after the INCLUDE)
        MOVRR R3,R4
        LDA LINELEN
        MVAT
        MVRLA R4
        ADDT
        MVARL R4
        MVRHA R4
        ADDIC 0
        MVARH R4
        LDIVR R4,0
        LDTI 32
ic_1:   LDAVR R3                ; the blanks, the first word, the blanks
        BRNEQ ic_2
        INCR R3
        BR ic_1
ic_2:   LDAVR R3
        BRZ ic_3
        BREQ ic_3
        INCR R3
        BR ic_2
ic_3:   LDAVR R3
        BRNEQ ic_4
        INCR R3
        BR ic_3
ic_4:   STR R3,IC_N             ; the name: up to a NUL or a control character
ic_5:   LDAVR R3
        BRZ ic_6
        LDTI 32
        BRLT ic_6
        LDTI 127
        BRGT ic_6
        INCR R3
        BR ic_5
ic_6:   LDIVR R3,0
        LDA FDEP
        LDTI 2
        BRNEQ ic_7
        MVIW R3,S_DEEP
        LDR R4,IC_N
        BR fatal
ic_7:   LDR R3,IC_N
        STR R3,SYSARG0
        LDR R7,SY_OPEN
        JSRUR R7
        LDR R3,SYSRES
        STR R3,IC_H
        MVRLA R3
        BRNZ ic_8
        MVIW R3,S_CANTOPN
        LDR R4,IC_N
        BR fatal
ic_8:   LDA FDEP                ; the outer file: handle, line number, the position of GLP
        SHL
        SHL
        ORI (SFILE).0           ; SFILE + 4*fdep: handle (1), line (2); SPOSN + 4*fdep: the position (3)
        MVIW R5,SFILE
        MVARL R5
        LDA FH+1
        STAVR R5
        INCR R5
        LDA LNUM
        STAVR R5
        INCR R5
        LDA LNUM+1
        STAVR R5
        LDA FDEP
        SHL
        SHL
        ORI (SPOSN).0
        MVIW R5,SPOSN
        MVARL R5
        LDR R3,GLP             ; R3 = GL_END - GLP: the bytes read but not used
        MVRLA R3
        INVA
        MVARL R3
        MVRHA R3
        INVA
        MVARH R3
        INCR R3
        LDR R4,GL_END
        MVRLA R4
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R4
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        LDAI 255                ; the position: NPOS - R3 = NPOS + ~R3 + 1 (24 bits)
        ADDI 1
        MVRLA R3
        INVA
        MVAT
        LDA NPOS+2
        ADDTC
        STA IC_P+2
        MVRHA R3
        INVA
        MVAT
        LDA NPOS+1
        ADDTC
        STA IC_P+1
        LDAI 255
        MVAT
        LDA NPOS
        ADDTC
        STAVR R5
        INCR R5
        LDA IC_P+1
        STAVR R5
        INCR R5
        LDA IC_P+2
        STAVR R5
        LDA FDEP
        ADDI 1
        STA FDEP
        LDR R3,IC_H
        STR R3,FH
        MVIW R3,0
        STR R3,LNUM
        BR gl_new

; popf (asm.c popf): the end of a file. ACC = 1: it was the source; 0: back in the outer file (its position SEEKed)
popf:   LDR R3,FH
        STR R3,SYSARG0
        LDR R7,SY_CLOSE
        JSRUR R7
        LDA FDEP
        BRNZ pf_1
        LDAI 1
        RET
pf_1:   SUBI 1
        STA FDEP
        SHL
        SHL
        ORI (SFILE).0
        MVIW R5,SFILE
        MVARL R5
        LDAI 0
        STA FH
        LDAVR R5
        STA FH+1
        INCR R5
        LDAVR R5
        STA LNUM
        INCR R5
        LDAVR R5
        STA LNUM+1
        JSR gl_new
        LDA FDEP
        SHL
        SHL
        ORI (SPOSN).0
        MVIW R5,SPOSN
        MVARL R5
        LDR R3,FH               ; SEEK(fh, hi, lo); READ starts at the sector's start: NPOS = it, GL_SKIP = the rest
        STR R3,SYSARG0
        LDAI 0
        STA SYSARG1
        STA NPOS+2
        STA GL_SKIP
        LDAVR R5
        STA SYSARG1+1
        STA NPOS
        INCR R5
        LDAVR R5
        STA SYSARG2
        ANDI 0FEH
        STA NPOS+1
        LDAVR R5
        ANDI 1
        STA GL_SKIP
        INCR R5
        LDAVR R5
        STA SYSARG2+1
        STA GL_SKIP+1
        LDR R7,SY_SEEK
        JSRUR R7
        LDAI 0
        RET

; =====================================================================================================================
; The symbol table (asm.c hash, symfind, symset, symget, deflabel). A record: len | 32 when the value is negative
; (its high word 65535), the next record of the chain (0 = none), the value, the name backwards. The chains' heads
; are HEADH[h]:HEADL[h], h = rotl8(h) + c over the name from 0.
; =====================================================================================================================
; symfind: the label R7 (ACC characters) -> R3 = its record, ACC = 1; ACC = 0 none. LASTH = its chain.
symfind: STA SF_N
        MOVRR R7,R4
        MVIW R6,0
        MVARL R5
        BRZ sfh_d
sfh_lp: LDAVR R4
        MVAT
        MVRLA R6
        RSHL
        ADDT
        MVARL R6
        INCR R4
        DECR R5
        MVRLA R5
        BRNZ sfh_lp
sfh_d:  DECR R4                 ; the name's last character
        STR R4,SF_E
        MVRLA R6
        STA LASTH
        MVIW R3,HEADH
        MVARL R3
        LDAVR R3
        MVARH R4
        ADDIW R3,256
        LDAVR R3
        MVARL R4
        LDA SF_N
        MVAT
sf_ch:  MVRHA R4                ; (the records are above $5000: a 0 high byte is the end)
        BRZ sf_no
        LDAVR R4
        ANDI 31
        BREQ sf_cmp
sf_nx:  INCR R4
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        MOVRR R3,R4
        BR sf_ch
sf_no:  LDAI 0
        RET
sf_cmp: MOVRR R4,R5             ; the name, backwards, against the label from its end
        ADDIW R5,5
        LDR R6,SF_E
        LDA SF_N
        MVARL R7
sfc_l:  LDAVR R5
        MVAT
        LDAVR R6
        BRNEQ sfc_no
        INCR R5
        DECR R6
        DECR R7
        MVRLA R7
        BRNZ sfc_l
        MOVRR R4,R3
        LDAI 1
        RET
sfc_no: LDA SF_N
        MVAT
        BR sf_nx

; symget: the value of record R3 -> X (its high word 0 or 65535)
symget: LDAVR R3
        ANDI 32
        BRZ sg_p
        MVIW R4,65535
        BR sg_s
sg_p:   MVIW R4,0
sg_s:   STR R4,X
        ADDIW R3,3
        LDAVR R3
        STA X+2
        INCR R3
        LDAVR R3
        STA X+3
        RET

; symset: record R3's value = X, whose high word must be 0 or 65535
symset: LDA X
        MVAT
        LDA X+1
        BREQ ss_ok              ; the two bytes of the high word equal: 0 or 65535 ...
ss_bad: MVIW R3,S_RANGE
        MVIW R4,0
        BR err
ss_ok:  BRZ ss_z
        LDTI 255
        BRNEQ ss_bad
        LDAVR R3                ; negative
        ORI 32
        BR ss_f
ss_z:   LDAVR R3
        ANDI 31
ss_f:   STAVR R3
        ADDIW R3,3
        LDA X+2
        STAVR R3
        INCR R3
        LDA X+3
        STAVR R3
        RET

; deflabel (asm.c deflabel, pass 1): this line's label = the address
deflabel: MVIW R3,LN            ; ln[n] = 0 (the message's text)
        LDA LLEN
        MVARL R3
        LDIVR R3,0
        MVIW R7,LN
        LDA LLEN
        JSR symfind
        BRZ dl_1
        MVIW R3,S_DUP
        MVIW R4,LN
        BR err
dl_1:   LDA LLEN
        LDTI 30
        BRLT dl_2
        MVIW R3,S_LONG
        MVIW R4,LN
        BR fatal
dl_2:   LDR R3,AHI
        MVRLA R3
        BRNZ dl_past
        MVRHA R3
        BRZ dl_3
dl_past: MVIW R3,S_LPAST
        MVIW R4,LN
        BR fatal
dl_3:   LDR R3,PTOP             ; room for 5 + n bytes below POOLEND?
        MOVRR R3,R4
        ADDIW R4,5
        LDA LLEN
        MVAT
        MVRLA R4
        ADDT
        MVARL R4
        MVRHA R4
        ADDIC 0
        MVARH R4
        LDTI (POOLEND).1
        BRLT dl_4
        BRNEQ dl_full
        MVRLA R4
        BRZ dl_4
dl_full: MVIW R3,S_FULL
        MVIW R4,0
        BR fatal
dl_4:   STR R4,PTOP             ; the record at R3
        STR R3,CURLAB
        LDA LLEN
        STAVR R3
        INCR R3
        MVIW R5,HEADH           ; next = the chain's head; the head = this record
        LDA LASTH
        MVARL R5
        LDAVR R5
        STAVR R3
        LDA CURLAB
        STAVR R5
        ADDIW R5,256
        INCR R3
        LDAVR R5
        STAVR R3
        LDA CURLAB+1
        STAVR R5
        INCR R3
        LDA ALO
        STAVR R3
        INCR R3
        LDA ALO+1
        STAVR R3
        INCR R3
        MVIW R5,LN              ; the name, backwards
        LDA LLEN
        MVARL R5
        MVARL R6
dl_nm:  DECR R5
        LDAVR R5
        STAVR R3
        INCR R3
        DECR R6
        MVRLA R6
        BRNZ dl_nm
        LDR R3,NSYM
        INCR R3
        STR R3,NSYM
        RET

; =====================================================================================================================
; Expressions (asm.c getnum, buildtk, tkend, process, level, apply): RC/asm's token algorithm in 32 bits, the token
; records copied and shifted exactly as there (8 bytes apart here: type 'C'/'N', the character, the value's high
; word, low word; the stale records beyond the count included, which an expression can read).
; =====================================================================================================================
; getnum: the value of the text R3..R5 -> X (0 after an error). The byte at R5 is a 0 meanwhile.
getnum: STR R3,GN_S
        STR R5,GN_E
        LDAVR R5
        STA GN_SV
        LDIVR R5,0
        MOVRR R3,R5
        JSR bt_fast
        LDTI 2
        BRNEQ gn_1
        LDR R5,GN_S             ; a blank inside a token: asm.c's tokenizer, copying
        JSR bt_slow
gn_1:   STA GN_R
        LDR R5,GN_E
        LDA GN_SV
        STAVR R5
        LDA GN_R
        BRNZ gn_0
        LDA TCOUNT              ; one number: its value (the usual case)
        LDTI 1
        BRNEQ gn_gen
        LDA TK
        LDTI 78
        BRNEQ gn_gen
gn_v0:  LDR R3,TK+2
        STR R3,X
        LDR R3,TK+4
        STR R3,X+2
        RET
gn_0:   MVIW R3,0
        STR R3,X
        STR R3,X+2
        RET
gn_gen: LDA TCOUNT              ; ( N ) . 0|1 - y1cc's (label).0 - at once: asm.c's algorithm on these five
        LDTI 5                  ; records leaves record 0 = record 1 with the value, records 1..4 = copies of
        BRNEQ gg_gen            ; the stale record 5 and the count 1; it reports an error only when record 5 is an
        LDA TK                  ; operator of a level ('C' . * / + - & !), which the general path does then
        LDTI 67
        BRNEQ gg_gen
        LDA TK+1
        LDTI 40
        BRNEQ gg_gen
        LDA TK+8
        LDTI 78
        BRNEQ gg_gen
        LDA TK+32
        BRNEQ gg_gen
        LDA TK+16
        LDTI 67
        BRNEQ gg_gen
        LDA TK+24
        BRNEQ gg_gen
        LDA TK+17
        LDTI 41
        BRNEQ gg_gen
        LDA TK+25
        LDTI 46
        BRNEQ gg_gen
        LDA TK+34
        BRNZ gg_gen
        LDA TK+35
        BRNZ gg_gen
        LDA TK+36
        BRNZ gg_gen
        LDA TK+37
        LDTI 2
        BRLT gf_1
        BR gg_gen
gf_1:   LDA TK+40
        LDTI 67
        BRNEQ gf_2
        LDA TK+41
        LDTI 46
        BREQ gg_gen
        LDTI 42
        BREQ gg_gen
        LDTI 47
        BREQ gg_gen
        LDTI 43
        BREQ gg_gen
        LDTI 45
        BREQ gg_gen
        LDTI 38
        BREQ gg_gen
        LDTI 33
        BREQ gg_gen
gf_2:   MVIW R3,TK+32           ; Y = the digit, X = the label's value: X.0 / X.1
        JSR rec2y
        MVIW R3,TK+8
        JSR rec2x
        JSR ap_dot
        MVIW R3,TK+8            ; record 0 = record 1, its value X
        MVIW R4,TK
        LDAI 1
        STA TM_N
        JSR tkmove
        MVIW R3,TK
        JSR x2rec
        MVIW R6,TK+8            ; records 1..4 = record 5
        MVIB R7,4
gf_3:   MVIW R3,TK+40
        MOVRR R6,R4
        JSR tkmove
        ADDIW R6,8
        DECR R7
        MVRLA R7
        BRNZ gf_3
        LDAI 1
        STA TCOUNT
        RET
gg_gen: LDAI 0                  ; the innermost parentheses first: the first ')' and the nearest '(' before it
        STA GI
gg_f1:  LDA TCOUNT
        MVAT
        LDA GI
        BREQ gg_brk
        JSR tkp
        LDAVR R3
        LDTI 67
        BRNEQ gg_f2
        INCR R3
        LDAVR R3
        LDTI 41
        BREQ gg_f3
gg_f2:  LDA GI
        ADDI 1
        STA GI
        BR gg_f1
gg_f3:  LDA GI
        ADDI 1
        STA GJ
gg_f4:  LDA GJ
        BRZ gg_brk
        SUBI 1
        JSR tkp
        LDAVR R3
        LDTI 67
        BRNEQ gg_f5
        INCR R3
        LDAVR R3
        LDTI 40
        BREQ gg_f6
gg_f5:  LDA GJ
        SUBI 1
        STA GJ
        BR gg_f4
gg_f6:  LDA GJ
        SUBI 1
        STA GJ
        LDA GI                  ; tkdel(i, 1); tkdel(j, 1)
        STA TD_I
        LDAI 1
        STA TD_K
        JSR tkdel
        LDA GJ
        STA TD_I
        JSR tkdel
        LDA GJ                  ; process(j, i - 1)
        STA PR_ST
        LDA GI
        SUBI 1
        STA PR_EX
        JSR process
        BRZ gg_gen
        LDAI 0
        STA TCOUNT
gg_brk: LDA TCOUNT
        BRZ gg_bad
        STA PR_EX
        LDAI 0
        STA PR_ST
        JSR process
        BRNZ gg_bad
        LDA TCOUNT
        LDTI 1
        BREQ gn_v0
gg_bad: MVIW R3,S_BADEX
        MVIW R4,0
        JSR err
        BR gn_0

; tkp: record ACC -> R3
tkp:    MVARL R3
        LDAI 0
        MVARH R3
        SHL16 R3
        SHL16 R3
        SHL16 R3
        ADDIW R3,TK
        RET

; tkdel (asm.c tkdel): records i+k.. down to i (up to the count + k, the stale ones included); count -= k
tkdel:  LDA TD_I
        MVAT
        LDA TCOUNT
        BRLT td_z
        BREQ td_z
        SUBT
        STA TM_N
        LDA TD_I
        JSR tkp
        MOVRR R3,R4
        LDA TD_I
        MVAT
        LDA TD_K
        ADDT
        JSR tkp
        JSR tkmove
td_z:   LDA TD_K
        MVAT
        LDA TCOUNT
        SUBT
        STA TCOUNT
        RET
; tkmove: TM_N records from R3 to R4 (upwards; R4 < R3)
tkmove: LDA TM_N
        MVARL R5
tm_lp:  LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        LDAVR R3
        STAVR R4
        ADDIW R3,3
        ADDIW R4,3
        DECR R5
        MVRLA R5
        BRNZ tm_lp
        RET

; process (asm.c process): the operators of records PR_ST..PR_EX; ACC = 1 on an error
process: LDAI 46
        STA LV_A
        STA LV_B
        JSR level
        BRNZ pr_1
        LDAI 42
        STA LV_A
        LDAI 47
        STA LV_B
        JSR level
        BRNZ pr_1
        LDA PR_ST               ; a leading sign: dropped; '-' negates the record at ex
        JSR tkp
        LDAVR R3
        LDTI 67
        BRNEQ pr_2
        INCR R3
        LDAVR R3
        STA PRC
        LDTI 43
        BREQ pr_s
        LDTI 45
        BRNEQ pr_2
pr_s:   ADDIW R3,7              ; p[6]: the next record's type
        LDAVR R3
        LDTI 78
        BRNEQ pr_1
        LDA TCOUNT
        BRZ pr_1
        LDA PR_ST               ; the records st+1..ex one down
        MVAT
        LDA PR_EX
        BRLT pr_m
        BREQ pr_m
        SUBT
        STA TM_N
        LDA PR_ST
        JSR tkp
        MOVRR R3,R4
        ADDIW R3,8
        JSR tkmove
pr_m:   LDA TCOUNT
        SUBI 1
        STA TCOUNT
        LDA PRC
        LDTI 45
        BRNEQ pr_2
        LDA PR_EX
        JSR tkp
        LDAVR R3
        LDTI 78
        BRNEQ pr_c
        STR R3,PR_P             ; a number: negated
        JSR rec2x
        JSR neg32
        LDR R3,PR_P
        JSR x2rec
        BR pr_2
pr_c:   INCR R3                 ; else its character = 256 - it
        LDAVR R3
        INVA
        ADDI 1
        STAVR R3
pr_2:   LDAI 43
        STA LV_A
        LDAI 45
        STA LV_B
        JSR level
        BRNZ pr_1
        LDAI 38
        STA LV_A
        LDAI 33
        STA LV_B
        BR level
pr_1:   LDAI 1
        RET

; rec2x: X = the value of record R3; x2rec: record R3's value = X; rec2y: Y = record R3's value
rec2x:  ADDIW R3,2
        LDAVR R3
        STA X
        INCR R3
        LDAVR R3
        STA X+1
        INCR R3
        LDAVR R3
        STA X+2
        INCR R3
        LDAVR R3
        STA X+3
        RET
x2rec:  ADDIW R3,2
        LDA X
        STAVR R3
        INCR R3
        LDA X+1
        STAVR R3
        INCR R3
        LDA X+2
        STAVR R3
        INCR R3
        LDA X+3
        STAVR R3
        RET
rec2y:  ADDIW R3,2
        LDAVR R3
        STA Y
        INCR R3
        LDAVR R3
        STA Y+1
        INCR R3
        LDAVR R3
        STA Y+2
        INCR R3
        LDAVR R3
        STA Y+3
        RET

; level (asm.c level): the operators LV_A and LV_B in records PR_ST.. below PR_EX, left to right; ACC = 1 on an error
level:  LDA PR_ST
        STA LV_I
lv_lp:  LDA PR_EX
        MVAT
        LDA LV_I
        BRLT lv_1
        LDAI 0
        RET
lv_1:   JSR tkp
        LDAVR R3
        LDTI 67
        BRNEQ lv_nx
        INCR R3
        LDAVR R3
        MVAT
        LDA LV_A
        BREQ lv_op
        LDA LV_B
        BREQ lv_op
lv_nx:  LDA LV_I
        ADDI 1
        STA LV_I
        BR lv_lp
lv_op:  LDA LV_I                ; if (!i || i + 1 == tcount || tcount < 3) return 1
        BRZ lv_e
        ADDI 1
        MVAT
        LDA TCOUNT
        BREQ lv_e
        LDTI 3
        BRLT lv_e
        DECR R3                 ; the records before and after: numbers
        STR R3,LV_P
        ADDIW R3,65528
        LDAVR R3
        LDTI 78
        BRNEQ lv_e
        ADDIW R3,16
        LDAVR R3
        BRNEQ lv_e
        JSR rec2y
        LDR R3,LV_P
        ADDIW R3,65528
        JSR rec2x
        LDR R3,LV_P
        INCR R3
        LDAVR R3
        JSR apply
        BRNZ lv_e
        LDR R3,LV_P
        ADDIW R3,65528
        JSR x2rec
        LDA LV_I
        STA TD_I
        LDAI 2
        STA TD_K
        JSR tkdel
        BR lv_lp
lv_e:   LDAI 1
        RET

; apply (asm.c apply): X = X op Y, op in ACC; ACC = 1 on an error
apply:  LDTI 42
        BREQ ap_mul
        LDTI 43
        BREQ ap_add
        LDTI 45
        BREQ ap_sub
        LDTI 38
        BREQ ap_and
        LDTI 33
        BREQ ap_or
        LDTI 46
        BREQ ap_dot
        JSR div16               ; '/'
        BRZ rts
        LDTI 1
        BRNEQ ap_d2
        MVIW R3,S_DIV0
        BR ap_de
ap_d2:  MVIW R3,S_DIV16
ap_de:  MVIW R4,0
        JSR err
        LDAI 1
        RET
ap_mul: JSR mul32
        LDAI 0
        RET
ap_add: JSR add32
        LDAI 0
        RET
ap_sub: JSR sub32
        LDAI 0
        RET
ap_and: MVIW R3,X
        MVIW R4,Y
        MVIB R5,4
apa_l:  LDAVR R4
        MVAT
        LDAVR R3
        ANDT
        STAVR R3
        INCR R3
        INCR R4
        DECR R5
        MVRLA R5
        BRNZ apa_l
        RET
ap_or:  MVIW R3,X
        MVIW R4,Y
        MVIB R5,4
apo_l:  LDAVR R4
        MVAT
        LDAVR R3
        ORT
        STAVR R3
        INCR R3
        INCR R4
        DECR R5
        MVRLA R5
        BRNZ apo_l
        LDAI 0
        RET
ap_dot: LDA Y                   ; .0 the low byte, .1 x / 256 (C's division, towards 0)
        BRNZ ap_1
        LDA Y+1
        BRNZ ap_1
        LDA Y+2
        BRNZ ap_1
        LDA Y+3
        BRZ ap_d0
        LDTI 1
        BRNEQ ap_1
        LDA X
        ANDI 128
        STA AP_SN
        BRZ ap_d1
        JSR neg32
ap_d1:  LDA X+2
        STA X+3
        LDA X+1
        STA X+2
        LDA X
        STA X+1
        LDAI 0
        STA X
        LDA AP_SN
        BRZ ap_ok
        JSR neg32
ap_ok:  LDAI 0
        RET
ap_d0:  STA X
        STA X+1
        STA X+2
        RET
ap_1:   LDAI 1
        RET

; 32-bit arithmetic on X and Y (4 bytes each, high byte first)
add32:  LDA Y+3
        MVAT
        LDA X+3
        ADDT
        STA X+3
        LDA Y+2
        MVAT
        LDA X+2
        ADDTC
        STA X+2
        LDA Y+1
        MVAT
        LDA X+1
        ADDTC
        STA X+1
        LDA Y
        MVAT
        LDA X
        ADDTC
        STA X
        RET
sub32:  LDAI 255                ; X + ~Y + 1: the carry set first
        ADDI 1
        LDA Y+3
        INVA
        MVAT
        LDA X+3
        ADDTC
        STA X+3
        LDA Y+2
        INVA
        MVAT
        LDA X+2
        ADDTC
        STA X+2
        LDA Y+1
        INVA
        MVAT
        LDA X+1
        ADDTC
        STA X+1
        LDA Y
        INVA
        MVAT
        LDA X
        ADDTC
        STA X
        RET
neg32:  LDA X+3
        INVA
        ADDI 1
        STA X+3
        LDA X+2
        INVA
        ADDIC 0
        STA X+2
        LDA X+1
        INVA
        ADDIC 0
        STA X+1
        LDA X
        INVA
        ADDIC 0
        STA X
        RET
; mul32: X = X * Y mod 2^32 (shift and add; Y is kept)
mul32:  MVIW R3,X               ; MA = X, MB = Y, X = 0
        MVIW R4,MA
        MVIB R5,4
mu_c1:  LDAVR R3
        STAVR R4
        LDIVR R3,0
        INCR R3
        INCR R4
        DECR R5
        MVRLA R5
        BRNZ mu_c1
        LDR R3,Y
        STR R3,MB
        LDR R3,Y+2
        STR R3,MB+2
mu_lp:  LDA MB
        BRNZ mu_1
        LDA MB+1
        BRNZ mu_1
        LDA MB+2
        BRNZ mu_1
        LDA MB+3
        BRZ rts
mu_1:   LDA MB+3
        ANDI 1
        BRZ mu_2
        LDA MA+3                ; X += MA
        MVAT
        LDA X+3
        ADDT
        STA X+3
        LDA MA+2
        MVAT
        LDA X+2
        ADDTC
        STA X+2
        LDA MA+1
        MVAT
        LDA X+1
        ADDTC
        STA X+1
        LDA MA
        MVAT
        LDA X
        ADDTC
        STA X
mu_2:   LDAI 0                  ; MA <<= 1
        CSHL
        LDA MA+3
        CSHL
        STA MA+3
        LDA MA+2
        CSHL
        STA MA+2
        LDA MA+1
        CSHL
        STA MA+1
        LDA MA
        CSHL
        STA MA
        LDAI 0                  ; MB >>= 1
        CSHR
        LDA MB
        CSHR
        STA MB
        LDA MB+1
        CSHR
        STA MB+1
        LDA MB+2
        CSHR
        STA MB+2
        LDA MB+3
        CSHR
        STA MB+3
        BR mu_lp
; div16 (asm.c div16): X = X / Y rounded towards 0; ACC = 0, 1 division by zero, 2 beyond 16 bits
div16:  LDAI 0
        STA AP_SN
        LDA X
        MVAT
        LDA X+1
        ORT
        BRZ dvx_p
        LDA X+1                 ; xh must be 65535 and xl not 0
        MVAT
        LDA X
        ANDT
        LDTI 255
        BRNEQ dx_2
        LDA X+2
        MVAT
        LDA X+3
        ORT
        BRZ dx_2
        JSR neg32
        LDAI 1
        STA AP_SN
dvx_p:  LDA Y
        MVAT
        LDA Y+1
        ORT
        BRZ dvy_p
        LDA Y+1
        MVAT
        LDA Y
        ANDT
        LDTI 255
        BRNEQ dx_2
        LDA Y+2
        MVAT
        LDA Y+3
        ORT
        BRZ dx_2
        LDR R3,Y+2              ; yl = -yl, yh = 0
        MVRLA R3
        INVA
        MVARL R3
        MVRHA R3
        INVA
        MVARH R3
        INCR R3
        STR R3,Y+2
        MVIW R3,0
        STR R3,Y
        LDA AP_SN
        XORI 1
        STA AP_SN
dvy_p:  LDR R4,Y+2
        MVRLA R4
        BRNZ dv_go
        MVRHA R4
        BRNZ dv_go
        LDAI 1
        RET
dx_2:   LDAI 2
        RET
dv_go:  LDR R3,X+2              ; R3 / R4, unsigned: shift and subtract
        MVIW R5,0
        MVIB R6,16
dq_lp:  MVRHA R3
        ANDI 128
        STA DV_B
        SHL16 R3
        SHL16 R5
        LDA DV_B
        BRZ dq_1
        INCR R5
dq_1:   MVRHA R4                ; R5 >= R4?
        MVAT
        MVRHA R5
        BRLT dq_2
        BRGT dq_s
        MVRLA R4
        MVAT
        MVRLA R5
        BRLT dq_2
dq_s:   LDAI 255                ; R5 -= R4
        ADDI 1
        MVRLA R4
        INVA
        MVAT
        MVRLA R5
        ADDTC
        MVARL R5
        MVRHA R4
        INVA
        MVAT
        MVRHA R5
        ADDTC
        MVARH R5
        INCR R3
dq_2:   DECR R6
        MVRLA R6
        BRNZ dq_lp
        STR R3,X+2
        LDA AP_SN
        BRZ ap_ok
        JSR neg32
        LDAI 0
        RET

; ---- the tokenizer (asm.c buildtk, tkend, newtk) -------------------------------------------------------------------
; bt_fast: the text at R5 up to its 0 -> the records, the count; in place. ACC = 0, 1 an error (reported), 2 a
; blank inside a token: bt_slow must do it (it writes the same records from the start).
; TOKC classes: 0 the end, 1 a blank (skipped), 2 a quote, 3 an operator, else the character itself.
bt_fast: LDAI 1
        STA TCOUNT
        MVIW R3,TK
        STR R3,CURP
        MVIW R6,TOKC
bt_out: LDTI 3                  ; between tokens
bto_l:  LDAVR R5
        INCR R5
        MVARL R6
        LDAVR R6
        BRGT bt_tok
        BREQ bt_op
        BRZ bt_end0
        LDTI 1
        BREQ bt_out
        MOVRR R5,R7             ; a quote starts a token
        DECR R7
        BR bt_q
bt_tok: MOVRR R5,R7             ; R7 = the token's start
        DECR R7
bti_l:  LDAVR R5                ; in a token: 5 instructions a character
        INCR R5
        MVARL R6
        LDAVR R6
        BRGT bti_l
        BREQ bt_opt
        BRZ bt_endt
        LDTI 1
        BREQ bt_frag
bt_q:   MOVRR R5,R3             ; a quote: the token goes on to the same quote (or the end)
        DECR R3
        LDAVR R3
        MVAT
btq_l:  LDAVR R5
        INCR R5
        BREQ bt_qc
        BRNZ btq_l
bt_endt: DECR R5                ; the end: the token [R7, R5), no newtk
        JSR bt_len
        BR tk_end
bt_end0: LDA TCOUNT             ; the end, no token: tcount--
        SUBI 1
        STA TCOUNT
        LDAI 0
        RET
bt_frag: LDAI 2
        RET
bt_qc:  JSR bt_tkn              ; the closing quote ends the token
        BRNZ bt_err
        BR bt_out
bt_opt: DECR R5                 ; an operator ends the token
        JSR bt_tkn
        BRNZ bt_err
        INCR R5
bt_op:  MOVRR R5,R3             ; the operator: a token of its own
        DECR R3
        LDAVR R3
        LDR R4,CURP
        LDIVR R4,67
        INCR R4
        STAVR R4
        LDTI 36
        BRNEQ bt_op2
        DECR R4                 ; '$': the address
        LDIVR R4,78
        ADDIW R4,2
        LDA AHI
        STAVR R4
        INCR R4
        LDA AHI+1
        STAVR R4
        INCR R4
        LDA ALO
        STAVR R4
        INCR R4
        LDA ALO+1
        STAVR R4
bt_op2: STR R5,BT_R5
        JSR newtk
        BRNZ bt_err
        LDR R5,BT_R5
        MVIW R6,TOKC
        BR bt_out
bt_err: LDAI 1
        RET
; bt_tkn: tkend the token [R7, R5), then newtk; ACC = 1 on an error (R5, R6 kept)
bt_tkn: STR R5,BT_R5
        JSR bt_len
        JSR tk_end
        BRNZ bt_tk1
        JSR newtk
bt_tk1: LDR R5,BT_R5
        MVIW R6,TOKC
        RET
bt_len: MVRLA R7                ; ACC = R5 - R7 (both in LN)
        MVAT
        MVRLA R5
        SUBT
        RET
; newtk (asm.c newtk): the next record; ACC = 1 after 45
newtk:  LDR R3,CURP
        ADDIW R3,8
        STR R3,CURP
        LDA TCOUNT
        ADDI 1
        STA TCOUNT
        LDTI 46
        BRLT rt0
        MVIW R3,S_EXLONG
        MVIW R4,0
        JSR err
        LDAI 1
        RET
rt0:    LDAI 0
        RET

; bt_slow (asm.c buildtk): the text at R5 up to its 0, each token copied to TBUF; ACC = 0, 1 an error
bt_slow: LDAI 1
        STA TCOUNT
        MVIW R3,TK
        STR R3,CURP
        LDAI 0
        STA BS_TL
        STA BSQ
bs_lp:  LDAVR R5
        BRZ bs_end
        INCR R5
        STA BS_C
        STR R5,BS_R5
        LDA BSQ
        BRZ bs_nq
        LDA BS_C                ; in quotes: every character
        JSR addc
        BRNZ bt_err
        LDA BSQ
        MVAT
        LDA BS_C
        BRNEQ bs_nx
        LDAI 0
        STA BSQ
        JSR bs_tk
        BRNZ bt_err
        BR bs_nx
bs_nq:  LDA BS_C
        LDTI 34
        BREQ bs_q
        LDTI 39
        BRNEQ bs_2
bs_q:   STA BSQ
        JSR addc
        BRNZ bt_err
        BR bs_nx
bs_2:   MVIW R6,TOKC
        MVARL R6
        LDAVR R6
        LDTI 3
        BRNEQ bs_3
        LDA BS_TL               ; an operator
        BRZ bs_o
        JSR bs_tk
        BRNZ bt_err
bs_o:   LDA BS_C
        JSR addc
        JSR bs_tk
        BRNZ bt_err
        BR bs_nx
bs_3:   LDTI 1
        BREQ bs_nx              ; a blank: skipped
        LDA BS_C
        JSR addc
        BRNZ bt_err
bs_nx:  LDR R5,BS_R5
        BR bs_lp
bs_end: LDA BS_TL
        BRZ bt_end0
        MVIW R7,TBUF
        BR tk_end
bs_tk:  MVIW R7,TBUF            ; tkend(), newtk()
        LDA BS_TL
        JSR tk_end
        BRNZ rts
        LDAI 0
        STA BS_TL
        BR newtk
; addc (asm.c addc): ACC -> TBUF; ACC = 1 after 32 characters
addc:   STA BS_A
        LDA BS_TL
        LDTI 32
        BRLT ad_ok
        MVIW R3,S_TKLONG
        MVIW R4,0
        JSR err
        LDAI 1
        RET
ad_ok:  ORI (TBUF).0             ; (TBUF is 64-aligned)
        MVIW R3,TBUF
        MVARL R3
        LDA BS_A
        STAVR R3
        LDA BS_TL
        ADDI 1
        STA BS_TL
        LDAI 0
        RET

; tk_end (asm.c tkend): the token R7, ACC characters -> the record at CURP. ACC = 1: over 32 characters (reported)
tk_end: STA TK_LEN
        STR R7,TK_PTR
        LDTI 33
        BRLT tke_ok
        MVIW R3,S_TKLONG
        MVIW R4,0
        JSR err
        LDAI 1
        RET
tke_ok: LDR R3,CURP
        LDIVR R3,67
        INCR R3
        LDAVR R7
        STAVR R3
        STA TK_C
        MVIW R3,0
        STR R3,X
        STR R3,X+2
        LDTI 39
        BREQ tke_q
        LDTI 34
        BREQ tke_q
        ORI 32
        LDTI 97
        BRLT tke_nl
        LDTI 123
        BRLT tke_lab
tke_nl: LDA TK_C
        LDTI 48
        BRLT tke_ns
        BR tke_num
tke_ns: LDTI 36
        BRNEQ rt0
        LDR R3,AHI              ; '$': the address
        STR R3,X
        LDR R3,ALO
        STR R3,X+2
tke_n:  LDR R3,CURP             ; the record is a number
        LDIVR R3,78
        JSR x2rec
        LDAI 0
        RET
tke_q:  LDA TK_LEN              ; a quoted character, signed
        LDTI 2
        BRLT tke_n
        INCR R7
        LDAVR R7
        STA X+3
        ANDI 128
        BRZ tke_n
        LDAI 255
        STA X
        STA X+1
        STA X+2
        BR tke_n
tke_lab: LDA TK_LEN             ; a label: its value; 1 in pass 1 when not (yet) defined
        LDTI 30
        BRLT tkl_f
        BR tkl_nf
tkl_f:  JSR symfind
        BRZ tkl_nf
        JSR symget
        BR tke_n
tkl_nf: LDA PASS
        LDTI 1
        BRNEQ tkl_u
        LDAI 1
        STA X+3
        BR tke_n
tkl_u:  LDR R3,TK_PTR           ; undefined: the message names it
        MVIW R4,TBUFE
        LDA TK_LEN
        MVARL R5
tku_l:  LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        DECR R5
        MVRLA R5
        BRNZ tku_l
        LDIVR R4,0
        MVIW R3,S_UNDEF
        MVIW R4,TBUFE
        JSR err
        BR tke_n
tke_num: LDR R4,TK_PTR          ; a number: hex when an H is anywhere in it (every hex digit counts), else atoi
        LDA TK_LEN
        MVARL R5
        LDAI 0
        STA TK_H
tkh_l:  LDAVR R4
        ORI 32
        LDTI 104
        BRNEQ tkh_n
        LDAI 1
        STA TK_H
tkh_n:  INCR R4
        DECR R5
        MVRLA R5
        BRNZ tkh_l
        LDR R4,TK_PTR
        LDA TK_LEN
        STA TK_CNT
        MVIW R3,0               ; R3 = the low word while the high word is 0 and it stays below 4096
tkd_l:  LDAVR R4
        LDTI 48
        BRLT tkd_nd
        LDTI 58
        BRLT tkd_dd
tkd_nd: LDA TK_H
        BRZ tkd_e
        LDAVR R4
        ORI 32
        LDTI 97
        BRLT tkd_nx
        LDTI 103
        BRLT tkd_hx
        BR tkd_nx
tkd_hx: SUBI 87
        STA TK_D
        LDAI 16
        BR tkd_dg
tkd_dd: SUBI 48
        STA TK_D
        LDA TK_H
        BRZ tkd_10
        LDAI 16
        BR tkd_dg
tkd_10: LDAI 10
tkd_dg: STA TK_B                ; digit(base, d): x = x * base + d
        LDA X
        BRNZ tkd_sl
        LDA X+1
        BRNZ tkd_sl
        MVRHA R3
        LDTI 16
        BRLT tkd_fa
tkd_sl: STR R3,X+2              ; beyond 4095: 32 bits
        STR R4,TK_R4
        MVIW R3,0
        STR R3,Y
        LDA TK_B
        MVARL R3
        STR R3,Y+2
        JSR mul32
        MVIW R3,0
        STR R3,Y
        LDA TK_D
        MVARL R3
        STR R3,Y+2
        JSR add32
        LDR R3,X+2
        LDR R4,TK_R4
        BR tkd_nx
tkd_fa: LDA TK_B
        LDTI 16
        BREQ tkd_16
        SHL16 R3                ; x * 10 = x * 8 + x * 2
        MOVRR R3,R7
        SHL16 R3
        SHL16 R3
        MVRLA R7
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R7
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        BR tkd_ad
tkd_16: SHL16 R3
        SHL16 R3
        SHL16 R3
        SHL16 R3
tkd_ad: LDA TK_D
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
tkd_nx: INCR R4
        LDA TK_CNT
        SUBI 1
        STA TK_CNT
        BRNZ tkd_l
tkd_e:  STR R3,X+2
        BR tke_n

; =====================================================================================================================
; The instruction (asm.c asmcmd, match, clsmatch, inrange, run, listout, equ): the mnemonic's chain in the
; generated table, its patterns in the .def's order, the first that matches is done.
; =====================================================================================================================
asmcmd: LDR R5,CMD
        LDAVR R5
        BRZ rts
        MVIW R6,TOKC            ; the first word (up to a blank or the end), hashed
        MVIB R7,OT_SEED
mn_lp:  LDAVR R5
        MVAT
        MVARL R6
        LDAVR R6
        ANDI 0FEH
        BRZ mn_e
        MVRLA R7
        RSHL
        ADDT
        MVARL R7
        INCR R5
        BR mn_lp
mn_e:   STR R5,AC_S
        LDA CMD+1
        MVAT
        MVRLA R5
        SUBT
        STA AC_N
        MVRLA R7                ; OT_HEAD[h & 63]
        ANDI 63
        SHL
        MVAT
        MVIW R3,OT_HEAD
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        LDAVR R3
        MVARH R4
        INCR R3
        LDAVR R3
        MVARL R4
        LDA AC_N
        MVAT
mn_ch:  MVRHA R4                ; the records: len, next, the name
        BRZ mn_no
        LDAVR R4
        BREQ mn_cmp
mn_nx:  INCR R4
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        MOVRR R3,R4
        BR mn_ch
mn_cmp: MOVRR R4,R3             ; the same length: the names up to the first difference; the record's 127 there
        ADDIW R3,3              ; (after its name) and a blank in the text (after the mnemonic) is the match
        LDR R5,CMD
mnc_l:  LDAVR R3
        MVAT
        LDAVR R5
        BRNEQ mnc_x
        INCR R3
        INCR R5
        BR mnc_l
mnc_x:  LDAVR R3
        LDTI 127
        BRNEQ mnc_no
        INCR R3
        LDAVR R3                ; the patterns
        STA AC_NP
        INCR R3
mp_lp:  LDA AC_NP
        BRZ mn_no
        STR R3,AC_PAT
        MOVRR R3,R4
        LDR R5,AC_S
        JSR match
        BRNZ mp_run
        LDR R3,AC_PAT           ; the next pattern: past the shape's 0, the operations
mp_s1:  LDAVR R3
        INCR R3
        BRNZ mp_s1
        LDAVR R3
        INCR R3
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        LDA AC_NP
        SUBI 1
        STA AC_NP
        BR mp_lp
mp_run: LDR R4,MAEND           ; the operations: their number, then them
        LDAVR R4
        INCR R4
        BR run
mnc_no: LDA AC_N
        MVAT
        BR mn_nx
mn_no:  LDR R5,CMD              ; ENDM: not supported; else, in pass 2, an invalid instruction
        MVIW R4,S_ENDM
        JSR pfx
        BRZ mn_inv
        LDAVR R5
        BRNZ mn_inv
        MVIW R3,S_NOTSUP
        MVIW R4,0
        BR err
mn_inv: LDA PASS
        LDTI 2
        BRNEQ rts
        MVIW R3,S_INVAL
        MVIW R4,0
        BR err

; match (asm.c match): the operand shape R4 against the text R5 (after the first word). ACC = 1: it matches, AV holds
; its arguments (4 bytes each: high word, low word), MAEND -> the pattern's operations; 0: it does not.
match:  MVIW R3,AV
        STR R3,AP
ma_lp:  LDAVR R4
        INCR R4
        BRZ ma_end
        LDTI 1
        BREQ ma_ws
        LDTI 8
        BRLT ma_num
        LDTI 16
        BRLT ma_cls
        MVAT                    ; a character, literally
        LDAVR R5
        INCR R5
        BREQ ma_lp
ma_no:  LDAI 0
        RET
ma_end: STR R4,MAEND
        LDAVR R5
        BRNZ ma_no
        LDAI 1
        RET
ma_ws:  MVIW R6,TOKC            ; white space: one or more (not the end)
        LDAVR R5
        MVARL R6
        LDAVR R6
        LDTI 1
        BRNEQ ma_no
maw_l:  INCR R5
        LDAVR R5
        MVARL R6
        LDAVR R6
        BREQ maw_l
        BR ma_lp
ma_cls: SUBI 8                  ; a class: the first of its names the text starts with (clsmatch)
        SHL
        MVAT
        MVIW R3,OT_CLS
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        LDAVR R3
        MVARH R6
        INCR R3
        LDAVR R3
        MVARL R6
        MOVRR R6,R3
        LDAVR R3
        INCR R3
        BRZ mc_ent
        LDAVR R3                ; direct (tools/gen_y1_optab.py): the first character, then by the second
        MVAT
        LDAVR R5
        BRNEQ ma_no
        INCR R3
        LDAVR R3
        MVAT
        INCR R5
        LDAVR R5
        SUBT                    ; k = the second character - the lowest
        MVAT
        INCR R3
        LDAVR R3                ; k < n
        BRGT mcd_in
        LDAI 0
        RET
mcd_in: INCR R3
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        LDAVR R3
        LDTI 255
        BREQ ma_no
        INCR R5
        LDR R6,AP
        LDIVR R6,0
        INCR R6
        LDIVR R6,0
        INCR R6
        LDIVR R6,0
        INCR R6
        STAVR R6
        INCR R6
        STR R6,AP
        BR ma_lp
mc_ent: LDAVR R3                ; linear: len name value ...; 0
        BRZ ma_no
        MVARL R7
        INCR R3
        MOVRR R5,R6
mc_c:   LDAVR R3
        MVAT
        LDAVR R6
        BRNEQ mc_sk
        INCR R3
        INCR R6
        DECR R7
        MVRLA R7
        BRNZ mc_c
        MOVRR R6,R5             ; it is this one: the value
        LDR R6,AP
        LDIVR R6,0
        INCR R6
        LDIVR R6,0
        INCR R6
        LDIVR R6,0
        INCR R6
        LDAVR R3
        STAVR R6
        INCR R6
        STR R6,AP
        BR ma_lp
mc_sk:  INCR R3                 ; the rest of the name, the value
        DECR R7
        MVRLA R7
        BRNZ mc_sk
        INCR R3
        BR mc_ent
ma_num: LDTI 6
        BRLT ma_bw
        STR R5,LISTP            ; \L, \M: the rest of the line
mal_l:  LDAVR R5
        BRZ mal_e
        INCR R5
        BR mal_l
mal_e:  LDR R3,AP
        ADDIW R3,4
        STR R3,AP
        BR ma_lp
ma_bw:  STA MA_B                ; \B, \W: up to a ',' or ' ' outside quotes
        STR R4,MA_P
        MOVRR R5,R3
        LDTI 44
mab_l:  LDAVR R5
        INCR R5
        BRGT mab_l
        DECR R5
        BRZ mab_e
        BREQ mab_e
        LDTI 32
        BREQ mab_e
        LDTI 34
        BREQ mab_q
        LDTI 39
        BREQ mab_q
        INCR R5
        LDTI 44
        BR mab_l
mab_q:  STA MA_Q                ; in quotes: to the same quote (the other one takes over)
        INCR R5
mabq_l: LDAVR R5
        BRZ mab_e
        INCR R5
        LDTI 34
        BREQ mab_qq
        LDTI 39
        BRNEQ mabq_l
mab_qq: MVAT
        LDA MA_Q
        BREQ mab_q0
        MVTA
        STA MA_Q
        BR mabq_l
mab_q0: LDTI 44
        BR mab_l
mab_e:  MVRLA R3                ; nothing: no match
        MVAT
        MVRLA R5
        BREQ ma_no
        STR R5,MA_D
        JSR getnum
        LDA X                   ; inrange: RC/asm's abs((int)v) < 256 (\B) or 65536 (\W)
        MVAT
        LDA X+1
        BRNEQ ir_x
        BRZ ir_p
        LDTI 255
        BRNEQ ir_x
        LDA MA_B                ; high word 65535
        LDTI 4
        BRNEQ ir_nw
        LDA X+2                 ; \B: xl > 65280
        LDTI 255
        BRNEQ ma_no
        LDA X+3
        BRZ ma_no
        BR ma_arg
ir_nw:  LDA X+2                 ; \W: xl != 0
        MVAT
        LDA X+3
        ORT
        BRZ ma_no
        BR ma_arg
ir_p:   LDA MA_B                ; high word 0: \B xl < 256
        LDTI 4
        BRNEQ ma_arg
        LDA X+2
        BRNZ ma_no
        BR ma_arg
ir_x:   LDA X                   ; else only 32768:0 (abs(INT_MIN) is negative)
        LDTI 128
        BRNEQ ma_no
        LDA X+1
        BRNZ ma_no
        LDA X+2
        BRNZ ma_no
        LDA X+3
        BRNZ ma_no
ma_arg: LDR R6,AP               ; putarg
        LDA X
        STAVR R6
        INCR R6
        LDA X+1
        STAVR R6
        INCR R6
        LDA X+2
        STAVR R6
        INCR R6
        LDA X+3
        STAVR R6
        INCR R6
        STR R6,AP
        LDR R4,MA_P
        LDR R5,MA_D
        BR ma_lp

; run (asm.c run): the ACC operations at R4 (tools/gen_y1_optab.py). R4 = the next operation, R5 = how many are left,
; R6 = B (the byte being built); wbyte keeps R4..R6, the rarer operations save them.
run:    MVARL R5
        MVIB R6,0
ru_lp:  MVRLA R5
        BRZ rts
        DECR R5
        LDAVR R4
        INCR R4
        LDTI 1
        BREQ ru_out
        LDTI 208
        BREQ ru_lit
        STA RO
        ANDI 0F0H
        LDTI 64
        BREQ ru_or
        LDTI 32
        BREQ ru_arg
        LDTI 48
        BREQ ru_hi
        LDTI 16
        BREQ ru_dg
        LDTI 80
        BREQ ru_or4
        LDTI 96
        BREQ ru_and
        PUSHR R4                ; the directives: R4..R6 saved
        PUSHR R5
        PUSHR R6
        JSR ru_dir
        POPR R6
        POPR R5
        POPR R4
        BR ru_lp
ru_out: MVRLA R6                ; write B
        JSR wbyte
        MVIB R6,0
        BR ru_lp
ru_lit: LDAVR R4                ; B = n
        MVARL R6
        INCR R4
        DECR R5
        BR ru_lp
ru_arg: JSR ru_av               ; B = lo(n)
        LDAVR R3
        MVARL R6
        BR ru_lp
ru_hi:  JSR ru_av               ; B = hi(n)
        DECR R3
        LDAVR R3
        MVARL R6
        BR ru_lp
ru_or:  JSR ru_av               ; B |= n
        LDAVR R3
        MVAT
        MVRLA R6
        ORT
        MVARL R6
        BR ru_lp
ru_or4: JSR ru_av               ; B |= n << 4
        LDAVR R3
        SHL
        SHL
        SHL
        SHL
        MVAT
        MVRLA R6
        ORT
        MVARL R6
        BR ru_lp
ru_dg:  MVRLA R6                ; B = B * 16 + d
        SHL
        SHL
        SHL
        SHL
        MVAT
        LDA RO
        ANDI 15
        ORT
        MVARL R6
        BR ru_lp
ru_and: LDAVR R4                ; B &= m
        INCR R4
        DECR R5
        MVAT
        MVRLA R6
        ANDT
        MVARL R6
        BR ru_lp
; ru_av: R3 -> the low byte of the operation's argument in AV (16-aligned)
ru_av:  LDA RO
        ANDI 3
        SHL
        SHL
        ORI (AV).0+3
        MVIW R3,AV
        MVARL R3
        RET
; ru_dir: the directives and the DB/DW lists (R5 -> the argument's first byte)
ru_dir: JSR ru_av
        MOVRR R3,R5
        DECR R5
        DECR R5
        DECR R5
        LDA RO
        ANDI 0F0H
        LDTI 112
        BREQ ru_lst
        LDTI 128
        BREQ ru_org
        LDTI 144
        BREQ ru_ds
        LDTI 160
        BREQ ru_end
        LDTI 176
        BREQ ru_equ
        MVIW R3,S_NOTSUP        ; PUBLIC, EXTERN, LIB
        MVIW R4,0
        BR err
ru_lst: LDA RO                  ; the DB (0) / DW (8) list
        ANDI 8
        BR listout
ru_org: LDAVR R5                ; ORG
        STA AHI
        INCR R5
        LDAVR R5
        STA AHI+1
        INCR R5
        LDAVR R5
        STA ALO
        INCR R5
        LDAVR R5
        STA ALO+1
        BR flush
ru_ds:  MOVRR R5,R3             ; DS: the address + n (32 bits)
        DECR R3
        DECR R3
        JSR rec2y
        LDR R3,AHI
        STR R3,X
        LDR R3,ALO
        STR R3,X+2
        JSR add32
        LDR R3,X
        STR R3,AHI
        LDR R3,X+2
        STR R3,ALO
        BR flush
ru_end: INCR R5                 ; END: the start address
        INCR R5
        LDAVR R5
        STA STARTA
        INCR R5
        LDAVR R5
        STA STARTA+1
        LDAI 1
        STA SSET
        RET
ru_equ: MOVRR R5,R3             ; EQU
        DECR R3
        DECR R3
        JSR rec2x
        BR equ

; equ (asm.c equ): this line's label = X
equ:    LDA PASS
        LDTI 1
        BRNEQ eq_2
        LDR R3,CURLAB
        MVRHA R3
        BRNZ symset
        RET
eq_2:   LDA LLEN
        BRNZ eq_3
        MVIW R3,S_NOLAB
        MVIW R4,0
        BR err
eq_3:   MVIW R7,LN
        JSR symfind
        BRNZ symset
        RET

; listout (asm.c listout): the DB (ACC = 0) / DW (8) items of LISTP: "text", 'text' or an expression each
listout: STA LO_W
        LDR R3,LISTP
        STR R3,LO_S
lo_lp:  LDR R5,LO_S             ; t = the item's end: a ',' outside quotes, or the end
        LDAI 0
        STA LO_Q
lot_l:  LDAVR R5
        BRZ lot_e
        MVAT
        LDA LO_Q
        BRZ lot_nq
        BRNEQ lot_n
        LDAI 0
        STA LO_Q
        BR lot_n
lot_nq: MVTA
        LDTI 44
        BREQ lot_e
        LDTI 34
        BREQ lot_q
        LDTI 39
        BRNEQ lot_n
lot_q:  STA LO_Q
lot_n:  INCR R5
        BR lot_l
lot_e:  STR R5,LO_T
        LDR R3,LO_S
        MVRLA R3
        MVAT
        MVRLA R5
        BREQ lo_nx              ; an empty item: nothing
        LDAVR R3
        LDTI 34
        BREQ lo_str
        LDTI 39
        BREQ lo_str
        JSR getnum              ; an expression: its low byte (DW: high, low)
        LDA LO_W
        BRZ lo_b
        LDA X+2
        JSR wbyte
lo_b:   LDA X+3
        JSR wbyte
        BR lo_nx
lo_str: STA LO_Q                ; a string: to the same quote or the item's end
        INCR R3
los_l:  STR R3,LO_S
        LDR R4,LO_T
        MVRLA R3
        MVAT
        MVRLA R4
        BREQ lo_nx
        LDAVR R3
        MVAT
        LDA LO_Q
        BREQ lo_nx
        LDA LO_W
        BRZ los_b
        LDAVR R3                ; DW: 255 before a byte over 127, else 0
        ANDI 128
        BRZ los_w
        LDAI 255
los_w:  JSR wbyte
los_b:  LDR R3,LO_S
        LDAVR R3
        JSR wbyte
        LDR R3,LO_S
        INCR R3
        BR los_l
lo_nx:  LDR R5,LO_T             ; the next item
        LDAVR R5
        BRZ rts
        INCR R5
        STR R5,LO_S
        BR lo_lp

; =====================================================================================================================
; The output (asm.c wbyte, oput, flush, ohexb): the program file from the first address to the last (gaps zero), or
; Intel hex (16-byte records, a new one at ORG and DS). oput preserves R3..R6.
; =====================================================================================================================
wbyte:  STA WB_B                ; (keeps R4..R6)
        LDA PASS
        LDTI 2
        BRNEQ wb_p1
        LDA AHI
        BRNZ wb_hi
        LDA AHI+1
        BRNZ wb_hi
        LDR R3,NBYTES
        INCR R3
        STR R3,NBYTES
        LDA HEXO
        BRZ wb_prg
        LDA OCNT                ; orow[ocnt++] = b (OROW is 16-aligned)
        ORI (OROW).0
        MVIW R3,OROW
        MVARL R3
        LDA WB_B
        STAVR R3
        LDA OCNT
        ADDI 1
        STA OCNT
        BR wb_adv
wb_prg: LDR R3,ALO              ; the program file: the byte goes out when it is the next one
        LDR R7,FPOS
        MVRLA R7
        MVAT
        MVRLA R3
        BRNEQ wb_sl
        MVRHA R7
        MVAT
        MVRHA R3
        BRNEQ wb_sl
        LDA WB_B
        JSR oput
        INCR R3
        STR R3,FPOS
        BR wb_adv
wb_sl:  PUSHR R4                ; else: alo < fpos is an error, a gap is zeros
        PUSHR R5
        PUSHR R6
        JSR wb_gap
        POPR R6
        POPR R5
        POPR R4
        BR wb_adv
wb_hi:  PUSHR R4
        PUSHR R5
        PUSHR R6
        MVIW R3,S_CPAST
        MVIW R4,0
        JSR err
        POPR R6
        POPR R5
        POPR R4
        RET
wb_gap: LDR R4,FPOS
        MVRHA R4
        MVAT
        MVRHA R3
        BRLT wb_dn
        BRGT wb_g1
        MVRLA R4
        MVAT
        MVRLA R3
        BRLT wb_dn
wb_g1:  LDAI 0
        JSR oput
        INCR R4
        MVRLA R4
        MVAT
        MVRLA R3
        BRNEQ wb_g1
        MVRHA R4
        MVAT
        MVRHA R3
        BRNEQ wb_g1
        LDA WB_B
        JSR oput
        INCR R4
        STR R4,FPOS
        RET
wb_dn:  MVIW R3,S_DOWN
        MVIW R4,0
        BR err
wb_p1:  LDA FSET                ; pass 1: the first byte's address
        BRNZ wb_adv
        LDR R3,ALO
        STR R3,FIRST
        LDAI 1
        STA FSET
wb_adv: LDR R3,ALO              ; the address + 1 (32 bits)
        INCR R3
        STR R3,ALO
        MVRLA R3
        BRNZ wb_16
        MVRHA R3
        BRNZ wb_16
        LDR R3,AHI
        INCR R3
        STR R3,AHI
wb_16:  LDA OCNT
        LDTI 16
        BRNEQ rts
; flush (asm.c flush, pass 2 with -h): the pending record (keeps R4..R6)
flush:  LDA PASS
        LDTI 2
        BRNEQ rts
        LDA HEXO
        BRZ rts
        LDA OCNT
        BRZ fl_z
        PUSHR R4
        LDAI 58
        JSR oput
        LDA OCNT
        JSR ohexb
        LDA OADDR
        JSR ohexb
        LDA OADDR+1
        JSR ohexb
        LDAI 0
        JSR ohexb
        LDA OCNT                ; the checksum: 0 - (count + address + its high byte + the bytes)
        MVAT
        LDA OADDR
        ADDT
        MVAT
        LDA OADDR+1
        ADDT
        STA FL_CK
        MVIW R3,OROW
        LDA OCNT
        MVARL R4
fl_lp:  LDAVR R3
        JSR ohexb
        LDAVR R3
        MVAT
        LDA FL_CK
        ADDT
        STA FL_CK
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ fl_lp
        LDA FL_CK
        INVA
        ADDI 1
        JSR ohexb
        LDAI 10
        JSR oput
        POPR R4
fl_z:   LDAI 0
        STA OCNT
        LDR R3,ALO
        STR R3,OADDR
        RET
; ohexb: ACC as two lower-case hex digits (preserves R3..R6)
ohexb:  STA OX_H
        SHR
        SHR
        SHR
        SHR
        JSR hexd
        JSR oput
        LDA OX_H
        ANDI 15
        JSR hexd
; oput: ACC -> the output; a full 64 bytes are written (preserves R3..R6)
oput:   LDR R7,OPTR
        STAVR R7
        INCR R7
        STR R7,OPTR
        MVRLA R7
        ANDI 63
        BRNZ rts
; owrite: the buffer (OPTR - OBUF bytes) written; a short write is fatal (preserves R3..R6)
owrite: PUSHR R3
        PUSHR R4
        PUSHR R5
        PUSHR R6
        LDR R3,OPTR
        ADDIW R3,65535-OBUF+1   ; the byte count: OPTR - OBUF
        STR R3,OW_N
        STR R3,SYSARG2
        LDR R3,OH
        STR R3,SYSARG0
        MVIW R3,OBUF
        STR R3,SYSARG1
        STR R3,OPTR
        LDR R7,SY_WRITE
        JSRUR R7
        LDR R3,SYSRES
        LDR R4,OW_N
        MVRLA R3
        MVAT
        MVRLA R4
        BRNEQ ow_f
        MVRHA R3
        MVAT
        MVRHA R4
        BREQ ow_r
ow_f:   MVIW R3,S_WFAIL
        MVIW R4,0
        JSR fatal
ow_r:   POPR R6
        POPR R5
        POPR R4
        POPR R3
        RET

; =====================================================================================================================
; The messages (single quotes: the assembler keeps their case) and the instruction table
; =====================================================================================================================
S_USAGE:    DB 'usage: asm [-h] SRC [OUT]',0
S_DOTASM:   DB '.ASM',0
S_DOTIMG:   DB '.IMG',0
S_CANTOPEN: DB 'asm: '
S_CANTOPN:  DB 'cannot open ',0
S_CANTMAKE: DB 'asm: cannot create ',0
S_ENDREC:   DB ':00000001ff',10,0
S_ASM:      DB 'asm: ',0
S_INCSP:    DB 'INCLUDE ',0
S_COLSP:    DB ': ',0
S_NLSP:     DB 10,'  ',0
S_ERROR:    DB ' error',0
S_ERRORS:   DB ' errors',0
S_NO:       DB ', no ',0
S_BYTES:    DB ' bytes, ',0
S_LABELS:   DB ' labels',0
S_LOAD:     DB ', load ',0
S_EXEC:     DB ' exec ',0
S_INCL:     DB 'INCLUDE',0
S_MACRO:    DB 'MACRO',0
S_ENDM:     DB 'ENDM',0
S_NOTSUP:   DB 'not supported',0
S_INVAL:    DB 'invalid instruction',0
S_UNDEF:    DB 'undefined label',0
S_DUP:      DB 'duplicate label',0
S_LONG:     DB 'label over 29 characters',0
S_LPAST:    DB 'label past $FFFF',0
S_FULL:     DB 'symbol table full',0
S_RANGE:    DB 'value out of range',0
S_EXLONG:   DB 'expression too long',0
S_TKLONG:   DB 'token too long',0
S_DIV0:     DB 'division by zero',0
S_DIV16:    DB 39,'/',39,' beyond 16 bits',0
S_BADEX:    DB 'bad expression',0
S_WFAIL:    DB 'write failed (disk full, or 16M)',0
S_CPAST:    DB 'code past $FFFF',0
S_DOWN:     DB 'addresses go down: use -h',0
S_NOLAB:    DB 'no label',0
S_DEEP:     DB 'INCLUDE too deep',0

        INCLUDE asmtab.inc

; =====================================================================================================================
; The data (not in the program file). The page-aligned tables and buffers are at fixed addresses at the top of the
; program area ($C400-$CFFF, below it the symbol table); the other variables follow the code (DS), and the symbol
; table (POOL) grows from there up to POOLEND. init zeroes ZBEG..ZEND, HEADH/HEADL and $CD10-$CFFF, and builds XL0,
; XL1 and TOKC.
; =====================================================================================================================
XL0:    EQU 0C400H              ; c -> c upper-cased; 0 for NUL, LF, quotes, ':' and ';' (an even page: XL1 = XL0 ^ 256)
XL1:    EQU 0C500H              ; the same inside single quotes, no upper case
TOKC:   EQU 0C600H              ; the tokenizer's classes (bt_fast); also isws: < 2
HEADH:  EQU 0C700H              ; the label chains: the high bytes of the first record
HEADL:  EQU 0C800H              ;   the low bytes
LN:     EQU 0C900H              ; the line (asm.c ln)
SPRE:   EQU 0CA00H              ; the source buffer: the start of a line moved down
SDATA:  EQU 0CB00H              ;   what READN read (512)
SSENT:  EQU 0CD00H              ;   the sentinel after a full sector
AV:     EQU 0CD10H              ; the arguments matched (4 of 4 bytes: high word, low word); 16-aligned
OROW:   EQU 0CD20H              ; the Intel-hex record being built; 16-aligned
SFILE:  EQU 0CD30H              ; INCLUDE: the outer files' handle, line number (4 bytes a level); 16-aligned
TBUF:   EQU 0CD40H              ; bt_slow's token (34 bytes); 64-aligned
SPOSN:  EQU 0CD70H              ; INCLUDE: the outer files' position (3 bytes of 4 a level); 16-aligned
OBUF:   EQU 0CD80H              ; the output buffer (64-aligned: oput tests OPTR & 63)
X:      EQU 0CDC0H              ; the 32-bit accumulator (asm.c xh:xl) and operand (yh:yl)
Y:      EQU 0CDC4H
MA:     EQU 0CDC8H              ; mul32's operands
MB:     EQU 0CDCCH
TBUFE:  EQU 0CDD0H              ; a token named in a message (34)
TK:     EQU 0CE00H              ; 48 token records of 8 bytes (384)
SRCN:   EQU 0CF80H              ; the names (64 each)
OUTN:   EQU 0CFC0H
POOLEND: EQU XL0                ; the symbol table ends below the tables
ZTOP:   EQU AV                  ; init zeroes AV .. $CFFF
ZTLEN:  EQU 0D000H-AV

ZBEG:
HEXO:   DS 1
PASS:   DS 1
STOP:   DS 1
LNERR:  DS 1
TOERR:  DS 1
FDEP:   DS 1
FSET:   DS 1
SSET:   DS 1
OCNT:   DS 1
ERRS:   DS 2
ALO:    DS 2
AHI:    DS 2
FIRST:  DS 2
STARTA:  DS 2
OH:     DS 2
FH:     DS 2
FPOS:   DS 2
NBYTES: DS 2
NSYM:   DS 2
PTOP:   DS 2
OPTR:   DS 2
OADDR:  DS 2
LNUM:   DS 2
CURLAB: DS 2
CMD:    DS 2
LLEN:   DS 1
LASTH:  DS 1
DOTP:   DS 2
AW_MAX: DS 1
OC_C:   DS 1
DV_B:   DS 1
OX_B:   DS 1
OX_H:   DS 1
ER_M:   DS 2
ER_W:   DS 2
ER_E:   DS 2
ER_SV:  DS 1
RP_C:   DS 1
GLP:   DS 2
GL_END: DS 2
GLLIM: DS 2
GL_LSV: DS 1
GL_LF:  DS 1
GLQ:   DS 1
GL_T:   DS 1
GL_E:   DS 1
GL_LW:  DS 1
GL_N:   DS 1
GL_SKIP: DS 2
GL_R5:  DS 2
GL_R6:  DS 2
LINEST: DS 2
LINELEN: DS 1
NPOS:   DS 3
IC_N:   DS 2
IC_H:   DS 2
IC_P:   DS 3
SF_N:   DS 1
SF_E:   DS 2
GN_S:   DS 2
GN_E:   DS 2
GN_SV:  DS 1
GN_R:   DS 1
GI:     DS 1
GJ:     DS 1
TD_I:   DS 1
TD_K:   DS 1
TM_N:   DS 1
PR_ST:  DS 1
PR_EX:  DS 1
PRC:   DS 1
PR_P:   DS 2
LV_A:   DS 1
LV_B:   DS 1
LV_I:   DS 1
LV_P:   DS 2
AP_SN:  DS 1
TCOUNT: DS 1
CURP:   DS 2
BT_R5:  DS 2
BS_TL:  DS 1
BSQ:   DS 1
BS_C:   DS 1
BS_A:   DS 1
BS_R5:  DS 2
TK_LEN: DS 1
TK_PTR: DS 2
TK_C:   DS 1
TK_H:   DS 1
TK_CNT: DS 1
TK_D:   DS 1
TK_B:   DS 1
TK_R4:  DS 2
AC_S:   DS 2
AC_N:   DS 1
AC_NP:  DS 1
AC_PAT: DS 2
AP:     DS 2
MAEND: DS 2
MA_B:   DS 1
MA_P:   DS 2
MA_D:   DS 2
MA_Q:   DS 1
LISTP:  DS 2
RO:     DS 1
LO_W:   DS 1
LO_S:   DS 2
LO_T:   DS 2
LO_Q:   DS 1
WB_B:   DS 1
FL_CK:  DS 1
OW_N:   DS 2
ZEND:
POOL:                                   ; the symbol table: from here to POOLEND
ZLEN:   EQU ZEND-ZBEG
