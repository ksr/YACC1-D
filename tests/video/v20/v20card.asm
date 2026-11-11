; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; v20card.asm - the video card V2.0's CPU side on the emulators (2026-11-10): Y1VID_CARD=v2.0, software/videomodel.h.
; Every register is on an I/O port (docs/cards/video-v2.md): PA/PB the 6845, PC control (OUT) / status (IN), PD/PE
; the PS/2 controller; the graphics window $D800-$DFFF reaches 2K of the 62256 at CPAGE * 16K + PLANE * 2K.
;   STATUS  IN PC before the 6845 is set up: $5x (card ID), bit 0 DOTS, bit 3 TEXT-ONLY, VSYNC = DE = 0
;   CRTC    R14 <- 15, R15 <- A5 through OUT PA / OUT PB, read back through IN PB
;   GFX     the 16 plane/page pairs (control 00-0F): $D800 <- 40+c, $DFFF <- 80+c, then all read back; the error count
;           (0 with the graphics chips, 32 on the text-only build: the window floats), $D800 with control 0B, and
;           the text RAM's $D000 untouched (54)
;   VSYNC   the 6845 set up with the MDA table (R0-R9 = 80 64 68 10 45 2 32 39 0 7, 18.52 kHz / 50.05 Hz at 8 dots):
;           polls of IN PC from one VSYNC rise to the next (a frame) and while VSYNC is high (16 scan lines)
;   DE      256 polls of IN PC: how many saw DE high
;   KEYS    OUT PD 01; three bytes typed on the keyboard, each read after IN PD showed FULL; then IN PD: FULL again,
;           the next byte typed (the monitor's 0) already loaded (the latch's last byte with FULL clear: model_test.c)
; Load: the monitor's : loader, then G3000. No R2.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showr7:     EQU 0ffd4h
showbytea:  EQU 0ffe0h

        ORG 3000h
start:  MVIW R7,s_head
        JSR stringout
; ---- STATUS
        MVIW R7,s_st
        JSR stringout
        INP PC
        JSR showbytea
        JSR crlf
; ---- CRTC: R14/R15 through the ports
        MVIW R7,s_crtc
        JSR stringout
        OUTI PA,14
        OUTI PB,15h
        OUTI PA,15
        OUTI PB,0a5h
        OUTI PA,14
        INP PB
        JSR showbytea
        JSR space
        OUTI PA,15
        INP PB
        JSR showbytea
        JSR crlf
; ---- GFX: 16 plane/page pairs
        LDAI 54h
        STA 0d000h
        LDAI 0
        STA cval
wloop:  LDA cval
        OUTA PC
        LDA cval
        ADDI 40h
        STA 0d800h
        LDA cval
        ADDI 80h
        STA 0dfffh
        LDA cval
        ADDI 1
        STA cval
        LDTI 16
        BRNEQ wloop
        LDAI 0
        STA cval
        STA errs
rloop:  LDA cval
        OUTA PC
        LDA cval
        ADDI 40h
        STA expv
        LDA 0d800h
        LDT expv
        BREQ r1
        LDA errs
        ADDI 1
        STA errs
r1:     LDA cval
        ADDI 80h
        STA expv
        LDA 0dfffh
        LDT expv
        BREQ r2
        LDA errs
        ADDI 1
        STA errs
r2:     LDA cval
        ADDI 1
        STA cval
        LDTI 16
        BRNEQ rloop
        MVIW R7,s_gfx
        JSR stringout
        LDA errs
        JSR showbytea
        JSR space
        OUTI PC,0bh
        LDA 0d800h
        JSR showbytea
        JSR space
        LDA 0d000h
        JSR showbytea
        OUTI PC,0
        JSR crlf
; ---- VSYNC: the MDA table, then a frame and the pulse in polls
        MVIW R6,mda
        LDAI 0
        STA cval
tloop:  LDA cval
        OUTA PA
        LDAVR R6
        OUTA PB
        INCR R6
        LDA cval
        ADDI 1
        STA cval
        LDTI 10
        BRNEQ tloop
v0:     INP PC                      ; wait for VSYNC low, then the rise
        ANDI 2
        BRNZ v0
v1:     INP PC
        ANDI 2
        BRZ v1
        MVIW R5,0                   ; the polls while it is high
v2:     INCR R5
        INP PC
        ANDI 2
        BRNZ v2
        STR R5,pulse
        MVIW R5,0                   ; then on to the next rise: R5 + pulse = a frame
v3:     INCR R5
        INP PC
        ANDI 2
        BRZ v3
        MVIW R7,s_vs
        JSR stringout
        LDR R7,pulse
        JSR showr7
        JSR space
        MOVRR R5,R7
        JSR showr7
        JSR crlf
; ---- DE: 256 polls
        MVIW R5,0
        LDAI 0
        STA cval
dloop:  INP PC
        ANDI 4
        BRZ d1
        INCR R5
d1:     LDA cval
        ADDI 1
        STA cval
        BRNZ dloop
        MVIW R7,s_de
        JSR stringout
        MOVRR R5,R7
        JSR showr7
        JSR crlf
; ---- KEYS
        MVIW R7,s_kbd
        JSR stringout
        OUTI PD,1                   ; interrupts on (the model keeps INTREQ)
        LDAI 3
        STA cval
kloop:  INP PD
        ANDI 1
        BRZ kloop
        INP PE
        JSR showbytea
        JSR space
        LDA cval
        SUBI 1
        STA cval
        BRNZ kloop
        INP PD
        JSR showbytea
        JSR crlf
        MVIW R7,s_done
        JSR stringout
        RET

space:  LDAI 32
        JSR charout
        RET
crlf:   LDAI 13
        JSR charout
        LDAI 10
        JSR charout
        RET

cval:   DB 0
errs:   DB 0
expv:   DB 0
pulse:  DW 0
mda:    DB 80,64,68,10,45,2,32,39,0,7
s_head: DB 13,10,"V2.0 CARD",13,10,0
s_st:   DB "STATUS ",0
s_crtc: DB "CRTC ",0
s_gfx:  DB "GFX ",0
s_vs:   DB "VSYNC ",0
s_de:   DB "DE ",0
s_kbd:  DB "KEYS ",0
s_done: DB "DONE",13,10,0
