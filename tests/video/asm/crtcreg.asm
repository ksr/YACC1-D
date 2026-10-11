; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
;
; crtcreg.asm - video card bring-up (2026-10-10): the 6845 register interface, after the RS-to-A1 bench fix
; (address register $D800, data register $D802; hardware/cards/video/docs/fix-6845-register-select.md).
;   LATCH   the JP1 read-back latch at the odd addresses $D801/$D803 (reads $FF with nothing jumpered)
;   R14     cursor high (6 bits, readable on every 6845): 00 3F 15 2A 12 written and read back
;   R15     cursor low (8 bits, readable): 00 FF 55 AA 34
;   REPEAT  256 write/read pairs of R15 back to back at full speed: review finding 6.1 - the E one-shot's C1 has no
;           charging path, so the FIRST accesses may work and later ones fail; prints the failure count
;   R12/R13 written 12/34 and read: 00 00 on Motorola's MC6845 (write-only there), 12 34 on parts that read them
; Every line ends OK or BAD. All BAD with 00 or FF read back = no -CS, RS still on A0, or no E (docs/cards/video.md 4).
; Load: tools/monload.py --go 3000 crtcreg.img. Never writes an odd address above $D800 (the latch drives the bus
; even on a write, finding 6.4). No R2. Hex as numbers: the assembler upper-cases every source line.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showr7:     EQU 0ffd4h
showbytea:  EQU 0ffe0h
VCRTCA:     EQU 0d800h
VCRTCD:     EQU 0d802h

        ORG 3000h
start:  MVIW R7,s_head
        JSR stringout
; ---- the JP1 latch
        MVIW R7,s_latch
        JSR stringout
        LDA 0d801h
        JSR showbytea
        LDAI 32
        JSR charout
        LDA 0d803h
        JSR showbytea
        JSR crlf
; ---- R14: 6 bits
        MVIW R7,s_r14
        JSR stringout
        LDAI 14
        STA reg
        LDAI 03fh
        STA rmask
        MVIW R6,t14
        JSR wrlist
; ---- R15: 8 bits
        MVIW R7,s_r15
        JSR stringout
        LDAI 15
        STA reg
        LDAI 0ffh
        STA rmask
        MVIW R6,t15
        JSR wrlist
; ---- 256 back-to-back accesses of R15
        MVIW R7,s_rep
        JSR stringout
        MVIW R5,0
        LDAI 0
        STA val
reploop: LDAI 15
        STA VCRTCA
        LDA val
        STA VCRTCD
        LDAI 15
        STA VCRTCA
        LDA VCRTCD
        LDT val
        BREQ repok
        INCR R5
repok:  LDA val
        ADDI 1
        STA val
        BRNZ reploop
        MOVRR R5,R7
        JSR showr7
        MVIW R7,s_fails
        JSR stringout
        MVRLA R5
        BRZ repgood
        MVIW R7,s_bad
        BR repend
repgood: MVIW R7,s_ok
repend: JSR stringout
; ---- R12/R13
        MVIW R7,s_r12
        JSR stringout
        LDAI 12
        STA VCRTCA
        LDAI 012h
        STA VCRTCD
        LDAI 13
        STA VCRTCA
        LDAI 034h
        STA VCRTCD
        LDAI 12
        STA VCRTCA
        LDA VCRTCD
        JSR showbytea
        LDAI 32
        JSR charout
        LDAI 13
        STA VCRTCA
        LDA VCRTCD
        JSR showbytea
        MVIW R7,s_r12n
        JSR stringout
        LDAI 12                     ; put the start address back to 0
        STA VCRTCA
        LDAI 0
        STA VCRTCD
        LDAI 13
        STA VCRTCA
        LDAI 0
        STA VCRTCD
        MVIW R7,s_done
        JSR stringout
        RET

; wrlist: for each byte of the list at R6 (5 entries): write it to register `reg`, read it back, mask with `rmask`,
; print "ww>rr", then OK or BAD for the register
wrlist: LDAI 0
        STA nbad
        LDAI 5
        STA cnt
wrl:    LDAVR R6
        STA val
        LDA reg
        STA VCRTCA
        LDA val
        STA VCRTCD
        LDA reg
        STA VCRTCA
        LDA VCRTCD
        LDT rmask
        ANDT
        STA got
        LDA val
        JSR showbytea
        LDAI '>'
        JSR charout
        LDA got
        JSR showbytea
        LDAI 32
        JSR charout
        LDA val
        LDT rmask
        ANDT
        LDT got
        BREQ wrok
        LDA nbad
        ADDI 1
        STA nbad
wrok:   INCR R6
        LDA cnt
        SUBI 1
        STA cnt
        BRNZ wrl
        LDA nbad
        BRZ wrgood
        MVIW R7,s_bad
        BR wrend
wrgood: MVIW R7,s_ok
wrend:  JSR stringout
        RET

crlf:   LDAI 13
        JSR charout
        LDAI 10
        JSR charout
        RET

reg:    DB 0
rmask:  DB 0
val:    DB 0
got:    DB 0
cnt:    DB 0
nbad:   DB 0
t14:    DB 00h,3fh,15h,2ah,12h
t15:    DB 00h,0ffh,55h,0aah,34h
s_head: DB 13,10,"CRTC REGISTER TEST: ADDRESS D800, DATA D802",13,10,0
s_latch: DB "LATCH D801 D803: ",0
s_r14:  DB "R14 ",0
s_r15:  DB "R15 ",0
s_rep:  DB "REPEAT R15 X256: ",0
s_fails: DB " FAILED",0
s_r12:  DB "R12 R13 READ: ",0
s_r12n: DB " (00 00 ON MC6845)",13,10,0
s_ok:   DB " OK",13,10,0
s_bad:  DB " BAD",13,10,0
s_done: DB "CRTC TEST DONE",13,10,0
