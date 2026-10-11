; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
;
; vram.asm - video card bring-up (2026-10-10): the whole 2K of display RAM the CPU reaches ($D000-$D7FF), not only the
; 1K the bus-tester test covers. Four passes, each writes every byte then reads every byte back:
;   pass 0: lo XOR hi of the address (a stuck or swapped address line A0-A10 changes the pattern somewhere)
;   pass 1: the same inverted (every data bit both ways)
;   pass 2: $55   pass 3: $AA
; The first 8 errors of a pass are printed as "AAAA GOT XX EXP YY"; each pass ends "PASS n ERRORS eeee".
; Runs at full speed with the CRTC reading the other port of the IDT7134 (if fitted): a failure only at speed and
; only with the 6845 running points at the dual-port arbitration. Load: tools/monload.py --go 3000 vram.img.
; Registers: R7 address, R5 error count; no R2 (the hidden operand register). Hex as numbers: the assembler
; upper-cases every line.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showr7:     EQU 0ffd4h
showbytea:  EQU 0ffe0h
VRAM:       EQU 0d000h

        ORG 3000h
start:  MVIW R7,s_head
        JSR stringout
        LDAI 0
        STA pass
ploop:  LDA pass                    ; the pass's mask: 00, FF, then fixed patterns 55, AA
        LDTI 0
        BREQ m0
        LDTI 1
        BREQ m1
        LDTI 2
        BREQ m2
        LDAI 0aah
        STA fixed
        LDAI 1
        STA isfix
        BR mset
m0:     LDAI 0
        STA mask
        STA isfix
        BR mset
m1:     LDAI 0ffh
        STA mask
        LDAI 0
        STA isfix
        BR mset
m2:     LDAI 055h
        STA fixed
        LDAI 1
        STA isfix
mset:
; ---- write every byte
        MVIW R7,VRAM
wloop:  JSR patt
        STAVR R7
        INCR R7
        MVRHA R7
        LDTI 0d8h
        BRNEQ wloop
; ---- read every byte back
        MVIW R5,0
        MVIW R7,VRAM
rloop:  JSR patt
        STA expv
        LDAVR R7
        STA gotv
        LDT expv
        BREQ rok
        INCR R5
        MVRHA R5                    ; print the first 8 errors only
        BRNZ rok
        MVRLA R5
        LDTI 8
        BRGT rok                    ; ACC > 8: not printed
        STR R7,addr
        JSR showr7                  ; the address (R7)
        MVIW R7,s_got
        JSR stringout
        LDA gotv
        JSR showbytea
        MVIW R7,s_exp
        JSR stringout
        LDA expv
        JSR showbytea
        JSR crlf
        LDR R7,addr
rok:    INCR R7
        MVRHA R7
        LDTI 0d8h
        BRNEQ rloop
; ---- pass summary
        MVIW R7,s_pass
        JSR stringout
        LDA pass
        JSR showbytea
        MVIW R7,s_err
        JSR stringout
        MOVRR R5,R7
        JSR showr7
        JSR crlf
        LDA pass
        ADDI 1
        STA pass
        LDTI 4
        BRNEQ ploop
        MVIW R7,s_done
        JSR stringout
        RET

; patt: ACC = the pass's byte for the address in R7
patt:   LDA isfix
        BRZ pvar
        LDA fixed
        RET
pvar:   MVRLA R7
        STA tlo
        MVRHA R7
        LDT tlo
        XORT
        LDT mask
        XORT
        RET

crlf:   LDAI 13
        JSR charout
        LDAI 10
        JSR charout
        RET

pass:   DB 0
mask:   DB 0
fixed:  DB 0
isfix:  DB 0
tlo:    DB 0
expv:   DB 0
gotv:   DB 0
addr:   DW 0
s_head: DB 13,10,"VRAM TEST D000-D7FF, 4 PASSES",13,10,0
s_got:  DB " GOT ",0
s_exp:  DB " EXP ",0
s_pass: DB "PASS ",0
s_err:  DB " ERRORS ",0
s_done: DB "VRAM DONE",13,10,0
