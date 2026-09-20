# firmware/microcode

- `ucode-generator2/` — the C generator (Dec 2020): 64 steps x 8 bytes per opcode. `main.c` walks the opcode table
  (`software/opcodes.h`) and `accumulator.c / branch.c / io.c / memory.c / register.c` emit the control-line
  patterns named in `../yaccsignaldefine.h` + `../yaccsignaldata2.h` (which control line is which bit of which byte).
  Outputs: `test.123` (binary, 256 x 64 x 8 = 131072 bytes) and `test.hex` (the text image). Builds unchanged with
  clang and regenerates `test.hex` byte-identical (`tools/verify_firmware.py`). Includes resolve through the symlink
  `firmware/opcodes.h` (`tools/layout_links.py`).
- `test.hexz` — byte-identical to `test.hex`; it is the file the Processing loader
  (`embedded/sequencer-card/microcode-loader/`) reads, so both names are kept. `cache` — the loader's record of what it
  last sent to the sequencer card (= `test.hex` without the final `!` sentinel): **the card holds this image**.
  `cache.old` (identical) dropped 2026-09-20.
- The v1 generator, its 32-step format and its signal table `yaccsignaldata.h` are in
  `archive/superseded-revisions/ucode-generator-v1/` (moved 2026-09-20); `software/disassembler/disasm2` decodes the v2 image.
