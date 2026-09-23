# YACC1 memory map

The definitive address map of the machine as built, what the ROM, BASIC, the compiler and the OS use, what is
reserved, and what the OS plan assigns. Written 2026-09-23 from the YACC1-D tree.

Sources: `docs/system/MACHINE.md` (the memory card's jumper settings, verified with the bus tester 2026-09-18),
`hardware/cards/memory/README.md` (decode and FORCE-ROM), `firmware/monitor/monitor.asm` and `monitor.lst`
(equates and addresses), `firmware/basic/basic.asm` (BASIC's areas), `firmware/abi/README.md`, `os/lib_abi.c`,
`os/README.md`, `docs/system/OS-PLAN.md` (map A/B), `software/compiler/y1cc.py` (`ORG_DEFAULT`, `STACK_TOP`),
`tests/assembler/romcount/README.md`, `software/emulator/main.c`, `software/ucemu/README.md`, `BACKLOG.md`.

## 1. The hardware decode (memory card v1.3)

- **$0000–$7FFF**: the low 62256 SRAM, always RAM.
- **$8000–$FFFF**: decoded per 4K block by IC7 (74LS138) into a 3×8 jumper header: jumper *up* = the high 62256
  (RAM), *down* = the 28C64 (ROM), *none* = undecoded. Fitted: $8000–$CFFF → RAM (5 jumpers up), **$D000–$DFFF → no
  jumper** (reserved for the video card), $E000–$FFFF → ROM (2 jumpers down) (`MACHINE.md`).
- **Reading an undecoded block returns the last value left on the bus** — it looks like RAM that echoes the last write
  (`MACHINE.md`; `tests/memory/memory_status.py` classifies blocks that way).
- **FORCE-ROM boot remap**: after `-RESET` the ROM appears at every address until the first bus cycle with ADDR15
  high. Record $00 fetches from $0000 and gets ROM[$F000]; the monitor's `BR eprom` ($F003) ends the remap. Every
  ROM-resident program's first instruction must be such a branch (`tests/assembler/romcount`, the compiler's `--boot`
  stub). Design-review MED: the remap flip-flop is clocked by `ADDR15·-VMA·-BUS-EN` and is masked today by asserting
  `-VMA` in every microcode step (`BACKLOG.md`).
- **The 28C64's `-WE` is the raw `-MEM-WR`** (`BACKLOG.md` MED): any store into $E000–$FFFF can program the EEPROM
  (and during FORCE-ROM any store at all). The interpreter exits on a write above $DFFF; ucemu ignores writes above
  $E000.
- The TMP0/TMP1 registers live on the memory card but are not memory-mapped (`MICROCODE-REVIEW-NOTES.md` 1.3).
- The video card v1.0 in the machine answers at $D000–$D3FF (1K tested, `tests/video/README.md`; 2K by design,
  `OS-PLAN.md`); the 6845 is not fitted and its register select is wrong as drawn (`MACHINE.md` known fault 1).

## 2. The map as used today

| Range | Size | What | Owner / source |
|---|---|---|---|
| $0000–$00FF | 256 | page zero: nothing in the tree uses it (the switch-ROM programs of bring-up lived at $0000–$000F, `tests/assembler/ledcount`) | free |
| $0100–$01FF | 256 | `BASIC_VARS`: BASIC's 26 one-byte variables, 256-byte aligned | `basic.asm` |
| $0200–$02FF | 256 | BASIC internal state: `bas_run_ended` $0200, text/token pointers $0202–$0216, FOR-NEXT stack $0280–, GOSUB stack $02C0– | `basic.asm` |
| $0300–$03FF | 256 | `parse_input_line`: BASIC's input line | `basic.asm` |
| $0400–$04FF | 256 | `parse_token_buffer`: BASIC's tokenised line under construction — **and**, while Y1/OS runs, the first of its handle buffers (below) | `basic.asm` |
| $0500–$0BFF | 1,792 | while Y1/OS runs: `HBUFS` $0400–$0BFF, the four file handles' 512-byte buffers (2026-09-23, out of the OS's 16K to make room for redirection and pipes); otherwise not assigned. The stack must not grow below $0C00 (no check) | `os/y1os.c` |
| $0C00–$0EFF | 768 | the stack: R1 = $0EFF at reset, grows down, $0C00 the informal floor | `monitor.asm` `STACK`, `firmware/abi/README.md` |
| $0F00–$0F04 | | `monmode` $0F00, `continue_addr` $0F02, `interupt_cnt` $0F04 | `monitor.asm` |
| $0F06–$0F0B | 6 | `SYSARG0..2`: Y1/OS syscall argument words (big-endian) | `os/lib_abi.c`, `y1cc.py` (2026-09-23) |
| $0F0C–$0F0D | 2 | `SYSRES`: the syscall result word | idem |
| $0F10–$0F12 | 3 | `CFLBA0..2`: the sector number for CFREAD/CFWRITE (low byte first) | `monitor.asm` (2026-09-22) |
| $0F14–$0F3F | 44 | `SYSTAB`: the OS's syscall jump table, 22 big-endian words, filled at boot; all 22 used since 2026-09-23 | `os/lib_abi.c`, `os/y1os.c` |
| $0F40–$0FBF | 128 | `ARGBUF`: a program's command tail from Y1/OS, NUL-terminated (`ARGMAX` 127); `argstr()`. The monitor's equate says 64 bytes; the upper 64 overlay `line_buffer` | `monitor.asm`, `os/lib_abi.c`, `y1cc.py` |
| $0F80–$0FFF | 128 | `line_buffer`: the monitor's line buffer (`P` command), idle while the OS runs | `monitor.asm` |
| $1000–$1FFF | 4K | BASIC's token buffer (`bas_tok_buf_start`..`_end` = $2000), cleared by `basic_cold` at every monitor boot — **and** `OSBASE`: where the `O` command loads Y1/OS. The two are never used together | `basic.asm`, `monitor.asm` |
| $1000–$4FFF | 16K | Y1/OS image and data when the OS is running (LBA 1–32 reserve; v0 was 5.1K; 2026-09-23 with redirection and pipes: a 14,673-byte image = 29 sectors + 1,424 bytes of data = 16,097 of 16,384, the Makefile checks it) | `os/README.md`, `os/y1os.c` |
| $2000 | | scratch of the removed monitor T-menu tests (nothing now) | `y1cc.py` comment |
| $3000 | | default `ORG` of a compiled program run from the monitor (`G3000`) | `y1cc.py` `ORG_DEFAULT` |
| $5000–$CFFF | 32K | Y1/OS transient program area (`TPA`..`TPATOP`); `/BIN` programs are compiled `--org 0x5000` | `os/lib_abi.c` |
| $8000–$CFFF | 20K | the high 62256 (jumpers up) — the upper part of the TPA | `MACHINE.md` |
| $D000–$D7FF | 2K | video card display RAM (1K verified on the built card) | `OS-PLAN.md`, `tests/video` |
| $D800–$DFFF | 2K | undecoded, unused | `MACHINE.md` |
| $E000–$EFFF | 4K | ROM: BASIC (entry table $E000..$E060 at 16-byte spacing; `ORG 0EF00h` and `0EFFFh` at its end) | `basic.asm`, `monitor.asm` equates |
| $F000–$F7FF | | ROM: the monitor (code through `nblink` at $F5DC, strings from `hello` and `PROMPT` $F60A, the help text `helpmenu` $F6AC into $F7xx; 2,979 bytes in all as of 2026-09-23) | `monitor.lst` |
| $F800–$FF8F | | ROM, unwritten ($FF in `rom.bin`) | `firmware/rom/README.md` |
| $FF90 | | the interrupt service routine `isrcode` | `monitor.asm` `org 0ff90h` |
| $FFC0–$FFFF | 64 | the 16 BIOS vectors, 4 bytes each (15 until 2026-09-23; the 2021 chip has 11, then `00 FF FF …`) | `monitor.asm` `org 0ffc0h`, `eprom-captured-2026-09-18.hex` |

The monitor's own routines are not at fixed addresses across builds; the vectors are ([MONITOR.md](MONITOR.md)).

## 3. Reserved and free, in one view

- **Do not touch** from a program: $0F00–$0FFF (monitor and OS variables, the syscall block), the stack region below
  $0EFF, $E000–$FFFF (EEPROM write hazard).
- **Free for a program run from the monitor** (no OS): $0500–$0BFF with care (stack), $2000–$CFFF ($1000–$1FFF only
  if BASIC will not be used afterwards — the monitor clears it at boot, which is why the compiler defaults to $3000).
- **Under Y1/OS**: programs own $5000–$CFFF only; $1000–$4FFF is the OS.
- **$D000–$DFFF**: never RAM on the machine as jumpered (reads echo the bus); the emulators treat it as RAM, so a
  program that works on an emulator with data there fails on the machine. **To verify:** whether the built video
  card responds to writes in $D400–$D7FF (only $D000–$D3FF was tested, `tests/video/README.md`).

## 4. What the OS plan assigns (`docs/system/OS-PLAN.md` decision 4)

| Range | A: video stays at $D000 (today, no card change) | B: video moved to $E000 |
|---|---|---|
| $0000–$0FFF | system page: monitor/BIOS variables, sector buffer, stack $0EFF down | same |
| $1000–$4FFF | OS, loaded from CF (16K reserve = LBA 1–32) | same |
| $5000–$CFFF | transient program area, 32K | $5000–$DFFF, 36K ($D000 jumper up = RAM) |
| $D000–$D7FF | video (2K); $D800–$DFFF unused | RAM |
| $E000–$EFFF | ROM, spare 4K once BASIC leaves (free for later, blank in the image) | video (2K used) |
| $F000–$FFFF | ROM: monitor + CF driver + boot loader, vectors $FFC0 | same |

Start with A (nothing to change on the cards); B is a jumper move later. The OS's TPA top is one constant
(`TPATOP`). BASIC leaves the ROM and returns as `/bin/basic` (plan decision 5, phase 3); until then `$E000–$EFFF`
is BASIC and `$1000–$1FFF` doubles as its buffer.

## 5. The emulators' view

- Interpreter (`software/emulator/main.c`): 64K flat, zero at start; the ROM images are loaded at $E000/$F000; any
  write above $DFFF prints `Rom Write` and exits; no FORCE-ROM (it starts at PC = $F000).
- ucemu (`software/ucemu`): RAM filled with $FF at start; writes above $E000 ignored; FORCE-ROM modelled (address
  bits 12–15 forced high until an A15-high address is presented with `-VMA`); no video card.
- Both: the CF card is on I/O ports, not in the memory map ([IO-PORTS.md](IO-PORTS.md)).

## 6. Open items touching the map (`BACKLOG.md`)

- The memory card's unconnected jumper wire on IC7 pin 4 (purpose not remembered).
- The FORCE-ROM race and the raw `-WE` (design-review MED items).
- Whether the OS load address stays $1000 if the OS grows past 16K.
