; romdiag.asm - a ROM-resident instruction check paced by the input switch (2026-09-22), for the bench after the
; microcode reload: romcount's count phase ran away on the machine, so this shows the result of each instruction
; the count loop depends on as a steady value on the LED board and the TIL311s, one stage per flip of the input
; switch (each stage waits for the line to change state, so a toggle switch advances one stage per flip).
;
;   stage  what                                   LEDs expected        (if wrong)
;   0      mirror the switches (as romcount)      the switches         -
;   1      LDAI 0AAH; OUTA                        AA                   the LED path from an immediate
;   2      MVIW R7,2011H; MVRHA R7                20                   MVRHA gives the low byte (11) or garbage
;   3      MVRLA R7                               11                   MVRLA
;   4      MVIW R7,0400H; DECR R7; MVRHA R7       03                   DECR (R7 = 03FF, high byte 03)
;   5      LDAI 0; BRNZ -> F0 else 01              01                   BRNZ taken on zero
;   6      LDAI 5; BRNZ -> 02 else F1              02                   BRNZ not taken on non-zero
;   7      ADDI 1 on 0FEH                         FF                   ADDI
;   8      the delay loop (2000H turns) then 55   55 (after a pause)   never arrives: the loop never exits
;   9      count from 0 with the delay, forever   00 01 02 ...         runs away: as romcount
;
; Registers: R1 = a stack (unused), R6 low = count, R7 = scratch/delay, R5 = the stage value while waiting.
SWITCHLED:  EQU 001H
TIL311:     EQU 080H
        ORG 0F000H
start:  BR  begin
begin:  MVIW R1,0EFFH
        OFF
mirror: OUTI P0,SWITCHLED       ; stage 0: mirror until the input line goes high
        INP  P1
        OUTA P1
        OUTI P0,TIL311
        OUTA P1
        BRINL mirror
        ON
        LDAI 0AAH               ; stage 1
        JSR  show
wlo1:   BRINH wlo1              ; wait for the line to go low
        MVIW R7,2011H           ; stage 2
        MVRHA R7
        JSR  show
whi2:   BRINL whi2
        MVRLA R7                ; stage 3
        JSR  show
wlo3:   BRINH wlo3
        MVIW R7,0400H           ; stage 4
        DECR R7
        MVRHA R7
        JSR  show
whi4:   BRINL whi4
        LDAI 0                  ; stage 5: BRNZ must fall through
        BRNZ bad5
        LDAI 001H
        BR   s5
bad5:   LDAI 0F0H
s5:     JSR  show
wlo5:   BRINH wlo5
        LDAI 5                  ; stage 6: BRNZ must be taken
        BRNZ good6
        LDAI 0F1H
        BR   s6
good6:  LDAI 002H
s6:     JSR  show
whi6:   BRINL whi6
        LDAI 0FEH               ; stage 7
        ADDI 1
        JSR  show
wlo7:   BRINH wlo7
        MVIW R7,2000H           ; stage 8: one delay, then 55
dly8:   DECR R7
        MVRHA R7
        BRNZ dly8
        LDAI 055H
        JSR  show
whi8:   BRINL whi8
        MVIW R6,0               ; stage 9: count with the delay
count:  MVRLA R6
        JSR  show
        MVIW R7,2000H
delay:  DECR R7
        MVRHA R7
        BRNZ delay
        MVRLA R6
        ADDI 1
        MVARL R6
        BR   count
;
show:   OUTI P0,SWITCHLED       ; ACC -> the LED board and the TIL311s (ACC preserved)
        OUTA P1
        OUTI P0,TIL311
        OUTA P1
        RET
