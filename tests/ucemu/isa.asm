; isa.asm - differential test of the ISA: every arithmetic, logic, shift, compare, register, memory and stack
; instruction, each result written raw to port 2. Run on the instruction-level emulator and on the microcode-level
; emulator; the two byte streams must be identical (tests/ucemu/run.py does that). Expected values in comments.
        ORG 3000H
main:   LDAI 5
        ADDI 3
        OUTA P2                 ; 08
        LDTI 7
        LDAI 9
        ADDT
        OUTA P2                 ; 10
        LDAI 200
        ADDI 100
        OUTA P2                 ; 2C, carry 1
        LDAI 1
        ADDIC 0
        OUTA P2                 ; 02
        LDAI 200
        LDTI 100
        ADDT
        LDAI 1
        ADDTC
        OUTA P2                 ; 66 (1+100+carry)
        LDAI 9
        SUBI 3
        OUTA P2                 ; 06
        LDTI 4
        LDAI 9
        SUBT
        OUTA P2                 ; 05
        LDAI 3
        SUBI 5
        OUTA P2                 ; FE
        LDAI 0F0H
        ANDI 03CH
        OUTA P2                 ; 30
        ORI 5
        OUTA P2                 ; 35
        XORI 0FFH
        OUTA P2                 ; CA
        INVA
        OUTA P2                 ; 35
        LDTI 0F0H
        LDAI 0FH
        ORT
        OUTA P2                 ; FF
        ANDT
        OUTA P2                 ; F0
        XORT
        OUTA P2                 ; 00
        LDAI 081H
        SHL
        OUTA P2                 ; 02
        LDAI 081H
        SHR
        OUTA P2                 ; 40
        LDAI 081H
        RSHL
        OUTA P2                 ; 03
        LDAI 081H
        RSHR
        OUTA P2                 ; C0
        LDAI 081H
        PSHR
        OUTA P2                 ; C0
        LDAI 0
        CSHL                    ; carry := 0
        LDAI 081H
        CSHL
        OUTA P2                 ; 02, carry 1
        LDAI 0
        CSHL
        OUTA P2                 ; 01
        LDAI 0
        CSHL                    ; carry := 0
        LDAI 081H
        CSHR
        OUTA P2                 ; 40, carry 1
        LDAI 0
        CSHR
        OUTA P2                 ; 80
; compares: ACC vs TMP
        LDTI 5
        LDAI 3
        BRLT c1
        LDAI 'N'
        BR c1e
c1:     LDAI 'Y'
c1e:    OUTA P2                 ; Y  (3 < 5)
        LDAI 3
        BRGT c2
        LDAI 'N'
        BR c2e
c2:     LDAI 'Y'
c2e:    OUTA P2                 ; N
        LDAI 5
        BREQ c3
        LDAI 'N'
        BR c3e
c3:     LDAI 'Y'
c3e:    OUTA P2                 ; Y
        LDAI 5
        BRNEQ c4
        LDAI 'N'
        BR c4e
c4:     LDAI 'Y'
c4e:    OUTA P2                 ; N
        LDAI 9
        BRGT c5
        LDAI 'N'
        BR c5e
c5:     LDAI 'Y'
c5e:    OUTA P2                 ; Y  (9 > 5)
        LDAI 0
        BRZ c6
        LDAI 'N'
        BR c6e
c6:     LDAI 'Y'
c6e:    OUTA P2                 ; Y
        LDAI 7
        BRNZ c7
        LDAI 'N'
        BR c7e
c7:     LDAI 'Y'
c7e:    OUTA P2                 ; Y
        LDAI 0
        BRNZ c8
        LDAI 'N'
        BR c8e
c8:     LDAI 'Y'
c8e:    OUTA P2                 ; N
        LDAI 200
        ADDI 100                ; carry 1
        BRC c9
        LDAI 'N'
        BR c9e
c9:     LDAI 'Y'
c9e:    OUTA P2                 ; Y
        LDAI 1
        ADDI 1                  ; carry 0
        BRC c10
        LDAI 'N'
        BR c10e
c10:    LDAI 'Y'
c10e:   OUTA P2                 ; N
; 16-bit registers
        MVIW R3,1234H
        MVRLA R3
        OUTA P2                 ; 34
        MVRHA R3
        OUTA P2                 ; 12
        LDAI 056H
        MVARL R3
        LDAI 078H
        MVARH R3
        MVRLA R3
        OUTA P2                 ; 56
        MVRHA R3
        OUTA P2                 ; 78
        INCR R3
        MVRLA R3
        OUTA P2                 ; 57
        DECR R3
        DECR R3
        MVRLA R3
        OUTA P2                 ; 55
        MVIW R3,00FFH
        INCR R3
        MVRHA R3
        OUTA P2                 ; 01 (carry into the high byte)
        MVRLA R3
        OUTA P2                 ; 00
        MOVRR R3,R4
        MVRHA R4
        OUTA P2                 ; 01
        MVIB R4,077H
        MVRLA R4
        OUTA P2                 ; 77
        MVRHA R4
        OUTA P2                 ; 01
        MOVRR R4,R7             ; across the two register cards
        MVRLA R7
        OUTA P2                 ; 77
; memory
        MVIW R5,var
        LDAI 0AAH
        STAVR R5
        LDAVR R5
        OUTA P2                 ; AA
        LDA var
        OUTA P2                 ; AA
        LDAI 055H
        STA var
        LDAVR R5
        OUTA P2                 ; 55
        MVIW R6,0BEEFH
        STR R6,var2
        LDR R7,var2
        MVRLA R7
        OUTA P2                 ; EF
        MVRHA R7
        OUTA P2                 ; BE
        LDT var
        MVTA
        OUTA P2                 ; 55
        LDAI 0
        STT var2
        LDA var2
        OUTA P2                 ; 55
        LDIVR R5,099H
        LDAVR R5
        OUTA P2                 ; 99
; stack
        LDAI 042H
        PUSH
        LDAI 0
        POP
        OUTA P2                 ; 42
        MVIW R3,0ABCDH
        PUSHR R3
        MVIW R3,0
        POPR R3
        MVRLA R3
        OUTA P2                 ; CD (H-1: PUSHR fights the bus)
        MVRHA R3
        OUTA P2                 ; AB
        JSR sub
        OUTA P2                 ; 'B' (after the call)
        MVIW R7,sub
        JSRUR R7
        OUTA P2                 ; 'B'
        MVIW R7,vec
        BRVR R7                 ; indirect: PC <- [vec] = tgt
        LDAI 'N'
        OUTA P2
tgt:    LDAI 'V'
        OUTA P2                 ; V
        MVIW R7,tgt2
        BRUR R7                 ; direct
        LDAI 'N'
        OUTA P2
tgt2:   LDAI 'U'
        OUTA P2                 ; U
        BRDEV dev
        LDAI 'I'                ; the interpreter prints I (BRDEV does not branch there)
        OUTA P2
dev:    LDAI 'D'                ; the microcode prints D only (BRDEV = BR)
        OUTA P2
; 2026-09-23: a stale SHIFT-OUT must not reach the carry of a later add or subtract. The ALU's carry flip-flop
; latches CO/BO OR SHIFT-OUT; the microcode clears SHIFT-OUT before every ADD/SUB (aluOp). Found on the machine.
        LDAI 80H
        SHL                     ; shifts a 1 out: SHIFT-OUT = 1, carry = 1
        LDAI 1
        LDTI 1
        ADDT                    ; 1 + 1 = 2, no carry out: the carry must now be 0
        LDAI 0
        LDTI 0
        ADDTC
        OUTA P2                 ; 00 (the old microcode on the machine: 01)
        LDAI 80H
        SHL
        LDAI 10H
        ADDI 20H                ; no carry
        LDAI 0
        ADDIC 0
        OUTA P2                 ; 00
; 2026-09-24: the page instructions LDZ/STZ ($80-$8F: the word at (R6.hi : d)), ADDIW ($C0-$C7: Rn += w) and
; SHL16 ($C8-$CF: Rn <<= 1). Every register they are meant for: R1 (with SP saved in R5 and nothing pushed meanwhile),
; R3-R7, and R2 for ADDIW/SHL16 only (LDZ/STZ address through R2 = IR; R2 is read back before the next output, which
; on the machine goes through outb's LDR/STR and so reloads R2). R0 is not tested: the machine loads R0 only when a
; branch is taken (the sequencer's load gate), the interpreter always. The page is zpg ($4000); d = 255 reaches
; its second byte at $4100.
        MVIW R6,zpg
        LDZ R3,0
        MVRHA R3
        OUTA P2                 ; 12
        MVRLA R3
        OUTA P2                 ; 34
        LDZ R4,254
        MVRHA R4
        OUTA P2                 ; 56
        MVRLA R4
        OUTA P2                 ; 78
        LDZ R5,255              ; $40FF, then $4100
        MVRHA R5
        OUTA P2                 ; 78
        MVRLA R5
        OUTA P2                 ; BC
        LDZ R7,2
        MVRHA R7
        OUTA P2                 ; DE
        MVRLA R7
        OUTA P2                 ; F0
        MOVRR R1,R5             ; LDZ R1: SP saved in R5
        LDZ R1,2
        MOVRR R1,R3
        MOVRR R5,R1
        MVRLA R3
        OUTA P2                 ; F0
        MVIW R3,0A1B2H
        STZ R3,4
        LDA zpg+4
        OUTA P2                 ; A1
        LDA zpg+5
        OUTA P2                 ; B2
        MVIW R4,0C3D4H
        STZ R4,255              ; $40FF, then $4100
        LDA zpg+255
        OUTA P2                 ; C3
        LDA zpg+256
        OUTA P2                 ; D4
        MVIW R5,0E5F6H
        STZ R5,6
        MVIW R7,01728H
        STZ R7,10
        LDR R3,zpg+6
        MVRLA R3
        OUTA P2                 ; F6
        LDR R3,zpg+10
        MVRHA R3
        OUTA P2                 ; 17
        MOVRR R1,R5             ; STZ R1: SP saved in R5
        MVIW R1,3949H
        STZ R1,12
        MOVRR R5,R1
        LDA zpg+13
        OUTA P2                 ; 49
        MVIW R6,zpg2            ; the page register itself: page $41
        LDZ R3,0
        MVRHA R3
        OUTA P2                 ; D4 (written by STZ R4,255)
        MVIW R6,zpg
        STZ R6,14               ; the page register as data
        LDA zpg+14
        OUTA P2                 ; 40
        LDZ R6,16               ; loads the page register: $4100
        LDZ R4,1                ; now from page $41: $4101-$4102
        MVRHA R4
        OUTA P2                 ; 65
; ADDIW: carries across the bytes and out of bit 15, ACC = the result's high byte, TMP kept
        MVIW R3,12FFH
        LDTI 5AH
        ADDIW R3,0001H
        OUTA P2                 ; 13 (ACC)
        MVRLA R3
        OUTA P2                 ; 00
        MVTA
        OUTA P2                 ; 5A (TMP kept)
        BRC d1
        LDAI 'N'
        BR d1e
d1:     LDAI 'Y'
d1e:    OUTA P2                 ; N
        MVIW R4,0FFFFH
        ADDIW R4,0001H
        BRC d2
        LDAI 'N'
        BR d2e
d2:     LDAI 'Y'
d2e:    OUTA P2                 ; Y (carry out of bit 15)
        MVRHA R4
        OUTA P2                 ; 00
        MVIW R5,8421H
        ADDIW R5,8421H
        MVRHA R5
        OUTA P2                 ; 08
        MVRLA R5
        OUTA P2                 ; 42
        MVIW R7,00F0H
        ADDIW R7,0F020H
        MVRHA R7
        OUTA P2                 ; F1
        MVRLA R7
        OUTA P2                 ; 10
        MVIW R6,1000H
        ADDIW R6,0FFFFH
        MVRHA R6
        OUTA P2                 ; 0F
        MVRLA R6
        OUTA P2                 ; FF
        MVIW R2,0ABCDH
        ADDIW R2,1111H
        MVRLA R2
        MVAT
        MVRHA R2
        OUTA P2                 ; BC
        MVTA
        OUTA P2                 ; DE
        MOVRR R1,R5             ; ADDIW R1: SP saved in R5
        ADDIW R1,0100H
        MOVRR R1,R3
        MOVRR R5,R1
        MOVRR R5,R4
        MVRHA R3
        MVAT
        MVRHA R4
        ADDI 1
        BREQ d3                 ; R3.hi = SP.hi + 1
        LDAI 'N'
        BR d3e
d3:     LDAI 'Y'
d3e:    OUTA P2                 ; Y
; SHL16: carries across the bytes and out of bit 15, ACC = the result's high byte, TMP kept
        MVIW R3,4081H
        LDTI 77H
        SHL16 R3
        OUTA P2                 ; 81 (ACC)
        MVRLA R3
        OUTA P2                 ; 02
        MVTA
        OUTA P2                 ; 77 (TMP kept)
        BRC e1
        LDAI 'N'
        BR e1e
e1:     LDAI 'Y'
e1e:    OUTA P2                 ; N
        MVIW R4,8001H
        SHL16 R4
        BRC e2
        LDAI 'N'
        BR e2e
e2:     LDAI 'Y'
e2e:    OUTA P2                 ; Y (bit 15 out)
        MVRHA R4
        OUTA P2                 ; 00
        MVRLA R4
        OUTA P2                 ; 02
        LDAI 0
        ADDIC 0
        OUTA P2                 ; 01 (SHL16 R4's carry survives the moves and outputs)
        MVIW R5,00C0H
        SHL16 R5
        MVRHA R5
        OUTA P2                 ; 01
        MVRLA R5
        OUTA P2                 ; 80
        MVIW R7,0C000H
        SHL16 R7
        MVRHA R7
        OUTA P2                 ; 80
        MVIW R6,1234H
        SHL16 R6
        SHL16 R6
        MVRHA R6
        OUTA P2                 ; 48
        MVRLA R6
        OUTA P2                 ; D0
        MVIW R2,0A55AH
        SHL16 R2
        MVRLA R2
        MVAT
        MVRHA R2
        OUTA P2                 ; 4A
        MVTA
        OUTA P2                 ; B4
        MOVRR R1,R5             ; SHL16 R1: SP saved in R5
        MVIW R1,1111H
        SHL16 R1
        MOVRR R1,R3
        MOVRR R5,R1
        MVRLA R3
        OUTA P2                 ; 22
        HALT
sub:    LDAI 'B'
        RET
vec:    DW tgt
var:    DS 1
var2:   DS 2
        ORG 4000H               ; the page of the LDZ/STZ tests
zpg:    DB 12H,34H,0DEH,0F0H
        DB 0,0,0,0,0,0,0,0,0,0,0,0
        DB 41H,00H
        ORG 40FEH
        DB 56H,78H
zpg2:   DB 0BCH,65H,43H
        ORG 0F000H
        BR 0F003H
        MVIW R1,0EFFH
        JSR main
        HALT
        END 0F000H
