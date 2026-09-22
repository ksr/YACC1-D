; romcount.asm - a ROM-resident program to prove the EPROM tool chain (2026-09-22): burn it into the 28C64 in place of
; the monitor, reset the machine, and it runs from $F000 without the monitor.
;
;   1. While the I/O card's input-switch line is low, the LED board and the TIL311 displays follow the eight switches
;      (set a value, see it appear).  The ON/OFF LED is off.
;   2. Flip the input switch high: the ON/OFF LED lights and the count starts from the switch value, on the LEDs and
;      the TIL311s, one count per delay loop, wrapping at $FF.  Reset to go again.
;
; The delay is the word after MVIW R7 at `dlyw` (see the listing / README: two bytes in ROM you can patch in the
; programmer for a faster or slower count).  $2000 = 8,192 turns of a 3-instruction loop, about a quarter second at
; a 1 MHz clock; with the function generator at a few Hz make it $0010.
; Registers: R1 = a stack (unused), R6 low = the count, R7 = the delay counter, ACC/TMP scratch.  Never R2.
SWITCHLED:  EQU 001H
TIL311:     EQU 080H
        ORG 0F000H
start:  BR  begin               ; the first fetch under FORCE-ROM; the branch target's A15 releases the remap
begin:  MVIW R1,0EFFH
        OFF
mirror: OUTI P0,SWITCHLED       ; LEDs = switches, TIL311 = switches, until the input line goes high
        INP  P1
        OUTA P1
        OUTI P0,TIL311
        OUTA P1
        BRINL mirror
        ON                      ; counting
        MVARL R6                ; count = the switches
count:  MVRLA R6
        OUTI P0,SWITCHLED
        OUTA P1
        OUTI P0,TIL311
        OUTA P1
dlyw:   MVIW R7,2000H           ; the delay word (patch the two bytes after the opcode)
delay:  DECR R7
        MVRHA R7
        BRNZ delay
        MVRLA R6
        ADDI 1
        MVARL R6
        BR count
