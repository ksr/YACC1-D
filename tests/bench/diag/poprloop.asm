; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
;
; poprloop.asm - bench diagnostic (2026-10-10): POPR, endlessly, for single-stepping with the bus tester as the clock
; (embedded/bus-tester/bus-stepper, tools/busstep.py). POPR loads wrong values at 1 MHz and right ones at 6 MHz
; (tests/bench/diag/pushr.asm). The loop pushes $ABCD, pops it into R3, pushes R3 again - so the popped value
; appears on the data bus during that PUSHR's -MEM-WR - and pops it into R4 to keep the stack balanced.
; Start with tools/monload.py --go 3000 at full speed, then switch the sequencer to SS: `busstep.py fADDR,08` stops on
; the POPR fetch (ADDR from the listing, label pop1).
;
        ORG 3000h
loop:   MVIW R3,0ABCDh
        PUSHR R3
        MVIW R3,0
pop1:   POPR R3
        PUSHR R3
        POPR R4
        BR loop
