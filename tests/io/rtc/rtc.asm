; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

;
; rtc.asm - the I/O card V1.2's clock, a DS12885, from a YACC1 program on the emulators (2026-11-20): Y1IO_CARD=v1.2,
; software/rtcmodel.h. Port 6 takes the register number, port 7 reads or writes the register (docs/cards/rtc.md).
;   RTC     is the chip there: RAM $20 <- A5, RAM $21 <- 5A, then both read back (ACC is 0 before each read, and the
;           register number is the last byte on the bus: without the chip neither A5 nor 5A comes back)
;   REGS    registers A, B and D as found: 26 (the oscillator on, 1024 Hz), 06 (binary, 24-hour), 80 (the cell good)
;   FOUND   year month day hours minutes as found: the time the emulator was started with
;   SET     the time set as a program does it: B <- 82 (SET, 24-hour, BCD), 2099-12-31 23:59:58, day 7, B <- 02;
;           then the seconds read back, read again after they changed, and once more: 58 59 00
;   AFTER   year month day hours minutes and the day of the week after that midnight: 00 01 01 00 00 01
;   RAM     $0E <- 11, $7F <- 22, $32 <- 33 (no century register on this chip: RAM), read back
;   FLAGS   A <- 20 (no periodic rate), register C read to clear it, a second waited, then C read twice with nothing
;           between: 10 (UF: an update ended) and 00 (the read cleared it)
; Load: the monitor's : loader, then G3000. No R2.
;
stringout:  EQU 0ffc0h
charout:    EQU 0ffc4h
showbytea:  EQU 0ffe0h

        ORG 3000h
start:  MVIW R7,s_head
        JSR stringout
; ---- RTC: is the chip there
        MVIW R7,s_rtc
        JSR stringout
        OUTI P6,20h
        OUTI P7,0a5h
        OUTI P6,21h
        OUTI P7,05ah
        OUTI P6,20h
        LDAI 0
        INP P7
        JSR showbytea
        JSR space
        OUTI P6,21h
        LDAI 0
        INP P7
        JSR showbytea
        JSR crlf
; ---- REGS: A, B, D as found
        MVIW R7,s_regs
        JSR stringout
        LDAI 0ah
        JSR show
        LDAI 0bh
        JSR show
        LDAI 0dh
        JSR show
        JSR crlf
; ---- FOUND: the date and the time of day as found
        MVIW R7,s_found
        JSR stringout
        JSR date
        JSR crlf
; ---- SET: 2099-12-31 23:59:58, in BCD, with SET held
        OUTI P6,0bh
        OUTI P7,082h
        OUTI P6,9
        OUTI P7,099h
        OUTI P6,8
        OUTI P7,012h
        OUTI P6,7
        OUTI P7,031h
        OUTI P6,6
        OUTI P7,7
        OUTI P6,4
        OUTI P7,023h
        OUTI P6,2
        OUTI P7,059h
        OUTI P6,0
        OUTI P7,058h
        OUTI P6,0bh
        OUTI P7,2
        MVIW R7,s_set
        JSR stringout
        OUTI P6,0
        INP P7
        STA last
        JSR showbytea
        JSR space
        JSR tick
        JSR showbytea
        JSR space
        JSR tick
        JSR showbytea
        JSR crlf
; ---- AFTER: the new century's first minute
        MVIW R7,s_after
        JSR stringout
        JSR date
        LDAI 6
        JSR show
        JSR crlf
; ---- RAM
        OUTI P6,0eh
        OUTI P7,011h
        OUTI P6,07fh
        OUTI P7,022h
        OUTI P6,032h
        OUTI P7,033h
        MVIW R7,s_ram
        JSR stringout
        LDAI 0eh
        JSR show
        LDAI 07fh
        JSR show
        LDAI 032h
        JSR show
        JSR crlf
; ---- FLAGS: UF after a second, cleared by the read
        OUTI P6,0ah
        OUTI P7,020h
        OUTI P6,0ch
        INP P7
        JSR tick
        OUTI P6,0ch
        INP P7
        STA c1
        INP P7
        STA c2
        MVIW R7,s_flags
        JSR stringout
        LDA c1
        JSR showbytea
        JSR space
        LDA c2
        JSR showbytea
        JSR crlf
        MVIW R7,s_done
        JSR stringout
        RET

; show: the register ACC names, in hex, and a space
show:   OUTA P6
        INP P7
        JSR showbytea
        JSR space
        RET

; date: year month day hours minutes
date:   LDAI 9
        JSR show
        LDAI 8
        JSR show
        LDAI 7
        JSR show
        LDAI 4
        JSR show
        LDAI 2
        JSR show
        RET

; tick: wait until the seconds register is no longer `last`; the new seconds in ACC and in `last`
tick:   OUTI P6,0
tick1:  LDA last
        MVAT
        INP P7
        BREQ tick1
        STA last
        RET

space:  LDAI 32
        JSR charout
        RET
crlf:   LDAI 13
        JSR charout
        LDAI 10
        JSR charout
        RET

last:   DB 0
c1:     DB 0
c2:     DB 0
s_head: DB 13,10,"RTC TEST",13,10,0
s_rtc:  DB "RTC ",0
s_regs: DB "REGS ",0
s_found: DB "FOUND ",0
s_set:  DB "SET ",0
s_after: DB "AFTER ",0
s_ram:  DB "RAM ",0
s_flags: DB "FLAGS ",0
s_done: DB "DONE",13,10,0
