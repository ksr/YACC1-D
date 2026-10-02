; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

; err_dup.asm - a label defined twice
        ORG 3000H
here:   LDAI 1
here:   LDAI 2
