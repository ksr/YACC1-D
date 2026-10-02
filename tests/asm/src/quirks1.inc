; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

; quirks1.inc - INCLUDEd by quirks.asm (one level), includes quirks2.inc (two levels)
inc1v:  EQU 21H
        LDAI 1
        INCLUDE quirks2.inc
        LDAI 3
