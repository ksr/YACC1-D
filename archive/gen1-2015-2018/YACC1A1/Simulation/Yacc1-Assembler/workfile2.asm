        .orig   0x00
        LDSP 0xFE
        INTE
:start2
        LDRI R0 0x54
        LDRI R1 data
        LDRI R2 0x02
        LDRI R3 sub
:top    CALL R3
        STR R0 R1
        OUTVR R1 1
        LDA R0
        ADD R2
        STRA R0
        BRZ R0 start2
        BR top
:sub    LON
        LOFF
        RET
:int
        OUTVR R1 2
        IRET

:data
    .orig FF
    .data int
