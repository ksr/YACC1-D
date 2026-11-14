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
  `cf_test.py`: the memory card v2.0's CF section through P8/P9 (reset, registers, 8-bit mode, IDENTIFY, sector 0;
  `--quick` seconds, the whole ~10 min; `--hold` holds a status read for the meter). 2026-11-03: ALL PASS, a TDK 125 MB card.
- `sequencer/` — run-mode boot transcripts of the sequencer-memory ATmega (2026-09-21): the clobbered copy with -BUS-EN
  asserted, the clean copy with the bus quiet, and the Sequencer4 boot (16 s copy, 29 s verify, RAM == EEPROM).
- `video/` — `video_ram_test.py`, the video card's display-RAM test over the bus tester (patterns, inverse, neighbour
  isolation, the block-0/9 write-through check, read stability); 8/8 on 2026-09-21 after the +5V/VCC join. `gate.py`
  (2026-10-11, in `make check`): the card at gate level (`y1ucemu -G`) against the behavioural model, byte for byte
  with 0 bus events, and without each bench rework (the RS fix, the +5V wire) the faults they fixed. `v20/run.py`
  (2026-11-10, branch `video-v2`, in `make check`): the video card V2.0's model (`Y1VID_CARD=v2.0`) - `model_test.c`
  on its own (the PS/2 keyboard from the console, the controller's timing, VSYNC / DE to the clock) and `v20card.asm`
  through the monitor on both emulators in four builds of the card (as designed, text-only, DOTS open, a 2 MHz CPU):
  the status port, the 6845 on PA/PB, the 16 plane/page pairs of the window, VSYNC's pulse and frame, DE, the keys;
  `tools/vidsim.py render` on its state file. `v30/run.py` (2026-11-11, in `make check`): the video card V3's model
  (`Y1VID_CARD=v3`) - the font EPROM's image against its generator, `model_test.c` (the HD63484's registers, FIFOs
  and commands with the manual's examples, the keyboard and the mouse), and `v30card.asm` through the monitor on both
  emulators: a YACC1 program starts the chip, writes "V3 OK" from the font EPROM and draws; the frame buffer is
  compared dot for dot with the same scene drawn in Python. `v40/run.py` (2026-11-14, in `make check`): the video
  card V4 (`Y1VID_CARD=v4`) and its ROM - both ROMs built from the one `monitor.asm` and compared with the committed
  images, `model_test.c` (the ports, both control registers, the 64K behind the window, VSYNC / DE at 16 dots a
  count), `v40card.asm` through the V4 monitor on both emulators in three builds (as designed, text-only, a 3.5 MHz
  CPU), and `v40scr.asm`, the ROM's screen driver: 80 x 25, lower case, six scrolls, the cursor's address and CURH.
  `v30_netsim.py` (2026-11-11, in `make check`): the video card V3's netlist
  (`hardware/cards/video/kicad/v3.0/v30_netlist.py`) run as a circuit, every part a model with its data-sheet
  delays at both ends of their ranges, against a model of the HD63484's memory cycles and against the microcode's
  I/O records: interleaved and superimposed access, the ports, set-up and hold, runt pulses on clocks, bus fights.
  It is the card's timing check; `docs/cards/video-v3.md` section 10d.
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
  monitor's input echo). `make os-test`. `NOXISA=1 python3 tests/os/run.py` runs the same sessions with every
  `/bin` program built by y1cc `--no-xisa` (`make -C os NOXISA=1`; `--xisa` is the default since 2026-10-04); the
  program sizes `ls`/`load` print are masked.
- `ucemu/hold.py` — the hold-step pass of the microcode generator removed only what the hardware does not need
  (2026-11-06, `docs/system/MICROCODE.md` 5.8), judged with its own copy of the rules against the `-DKEEPHOLD` image.
- `native/` — the toolchain under Y1/OS: `run.py` (native compile), `selfhost.py`, `srcmake.py`, `mkdisk.py` (the system
  rebuilt onto a new disk), `profile.py` (where one program's instructions go), `clocks.py` (2026-11-05: the fast
  emulator's clocks against the microcode, `docs/system/SPEED.md`), and `errors.py` (2026-11-05: `/bin/cc`'s error
  messages against y1cc.py's, the one path where a pass reads a second file).
- `asm/` — the native assemblers `/bin/asmc` (asm.c, 2026-09-25) and `/bin/asm` (asm.asm, in YACC1 assembly, 2026-09-26;
  `run.py` also runs it under Y1/OS on the instruction-level emulator on the whole corpus and compares its messages
  and files with asm.c's, `--uc` 27 sources on the microcode emulator too): `run.py` builds `os/commands/asm.c` for the Mac against an
  emulation of the Y1/OS syscalls (`host_asm.c`, `host_sys.c`: int = unsigned short, unsigned char) and compares it with
  the host assembler RC/asm on every source in the tree (the y1cc corpus plain and `--xisa`, the firmware, the
  hand-written tests, `y1os.asm`, and `src/`: `quirks.asm` with two INCLUDE levels, `longline.asm` with lines of
  100 to 254 characters, nine sources both must refuse), as Intel hex and as program files: 357 sources, 0
  different (2026-11-11). Before the corpus RC/asm is put at its own limits - a line of 254 characters and one of
  255, names of 30 and 40 characters as operands, a label of 30, the cross-reference of a 29-character label: the
  exit status and the message of each (all but the label ended it on a signal with no message until 2026-11-11);
  a source RC/asm dies on is a failure, never one "refused by both". `run.py --target` (`target.py`, `target.session`, the
  transcripts `target.int.out`/`target.uc.out`) runs `asm` under Y1/OS on both emulators - y1cc programs assembled
  and run, the ROM monitor, `isa.asm`, compiler pass cc4 - and compares every file it wrote with RC/asm's output.
  `make asm-test`; both in `make check`.
- `ybasic/` — BASIC in assembly against BASIC in C (2026-11-11): `run.py` runs each session (`expr`, `prog`, `files`, `limits`)
  on a copy of the disk, whose `/bin/basic` is `os/commands-asm/basic.asm`, and on a copy with the C BASIC
  (`os/commands/basic.c`, `/bin/basicc`) in its place: the console transcripts must be the same byte for byte and so must the files left behind.
  Then `tests/os/ybasic.session` with the C BASIC against the OS tests' expected transcripts on both emulators,
  and both interpreters counted in instructions on a loop (the assembly one must need under a quarter). `--uc` runs
  the sessions on the microcode emulator too. (`tests/basic/` is the ROM's uBASIC, not this.)
- `disasm/` — `/bin/disasm` (os/commands/disasm.c, 2026-09-29): `run.py` builds it for the Mac (`host_disasm.c`,
  `host_sys.c`: int = unsigned short, OPEN/GETC/CLOSE/ENTRY/SEEK and peek emulated) and round-trips - `disasm -s`,
  RC/asm, the same bytes, the listing true to them - over tests/asm's corpus, every program of the OS build, the ROM
  from memory, random bytes and every opcode + operand byte (382, ~20 s), then START/COUNT ranges and the errors;
  `tools/gen_y1_distab.py --check` first. The run on Y1/OS is `tests/os/disasm.session`. `make disasm-test`; in
  `make check`.
- `ucemu/` — the same programs (and `assembler/brur`) on the MICROCODE-level emulator `software/ucemu` with the monitor ROM
  loaded (`run.py`, 14/14 on 2026-09-22, `chars.ucout` = the expectation with the monitor's input echo), and `isa.asm`, a
  differential test of every instruction whose port-2 byte stream must be identical on both emulators (it is, BRDEV aside;
  since 2026-09-24 it covers LDZ/STZ/ADDIW/SHL16 too, 114 bytes, and `tests/bench` runs it on the machine).
- `y1dbg/` — the debugger (2026-10-11): `y1ucemu -D`'s debug server and `software/y1dbg` driven by script - a breakpoint
  at the monitor's `cmdloop`, the registers, stepping, the disassembly and trace, the monitor's video driver on the
  screen (`V I`, `V M1`) and poked inverse glyphs, BASIC typed through `key`, a run paused and stopped by a write
  watch, reset, the `-c` command line, the emulator's exit when the debugger closes or drops the connection - and
  the curses UI in a pty (its screen pane captured with `snap`). In `make check`.
- `y1term/` — `tools/y1term.py --send` against the microcode emulator through a pty (2026-10-08): `good.bas` (lower
  case, a tab, a blank line, a `#` comment, FOR/NEXT) sent with `--new --run` must print `Hello 1 2 3 21`; `bad.bas`
  must exit 1 naming its `print !` line as SYNTAX ERROR, the other lines stored. In `make check`.
- `kermit/` — `/bin/kermit` (2026-09-26): `run.py` boots Y1/OS on both emulators with the console on a pseudo-terminal
  and runs `tools/y1kermit.py` against `kermit -r`, `-s` and `-x`: text, all 256 byte values, a 70K file, long runs, an
  empty file, a name to clean; block checks 1-2, 8th-bit prefixing, text mode, `-n`, `-a`; damaged, missing and
  unanswered packets both ways, three Ctrl-Cs; the server's SEND/GET/FINISH. Files compared on the host and on the
  disk image (`p8xfs.py get`, fsck); the throughput from the instruction-level emulator's PC histogram; `--calib`
  checks `os/kermit_io.asm`'s timing on the microcode emulator (a timeout second = 1,000,176 clocks, 217 clocks a
  received character, with the 2026-09-29 microcode). In `make check` (~2.5 minutes).
- Hardware findings of 2026-09 (memory-card block map, EPROM identity, video-card write-through) are in the card READMEs.
