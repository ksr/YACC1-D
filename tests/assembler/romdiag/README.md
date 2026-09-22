# romdiag — instruction check in ROM, paced by the input switch (2026-09-22)

Written the evening the sequencer EEPROM was reloaded (BRUR + the H-1/H-2 fixes), when `../romcount/` mirrored the
switches correctly on the machine but its count phase lit every LED: the count loop depends on `MVRHA`, `MVRLA`, `DECR`,
`BRNZ` and `ADDI`, and this ROM shows the result of each as a steady value, advancing one stage per flip of the input
switch (each stage waits for the line to change state). Burn `romdiag.bin` (8K, program at offset $1000, rest $FF),
reset, then flip the input switch once per stage and read the LED board / TIL311s:

| Stage | Instructions | LEDs | If wrong |
|---|---|---|---|
| 0 | mirror the switches (as romcount) until the line goes high | the switches | the switch read / LED path |
| 1 | `LDAI 0AAH` → show | **AA** | the LED path from an immediate, or `JSR`/`RET` (the stack at $0EFF) |
| 2 | `MVIW R7,2011H` / `MVRHA R7` | **20** | `MVRHA` (11 = it gave the low byte) |
| 3 | `MVRLA R7` | **11** | `MVRLA` |
| 4 | `MVIW R7,0400H` / `DECR R7` / `MVRHA R7` | **03** | `DECR` (R7 should be $03FF) |
| 5 | `LDAI 0` / `BRNZ` → F0, else 01 | **01** | F0 = `BRNZ` taken on zero |
| 6 | `LDAI 5` / `BRNZ` → 02, else F1 | **02** | F1 = `BRNZ` not taken on non-zero (romcount's delay would exit at once) |
| 7 | `LDAI 0FEH` / `ADDI 1` | **FF** | `ADDI` |
| 8 | one delay loop of $2000 turns, then `LDAI 055H` | **55** after ~590,000 clocks | stays at 02: the loop never exits (`DECR`/`MVRHA`/`BRNZ` together) |
| 9 | count from 00 with the delay, forever | 00 01 02 … | runs away = the romcount symptom without a stage-5..8 failure |

The ON/OFF LED lights when stage 0 ends. Stage 1 also proves `JSR`/`RET` (the `show` routine), which need working RAM
at the stack ($0EFF down). Sequence: `romdiag.asm` → `romdiag.img` (assembler) → `romdiag.bin` (`tools/img2bin.py
... --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`).

On the microcode emulator (`-I N` flips the input line every N steps, `-L` reports the LED writes) the stages read
25 ON AA 20 11 03 01 02 FF 55 00 01 02 03 with 0 bus fights (`run.py`).
