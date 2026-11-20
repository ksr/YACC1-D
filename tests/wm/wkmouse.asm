; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; wkmouse.asm - the video card V4's mouse moving the pointer on a desktop in dots (2026-11-20; BACKLOG.md, "The P8X's
; desktop on this machine", step 2: the mouse and the keys as events)
;
; A desktop is drawn (wk.inc), the pointer put in the middle, the mouse turned on (OUT PD $04). Then every byte of
; the card's PS/2 controller is taken as the driver rule says - IN PE only after IN PD showed FULL - and sorted by
; where it came from (IN PD bit 1):
;   a key        q or Q ends the program; any other is ignored
;   a mouse byte the three of a packet are gathered (the first has bit 3 set: a byte without it is not a first
;                byte, and is dropped). A packet: byte 1 = the buttons (bit 0 left, 1 right, 2 middle), bit 4 the
;                sign of the movement across, bit 5 of the movement up, bits 6 and 7 an overflow (the movement is
;                then left out); byte 2 the movement across; byte 3 the movement up. The pointer's place is the old
;                one plus the movement, held to the screen (0..639, 0..399; up is towards y = 0); when it changes
;                the pointer is taken away from the old place and drawn at the new. The left button going down
;                inverts the cell the pointer's top left dot is in (the pointer away while it is done).
; At the end the mouse is turned off (OUT PD $05), the text layer comes back, and the place, the buttons and the
; packets counted are printed: X hhhh Y hhhh B hh N hh.
; tests/wm/run.py runs it on both emulators with a script of packets (Y1VID_MOUSE) and holds the picture and that
; line to the same script worked out in Python. `python3 tests/wm/run.py --try` opens it in the browser debugger,
; where the browser's mouse is the card's.
; Load: the monitor's : loader, then G3000. No R2.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showbytea:  EQU 0ffe0h

        ORG 3000h
start:  JSR wkinit
        JSR wkpinit
        MVIW R3,scene
        JSR wkscript
        MVIW R3,320
        STR R3,MS_X
        MVIW R3,200
        STR R3,MS_Y
        LDAI 0
        STA MS_N
        STA MS_BT
        STA MS_CNT
        JSR ms_on
        OUTI PD,04h
ev:     INP PD                  ; a byte from the controller?
        ANDI 1
        BRZ ev
        INP PD
        ANDI 2
        BRNZ ev_m
        INP PE                  ; a key
        LDTI 113
        BREQ quit
        LDTI 81
        BREQ quit
        BR ev
ev_m:   INP PE                  ; a mouse byte
        STA MS_T
        LDA MS_N
        BRNZ ev_1
        LDA MS_T                ; a packet's first byte has bit 3 set
        ANDI 8
        BRZ ev
ev_1:   MVIW R5,MS_PK
        LDA MS_N
        JSR adda5
        LDA MS_T
        STAVR R5
        LDA MS_N
        ADDI 1
        STA MS_N
        LDTI 3
        BRLT ev
        LDAI 0
        STA MS_N
        JSR ms_packet
        BR ev

quit:   OUTI PD,05h             ; the mouse off, the text back, the picture hidden
        LDA VIDC2
        ANDI 0feh
        STA VIDC2
        OUTA PF
        LDAI 0
        OUTA PC
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
        LDA MS_BT
        JSR showbytea
        MVIW R7,s_n
        JSR stringout
        LDA MS_CNT
        JSR showbytea
        MVIW R7,s_nl
        JSR stringout
        RET

; ms_on: the pointer drawn at MS_X, MS_Y (wk.inc's wkpoff takes it away)
ms_on:  LDR R3,MS_X
        STR R3,WK_PX
        LDR R3,MS_Y
        STR R3,WK_PY
        BR wkpon

; ms_packet: the packet in MS_PK
ms_packet: LDA MS_CNT
        ADDI 1
        STA MS_CNT
        LDA MS_PK
        ANDI 0c0h
        BRNZ mp_b
        LDR R3,MS_X             ; across: x + the movement, a 9-bit number with its sign in byte 1
        LDA MS_PK
        ANDI 10h
        BRZ mp_1
        LDAI 0ffh
mp_1:   MVARH R4
        LDA MS_PK+1
        MVARL R4
        JSR add34
        MVRHA R3                ; held to 0..639
        ANDI 80h
        BRZ mp_2
        MVIW R3,0
        BR mp_4
mp_2:   MVRHA R3
        LDTI 2
        BRGT mp_3
        BRLT mp_4
        MVRLA R3
        LDTI 127
        BRGT mp_3
        BR mp_4
mp_3:   MVIW R3,639
mp_4:   STR R3,MS_NX
        LDA MS_PK               ; up: y - the movement (R4 = its complement, and one more)
        ANDI 20h
        BRZ mp_5
        LDAI 0ffh
mp_5:   INVA
        MVARH R4
        LDA MS_PK+2
        INVA
        MVARL R4
        INCR R4
        LDR R3,MS_Y
        JSR add34
        MVRHA R3                ; held to 0..399
        ANDI 80h
        BRZ mp_6
        MVIW R3,0
        BR mp_8
mp_6:   MVRHA R3
        LDTI 1
        BRGT mp_7
        BRLT mp_8
        MVRLA R3
        LDTI 143
        BRGT mp_7
        BR mp_8
mp_7:   MVIW R3,399
mp_8:   STR R3,MS_NY
        LDT MS_X                ; moved?
        LDA MS_NX
        BRNEQ mp_m
        LDT MS_X+1
        LDA MS_NX+1
        BRNEQ mp_m
        LDT MS_Y
        LDA MS_NY
        BRNEQ mp_m
        LDT MS_Y+1
        LDA MS_NY+1
        BREQ mp_b
mp_m:   JSR wkpoff              ; away from the old place, drawn at the new
        LDR R3,MS_NX
        STR R3,MS_X
        LDR R3,MS_NY
        STR R3,MS_Y
        JSR ms_on
mp_b:   LDA MS_PK               ; the left button going down: the cell under the tip inverted
        ANDI 1
        BRZ mp_r
        LDA MS_BT
        ANDI 1
        BRNZ mp_r
        JSR wkpoff
        LDA MS_X+1
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
        LDA MS_Y+1
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
        JSR wkinv
        JSR ms_on
mp_r:   LDA MS_PK
        ANDI 7
        STA MS_BT
        RET

MS_X:   DS 2                    ; the pointer's place
MS_Y:   DS 2
MS_NX:  DS 2
MS_NY:  DS 2
MS_PK:  DS 3                    ; the packet being gathered, MS_N bytes of it
MS_N:   DS 1
MS_T:   DS 1
MS_BT:  DS 1                    ; the buttons of the last packet
MS_CNT: DS 1                    ; packets so far
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

        INCLUDE wk.inc
