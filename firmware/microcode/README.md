# firmware/microcode

- `ucode-generator2/` — the C generator (Dec 2020): 64 steps x 8 bytes per opcode. `main.c` walks the opcode table
  (`software/opcodes.h`) and `accumulator.c / branch.c / io.c / memory.c / register.c` emit the control-line
  patterns named in `../yaccsignaldefine.h` + `../yaccsignaldata2.h` (which control line is which bit of which byte).
  Outputs: `test.123` (binary, 256 x 64 x 8 = 131072 bytes) and `test.hex` (the text image). `make` builds it, `make check` regenerates into `build/` and diffs against the committed `test.hex` (identical),
  `make regen` rewrites the images in place. The program writes its outputs beside its own executable (2026-09-20), so a
  Finder double-click regenerates them here. Includes resolve through the symlink `firmware/opcodes.h` (`tools/layout_links.py`).
- `test.hexz` — byte-identical to `test.hex`; it is the file the Processing loader
  (`embedded/sequencer-card/microcode-loader/`) reads, so both names are kept. `cache` — the loader's record of what it
  last sent to the sequencer card (= `test.hex` without the final `!` sentinel): **the card holds this image**.
  `cache.old` (identical) dropped 2026-09-20.
- **2026-09-22: `test.hex`/`test.hexz`/`test.123` regenerated with `BRUR Rn` at $AD** (PC ← Rn, 2 bytes, `branch.c`) and
  the H-1 (PUSHR, $07) and H-2 (BRZ/BRNZ/BR16Z/BR16NZ, $A1/$A2/$AB/$AC) release fixes from `docs/isa/MICROCODE-REVIEW-NOTES.md`:
  six records differ from the 2026-09-21 image. Loaded into the card's EEPROM the same evening with `tools/ucode_send.py --all`
  (every record, Ken's choice), so `cache` == `test.hex`. Bench checks to come: `tests/assembler/brur/` (`ABC0123`) and
  `tests/ucemu/isa.asm`.
- The v1 generator, its 32-step format and its signal table `yaccsignaldata.h` are in
  `archive/superseded-revisions/ucode-generator-v1/` (moved 2026-09-20); `software/disassembler/disasm2` decodes the v2 image.
- **2026-09-23 (evening): `aluOp()` clears SHIFT-OUT before every add/subtract** (the carry fix found with
  `tests/bench/diag/div.c` on the machine; `docs/cards/alu.md`). Records $B0 $B1 $B8 $B9 $E2 $E3 change (+2 steps each).
  **Loaded 2026-09-23 evening** (`--all`); boot check: RAM == EEPROM, 320 dumped lines == test.hex
  (`tests/sequencer/boot-run-mode-2026-09-23-carryfix.log`).
- **2026-09-24: `LDZ`/`STZ`/`ADDIW`/`SHL16`** in the 32 opcodes that had no microcode (OUTVR $80-$8F, LDTVR $C0-$C7,
  STTVR $C8-$CF, never generated): `register.c` (LDZ/STZ: the operand address built in IR from R6's high byte and the
  offset byte, then LDR's and STR's own second halves, now shared functions - $E8-$F7 unchanged) and
  `accumulator.c` (ADDIW/SHL16 from the MVRLA/ADD/MVARL/MVRHA/ADDC/MVARH steps, TMP1 holding ADDIW's high byte).
  `test.hex`/`test.hexz`/`test.123` regenerated: exactly records $80-$8F and $C0-$CF differ from the image the card
  holds (`cache`, untouched). Checked on `software/ucemu` (`tests/ucemu/isa.asm`, 0 bus fights, the same bytes as the
  instruction-level emulator). **Reload the EEPROM** (`tools/ucode_send.py --all`) and run `tests/bench` on the machine.
