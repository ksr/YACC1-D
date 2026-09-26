; err_stale.asm - a stale token record (tests/asm/run.py, 2026-09-26): RC/asm's token list keeps the records past
; its count from the expression before, and a later (x).0 reads them: after the bad expression on line 7, record 5
; is an operator, so lines 8 and 9 are bad expressions too in RC/asm (and in both native assemblers: asm.asm's fast path
; for (label).0 must fall back to the general algorithm here).
        ORG 3000H
x:      DB 0
        LDAI ((1&3+1&6-3!3&2)*1)&0
        LDAI (x).0
        LDAI (x).1
