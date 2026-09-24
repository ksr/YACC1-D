# The YACC1 tool chain, end to end

From a source file to a running program: assemble or compile, run on the emulators, burn a ROM or build a CF image,
load microcode into the sequencer, and run the proofs. Written 2026-09-23 from the YACC1-D tree.

Sources: `Makefile` (root), `software/README.md`, `software/assembler/Makefile`, `firmware/microcode/README.md` and
`ucode-generator2/Makefile`, `firmware/rom/README.md`, `tools/img2bin.py`, `tools/p8xfs.py`, `tools/ucode_send.py`,
`tools/verify_firmware.py`, `tools/audit_tree.py`, `tools/patched_files.txt`, `tools/romimage.py`, `tools/layout_links.py`
(named in `software/README.md`), `tests/README.md`, `tests/*/run.py`, `tests/memory/*.py` and `tests/video/README.md`
(docstrings), `tests/sequencer/run.py`, `os/Makefile`, `docs/system/MACHINE.md`, `BACKLOG.md`.

## 1. The pieces

| Step | Tool | Input → output |
|---|---|---|
| compile C | `software/compiler/y1cc.py` (Python) | `prog.c` → `prog.asm` |
| assemble | `software/assembler/asm` (C, RC/asm) | `prog.asm` (+ `yacc1.def`, `rcasm.rc`) → `prog.img` (Intel hex) + listing |
| run | `software/emulator/emulator`, `software/ucemu/y1ucemu` | `.img` (+ ROM images, CF image) |
| flatten | `tools/img2bin.py` | `.img` → `.bin` (ROM chip image or a P8XFS payload) |
| disk image | `tools/p8xfs.py` | `.bin` files → `disk.img` (P8XFS v2) |
| microcode | `firmware/microcode/ucode-generator2/ucodegen` (C) | `opcodes.h` + `*.c` → `test.hex` / `test.hexz` / `test.123` |
| load microcode | `tools/ucode_send.py` (pyserial) | `test.hex` → the sequencer card's EEPROM |
| ROM | `firmware/rom/makerom` (two shell lines) | `basic.img` + `monitor.img` → `rom` → `rom.bin` |

`make` at the root builds every C tool (`software/emulator`, `software/ucemu`, `software/assembler`,
`firmware/microcode/ucode-generator2`, `software/disassembler/disasm2`, `software/ubasic-c`, the test-vector
generator) after `tools/layout_links.py` creates the three symlinks the old include paths need
(`firmware/opcodes.h`, `software/disassembler/yaccsignaldefine.h`, `software/disassembler/ucode-Generator2`).
Each tool's Makefile includes `mk/sdk.mk`, which falls back to an older macOS SDK when the default no longer links
(2026-09-22, macOS 27 / Xcode 17). All six binaries find their inputs relative to the executable, so a Finder
double-click works.

## 2. Source → image → emulator

```
python3 software/compiler/y1cc.py prog.c -o prog.asm --boot      # or write prog.asm by hand
cp software/assembler/yacc1.def . && echo -h > rcasm.rc
software/assembler/asm prog -d=yacc1 > prog.lst                    # -> prog.img ; check "0 Errors"
software/emulator/emulator -x -f prog.img                          # interpreter
software/ucemu/y1ucemu -x -m -f prog.img                           # microcode emulator (ROM loaded for the console)
```

Details: [ASSEMBLER.md](ASSEMBLER.md) (the invocation gotcha: source name before `-d=`), [C-COMPILER.md](C-COMPILER.md),
[EMULATORS.md](EMULATORS.md). For a program to run under the monitor, omit `--boot`, assemble at `$3000`, and type
`G3000` at the prompt (`emulator -m -f prog.img`).

## 3. Image → ROM (28C64 on the memory card)

1. The image must live in `$E000–$FFFF`: the monitor + BASIC (`firmware/rom/shipped/rom`, produced by `makerom`:
   `awk` drops `basic.img`'s end record, `cat` appends `monitor.img`), or a stand-alone program at `ORG 0F000H`
   whose first instruction branches to an A15-high address (`tests/assembler/romcount`).
2. Flatten to the chip's 8,192 bytes, offset 0 = `$E000`, unwritten bytes `$FF` like a blank part:

   ```
   python3 tools/img2bin.py firmware/rom/shipped/rom firmware/rom/shipped/rom.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192
   python3 tools/img2bin.py romcount.img romcount.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192
   ```

   `img2bin.py in.img out.bin [--base A] [--end A] [--fill B] [--size N]`: `--base` the first address of the output
   (default the lowest in the file), `--end` stop before this address (default `$F000`, so a compiler `--boot` stub is
   left out — hence the explicit `--end 0x10000` for a ROM), `--fill` the byte for holes (default 0), `--size` pad or
   truncate to a whole chip.
3. Or, without burning anything, send a RAM program to a running machine: `python3 tools/monload.py prog.img --go 3000`
   through the monitor's `:` loader (`docs/programming/MONITOR.md`, `docs/procedures/BRING-UP.md` section 6a).
3. Burn with Visual Minipro / `minipro`, device 28C64 (`firmware/rom/README.md`). A program lands at offset `$1000`
   of the chip when assembled at `$F000`.
4. Tell builds apart: the power-up banner ends `ROM 2026-09-23` on the current build; otherwise `rom.bin`'s MD5
   (d2d7b027e7c6951d7dd93412a8fd9cd8, `firmware/rom/README.md`) or the two check bytes in `docs/procedures/BRING-UP.md` section 5. The chip in the machine holds this build,
   burned 2026-09-23 (`MACHINE.md`); before that it held the 2021 build (`eprom-captured-2026-09-18.bin/.hex`).
5. After burning: `tests/memory/rom_verify.py` (~30 s, through the bus tester) compares every byte with
   `tools/romimage.py`'s image of `basic.img` + `monitor.img`; `memory_status.py` (~1 min) also checks the boot remap
   and the block map. Against a chip still holding the 2021 build both report the monitor half as different.

## 4. Image → CF disk image (Y1/OS)

```
python3 tools/img2bin.py prog.img prog.bin --base 0x5000                      # a /BIN program compiled --org 0x5000
python3 tools/p8xfs.py create disk.img --sectors 2048
python3 tools/p8xfs.py boot   disk.img os/build/y1os.bin                      # LBA 1.., OSCNT in the boot block
python3 tools/p8xfs.py mkdir  disk.img /BIN
python3 tools/p8xfs.py put    disk.img prog.bin --name /BIN/PROG --load 0x5000 --exec 0x5000
python3 tools/p8xfs.py tree   disk.img
software/ucemu/y1ucemu -m -c disk.img          # then O at the monitor prompt
```

`make -C os` does all of it for `os/y1os.c`, `os/commands/*.c` and `os/disk/*`; `make -C os run` / `run-int` boot it;
`make -C os test` replays the sessions. Format and shell: [OS.md](OS.md). The CF hardware is not built (planned on the memory
card, `docs/cards/cf.md`); the emulators model it (`software/cfmodel.h`). Writing the image to a real CF card:
`tools/cfcard.py`, `docs/procedures/CF-CARD.md` (not yet tried on a real card); the burned ROM's `O` then boots it.

## 5. Microcode: generate, verify, load

- **Generate**: `make -C firmware/microcode/ucode-generator2` builds `ucodegen`; `make check` regenerates into
  `build/` and diffs against the committed `test.hex` (identical); `make regen` rewrites `test.hex`, `test.hexz`
  (the same bytes, the Processing loader's name) and `test.123` (binary, 131,072 bytes) in place. The generator
  walks `software/opcodes.h` and the `*.c` files emit the control-line patterns named in
  `firmware/microcode/yaccsignaldata2.h` (`firmware/microcode/README.md`). `docs/isa/` (`make isa`,
  `tools/ucode_wavedrom.py --all`) regenerates the per-opcode step listings and diagrams from `test.hex`.
- **Verify on the emulator before loading**: `python3 tests/ucemu/run.py` (the compiler suite + `brur` on the new
  image, 0 bus fights expected), `y1ucemu -x -m -f prog.img -w` for the fight list; `tools/ucode_review.py`
  produces the mechanical review (`docs/isa/MICROCODE-REVIEW.md`).
- **Load** (`tools/ucode_send.py`, replaces the Processing sketch; protocol of `embedded/sequencer-card/sequencer4/
  download.ino`): on the card set `UCODESWITCH` to DOWNLOAD, reset the card (LOADING on), press `STARTSWITCH`; then

  ```
  python3 tools/ucode_send.py [--port /dev/cu.usbserial-XXXX] [--all] [--dry-run] [--delay MS] [--settle MS]
  ```

  The card prompts `>>` before every instruction; the sender waits `--settle` (default 250 ms — the card flashes a
  LED for 100 ms after the prompt and its serial buffer is 64 bytes; at 1 ms/char without the settle the head of the
  record was lost, 2026-09-22) and sends `%` cc ii + 1024 hex digits (the trailing `-` of `test.hex` is not sent),
  `!` at the end. Only records that differ from `firmware/microcode/ucode-generator2/cache` (what the card holds) go
  out unless `--all`; the cache is updated record by record, so an interrupted load resumes by re-running. 115200
  baud; `--delay` default 2 ms per character. Ken loaded the 2026-09-22 image with `--all` (`firmware/microcode/README.md`).
  Bench order (2026-09-22, settled): UCODESWITCH to DOWNLOAD, **run the tool first**, then press START. Opening the FTDI
  port resets the ATmega through DTR (the standard Arduino auto-reset, C19 on the card), so a START pressed before the
  tool opens the port is undone and has to be pressed again.
- **Boot check**: set `UCODESWITCH` back to run, reset: Sequencer4 copies the EEPROM to the microcode RAM and verifies
  it (copy 16 s, verify 29 s, READY at ~54 s). `python3 tools/ucode_send.py --boot-check [--log FILE]` captures that
  transcript until `READY!!!`, requires `RAM == EEPROM for all 256 instructions`, and compares the five instructions
  the firmware dumps (`Ins=N` / `LINE:nn` blocks) with `test.hex`. `tests/sequencer/*.log` are the recorded boots.
- **Without hardware**: `python3 tests/sequencer/run.py` exercises `ucode_send.py` against `mock_card.py` (a fake card
  on a pty): a differential send, an `--all` send, and the `--boot-check` comparison on the 2026-09-21 transcript.

## 6. The proofs: `make check` at the root

In order (`Makefile`):

| Step | What it proves | Needs hardware |
|---|---|---|
| `tools/audit_tree.py` | every file in the tree is explained (section 7) | no |
| `tools/verify_firmware.py` | the assembler, both firmware images, `rom` and `test.hex` rebuild byte-identical from source in a scratch directory (`FIRMWARE VERIFIED`) | no |
| `tools/verify_embedded.py` | the Arduino sketches compile against the vendored libraries | no (arduino-cli) |
| `tools/verify_processing.py` | the Processing command sender builds | no (Processing 4) |
| `make -C software/assembler check` | `monitor.img`, `basic.img`, `rom` identical to the committed ones | no |
| `make -C firmware/microcode/ucode-generator2 check` | regenerated `test.hex` identical | no |
| `tests/compiler/run.py` | the C test programs on the interpreter (15/15) | no |
| `tests/ucemu/run.py` | the same on the microcode emulator with the ROM, 0 bus fights, plus `brur` (14/14) | no |
| `tests/os/run.py` | the Y1/OS session on both emulators against the transcripts | no |
| `tests/sequencer/run.py` | `ucode_send.py` against the mock card | no |
| `tests/assembler/romcount/run.py` | the ROM counter: assembly, `.bin`, and its LED sequence on ucemu | no |
| `tests/assembler/romdiag/run.py` | the twelve-stage ROM diagnostic on ucemu with 2 and 1 register cards | no |

`make cc-test` = the two compiler runners; `make os-test` = the OS sessions; `make bom` regenerates `docs/bom/`
from the Eagle schematics (`tools/gen_bom.py`, added 2026-09-23); `make isa` the `docs/isa/` diagrams.

Note (2026-09-23): the OS and compiler sources were being edited while this was written (Y1/OS v0.1 with a file
API and syscalls, `y1cc` `sys()`/`funcaddr()`, the monitor's sixteenth vector); `tests/os/*.out` and
`tools/patched_files.txt` had not yet been updated for them, so `make check` may fail on those steps until they are.

Bench-only tests (through the Bus Test Card, FTDI 19200, `tools/busdrv.py`; the CPU's sequencer-logic card must be
unplugged or the bus tester fights its outputs — `BACKLOG.md` "CPU off switch"): `tests/memory/rom_verify.py`,
`memory_status.py`, `memory_full_test.py` (~16 min: ROM, address lines, two full RAM patterns over $0000–$CFFF, the
video RAM); `tests/video/video_ram_test.py [--quick]` (8/8 on 2026-09-21). Their logs sit beside them.

## 7. `tools/audit_tree.py` and `tools/patched_files.txt`

The tree was migrated from the old YACCS folders (`MIGRATION.md`), and `audit_tree.py` enforces that **every file is
accounted for**: a migration-plan row whose MD5 is re-checked (`migration/dryrun-plan.tsv`), an extra source from a
migration run log, a hand-made file in a known place (the `HAND_MADE` prefixes: `tests/assembler/{ledcount,brur,
romcount,romdiag}/`, `software/compiler/`, `software/ucemu/`, `os/`, `tests/os/`, `docs/programming/`, `docs/cards/`,
`docs/DOC-PLAN.md` …), a generated file (KiCad conversions, PDFs, `docs/isa/`, `rom.bin`, FABRICATED markers,
Markdown twins of `.rtf`), or a git-ignored build product. It prints the buckets and exits 1 on any hash mismatch,
unexplained file, or plan row missing from disk.

`tools/patched_files.txt` is the list of **migrated files that were deliberately edited** in this tree, one path per
line with a tab and the reason: the audit accepts a differing hash for them, `migrate_purge.py` never reverts them,
`migrate_run.py` never overwrites them. It is also the change log of the toolchain: the emulator's `-x`/`-c`/`-l`
and the BRVR/JSRUR/BRUR semantics, the assembler's `DS` fix and `P8=8`, the monitor's `G` fix, CF driver and `O`
command, the generator's BRUR and H-1/H-2 fixes, the regenerated `test.hex`, the compiler-warning cleanups of the
sketches. **Any further edit to a migrated file needs a line there, or `make check` fails at the first step.**

## 8. What is not automated yet (`BACKLOG.md`)

- Loading a program into RAM on the machine: the monitor has no hex loader; `tools/monload.py` through the `E`
  command is planned (protocol: `E` + address, two hex digits per byte, `-` to end, then `G` + address); the bus
  tester cannot load RAM while the sequencer-logic card is fitted.
- Burning the rebuilt ROM and re-capturing it.
- Bench checks of the reloaded microcode: `tests/assembler/brur` (`ABC0123`), `tests/ucemu/isa.asm`'s byte stream,
  then the monitor from ROM (`romcount` has run overnight; `romdiag` found the missing register card).
- The Python replacement of the Processing command sender for the bus-tester scripts.
