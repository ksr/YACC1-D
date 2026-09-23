# YACC1 test inventory: every test in the tree, what it proves, how to run it

The complete list of tests under `tests/`, the root `make check`, the verification tools under `tools/`, and the emulator
modes they rely on. For each: what it proves, how to run it, what a pass looks like, and whether it needs hardware.

Written 2026-09-23 from the YACC1-D tree.

Sources: `Makefile` (root), `tests/README.md` and the READMEs under `tests/*/`, the docstrings of every `run.py` and of
`tools/verify_firmware.py`, `verify_embedded.py`, `verify_processing.py`, `audit_tree.py`, `gen_bom.py`; `software/emulator/README.md`,
`software/ucemu/README.md`, `os/README.md` and `os/Makefile`; `software/assembler/Makefile` and `firmware/microcode/ucode-generator2/Makefile`
(the two `check` targets); `tests/memory/*.log`, `tests/sequencer/*.log`, `tests/video/README.md`. The "pass looks like" columns
are from a run of every software-only test on this tree on 2026-09-23 (all passed). The bench procedures behind the hardware
tests are in `BRING-UP.md`.

**Needs hardware?** column: **no** = runs on the Mac alone; **tester** = the machine on the bench with the Bus Test Card on its
FTDI port; **card** = the sequencer-memory card's FTDI port; **burn** = a 28C64 to program and the machine to run it.

---

## 1. `make check` - the tree's own proof, in order

`make check` at the root runs, in this order (root `Makefile`):

| Step | Command | What it enforces |
|---|---|---|
| 1 | `python3 tools/audit_tree.py` | every file in the tree is explained (section 4) |
| 2 | `python3 tools/verify_firmware.py` | the ROM and microcode images reproduce from source (section 4) |
| 3 | `python3 tools/verify_embedded.py` | every Arduino sketch compiles with zero warnings (needs arduino-cli) |
| 4 | `python3 tools/verify_processing.py` | the Processing command sender builds with zero warnings (needs Processing 4) |
| 5 | `make -C software/assembler check` | monitor.img / basic.img / shipped rom re-assemble identical |
| 6 | `make -C firmware/microcode/ucode-generator2 check` | test.hex regenerates identical |
| 7 | `python3 tests/compiler/run.py` | 15 C programs on the instruction-level emulator |
| 8 | `python3 tests/ucemu/run.py` | 13 of them + brur on the microcode-level emulator |
| 9 | `python3 tests/os/run.py` | the Y1/OS session on both emulators |
| 10 | `python3 tests/sequencer/run.py` | the microcode sender against a mock card |
| 11 | `python3 tests/assembler/romcount/run.py` | the ROM counter on the microcode emulator |
| 12 | `python3 tests/assembler/romdiag/run.py` | the ROM diagnostic on the microcode emulator |

Shortcuts: `make cc-test` = steps 7+8, `make os-test` = step 9. `make` (all) first builds the C tools the tests need:
`software/emulator`, `software/ucemu`, `software/assembler`, `firmware/microcode/ucode-generator2`, `software/disassembler/disasm2`,
`software/ubasic-c/ubasic-master`, the bus-tester vector generator - after `tools/layout_links.py` has laid the include symlinks.
Steps 3 and 4 are the only ones that need tools outside the tree (arduino-cli, Processing 4); everything else is Python 3 and cc.

Generated documentation has its own checks that are **not** in `make check`: `python3 tools/gen_bom.py --check` (`docs/bom/`,
section 4) and `make isa` (`docs/isa/`, regenerate rather than check).

---

## 2. The emulators and their scripted modes

Two emulators, deliberately different (`software/ucemu/README.md`):

- **`software/emulator/emulator`** - the instruction-level reference model (`main.c`): knows what every opcode does, 64K, 16
  ports, console on port 2. Quick and forgiving. Options used by the tests: `-x` scripted mode (no load/dump chatter, no raw
  tty, stdout flushed, `HALT` exits with `HALT at aaaa after N instructions, R3=xxxx` on stderr), `-f FILE` load an Intel-hex
  image (the assembler's `.img`), `-m` load the monitor+BASIC ROM (`firmware/basic/basic.img` + `firmware/monitor/monitor.img`,
  found relative to the executable), `-c disk.img` a CompactFlash image on ports P8/P9 (`MACHINE.md`). Since 2026-09-22 `BRVR`
  and `JSRUR` do what the microcode does, so the monitor's `G` and `T` work on it. It also stops itself at an instruction limit
  (`tests/os/basic.int.out` ends with `instruction limit reached at f530 after 6000000 instructions`).
- **`software/ucemu/y1ucemu`** - the microcode-level model: does not know what any instruction does; it steps the control words
  of `firmware/microcode/ucode-generator2/test.hex` (256 x 64 x 64 bits) through a model of the cards (sequencer, register cards,
  ALU, memory with FORCE-ROM, I/O with the 16550 model), and counts **bus fights** (two drivers disagreeing on a data lane, per
  opcode and step). This is what turned the microcode review's findings into runnable tests. Options: `-x` scripted, `-m`
  monitor ROM, `-f FILE`, `-u test.hex` another control store, `-F and|src` how a fight resolves (AND = the usual TTL outcome;
  src = the ALU's `-AC-RD` loses), `-s NN` the switch byte, `-l N` stop after N steps, `-t` one line per instruction fetch,
  `-T` every step with signals, `-w` list every fight as it first occurs, `-i 0|1` the input-switch line level (`BRINH/BRINL`),
  `-I N` flip that line every N steps, `-L` report LED-board / TIL311 / ON-OFF writes on stderr, `-R 1|2` the number of
  index-register cards fitted (with 1, R4..R7 read $FF and lose loads and counts), `-c disk.img`. Its status line gives
  instructions, steps, clocks (a step is two clock periods), R3 and the fight count - e.g. `HALT at 3046 after 90 instructions,
  1187 steps, 2285 clocks, R3=0000; bus fights: 0 in 0 (opcode,step) pairs; weak pull-up drives: 162`.

Under the microcode `BRDEV` always branches, so a program's console goes through the monitor's `charout`/`uartin` and the UART
model - the path the real machine takes - and the monitor's `uartin` **echoes** every character it reads. That is why some
tests have a second expectation file (`.ucout`, `.uc.out`) for the microcode emulator.

Every test image is loaded at $3000 (the C compiler's default; BASIC's token buffer is $1000-$1FFF) and starts with a branch to
an address above $8000 (`--boot` stub) so that the FORCE-ROM remap is released exactly as on the hardware.

---

## 3. The tests under `tests/`

### 3.1 `tests/compiler/` - the C cross-compiler (no hardware)

- **Proves:** `software/compiler/y1cc.py` compiles each program correctly for the YACC1: 15 programs (`arith`, `arrays`, `calls`,
  `chars` (with stdin), `control`, `fib`, `globals`, `hello`, `io`, `sieve`, `structs`, `switch`, `switchnb` = `switch` compiled with
  `--no-brur`) plus two that must **fail** to compile (`bigconst.err` "does not fit 16 bits", `recurse.err` "recursion is not supported").
- **Run:** `python3 tests/compiler/run.py [name ...] [--oracle] [--keep]`. Per test: compile with `--boot` (stack, `JSR main`,
  `HALT`), assemble with `software/assembler/asm NAME -d=yacc1`, run `emulator -x -f NAME.img < NAME.in`, compare stdout with
  `NAME.out`. Per-test compiler flags in a `// y1cc:` comment. `--oracle` regenerates the `.out` files with the host C compiler
  through `host_shim.h` (int = unsigned short, char unsigned) for tests not marked `// no-oracle`. `--keep` leaves `build/`.
- **Pass looks like:** one line per test and `15/15 passed`, e.g. `arith PASS 2364 bytes 184720 instructions`,
  `bigconst PASS expected compile error 'does not fit 16 bits': seen`. A failure writes `build/NAME/NAME.got` and prints both.

### 3.2 `tests/ucemu/` - the same programs on the microcode (no hardware)

- **Proves:** the control store in `test.hex` executes the compiler's programs the way the instruction-level emulator says
  they should, with **zero bus fights**, through the monitor's real console path. Also runs `tests/assembler/brur`.
- **Run:** `python3 tests/ucemu/run.py [name ...] [--keep] [--ucode PATH] [--fight and|src]`. Each program is compiled with
  `--boot` and run with `-m` (monitor ROM); the expectation is `tests/compiler/NAME.out`, or `NAME.ucout` where the hardware's
  input echo makes it differ (`chars.ucout`).
- **Pass looks like:** `arith PASS 196018 instr 2577002 steps 4957987 clocks fights 0 (0 pairs)` ... `brur PASS HALT at 3046
  after 90 instructions ... bus fights: 0 ...`, then `14 passed, 0 failed`. A non-zero fight count is a failure even when the
  output matches: it means the image has a two-driver step (this is how H-1 and H-2 were reproduced on 2026-09-22).
- **`tests/ucemu/isa.asm`** - the differential ISA test: every arithmetic, logic, shift, compare, register, memory and stack
  instruction, each result written raw to port 2 with the expected value in a comment. Run on both emulators, the byte streams
  must be identical (they are, `BRDEV` aside). `run.py` does not run it by default; assemble it beside `yacc1.def` and compare
  `emulator -x -f isa.img` with `y1ucemu -x -f isa.img` by hand. It is also the byte stream to check on the **machine** through
  the UART once a RAM loader exists (BACKLOG; `BRING-UP.md` section 4).

### 3.3 `tests/os/` - Y1/OS on both emulators (no hardware)

- **Proves:** `os/` builds (`y1os.bin`, the `/BIN` programs, `disk.img` as a P8XFS v2 volume via `tools/p8xfs.py`), the monitor's
  `O` command boots it from the CF model on ports P8/P9, and a scripted shell session gives the same transcript on both emulators.
- **Run:** `python3 tests/os/run.py [--keep] [--update]` (= `make os-test`, `make -C os test`). Sessions are `tests/os/*.session`
  (one console line per line, sent after `O`); expectations `NAME.int.out` (instruction-level) and `NAME.uc.out` (microcode, with
  the input echo). The comparison starts at `BOOT FROM CF` and ends after the OS says `bye` and the prompt returns. `--update`
  rewrites the expectations from the run - only after reading them by eye.
- **Pass looks like:** `basic int PASS instruction limit reached at f530 after 6000000 instructions, R3=22a7` and
  `basic uc PASS HALT at F529 after 5023647 instructions, 80000000 steps, ...`, `2 passed, 0 failed`. The session exercises
  `dir`, `cat`, `cd`, `pwd`, `hello a b c` (implicit `/BIN` lookup with arguments), `run /BIN/ECHO hi there`, `wc 45 1` (raw sectors
  through the BIOS vectors), an unknown command, `load`, `help`, `exit`.
- The CF card hardware does not exist yet (`os/README.md`), so this is emulator-only by nature.

### 3.4 `tests/sequencer/` - the microcode sender, without the card (no hardware)

- **Proves:** `tools/ucode_send.py` speaks the Sequencer4 download protocol correctly: (1) a differential send - a cache that
  differs from `test.hex` in four records plus one never sent makes exactly those five reach the card with the right bytes, and
  the cache ends equal to `test.hex`; (2) `--all` sends all 256; (3) `--boot-check`'s dump comparison, applied to the recorded
  2026-09-21 Sequencer4 transcript, finds exactly the pre-fix `$07` (PUSHR) lines differing and nothing else.
- **Run:** `python3 tests/sequencer/run.py`. `mock_card.py OUTFILE` is a fake Sequencer4 in download mode on a pseudo-terminal
  (prints its slave path, then `>>` prompts, takes `%` cc ii + 512 hex byte values per instruction, `!` ends; writes what it
  received as 256 lines).
- **Pass looks like:** `PASS differential send: 5 records` / `PASS --all send: 256 records` / `PASS boot-check: 320 dumped lines
  compared, only the pre-fix $07 (PUSHR) lines differ (20)` / `0 failed`.
- **The logs** (`boot-run-mode-*.log`) are bench captures, not tests: the clobbered copy with `-BUS-EN` asserted, the clean copy,
  the Sequencer4 boot, and the boot after the 2026-09-22 reload. `BRING-UP.md` section 8 explains how to read them; a fresh
  capture is `tools/ucode_send.py --boot-check --log FILE` (**card**).

### 3.5 `tests/assembler/` - the assembler-level programs

| Item | Proves | Run | Pass | Hardware |
|---|---|---|---|---|
| `romcount/run.py` | `romcount.asm` assembles to the committed `romcount.img`, `img2bin` gives the committed 8K `romcount.bin`, and on the microcode emulator it mirrors the switches with the input line low (`-s 0x25 -i 0 -L`), counts from the switch value with it high, and wraps FF -> 00 (`-s 0xFD`), 0 bus fights | `python3 tests/assembler/romcount/run.py` | `PASS romcount.img == assembled` / `PASS romcount.bin == img2bin of the image (8192 bytes)` / `PASS input low: mirrors the switches, no ON` / `PASS input high: counts from the switches` / `PASS wraps FF -> 00` / `0 failed` | no (emulator); **burn** for the real thing - it ran overnight 2026-09-22/23 on the machine (`MACHINE.md`) |
| `romdiag/run.py` | `romdiag.asm`/`.img`/`.bin` match, and the twelve stages read `25 ON AA 20 11 03 01 02 FF 33 20 55 00 01 02` with two register cards (`-R 2`, `-I 100000` flipping the input line every 100,000 steps) and `... 33 FF 55 ...` with one (`-R 1`) | `python3 tests/assembler/romdiag/run.py` | `PASS stages, 2 register cards: 25 ON AA 20 11 03 01 02 FF 33 20 55 00 01 02` / `PASS stages, 1 register card: ... 33 FF 55 ...` / `0 failed` | no; **burn** on the bench (its first run found the missing register card 1, 2026-09-22) |
| `brur/brur.asm` | `BRUR Rn` ($AD, added 2026-09-22): a plain `BRUR R5`, a jump through a table-fetched address, a four-way dispatch; prints `ABC0123` then HALT (89 instructions) | assemble beside `yacc1.def` with a `-h` `rcasm.rc`, then `emulator -x -f brur.img`; also run by `tests/ucemu/run.py` | `ABC0123`; on the microcode emulator `HALT at 3046 after 90 instructions ... bus fights: 0` | no; **not yet on the machine** (needs a RAM loader) |
| `ledcount/` | the 10-byte switch-ROM LED counter for the Mem Switch card; `ledcount.prg` is the assembled output | set the DIP switches per its README table, clock the machine | LEDs count 00..FF at one count per four instructions | **hardware only** (the 2026-09-21 first-run program) |
| `yacc1test.asm` + `history-2020/` | the 2020 CPU test program and its 15 dated snapshots (serial out, ROM, RAM, push/pop, ring shift, "major test"); `test_output.txt` is a 2026-05-26 assembler run | assemble; run on the emulator or the machine | a record of how bring-up progressed rather than a pass/fail test | either |

### 3.6 `tests/memory/` - the memory card through the bus tester (**tester**)

| Script | Proves | Time | Result on record |
|---|---|---|---|
| `memory_status.py [port]` | boot remap after `-RESET` (ROM at $0000 until an A15-high access), every ROM byte against `basic.img`+`monitor.img` (`tools/romimage.py`), 8 low-RAM spots, every 4K block $8000-$FFFF classified RAM / ROM / VIDEO / undecoded against the jumper table in `MACHINE.md` | ~1 min | 2026-09-18: the fitted map ($8000-$CFFF RAM, $D000 undecoded/video, $E000-$FFFF ROM) |
| `rom_verify.py [port] [--save]` | the 28C64 holds exactly the tree's ROM image; `--save` keeps the read-back as `rom-readback-<date>.bin` | ~30 s (blocks-1 firmware) | the monitor half **differs** until the 2026 image is burned - expected (`firmware/rom/README.md`) |
| `memory_full_test.py [port] [--log F]` | A ROM; B address lines (unique byte at $0000 and at every 1<<n, read after all writes: an open or shorted address line shows in seconds); C RAM $0000-$7FFF and $8000-$CFFF address-derived pattern written in one sweep, verified in a second (retention); D the inverted pattern; E video RAM (both patterns, neighbour isolation, the block-0/9 write-through checks, read stability); F ROM again and nothing answers at $D800-$DFFF | ~20 min with blocks-1 (~10 h per byte) | `full-run-2026-09-21.log`: **14/14 PASS**, 53,248 cells x 2 patterns, 0 bad, in 0.3 h |

The four logs beside them tell the day's story: `attempt1-linkdrop` (the USB port vanished mid-sweep, which is why `busdrv.py`
now reopens and resends), `attempt2-stopped-for-reflash` (stopped by Ken after 157 min to flash the blocks-1 firmware),
`blocks-13of14` (first blocks-1 run; F2 failed because the test expected the $D800 block to echo the bus and the card, with no
CRTC, gives `00 FF` instead - the test was corrected), then the clean 14/14.

### 3.7 `tests/video/` - the video card's display RAM (**tester**)

- `video_ram_test.py [port] [--quick]`: five tests over $D000-$D3FF (address-derived pattern, inverted, one-cell neighbour
  isolation for address-line shorts, the 2026-09-18 write-through check - writes to $0010 / $9010 / $0011 / $1010 must not reach
  $D010 - and read stability with memory-card traffic in between, because $D000 is undecoded on the memory card and a floating bus
  can fake a good read). `--quick` = first 64 cells (~1 min), full ~14 min. **8/8 PASS** on 2026-09-21 after the +5V/VCC join,
  and again with RN2 back at 10k; before the join the write-through fault reproduced every time.
- `hold_address.py HEXADDR [--rd]`: not a test - holds an address on the bus (with `-VMA`, optionally `-MEM-RD`) for a meter or
  scope on the card's decode pins; Enter releases. The port must stay open (the tester resets when it closes).
- `tools/alias_min.py`: the minimal reproduction of the write-through fault (write $0010; `$D010` must keep 11, fault = 22).

### 3.8 `tests/bus-tester-scripts/` - the 2020 `CMD:OPERAND#` scripts (**tester**)

Not pass/fail tests but the scripts that brought each card up in 2020, sent by `embedded/command-sender/command_sender_8`
(or line by line with `tools/busdrv.py --raw`): `Memory Card Tests/` (low/high RAM and EPROM fill-and-dump, `dump-eprom.txt`),
`ALU/*.new` (add, and, or, sub, branch, zero test, in the 2020 signal names), `IO/` (`basic-out`, `serialin`, `serialout`),
`Index Register/commands-1 copy.txt` (372 lines), `Gen Test Vectors/` (a C generator for the **2016** register card - stale signal
names, template only), `ramtest.logicsettings` (Saleae capture set-up). Format and the script language (LET/FOR/NEXT/labels/
expected values) are in `BRING-UP.md` section 7.3. Always `-BUS-EN:1#` and `-VMA:1#` before driving memory.

### 3.9 `tests/basic/` - `test`

A short program using `LET`, `FOR ... NEXT`, `:loop`, `DUMPVARS`, `DUMPLABELS`. Its README (2026-09-20) says the interpreter had
not been identified and that it is not uBASIC. Every one of those keywords is in the bus-driver script language of
`docs/procedures/BUS Driver Commands - Google Docs.pdf` (`LET VARIABLE=VALUE`, `FOR VARIABLE=Initial,Final,Increment`, `NEXT`,
`:Label`, `DUMPVARS`, `DUMPLABELS`), so it is a test of the **command sender's script interpreter**, not of any BASIC: send it
with `command_sender_8` and the variable dumps should show the loop variables. Nothing to run on an emulator. (`tests/basic/README.md`
is not among this document's files and is left as it is.)

---

## 4. The verification tools under `tools/`

| Tool | Enforces | Needs | Pass |
|---|---|---|---|
| `verify_firmware.py` | the images in the machine reproduce from source: builds `software/assembler`, assembles `firmware/monitor/monitor.asm` and `firmware/basic/basic.asm` with `yacc1.def` in a scratch dir, compares `monitor.img` / `basic.img`, runs `makerom` and compares `firmware/rom/shipped/rom`; builds the microcode generator and compares `test.hex`. Never writes into the tree | cc | `monitor.img IDENTICAL` / `basic.img IDENTICAL` / `rom (shipped = image to burn) IDENTICAL` / `microcode test.hex IDENTICAL` / `FIRMWARE VERIFIED` |
| `make -C software/assembler check` | the same for the ROM, plus the listings (`basic.lst: differs (listing only)` is informational) | cc | `basic.img: IDENTICAL ...` / `rom: IDENTICAL to firmware/rom/shipped/rom (the image to burn)` |
| `make -C firmware/microcode/ucode-generator2 check` | `test.hex` regenerates identical (fails on any difference - the guard that the committed image is what the generator says) | cc | `test.hex: IDENTICAL to the committed microcode image` |
| `verify_embedded.py` | every Arduino sketch under `embedded/` compiles for `arduino:avr:uno` against **only** the vendored `embedded/libraries` (a private user-libraries dir keeps `~/Documents/Arduino/libraries` out), with `--warnings all`; expected outcomes in `EXPECT` (the MCP23X17 work-in-progress is expected to fail); sketch folders whose name differs from the `.ino` are copied under the right name first | arduino-cli | `12 sketches, 0 unexpected results -> EMBEDDED VERIFIED` (2026-09-20) |
| `verify_processing.py` | `embedded/command-sender/command_sender_8` builds with the Processing 4 command-line builder and the generated Java re-compiles with Processing's Eclipse compiler with warnings on, cosmetic categories excluded | Processing 4 in /Applications | zero warnings (2026-09-20) |
| `audit_tree.py` | every file in the tree is explained: a migration-plan row (hash re-checked against `migration/dryrun-plan.tsv`), an extra source from the run logs, a hand-made file (the `HAND_MADE` prefixes: tools/, migration/, front-page docs, `docs/cards/`, `docs/programming/`, `docs/procedures/`, ...), or a generated file (FABRICATED markers, KiCad conversions, PDFs, `docs/isa/`, `docs/bom/` (`tools/gen_bom.py`), ...). Prints the buckets, hash mismatches, unexplained files and plan rows missing from disk; git-ignored build products are excluded | git | `unexplained files: 0 []` and `plan rows missing from disk: 0 []`; exit 0. On 2026-09-23 it reports one hash mismatch, `firmware/microcode/ucode-generator2/cache` - the loader's record of what the card holds, rewritten by `ucode_send.py --all` on 2026-09-22 after the plan was made, so the mismatch is expected until the plan row is refreshed |
| `gen_bom.py --check` | `docs/bom/` matches what the active schematics say (regenerates into a temp dir and diffs, ignoring the generation-date line) | Python | `docs/bom: UP TO DATE (13 files, date line ignored)` |
| `gen_fabricated.py`, `gen_provenance.py`, `compare_eagle.py`, `eagle_to_kicad_all.py`, `brd_to_pdf.py`, `sch_to_pdf.py`, `ucode_wavedrom.py` | generators for `hardware/FABRICATED.md`, `PROVENANCE.md`, `NEWER-DESIGNS-vs-ACTIVE.txt`, the KiCad conversions, the board/schematic PDFs and `docs/isa/` - regenerate and diff by hand (`git diff`) rather than a `--check` | various | |
| `ucode_review.py` | the mechanical microcode review (rule R2 "two drivers" count went from 37 to 3 with the H-1/H-2 fixes, `software/ucemu/README.md`) | Python | a report, not pass/fail |

---

## 5. Hardware tests, summarised (what the machine has proven so far)

| Date | Test | Result | Where |
|---|---|---|---|
| 2026-09-18 | memory card map, boot remap, ROM capture | jumper map as designed; chip = the 2021 sources | `tests/memory/memory_status.py`, `firmware/rom/eprom-captured-2026-09-18.*` |
| 2026-09-18 | video write-through fault | reproduced | `tools/alias_min.py` |
| 2026-09-21 | full memory test | 14/14, 53,248 cells x 2, 0 bad | `tests/memory/full-run-2026-09-21.log` |
| 2026-09-21 | video RAM after the +5V/VCC join | 8/8 quick and full | `tests/video/README.md` |
| 2026-09-21 | sequencer boot, bus quiet, then Sequencer4 | RAM == EEPROM == test.hex, READY 54 s | `tests/sequencer/*.log` |
| 2026-09-21 | switch-ROM `ledcount` on the CPU (ALU + one register card, function-generator clock) | executes as expected | `MACHINE.md` |
| 2026-09-22 | microcode reload (BRUR, H-1, H-2), boot-check | all 256 sent, boot dumps == test.hex | `tests/sequencer/boot-run-mode-2026-09-22-reload.log` |
| 2026-09-22 | `romcount` first build, then `romdiag` | found register card 1 missing (stage 2/9 = FF); card fitted | `tests/assembler/romcount/README.md`, `romdiag/README.md` |
| 2026-09-22/23 | `romcount` (R3/TMP build) overnight from ROM | counting without a fault | `MACHINE.md` |

Still owed on the bench (BACKLOG, `MACHINE.md`): burn the 2026 ROM and re-verify; `brur` and `isa.asm` on the machine (need a RAM
loader); the H-5 scope check on bus C3; the 6845 register-select fix on the video card.
