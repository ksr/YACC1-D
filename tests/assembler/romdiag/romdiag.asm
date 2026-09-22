; romdiag.asm - a ROM-resident instruction check paced by the input switch (2026-09-22), for the bench after the
; microcode reload: romcount's count phase lit every LED on the machine.  Cause found with the first build of this
; ROM: the bring-up machine has ONE index-register card (R0..R3); R4..R7 read as a floating bus ($FF).  This build
; uses R3 and TMP, and stage 9 probes R7 so the LEDs say whether register card 1 is fitted.
; Each stage waits for the input line to change state, so a toggle switch advances one stage per flip.
;
;   stage  what                                   LEDs expected        (if wrong)
;   0      mirror the switches (as romcount)      the switches         -
;   1      LDAI 0AAH; OUTA (via JSR show)         AA                   the LED path from an immediate, JSR/RET
;   2      MVIW R3,2011H; MVRHA R3                20                   MVRHA gives the low byte (11) or garbage
;   3      MVRLA R3                               11                   MVRLA
;   4      MVIW R3,0400H; DECR R3; MVRHA R3       03                   DECR (R3 = 03FF, high byte 03)
;   5      LDAI 0; BRNZ -> F0 else 01              01                   BRNZ taken on zero
;   6      LDAI 5; BRNZ -> 02 else F1              02                   BRNZ not taken on non-zero
;   7      ADDI 1 on 0FEH                         FF                   ADDI
;   8      LDAI 33H; MVAT; LDAI 0; MVTA           33                   TMP (MVAT/MVTA)
;   9      MVIW R7,2011H; MVRHA R7                20 = card 1 fitted   FF = no register card 1 (R4..R7 absent)
;   10     the delay loop (2000H turns, R3) then 55   55 (after a pause)   never arrives: the loop never exits
;   11     count from 0 in TMP with the delay     00 01 02 ...         runs away or freezes: see stages 4-8
;
; Registers: R1 = a stack, R3 = scratch/delay, TMP = the count.  Never R2.
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
        MVIW R3,2011H           ; stage 2
        MVRHA R3
        JSR  show
whi2:   BRINL whi2
        MVRLA R3                ; stage 3
        JSR  show
wlo3:   BRINH wlo3
        MVIW R3,0400H           ; stage 4
        DECR R3
        MVRHA R3
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
        LDAI 033H               ; stage 8: TMP round trip
        MVAT
        LDAI 0
        MVTA
        JSR  show
whi8:   BRINL whi8
        MVIW R7,2011H           ; stage 9: is register card 1 (R4..R7) there?
        MVRHA R7
        JSR  show
wlo9:   BRINH wlo9
        MVIW R3,2000H           ; stage 10: one delay, then 55
dly10:  DECR R3
        MVRHA R3
        BRNZ dly10
        LDAI 055H
        JSR  show
whi10:  BRINL whi10
        LDAI 0                  ; stage 11: count in TMP with the delay
        MVAT
count:  MVTA
        JSR  show
        MVIW R3,2000H
delay:  DECR R3
        MVRHA R3
        BRNZ delay
        MVTA
        ADDI 1
        MVAT
        BR   count
;
show:   OUTI P0,SWITCHLED       ; ACC -> the LED board and the TIL311s (ACC preserved)
        OUTA P1
        OUTI P0,TIL311
        OUTA P1
        RET
