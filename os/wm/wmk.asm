; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; wmk.asm - the window kernel for the video card V4 (version 2, 2026-11-20; BACKLOG.md, "The P8X's desktop on this
; machine", step 3). Drawing in dots (wk.inc), the mouse's pointer and the keys as events, in 4K at $C000-$CFFF (and,
; while it runs, 816 bytes of the card's text RAM for the pointer, the text layer being off): loaded
; once, above the program that uses it, and called through a table of entries at $C004 (wkabi.inc has them, the
; parameter block at $C030 and what each does). The P8X kept its window kernel inside its OS; the Y1/OS's 16K is
; full, so this one is a module of its own, as the P8X's first design was. A program that is not a window program
; may overwrite it: one that is checks the signature at $C000 ('WK', the version) and loads it again.
; The font is wkfont.inc, made by os/wm/mkfont.py. os/Makefile builds it as /lib/wmk on the disk (loaded at $C000);
; os/lib_wk.c loads it for a C program and calls it.
; No R2.
;
        INCLUDE wkabi.inc
VIDMIR:     EQU 0ff1h           ; the ROM's: nonzero = the console is also written to the text screen

        ORG 0c000h
        DB 'W','K',2,0
        BR k_init
        BR wkfill
        BR wkframe
        BR wkinv
        BR wktext
        BR k_show
        BR k_hide
        BR k_script
        BR k_event
        BR k_done
        BR wkxframe

        ORG 0c050h              ; after the parameter block ($C030-$C04F)
k_init: LDA VIDMIR              ; the ROM's console mirror off while the text RAM is the pointer's
        STA MS_MIR
        LDAI 0
        STA VIDMIR
        JSR wkinit
        JSR wkpinit
        MVIW R3,320
        STR R3,MS_X
        MVIW R3,200
        STR R3,MS_Y
        LDAI 0
        STA MS_B
        STA MS_VIS
        STA MS_CNT
        STA MS_N
        OUTI PD,04h
        RET

k_show: LDA MS_VIS
        BRNZ rts
        LDAI 1
        STA MS_VIS
        LDR R3,MS_X
        STR R3,WK_PX
        LDR R3,MS_Y
        STR R3,WK_PY
        BR wkpon

k_hide: LDA MS_VIS
        BRZ rts
        LDAI 0
        STA MS_VIS
        BR wkpoff

k_script: LDR R3,WK_S
        BR wkscript

k_done: OUTI PD,05h             ; the mouse off, the graphics layer hidden, the text RAM cleared, the text back
        LDAI 0
        OUTA PC
        STA MS_VIS
        LDAI 2
        JSR vidctl
        LDA VIDC2
        ANDI 0feh
        STA VIDC2
        OUTA PF
        LDA MS_MIR
        STA VIDMIR
        RET

; k_event: one look at the controller -> R3 = ACC = the event (wkabi.inc)
k_event: INP PD
        ANDI 1
        BRZ ev_0
        INP PD
        ANDI 2
        BRNZ ev_m
        INP PE                  ; a key
        STA EV_KEY
        LDAI 1
        BR ev_r
ev_m:   INP PE                  ; a mouse byte: a packet's first has bit 3 set
        STA MS_T
        LDA MS_N
        BRNZ ev_1
        LDA MS_T
        ANDI 8
        BRZ ev_0
ev_1:   MVIW R5,MS_PK
        LDA MS_N
        JSR adda5
        LDA MS_T
        STAVR R5
        LDA MS_N
        ADDI 1
        STA MS_N
        LDTI 3
        BRLT ev_0
        LDAI 0
        STA MS_N
        JSR ms_packet
        BR ev_r
ev_0:   LDAI 0
ev_r:   STA MS_T
        MVARL R3
        LDAI 0
        MVARH R3
        LDA MS_T
        RET

; ms_packet: the packet in MS_PK -> ACC = the event: 3 a button down, else 4 one up, else 2 moved, else 0
ms_packet: LDA MS_CNT
        ADDI 1
        STA MS_CNT
        LDAI 0
        STA MS_MV
        LDA MS_PK
        ANDI 0c0h
        BRNZ mp_b               ; an overflow: the movement is left out
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
mp_m:   LDAI 1
        STA MS_MV
        LDA MS_VIS
        BRZ mp_n
        JSR wkpoff              ; away from the old place
mp_n:   LDR R3,MS_NX
        STR R3,MS_X
        STR R3,WK_PX
        LDR R3,MS_NY
        STR R3,MS_Y
        STR R3,WK_PY
        LDA MS_VIS
        BRZ mp_b
        JSR wkpon               ; drawn at the new
mp_b:   LDA MS_B                ; the buttons: down = new AND NOT old, up = old AND NOT new
        INVA
        MVAT
        LDA MS_PK
        ANDI 7
        ANDT
        STA MS_DN
        LDA MS_PK
        ANDI 7
        INVA
        MVAT
        LDA MS_B
        ANDT
        STA MS_UP
        LDA MS_PK
        ANDI 7
        STA MS_B
        LDA MS_DN
        BRZ mp_u
        LDAI 3
        RET
mp_u:   LDA MS_UP
        BRZ mp_v
        LDAI 4
        RET
mp_v:   LDA MS_MV
        BRZ mp_z
        LDAI 2
        RET
mp_z:   LDAI 0
        RET

        INCLUDE wk.inc

MS_NX:  DS 2                    ; the kernel's own
MS_NY:  DS 2
MS_PK:  DS 3                    ; the packet being gathered, MS_N bytes of it
MS_N:   DS 1
MS_T:   DS 1
MS_MV:  DS 1
MS_MIR: DS 1                    ; the ROM's console mirror (VIDMIR) as wk_init found it

        INCLUDE wkfont.inc
