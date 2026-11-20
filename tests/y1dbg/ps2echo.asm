; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; ps2echo.asm - what the video card V4's PS/2 controller hands the CPU, printed (2026-11-20; tests/y1dbg/run.py, the
; case ps2: the debugger's `ps2 key` and `ps2 mouse`). The mouse is turned on (OUT PD $04), "MOUSE ON" printed, and
; then every byte is taken as the driver rule says - IN PE only after IN PD showed FULL - and printed with where it
; came from (IN PD bit 1, SRC): K and its two hex digits for a keyboard byte, M for a mouse byte, a blank after each.
; The key q ends it: "DONE". Load: the monitor's : loader (or y1ucemu -f), then G3000. No R2.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showbytea:  EQU 0ffe0h

        ORG 3000h
start:  OUTI PD,04h
        MVIW R7,s_on
        JSR stringout
loop:   INP PD
        ANDI 1
        BRZ loop
        INP PD
        ANDI 2
        STA src
        BRZ key
        LDAI 77
        BR show
key:    LDAI 75
show:   JSR charout
        INP PE
        STA last
        JSR showbytea
        LDAI 32
        JSR charout
        LDA src
        BRNZ loop
        LDA last
        LDTI 113
        BRNEQ loop
        MVIW R7,s_done
        JSR stringout
        RET
src:    DB 0
last:   DB 0
s_on:   DB 13,10,"MOUSE ON",13,10,0
s_done: DB "DONE",13,10,0
