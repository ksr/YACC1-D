; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
;
; testcard.asm - video card bring-up (2026-10-10): program the 6845 from a table and draw a test card, then return to
; the monitor (the picture stays). The table is at $3003, right after the first jump, so the timing can be changed at
; the machine without reassembling: `E 3003` and type new R0..R15 bytes, then `G3000` again. Its default is the ROM's
; (monitor.asm vcrtab: 80 x 24, 15.7 kHz / 60 Hz for an assumed 10 MHz dot clock; tools/vidsim.py timing checks a
; table for any crystal and against IBM 5151/5153 monitors).
; The card (80 x 24 from $D000):
;   row 0     title
;   row 1     a column ruler 0123456789 x 8 (a missing or doubled column shows at once)
;   row 2     the 64 glyph codes 00-3F (the EPROM's whole set, in code order)
;   row 3     the same with bit 7 set (inverse video)
;   rows 4-22 the row number in hex, a border *, 76 characters of text shifted one place per row, a border *
;   row 23    last-row text; the cursor (R14:R15) at row 12, column 40
; Expected picture: tools/vidsim.py run testcard.img --png card.png. Load: tools/monload.py --go 3000 testcard.img.
; No R2. Hex as numbers: the assembler upper-cases every source line.
;
VRAM:       EQU 0d000h
VCRTCA:     EQU 0d800h
VCRTCD:     EQU 0d802h

        ORG 3000h
        BR start
crtab:  DB 126            ; R0  horizontal total - 1                  ($3003)
        DB 80             ; R1  characters displayed
        DB 98             ; R2  horizontal sync position
        DB 10             ; R3  sync width
        DB 31             ; R4  vertical total - 1 (rows)
        DB 6              ; R5  vertical total adjust (scan lines)
        DB 24             ; R6  rows displayed
        DB 28             ; R7  vertical sync position (row)
        DB 0              ; R8  interlace off
        DB 7              ; R9  scan lines per row - 1
        DB 067h           ; R10 cursor start line 7, blinking 1/32
        DB 7              ; R11 cursor end line 7
        DB 0              ; R12 start address high
        DB 0              ; R13 start address low
        DB 3              ; R14 cursor high  (row 12, column 40 = 1000 = $03E8)
        DB 0e8h           ; R15 cursor low                             ($3012)

start:
; ---- the CRTC from the table
        MVIW R7,crtab
        LDAI 0
        STA rn
cinit:  LDA rn
        STA VCRTCA
        LDAVR R7
        STA VCRTCD
        INCR R7
        LDA rn
        ADDI 1
        STA rn
        LDTI 16
        BRNEQ cinit
; ---- clear the 2K
        MVIW R6,VRAM
clr:    LDAI ' '
        STAVR R6
        INCR R6
        MVRHA R6
        LDTI 0d8h
        BRNEQ clr
; ---- rows 0 and 1
        MVIW R6,VRAM
        MVIW R7,s_title
        JSR puts
        MVIW R6,VRAM+80
        MVIW R7,s_ruler
        JSR puts
; ---- rows 2 and 3: the 64 codes, plain then inverse
        MVIW R6,VRAM+160
        LDAI 0
        STA code
r2:     LDA code
        STAVR R6
        INCR R6
        ADDI 1
        STA code
        LDTI 64
        BRNEQ r2
        MVIW R7,s_codes
        JSR puts
        MVIW R6,VRAM+240
        LDAI 0
        STA code
r3:     LDA code
        ORI 080h
        STAVR R6
        INCR R6
        LDA code
        ADDI 1
        STA code
        LDTI 64
        BRNEQ r3
        MVIW R7,s_inv
        JSR puts
; ---- rows 4-22
        MVIW R6,VRAM+320
        MVIW R5,s_text
        LDAI 4
        STA row
rows:   STR R6,rowp
        LDA row                     ; the row number, two hex digits
        SHR
        SHR
        SHR
        SHR
        JSR hexd
        STAVR R6
        INCR R6
        LDA row
        ANDI 0fh
        JSR hexd
        STAVR R6
        INCR R6
        LDAI '*'
        STAVR R6
        INCR R6
        MOVRR R5,R7                 ; 76 characters from the text, one place further each row
        LDAI 76
        STA cnt
rtext:  LDAVR R7
        STAVR R6
        INCR R7
        INCR R6
        LDA cnt
        SUBI 1
        STA cnt
        BRNZ rtext
        LDAI '*'
        STAVR R6
        INCR R5
        LDR R6,rowp
        ADDIW R6,80
        LDA row
        ADDI 1
        STA row
        LDTI 23
        BRNEQ rows
; ---- row 23
        MVIW R7,s_last
        JSR puts                    ; R6 is row 23's start here
        RET

; puts: copy the zero-terminated string at R7 to the screen at R6 (both advanced)
puts:   LDAVR R7
        BRZ putx
        STAVR R6
        INCR R7
        INCR R6
        BR puts
putx:   RET

; hexd: ACC 0-15 -> its hex digit in ASCII
hexd:   LDTI 10
        BRLT hexn
        ADDI 37h
        RET
hexn:   ADDI 30h
        RET

rn:     DB 0
code:   DB 0
row:    DB 0
cnt:    DB 0
rowp:   DW 0
s_title: DB " YACC1 VIDEO TEST CARD - 80 X 24 - TESTCARD.ASM",0
s_ruler: DB "01234567890123456789012345678901234567890123456789012345678901234567890123456789",0
s_codes: DB " CODES 00-3F",0
s_inv:  DB " INVERSE",0
s_text: DB "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG 0123456789 "
        DB "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG 0123456789 ",0
s_last: DB "ROW 23 - LAST ROW. CURSOR AT ROW 12, COLUMN 40.",0
