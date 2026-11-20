; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; wk.inc - windows in dots on the video card V4: the drawing routines (2026-11-20; BACKLOG.md, "The P8X's desktop on
; this machine"). INCLUDEd by the programs here (wkdemo.asm, wkmouse.asm); it will be the window kernel's drawing.
;
; The V4 card is a bitmap of 640 x 400 dots that the CPU fills a byte at a time through the 2K window at $D800. The
; routines work in cells: a cell is a character's place, 8 dots wide and 16 high, 80 x 25 of them. A cell's sixteen
; lines are the sixteen planes (control 1, bits 3..0) at ONE address, $D800 + row * 80 + column: a byte is 8 dots of
; one line of one cell. A call's numbers are in WK_X, WK_Y (a cell), WK_W, WK_H (cells) and the routine's own.
;   wkinit   the video unit started (the ROM), the text layer off, the graphics layer on, page 0
;   wkfill   a rectangle of cells in a pattern: WK_PA for the even lines, WK_PB for the odd ($AA/$55 the grey
;            desktop, $FF/$00 a striped title bar, $FF/$FF paper). A plane at a time, a row of cells at a time, the
;            bytes of a row by a run of 80 STAVR / INCR pairs entered at the place that leaves the row's width: 2
;            instructions a byte.
;   wkframe  a rectangle of cells' outer edge in black: the top line of its top cells, the bottom line of its bottom
;            ones, the left dot of its left column and the right dot of its right column.
;   wkinv    a rectangle of cells inverted (a selected line, a button pressed).
;   wktext   the string at WK_S from the cell on, a character 8 x 16 from the card's own font (WK_FONT: the codes
;            $20-$7E of firmware/video/chargen-v40.bin, which tests/wm/run.py appends to the program): sixteen planes,
;            sixteen bytes at one address, each XORed with WK_M ($00 lit letters, $FF dark letters on lit paper).
;   wkpinit  the pointer's eight shifted forms, made once
;   wkpon    the pointer, 16 x 16 dots with its top left dot at WK_PX, WK_PY (any dot): an arrow, dark with a lit
;            outline, over whatever is there, which is kept;  wkpoff  puts that back. A move is wkpoff, wkpon: 16
;            lines of three bytes each. Whoever draws under the pointer takes it away first.
;   wkscript a picture as a script of these at R3 (a scene, a window's furniture):
;            1 fill x y w h even odd | 2 frame x y w h | 3 text x y mask '...' 0 | 4 pointer on xh xl yh yl |
;            5 invert x y w h | 6 pointer off | 0 the end
;            (in a DB line no blank after a comma: RC/asm takes only the first character of a string that follows
;            one; single quotes: it makes capitals of everything outside them)
; R3-R7, ACC and TMP are used; never R2.
;
vidctl:     EQU 0ffbch          ; the ROM's video entry: ACC 1 = start the video unit
VIDC2:      EQU 0ff9h           ; the ROM's copy of control 2 (OUT PF)

; wkscript: the script at R3, to its 0
wkscript: STR R3,SCP
sc_l:   JSR sc_get
        BRZ sc_end
        LDTI 1
        BREQ sc_fill
        LDTI 2
        BREQ sc_frame
        LDTI 3
        BREQ sc_text
        LDTI 5
        BREQ sc_inv
        LDTI 6
        BREQ sc_off
        BR sc_ptr
sc_end: RET
; sc_get: ACC = the script's next byte
sc_get: LDR R3,SCP
        INCR R3
        STR R3,SCP
        DECR R3
        LDAVR R3
        RET
; sc_xywh: the next four bytes -> WK_X, WK_Y, WK_W, WK_H
sc_xywh: JSR sc_get
        STA WK_X
        JSR sc_get
        STA WK_Y
        JSR sc_get
        STA WK_W
        JSR sc_get
        STA WK_H
        RET
sc_fill: JSR sc_xywh            ; 1, x, y, w, h, even lines, odd lines
        JSR sc_get
        STA WK_PA
        JSR sc_get
        STA WK_PB
        JSR wkfill
        BR sc_l
sc_frame: JSR sc_xywh           ; 2, x, y, w, h
        JSR wkframe
        BR sc_l
sc_text: JSR sc_get             ; 3, x, y, mask, the string, 0
        STA WK_X
        JSR sc_get
        STA WK_Y
        JSR sc_get
        STA WK_M
        LDR R3,SCP
        STR R3,WK_S
        JSR wktext              ; leaves WK_S at the string's 0
        LDR R3,WK_S
        INCR R3
        STR R3,SCP
        BR sc_l
sc_inv: JSR sc_xywh             ; 5, x, y, w, h
        JSR wkinv
        BR sc_l
sc_ptr: JSR sc_get              ; 4, x high, x low, y high, y low
        STA WK_PX
        JSR sc_get
        STA WK_PX+1
        JSR sc_get
        STA WK_PY
        JSR sc_get
        STA WK_PY+1
        JSR wkpon
        BR sc_l
sc_off: JSR wkpoff              ; 6
        BR sc_l

rts:    RET
; adda5, adda6: R5, R6 += ACC
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

; wkinit: the video unit started, the text layer off, the graphics layer on (page 0 drawn on and shown), and
; WK_CT[p] = control 1 for plane p
wkinit: LDAI 1
        JSR vidctl
        LDA VIDC2
        ORI 1
        STA VIDC2
        OUTA PF
        LDAI 40h
        STA WK_HI
        MVIW R6,WK_CT
        LDAI 0
        STA WK_P
wi_1:   LDT WK_HI
        LDA WK_P
        ORT
        STAVR R6
        INCR R6
        LDA WK_P
        ADDI 1
        STA WK_P
        LDTI 16
        BRLT wi_1
        LDA WK_CT
        OUTA PC
        RET

; wkaddr: ACC = a row of cells -> R6 = the address of its cell in column WK_X (R5, TMP used)
wkaddr: SHL
        MVIW R5,WK_ROWT
        JSR adda5
        LDAVR R5
        MVARH R6
        INCR R5
        LDAVR R5
        MVARL R6
        LDA WK_X
        BR adda6

; wkplane: ACC = a plane -> control 1 (R5, TMP used)
wkplane: MVIW R5,WK_CT
        JSR adda5
        LDAVR R5
        OUTA PC
        RET

; wkent: WK_ENT = where to enter the run for WK_W bytes (wf_ret - 2 * W), WK_SKIP = 80 - W
wkent:  MVIW R5,wf_ret
        LDA WK_W
        SHL
        INVA
        ADDI 1                  ; -2W as a byte (W is 1..80, so its high byte is $FF)
        MVAT
        MVRLA R5
        ADDT
        MVARL R5
        MVRHA R5
        ADDIC 0ffh
        MVARH R5
        STR R5,WK_ENT
        LDA WK_W
        INVA
        ADDI 81
        STA WK_SKIP
        RET

; wkfill: the cells WK_X, WK_Y, WK_W wide, WK_H high <- WK_PA on their even lines, WK_PB on their odd lines
wkfill: LDA WK_W
        BRZ rts
        LDA WK_H
        BRZ rts
        JSR wkent
        LDAI 0
        STA WK_P
wf_p:   LDA WK_P                ; a plane: a line of every row of cells
        JSR wkplane
        LDA WK_P
        ANDI 1
        BRZ wf_e
        LDA WK_PB
        BR wf_v
wf_e:   LDA WK_PA
wf_v:   STA WK_V
        LDA WK_H
        STA WK_R
        LDA WK_Y
        JSR wkaddr
wf_r:   LDR R5,WK_ENT           ; a row: W bytes
        LDA WK_V
        JSRUR R5
        LDA WK_SKIP             ; the same column, the next row of cells
        JSR adda6
        LDA WK_R
        SUBI 1
        STA WK_R
        BRNZ wf_r
        LDA WK_P
        ADDI 1
        STA WK_P
        LDTI 16
        BRLT wf_p
        RET
; the run: 80 times "the byte <- ACC, the next byte". Entered 2 * W bytes before wf_ret.
wf_run:
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
        STAVR R6
        INCR R6
wf_ret: RET

; wkframe: the outer edge of the cells WK_X, WK_Y, WK_W, WK_H in black (dots off)
wkframe: LDA WK_W
        BRZ rts
        LDA WK_H
        BRZ rts
        JSR wkent
        LDAI 0                  ; the top line: plane 0 of the top row
        JSR wkplane
        LDA WK_Y
        JSR wkaddr
        LDR R5,WK_ENT
        LDAI 0
        JSRUR R5
        LDAI 15                 ; the bottom line: plane 15 of the bottom row
        JSR wkplane
        LDT WK_H
        LDA WK_Y
        ADDT
        SUBI 1
        JSR wkaddr
        LDR R5,WK_ENT
        LDAI 0
        JSRUR R5
        LDAI 0                  ; the sides: every plane of every row
        STA WK_P
wr_p:   LDA WK_P
        JSR wkplane
        LDA WK_Y
        JSR wkaddr              ; R6 = the left column's cell
        LDA WK_W
        SUBI 1
        MVAT
        MVRLA R6                ; R7 = the right column's: R6 + W - 1
        ADDT
        MVARL R7
        MVRHA R6
        ADDIC 0
        MVARH R7
        MVIW R4,0
        LDA WK_H
        MVARL R4
wr_r:   LDAVR R6
        ANDI 7fh
        STAVR R6
        LDAVR R7
        ANDI 0feh
        STAVR R7
        ADDIW R6,80
        ADDIW R7,80
        DECR R4
        MVRLA R4
        BRNZ wr_r
        LDA WK_P
        ADDI 1
        STA WK_P
        LDTI 16
        BRLT wr_p
        RET

; wkinv: the cells WK_X, WK_Y, WK_W, WK_H inverted: every dot the other
wkinv:  LDA WK_W
        BRZ rts
        LDA WK_H
        BRZ rts
        LDA WK_W
        INVA
        ADDI 81
        STA WK_SKIP
        LDAI 0
        STA WK_P
wv_p:   LDA WK_P
        JSR wkplane
        LDA WK_H
        STA WK_R
        LDA WK_Y
        JSR wkaddr
wv_r:   MVIW R4,0
        LDA WK_W
        MVARL R4
wv_b:   LDAVR R6
        INVA
        STAVR R6
        INCR R6
        DECR R4
        MVRLA R4
        BRNZ wv_b
        LDA WK_SKIP
        JSR adda6
        LDA WK_R
        SUBI 1
        STA WK_R
        BRNZ wv_r
        LDA WK_P
        ADDI 1
        STA WK_P
        LDTI 16
        BRLT wv_p
        RET

; wktext: the string at WK_S from the cell WK_X, WK_Y on, each byte of a glyph XORed with WK_M. Leaves WK_S at the
; string's 0. A code outside $20-$7E is a blank.
wktext: LDA WK_Y
        JSR wkaddr
        STR R6,WK_A
wt_c:   LDR R4,WK_S
        INCR R4
        STR R4,WK_S
        DECR R4
        LDAVR R4
        BRNZ wt_1
        STR R4,WK_S
        RET
wt_1:   LDTI 32
        BRLT wt_b
        LDTI 126
        BRGT wt_b
        BR wt_g
wt_b:   LDAI 32
wt_g:   SUBI 32                 ; R5 = WK_FONT + 16 * (the code - 32)
        MVARL R5
        LDAI 0
        MVARH R5
        SHL16 R5
        SHL16 R5
        SHL16 R5
        SHL16 R5
        ADDIW R5,WK_FONT
        LDR R6,WK_A
        LDT WK_M
        LDA WK_CT+0
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+1
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+2
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+3
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+4
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+5
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+6
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+7
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+8
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+9
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+10
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+11
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+12
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+13
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+14
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        LDA WK_CT+15
        OUTA PC
        LDAVR R5
        XORT
        STAVR R6
        INCR R5
        INCR R6
        STR R6,WK_A
        BR wt_c

; wkpinit: the pointer's forms, made once: WK_SPA[k] and WK_SPO[k], its 16 lines of three bytes shifted right by k
; dots (k = 0..7) - the dots to keep (ANDed) and the dots to light (ORed)
wkpinit: MVIW R4,WK_ARA         ; form 0 of each: the word's two bytes and a third that changes nothing
        MVIW R5,WK_SPA
        LDAI 0ffh
        STA WK_B0
        JSR wq_0
        MVIW R4,WK_ARO
        MVIW R5,WK_SPO
        LDAI 0
        STA WK_B0
        JSR wq_0
        MVIW R4,WK_SPA          ; forms 1..7: a line of the form before, one dot to the right
        MVIW R5,WK_SPA+48
        LDAI 80h                ; (the dot that comes in at the left is one to keep)
        STA WK_B2
        JSR wq_s
        MVIW R4,WK_SPO
        MVIW R5,WK_SPO+48
        LDAI 0
        STA WK_B2
        BR wq_s
; wq_0: 16 words at R4 -> 16 lines at R5: a word's two bytes and WK_B0
wq_0:   LDAI 16
        STA WK_R
wq_01:  LDAVR R4
        STAVR R5
        INCR R4
        INCR R5
        LDAVR R4
        STAVR R5
        INCR R4
        INCR R5
        LDA WK_B0
        STAVR R5
        INCR R5
        LDA WK_R
        SUBI 1
        STA WK_R
        BRNZ wq_01
        RET
; wq_s: 112 lines at R5 <- the 112 lines at R4, each a dot to the right, WK_B2 ($80 or 0) coming in at the left
wq_s:   LDAI 112
        STA WK_R
wq_1:   LDAVR R4                ; byte 0
        STA WK_B0
        SHR
        MVAT
        LDA WK_B2
        ORT
        STAVR R5
        INCR R4
        INCR R5
        LDAVR R4                ; byte 1, with byte 0's last dot
        STA WK_B1
        SHR
        STA WK_V
        LDA WK_B0
        ANDI 1
        BRZ wq_2
        LDA WK_V
        ORI 80h
        STA WK_V
wq_2:   LDA WK_V
        STAVR R5
        INCR R4
        INCR R5
        LDAVR R4                ; byte 2, with byte 1's last dot
        SHR
        STA WK_V
        LDA WK_B1
        ANDI 1
        BRZ wq_3
        LDA WK_V
        ORI 80h
        STA WK_V
wq_3:   LDA WK_V
        STAVR R5
        INCR R4
        INCR R5
        LDA WK_R
        SUBI 1
        STA WK_R
        BRNZ wq_1
        RET

; wp_set: R3 = x, R4 = y of the pointer's top left dot -> WK_X its column, WK_PN the bytes of a line that are on the
; screen (80 - the column, 3 at most), WK_YY = y, 16 lines to go
wp_set: STR R4,WK_YY
        MVRLA R3
        SHR
        SHR
        SHR
        MVAT
        MVRHA R3
        SHL
        SHL
        SHL
        SHL
        SHL
        ORT
        STA WK_X
        INVA
        ADDI 81
        LDTI 3
        BRLT ws_n
        LDAI 3
ws_n:   STA WK_PN
        LDAI 16
        STA WK_R
        RET
; wp_row: the line WK_YY -> ACC 0 = off the bottom; else its plane chosen, R6 = its byte in column WK_X, ACC 1
wp_row: LDR R3,WK_YY
        MVRHA R3
        LDTI 1
        BRGT wp_no
        BRLT wp_1
        MVRLA R3
        LDTI 143
        BRGT wp_no
wp_1:   MVRLA R3
        ANDI 15
        JSR wkplane
        LDR R3,WK_YY            ; its row of cells: y >> 4
        MVRLA R3
        SHR
        SHR
        SHR
        SHR
        MVAT
        MVRHA R3
        SHL
        SHL
        SHL
        SHL
        ORT
        JSR wkaddr
        LDAI 1
        RET
wp_no:  LDAI 0
        RET
; wp_next: the next line: the forms' and the kept bytes' places 3 on, y + 1 -> ACC = the lines still to go
wp_next: LDR R4,WK_SPP
        ADDIW R4,3
        STR R4,WK_SPP
        LDR R4,WK_SVP
        ADDIW R4,3
        STR R4,WK_SVP
        LDR R3,WK_YY
        INCR R3
        STR R3,WK_YY
        LDA WK_R
        SUBI 1
        STA WK_R
        RET

; wkpon: the pointer drawn with its top left dot at WK_PX, WK_PY (0..639, 0..399), what was under it kept for
; wkpoff. The dots of its outline are lit, those of its body dark, the others as they were; what would fall off the
; right or the bottom is left out. Whoever draws where the pointer is takes it away first (wkpoff) and puts it back.
wkpon:  LDR R3,WK_PX
        STR R3,WK_SVX
        LDR R4,WK_PY
        STR R4,WK_SVY
        JSR wp_set
        LDA WK_PX+1             ; the forms for x & 7
        ANDI 7
        SHL
        MVIW R5,WK_SPT
        JSR adda5
        LDAVR R5
        MVARH R4
        INCR R5
        LDAVR R5
        MVARL R4
        STR R4,WK_SPP
        MVIW R4,WK_SAVE
        STR R4,WK_SVP
wo_r:   JSR wp_row
        BRZ rts
        LDR R4,WK_SPP           ; the line's dots to keep; its dots to light are 384 bytes on
        MOVRR R4,R5
        ADDIW R5,384
        LDR R7,WK_SVP
        JSR wo_b
        LDA WK_PN
        LDTI 2
        BRLT wo_2
        JSR wo_b
        LDA WK_PN
        LDTI 3
        BRLT wo_2
        JSR wo_b
wo_2:   JSR wp_next
        BRNZ wo_r
        RET
; wo_b: a byte of the screen: kept, then (it AND the dots to keep) OR the dots to light
wo_b:   LDAVR R6
        STAVR R7
        MVAT
        LDAVR R4
        ANDT
        MVAT
        LDAVR R5
        ORT
        STAVR R6
        INCR R4
        INCR R5
        INCR R6
        INCR R7
        RET

; wkpoff: the pointer away: what was under it, where wkpon drew it, put back
wkpoff: LDR R3,WK_SVX
        LDR R4,WK_SVY
        JSR wp_set
        MVIW R4,WK_SAVE
        STR R4,WK_SVP
wx_r:   JSR wp_row
        BRZ rts
        LDR R7,WK_SVP
        LDAVR R7
        STAVR R6
        LDA WK_PN
        LDTI 2
        BRLT wx_2
        INCR R7
        INCR R6
        LDAVR R7
        STAVR R6
        LDA WK_PN
        LDTI 3
        BRLT wx_2
        INCR R7
        INCR R6
        LDAVR R7
        STAVR R6
wx_2:   JSR wp_next
        BRNZ wx_r
        RET

WK_ROWT:
        DW 0d800h, 0d850h, 0d8a0h, 0d8f0h, 0d940h
        DW 0d990h, 0d9e0h, 0da30h, 0da80h, 0dad0h
        DW 0db20h, 0db70h, 0dbc0h, 0dc10h, 0dc60h
        DW 0dcb0h, 0dd00h, 0dd50h, 0dda0h, 0ddf0h
        DW 0de40h, 0de90h, 0dee0h, 0df30h, 0df80h
WK_SPT: DW WK_SPA, WK_SPA+48, WK_SPA+96, WK_SPA+144, WK_SPA+192, WK_SPA+240, WK_SPA+288, WK_SPA+336
; the pointer: an arrow, its body dark and a lit outline of one dot round it (the body's tip is the dot one to the
; right of and one below the top left dot). WK_ARA: a word a line, the dots to keep (all but the arrow's and its
; outline's); WK_ARO: the dots to light (the outline). The high byte is the left one.
WK_ARA:
        DW 01fffh, 00fffh, 007ffh, 003ffh, 001ffh, 000ffh, 0007fh, 0003fh
        DW 0003fh, 0003fh, 000ffh, 000ffh, 0107fh, 0f07fh, 0f87fh, 0f87fh
WK_ARO:
        DW 0e000h, 0b000h, 09800h, 08c00h, 08600h, 08300h, 08180h, 080c0h
        DW 08040h, 083c0h, 09300h, 0b900h, 0e980h, 00c80h, 00480h, 00780h
SCP:    DS 2                    ; the script's place
WK_X:   DS 1                    ; a call's cells
WK_Y:   DS 1
WK_W:   DS 1
WK_H:   DS 1
WK_PA:  DS 1
WK_PB:  DS 1
WK_M:   DS 1
WK_S:   DS 2
WK_A:   DS 2
WK_HI:  DS 1                    ; control 1's bits 7..4
WK_CT:  DS 16                   ; control 1 for each plane
WK_P:   DS 1
WK_R:   DS 1
WK_V:   DS 1
WK_ENT: DS 2
WK_SKIP: DS 1
WK_PX:  DS 2                    ; the pointer
WK_PY:  DS 2
WK_YY:  DS 2
WK_PN:  DS 1
WK_SPP: DS 2
WK_SVP: DS 2                    ; the kept bytes' place, and where the pointer was drawn
WK_SVX: DS 2
WK_SVY: DS 2
WK_B0:  DS 1
WK_B1:  DS 1
WK_B2:  DS 1
WK_SAVE: DS 48                  ; what is under the pointer: 16 lines of three bytes
WK_SPA: DS 384                  ; its eight forms: the dots to keep ...
WK_SPO: DS 384                  ; ... and, 384 bytes on, the dots to light
; WK_FONT (the 95 glyphs $20-$7E, 16 bytes each) is appended by tests/wm/run.py from firmware/video/chargen-v40.bin
