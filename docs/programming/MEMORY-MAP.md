# YACC1 memory map

The definitive address map of the machine as built, what the ROM, BASIC, the compiler and the OS use, what is
reserved, and what the OS plan assigns. Written 2026-09-23 from the YACC1-D tree; checked against the sources and
listings again 2026-10-08 (section 2a: what bounds each area, and what does not).

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
| $0100–$01FF | 256 | `BASIC_VARS`: BASIC's 26 variables A–Z, **two bytes each** at $0100 + 2 × index ($0100–$0133; the source's comment says one-byte), 256-byte aligned because `exe_set_variable`/`exe_get_variable` put the index into R2's low byte (section 2a) | `basic.asm` |
| $0200–$02FF | 256 | BASIC internal state: `bas_run_ended` $0200, text/token pointers and the line being added $0202–$0217; the FOR-NEXT stack $0282–$02BF (6 bytes a level: 10 levels) and the GOSUB stack $02C2–$02FF (2 bytes a level: 30 levels). While a program runs their pointers are **R4** (FOR) and **R5** (GOSUB), set by `exe_init`; the words `bas_forstackptr` $0280 and `bas_gosubptr` $02C0 are not used. Neither stack is checked (section 2a) | `basic.asm` |
| $0300–$03FF | 256 | `parse_input_line`: BASIC's input line (`get_inputline`; no length check) | `basic.asm` |
| $0400–$04FF | 256 | `parse_token_buffer`: BASIC's tokenised line under construction — **and**, while Y1/OS runs, the first of its handle buffers (below) | `basic.asm` |
| $0500–$0BFF | 1,792 | while Y1/OS runs: `HBUFS` $0400–$0BFF, the four file handles' 512-byte buffers (2026-09-23, out of the OS's 16K to make room for redirection and pipes); otherwise not assigned. The stack must not grow below $0C00 (no check) | `os/y1os.asm`, `os/y1os.c` |
| $0C00–$0EFF | 768 | the stack: R1 = $0EFF at reset, grows down, $0C00 the informal floor | `monitor.asm` `STACK`, `firmware/abi/README.md` |
| $0F00–$0F04 | | `monmode` $0F00, `continue_addr` $0F02, `interupt_cnt` $0F04 | `monitor.asm` |
| $0F06–$0F0B | 6 | `SYSARG0..2`: Y1/OS syscall argument words (big-endian) | `os/lib_abi.c`, `y1cc.py` (2026-09-23) |
| $0F0C–$0F0D | 2 | `SYSRES`: the syscall result word | idem |
| $0F10–$0F12 | 3 | `CFLBA0..2`: the sector number for CFREAD/CFWRITE (low byte first) | `monitor.asm` (2026-09-22) |
| $0F14–$0F3F | 44 | `SYSTAB`: the OS's syscall jump table, 22 big-endian words (entries 0..21), filled at boot from SYSTAB2 ($4FC0, 32 entries, 2026-09-25); all 22 used since 2026-09-23 | `os/lib_abi.c`, `os/y1os.asm` |
| $0F40–$0FBF | 128 | `ARGBUF`: a program's command tail from Y1/OS, NUL-terminated (`ARGMAX` 127); `argstr()`. The monitor's equate says 64 bytes; the upper 64 overlay `line_buffer` | `monitor.asm`, `os/lib_abi.c`, `y1cc.py` |
| $0F80–$0FEF | 112 | `line_buffer`: the monitor's line buffer (`P` command), idle while the OS runs (128 bytes until 2026-09-25) | `monitor.asm` |
| $0FF0–$0FF7 | 8 | the video driver's variables (ROM 2026-09-25): `VIDPRES` $0FF0, `VIDMIR` $0FF1 (the mirroring switch), `VIDCUR`, `VROW`, `VCOL`, `VCHAR`, `VLINE` $0FF6 | `monitor.asm`, `firmware/abi/README.md` |
| $1000–$1FFF | 4K | BASIC's token buffer (`bas_tok_buf_start`..`_end` = $2000; `basic_cold` writes the end token at $1000 at every monitor boot; adding a line moves the whole 4K, and a full buffer drops its end silently, section 2a) — **and** `OSBASE`: where the `O` command loads Y1/OS. The two are never used together | `basic.asm`, `monitor.asm` |
| $1000–$4FFF | 16K | Y1/OS when the OS is running (LBA 1–32 reserve). The assembly OS (v0.2, 2026-09-23, the default): image $1000–$2BE0 (7,137 bytes = 14 sectors), free $2BE1–$49FF (7,711 bytes), RAM $4A00–$4F0F cleared at boot (line $4A00, path $4A82, pipeline table $4B80, sector buffer $4C00, handle records $4E00, variables $4E50), free $4F10–$4FFF ($4FC0–$4FFF kept for a larger SYSTAB). The C OS (`make -C os OS=c`): a 14,619-byte image = 29 sectors + 1,424 bytes of data = 16,043 of 16,384 (v0 was 5.1K). The Makefile checks both | `os/README.md`, `os/y1os.asm`, `os/y1os.c` |
| $2000 | | scratch of the removed monitor T-menu tests (nothing now) | `y1cc.py` comment |
| $3000 | | default `ORG` of a compiled program run from the monitor (`G3000`) | `y1cc.py` `ORG_DEFAULT` |
| $5000–$CFFF | 32K | Y1/OS transient program area (`TPA`..`TPATOP`); `/BIN` programs are compiled `--org 0x5000` | `os/lib_abi.c` |
| $8000–$CFFF | 20K | the high 62256 (jumpers up) — the upper part of the TPA | `MACHINE.md` |
| $D000–$D7FF | 2K | video card display RAM (1K verified on the built card); the ROM's screen is 80 x 24 from $D000 (2026-09-25) | `OS-PLAN.md`, `tests/video`, `monitor.asm` |
| $D800–$DFFF | 2K | the video card's CRTC half: the 6845 at even addresses ($D800 address register, $D802 data register after the RS-to-A1 fix; not fitted), the JP1 latch at odd ones (netlist reading, `docs/cards/video.md` section 4) | `docs/cards/video.md`, `monitor.asm` `VCRTCA` |
| $E000–$EFFF | 4K | ROM: BASIC (ROM 2026-10-07, 2026-10-08 layout): the entry table $E000..$E060 at 16-byte spacing (each stub fits its slot), the code to $EF3D at its ROM 2026-09-23 addresses, the new line input and SYNTAX ERROR code $EF3E–$EFDD, free $EFDE–$EFFE (33 bytes), the end byte at $EFFF. `ORG 0EF00h` (the old test program's place, its data commented out) lies inside the code and emits nothing | `basic.asm`, `basic.lst`, `monitor.asm` equates |
| $F000–$FF14 | | ROM: the monitor with the video unit (ROM 2026-09-25 and later; in the chip since 2026-10-07): 3,947 bytes in the half | `monitor.lst` |
| $FF15–$FF8F, $FFA2–$FFBB | 123 + 26 | ROM, free ($FF in `rom.bin`) | `firmware/rom/README.md` |
| $FF90 | | the interrupt service routine `isrcode` | `monitor.asm` `org 0ff90h` |
| $FFBC | 4 | (ROM 2026-09-25) the video entry `JSR vidctl / RET`, below the full table: ACC 0 probe, 1 init, 2 clear | `monitor.asm`, `firmware/abi/README.md` |
| $FFC0–$FFFF | 64 | the 16 BIOS vectors, 4 bytes each (15 until 2026-09-23; the 2021 chip has 11, then `00 FF FF …`) | `monitor.asm` `org 0ffc0h`, `eprom-captured-2026-09-18.hex` |

The monitor's own routines are not at fixed addresses across builds; the vectors are ([MONITOR.md](MONITOR.md)).

## 2a. What bounds each area (checked 2026-10-08)

Both ROM images were checked byte for byte (`basic.img`, `monitor.img`: no address is written twice, every BASIC entry
stub fits its 16-byte slot, neither half runs into the other). The RAM areas are fixed by equates and nothing
checks a size at run time:

| Area | What can overrun it | Into |
|---|---|---|
| BASIC input line $0300 | a line over 256 characters (`get_inputline` stores until LF) | $0400, the line under construction |
| the monitor's `line_buffer` $0F80 (`P`) | a line over 112 characters | the video variables $0FF0, then the BASIC program at $1000 |
| FOR-NEXT stack $0282 (R4) | more than 10 nested FOR | the GOSUB stack |
| GOSUB stack $02C2 (R5) | more than 30 nested GOSUB (or GOSUB in a loop without RETURN) | $0300, the input line, and on |
| BASIC program $1000–$1FFF | a program over 4K | nothing: the end (with the end token) is dropped without a message |
| the stack $0EFF down | deep recursion | $0BFF down (under Y1/OS: the handle buffers) |

Other hazards found the same day:

- **R2.** `exe_set_variable` and `exe_get_variable` address the variables through R2, the register the microcode
  uses for every LDA/STA/LDR/STR (CLAUDE.md, "Machine facts"; the emulators keep it apart, so a fault shows on the
  machine only). No memory-direct instruction sits between setting R2 and using it, so it holds today; any change
  there must keep it that way, or move the pointer to another register.
- **Division by zero** (`/` and `MOD`: `parse_div16` / `parse_mod16` subtract until the remainder is below the
  divisor) never ends: a program that divides by 0 hangs the machine.
- **The monitor's `C` command** copies $0400 bytes from `BASIC_TEST` ($EF00) into the program buffer, but the test
  program there is commented out and BASIC's code has reached past $EF00 since the 2021 build ($EF51 then, $EFDD
  now): it loads code (and the start of the monitor) as a program.
- **ARGBUF and `line_buffer` overlap** at $0F80–$0FBF (ARGBUF is 128 bytes since 2026-09-23; the monitor's equate
  comment still says 64). They are never in use together today.
- **An address-dependent fault**: with BASIC's code 13–20 bytes higher (the first ROM 2026-10-07 build), `LIST`
  printed a wrong line number on the machine only (`BACKLOG.md`).

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
  bits 12–15 forced high until an A15-high address is presented with `-VMA`).
- Both (2026-09-25, `software/videomodel.h`): the video card — $D000–$D7FF RAM as before, the 6845 at $D800/$D802,
  $FF from the odd (latch) addresses; `-V` prints the screen at exit, `-W` logs CRTC writes, `-N` takes the card away
  ($D000–$DFFF reads $FF).
- Both: the CF card is on I/O ports, not in the memory map ([IO-PORTS.md](IO-PORTS.md)).

## 6. Open items touching the map (`BACKLOG.md`)

- The memory card's unconnected jumper wire on IC7 pin 4 (purpose not remembered).
- The FORCE-ROM race and the raw `-WE` (design-review M1, M2): memory card v2.0 has R15 (ADDR15 pull-down) and JP3
  (ROM write protect); the AT28C64B in the machine has its software data protection set (2026-10-07).
- The unchecked areas and hazards of section 2a (each one an item in `BACKLOG.md`, 2026-10-08).
- Whether the OS load address stays $1000 if the OS grows past 16K.
