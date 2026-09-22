; brur.asm - test of BRUR Rn (opcode $AD, 2026-09-22): PC <- Rn, no return address, Rn unchanged.
; Prints "AB" then a computed jump through a table of addresses picks "C", then a loop counts 0..3 through
; BRUR-based dispatch and prints the digits, then HALT. Expected console output: ABC0123
; Run: emulator -x -f brur.img  (boot stub at $F000 like the compiler's --boot)
        ORG 3000H
main:   MVIW R5,two             ; direct: jump to the address in R5
        BRUR R5
        LDAI 'X'                ; skipped
        OUTA P2
two:    LDAI 'A'
        OUTA P2
        MVIW R5,three
        LDAI 'B'
        OUTA P2
        BRUR R5
        HALT
three:  MVIW R6,table+4         ; computed: fetch an address from a table, jump to it
        LDAVR R6
        MVARH R5
        INCR R6
        LDAVR R6
        MVARL R5
        BRUR R5
        HALT
sayC:   LDAI 'C'
        OUTA P2
        MVIW R7,0               ; counter 0..3
loop:   MVIW R6,digits          ; R5 = digits[R7*2 .. +1]
        MVRLA R7
        MVAT
        MVRLA R6
        ADDT
        MVARL R6                ; low byte add only: the table sits inside one page
        LDAVR R6
        MVARH R5
        INCR R6
        LDAVR R6
        MVARL R5
        BRUR R5                 ; dispatch (R5 must be unchanged after BRUR: next uses it? no, R7 is the state)
d0:     LDAI '0'
        BR next
d1:     LDAI '1'
        BR next
d2:     LDAI '2'
        BR next
d3:     LDAI '3'
        OUTA P2
        HALT
next:   OUTA P2
        INCR R7
        INCR R7
        BR loop
table:  DW two,three,sayC
digits: DW d0,d1,d2,d3
        ORG 0F000H
        MVIW R1,0EFFH
        JSR main
        HALT
        END 0F000H
