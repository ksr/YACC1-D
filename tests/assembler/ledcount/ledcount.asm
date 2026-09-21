; ledcount.asm - 16-byte switch-ROM program: count up by one and show the count on the IO card's LED board.
; Same LED idiom as the monitor's ledout (OUTI P0,SWITCHLED selects the switch/LED board, OUTA P1 writes the byte).
; 12 bytes at $0000; fits the Mem Switch card. Speed = the CPU clock: at 1 Hz the LEDs step visibly.
SWITCHLED:  EQU 001H
        ORG 0000H
        LDAI 0                  ; count = 0
loop:   OUTI P0,SWITCHLED       ; select the LED board
        OUTA P1                 ; LEDs = count
        ADDI 1                  ; count += 1
        BR loop                 ; forever
