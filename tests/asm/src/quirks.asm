; quirks.asm - RC/asm dialect corners for tests/asm/run.py (2026-09-25): every line here assembles in RC/asm
; (software/assembler) with 0 errors, and /BIN/ASM must produce the same bytes. Not a program: never run.
        ORG 3000H
start:  LDAI 0                          ; decimal, hex with H, characters
        LDAI 0FFH
        ldai 'a'                        ; single quotes keep the case: 61
        LDAI "a"                        ; double quotes are upper-cased first: 41
        LDAI ';'                        ; a quoted ';' is not a comment
        LDAI ':'                        ; nor a quoted ':' a label
        LDAI -1                         ; RC/asm drops a leading minus: 01
        LDAI 0-1                        ; -1 as a byte: FF (abs() is under 256)
        LDAI (0-255)                    ; 01
        LDAI 7!8                        ; '!' is OR
        LDAI 0F0H&3CH
        LDAI 2*3+4
        LDAI 100/7
        LDAI (0-100)/7                  ; C division rounds towards 0: -14 = F2
        LDAI 1+2*3.0                    ; '.' first, then '*', then '+'
        LDAI ((1+2)*(3+4))
        LDAI (target).0
        LDAI (target).1
        LDAI (0-2).1                    ; -2/256 = 0
        LDAI (0-300).1                  ; -1: FF
        LDAI 3H3                        ; every hex digit of a token with an H counts: 33
        LDAI 1A                         ; no H: atoi stops at the A
        MVIW R3,$                       ; the address of this instruction
        MVIW R4,$+3
        MVIW R5,target+4-2
        MVIW R6,0-1                     ; FFFF
        MVIW R7,65535
        MVIW R1,fwd                     ; a forward reference
        MOVRR R3,R4
        MOVRR R7,R1
        POPR R5
        PUSHR R2
        OUTI P0,(UARTA!UARTCS)
        OUTI PF,7
        OUTA PA
        INP P9
        LDIVR R3,'Z'
        LDZ R3,(zvar).0
        STZ R4,(zvar+1).0
        ADDIW R3,1000
        SHL16 R5
        BRVR R6
        JSRUR R7
        BRUR R3
        JSR target
        BRZ start
        IADDR 1234H
        LDA zvar+1
        STR R3,zvar
	LDR	R4,zvar		; tabs
UARTA:  EQU 18H
UARTCS: EQU 40H
REGX:   EQU R5                          ; a register name as an EQU value: 5
        MVIB R3,REGX
twice:  EQU 2*UARTA
        LDAI twice
        DB 1,2,3
        DB "Hello, world",0             ; upper-cased, the comma inside quotes stays
        DB 'Mixed Case',10,13
        DB 'it''s'                       ; two quoted items: IT, S
        DB "a;b:c"                       ; ';' and ':' inside quotes
        DB HIGH 1234H
        DB HIGH target
        DB (target).0,(target).1,$
        DW 1234H
        DW target,fwd,$
        DW "AB",0                       ; a string in DW: a byte and its high byte 0 each
        DW 1,2,3
        DS 5                            ; a new hex record after DS
        DB 99
        DS (256-(pad).0)&255            ; the --xisa page alignment: the label on this line counts
pad:    DB 0
        ORG 3200H                       ; a gap
target: RET
fwd:    HALT
        LDAI  1   ;  spaces
zvar:   DS 2
        INCLUDE quirks1.inc
        LDAI inc1v
        LDAI inc2v
        DB 11H,22H,33H,44H,55H,66H,77H,88H,99H,0AAH,0BBH,0CCH,0DDH,0EEH,0FFH,00H,01H,02H,03H,04H,05H
        END start
