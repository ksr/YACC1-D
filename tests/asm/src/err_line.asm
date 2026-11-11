; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

; err_line.asm - a line of 255 characters (254 is the limit; tests/asm/run.py, 2026-11-11). RC/asm stops at it with
; `ERR - Line longer than 254 characters`; until then it assembled the first 254 as one line and the rest as the
; next, as /bin/asm does: there the 255th character is a line of its own, an invalid instruction.
        ORG 3000H
        DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,013H,014H,015H,016H,017H,018H,019H,01AH,01BH,01CH,01DH,01EH,01FH,020H,021H,022H,023H,024H,025H,026H,027H,028H,029H,02AH,02BH,02CH,02DH,02EH,02FH,030H,0007
        HALT
