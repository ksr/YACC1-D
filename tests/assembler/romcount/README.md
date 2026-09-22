# romcount — a ROM-resident program to prove the EPROM tool chain (2026-09-22)

Burn `romcount.bin` into the 28C64 instead of the monitor, reset the machine, and the CPU runs it straight from $F000:

1. While the I/O card's **input-switch line is low**, the LED board and the TIL311 displays follow the eight switches.
   The ON/OFF LED is off. Change the switches and the displays follow.
2. **Flip the input switch high**: the ON/OFF LED lights and the machine counts up from the switch value on the LEDs
   and the TIL311s, wrapping $FF → $00. Reset to go again (the input switch back low first).

`romcount.asm` is 41 bytes at $F000 (`software/assembler`, `asm romcount -d=yacc1` with `yacc1.def` and a `-h`
`rcasm.rc` beside it). `romcount.img` is its Intel-hex output; `romcount.bin` the 8,192-byte 28C64 image (offset 0 =
$E000, the program at offset $1000, everything else $FF) built with
`python3 tools/img2bin.py romcount.img romcount.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`.

## The bytes

```
F000  A0 F0 03     BR  begin          the first fetch under FORCE-ROM; the target's A15 releases the remap
F003  19 0E FF     MVIW R1,0EFFH
F006  02           OFF
F007  70 01        OUTI P0,SWITCHLED  mirror: select the switch/LED board
F009  91           INP  P1            ACC = the switches
F00A  61           OUTA P1            LEDs = ACC
F00B  70 80        OUTI P0,TIL311
F00D  61           OUTA P1            TIL311 = ACC
F00E  A4 F0 07     BRINL mirror       input line low: keep mirroring
F011  01           ON
F012  36           MVARL R6           count = the switches
F013  26           MVRLA R6           count: ACC = count
F014  70 01 61     OUTI P0,SWITCHLED / OUTA P1
F017  70 80 61     OUTI P0,TIL311 / OUTA P1
F01A  1F 20 00     MVIW R7,2000H      the DELAY word is at F01B-F01C
F01D  5F           DECR R7            delay: 3 instructions per turn
F01E  2F           MVRHA R7
F01F  A2 F0 1D     BRNZ delay         until the high byte of R7 is zero
F022  26           MVRLA R6
F023  B0 01        ADDI 1
F025  36           MVARL R6
F026  A0 F0 13     BR count
```

**The delay** is the two bytes at ROM offset $101B–$101C ($F01B–$F01C), big-endian. $2000 = 8,192 turns × 3
instructions ≈ 590,000 clocks per count (the microcode emulator's figure): about 0.6 s per count at 1 MHz. Patch them in
the programmer's buffer for a faster or slower count; with the function generator at a few Hz make it $0010 (16 turns,
about 50 instructions per count).

## On the microcode emulator

`software/ucemu/y1ucemu` gained `-i 0|1` (the level of the input-switch line that BRINH/BRINL test) and `-L` (report LED
board, TIL311 and ON/OFF writes on stderr as they change), so `run.py` checks the program without hardware:

```
y1ucemu -x -f romcount.img -s 0x25 -i 0 -L -l 20000        # LED=25 TIL=25, no ON, stays in the mirror loop
y1ucemu -x -f romcount.img -s 0x25 -i 1 -L -l 1500000      # LED=25 TIL=25 ON LED=26 TIL=26 LED=27 ... (0 bus fights)
y1ucemu -x -f romcount.img -s 0xFD -i 1 -L -l 1200000      # ... FE FF 00: wraps
```

Neither emulator can flip the line during a run, so the toggle itself is a bench check.

## What a failure tells you

- Nothing on the LEDs after reset: the ROM is not being read at $F000 (FORCE-ROM, chip select, the socket) or the
  first bytes are wrong: read the chip back and look at offset $1000.
- Switches mirrored but the count never starts: the input-switch line (BRINL's condition) is not reaching the
  condition mux, or the switch rests high (then it counts at once and the mirror phase is skipped).
- Counts but skips or repeats values: `ADDI`, `MVARL`/`MVRLA` or the LED latch; compare with the emulator's sequence.
- The ON LED never lights: the OUT-ON control line.
