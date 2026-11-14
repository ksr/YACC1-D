; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; v40scr.asm - the V4 ROM's screen driver on the emulators (2026-11-14; firmware/monitor/monitor.asm's V4 build):
; the video unit started through the entry at $FFBC, the console mirrored to the screen, 30 lines printed - each with
; lower case, which the V4 driver stores as it comes - so that the screen of 25 rows scrolls six times, then "end"
; with no line end: the cursor stands at row 24, column 3. The mirror is then turned off and the 6845's cursor
; registers are read back through the ports: R14/R15 = (24 * 80 + 3) / 2 = $03C1, and the odd bit is CURH in control
; 2 (which only the emulator's -V line shows: the card cannot read it back).
; tests/video/v40/run.py checks the -V screen: lines 07 to 1E on rows 0-23, "end" on row 24.
; Load: the monitor's : loader, then G3000. No R2.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showbytea:  EQU 0ffe0h
vidctl:     EQU 0ffbch
VIDMIR:     EQU 0ff1h

        ORG 3000h
start:  LDAI 1                      ; V I: the control registers, the 6845's table, clear, home
        JSR vidctl
        LDAI 1
        STA VIDMIR
        LDAI 1
        STA cval
lloop:  MVIW R7,s_line
        JSR stringout
        LDA cval
        JSR showbytea
        MVIW R7,s_text
        JSR stringout
        LDA cval
        ADDI 1
        STA cval
        LDTI 31
        BRNEQ lloop
        MVIW R7,s_end
        JSR stringout
        LDAI 0
        STA VIDMIR
        MVIW R7,s_cur
        JSR stringout
        OUTI PA,14
        INP PB
        JSR showbytea
        LDAI 32
        JSR charout
        OUTI PA,15
        INP PB
        JSR showbytea
        MVIW R7,s_done
        JSR stringout
        RET

cval:   DB 0
s_line: DB 108,105,110,101,32,0             ; "line "
; (the assembler makes every source line upper case, a string's text with it: the lower-case text as numbers)
s_text: DB 32,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111
        DB 112,113,114,115,116,117,118,119,120,121,122,32,123,124,125,126,13,10,0   ; "abcdefghijklmnopqrstuvwxyz {|}~"
s_end:  DB 101,110,100,0                    ; "end"
s_cur:  DB 13,10,"CUR ",0
s_done: DB 13,10,"DONE",13,10,0
