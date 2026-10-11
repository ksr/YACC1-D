; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
;
; estrobe.asm - video card bring-up (2026-10-10): an endless loop of 6845 accesses for the scope (stop it with reset).
; Each pass: R14 selected ($0E to $D800), $2A written to $D802, read back from $D802, one display-RAM write and read
; ($D000), then a short pause, so the scope can trigger on -CS (IC17 pin 25) and see, for every access:
;   E (IC17 pin 23 = IC1 pin 3): a clean pulse while -MEM-RD/-MEM-WR is low, at least 450 ns (280 ns for faster
;     grades); review finding 6.1: C1 (IC1 pin 2, N$4) has no charging path - if it sits below ~1.5 V, E never comes
;   RS (IC17 pin 24): low for $D800, high for $D802 (after the RS-to-A1 fix; stays low = the fix is not in)
;   R/-W (IC17 pin 22) = -MEM-WR; the data on D0-D7
; The display-RAM access shows the RAM half is quiet on the CRTC lines (-CS stays high).
; Load: tools/monload.py --go 3000 estrobe.img. No R2. Hex as numbers.
;
VCRTCA:     EQU 0d800h
VCRTCD:     EQU 0d802h

        ORG 3000h
loop:   LDAI 14
        STA VCRTCA
        LDAI 02ah
        STA VCRTCD
        LDA VCRTCD
        STA 0d000h
        LDA 0d000h
        MVIW R7,20
pause:  DECR R7
        MVRLA R7
        BRNZ pause
        BR loop
