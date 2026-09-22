# romdiag — instruction check in ROM, paced by the input switch (2026-09-22)

Written the evening the sequencer EEPROM was reloaded (BRUR + the H-1/H-2 fixes), when `../romcount/` mirrored the
switches correctly on the machine but its count phase lit every LED. **Its first run found the cause:** stage 2 read FF
where 20 was expected, because the bring-up machine had **one index-register card** (R0..R3 on card 0; R4..R7 live on
card 1, `hardware/cards/register`), and the first romcount kept its count in R6 and its delay in R7: a read of an absent
register leaves the bus to its pull-ups ($FF), so the count showed FF and the delay loop never ended. `y1ucemu -R 1`
models that now and reproduces the symptom (`25 ON FF`).

This build uses R3 and TMP, so it runs on one card, and stage 9 probes R7 so the LEDs say whether card 1 is fitted.
Burn `romdiag.bin` (8K, program at offset $1000, rest $FF), reset with the input switch low, then flip the switch once
per stage (each stage waits for the line to change state) and read the LED board / TIL311s:

| Stage | Instructions | LEDs | If wrong |
|---|---|---|---|
| 0 | mirror the switches (as romcount) until the line goes high | the switches | the switch read / LED path |
| 1 | `LDAI 0AAH` → show | **AA** | the LED path from an immediate, or `JSR`/`RET` (the stack at $0EFF) |
| 2 | `MVIW R3,2011H` / `MVRHA R3` | **20** | `MVRHA` (11 = it gave the low byte; FF = no register responded) |
| 3 | `MVRLA R3` | **11** | `MVRLA` |
| 4 | `MVIW R3,0400H` / `DECR R3` / `MVRHA R3` | **03** | `DECR` (R3 should be $03FF) |
| 5 | `LDAI 0` / `BRNZ` → F0, else 01 | **01** | F0 = `BRNZ` taken on zero |
| 6 | `LDAI 5` / `BRNZ` → 02, else F1 | **02** | F1 = `BRNZ` not taken on non-zero |
| 7 | `LDAI 0FEH` / `ADDI 1` | **FF** | `ADDI` |
| 8 | `LDAI 033H` / `MVAT` / `LDAI 0` / `MVTA` | **33** | TMP round trip |
| 9 | `MVIW R7,2011H` / `MVRHA R7` | **20** with two register cards | **FF = register card 1 (R4..R7) is not fitted** |
| 10 | one delay loop of $2000 turns (R3), then `LDAI 055H` | **55** after ~590,000 clocks | stays at 20/FF: the loop never exits |
| 11 | count from 00 in TMP with the delay, forever | 00 01 02 … | runs away or freezes: see stages 4-8 |

The ON/OFF LED lights when stage 0 ends. Sequence: `romdiag.asm` → `romdiag.img` (assembler) → `romdiag.bin`
(`tools/img2bin.py ... --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`).

On the microcode emulator (`-I N` flips the input line every N steps, `-L` reports the LED writes, `-R 1` = one register
card) the stages read `25 ON AA 20 11 03 01 02 FF 33 20 55 00 01 02` with two cards and `... 33 FF 55 ...` with one,
0 bus fights (`run.py`).
