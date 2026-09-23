# YACC1 — machine state as of 2026-09-20

What is physically in the machine and what is loaded into it, so the tree can be read against the hardware.
Sources: `hardware/FABRICATED.md` (per-card confirmation), the bring-up session of 2026-09-18/19 with the bus tester,
Ken's confirmations of 2026-09-19/20. Ken answered the open questions on 2026-09-20; both ATmega firmwares were settled 2026-09-21 by reading the flash out (bus tester = 2020 bus-driver, since re-flashed; sequencer = Sequencer3).
only a rebuild-and-reflash from the tree can settle.

## Cards on the bus

| Card | Revision in the machine | Design | Notes |
|---|---|---|---|
| Backplane | V2.0 (2021-08) | `hardware/bus/backplane/eagle/v2.0` | 8 slots; bus signal naming = Bus Template V3.2 |
| Bus jumpers | none fitted | `hardware/bus/bus-jumper-*` | horizontal V3.2 and vertical V3.0 were built for an older bus arrangement and are obsolete (Ken 2026-09-20) |
| Sequencer logic | v2.1 (2020-12) | `hardware/cards/sequencer-logic/eagle/v2.1` | the 218 mm "V2.1l" board |
| Sequencer memory | V2.1 (2020-12) + EEPROM adaptor | `hardware/cards/sequencer-memory/eagle/v2.1`, `accessories/eeprom-adaptor` | adaptor fitted in IC9, carries two 24Cxx at I2C 6 and 7 (Ken 2026-09-20) |
| ALU | V3.2 (2020-11) | `hardware/cards/alu/eagle/v3.2` | |
| Index registers | 1.1 (2020-08) | `hardware/cards/register/eagle/v1.1` | two cards: R0–R3 and R4–R7, selected by ADDR-REG-ID2..3 via each card's J3 (Ken 2026-09-20). **Only card 0 was in the bring-up build until 2026-09-22 evening**: `tests/assembler/romdiag` read R7 as $FF, and the monitor ROM needs both (R7 = every string pointer); **card 1 fitted 2026-09-22 evening**: `tests/assembler/romcount` (R3 + TMP build) then ran overnight into 2026-09-23 on the reloaded microcode, counting on the LEDs/TIL311s without a fault (Ken) |
| I/O | V1.1 (2020-11) | `hardware/cards/io/eagle/v1.1` | UART behind P0/P1 at 38400, switch/LED port, TIL311s |
| Memory | v1.3 (design 2021-03, boards ordered 2025-06) | `hardware/cards/memory/eagle/v1.3` (+ KiCad) | see jumpers below |
| Video | V1.0 (Fusion, export 2026-09-18); design master now `kicad/v1.1` (KiCad, 2026-09-21) | `hardware/cards/video/eagle/v1.0-fusion-export-2026-09-18` | installed for bring-up, **no 6845 fitted**; two bent pins straightened 2026-09-18; RN2 = 10k as designed (was 1k from the 2026-09-18 tests until 2026-09-21); **+5V and VCC joined by a wire (Ken 2026-09-21)** — the design left the +5V rail unfed |
| Bus tester | v1.1 (2016 board, 2020 rework) | `hardware/cards/bus-tester/eagle/v1.1` | plugged in for bring-up sessions, FTDI 19200 |
| Mem Switch / Mem Register | **re-fitted 2026-09-21** for CPU bring-up | `hardware/cards/mem-switch`, `mem-register` | the bring-up cards (switch ROM at $0000, 16-byte RAM at $0010); removed once the memory card worked (Ken 2026-09-20), back in 2026-09-21 with the ALU and one index card: **the CPU executes the 16-byte switch-ROM program as expected** on a function-generator TTL clock in the logic card's oscillator socket (pin 8 clock, pin 7 GND), with the tree's microcode in the sequencer RAM (Ken 2026-09-21) |

Not in the machine: the two bring-up cards (Mem Switch, Mem Register), the two bus jumper boards (obsolete), Address+TMP (retired 2021), all `deprecated/` revisions, Bus Tester V3.1/V3.11 (never built), Blank V3.2 (design only).

## Memory card v1.3 settings (verified with the bus tester 2026-09-18)

- Low RAM $0000–$7FFF; high half decoded per 4K block by IC7 into the 3x8 jumper header: jumper up = high RAM, down = ROM, none = undecoded.
- Fitted: $8000–$CFFF → RAM (5 jumpers up), **$D000–$DFFF → no jumper (undecoded, reserved for the video card)**, $E000–$FFFF → ROM (2 jumpers down).
- FORCE-ROM boot remap: after -RESET the ROM appears at every address until the first access with ADDR15 high.
- Reading an undecoded block returns the last value left on the bus (looks like RAM that echoes the last write).
- A jumper wire from IC7 pin 4 is present but unconnected; purpose not remembered (Ken 2026-09-20) — see BACKLOG.

## What is loaded

| Store | Contents | Proof |
|---|---|---|
| Memory card 28C64 EEPROM | **the 2026-09-23 build, burned by Ken 2026-09-23** (Visual Minipro, `firmware/rom/shipped/rom.bin`, MD5 d2d7b027e7c6951d7dd93412a8fd9cd8): BASIC unchanged; the monitor with G = JSRUR R7, the CompactFlash driver and `O`, the `:` Intel-hex loader, vectors CFINIT/CFREAD/CFWRITE/CONST/UARTINNE at $FFEC..$FFFC; banner `YACC 2020: HELLO WORLD  ROM 2026-09-23` | **first boot on the machine 2026-09-23**: banner, register dump and the full help menu (with `O` and `:`) over the UART at 38400 (`screen /dev/cu.usbserial-AB0MVHSQ 38400`); Ken then used the monitor commands and ROM BASIC interactively, all working (Ken 2026-09-23). The ROM tool chain (assembler -> image -> Visual Minipro -> 28C64 -> boot) is proven. **tests/bench on the machine, 2026-09-23 evening: 14 of 14 PASS** (`tests/bench/logs/bench-2026-09-23-1855.log`): the `:` loader, BRUR, the full ISA sweep and eleven compiled C programs, byte-identical to the microcode emulator, after the SHIFT-OUT carry fix (`docs/cards/alu.md` 3.3). The first run (`bench-2026-09-23-1809.log`) found that fault: hello, brur and isa passed, arith hung. The 2021 chip image is kept as `firmware/rom/eprom-captured-2026-09-18.*` |
| Sequencer microcode (RAM/EEPROM on the sequencer-memory card) | **the 2026-09-22 image = the tree's `firmware/microcode/ucode-generator2/test.hex`** (BRUR at $AD, the H-2 fix in BRZ/BRNZ/BR16Z/BR16NZ, the H-1 fix in PUSHR: six records differed from the 2026-09-21 image; all 256 sent with `tools/ucode_send.py --all` on 2026-09-22, the card verified RAM == EEPROM and its five boot dumps equal test.hex, `tests/sequencer/boot-run-mode-2026-09-22-reload.log`) | the loader's `cache` = what was last sent = this image |
| Sequencer-memory ATmega328P | `embedded/sequencer-card/sequencer4` **flashed 2026-09-21** (400 kHz I2C, block EEPROM reads, page writes, the copy read back before READY) | run-mode boot: copy 16 s, verify 29 s, READY at 54 s, RAM == EEPROM for all 256 instructions (`tests/sequencer/boot-run-mode-2026-09-21-sequencer4.log`). Sequencer3 (what it ran before, 156 s unverified) is in `deprecated/sequencer3`; the pre-2026 flash is in `readback/` |
| Bus tester ATmega328P | `embedded/bus-tester/bus-driver` **blocks-1 (2026-09-21)**, flashed by arduino-cli as an Uno at 115200 through the FTDI | Before the flash the chip held the 2020 bus-driver (same strings and signal table, older toolchain build; read out to `embedded/bus-tester/readback/`), so the MCP23X17 port was never loaded. Banner `bus-driver blocks-1 2026-09-21` |
| Video card | nothing loaded; 6845 socket empty | dual-port RAM tested via the bus: `tests/video/video_ram_test.py` 8/8 on 2026-09-21 |

Plan for the disk operating system, CF card and the port/memory maps: `OS-PLAN.md` (2026-09-22).

## Software that talks to it (Mac)

- `tools/busdrv.py` — drives the bus tester (`CMD:OPERAND#`, `>>` prompt); `tools/alias_min.py` reproduces the (now resolved) video-card fault; `tests/video/video_ram_test.py` is the video RAM test; `tests/memory/memory_status.py` the memory-card status check (boot remap, ROM image, RAM, block map).
- `embedded/command-sender/command_sender_8` (Processing) — sends `tests/bus-tester-scripts/`.
- `embedded/sequencer-card/microcode-loader/simple_microcode_sender_64` (Processing, 115200) — loads `test.hexz`.
- `software/assembler` (`asm file -d=yacc1`), `software/emulator`, `software/ubasic-c`, `software/disassembler/disasm2` (needs its include restored).
- `os/` (2026-09-22) — Y1/OS v0: `make -C os run` boots it on the microcode emulator from `os/disk.img` (P8XFS v2, `tools/p8xfs.py`); both emulators take `-c disk.img` for the CF card on ports P8/P9. The card is not built yet.
- `software/ucemu/y1ucemu` (2026-09-22) — the microcode-level emulator (steps `test.hex` through a model of the cards); the monitor boots on it from reset and runs compiled programs via `G3000`.
- `software/compiler/y1cc.py` (2026-09-22) — the C cross-compiler: `prog.c` → YACC1 assembly → `.img`; images load at $3000 (BASIC's token buffer is $1000-$1FFF); with the rebuilt monitor `G3000` calls main and RET comes back to the prompt (`--vector` for the 2021 chip). Not yet run on the machine: loading RAM needs the E-command loader (BACKLOG).

## Known faults / open on the hardware

1. Video card: 6845 data register unreachable as drawn (-CS includes /A0 while RS = A0); bench fix = RS to A1, see `hardware/cards/video/docs/fix-6845-register-select.md`.
2. Video card: 7416 open-collector outputs with no pull-ups.
3. Video card: the block-0/9 write-through fault of 2026-09-18 is RESOLVED (2026-09-21): its cause was the unpowered +5V
   rail (IC1, IC2, RN2 and all decoupling on a net with no source); joined to VCC by a wire, 1K RAM test passes 8/8.
4. Blank V3.1 template (and the cards drawn on it) label C3–C6 with the pre-V3.2 names; harmless, documented.
6. Sequencer EEPROM: the tree's microcode gained `BRUR Rn` ($AD) and the H-1/H-2 bus-fight fixes (2026-09-22); until the
   EEPROM is reloaded, $AD is an all-zero word on the machine and PUSHR/BRZ/BRNZ run with the fights the microcode emulator
   showed to corrupt the pushed word and the branch target under the usual TTL rule (if the monitor ever printed a string
   on the machine, the fight fell the other way: worth one scope look at DATA0 during a taken BRZ, `MICROCODE-REVIEW-NOTES.md`
   H-2). Load, then bench-check with `tests/assembler/brur/` (`ABC0123`) and `tests/ucemu/isa.asm` (the byte stream).
5. Monitor as burned (2021): the G command is `BRVR R7`, an indirect jump through the word at the address (the microcode's
   `branch()` fetches the target through the register), so `G AAAA` never ran the code at AAAA. Fixed in the tree 2026-09-22
   (`JSRUR R7 + BR cmdloop`: a call, the program returns with RET) — **reburn the 28C64 from `firmware/rom/shipped/rom`**.
   Compiled programs for the OLD chip need `y1cc.py --vector`.
