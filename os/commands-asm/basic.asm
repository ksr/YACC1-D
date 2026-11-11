; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

; =====================================================================================================================
; basic.asm - BASIC under Y1/OS, hand-written in YACC1 assembly (2026-11-11).
;
; The same program as os/commands/basic.c, which stays in the tree as THE SPECIFICATION: the same command line
; (basic, basic FILE, basic -r FILE), the same statements, functions, messages, limits and files, and the same
; console output byte for byte on every session (tests/basic/run.py runs both on the same sessions and compares).
; Every routine below names the C function it implements and follows it step by step, the error flag included: a C
; function that goes on after an error (and may then make a variable, or print a second message) goes on here too.
; Any change of behaviour goes into both files.
;
; Built by os/Makefile with the host assembler (software/assembler, `asm basic -d=yacc1`, Intel hex, img2bin at $5000).
;
; ---- conventions -----------------------------------------------------------------------------------------------
; R0 = PC, R1 = SP. R2 is NEVER used (the machine's LDA/STA/LDR/STR leave the operand address in it).
; The interpreter recurses - an expression in brackets, IF ... THEN statement, RUN - so it runs on a stack of its
;   own (STACK, 1 K at the end of the program's memory; the shell's stack is 768 bytes shared with the shell): the
;   shell's SP is kept in OSSP and comes back at `exit`. A value that must survive a recursive call is pushed
;   (PUSHR); the other temporaries are the variables at the end, each used by one routine.
; R3 carries a 16-bit value: an expression's result, a pointer argument. R5 is the parse cursor while a routine
;   reads the text: tp itself lives in memory (TP); skipsp returns R5 = tp and ACC = the character there, and a
;   routine that moves on stores R5 back. R4, R6, R7 are scratch. A yes/no result comes back in ACC (0 = no), tested
;   by the caller's BRZ/BRNZ.
; The Y1/OS syscalls clobber R3..R7, ACC and TMP: the wrappers here keep R3..R6 (output: sysk) or R4..R6 (a
;   result in R3: sysr). R7 is the wrappers' scratch.
; Uses the --xisa instructions ADDIW and SHL16 (the 2026-09-24 microcode, as every native tool since then).
; 16-bit adds are ADDT/ADDI then ADDTC/ADDIC with nothing but moves between; a 16-bit subtract is the add of the
;   complement (sub34); nothing tests the carry after a shift or a subtract. Multiply and divide are y1cc's runtime
;   routines (software/compiler/lib/y1ccrt.txt rt_mul, rt_divmod), so * / % give what the compiled C gives.
; Words in RAM are big-endian (LDR/STR order). Text is in single quotes, which the assembler does not upper-case.
;
; ---- what differs from the C inside (nothing a session can see) --------------------------------------------------
; - A variable is known by the address of its value (C: its index), a FOR frame holds that address.
; - The keywords are a table of 8-byte entries, searched by the first letter; a statement's token is an index into
;   a table of handlers (STTAB).
; - The flags and counts that are 16-bit ints in C are bytes; pend is two bytes (PENDF, PENDC).
; - RUN takes the next line from where the parse cursor stopped (the line's end) instead of scanning the line again;
;   it remembers where it found the last lines a GOTO, GOSUB or THEN named (8 of them, until the program changes),
;   and looks for a line from the current one on when its number is not below it.
; - A one-letter variable is found through a table of 26 addresses once it has been looked up by name.
; - Only the variables are cleared at the start, not the program area (C clears all its BSS: 13 K).
; =====================================================================================================================

        ORG 5000H
start:  BR main
        DB 0
; STTAB: the statement of each token, 128 up (a token that cannot start a statement: an error). It is at $5004, so
; that stmt makes an entry's address from the token alone (the page $50, the low byte 4 + 2 x the token's number).
STTAB:  DW st_print
        DW s_let
        DW st_if
        DW synerr
        DW st_for
        DW synerr
        DW st_next
        DW s_goto
        DW st_gosub
        DW st_return
        DW st_input
        DW s_rem
        DW s_end
        DW st_run
        DW s_list
        DW s_new
        DW synerr
        DW synerr
        DW synerr
        DW st_poke
        DW synerr
        DW s_bye
        DW st_help
        DW st_save
        DW st_load
        DW synerr
        DW synerr
        DW synerr
        DW synerr
        DW synerr
        DW synerr
        DW st_open
        DW s_close
        DW synerr
        DW synerr
        DW synerr
        DW synerr

; ---- the Y1/OS syscall interface (os/lib_abi.c) ------------------------------------------------------------------
SYSARG0:    EQU 0F06H           ; the syscall arguments and result, big-endian words
SYSARG1:    EQU 0F08H
SYSARG2:    EQU 0F0AH
SYSRES:     EQU 0F0CH
ARGBUF:     EQU 0F40H           ; the command tail
SY_OPEN:    EQU 0F14H           ; SYSTAB + 2n: the handlers of OPEN (0), GETC (2), CLOSE (3), CREATE (4), PUTC (6),
SY_GETC:    EQU 0F18H           ;   CONIN (17), CONST (18), CONOUT (19), STDIO (21)
SY_CLOSE:   EQU 0F1AH
SY_CREATE:  EQU 0F1CH
SY_PUTC:    EQU 0F20H
SY_CONIN:   EQU 0F36H
SY_CONST:   EQU 0F38H
SY_CONOUT:  EQU 0F3AH
SY_STDIO:   EQU 0F3EH

; ---- the limits (basic.c's #defines) -----------------------------------------------------------------------------
PROGSZ:     EQU 12288           ; the program area
STKSZ:      EQU 1024            ; this program's stack
; the tokens that are tested by name: 128 + the keyword's place in KWTAB
T_LET:      EQU 129
T_THEN:     EQU 131
T_FOR:      EQU 132
T_TO:       EQU 133
T_INPUT:    EQU 138
T_REM:      EQU 139
T_RUN:      EQU 141
T_ABS:      EQU 144
T_RND:      EQU 145
T_PEEK:     EQU 146
T_STEP:     EQU 148
T_CHRS:     EQU 153
T_LEFTS:    EQU 154
T_RIGHTS:   EQU 155
T_MIDS:     EQU 156
T_LEN:      EQU 157
T_ASC:      EQU 158
T_OUTPUT:   EQU 161
T_STRS:     EQU 162
T_VAL:      EQU 163
T_EOF:      EQU 164
NKW:        EQU 37              ; the keywords: tokens 128..164

; =====================================================================================================================
; main (basic.c main): the variables cleared, the arguments, then the prompt's loop.
; =====================================================================================================================
main:   MVIW R3,ZBEG            ; C's BSS clear, for the variables and the tables (not the program area)
        MVIW R4,ZLEN
st_z:   LDIVR R3,0
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ st_z
        MVRHA R4
        BRNZ st_z
        MOVRR R1,R5             ; onto the stack of this program; the shell's SP for the way out
        STR R5,OSSP
        MVIW R1,STKTOP
        JSR newprog
        MVIW R3,44257
        STR R3,SEED
        LDR R7,SY_STDIO         ; redir = stdio() & 1
        JSR sysr
        MVRLA R3
        ANDI 1
        STA REDIR
        MVIW R5,ARGBUF          ; a = argstr(), past the blanks
m_sp:   LDAVR R5
        LDTI 32
        BRNEQ m_a
        INCR R5
        BR m_sp
m_a:    LDTI 45                 ; "-r " : run the file and leave
        BRNEQ m_w
        MOVRR R5,R4
        INCR R4
        LDAVR R4
        ORI 32
        LDTI 114
        BRNEQ m_use
        INCR R4
        LDAVR R4
        LDTI 32
        BRNEQ m_use
        LDAI 1
        STA RUNIT
        MOVRR R4,R5
        BR m_w
m_use:  MVIW R3,S_USAGE         ; any other -x
        BR m_puts
m_w:    MVIW R4,NAME            ; argword(a, name, 50)
        MVIW R6,0
m_w0:   LDAVR R5
        LDTI 32
        BRNEQ m_w1
        INCR R5
        BR m_w0
m_w1:   LDAVR R5
        BRZ m_w3
        LDTI 32
        BREQ m_w3
        MVRLA R6
        LDTI 50
        BRLT m_w2
        BR m_w2a
m_w2:   LDAVR R5
        STAVR R4
        INCR R4
        INCR R6
m_w2a:  INCR R5
        BR m_w1
m_w3:   LDIVR R4,0
        LDA NAME
        BRZ m_non
        MVIW R3,NAME
        JSR loadfile
        BRNZ m_ld
        LDA RUNIT               ; the file did not load: -r ends here, else the prompt
        BRNZ exit
        BR m_ban
m_ld:   LDA RUNIT
        BRZ m_ban
        LDAI T_RUN              ; -r: the line "RUN", then back to the shell
        STA LBUF
        LDAI 0
        STA LBUF+1
        MVIW R5,LBUF
        STR R5,TP
        LDAI 0
        STA ERR
        STA ENDF
        JSR stmtline
        JSR fileclose
        BR exit
m_non:  LDA RUNIT
        BRZ m_ban
        MVIW R3,S_USAGER
m_puts: JSR puts
        BR exit
m_ban:  MVIW R3,S_BANNER
        JSR outs
        MVIW R3,PROGSZ-2
        JSR prdecu
        MVIW R3,S_BANNER2
        JSR outs
m_lp:   LDAI 0                  ; the prompt: a line with a number is stored, one without runs at once
        STA RUNNING
        STA ERR
        STA ENDF
        STA BRANCHF
        STA JUMPF
        MVIW R3,S_PROMPT
        JSR outs
        JSR getline
        LDA EOFIN
        BRNZ m_bye
        JSR crunch
        JSR checkline
        BRNZ m_lp
        MVIW R5,LBUF
        STR R5,TP
        JSR skipsp
        LDTI 48
        BRLT m_st
        LDTI 57
        BRGT m_st
        JSR parsedec
        STR R3,LNUM
        JSR skipsp
        MOVRR R5,R3
        JSR edit
        BR m_lp
m_st:   BRZ m_lp                ; (ACC = the first character) an empty line
        JSR stmtline
        LDA ENDF
        LDTI 2
        BREQ m_bye              ; BYE
        LDA ERR
        BRNZ m_lp
        LDA BRANCHF             ; GOTO, GOSUB, RETURN, NEXT typed at the prompt
        BRNZ m_only
        LDA JUMPF
        BRZ m_lp
m_only: MVIW R3,S_ONLY
        JSR outs
        BR m_lp
m_bye:  JSR fileclose
exit:   LDR R1,OSSP             ; the shell's stack again; its RET address is on top
rts:    RET
ret0:   LDAI 0
        RET
ret1:   LDAI 1
        RET

; =====================================================================================================================
; The syscalls (os/lib_fs.c). sysk: a call with no result, R3..R6 kept. sysr: the result in R3, R4..R6 kept.
; =====================================================================================================================
sysk:   PUSHR R3
        PUSHR R4
        PUSHR R5
        PUSHR R6
        JSRUR R7
        POPR R6
        POPR R5
        POPR R4
        POPR R3
        RET
sysr:   PUSHR R4
        PUSHR R5
        PUSHR R6
        JSRUR R7
        POPR R6
        POPR R5
        POPR R4
        LDR R3,SYSRES
        RET
; putchr: ACC to stdout (y1cc's putchar under --os: CONOUT). Keeps R3..R6.
putchr: STA SYSARG0+1
        LDAI 0
        STA SYSARG0
        LDR R7,SY_CONOUT
        BR sysk
; fputc: ACC to the file whose handle is in R7 (the result is not used). Keeps R3..R6.
fputc:  STA SYSARG1+1
        LDAI 0
        STA SYSARG1
        STR R7,SYSARG0
        LDR R7,SY_PUTC
        BR sysk
conin:  LDR R7,SY_CONIN         ; -> R3: a byte, 65535 at the end of the input / Ctrl-D
        BR sysr
constat: LDR R7,SY_CONST        ; -> R3: 1 when a byte waits
        BR sysr
fgetc:  STR R3,SYSARG0          ; R3 = the handle -> R3: a byte, 65535 at the end
        LDR R7,SY_GETC
        BR sysr
fopen:  STR R3,SYSARG0          ; R3 = the path -> R3: the handle, 0 = cannot
        LDR R7,SY_OPEN
        BR sysr
fcreate: STR R3,SYSARG0         ; fcreate(path, 0, 0) -> R3: the handle, 0 = cannot
        MVIW R3,0
        STR R3,SYSARG1
        STR R3,SYSARG2
        LDR R7,SY_CREATE
        BR sysr
fclose: STR R3,SYSARG0          ; R3 = the handle -> R3: 1 done
        LDR R7,SY_CLOSE
        BR sysr
; puts: the string at R3 and a line feed to stdout
puts:   LDAVR R3
        BRZ pu_e
        JSR putchr
        INCR R3
        BR puts
pu_e:   LDAI 10
        BR putchr

; =====================================================================================================================
; Console (basic.c outc, crlf, outs, putch, getline, brk, getkey)
; =====================================================================================================================
; outc: ACC to SAVE's file while LIST writes it, else to stdout. Keeps R3..R6.
outc:   STA OC_C
        LDR R7,LSAVE
        MVRLA R7
        BRZ oc_1
        LDA OC_C
        BR fputc
oc_1:   LDA OC_C
        BR putchr
crlf:   LDAI 10
        BR outc
; outs: the string at R3 through outc
outs:   LDAVR R3
        BRZ rts
        JSR outc
        INCR R3
        BR outs
; putch: ACC to STR$'s buffer, to PRINT#'s file, or to stdout. Keeps R3..R6.
putch:  STA OC_C
        LDA STRSINK
        BRZ ph_1
        LDR R7,STRSP
        LDA OC_C
        STAVR R7
        INCR R7
        STR R7,STRSP
        LDA STRSN
        ADDI 1
        STA STRSN
        RET
ph_1:   LDA OUTFILE
        BRZ ph_2
        LDR R7,FH
        LDA OC_C
        BR fputc
ph_2:   LDA OC_C
        BR putchr
; getline: a line into LBUF, echoed unless stdin is a file or a pipe; EOFIN at Ctrl-D / the end of the input
getline: MVIW R5,LBUF
        MVIW R4,0               ; n
gl_lp:  JSR getkey
        MVRHA R3
        BRZ gl_ch
        MVRLA R4                ; 65535: the end of the input
        BRNZ gl_end
        LDAI 1
        STA EOFIN
gl_end: LDIVR R5,0
        LDA REDIR
        BRNZ rts
        BR crlf
gl_ch:   MVRLA R3
        LDTI 10
        BREQ gl_end
        LDTI 13
        BREQ gl_end
        LDTI 8
        BREQ gl_bs
        LDTI 127
        BREQ gl_bs
        LDTI 32
        BRLT gl_lp
        STA GL_C
        MVRLA R4
        LDTI 98
        BRLT gl_st
        BR gl_lp
gl_st:  LDA REDIR
        BRNZ gl_s2
        LDA GL_C
        JSR putchr
gl_s2:  LDA GL_C
        STAVR R5
        INCR R5
        INCR R4
        BR gl_lp
gl_bs:  MVRLA R4
        BRZ gl_lp
        DECR R4
        DECR R5
        LDA REDIR
        BRNZ gl_lp
        LDAI 8
        JSR putchr
        LDAI 32
        JSR putchr
        LDAI 8
        JSR putchr
        BR gl_lp
; brk: Ctrl-C typed while a program runs? -> ACC 1 after "BREAK IN n". Another key is kept for the next input.
brk:    LDA REDIR
        BRNZ ret0
        LDA PENDF
        BRNZ ret0
        JSR constat
        JSR tst3
        BRZ ret0
        JSR conin
        MVRLA R3
        LDTI 3
        BREQ bk_1
        STA PENDC               ; pend = c | 256: the low byte is what getkey gives back
        LDAI 1
        STA PENDF
        BR ret0
bk_1:   MVIW R3,S_BREAK
        JSR outs
        JSR curnum
        JSR prdecu
        JSR crlf
        BR ret1
; getkey: conin(), after a key brk kept -> R3
getkey: LDA PENDF
        BRZ conin
        LDAI 0
        STA PENDF
        MVARH R3
        LDA PENDC
        MVARL R3
        RET

; =====================================================================================================================
; Characters and the cursor (basic.c upch, isalnum, skipsp; tp = tp + 1)
; =====================================================================================================================
; upch: ACC in upper case. Clobbers TMP.
upch:   LDTI 97
        BRLT rts
        LDTI 122
        BRGT rts
        SUBI 32
        RET
; isalnum: ACC a digit or a letter? -> ACC 1 / 0
isalnum: LDTI 48
        BRLT ret0
        LDTI 58
        BRLT ret1
        JSR upch
        LDTI 65
        BRLT ret0
        LDTI 91
        BRLT ret1
        BR ret0
; skipsp: tp past the blanks -> R5 = tp, ACC = the character there. Keeps R3, R4, R6, R7.
skipsp: LDR R5,TP
        LDAVR R5
        LDTI 32
        BREQ ss_lp
        RET
ss_lp:  INCR R5
        LDAVR R5
        BREQ ss_lp
        STR R5,TP
        RET

; =====================================================================================================================
; 16-bit arithmetic
; =====================================================================================================================
; add34: R3 = R3 + R4
add34:  MVRLA R4
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R4
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        RET
; sub34: R3 = R3 - R4 (R3 + the complement of R4 + 1; R4 kept, R7 scratch)
sub34:  MVRHA R4
        INVA
        MVARH R7
        MVRLA R4
        INVA
        MVAT
        LDAI 255
        ADDI 1                  ; carry = 1
        MVRLA R3
        ADDTC
        MVARL R3
        MVRHA R7
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        RET
; neg16: R3 = 0 - R3
neg16:  MVRHA R3
        INVA
        MVARH R3
        MVRLA R3
        INVA
        ADDI 1
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        RET
; mul16: R3 = R3 * R4, the low 16 bits (y1cc's rt_mul; R4, R5 clobbered)
mul16:  MVIW R5,0
mu_lp:  MVRLA R4
        MVAT
        MVRHA R4
        ORT
        BRZ mu_e
        MVRLA R4
        ANDI 1
        BRZ mu_s
        MVRLA R3
        MVAT
        MVRLA R5
        ADDT
        MVARL R5
        MVRHA R3
        MVAT
        MVRHA R5
        ADDTC
        MVARH R5
mu_s:   SHL16 R3
        LDAI 0
        CSHL
        MVRHA R4
        CSHR
        MVARH R4
        MVRLA R4
        CSHR
        MVARL R4
        BR mu_lp
mu_e:   MOVRR R5,R3
        RET
; divz: R3 = R3 / R4, R5 = the remainder; both 0 when R4 is 0 (basic.c term)
divz:   MVRLA R4
        BRNZ divmod
        MVRHA R4
        BRNZ divmod
        MVIW R3,0
        MVIW R5,0
        RET
; divmod: R3 = R3 / R4 unsigned, R5 = the remainder (y1cc's rt_divmod; R7 clobbered)
divmod: MVIW R5,0
        MVIW R7,16
dm_lp:  MVRLA R3
        MVAT
        ADDT
        MVARL R3
        MVRHA R3
        MVAT
        ADDTC
        MVARH R3
        MVRLA R5
        MVAT
        ADDTC
        MVARL R5
        MVRHA R5
        MVAT
        ADDTC
        MVARH R5
        MVRHA R4
        MVAT
        MVRHA R5
        BRLT dm_n
        BRNEQ dm_y
        MVRLA R4
        MVAT
        MVRLA R5
        BRLT dm_n
dm_y:   MVRLA R4
        MVAT
        MVRLA R5
        BRLT dm_b
        SUBT
        MVARL R5
        MVRHA R4
        MVAT
        MVRHA R5
        SUBT
        MVARH R5
        INCR R3
        BR dm_n
dm_b:   SUBT
        MVARL R5
        MVRHA R4
        MVAT
        MVRHA R5
        SUBT
        SUBI 1
        MVARH R5
        INCR R3
dm_n:   DECR R7
        MVRLA R7
        BRNZ dm_lp
        RET
; adda5, adda6: R5 / R6 = itself + ACC. Clobber TMP.
adda5:  MVAT
        MVRLA R5
        ADDT
        MVARL R5
        MVRHA R5
        ADDIC 0
        MVARH R5
        RET
adda6:  MVAT
        MVRLA R6
        ADDT
        MVARL R6
        MVRHA R6
        ADDIC 0
        MVARH R6
        RET
; ldw3: R3 = the word at R3 (vget).  stw: the word at R3 = R4 (vset).
ldw3:   LDAVR R3
        MVAT
        INCR R3
        LDAVR R3
        MVARL R3
        MVTA
        MVARH R3
        RET
stw:    MVRHA R4
        STAVR R3
        INCR R3
        MVRLA R4
        STAVR R3
        RET
; ldw6: R3 = the word at R6, R6 past it.  stw6: the word at R6 = R3, R6 past it.
ldw6:   LDAVR R6
        MVARH R3
        INCR R6
        LDAVR R6
        MVARL R3
        INCR R6
        RET
stw6:   MVRHA R3
        STAVR R6
        INCR R6
        MVRLA R3
        STAVR R6
        INCR R6
        RET
; tst3: ACC = 0 when R3 is 0
tst3:   MVRHA R3
        MVAT
        MVRLA R3
        ORT
        RET

; =====================================================================================================================
; Numbers (basic.c prdecu, prlnum, prdec, parsedec, hexval, parsehex)
; =====================================================================================================================
; decdig: R3 in decimal at DBUF, NUL-terminated, no leading zeros -> R4 = DBUF. Clobbers R3..R6.
decdig: MVIW R6,DBUF
        LDAI 0
        STA DD_NZ
        MVIW R4,10000
        MVIW R5,0D8F0H          ; -10000
        JSR dd_pw
        MVIW R4,1000
        MVIW R5,0FC18H
        JSR dd_pw
        MVIW R4,100
        MVIW R5,0FF9CH
        JSR dd_pw
        MVIW R4,10
        MVIW R5,0FFF6H
        JSR dd_pw
        MVRLA R3
        ADDI 48
        STAVR R6
        INCR R6
        LDIVR R6,0
        MVIW R4,DBUF
        RET
; dd_pw: one digit: R3 less the power in R4 (R5 = minus it) while it is not below; put unless a leading zero
dd_pw:  LDAI 0
        STA DD_D
dp_lp:  MVRHA R4
        MVAT
        MVRHA R3
        BRLT dp_e
        BRNEQ dp_s
        MVRLA R4
        MVAT
        MVRLA R3
        BRLT dp_e
dp_s:   MVRLA R5
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R5
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        LDA DD_D
        ADDI 1
        STA DD_D
        BR dp_lp
dp_e:   LDA DD_D
        BRNZ dp_o
        LDA DD_NZ
        BRZ rts
dp_o:   LDA DD_D
        ADDI 48
        STAVR R6
        INCR R6
        LDAI 1
        STA DD_NZ
        RET
; prdecu: R3 unsigned through putch.  prdec: R3 signed.  prlnum: a line number through outc (LIST, SAVE).
prdec:  MVRHA R3
        ANDI 128
        BRZ prdecu
        LDAI 45
        JSR putch
        JSR neg16
prdecu: JSR decdig
pd_lp:  LDAVR R4
        BRZ rts
        JSR putch
        INCR R4
        BR pd_lp
prlnum: JSR decdig
pl_lp:  LDAVR R4
        BRZ rts
        JSR outc
        INCR R4
        BR pl_lp
; parsedec: the decimal digits at tp -> R3 (0 for none), tp past them. Clobbers R4, R5.
parsedec: LDR R5,TP
        LDAVR R5
        LDTI 48
        BRLT pn_0
        LDTI 57
        BRGT pn_0
pn_d1:  SUBI 48                 ; (entry: ACC = the first digit's character, R5 at it)
        MVARL R3
        LDAI 0
        MVARH R3
        INCR R5
        LDAVR R5                ; a second digit: in 8 bits, 99 at most
        LDTI 48
        BRLT pn_e
        LDTI 57
        BRGT pn_e
        SUBI 48
        STA PN_D
        MVRLA R3
        SHL
        MVAT
        SHL
        SHL
        ADDT
        MVAT
        LDA PN_D
        ADDT
        MVARL R3
        INCR R5
pn_lp:  LDAVR R5                ; more: v = v * 10 + the digit in 16 bits (entry: R3 = v, R5 at the next character)
        LDTI 48
        BRLT pn_e
        LDTI 57
        BRGT pn_e
        SUBI 48
        STA PN_D
        SHL16 R3
        MOVRR R3,R4
        SHL16 R3
        SHL16 R3
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
        LDA PN_D
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        INCR R5
        BR pn_lp
pn_e:   STR R5,TP
        RET
pn_0:   MVIW R3,0
        RET
; parsehex: the hex digits at tp -> R3, tp past them
parsehex: LDR R5,TP
        MVIW R3,0
px_lp:  LDAVR R5
        LDTI 48
        BRLT px_e
        LDTI 58
        BRLT px_d
        LDTI 97
        BRLT px_u
        LDTI 122
        BRGT px_u
        SUBI 32
px_u:   LDTI 65
        BRLT px_e
        LDTI 70
        BRGT px_e
        SUBI 7
px_d:   SUBI 48
        STA PN_D
        SHL16 R3
        SHL16 R3
        SHL16 R3
        SHL16 R3
        MVRLA R3
        MVAT
        LDA PN_D
        ORT
        MVARL R3
        INCR R5
        BR px_lp
px_e:   STR R5,TP
        RET

; =====================================================================================================================
; Errors (basic.c synerr, msgerr, expect): ERR is set and every level returns through it
; =====================================================================================================================
synerr: LDA ERR
        BRNZ rts
        LDAI 1
        STA ERR
        LDAI 0
        STA OUTFILE
        STA STRSINK
        LDA RUNNING
        BRNZ sy_r
        MVIW R3,S_SYN
        BR outs
sy_r:   MVIW R3,S_SYNIN
        JSR outs
        JSR curnum
        JSR prdecu
        BR crlf
; msgerr: the message at R3
msgerr: LDAI 1
        STA ERR
        LDAI 0
        STA OUTFILE
        STA STRSINK
        BR outs
; expect: the character in ACC must come next (after blanks)
expect: STA EX_C
        JSR skipsp
        MVAT
        LDA EX_C
        BRNEQ synerr
        INCR R5
        STR R5,TP
        RET

; =====================================================================================================================
; Keywords (basic.c kwmatch, crunch, prkw): KWTAB holds them in token order, 8 bytes each
; =====================================================================================================================
; kwmatch: a keyword at R5? ACC = its first character in upper case on entry -> ACC = the token (0: none),
; KWLEN = its length. Keeps R3, R5. A keyword must not run on into a longer name (TOTAL is not TO).
kwmatch: STA KW_C0
        MVAT
        MVIW R6,KWTAB
        MVIW R7,128
km_lp:  LDAVR R6
        BRZ ret0                ; the end of the table
        BREQ km_try
km_nx:  ADDIW R6,8
        INCR R7
        BR km_lp
km_try: STR R6,KW_T
        MOVRR R5,R4
km_c:   INCR R6
        INCR R4
        LDAVR R6
        BRZ km_end
        LDAVR R4
        JSR upch
        MVAT
        LDAVR R6
        BREQ km_c
km_f:   LDR R6,KW_T             ; not this one: on with the next
        LDA KW_C0
        MVAT
        BR km_nx
km_end: LDAVR R4
        JSR isalnum
        BRNZ km_f
        MVRLA R5
        MVAT
        MVRLA R4
        SUBT
        STA KWLEN
        MVRLA R7
        RET
; crunch: the keywords of LBUF outside quotes become tokens, in place
crunch: MVIW R5,LBUF            ; r
        MVIW R3,LBUF            ; w
cr_lp:  LDAVR R5
        BRZ cr_e
        LDTI 34
        BRNEQ cr_l
        STAVR R3                ; a string: copied up to its closing quote
        INCR R3
        INCR R5
cr_q:   LDAVR R5
        BRZ cr_e
        STAVR R3
        INCR R3
        INCR R5
        LDTI 34
        BRNEQ cr_q
        BR cr_lp
cr_l:   JSR upch
        LDTI 65
        BRLT cr_cp
        LDTI 90
        BRGT cr_cp
        JSR kwmatch
        BRZ cr_cp
        STAVR R3
        INCR R3
        LDA KWLEN
        JSR adda5
        BR cr_lp
cr_cp:  LDAVR R5
        STAVR R3
        INCR R3
        INCR R5
        BR cr_lp
cr_e:   LDIVR R3,0
        RET
; prkw: the keyword of the token in ACC through outc (nothing for a byte that is no token). Keeps R3..R5.
prkw:   SUBI 128
        LDTI NKW
        BRLT pk_1
        RET
pk_1:   MVARL R6
        LDAI 0
        MVARH R6
        SHL16 R6
        SHL16 R6
        SHL16 R6
        ADDIW R6,KWTAB
pk_lp:  LDAVR R6
        BRZ rts
        JSR outc
        INCR R6
        BR pk_lp

; =====================================================================================================================
; The check of a line as it is entered or loaded (basic.c cklead, ckbad, checkline) -> ACC 1 = refused
; =====================================================================================================================
checkline: MVIW R5,LBUF
ck_s0:  LDAVR R5
        LDTI 32
        BRNEQ ck_d
        INCR R5
        BR ck_s0
ck_d:   LDAVR R5                ; the line number
        LDTI 48
        BRLT ck_st
        LDTI 57
        BRGT ck_st
        INCR R5
        BR ck_d
ck_st:  MVIW R4,0               ; a statement: dep = 0
ck_s1:  LDAVR R5
        LDTI 32
        BRNEQ ck_ld
        INCR R5
        BR ck_s1
ck_ld:  BRZ ret0                ; cklead: may this start a statement?
        LDTI T_REM
        BREQ ret0               ; the rest is a remark
        LDTI 128
        BRLT ck_ch
        LDTI T_THEN
        BREQ ck_bad
        LDTI T_TO
        BREQ ck_bad
        LDTI T_STEP
        BREQ ck_bad
        LDTI T_OUTPUT
        BREQ ck_bad
        LDTI 144
        BRLT ck_in
        LDTI 147
        BRLT ck_bad             ; ABS RND PEEK
        LDTI 153
        BRLT ck_in
        LDTI 159
        BRLT ck_bad             ; CHR$ LEFT$ RIGHT$ MID$ LEN ASC
        LDTI 162
        BRLT ck_in
        LDTI 165
        BRLT ck_bad             ; STR$ VAL EOF
        BR ck_in
ck_ch:  JSR upch
        LDTI 65
        BRLT ck_bad
        LDTI 90
        BRGT ck_bad
ck_in:  LDAVR R5                ; to the statement's end: quotes closed, brackets balanced
        BRZ ck_e0
        LDTI 34
        BREQ ck_q
        LDTI 40
        BREQ ck_op
        LDTI 41
        BREQ ck_cl
        LDTI 58
        BREQ ck_co
ck_nx:  INCR R5
        BR ck_in
ck_e0:  MVRLA R4
        BRZ ret0
ck_bad: MVIW R3,S_SYN
        JSR outs
        BR ret1
ck_q:   INCR R5
ck_q1:  LDAVR R5
        BRZ ck_bad
        LDTI 34
        BREQ ck_nx
        INCR R5
        BR ck_q1
ck_op:  INCR R4
        BR ck_nx
ck_cl:  MVRLA R4
        BRZ ck_bad
        DECR R4
        BR ck_nx
ck_co:  MVRLA R4
        BRNZ ck_bad
        INCR R5
        BR ck_st

; =====================================================================================================================
; Variables (basic.c parsename, nameeq, varfind, varget, svarfind, svarget, speek). VTAB: 32 entries name[6]
; value[2]; SVTAB: 16 entries name[6] [len][32 characters] and a spare byte. A variable is its value's address.
; =====================================================================================================================
; parsename: NMBUF = the name at tp, upper case, blank-padded -> ACC 1, R5 = tp past it; 0 when there is none
parsename: LDR R5,TP
        LDAVR R5
        JSR upch
        LDTI 65
        BRLT ret0
        LDTI 90
        BRGT ret0
        MVAT
        MVIW R4,NMBUF+1
        LDIVR R4,32
        INCR R4
        LDIVR R4,32
        INCR R4
        LDIVR R4,32
        INCR R4
        LDIVR R4,32
        INCR R4
        LDIVR R4,32
        MVIW R4,NMBUF
        MVIB R6,6
        MVTA
pm_lp:  MVAT                    ; the first six characters are kept
        MVRLA R6
        BRZ pm_nx
        MVTA
        STAVR R4
        INCR R4
        DECR R6
pm_nx:  INCR R5
        LDAVR R5
        JSR upch
        LDTI 48
        BRLT pm_e
        LDTI 58
        BRLT pm_lp
        LDTI 65
        BRLT pm_e
        LDTI 91
        BRLT pm_lp
pm_e:   STR R5,TP
        BR ret1
; nmcopy: NMBUF to the six bytes at R6; R6 past them
nmcopy: MVIW R4,NMBUF
        MVIB R7,6
nc_lp:  LDAVR R4
        STAVR R6
        INCR R4
        INCR R6
        DECR R7
        MVRLA R7
        BRNZ nc_lp
        RET
; varfind: the variable named NMBUF, made (0) if new -> R3 = its value's address
varfind: MVIW R6,VTAB
        LDA VARCNT
        STA VF_N
vf_lp:  LDA VF_N
        BRZ vf_new
        MVIW R4,NMBUF
        MOVRR R6,R3
        MVIB R7,6
vf_c:   LDAVR R4
        MVAT
        LDAVR R3
        BRNEQ vf_nx
        INCR R4
        INCR R3
        DECR R7
        MVRLA R7
        BRNZ vf_c
        BR vf_ok                ; found: R3 is past the name
vf_nx:  ADDIW R6,8
        LDA VF_N
        SUBI 1
        STA VF_N
        BR vf_lp
vf_new: LDA VARCNT
        LDTI 32
        BRLT vf_mk
        MVIW R3,S_TMV
        JSR msgerr
        MVIW R3,VTAB+6          ; (C returns index 0)
        RET
vf_mk:  JSR nmcopy
        MOVRR R6,R3
        LDIVR R6,0
        INCR R6
        LDIVR R6,0
        LDA VARCNT
        ADDI 1
        STA VARCNT
vf_ok:  LDA NMBUF+1             ; a one-letter name: its value's address into VCPAGE for varget
        LDTI 32
        BRNEQ rts
        LDA NMBUF
        SHL
        MVIW R6,VCPAGE
        MVARL R6
        MVRHA R3
        STAVR R6
        INCR R6
        MVRLA R3
        STAVR R6
        RET
; varget: the variable at tp -> ACC 1, R3 = its value's address; ACC 0 when no name is there
; vg_c: the same with R5 = tp and ACC = the character there. A one-letter name that was looked up before comes
; straight from VCPAGE (its value's address at 2 x the letter), without NMBUF and the search.
varget: LDR R5,TP
        LDAVR R5
vg_c:   LDTI 91
        BRLT vg_u
        LDTI 97
        BRLT ret0
        LDTI 122
        BRGT ret0
        SUBI 32
        BR vg_l
vg_u:   LDTI 65
        BRLT ret0
vg_l:   MVARL R4                ; the letter, in upper case
        INCR R5
        LDAVR R5                ; does the name go on?
        LDTI 48
        BRLT vg_f
        LDTI 58
        BRLT vg_s
        LDTI 65
        BRLT vg_f
        LDTI 91
        BRLT vg_s
        LDTI 97
        BRLT vg_f
        LDTI 123
        BRLT vg_s
vg_f:   MVRLA R4
        SHL
        MVIW R6,VCPAGE
        MVARL R6
        LDAVR R6
        BRZ vg_s                ; not looked up yet (an address's high byte is never 0)
        MVARH R3
        INCR R6
        LDAVR R6
        MVARL R3
        STR R5,TP
        LDAI 1
        RET
vg_s:   JSR parsename
        JSR varfind
        LDAI 1
        RET
; svarfind: the string variable named NMBUF, made (empty) if new -> R3 = its string's address
svarfind: MVIW R6,SVTAB
        LDA SVARCNT
        STA VF_N
sf_lp:  LDA VF_N
        BRZ sf_new
        MVIW R4,NMBUF
        MOVRR R6,R3
        MVIB R7,6
sf_c:   LDAVR R4
        MVAT
        LDAVR R3
        BRNEQ sf_nx
        INCR R4
        INCR R3
        DECR R7
        MVRLA R7
        BRNZ sf_c
        RET
sf_nx:  ADDIW R6,40
        LDA VF_N
        SUBI 1
        STA VF_N
        BR sf_lp
sf_new: LDA SVARCNT
        LDTI 16
        BRLT sf_mk
        MVIW R3,S_TMS
        JSR msgerr
        MVIW R3,SVTAB+6
        RET
sf_mk:  JSR nmcopy
        MOVRR R6,R3
        LDIVR R6,0
        LDA SVARCNT
        ADDI 1
        STA SVARCNT
        RET
; svarget: NAME$ at tp -> ACC 1, R3 = its string's address; ACC 0 when it is not a string variable
svarget: JSR parsename
        BRZ rts
        LDAVR R5
        LDTI 36
        BRNEQ ret0
        INCR R5
        STR R5,TP
        JSR svarfind
        BR ret1
; speek: does a string expression begin at tp? -> ACC 1 / 0 (tp only moves past blanks)
speek:  JSR skipsp
        LDTI 64
        BRGT sk_hi
        LDTI 34                 ; below the letters only a " starts a string
        BREQ ret1
        BR ret0
sk_hi:  LDTI 128
        BRLT sk_nm
        LDTI T_CHRS
        BRLT ret0
        LDTI T_LEN
        BRLT ret1               ; CHR$ LEFT$ RIGHT$ MID$
        LDTI T_STRS
        BREQ ret1
        BR ret0
sk_nm:  LDTI 91                 ; a name: a string's when a $ ends it
        BRLT sk_lp
        LDTI 97
        BRLT ret0
        LDTI 123
        BRLT sk_lp
        BR ret0
sk_lp:  INCR R5
        LDAVR R5
        LDTI 48
        BRLT sk_e
        LDTI 58
        BRLT sk_lp
        LDTI 65
        BRLT sk_e
        LDTI 91
        BRLT sk_lp
        LDTI 97
        BRLT sk_e
        LDTI 123
        BRLT sk_lp
sk_e:   LDTI 36
        BREQ ret1
        BR ret0

; =====================================================================================================================
; Strings: [length][characters], 32 at most (basic.c smove, sapp, scpylit, sput, sarg_, clampn, substr, stmopen,
; sterm, seval, scmp). SACC, STMP, SARG, SCMPB are the work buffers.
; =====================================================================================================================
; smove: the string at R3 to R4
smove:  LDAVR R3
        ADDI 1
        MVARL R7
sm_lp:  LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        DECR R7
        MVRLA R7
        BRNZ sm_lp
        RET
; sapp: the string at R3 appended to the one at R4, cut at 32 characters
sapp:   LDAVR R4
        STA SA_M
        LDAVR R3
        STA SA_N
        INCR R3
        MOVRR R4,R6
        INCR R6
        LDA SA_M
        JSR adda6
sa_lp:  LDA SA_N
        BRZ sa_e
        LDA SA_M
        LDTI 32
        BRLT sa_c
        BR sa_e
sa_c:   LDAVR R3
        STAVR R6
        INCR R3
        INCR R6
        LDA SA_M
        ADDI 1
        STA SA_M
        LDA SA_N
        SUBI 1
        STA SA_N
        BR sa_lp
sa_e:   LDA SA_M
        STAVR R4
        RET
; scpylit: the "..." at tp to the string at R4 (a missing closing quote ends at the line's end)
scpylit: LDR R5,TP
        INCR R5
        MOVRR R4,R6
        INCR R6
        MVIW R7,0
sl_lp:  LDAVR R5
        BRZ sl_e
        LDTI 34
        BREQ sl_q
        MVRLA R7
        LDTI 32
        BRLT sl_st
        BR sl_nx
sl_st:  LDAVR R5
        STAVR R6
        INCR R6
        INCR R7
sl_nx:  INCR R5
        BR sl_lp
sl_q:   INCR R5
sl_e:   STR R5,TP
        MVRLA R7
        STAVR R4
        RET
; sput: the string at R3 through putch
sput:   LDAVR R3
        MVARL R4
sp_lp:  MVRLA R4
        BRZ rts
        INCR R3
        LDAVR R3
        JSR putch
        DECR R4
        BR sp_lp
; sarg_: a literal or a string variable at tp to the string at R4
sarg_:  STR R4,SG_D
        JSR skipsp
        LDTI 34
        BREQ scpylit
        JSR svarget
        BRZ synerr
        LDR R4,SG_D
        BR smove
; sargpar: ( string ) into SARG (LEN, ASC, VAL)
sargpar: LDAI 40
        JSR expect
        MVIW R4,SARG
        JSR sarg_
        LDAI 41
        BR expect
; clampn: R3 as a count -> ACC: 0 for a negative number, 32 for one over 255
clampn: MVRHA R3
        BRZ cn_lo
        ANDI 128
        BRNZ ret0
        LDAI 32
        RET
cn_lo:  MVRLA R3
        RET
; substr: STMP = the part of SARG from character R3.lo (0 = the first), R4.lo characters at most
substr: LDA SARG
        STA SB_L
        MVAT
        MVRLA R3
        BRLT sb_1
        LDAI 0                  ; it starts past the end
        STA STMP
        RET
sb_1:   MVAT                    ; TMP = si
        LDA SB_L
        SUBT
        MVAT                    ; TMP = l - si
        MVRLA R4
        BRGT sb_2
        BR sb_3
sb_2:   MVTA
        MVARL R4
sb_3:   MVRLA R4
        STA STMP
        MVIW R5,SARG+1
        MVRLA R3
        JSR adda5
        MVIW R6,STMP+1
sb_lp:  MVRLA R4
        BRZ rts
        LDAVR R5
        STAVR R6
        INCR R5
        INCR R6
        DECR R4
        BR sb_lp
; stmopen: after LEFT$ RIGHT$ MID$: ( string , number -> the string in SARG, the number in R3
stmopen: INCR R5
        STR R5,TP
        LDAI 40
        JSR expect
        LDA ERR
        BRNZ rts
        MVIW R4,SARG
        JSR sarg_
        LDA ERR
        BRNZ rts
        LDAI 44
        JSR expect
        LDA ERR
        BRNZ rts
        BR expr
; sterm: one string term at tp into STMP (C: sterm(dst), only ever called with stmp)
sterm:  JSR skipsp
        LDTI 34
        BRNEQ tm_1
        MVIW R4,STMP
        BR scpylit
tm_1:   LDTI T_CHRS
        BRNEQ tm_2
        INCR R5                 ; CHR$(n)
        STR R5,TP
        LDAI 40
        JSR expect
        JSR expr
        PUSHR R3
        LDAI 41
        JSR expect
        POPR R3
        LDAI 1
        STA STMP
        MVRLA R3
        STA STMP+1
        RET
tm_2:   LDTI T_STRS
        BRNEQ tm_3
        INCR R5                 ; STR$(n): prdec into the string
        STR R5,TP
        LDAI 40
        JSR expect
        JSR expr
        PUSHR R3
        LDAI 41
        JSR expect
        POPR R3
        MVIW R4,STMP+1
        STR R4,STRSP
        LDAI 0
        STA STRSN
        LDAI 1
        STA STRSINK
        JSR prdec
        LDAI 0
        STA STRSINK
        LDA STRSN
        STA STMP
        RET
tm_3:   LDTI T_LEFTS
        BRNEQ tm_4
        JSR stmopen             ; LEFT$(s, n)
        LDA ERR
        BRNZ rts
        JSR clampn
        MVARL R4
        MVIW R3,0
        JSR substr
        LDAI 41
        BR expect
tm_4:   LDTI T_RIGHTS
        BRNEQ tm_5
        JSR stmopen             ; RIGHT$(s, n)
        LDA ERR
        BRNZ rts
        JSR clampn
        MVARL R4
        MVAT
        MVIW R3,0
        LDA SARG
        BRGT tm_4a              ; the string is longer than n: from l - n
        BR tm_4b
tm_4a:  SUBT
        MVARL R3
tm_4b:  JSR substr
        LDAI 41
        BR expect
tm_5:   LDTI T_MIDS
        BRNEQ tm_6
        JSR stmopen             ; MID$(s, start [, n])
        LDA ERR
        BRNZ rts
        MVRHA R3
        BRZ tm_5a
        ANDI 128
        BRNZ tm_5z
        LDAI 32
        BR tm_5s
tm_5a:  MVRLA R3
        BRZ tm_5s
        SUBI 1
        BR tm_5s
tm_5z:  LDAI 0
tm_5s:  STA TM_I
        JSR skipsp
        LDTI 44
        BRNEQ tm_5d
        INCR R5
        STR R5,TP
        JSR expr
        JSR clampn
        BR tm_5e
tm_5d:  LDAI 32
tm_5e:  MVARL R4
        LDA TM_I
        MVARL R3
        JSR substr
        LDAI 41
        BR expect
tm_6:   JSR svarget             ; a string variable
        BRZ synerr
        MVIW R4,STMP
        BR smove
; seval: term { + term } into SACC
seval:  LDAI 0
        STA SACC
sv_lp:  JSR sterm
        LDA ERR
        BRNZ rts
        MVIW R3,STMP
        MVIW R4,SACC
        JSR sapp
        JSR skipsp
        LDTI 43
        BRNEQ rts
        INCR R5
        STR R5,TP
        BR sv_lp
; scmp: REL = SCMPB against SACC, by character code, then by length
scmp:   LDA SACC
        MVAT
        LDA SCMPB
        BRLT sc_n
        MVTA
sc_n:   MVARL R5                ; the shorter length
        MVIW R3,SCMPB+1
        MVIW R4,SACC+1
sc_lp:  MVRLA R5
        BRZ sc_len
        LDAVR R4
        MVAT
        LDAVR R3
        BRLT sc_lt
        BRGT sc_gt
        INCR R3
        INCR R4
        DECR R5
        BR sc_lp
sc_len: LDA SACC
        MVAT
        LDA SCMPB
        BRLT sc_lt
        BRGT sc_gt
        LDAI 2
        BR sc_set
sc_lt:  LDAI 1
        BR sc_set
sc_gt:  LDAI 4
sc_set: STA REL
        RET

; =====================================================================================================================
; Expressions (basic.c relopp, parget, random_, factor, term, expr, relresult, evalstr, eval) -> R3
; =====================================================================================================================
; relopp: a comparison at tp? -> ACC 1 and RELM = its bits (1 below, 2 equal, 4 above); ACC 0 when there is none
relopp: JSR skipsp
        LDTI 61
        BRNEQ ro_1
        LDAI 2
        BR ro_s1
ro_1:   LDTI 60
        BRNEQ ro_2
        INCR R5
        LDAVR R5
        LDTI 61
        BRNEQ ro_1a
        LDAI 3
        BR ro_s1
ro_1a:  LDTI 62
        BRNEQ ro_1b
        LDAI 5
        BR ro_s1
ro_1b:  LDAI 1
        BR ro_s0
ro_2:   LDTI 62
        BRNEQ ret0
        INCR R5
        LDAVR R5
        LDTI 61
        BRNEQ ro_2a
        LDAI 6
        BR ro_s1
ro_2a:  LDAI 4
        BR ro_s0
ro_s1:  INCR R5
ro_s0:  STA RELM
        STR R5,TP
        BR ret1
; parget: ( expression ) -> R3 (0 when the bracket is missing)
parget: LDAI 40
        JSR expect
        LDA ERR
        BRZ pg_1
        MVIW R3,0
        RET
pg_1:   JSR expr
        PUSHR R3
        LDAI 41
        JSR expect
        POPR R3
        RET
; random_: the next number of the generator -> R3
random_: LDR R3,SEED
        MVIW R4,25173
        JSR mul16
        ADDIW R3,13849
        STR R3,SEED
        RET
; factor
factor: JSR skipsp
        LDTI 128
        BRLT fa_ch
        LDTI T_ABS
        BREQ fa_abs
        LDTI T_PEEK
        BREQ fa_pk
        LDTI T_RND
        BREQ fa_rnd
        LDTI T_LEN
        BREQ fa_len
        LDTI T_ASC
        BREQ fa_asc
        LDTI T_VAL
        BREQ fa_val
        LDTI T_EOF
        BREQ fa_eof
fa_syn: JSR synerr
fa_z:   MVIW R3,0
        RET
fa_ch:  LDTI 48
        BRLT fa_p
        LDTI 58
        BRLT fa_num
fa_var: JSR vg_c                ; a variable; anything else is an error
        BRZ fa_syn
        BR ldw3
fa_num: LDTI 48                 ; a number: decimal, or 0x and hex digits
        BRNEQ pn_d1
        INCR R5
        LDAVR R5
        ORI 32
        LDTI 120
        BREQ fa_hex
        MVIW R3,0               ; a number that starts with 0
        BR pn_lp
fa_hex: INCR R5
        STR R5,TP
        BR parsehex
fa_p:   LDTI 45                 ; - factor
        BRNEQ fa_p1
        INCR R5
        STR R5,TP
        JSR factor
        BR neg16
fa_p1:  LDTI 43                 ; + factor
        BRNEQ fa_p2
        INCR R5
        STR R5,TP
        BR factor
fa_p2:  LDTI 40                 ; ( expression )
        BRNEQ fa_var
        INCR R5
        STR R5,TP
        JSR expr
        PUSHR R3
        LDAI 41
        JSR expect
        POPR R3
        RET
fa_abs: INCR R5
        STR R5,TP
        JSR parget
        MVRHA R3
        ANDI 128
        BRZ rts
        BR neg16
fa_pk:  INCR R5                 ; PEEK(a)
        STR R5,TP
        JSR parget
        LDAVR R3
fa_b:   MVARL R3                ; a byte as the value
        LDAI 0
        MVARH R3
        RET
fa_rnd: INCR R5                 ; RND(n): 1..n, 0 for n = 0
        STR R5,TP
        JSR parget
        JSR tst3
        BRZ rts
        PUSHR R3
        JSR random_
        POPR R4
        JSR divmod
        MOVRR R5,R3
        INCR R3
        RET
fa_len: INCR R5
        STR R5,TP
        JSR sargpar
        LDA SARG
        BR fa_b
fa_asc: INCR R5
        STR R5,TP
        JSR sargpar
        LDA SARG
        BRZ fa_z
        LDA SARG+1
        BR fa_b
fa_val: INCR R5                 ; VAL(s): the string read as a number
        STR R5,TP
        JSR sargpar
        LDA ERR
        BRNZ fa_z
        MVIW R5,SARG+1
        LDA SARG
        JSR adda5
        LDIVR R5,0
        LDR R5,TP
        STR R5,FV_SV
        MVIW R5,SARG+1
        STR R5,TP
        JSR skipsp
        LDTI 45
        BRNEQ fv_1
        INCR R5
        STR R5,TP
        JSR parsedec
        JSR neg16
        BR fv_3
fv_1:   LDTI 43
        BRNEQ fv_2
        INCR R5
        STR R5,TP
fv_2:   JSR parsedec
fv_3:   LDR R5,FV_SV
        STR R5,TP
        RET
fa_eof: INCR R5                 ; EOF(n): 1 unless a file is open for input and has more
        STR R5,TP
        JSR parget
        LDA FMODE
        LDTI 1
        BREQ fe_1
        MVIW R3,1
        RET
fe_1:   LDA FLOOKC
        BR fa_b
; term: factor { * / % factor }
term:   JSR factor
te_lp:  JSR skipsp
        LDTI 42
        BREQ te_mul
        LDTI 47
        BREQ te_div
        LDTI 37
        BREQ te_mod
        RET
te_mul: INCR R5
        STR R5,TP
        PUSHR R3
        JSR factor
        POPR R4
        JSR mul16
        BR te_ck
te_div: INCR R5
        STR R5,TP
        PUSHR R3
        JSR factor
        MOVRR R3,R4
        POPR R3
        JSR divz
        BR te_ck
te_mod: INCR R5
        STR R5,TP
        PUSHR R3
        JSR factor
        MOVRR R3,R4
        POPR R3
        JSR divz
        MOVRR R5,R3
te_ck:  LDA ERR
        BRZ te_lp
        BR fa_z
; expr: term { + - term }
expr:   JSR term
ex_lp:  JSR skipsp
        LDTI 43
        BREQ ex_add
        LDTI 45
        BREQ ex_sub
        RET
ex_add: INCR R5
        STR R5,TP
        PUSHR R3
        JSR term
        POPR R4
        JSR add34
        BR ex_ck
ex_sub: INCR R5
        STR R5,TP
        PUSHR R3
        JSR term
        MOVRR R3,R4
        POPR R3
        JSR sub34
ex_ck:  LDA ERR
        BRZ ex_lp
        BR fa_z
; eval: expr [comparison expr] -> the value, or 1 / 0; strings compare as strings (evalstr)
eval:   JSR speek
        BRNZ evalstr
        JSR expr
        LDA ERR
        BRNZ fa_z
        JSR relopp              ; (keeps R3)
        BRZ rts
        PUSHR R3
        JSR expr
        POPR R4                 ; l in R4, r in R3
        LDA ERR
        BRNZ fa_z
        MVRHA R3                ; a signed compare: the sign bits turned over
        XORI 128
        MVAT
        MVRHA R4
        XORI 128
        BRLT ev_lt
        BRGT ev_gt
        MVRLA R3
        MVAT
        MVRLA R4
        BRLT ev_lt
        BRGT ev_gt
        LDAI 2
        BR ev_r
ev_lt:  LDAI 1
        BR ev_r
ev_gt:  LDAI 4
ev_r:   STA REL
relres: LDA RELM                ; relresult
        MVAT
        LDA REL
        ANDT
        BRZ fa_z
        MVIW R3,1
        RET
evalstr: JSR seval
        LDA ERR
        BRNZ fa_z
        MVIW R3,SACC
        MVIW R4,SCMPB
        JSR smove
        JSR relopp
        BRNZ es_1
        JSR synerr
        BR fa_z
es_1:   JSR seval
        LDA ERR
        BRNZ fa_z
        JSR scmp
        BR relres

; =====================================================================================================================
; The program text: records num[2] (big-endian) text NUL, the end a record numbered 0 (basic.c recnum, nextrec,
; newprog, progend, findline, edit, prtext, list)
; =====================================================================================================================
; curnum: R3 = the current line's number.  recnum: R3 = the number of the record at R5 (R5 kept).
curnum: LDR R5,CURLINE
recnum: LDAVR R5
        MVARH R3
        INCR R5
        LDAVR R5
        MVARL R3
        DECR R5
        RET
; nextrec: R5 = the record after the one at R5
nextrec: INCR R5
        INCR R5
nr_lp:  LDAVR R5
        INCR R5
        BRNZ nr_lp
        RET
newprog: LDAI 0
        STA PROG
        STA PROG+1
        STA VARCNT
        STA SVARCNT
        MVIW R6,VCPAGE          ; and what varget and RUN remember of the variables and the lines
        MVIB R7,0
np_lp:  LDIVR R6,0
        INCR R6
        DECR R7
        MVRLA R7
        BRNZ np_lp
        RET
; gc_clr: RUN's memory of where the lines are is cleared (the program's text moves)
gc_clr: MVIW R6,VCPAGE
        MVIB R7,32
gc_lp:  LDIVR R6,0
        INCR R6
        DECR R7
        MVRLA R7
        BRNZ gc_lp
        RET
; progend: R5 = the end record
progend: MVIW R5,PROG
pe_lp:  JSR recnum
        JSR tst3
        BRZ rts
        JSR nextrec
        BR pe_lp
; findline: the record numbered R3 -> ACC 1 and R5 = it; ACC 0 when there is none. fl_from: the search starts at
; the record at R5 (one whose number is not above R3).
findline: MVIW R5,PROG
fl_from: LDAVR R5
        MVARH R4
        INCR R5
        LDAVR R5
        MVARL R4
        DECR R5
        BRNZ fl_c               ; (ACC = the low byte) the end record: not there
        MVRHA R4
        BRZ ret0
fl_c:   MVRHA R3
        MVAT
        MVRHA R4
        BRGT ret0               ; past it
        BRLT fl_n
        MVRLA R3
        MVAT
        MVRLA R4
        BRGT ret0
        BREQ ret1
fl_n:   JSR nextrec
        BR fl_from
; edit: line LNUM is put in, replaced or (text empty) deleted, in place. R3 = the text.
edit:   STR R3,ED_TXT
        JSR gc_clr
        LDR R4,LNUM
        MVRLA R4
        BRNZ ed_1
        MVRHA R4
        BRNZ ed_1
        MVIW R3,S_BADLN
        BR msgerr
ed_1:   MVIW R5,PROG
ed_f:   JSR recnum              ; the first record not below LNUM
        JSR tst3
        BRZ ed_ins
        MVRHA R4
        MVAT
        MVRHA R3
        BRLT ed_nx
        BRGT ed_ins
        MVRLA R4
        MVAT
        MVRLA R3
        BRLT ed_nx
        BRGT ed_ins
        STR R5,ED_P             ; the old line goes: the rest moves down over it
        JSR nextrec
        MOVRR R5,R4             ; s
        JSR progend
        INCR R5
        INCR R5                 ; e
        LDR R6,ED_P             ; d
ed_d1:  MVRLA R4
        MVAT
        MVRLA R5
        BRNEQ ed_d2
        MVRHA R4
        MVAT
        MVRHA R5
        BREQ ed_d3
ed_d2:  LDAVR R4
        STAVR R6
        INCR R4
        INCR R6
        BR ed_d1
ed_d3:  LDR R5,ED_P
        BR ed_ins
ed_nx:  JSR nextrec
        BR ed_f
ed_ins: STR R5,ED_P             ; p: where the line goes
        LDR R3,ED_TXT
        LDAVR R3
        BRZ rts                 ; a number alone deletes
        MVIW R4,3               ; n = the text's length + 3: num[2] text NUL
ed_n:   LDAVR R3
        BRZ ed_n1
        INCR R3
        INCR R4
        BR ed_n
ed_n1:  JSR progend
        INCR R5
        INCR R5                 ; e = past the end record
        MOVRR R5,R3
        JSR add34               ; d = e + n: must not pass the program area
        MVIW R6,PROGTOP
        MVRHA R6
        MVAT
        MVRHA R3
        BRGT ed_oom
        BRLT ed_ok
        MVRLA R6
        MVAT
        MVRLA R3
        BRGT ed_oom
ed_ok:  LDR R4,ED_P             ; the rest moves up to make room
ed_m:   MVRLA R4
        MVAT
        MVRLA R5
        BRNEQ ed_m1
        MVRHA R4
        MVAT
        MVRHA R5
        BREQ ed_w
ed_m1:  DECR R5
        DECR R3
        LDAVR R5
        STAVR R3
        BR ed_m
ed_w:   LDA LNUM                ; the record: the number, the text, its NUL
        STAVR R5
        INCR R5
        LDA LNUM+1
        STAVR R5
        INCR R5
        LDR R3,ED_TXT
ed_w1:  LDAVR R3
        STAVR R5
        BRZ rts
        INCR R3
        INCR R5
        BR ed_w1
ed_oom: MVIW R3,S_OOM
        BR msgerr
; prtext: the text at R5 through outc, tokens as their keywords; R5 ends at its NUL
prtext: LDAVR R5
        BRZ rts
        LDTI 128
        BRLT pt_c
        JSR prkw
        BR pt_n
pt_c:   JSR outc
pt_n:   INCR R5
        BR prtext
; list: every line, as it would be typed
list:   MVIW R5,PROG
ls_lp:  JSR recnum
        JSR tst3
        BRZ rts
        PUSHR R5
        JSR prlnum
        LDAI 32
        JSR outc
        POPR R5
        INCR R5
        INCR R5
        JSR prtext
        JSR crlf
        INCR R5
        BR ls_lp

; =====================================================================================================================
; Files (basic.c getpath, fprime, gnb, freadrec, fileclose, st_save, loadfile, st_load, st_open)
; =====================================================================================================================
; getpath: a string expression at tp -> PBUF, NUL-terminated; ACC 1 = there is a path
getpath: JSR seval
        LDA ERR
        BRNZ ret0
        MVIW R3,SACC
        LDAVR R3
        MVARL R5
        MVIW R4,PBUF
gp_lp:  MVRLA R5
        BRZ gp_e
        INCR R3
        LDAVR R3
        STAVR R4
        INCR R4
        DECR R5
        BR gp_lp
gp_e:   LDIVR R4,0
        LDA PBUF
        BRNZ ret1
        JSR synerr
        BR ret0
; fprime: the data file's next byte into the lookahead (FLOOK; FLOOKC = 1 at the end)
fprime: LDR R3,FH
        JSR fgetc
        MVRHA R3
        BRZ fp_1
        LDAI 1
        STA FLOOKC
        RET
fp_1:   STA FLOOKC
        MVRLA R3
        STA FLOOK
        RET
; gnb: the next byte of the data file -> R3, 65535 at the end
gnb:    LDA FLOOKC
        BRZ gn_1
        MVIW R3,0FFFFH
        RET
gn_1:   LDA FLOOK
        PUSH
        JSR fprime
        POP
        BR fa_b
; freadrec: one record of the data file (to LF, CR or CR LF) -> SACC, cut at 32 characters, a NUL after it
freadrec: MVIW R4,SACC+1
        MVIW R6,0
rr_lp:  JSR gnb
        MVRHA R3
        BRNZ rr_e
        MVRLA R3
        LDTI 10
        BREQ rr_e
        LDTI 13
        BREQ rr_cr
        MVRLA R6
        LDTI 32
        BRLT rr_st
        BR rr_lp
rr_st:  MVRLA R3
        STAVR R4
        INCR R4
        INCR R6
        BR rr_lp
rr_cr:  LDA FLOOKC              ; CR LF is one end of line
        BRNZ rr_e
        LDA FLOOK
        LDTI 10
        BRNEQ rr_e
        JSR gnb
rr_e:   LDIVR R4,0
        MVRLA R6
        STA SACC
        RET
fileclose: LDA FMODE
        BRZ fc_1
        LDR R3,FH
        JSR fclose
fc_1:   LDAI 0
        STA FMODE
        STA OUTFILE
        RET
; SAVE "file": the program as LIST shows it
st_save: INCR R5
        STR R5,TP
        JSR getpath
        BRZ rts
        MVIW R3,PBUF
        JSR fcreate
        JSR tst3
        BRZ sv_bad
        STR R3,LSAVE
        JSR list
        LDR R3,LSAVE
        MVIW R4,0
        STR R4,LSAVE
        JSR fclose
        JSR tst3
        BRZ sv_bad
        MVIW R3,S_SAVED
        BR outs
sv_bad: MVIW R3,S_CANTSAVE
        BR msgerr
; loadfile: NEW, then each line of the file at R3 as if typed -> ACC 1 = every line went in
loadfile: JSR fopen
        JSR tst3
        BRNZ lf_1
        MVIW R3,S_NOFILE
        JSR outs
        BR ret0
lf_1:   STR R3,LF_H
        JSR newprog
        LDAI 0
        STA LF_BAD
lf_ln:  MVIW R5,LBUF
        MVIW R6,0               ; n
lf_rd:   LDR R3,LF_H
        JSR fgetc
        MVRHA R3
        BRNZ lf_eol
        MVRLA R3
        LDTI 10
        BREQ lf_eol
        LDTI 13
        BREQ lf_eol
        MVRLA R6
        LDTI 98
        BRLT lf_st
        BR lf_rd
lf_st:  MVRLA R3
        STAVR R5
        INCR R5
        INCR R6
        BR lf_rd
lf_eol: LDIVR R5,0
        STR R3,LF_C             ; the byte that ended the line: 65535 = the end of the file
        MVRLA R6
        BRZ lf_nx
        JSR crunch
        LDAI 0
        STA ERR
        JSR checkline
        BRNZ lf_no
        MVIW R5,LBUF
        STR R5,TP
        JSR skipsp
        LDTI 48
        BRLT lf_nn
        LDTI 57
        BRGT lf_nn
        JSR parsedec
        STR R3,LNUM
        JSR skipsp
        MOVRR R5,R3
        JSR edit
        LDA ERR
        BRNZ lf_no
        BR lf_nx
lf_nn:  BRZ lf_nx               ; (ACC = the first character) a line of blanks
        MVIW R3,S_NOLNUM
        JSR outs
        MVIW R3,LBUF
        JSR outs
        JSR crlf
lf_no: LDAI 1
        STA LF_BAD
lf_nx:  LDA LF_C
        BRZ lf_ln
        LDR R3,LF_H
        JSR fclose
        LDAI 0
        STA ERR
        LDA LF_BAD
        BRNZ ret0
        BR ret1
; LOAD "file"
st_load: INCR R5
        STR R5,TP
        JSR getpath
        BRZ rts
        MVIW R3,PBUF
        JSR loadfile
        BRZ ld_1
        MVIW R3,S_LOADED
        JSR outs
ld_1:   LDAI 1                  ; the line it came from is gone
        STA ENDF
        RET
; OPEN "file" FOR OUTPUT | INPUT
st_open: INCR R5
        STR R5,TP
        JSR getpath
        BRZ rts
        JSR fileclose
        JSR skipsp
        LDTI T_FOR
        BRNEQ op_1
        INCR R5
        STR R5,TP
        JSR skipsp
op_1:   LDTI T_OUTPUT
        BRNEQ op_2
        INCR R5
        STR R5,TP
        MVIW R3,PBUF
        JSR fcreate
        STR R3,FH
        JSR tst3
        BRNZ op_1a
        MVIW R3,S_CANTOPEN
        BR msgerr
op_1a:  LDAI 2
        STA FMODE
        RET
op_2:   LDTI T_INPUT
        BRNEQ synerr
        INCR R5
        STR R5,TP
        MVIW R3,PBUF
        JSR fopen
        STR R3,FH
        JSR tst3
        BRNZ op_2a
        MVIW R3,S_NOFILE
        BR msgerr
op_2a:  LDAI 1
        STA FMODE
        BR fprime

; =====================================================================================================================
; Statements (basic.c st_print, st_let, st_gotoN, st_if, st_input, st_poke, st_gosub, st_return, st_for, st_next,
; st_run, st_help, stmt, stmtline). Each is entered with tp at its keyword.
; =====================================================================================================================
; PRINT [item {; | , item}] and PRINT# item
st_print: INCR R5
        STR R5,TP
        JSR skipsp
        LDTI 35
        BREQ pr_f
pr_lp:  JSR skipsp
        BRZ crlf
        LDTI 58
        BREQ crlf
        JSR pr_item
        LDA ERR
        BRNZ rts
        JSR skipsp
        LDTI 59
        BRNEQ pr_1
        INCR R5
        STR R5,TP
        BR pr_2
pr_1:   LDTI 44
        BRNEQ crlf
        INCR R5
        STR R5,TP
        LDAI 32
        JSR putch
pr_2:   JSR skipsp              ; a ; or , at the end keeps the line open
        BRZ rts
        LDTI 58
        BREQ rts
        BR pr_lp
pr_item: JSR speek              ; a string or a number through putch
        BRZ pi_n
        JSR seval
        LDA ERR
        BRNZ rts
        MVIW R3,SACC
        BR sput
pi_n:   JSR eval
        LDA ERR
        BRNZ rts
        BR prdec
pr_f:   LDA FMODE               ; PRINT#: one value and a line feed to the file open for output
        LDTI 2
        BRNEQ synerr
        INCR R5
        STR R5,TP
        LDAI 1
        STA OUTFILE
        JSR skipsp
        LDTI 44
        BRNEQ pf_1
        INCR R5
        STR R5,TP
        JSR skipsp
pf_1:   BRZ pf_2
        JSR pr_item
        LDA ERR
        BRNZ rts
pf_2:   LDR R7,FH
        LDAI 10
        JSR fputc
        LDAI 0
        STA OUTFILE
        RET
; [LET] v = expression, v$ = string expression
s_let:  INCR R5                 ; past LET
        STR R5,TP
        JSR skipsp
st_let: MOVRR R5,R4             ; one character and then = or a blank is not a string's name (the usual case, cheaply)
        INCR R4
        LDAVR R4
        LDTI 61
        BREQ lt_n
        LDTI 32
        BREQ lt_n
        JSR speek
        BRZ lt_n
        JSR svarget
        BRZ synerr
        STR R3,LT_A
        LDAI 61
        JSR expect
        LDA ERR
        BRNZ rts
        JSR seval
        LDA ERR
        BRNZ rts
        MVIW R3,SACC
        LDR R4,LT_A
        BR smove
lt_n:   JSR varget
        BRZ synerr
        STR R3,LT_A
        LDAI 61
        JSR expect
        LDA ERR
        BRNZ rts
        JSR eval
        LDA ERR
        BRNZ rts
        MOVRR R3,R4
        LDR R3,LT_A
        BR stw
; GOTO n (and the n of GOSUB, THEN): the line to go to, for RUN's loop
s_goto: INCR R5
        STR R5,TP
        JSR skipsp
st_gotoN: JSR parsedec
        STR R3,BRANCHN
        LDAI 1
        STA BRANCHF
        RET
; IF expression THEN statements | line number
st_if:  INCR R5
        STR R5,TP
        JSR eval
        LDA ERR
        BRNZ rts
        JSR skipsp
        LDTI T_THEN
        BRNEQ synerr
        INCR R5
        JSR tst3
        BRNZ if_t
if_f:   LDAVR R5                ; false: the rest of the line is skipped
        BRZ if_e
        INCR R5
        BR if_f
if_e:   STR R5,TP
        RET
if_t:   STR R5,TP
        JSR skipsp
        LDTI 48
        BRLT stmtline
        LDTI 57
        BRGT stmtline
        BR st_gotoN
; INPUT ["prompt";] v | v$ and INPUT# v | v$
st_input: INCR R5
        STR R5,TP
        JSR skipsp
        LDTI 35
        BREQ in_f
        LDTI 34
        BRNEQ in_1
        MVIW R4,SACC            ; the prompt
        JSR scpylit
        MVIW R3,SACC
        JSR sput
        JSR skipsp
        LDTI 59
        BREQ in_0
        LDTI 44
        BRNEQ in_1
in_0:   INCR R5
        STR R5,TP
in_1:   JSR speek
        BRZ in_n
        JSR svarget             ; a string: the line as it was typed
        BRZ synerr
        STR R3,IN_A
        LDR R5,TP
        STR R5,IN_SV
        JSR in_ask
        MVIW R3,LBUF
        MVIW R4,SACC+1
        MVIW R6,0
in_c:   LDAVR R3
        BRZ in_ce
        MVRLA R6
        LDTI 32
        BRLT in_c1
        BR in_ce
in_c1:  LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        INCR R6
        BR in_c
in_ce:  MVRLA R6
        STA SACC
in_ss:  LDR R5,IN_SV            ; tp back; the string variable gets SACC
        STR R5,TP
        MVIW R3,SACC
        LDR R4,IN_A
        BR smove
in_n:   JSR varget              ; a number
        BRZ synerr
        STR R3,IN_A
        LDR R5,TP
        STR R5,IN_SV
        JSR in_ask
        MVIW R5,LBUF
in_num: STR R5,TP               ; the number in the text at R5 -> the variable; tp back
        JSR skipsp
        LDTI 45
        BRNEQ in_p
        INCR R5
        STR R5,TP
        JSR parsedec
        JSR neg16
        BR in_st
in_p:   JSR parsedec
in_st:  MOVRR R3,R4
        LDR R5,IN_SV
        STR R5,TP
        LDR R3,IN_A
        BR stw
in_ask: LDAI 63                 ; "? " and a line from the keyboard
        JSR putchr
        LDAI 32
        JSR putchr
        BR getline
in_f:   LDA FMODE               ; INPUT#: one record of the file open for input
        LDTI 1
        BRNEQ synerr
        INCR R5
        STR R5,TP
        JSR skipsp
        LDTI 44
        BRNEQ in_f1
        INCR R5
        STR R5,TP
in_f1:  JSR speek
        BRZ in_fn
        JSR svarget
        BRZ synerr
        STR R3,IN_A
        LDR R5,TP
        STR R5,IN_SV
        JSR freadrec
        BR in_ss
in_fn:  JSR varget
        BRZ synerr
        STR R3,IN_A
        LDR R5,TP
        STR R5,IN_SV
        JSR freadrec
        MVIW R5,SACC+1
        BR in_num
; POKE address, byte
st_poke: INCR R5
        STR R5,TP
        JSR eval
        PUSHR R3
        LDAI 44
        JSR expect
        LDA ERR
        BRZ po_1
        POPR R3
        RET
po_1:   JSR eval
        POPR R4
        MVRLA R3
        STAVR R4
        RET
; GOSUB n: the place after it (the line, the text) on the GOSUB stack, 8 deep
st_gosub: INCR R5
        STR R5,TP
        JSR skipsp
        JSR st_gotoN
        JSR skipsp
        LDTI 58
        BRNEQ gs_1
        INCR R5
        STR R5,TP
gs_1:   LDA GSP
        LDTI 8
        BRLT gs_2
        MVIW R3,S_GSDEEP
        BR msgerr
gs_2:   SHL
        SHL
        MVIW R6,GSTK
        JSR adda6
        LDR R3,CURLINE
        JSR stw6
        MOVRR R5,R3
        JSR stw6
        LDA GSP
        ADDI 1
        STA GSP
        RET
; RETURN
st_return: INCR R5
        STR R5,TP
        LDA GSP
        BRNZ rt_1
        MVIW R3,S_RETNOGS
        BR msgerr
rt_1:   SUBI 1
        STA GSP
        SHL
        SHL
        MVIW R6,GSTK
        JSR adda6
        JSR ldw6
        STR R3,CURLINE
        JSR ldw6
        STR R3,JUMPADDR
        LDAI 2
        STA JUMPF
        RET
; FOR v = a TO b [STEP s]: a frame of five words (the variable, the limit, the step, where the loop's body starts:
; the line and the text), 8 deep
st_for: INCR R5
        STR R5,TP
        JSR skipsp
        JSR varget
        BRZ synerr
        STR R3,FO_A
        LDAI 61
        JSR expect
        LDA ERR
        BRNZ rts
        JSR eval
        LDA ERR
        BRNZ rts
        MOVRR R3,R4
        LDR R3,FO_A
        JSR stw
        JSR skipsp
        LDTI T_TO
        BRNEQ synerr
        INCR R5
        STR R5,TP
        JSR eval
        LDA ERR
        BRNZ rts
        STR R3,FO_LIM
        MVIW R3,1
        STR R3,FO_STEP
        JSR skipsp
        LDTI T_STEP
        BRNEQ fo_1
        INCR R5
        STR R5,TP
        JSR eval
        LDA ERR
        BRNZ rts
        STR R3,FO_STEP
fo_1:   JSR skipsp
        STA FO_C
        LDA RUNNING
        BRNZ fo_2
        MVIW R3,S_FORPROG
        BR msgerr
fo_2:   LDA FO_C
        LDTI 58
        BRNEQ fo_3
        INCR R5                 ; more on this line: the body starts after the :
        MOVRR R5,R4
        LDR R5,CURLINE
        BR fo_4
fo_3:   LDR R5,CURLINE          ; else at the next line
        JSR nextrec
        MOVRR R5,R4
        INCR R4
        INCR R4
fo_4:   LDA FSP
        LDTI 8
        BRLT fo_5
        MVIW R3,S_FORDEEP
        BR msgerr
fo_5:   JSR fsaddr
        LDR R3,FO_A
        JSR stw6
        LDR R3,FO_LIM
        JSR stw6
        LDR R3,FO_STEP
        JSR stw6
        MOVRR R5,R3
        JSR stw6
        MOVRR R4,R3
        JSR stw6
        LDA FSP
        ADDI 1
        STA FSP
        RET
; fsaddr: R6 = the FOR frame numbered ACC (0..7)
fsaddr: MVAT
        SHL
        SHL
        ADDT
        SHL
        MVIW R6,FSTK
        BR adda6
; NEXT [v]: the innermost loop's variable stepped; back to the body until it passes the limit
st_next: INCR R5
        STR R5,TP
        JSR skipsp
        JSR upch
        LDTI 65
        BRLT nx_1
        LDTI 90
        BRGT nx_1
        JSR varget              ; (the name is read, not compared)
nx_1:   LDA FSP
        BRNZ nx_2
        MVIW R3,S_NEXTNOFOR
        BR msgerr
nx_2:   SUBI 1
        JSR fsaddr
        JSR ldw6
        MOVRR R3,R5             ; the variable
        JSR ldw6
        STR R3,NX_LIM
        JSR ldw6                ; the step
        MVRHA R3
        ANDI 128
        STA NX_SG
        MOVRR R3,R4
        MOVRR R5,R3
        JSR ldw3
        JSR add34               ; v = the variable + the step
        MOVRR R3,R4
        MOVRR R5,R3
        JSR stw
        LDR R3,NX_LIM           ; v (R4) against the limit (R3), signed
        MVRHA R3
        XORI 128
        MVAT
        MVRHA R4
        XORI 128
        BRLT nx_lt
        BRGT nx_gt
        MVRLA R3
        MVAT
        MVRLA R4
        BRLT nx_lt
        BRGT nx_gt
        BR nx_go                ; at the limit: once more
nx_lt:  LDA NX_SG               ; below: a loop that counts down is done
        BRNZ nx_fin
        BR nx_go
nx_gt:  LDA NX_SG               ; above: a loop that counts up is done
        BRZ nx_fin
nx_go:  JSR ldw6
        STR R3,CURLINE
        JSR ldw6
        STR R3,JUMPADDR
        LDAI 2
        STA JUMPF
        RET
nx_fin: LDA FSP
        SUBI 1
        STA FSP
        RET
; RUN: the program from its first line; Ctrl-C is looked for before each line
st_run: INCR R5
        STR R5,TP
        LDAI 0
        STA GSP
        STA FSP
        JSR fileclose
        LDAI 1
        STA RUNNING
        MVIW R5,PROG
        STR R5,CURLINE
rn_ln:  LDR R5,CURLINE          ; a line: the end record (number 0) stops the program
        LDAVR R5
        INCR R5
        BRNZ rn_0
        LDAVR R5
        BRZ rn_end
rn_0:   INCR R5
        STR R5,TP
        JSR brk
        BRNZ rn_end
rn_in:  LDAI 0
        STA BRANCHF
        STA JUMPF
        STA ENDF
        JSR stmtline
        LDA ERR
        BRNZ rn_end
        LDA ENDF
        BRNZ rn_end
        LDA JUMPF               ; RETURN, NEXT: on from the place they give
        LDTI 2
        BRNEQ rn_1
        LDR R5,JUMPADDR
        STR R5,TP
        BR rn_in
rn_1:   LDA BRANCHF
        BRNZ rn_go
        LDR R5,TP               ; the next line: the cursor is at this one's NUL
        INCR R5
        STR R5,CURLINE
        BR rn_ln
rn_go:  LDR R3,BRANCHN          ; GOTO, GOSUB, THEN n: where the line was found the last time (VCPAGE: 8 places of
        MVRLA R3                ; number and record, by the number's low bits; all empty after the program changes)
        ANDI 7
        SHL
        SHL
        MVIW R6,VCPAGE
        MVARL R6
        LDAVR R6
        MVAT
        MVRHA R3
        BRNEQ rn_gs
        INCR R6
        LDAVR R6
        MVAT
        MVRLA R3
        BRNEQ rn_gs
        INCR R6
        LDAVR R6
        BRZ rn_gs               ; an empty place (a record's address has no 0 high byte)
        MVARH R5
        INCR R6
        LDAVR R6
        MVARL R5
        STR R5,CURLINE
        BR rn_ln
rn_gs:  JSR curnum              ; the search: from this line on when n is not below it, else from the first
        MOVRR R3,R4
        LDR R3,BRANCHN
        MVRHA R4
        MVAT
        MVRHA R3
        BRLT rn_g0
        BRGT rn_g1
        MVRLA R4
        MVAT
        MVRLA R3
        BRLT rn_g0
rn_g1:  JSR fl_from
        BR rn_g2
rn_g0:  JSR findline
rn_g2:  BRZ rn_und
        STR R5,CURLINE
        MVRLA R3                ; remembered
        ANDI 7
        SHL
        SHL
        MVIW R6,VCPAGE
        MVARL R6
        JSR stw6
        MOVRR R5,R3
        JSR stw6
        BR rn_ln
rn_und: MVIW R3,S_UNDEF
        JSR outs
        LDR R3,BRANCHN
        JSR prdecu
        MVIW R3,S_IN
        JSR outs
        JSR curnum
        JSR prdecu
        JSR crlf
rn_end: LDA ENDF
        LDTI 2
        BREQ rts                ; BYE in a program
        JSR fileclose
        LDAI 0
        STA RUNNING
        LDAI 1
        STA ENDF
        LDA ERR
        BRNZ rts
        MVIW R3,S_OK
        BR outs
; the short statements
s_rem:                          ; REM: the rest of the line
sr_lp:  LDAVR R5
        BRZ sr_e
        INCR R5
        BR sr_lp
sr_e:   STR R5,TP
        RET
s_end:  INCR R5
        STR R5,TP
        LDAI 1
        STA ENDF
        RET
s_list: INCR R5
        STR R5,TP
        BR list
s_new:  INCR R5
        STR R5,TP
        JSR newprog
        LDAI 1
        STA ENDF
        RET
s_close: INCR R5
        STR R5,TP
        BR fileclose
s_bye:  LDAI 2
        STA ENDF
        RET
st_help: INCR R5
        STR R5,TP
        MVIW R3,S_HELP
        BR outs
; stmt: one statement at tp. A token goes through STTAB, a letter is an assignment. A statement's routine is entered
; with R5 = tp, at its keyword.
stmt:   JSR skipsp
        BRZ rts
        LDTI 128
        BRLT sm_ch
        LDTI 165
        BRLT sm_tk
        BR synerr
sm_tk:  SHL                     ; 2 x (the token - 128): its place in STTAB, which is at $5004
        ADDI 4
        MVIW R6,STTAB
        MVARL R6
        BRVR R6
sm_ch:  LDTI 65
        BRLT synerr
        LDTI 91
        BRLT st_let
        LDTI 97
        BRLT synerr
        LDTI 123
        BRLT st_let
        BR synerr
; stmtline: statements separated by : to the end of the line, or until one ends or leaves the line
stmtline: JSR stmt
        LDA ERR
        BRNZ rts
        LDA ENDF
        BRNZ rts
        LDA BRANCHF
        BRNZ rts
        LDA JUMPF
        BRNZ rts
        JSR skipsp
        BRZ rts
        LDTI 58
        BRNEQ synerr
        INCR R5
        STR R5,TP
        BR stmtline

; =====================================================================================================================
; Tables and text
; =====================================================================================================================
; the keywords in token order (128 = PRINT ... 164 = EOF), 8 bytes each, a 0 after the last
KWTAB:  DB 'PRINT',0,0,0
        DB 'LET',0,0,0,0,0
        DB 'IF',0,0,0,0,0,0
        DB 'THEN',0,0,0,0
        DB 'FOR',0,0,0,0,0
        DB 'TO',0,0,0,0,0,0
        DB 'NEXT',0,0,0,0
        DB 'GOTO',0,0,0,0
        DB 'GOSUB',0,0,0
        DB 'RETURN',0,0
        DB 'INPUT',0,0,0
        DB 'REM',0,0,0,0,0
        DB 'END',0,0,0,0,0
        DB 'RUN',0,0,0,0,0
        DB 'LIST',0,0,0,0
        DB 'NEW',0,0,0,0,0
        DB 'ABS',0,0,0,0,0
        DB 'RND',0,0,0,0,0
        DB 'PEEK',0,0,0,0
        DB 'POKE',0,0,0,0
        DB 'STEP',0,0,0,0
        DB 'BYE',0,0,0,0,0
        DB 'HELP',0,0,0,0
        DB 'SAVE',0,0,0,0
        DB 'LOAD',0,0,0,0
        DB 'CHR$',0,0,0,0
        DB 'LEFT$',0,0,0
        DB 'RIGHT$',0,0
        DB 'MID$',0,0,0,0
        DB 'LEN',0,0,0,0,0
        DB 'ASC',0,0,0,0,0
        DB 'OPEN',0,0,0,0
        DB 'CLOSE',0,0,0
        DB 'OUTPUT',0,0
        DB 'STR$',0,0,0,0
        DB 'VAL',0,0,0,0,0
        DB 'EOF',0,0,0,0,0
        DB 0
S_USAGE:    DB 'usage: basic [file] | basic -r file   (BYE or Ctrl-D: back to the shell)',0
S_USAGER:   DB 'usage: basic -r file',0
S_BANNER:   DB 'Y1 BASIC  ',0
S_BANNER2:  DB ' bytes for the program',10,0
S_PROMPT:   DB '> ',0
S_ONLY:     DB '?ONLY IN A PROGRAM',10,0
S_BREAK:    DB 'BREAK IN ',0
S_SYN:      DB '?SYNTAX ERROR',10,0
S_SYNIN:    DB '?SYNTAX ERROR IN ',0
S_TMV:      DB '?TOO MANY VARIABLES',10,0
S_TMS:      DB '?TOO MANY STRINGS',10,0
S_BADLN:    DB '?BAD LINE NUMBER',10,0
S_OOM:      DB '?OUT OF MEMORY',10,0
S_CANTSAVE: DB '?CANNOT SAVE',10,0
S_SAVED:    DB 'Saved',10,0
S_NOFILE:   DB '?NO FILE',10,0
S_LOADED:   DB 'Loaded',10,0
S_NOLNUM:   DB '?NO LINE NUMBER: ',0
S_CANTOPEN: DB '?CANNOT OPEN',10,0
S_GSDEEP:   DB '?GOSUB TOO DEEP',10,0
S_RETNOGS:  DB '?RETURN WITHOUT GOSUB',10,0
S_FORPROG:  DB '?FOR ONLY IN A PROGRAM',10,0
S_FORDEEP:  DB '?FOR TOO DEEP',10,0
S_NEXTNOFOR: DB '?NEXT WITHOUT FOR',10,0
S_UNDEF:    DB '?UNDEF',39,'D LINE ',0
S_IN:       DB ' IN ',0
S_OK:       DB 'Ok',10,0
S_HELP:     DB 'STATEMENTS: PRINT LET IF/THEN FOR/TO/STEP NEXT GOTO GOSUB RETURN',10
            DB '  INPUT [',34,'prompt',34,59,'] POKE REM END   several on a line with :',10
            DB 'COMMANDS: RUN LIST NEW SAVE ',34,'f',34,' LOAD ',34,'f',34,' HELP BYE (or Ctrl-D)',10
            DB 'FILES: OPEN ',34,'f',34,' FOR OUTPUT|INPUT  PRINT# x  INPUT# x  EOF(1)  CLOSE',10
            DB 'FUNCTIONS: ABS(x) RND(n) PEEK(a) LEN ASC VAL CHR$ LEFT$ RIGHT$ MID$ STR$',10
            DB 'NUMBERS: integers -32768..32767, 0x1F hex  OPERATORS: + - * / %',10
            DB '  = <> < > <= >=   STRINGS: A$ (up to 32 chars), + joins',10
            DB 'Ctrl-C stops a running program. man basic for more.',10,0

; =====================================================================================================================
; Variables. ZBEG..ZEND is cleared at the start; the program area and the stack follow it.
; =====================================================================================================================
OSSP:   DS 2                    ; the shell's stack pointer
ZBEG:
TP:     DS 2                    ; the parse cursor
CURLINE: DS 2                   ; RUN: the current line's record
JUMPADDR: DS 2                  ; RETURN, NEXT: the text to go on at
STRSP:  DS 2                    ; STR$: where putch writes
BRANCHN: DS 2                   ; GOTO: the line number
LNUM:   DS 2                    ; the number of the line entered
SEED:   DS 2
FH:     DS 2                    ; the data file's handle
LSAVE:  DS 2                    ; SAVE: LIST's output goes to this handle
ERR:    DS 1                    ; an error unwound the statement
RUNNING: DS 1
ENDF:   DS 1                    ; 1: the line or the program ends; 2: BYE
BRANCHF: DS 1
JUMPF:  DS 1
GSP:    DS 1
FSP:    DS 1
VARCNT: DS 1
SVARCNT: DS 1
FMODE:  DS 1                    ; the data file: 0 closed, 1 input, 2 output
OUTFILE: DS 1                   ; PRINT# is writing
STRSINK: DS 1                   ; STR$ is writing
STRSN:  DS 1
FLOOK:  DS 1                    ; the data file's next byte
FLOOKC: DS 1                    ; 1: there is none
RELM:   DS 1                    ; the comparison asked for
REL:    DS 1                    ; the comparison found
REDIR:  DS 1                    ; stdin is a file or a pipe: no echo
EOFIN:  DS 1                    ; Ctrl-D / the end of the input
PENDF:  DS 1                    ; a key brk read that was not Ctrl-C ...
PENDC:  DS 1                    ; ... and the key
RUNIT:  DS 1                    ; basic -r
KWLEN:  DS 1
KW_C0:  DS 1
KW_T:   DS 2
OC_C:   DS 1
GL_C:   DS 1
EX_C:   DS 1
PN_D:   DS 1
DD_D:   DS 1
DD_NZ:  DS 1
DBUF:   DS 6
VF_N:   DS 1
SA_M:   DS 1
SA_N:   DS 1
SG_D:   DS 2
SB_L:   DS 1
TM_I:   DS 1
FV_SV:  DS 2
ED_TXT: DS 2
ED_P:   DS 2
LF_H:   DS 2
LF_C:   DS 2
LF_BAD: DS 1
LT_A:   DS 2
IN_A:   DS 2
IN_SV:  DS 2
FO_A:   DS 2
FO_LIM: DS 2
FO_STEP: DS 2
FO_C:   DS 1
NX_LIM: DS 2
NX_SG:  DS 1
LBUF:   DS 100                  ; the input line
NMBUF:  DS 6                    ; a name, upper case, blank-padded
GSTK:   DS 32                   ; the GOSUB frames: line record, text
FSTK:   DS 80                   ; the FOR frames
VTAB:   DS 256                  ; 32 variables: name[6] value[2]
SVTAB:  DS 640                  ; 16 strings: name[6] [len][32] and a spare byte
SACC:   DS 40                   ; the string work buffers: [len][characters]
STMP:   DS 40
SARG:   DS 40
SCMPB:  DS 40
PBUF:   DS 52                   ; a path
NAME:   DS 52                   ; the file named on the command line
ZEND:
ZLEN:   EQU ZEND-ZBEG
VCPAD:  DS (256-(VCPAD).0)&255 ; to a page's start
VCPAGE: DS 256                  ; 0..31: RUN's 8 lines (number, record); 130..181: the one-letter variables' addresses
PROG:   DS PROGSZ               ; the program
PROGTOP: EQU PROG+PROGSZ
STACK:  DS STKSZ
STKTOP: EQU STACK+STKSZ-1
