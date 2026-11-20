; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; wkdemo.asm - windows in dots on the video card V4: a desktop drawn with os/wm/wk.inc's routines (2026-11-20)
;
; The first step towards the P8X's desktop on this machine (BACKLOG.md). The P8X's graphics card draws for itself:
; rectangles, text, clipping. The V4 card is a bitmap the CPU fills, so what a window costs is what wk.inc's
; routines cost; this program is the scene they are measured on. The scene is a script (the lines from the label
; scene to the label scend; wk.inc's wkscript), which tests/wm/run.py reads from this file and draws again in
; Python: the 64K of graphics RAM must be the same from both emulators and from that. The text layer is switched
; off: the picture is dots alone.
; The routines are assembled into this program (their parameter block at the kernel's place, $C030; the
; kernel itself is not loaded). Load: the monitor's : loader, then G3000 (the RET returns to the command loop). No R2.
;
        ORG 3000h
start:  JSR wkinit
        JSR wkpinit
        MVIW R3,scene
        JSR wkscript
        RET

; the scene (wk.inc's script)
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

        INCLUDE wkabi.inc
        INCLUDE wk.inc
        INCLUDE wkfont.inc
