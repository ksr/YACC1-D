# tests

- `bus-tester-scripts/` — `CMD:OPERAND#` scripts for the Bus Test Card (sent by `embedded/command-sender/` or
  `tools/busdrv.py`): `ALU/*.new` (2020 signal names), `IO/`, `Index Register/`, `Memory Card Tests/`,
  `Gen Test Vectors/` (C program that generates vector scripts), `ramtest.logicsettings` (Saleae Logic capture setup).
  `deprecated/gen1-2016/` = the 2016 gen-1 scripts in the OLD signal names (RESET, ALU-FUNC, RD-AC, WDATA…) plus `fix`,
  the sed converter that produced the `.new` files; `deprecated/address-register-2020-07/` = tests for the retired card.
- `assembler/` — `yacc1test.asm`, the CPU test program (2020-10-31), its 15 dated 2020 snapshots, a 2026 run log; `ledcount/`
  (the 16-byte switch-ROM LED counter); `brur/` (the BRUR $AD test, `ABC0123` on the emulator, 2026-09-22).
- `memory/` — `rom_verify.py` (~30 s): every ROM byte against the image assembled from `basic.img` + `monitor.img`;
  `memory_status.py` (~1 min): boot remap, every ROM byte against `basic.img` + `monitor.img` (what the emulator
  loads; `tools/romimage.py`), low RAM spots, and a classification of every 4K block above $8000 (RAM / ROM / video /
  undecoded). `memory_full_test.py` (~16 min with the blocks-1 bus-tester firmware): ROM, address lines, two full RAM
  patterns over $0000-$CFFF written then verified in separate sweeps, the video RAM, ROM again. Logs beside them:
  2026-09-21 all RAM cells good, ROM = sources, video RAM good.
- `sequencer/` — run-mode boot transcripts of the sequencer-memory ATmega (2026-09-21): the clobbered copy with -BUS-EN
  asserted, the clean copy with the bus quiet, and the Sequencer4 boot (16 s copy, 29 s verify, RAM == EEPROM).
- `video/` — `video_ram_test.py`, the video card's display-RAM test over the bus tester (patterns, inverse, neighbour
  isolation, the block-0/9 write-through check, read stability); 8/8 on 2026-09-21 after the +5V/VCC join.
- `basic/` — `test`, a small BASIC program (LET/FOR loops) used to exercise the interpreter.
- `compiler/` — the C compiler's test programs (`*.c` + expected `.out`/`.in`/`.err`) and `run.py`, which compiles each with
  `software/compiler/y1cc.py --boot`, assembles it and runs it on `emulator -x`; `--oracle` regenerates the expectations with
  the host C compiler through `host_shim.h`. 14/14 on 2026-09-22 (switch.c also compiled with `--no-brur` as switchnb.c); `make cc-test`.
- Hardware findings of 2026-09 (memory-card block map, EPROM identity, video-card write-through) are in the card READMEs.
