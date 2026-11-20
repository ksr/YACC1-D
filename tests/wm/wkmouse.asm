; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; wkmouse.asm - a program of the window kernel (os/wm/wmk.asm at $C000): the video card V4's mouse moves the
; pointer on a desktop in dots (2026-11-20; BACKLOG.md, "The P8X's desktop on this machine", steps 2 and 3)
;
; wk_init, a desktop drawn by wk_script, the pointer shown; then wk_event in a loop:
;   1 a key      q or Q ends the program; any other is ignored
;   3 a button   the left one going down inverts the cell the pointer's top left dot is in (the pointer hidden
;                meanwhile)
;   2, 4, 0      nothing to do: the kernel has moved the pointer already
; At the end wk_done, and the place, the buttons and the packets the kernel counted are printed:
; X hhhh Y hhhh B hh N hh. tests/wm/run.py loads the kernel and this, runs them on both emulators with a script of
; packets (Y1VID_MOUSE), and holds the picture and that line to the same script worked out in Python. `run.py --try`
; opens them in the browser debugger, where the browser's mouse is the card's.
; Load: the kernel and this with the monitor's : loader, then G3000. No R2.
;
stringout:  EQU 0ffc0h
showbytea:  EQU 0ffe0h
        INCLUDE wkabi.inc

        ORG 3000h
start:  JSR wk_init
        MVIW R3,scene
        STR R3,WK_S
        JSR wk_script
        JSR wk_show
ev:     JSR wk_event
        BRZ ev
        LDTI 1
        BREQ key
        LDTI 3
        BRNEQ ev
        LDA MS_DN               ; the left button down: its cell inverted
        ANDI 1
        BRZ ev
        JSR wk_hide
        LDA MS_X+1              ; the column: x >> 3
        SHR
        SHR
        SHR
        MVAT
        LDA MS_X
        SHL
        SHL
        SHL
        SHL
        SHL
        ORT
        STA WK_X
        LDA MS_Y+1              ; the row: y >> 4
        SHR
        SHR
        SHR
        SHR
        MVAT
        LDA MS_Y
        SHL
        SHL
        SHL
        SHL
        ORT
        STA WK_Y
        LDAI 1
        STA WK_W
        STA WK_H
        JSR wk_inv
        JSR wk_show
        BR ev
key:    LDA EV_KEY
        LDTI 113
        BREQ quit
        LDTI 81
        BREQ quit
        BR ev

quit:   JSR wk_done
        MVIW R7,s_x
        JSR stringout
        LDA MS_X
        JSR showbytea
        LDA MS_X+1
        JSR showbytea
        MVIW R7,s_y
        JSR stringout
        LDA MS_Y
        JSR showbytea
        LDA MS_Y+1
        JSR showbytea
        MVIW R7,s_b
        JSR stringout
        LDA MS_B
        JSR showbytea
        MVIW R7,s_n
        JSR stringout
        LDA MS_CNT
        JSR showbytea
        MVIW R7,s_nl
        JSR stringout
        RET

s_x:    DB 13,10,"X ",0
s_y:    DB " Y ",0
s_b:    DB " B ",0
s_n:    DB " N ",0
s_nl:   DB 13,10,0

; the scene (wk.inc's script)
scene:  DB 1,0,0,80,25,0aah,055h
        DB 1,0,0,80,1,0ffh,0ffh
        DB 2,0,0,80,1
        DB 3,2,0,0ffh,'YACC1   Mouse',0
        DB 1,14,4,52,9,0ffh,0ffh
        DB 1,14,4,52,1,0ffh,000h
        DB 2,14,4,52,9
        DB 3,34,4,0ffh,' The mouse ',0
        DB 3,16,6,0ffh,'Move the mouse: the arrow follows it.',0
        DB 3,16,8,0ffh,'The left button inverts the cell under the',0
        DB 3,16,9,0ffh,'tip of the arrow.',0
        DB 3,16,11,0ffh,'The key q ends this.',0
        DB 0
scend:
