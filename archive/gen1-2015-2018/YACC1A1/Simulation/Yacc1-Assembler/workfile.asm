:start
        .orig   0x00
:start2
        LDRI R0 0x55
        LDRI R2 data
:top    MOV R0 R1
        STR R1 R2
        OUTVR R2 1
        LDA R0
        STRA R3
        INC R0
        BZ  start2
        BR top
:data