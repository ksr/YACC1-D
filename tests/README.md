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
  the host C compiler through `host_shim.h`. 15/15 on 2026-09-22 (switch.c also compiled with `--no-brur` as switchnb.c); `make cc-test`.
  22 programs since 2026-09-24 (the recursion tests `rfact rmutual rlocals rcalc`, errors `recurse rmain adjstr`). Beside it:
  `corpus.py` (every C program the tree compiles, with its options), `diffcheck.py` (an old y1cc.py from git against the
  working one over the corpus: identical assembly), `twin.py` (y1cc.py against its C twin `software/compiler/c/y1cc`, also
  `--16`; `--chain`/`--chain16` against the multi-pass compiler `y1ccp`, cc1..cc9), `twinfuzz.py` (random subset programs and
  60 invalid ones through both compilers; `--chain` too), `passes.py` (each pass of the multi-pass compiler against the Y1/OS
  program area: image, tables, measured stack; the corpus through the passes with their Y1/OS table sizes). Since
  2026-09-24 `run.py`, `twin.py`, `twinfuzz.py`, `passes.py` and `../ucemu/run.py` take `--xisa` (every compile with
  y1cc's `--xisa`: the LDZ/STZ page, ADDIW, SHL16), `xisa.c` (`// y1cc: --xisa`) is the 23rd program, and `diffcheck.py`
  proves the default output unchanged.
- `os/` — Y1/OS: `run.py` builds `os/disk.img`, boots it on both emulators with the console script `basic.session`
  after the monitor's `O` command, and diffs the transcripts (`basic.int.out`, `basic.uc.out`; the latter shows the
  monitor's input echo). `make os-test`. `XISA=1 python3 tests/os/run.py` (2026-09-24) runs the same sessions with
  every `/BIN` program built by y1cc `--xisa` (`make -C os XISA=1`); the program sizes `ls`/`load` print are masked.
- `asm/` — the native assembler `/BIN/ASM` (2026-09-25): `run.py` builds `os/commands/asm.c` for the Mac against an
  emulation of the Y1/OS syscalls (`host_asm.c`, `host_sys.c`: int = unsigned short, unsigned char) and compares it with
  the host assembler RC/asm on every source in the tree (the y1cc corpus plain and `--xisa`, the firmware, the
  hand-written tests, `y1os.asm`, and `src/`: `quirks.asm` with two INCLUDE levels, six sources both must refuse), as
  Intel hex and as program files: 297 sources, 0 different. `run.py --target` (`target.py`, `target.session`, the
  transcripts `target.int.out`/`target.uc.out`) runs `asm` under Y1/OS on both emulators - y1cc programs assembled
  and run, the ROM monitor, `isa.asm`, compiler pass cc4 - and compares every file it wrote with RC/asm's output.
  `make asm-test`; both in `make check`.
- `ucemu/` — the same programs (and `assembler/brur`) on the MICROCODE-level emulator `software/ucemu` with the monitor ROM
  loaded (`run.py`, 14/14 on 2026-09-22, `chars.ucout` = the expectation with the monitor's input echo), and `isa.asm`, a
  differential test of every instruction whose port-2 byte stream must be identical on both emulators (it is, BRDEV aside;
  since 2026-09-24 it covers LDZ/STZ/ADDIW/SHL16 too, 114 bytes, and `tests/bench` runs it on the machine).
- Hardware findings of 2026-09 (memory-card block map, EPROM identity, video-card write-through) are in the card READMEs.
