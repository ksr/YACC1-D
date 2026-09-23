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
        HALT
sub:    LDAI 'B'
        RET
vec:    DW tgt
var:    DS 1
var2:   DS 2
        ORG 0F000H
        BR 0F003H
        MVIW R1,0EFFH
        JSR main
        HALT
        END 0F000H
