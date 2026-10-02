; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

; err_undef.asm - an undefined label: both assemblers must refuse the source (tests/asm/run.py)
        ORG 3000H
        LDAI nothere
