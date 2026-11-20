; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; wkdemo.asm - windows in dots on the video card V4: the drawing routines tried out, and what they cost (2026-11-20)
;
; The first step towards the P8X's desktop on this machine (BACKLOG.md). The P8X's graphics card draws for itself:
; rectangles, text, clipping. The V4 card is a bitmap of 640 x 400 dots that the CPU fills a byte at a time through
; the 2K window at $D800, so what a window costs is what these routines cost. They work in cells: a cell is a
; character's place, 8 dots wide and 16 high, 80 x 25 of them. A cell's sixteen lines are the sixteen planes
; (control 1, bits 3..0) at ONE address, $D800 + row * 80 + column: a byte is 8 dots of one line of one cell. So:
;   wkfill   a rectangle of cells in a pattern: one byte for the even lines, one for the odd ($AA/$55 the grey
;            desktop, $FF/$00 a striped title bar, $FF/$FF paper). A plane at a time, a row of cells at a time, the
;            bytes of a row by a run of 80 STAVR / INCR pairs entered at the place that leaves the row's width: 2
;            instructions a byte.
;   wkframe  a rectangle of cells' outer edge in black: the top line of its top cells, the bottom line of its bottom
;            ones, the left dot of its left column and the right dot of its right column.
;   wktext   a string from a cell on, a character 8 x 16 from the card's own font (firmware/video/chargen-v40.bin's
;            codes $20-$7E, appended to this source as WK_FONT by tests/wm/run.py): sixteen planes, sixteen bytes at
;            one address, each XORed with a mask ($00 lit letters, $FF dark letters on lit paper).
;   wkptr    the mouse pointer, 16 x 16 dots XORed at any dot: drawn again it is gone. Its eight shifted forms are
;            made once (wkpinit), so a move is 16 lines of three bytes, twice.
; The scene below is a script of these (scene: .. scend:), which tests/wm/run.py reads from this file and draws again
; in Python: the 64K of graphics RAM must be the same from both emulators and from that. The text layer is switched
; off (control 2, TEXT-OFF): the picture is dots alone.
; Load: the monitor's : loader, then G3000 (the ROM's RET returns to the command loop). No R2.
;
vidctl:     EQU 0ffbch          ; the ROM's video entry: ACC 1 = start the video unit
VIDC2:      EQU 0ff9h           ; the ROM's copy of control 2 (OUT PF)

        ORG 3000h
start:  JSR wkinit
        JSR wkpinit
        MVIW R3,scene
        STR R3,SCP
sc_l:   JSR sc_get
        BRZ sc_end
        LDTI 1
        BREQ sc_fill
        LDTI 2
        BREQ sc_frame
        LDTI 3
        BREQ sc_text
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
sc_ptr: JSR sc_get              ; 4, x high, x low, y high, y low
        STA WK_PX
        JSR sc_get
        STA WK_PX+1
        JSR sc_get
        STA WK_PY
        JSR sc_get
        STA WK_PY+1
        JSR wkptr
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

; wkpinit: the pointer's eight forms, WK_SPR[k] = its 16 lines of three bytes shifted right by k dots
wkpinit: MVIW R4,WK_ARROW       ; form 0: high byte, low byte, 0
        MVIW R5,WK_SPR
        LDAI 16
        STA WK_R
wq_0:   LDAVR R4
        STAVR R5
        INCR R4
        INCR R5
        LDAVR R4
        STAVR R5
        INCR R4
        INCR R5
        LDAI 0
        STAVR R5
        INCR R5
        LDA WK_R
        SUBI 1
        STA WK_R
        BRNZ wq_0
        MVIW R4,WK_SPR          ; forms 1..7: a line of the form before, one dot to the right
        LDAI 112
        STA WK_R
wq_1:   LDAVR R4                ; byte 0
        STA WK_B0
        SHR
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

; wkptr: the pointer XORed with its top left dot at WK_PX, WK_PY (0..639, 0..399); what would fall off the right or
; the bottom is left out
wkptr:  LDA WK_PX+1             ; the column: x >> 3
        SHR
        SHR
        SHR
        MVAT
        LDA WK_PX
        SHL
        SHL
        SHL
        SHL
        SHL
        ORT
        STA WK_X
        INVA                    ; the bytes of a line that are on the screen: 80 - the column, 3 at most
        ADDI 81
        LDTI 3
        BRLT wp_n
        LDAI 3
wp_n:   STA WK_PN
        LDA WK_PX+1             ; the form: x & 7
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
        LDR R3,WK_PY
        STR R3,WK_YY
        LDAI 16
        STA WK_R
wp_r:   LDR R3,WK_YY            ; a line: off the bottom?
        MVRHA R3
        LDTI 1
        BRGT rts
        BRLT wp_1
        MVRLA R3
        LDTI 143
        BRGT rts
wp_1:   MVRLA R3                ; its plane
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
        LDR R4,WK_SPP
        LDAVR R4
        MVAT
        LDAVR R6
        XORT
        STAVR R6
        LDA WK_PN
        LDTI 2
        BRLT wp_2
        INCR R4
        INCR R6
        LDAVR R4
        MVAT
        LDAVR R6
        XORT
        STAVR R6
        LDA WK_PN
        LDTI 3
        BRLT wp_2
        INCR R4
        INCR R6
        LDAVR R4
        MVAT
        LDAVR R6
        XORT
        STAVR R6
wp_2:   LDR R4,WK_SPP
        ADDIW R4,3
        STR R4,WK_SPP
        LDR R3,WK_YY
        INCR R3
        STR R3,WK_YY
        LDA WK_R
        SUBI 1
        STA WK_R
        BRNZ wp_r
        RET

; ---- the scene: 1 fill x y w h even odd | 2 frame x y w h | 3 text x y mask '...' 0 | 4 pointer xh xl yh yl | 0
; (no blank after a comma: RC/asm takes only the first character of a string that follows one; single quotes: it
; makes capitals of everything outside them)
scene:  DB 1,0,0,80,25,0aah,055h
        DB 1,0,0,80,1,0ffh,0ffh
        DB 2,0,0,80,1
        DB 3,2,0,0ffh,'YACC1   File   Edit   View   Special',0
        DB 3,67,0,0ffh,'20 Nov 12:34',0
        DB 1,4,3,36,14,0ffh,0ffh
        DB 1,4,3,36,1,0ffh,000h
        DB 2,4,3,36,14
        DB 3,17,3,0ffh,' /bin ',0
        DB 3,6,5,0ffh,'Name          Size  Kind',0
        DB 3,6,6,0ffh,'asm          11046  program',0
        DB 3,6,7,000h,'basic        11209  program ',0
        DB 3,6,8,0ffh,'cat           1322  program',0
        DB 3,6,9,0ffh,'cc            2710  program',0
        DB 3,6,10,0ffh,'kermit        9834  program',0
        DB 3,6,11,0ffh,'ls            3120  program',0
        DB 3,6,12,0ffh,'make          6002  program',0
        DB 3,6,13,0ffh,'vi            7421  program',0
        DB 3,6,15,0ffh,'52 items, 1.2M free',0
        DB 1,30,9,46,14,0ffh,0ffh
        DB 1,30,9,46,1,0ffh,000h
        DB 2,30,9,46,14
        DB 3,47,9,0ffh,' notes.txt ',0
        DB 3,32,11,0ffh,'The YACC1 draws this window a byte at a',0
        DB 3,32,12,0ffh,'time: every dot on this screen went',0
        DB 3,32,13,0ffh,'through the 2K window at $D800.',0
        DB 3,32,15,0ffh,'A cell is 8 dots by 16: 80 x 25 of them,',0
        DB 3,32,16,0ffh,'and the sixteen lines of a cell are sixteen',0
        DB 3,32,17,0ffh,'planes at one address.',0
        DB 3,32,19,0ffh,'0123456789 !#$%&()*+,-./:<=>?@[]^_{|}~',0
        DB 3,78,24,0ffh,'end',0
        DB 4,1,164,0,224
        DB 4,2,122,1,136
        DB 0
scend:

WK_ROWT:
        DW 0d800h, 0d850h, 0d8a0h, 0d8f0h, 0d940h
        DW 0d990h, 0d9e0h, 0da30h, 0da80h, 0dad0h
        DW 0db20h, 0db70h, 0dbc0h, 0dc10h, 0dc60h
        DW 0dcb0h, 0dd00h, 0dd50h, 0dda0h, 0ddf0h
        DW 0de40h, 0de90h, 0dee0h, 0df30h, 0df80h
WK_SPT: DW WK_SPR, WK_SPR+48, WK_SPR+96, WK_SPR+144, WK_SPR+192, WK_SPR+240, WK_SPR+288, WK_SPR+336
WK_ARROW:
        DB 080h, 000h, 0c0h, 000h, 0e0h, 000h, 0f0h, 000h
        DB 0f8h, 000h, 0fch, 000h, 0feh, 000h, 0ffh, 000h
        DB 0ffh, 080h, 0ffh, 0c0h, 0fch, 000h, 0eeh, 000h
        DB 0c7h, 000h, 087h, 000h, 003h, 080h, 003h, 080h
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
WK_B0:  DS 1
WK_B1:  DS 1
WK_SPR: DS 384
; WK_FONT (the 95 glyphs $20-$7E, 16 bytes each) is appended by tests/wm/run.py from firmware/video/chargen-v40.bin
