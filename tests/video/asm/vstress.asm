; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
;
; vstress.asm - video card bring-up (2026-10-10): the CPU writing the display RAM at full speed while the 6845 reads it
; through the IDT7134's other port. Run testcard.asm first (CRTC programmed, card drawn), then this: rows 4-22 (1,216
; bytes of the 64-column card) get every glyph code added by one, over and over - the text rolls through the whole character set - and row 23
; counts the passes in hex. The test card returns when it stops: any key on the console ends it.
; What to watch: snow, torn or wrong characters while the CPU writes (dual-port contention), characters that stay
; wrong after the rolling stops, the count stopping (a crash). Load: tools/monload.py --go 3000 vstress.img.
; No R2. Hex as numbers: the assembler upper-cases every source line.
;
CONST:      EQU 0fff8h          ; ACC = 1 when a console byte is waiting
UARTINNE:   EQU 0fffch          ; the byte, without echo
VRAM:       EQU 0d000h

        ORG 3000h
        MVIW R5,0               ; the pass count
pass:   MVIW R7,VRAM+256        ; rows 4-22 (64 columns)
add1:   LDAVR R7
        ADDI 1
        STAVR R7
        INCR R7
        MVRHA R7
        LDTI 0d5h
        BRNEQ add1
        MVRLA R7                ; $D000+256+1216 = $D5C0: stop at $D5C0
        LDTI 0c0h
        BRNEQ add1
        INCR R5
        MVIW R7,VRAM+1472+48    ; row 23, column 48: the pass count in hex
        MVRHA R5
        JSR hex2
        MVRLA R5
        JSR hex2
        JSR CONST
        BRZ pass
        JSR UARTINNE
        RET

; hex2: ACC as two hex digits at R7 (R7 advanced by 2)
hex2:   STA hb
        SHR
        SHR
        SHR
        SHR
        JSR hexd
        STAVR R7
        INCR R7
        LDA hb
        ANDI 0fh
        JSR hexd
        STAVR R7
        INCR R7
        RET
hexd:   LDTI 10
        BRLT hexn
        ADDI 37h
        RET
hexn:   ADDI 30h
        RET
hb:     DB 0
