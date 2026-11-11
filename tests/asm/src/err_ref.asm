; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

; err_ref.asm - names of 30 and of 40 characters as operands (a label is 29 at most; tests/asm/run.py, 2026-11-11):
; a label that is not there. Until that day RC/asm died on them with status 133 and no message.
        ORG 3000H
abcdefghijabcdefghijabcdefghi: HALT
        BR abcdefghijabcdefghijabcdefghij
        MVIW R3,abcdefghijabcdefghijabcdefghijklmnopqrst
