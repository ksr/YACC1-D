; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; wkabi.inc - the window kernel's interface (os/wm/wmk.asm, version 2, 2026-11-20; version 1 had no wk_xframe): where it is, its entries and its
; parameter block. A program INCLUDEs this and calls the entries with JSR (a C program: poke the parameters, then
; call(entry), which returns R3). The kernel is 4K at $C000-$CFFF, above the program: a program that uses it keeps
; below $C000, its stack too.
;
; Every entry may change R3-R7, ACC and TMP; none uses R2.
;   wk_init    the video unit started, the text layer off, the graphics layer on (page 0), the pointer's forms
;              made, the pointer in the middle (MS_X 320, MS_Y 200) and hidden, the mouse on (OUT PD $04). From
;              here to wk_done the card's text RAM ($D000-$D32F) is the kernel's, and the ROM's console is not
;              mirrored on the screen (VIDMIR 0)
;   wk_fill    the cells WK_X, WK_Y, WK_W wide, WK_H high: WK_PA on their even lines, WK_PB on their odd
;   wk_frame   their outer edge in black          wk_inv   them inverted
;   wk_text    the string at WK_S (to its 0) from the cell WK_X, WK_Y, each glyph XORed with WK_M; WK_S is left at
;              the 0
;   wk_show    the pointer drawn at MS_X, MS_Y (if it is hidden)    wk_hide   taken away (if it is shown). Whoever
;              draws where the pointer is hides it first.
;   wk_script  the script at WK_S (wk.inc's wkscript: 1 fill, 2 frame, 3 text, 4 pointer, 5 invert, 6 pointer off)
;   wk_event   one look at the PS/2 controller, never waiting -> R3 and ACC: 0 nothing; 1 a key (EV_KEY); 2 the
;              mouse moved (MS_X, MS_Y; the pointer, if shown, with it); 3 a button went down (MS_DN: which); 4
;              one went up. MS_B is the buttons held (1 left, 2 right, 4 middle), MS_CNT the packets so far.
;   wk_xframe  the edge of the cells WK_X, WK_Y, WK_W, WK_H inverted: drawn again it is gone (an outline while a
;              window is dragged; the pointer hidden meanwhile)
;   wk_done    the mouse off, the graphics layer hidden, the text screen cleared and shown, the mirror as it was
;
WKBASE:     EQU 0c000h
WK_SIG:     EQU 0c000h          ; 'W', 'K', the version (2), 0
wk_init:    EQU 0c004h
wk_fill:    EQU 0c007h
wk_frame:   EQU 0c00ah
wk_inv:     EQU 0c00dh
wk_text:    EQU 0c010h
wk_show:    EQU 0c013h
wk_hide:    EQU 0c016h
wk_script:  EQU 0c019h
wk_event:   EQU 0c01ch
wk_done:    EQU 0c01fh
wk_xframe:  EQU 0c022h
; the parameter block, $C030-$C04F
WK_X:       EQU 0c030h          ; a cell: 0..79
WK_Y:       EQU 0c031h          ; 0..24
WK_W:       EQU 0c032h          ; cells
WK_H:       EQU 0c033h
WK_PA:      EQU 0c034h          ; a fill's pattern: the even lines, the odd
WK_PB:      EQU 0c035h
WK_M:       EQU 0c036h          ; text: $00 lit letters, $FF dark letters on lit paper
WK_S:       EQU 0c038h          ; a string's or a script's address (a word, high byte first)
MS_X:       EQU 0c03ah          ; the pointer's top left dot: 0..639 (a word)
MS_Y:       EQU 0c03ch          ; 0..399
MS_B:       EQU 0c03eh          ; the buttons held
EV_KEY:     EQU 0c03fh          ; the key of event 1
MS_VIS:     EQU 0c040h          ; 1 while the pointer is shown
MS_CNT:     EQU 0c041h          ; mouse packets so far (counting round)
MS_DN:      EQU 0c042h          ; event 3: the buttons that went down
MS_UP:      EQU 0c043h          ; event 4: the buttons that went up
