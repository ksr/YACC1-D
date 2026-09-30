; dis.asm - the known program of tests/os/disasm.session (2026-09-29): every operand form /BIN/DISASM prints, at
; $C000 (above disasm itself at $5000, inside the `load` range $5000-$CFFF), then bytes that begin no instruction.
; tests/os/run.py assembles it with RC/asm (EXTRA) and puts it on the disk as /DIS (load C000).
        ORG 0C000H
start:  MVIW R1,0CFFFH          ; register in the opcode + a word (0 before a letter)
        LDAI 5                  ; a byte
        MVIB R3,0A5H
        MOVRR R4,R5             ; two registers in one operand byte
        POPR R6                 ; the register << 4
        PUSHR R7                ; the register in the operand byte
        JSRUR R3
        BRUR R4                 ; $AD (2026-09-22)
        OUTI P1,80H             ; a port in the opcode + a byte
        INP PA
        OUTA PF
        LDZ R3,10H              ; the --xisa four (2026-09-24)
        STZ R5,0FEH
        ADDIW R7,1234H
        SHL16 R2
        LDR R3,start
        STR R4,0FFFEH
        JSR 1000H
        BRNZ start
        RET
        DB 0                    ; not an opcode
        DB 6,8                  ; JSRUR with a register byte over 7
        DB 4,12H                ; JSR cut off by the end of the file
