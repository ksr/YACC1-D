; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
;
; listread.asm - bench diagnostic (2026-10-07): BASIC's LIST shows line 20 of "10 L=0 / 20 C=0" as 18452 ($4814) on
; the machine, both emulators show 20. The program bytes in memory are right ($100D: 25 14 00 = line 20); LIST reads
; the high byte $00 at $100F as $48. This program does LIST's reads on its own, at the same addresses, on a copy of
; the same 26 bytes, eight times each:
;   T1  INCR R3 / LDAVR R3 of $100F, printed as a byte
;   T2  LIST's line-number read (baslist37): INCR, LDAVR, MVARL R7, INCR, LDAVR, MVARH R7 -> R7 printed
;   T3  T2 right after printing CR/LF through the ROM (LIST does that at the end of line 1)
;   T4  T2 on line 10's number at $1001 (read right by LIST)
;   T5  LIST's order with BASIC's own exe_itoa ($E5FF in ROM 2026-10-07): itoa(0), a space, the read of line 20,
;       R7 shown in hex, then itoa(R7); each pass prints "0 0014=20"
; Every value should print 14 / 0014 / 0014 / 000A / 0 0014=20. Load with tools/monload.py --go 3000.
; The hex bounds are written as numbers: the assembler upper-cases every source line.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showr7:     EQU 0ffd4h
showbytea:  EQU 0ffe0h
exe_itoa:   EQU 0e5ffh          ; BASIC's decimal print of R7 (firmware/basic/basic.lst, ROM 2026-10-07)

        ORG 1000h
prog:   DB 25h,0ah,00h,0dh,00h,04h,0bh,00h,23h,02h,00h,00h,24h      ; 10 L = 0
        DB 25h,14h,00h,0dh,00h,04h,02h,00h,23h,02h,00h,00h,24h      ; 20 C = 0
        DB 01h                                                      ; end

        ORG 3000h
start:
        MVIW R7,s_t1
        JSR stringout
        MVIW R5,8
t1:     MVIW R3,100eh
        INCR R3
        LDAVR R3
        JSR showbytea
        LDAI 20h
        JSR charout
        DECR R5
        MVRLA R5
        BRNZ t1

        MVIW R7,s_t2
        JSR stringout
        MVIW R5,8
t2:     MVIW R3,100dh
        JSR rdnum
        JSR showr7
        LDAI 20h
        JSR charout
        DECR R5
        MVRLA R5
        BRNZ t2

        MVIW R7,s_t3
        JSR stringout
        MVIW R5,8
t3:     MVIW R7,crlf
        JSR stringout
        MVIW R3,100dh
        JSR rdnum
        JSR showr7
        DECR R5
        MVRLA R5
        BRNZ t3

        MVIW R7,s_t4
        JSR stringout
        MVIW R5,8
t4:     MVIW R3,1000h
        JSR rdnum
        JSR showr7
        LDAI 20h
        JSR charout
        DECR R5
        MVRLA R5
        BRNZ t4

        MVIW R7,s_t5
        JSR stringout
        MVIW R5,8
t5:     MVIW R7,crlf
        JSR stringout
        MVIW R7,0
        JSR exe_itoa
        LDAI 20h
        JSR charout
        MVIW R3,100dh
        JSR rdnum
        JSR showr7
        LDAI 3dh            ; '='
        JSR charout
        JSR exe_itoa
        DECR R5
        MVRLA R5
        BRNZ t5

        MVIW R7,s_end
        JSR stringout
        RET

; rdnum: R3 at a line-number token -> R7 = its number, exactly as basic.asm's baslist37 reads it
rdnum:  INCR R3
        LDAVR R3
        MVARL R7
        INCR R3
        LDAVR R3
        MVARH R7
        RET

crlf:   DB 0ah,0dh,0
s_t1:   DB 0ah,0dh,"T1 100F: ",0
s_t2:   DB 0ah,0dh,"T2 LINE 20: ",0
s_t3:   DB 0ah,0dh,"T3 AFTER CRLF:",0
s_t4:   DB 0ah,0dh,"T4 LINE 10: ",0
s_t5:   DB 0ah,0dh,"T5 ITOA(0) THEN LINE 20:",0
s_end:  DB 0ah,0dh,"LISTREAD DONE",0ah,0dh,0
