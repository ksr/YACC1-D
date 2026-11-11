; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; v30card.asm - the video card V3 from a YACC1 program, on the emulators (2026-11-11): Y1VID_CARD=v3,
; software/videomodel.h and acrtcmodel.h; docs/cards/video-v3.md. The card is ports only: PA OUT the HD63484's address
; register, PB OUT its data (a register, or the write FIFO at r00), PC IN its status, PD IN its data (the read FIFO);
; PE IN the card's status (PS/2 FULL / SRC / BUSY, the ID $6x), PF IN the PS/2 data.
;   ID      IN PE and $F8: 60
;   STATUS  the chip's status as reset leaves it: 23 (ABT set, the FIFOs shut)
;   then the chip is started for 640 x 480 (the registers of the design note's section 3, a byte at a time), the
;   screen cleared, "V3 OK" copied from the font EPROM into row 1 (SCPY under the mask: two characters a word), a
;   frame, a diagonal, a filled box and a dot drawn
;   RD      the word under "V3"'s second line read back through the read FIFO: 3E 41
;   CP      the current pointer after the dot (RPR): 0140 00F0
;   STATUS  23 again: every command done, both FIFOs empty
;   PS2     four bytes from the PS/2 controller, each with the status that announced it: a key (SRC 0) and a mouse
;           packet (SRC 1): Y1VID_KEYS=k, Y1VID_MOUSE=3,-2,2 give 01:6B 03:2A 03:03 03:FE
; Load: the monitor's : loader, then G3000. No R2.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showbytea:  EQU 0ffe0h

        ORG 3000h
start:  MVIW R7,s_head
        JSR stringout
        MVIW R7,s_id
        JSR stringout
        INP PE
        ANDI 0f8h
        JSR showbytea
        JSR crlf
        MVIW R7,s_st
        JSR stringout
        INP PC
        JSR showbytea
        JSR crlf
; ---- the chip's registers, then the commands
        MVIW R6,regs
        JSR sregs
        MVIW R6,setup
        JSR sfifo
        MVIW R6,text
        JSR sfifo
        MVIW R6,draw
        JSR sfifo
; ---- read back
        MVIW R6,readw
        JSR sfifo
        MVIW R7,s_rd
        JSR stringout
        INP PD
        JSR showbytea
        JSR space
        INP PD
        JSR showbytea
        JSR crlf
        MVIW R6,readcp
        JSR sfifo
        MVIW R7,s_cp
        JSR stringout
        INP PD
        JSR showbytea
        INP PD
        JSR showbytea
        JSR space
        INP PD
        JSR showbytea
        INP PD
        JSR showbytea
        JSR crlf
        MVIW R7,s_st
        JSR stringout
        INP PC
        JSR showbytea
        JSR crlf
; ---- the keyboard and the mouse
        MVIW R7,s_ps2
        JSR stringout
        LDAI 4
        STA cnt
kloop:  INP PE
        ANDI 1
        BRZ kloop
        INP PE
        ANDI 7
        JSR showbytea
        LDAI ':'
        JSR charout
        INP PF
        JSR showbytea
        JSR space
        LDA cnt
        SUBI 1
        STA cnt
        BRNZ kloop
        JSR crlf
        MVIW R7,s_done
        JSR stringout
        RET

; sregs: register bytes from the table at R6 - a register number and its byte, to $FF
sregs:  LDAVR R6
        LDTI 0ffh
        BREQ sregx
        OUTA PA
        INCR R6
        LDAVR R6
        OUTA PB
        INCR R6
        BR sregs
sregx:  RET
; sfifo: bytes to the write FIFO from the table at R6 - their count, then the bytes (a word's high byte first)
sfifo:  OUTI PA,0
        LDAVR R6
        MVARL R5
        INCR R6
sfl:    LDAVR R6
        OUTA PB
        INCR R6
        DECR R5
        MVRLA R5
        BRNZ sfl
        RET
space:  LDAI 32
        JSR charout
        RET
crlf:   LDAI 13
        JSR charout
        LDAI 10
        JSR charout
        RET

cnt:    DB 0
; CCR 0000 (ABT off, 1 bit a pixel), OMR 8088 (stopped, static RAM, interleaved), DCR 4000 (the Base screen on),
; HSR 630C, HDR 054F, VSR 020D, VDR 2002, SP1 01E0, MWR1 0028, SAR1 0, then OMR C088: start
regs:   DB 002h,000h,003h,000h,004h,080h,005h,088h,006h,040h,007h,000h
        DB 082h,063h,083h,00ch,084h,005h,085h,04fh,086h,002h,087h,00dh
        DB 088h,020h,089h,002h,08ah,001h,08bh,0e0h
        DB 0cah,000h,0cbh,028h,0cch,000h,0cdh,000h,0ceh,000h,0cfh,000h
        DB 004h,0c0h,005h,088h,0ffh
; ORG the Base screen at word 19,160 (the bottom-left); CL0 0, CL1 FFFF; pattern word 0 all ones, PRC on it;
; RWP word 0, CLR 40 words x 480 lines of 0
setup:  DB 40
        DB 004h,000h,040h,004h,0adh,080h
        DB 008h,000h,000h,000h,008h,001h,0ffh,0ffh
        DB 018h,000h,000h,002h,0ffh,0ffh
        DB 008h,005h,000h,000h,008h,006h,000h,000h,008h,007h,000h,0f0h
        DB 008h,00ch,040h,000h,008h,00dh,000h,000h
; (CLR goes with the text's table: a table is at most 255 bytes)
; "V3 OK" in row 1 (words 641-643): for each character the mask (the half of the word), RWP, and SCPY one word x
; 16 lines down from the glyph in the EPROM ($80000 + (code / 40) x 640 + code mod 40)
text:   DB 92
        DB 058h,000h,000h,000h,000h,027h,0feh,021h
        DB 008h,004h,000h,0ffh,008h,00ch,040h,000h,008h,00dh,028h,010h
        DB 071h,000h,000h,080h,050h,060h,000h,000h,0ffh,0f1h
        DB 008h,004h,0ffh,000h,008h,00ch,040h,000h,008h,00dh,028h,010h
        DB 071h,000h,000h,080h,028h,0b0h,000h,000h,0ffh,0f1h
        DB 008h,00ch,040h,000h,008h,00dh,028h,020h
        DB 071h,000h,000h,080h,02ah,070h,000h,000h,0ffh,0f1h
        DB 008h,004h,000h,0ffh,008h,00ch,040h,000h,008h,00dh,028h,030h
        DB 071h,000h,000h,080h,02ah,030h,000h,000h,0ffh,0f1h
; AMOVE 0,0; ARCT 639,479; ALINE 639,479; AMOVE 100,100; AFRCT 199,149; AMOVE 320,240; DOT
draw:   DB 38
        DB 080h,000h,000h,000h,000h,000h,090h,000h,002h,07fh,001h,0dfh
        DB 088h,000h,002h,07fh,001h,0dfh
        DB 080h,000h,000h,064h,000h,064h,0c0h,000h,000h,0c7h,000h,095h
        DB 080h,000h,001h,040h,000h,0f0h,0cch,000h
; RWP word 681 (row 1's second line, under "V3"), RD
readw:  DB 10
        DB 008h,00ch,040h,000h,008h,00dh,02ah,090h,044h,000h
; RPR CP's X and Y
readcp: DB 4
        DB 00ch,012h,00ch,013h
s_head: DB 13,10,"V3 CARD",13,10,0
s_id:   DB "ID ",0
s_st:   DB "STATUS ",0
s_rd:   DB "RD ",0
s_cp:   DB "CP ",0
s_ps2:  DB "PS2 ",0
s_done: DB "DONE",13,10,0
