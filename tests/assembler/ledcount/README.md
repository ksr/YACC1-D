# ledcount — 16-byte switch-ROM program: count on the IO card's LEDs

`ledcount.asm` assembles to 10 bytes at $0000 (`software/assembler`: `asm ledcount -d=yacc1` with `yacc1.def` beside the
source; output `ledcount.prg`). It uses the monitor's LED idiom: `OUTI P0,SWITCHLED` selects the switch/LED board, then
`OUTA P1` puts the accumulator on the LEDs. The loop adds one and branches back, so the LEDs count 00, 01, 02 ... FF, 00
at one count per 4 instructions; with the function-generator clock at a few Hz each step is visible.

```
        LDAI 0                  ; count = 0
loop:   OUTI P0,SWITCHLED       ; select the LED board   (SWITCHLED = 1)
        OUTA P1                 ; LEDs = count
        ADDI 1                  ; count += 1
        BR loop                 ; forever (absolute address $0002)
```

Hex: `0E 00 70 01 61 B0 01 A0 00 02`, then $000A-$000F unused (leave 00).

Mem Switch card settings (one row of 8 switches per byte, bit 7 first):

| Address | Byte | Switches 7..0 | Instruction |
|---|---|---|---|
| $0000 | 0E | 00001110 | LDAI 0 |
| $0001 | 00 | 00000000 |  |
| $0002 | 70 | 01110000 | OUTI P0,001H |
| $0003 | 01 | 00000001 |  |
| $0004 | 61 | 01100001 | OUTA P1 |
| $0005 | B0 | 10110000 | ADDI 1 |
| $0006 | 01 | 00000001 |  |
| $0007 | A0 | 10100000 | BR 0002H |
| $0008 | 00 | 00000000 |  |
| $0009 | 02 | 00000010 |  |
| $000A-$000F | 00 | 00000000 | (unused) |

Encoding notes (from `yacc1.def`): OUTI = 70 | port, then the byte; OUTA = 60 | port; ADDI = B0, byte; BR = A0, address
high, address low. LDAI 0 could be dropped (the accumulator would start wherever it was) to save 2 bytes.
