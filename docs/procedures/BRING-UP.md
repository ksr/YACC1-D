# YACC1 bench procedures: power, reset, clock, microcode, ROM, test programs, bus tester

The procedure book for the machine on the bench: how to bring it up, how to load what it needs, how to prove each
piece with the programs and scripts in the tree, and what to look at when a step fails.

Written 2026-09-23 from the YACC1-D tree.

Sources (every section says which one it draws on): `docs/system/MACHINE.md` (what is in the machine and what is
loaded), `hardware/FABRICATED.md`, `tools/ucode_send.py` (docstring), `embedded/sequencer-card/README.md` and
`sequencer4/Sequencer4.ino`, `firmware/rom/README.md`, `firmware/abi/README.md`, `firmware/rom/eprom-captured-2026-09-18.bin`
and `firmware/rom/shipped/rom.bin` (compared byte for byte for this document), `tests/assembler/{ledcount,romcount,romdiag,brur}/README.md`,
`docs/procedures/BUS Driver Commands - Google Docs.pdf` (the script language; read with pypdf), `tests/bus-tester-scripts/README.md`,
`tools/busdrv.py`, `embedded/bus-tester/README.md` and `bus-driver/bus-driver.ino`, `tests/memory/*.py` and their logs,
`tests/video/README.md`, `tests/sequencer/*.log`, `hardware/DESIGN-REVIEW-NOTES-datapath.md`, `hardware/DESIGN-REVIEW-NOTES-control-io.md`,
`docs/isa/MICROCODE-REVIEW-NOTES.md` (section 7), the card READMEs and `Build Notes.md` under `hardware/cards/`, `docs/procedures/System Build Notes.md`,
`docs/system/connector/README.md`, and the generated `docs/bom/*.md` (for the names of switches, jumpers and LEDs on each card).
Anything the tree does not settle is marked **To verify:** with what would settle it.

The companion document `TESTING.md` lists every test in the tree; this one is about the bench.

---

## 1. What is on the bench

The machine is a set of cards on a 96-pin DIN 41612 backplane (Bus Template V3.2 signal names, `docs/system/connector/README.md`).
From `docs/system/MACHINE.md` (2026-09-20, updated through 2026-09-23):

| Slot use | Card | Revision | Why it is there |
|---|---|---|---|
| bus | Backplane | V2.0 | 8 slots X1..X8, bulk electrolytics C7/C8, 5 V and GND wire pads, PWR LED (`docs/bom/backplane.md`) |
| CPU | Sequencer logic | v2.1 ("V2.1l", 218 mm) | instruction register, step counter, the pipeline latches that drive every control line, front panel |
| CPU | Sequencer memory | V2.1 + EEPROM adaptor in IC9 | the control store: 64 steps x 8 bytes per opcode in eight 62256 RAMs, loaded from the I2C EEPROMs by an ATmega328P |
| CPU | ALU | V3.2 | accumulator, TMP path, adders, shifter, the branch-condition mux |
| CPU | Index registers x2 | 1.1 | card 0 = R0..R3, card 1 = R4..R7 (J3 selects the card); R0 is the PC, R1 the stack pointer (`firmware/abi/README.md`) |
| I/O | I/O | V1.1 | 16C550 UART behind P0/P1 at 38400, switch/LED port, two TIL311 displays, LCD header |
| memory | Memory | v1.3 | 2 x 62256 (64K RAM), one 28C64 (8K EEPROM at $E000), FORCE-ROM boot remap, the TMP0/TMP1 registers |
| video | Video | V1.0 (Fusion export) | installed for bring-up, **6845 socket empty**, +5V and VCC joined by a wire (2026-09-21) |
| bench | Bus Test Card | v1.1 | ATmega328P + MCP23017 expanders; drives or watches every bus line from a serial console (FTDI, 19200) |
| bench | Mem Switch | V1.1 | 16-byte switch-programmed ROM at $0000 (sixteen 8-way DIP switches named `0000`..`1111`), for CPU bring-up without the memory card |
| bench | Mem Register | V1.0 | 16-byte RAM at $0010 with read/write LEDs, the same purpose |

Not fitted and not needed: the two bus jumper boards (obsolete), Address+TMP (retired 2021), Bus Tester V3.1 (never ordered).

The order in which the cards were originally built and brought up is in `docs/procedures/System Build Notes.md`:
bus tester, backplane, memory, (prototype), index register 1, ALU, index register 2, sequencer memory, sequencer logic.
That is also a sensible order for a rebuild, because each step can be proved with the bus tester before the next card
depends on it (sections 6 and 7).

### 1.1 Board check before a card ever goes on the bus

From the card `Build Notes.md` files (memory, bus tester; the text is the same on both):

1. GND is the 3 far-right and 3 far-left pins of the 96-pin connector, VCC the 3 pins next to GND on each side. Check they
   are connected on the card.
2. VCC must not be shorted to GND. Check with a meter on any bypass capacitor (every cap has a GND side and a VCC side), so
   the check also proves the rails reach the card.
3. Plug the card in, power the bus: the card's PWR LED must light (every card has one, `docs/bom/<card>.md`).
4. With the Bus Test Card fitted, run its `bus-test` sketch (`embedded/bus-tester/bus-test`) to look for shorts between
   bus lines before any ICs are installed.

---

## 2. Power

- The backplane takes 5 V on its `5V` / `GND` wire pads (`docs/bom/backplane.md`: two WIREPAD parts, package 4,16O1,6) and
  has a PWR LED and two bulk electrolytics (C7/C8, added in V2.0 per `hardware/FABRICATED.md`). Every card is TTL/LS on the
  one 5 V rail.
- **To verify:** the bench supply's rating and connector. The tree records no current figure for the full card set; measure
  it once at the supply and note it in `docs/system/MACHINE.md`.
- The bus tester and the sequencer-memory card can also be powered from their FTDI cable through the `FTDI-VCC` solder
  jumper (`docs/bom/bus-tester.md`, `docs/bom/sequencer-memory.md`). The bus-tester build notes say: jumper FTDI-VCC only when
  the card is being run **off** the bus; remove it when the card is on a powered bus. `hardware/DESIGN-REVIEW-NOTES-control-io.md`
  2.2 says why: closed on the bus it parallels the FTDI's 5 V with the backplane rail.
- The video card as designed had its `+5V` net fed by nothing (`hardware/cards/video/README.md`); Ken joined `+5V` to `VCC`
  with a wire on 2026-09-21. Do not remove that wire: IC1, IC2, RN2 and every decoupling capacitor on the card hang off it.

### 2.1 What happens at power-up (why the machine is not usable for the first minute)

1. The sequencer-memory ATmega boots (`embedded/sequencer-card/sequencer4/Sequencer4.ino`). With the `UCODE` switch in run
   mode it copies the microcode from the I2C EEPROMs into the eight 62256 RAMs (16 s), reads the whole copy back and compares
   it with the EEPROM (29 s), and only then raises READY - 54 s after reset (`tests/sequencer/boot-run-mode-2026-09-21-sequencer4.log`).
   LOADING is on while copying; READY comes on when done; on a mismatch FAULT blinks six times and READY never comes.
2. READY drives the bus signal `-BUS-EN` through the logic card (`DESIGN-REVIEW-NOTES-control-io.md` 1.8). Until then every
   control line on rows B and C of the bus is a tri-stated 74LS374 output with no pull-up anywhere (`DESIGN-REVIEW-NOTES-datapath.md`
   M5, S3): the lines float at ~1.5-1.9 V. LS inputs read that as high (inactive), so nothing is selected, but the levels are
   undefined. This is the window in which the memory card's `-WE` follows an undefined `-MEM-WR` (M2, M5).
3. **The bus must be quiet during the copy.** The clobbered transcript `tests/sequencer/boot-run-mode-2026-09-21.log` is what
   you get when the bus tester holds `-BUS-EN` asserted while the ATmega writes the RAMs: the logic card drives the address
   lines, every write lands on address 0 and every dumped instruction reads as zeros. With the tester idle
   (`bus-monitor` sketch, or `bus-driver` with nothing asserted) the same boot gives RAM == EEPROM (`...-bus-quiet.log`).
4. There is **no power-on reset** (`DESIGN-REVIEW-NOTES-datapath.md` S1): `-RESET` comes from a manual RS latch on the logic
   card (RESET = NOR(FP-RESET, RUN)). After a cold start the memory card's FORCE-ROM flip-flop, the sixteen 74LS192 register
   counters and the ALU's carry/shift flip-flops are in arbitrary states until the front-panel RESET is operated. So the first
   thing after READY is always a reset (section 3).

---

## 3. Reset and run: the front panel

The sequencer-logic card carries the front panel (`docs/bom/sequencer-logic.md`): three toggle switches `RESET`, `SS/WAIT`
and `STEP-CLK` (9070-1W), two push buttons `HALT` and `CONT`, an `OUT` LED (the ON/OFF flag the `ON`/`OFF` instructions set,
`firmware/abi`), jumpers `JP1`..`JP4`, `SS-SEL` and `-INT-PULLUP`, and the oscillator socket `QG1`.

### 3.1 Reset

- `RESET` toggle: in the RESET position the latch holds `RESET` high and `-RESET` (bus pin C30) low; moving it to the run
  position (called EXECUTE in the design review) releases it. Only the **release** edge reloads the pipeline (a ~30-45 ns pulse
  `N$32`, `DESIGN-REVIEW-NOTES-control-io.md` 1.3): while the switch sits in RESET the pipeline latches keep driving whatever
  step was executing, or power-up garbage, onto the bus.
- What reset does around the machine (`DESIGN-REVIEW-NOTES-datapath.md` S2, `software/ucemu/README.md` "Reset"): the
  instruction register clears, all sixteen register counters clear (so PC = R0 = $0000), the ALU carry/shift flip-flops
  clear, and the memory card's FORCE-ROM flip-flop is preset, so the 28C64 answers **every** address until the first `-VMA`
  cycle with ADDR15 high. That is why the first fetch at $0000 gets the byte at ROM offset $1000 = $F000, and why every
  ROM image in the tree starts with a `BR` to an address above $8000 (`tests/assembler/romcount/README.md`: `F000 A0 F0 03 BR begin`).
- From the bus tester: `-RESET:1#` then `-RESET:0#` (asserts then releases; the firmware inverts active-low names,
  `tools/busdrv.py`). `busdrv.py --reset` does the same pulse. The tester also has push buttons `BUS-RESET` and `CPU-RESET`
  (`docs/bom/bus-tester.md`). **To verify:** which of the two drives bus `-RESET` and which resets the tester's own ATmega;
  the schematic `hardware/cards/bus-tester/eagle/v1.1/tester.sch` answers it.
- The sequencer-memory card has its own `LOCAL-CPU-RESET` push button that resets **its ATmega** (and through JP1 pin 2 /
  `-MEM-CPU-RESET` can be tied to the logic card, `DESIGN-REVIEW-NOTES-control-io.md` 1.4). Pressing it restarts the 54 s
  copy. It is what "reset the card" means in the microcode-loading procedure (section 4).

Known hazard while reset is held (control-io 1.3): a stale pipeline word with `-MEM-WR` and `-VMA` asserted writes the
28C64 during reset, because the memory card's EEPROM `-WE` is `-MEM-WR` unqualified (`DESIGN-REVIEW-NOTES-datapath.md` M2).
It has not been seen to happen (the chip read back byte-identical to the 2021 sources on 2026-09-18), but do not leave the
machine sitting in RESET, and re-check the ROM (`tests/memory/rom_verify.py`) after a batch of power cycles.

### 3.2 Clock

- The logic card's `QG1` is a 14-pin oscillator socket (BOM: deviceset `XO-`, package DIL14S). During bring-up the machine has
  been clocked from a **function generator's TTL output plugged into that socket: pin 8 = clock, pin 7 = GND**
  (`docs/system/MACHINE.md`, 2026-09-21). At a few hertz every step is visible on the LEDs (`tests/assembler/ledcount/README.md`).
- One microcode step is two clock periods (the step counter's QA is a phase bit, `DESIGN-REVIEW-NOTES-control-io.md` 1.2;
  `software/ucemu/README.md`). `tests/assembler/romcount/README.md` gives the scale: ~590,000 clocks per LED count with the
  $2000 delay, about 0.6 s per count at 1 MHz.
- Single-stepping: `STEP-CLK` and `SS/WAIT` toggles and the `SS-SEL` jumper select the step-clock source - the front-panel
  latch (IC29) or an external clock on `JP4` pin 2 (control-io "Checked, no issue": "Step-clock source jumper SS-SEL ...;
  JP4 exposes UCODE-COUNT-RESET"). `embedded/clocker/clocker.ino` is an Arduino for that external input: pin 13 outputs the
  clock, pin 12 reads `UCODE_CLOCK`, and three buttons give one pulse, one instruction (pulse until the `UCODE_CLOCK`
  input goes high, then one more) or ten instructions. **To verify:** which JP4 pin the clocker's pin 12 goes to (the
  sketch calls it UCODE_CLOCK; the review calls the exposed signal UCODE-COUNT-RESET) and the exact switch positions for
  external stepping - read `hardware/cards/sequencer-logic/eagle/v2.1/Sequencer-Logic-Prod-V2.1l.sch` sheet with IC29/JP4.
- **To verify:** the maximum clock. Nothing in the tree gives it; `docs/isa/MICROCODE-REVIEW-NOTES.md` section 7 item 6 is
  the experiment: raise the generator until `BR` mis-targets or `INP` reads $FF and note the frequency.
- `HALT` / `CONT` buttons: HALT sets a flip-flop at the next UCODE-COUNT-RESET (instruction boundary), CONT or RESET clears
  it (control-io "Checked, no issue"). The `HALT` **instruction** ($03) stops the machine the same way (SOFT-HALT).

### 3.3 Jumpers that must be right (per card)

The names are from `docs/bom/<card>.md`; the meaning from the READMEs and the design review.

| Card | Header | Setting in the machine | Source |
|---|---|---|---|
| Memory v1.3 | `U$1` 3x8 block header | one column per 4K block $8000..$FFFF: jumper **up** = RAM, **down** = ROM, **none** = undecoded. Fitted: $8000-$CFFF up (5), $D000 none (video), $E000-$FFFF down (2) | `docs/system/MACHINE.md`, `hardware/cards/memory/README.md` |
| Memory v1.3 | `JP1` 1x3 | must be fitted: it feeds IC7's G2B (the block decoder) | `DESIGN-REVIEW-NOTES-datapath.md` M7 |
| Memory v1.3 | wire from IC7 pin 4 | present, unconnected, purpose not remembered | `MACHINE.md`, BACKLOG |
| Index registers 1.1 | `J1` (RD), `J2` (LD), `J3` (ADDR), each 2x4 | all three on one card set to the **same** ID2-3 code: card 0 = R0-R3, card 1 = R4-R7 | `hardware/cards/register/README.md`; datapath "Checked, no issue" |
| ALU V3.2 | `JP1` 1x3 | the branch-condition mux enable: pin 1 = `-ALU-FUNC`, pin 3 = GND. On GND the mux always drives BR-COND (C24); on `-ALU-FUNC` it floats whenever `-ALU-FUNC` is high | `DESIGN-REVIEW-NOTES-datapath.md` A1. **To verify:** which position is fitted (meter on C24 with `-ALU-FUNC` high) |
| ALU V3.2 | `JP2` 1x3 | **To verify:** not described in the review notes; read the schematic | |
| Sequencer logic v2.1 | `JP2` 1x2 | **must stay OPEN**: it would tie the pipeline's SPARE3 bit (always 0) to the sequencer-memory ATmega's reset and hold the loader in reset for ever | control-io 1.4 |
| Sequencer logic v2.1 | `JP3` 1x5 + `-INT-PULLUP` 1x2 | interrupt mode: `-INT` (C13) to pin 2 = edge or pin 4 = level, and the **other** input jumpered to its GND neighbour, else PRE or the clock floats | control-io 1.6 |
| Sequencer logic v2.1 | `JP1` 2x2 | SPARE3 / -MEM-CPU-RESET / SRC-ADDR / DEST-ADDR, 1:1 with the memory card's JP1 over the ribbon | control-io "Checked" |
| Sequencer logic v2.1 | `SS-SEL` 1x3, `JP4` 1x4 | step-clock source / external step clock and UCODE-COUNT-RESET (section 3.2) | control-io "Checked" |
| Sequencer memory V2.1 | `DTR-RESET` solder jumper | dead-ends (pin 2 reaches nothing): flashing the ATmega needs the local reset button | control-io 2.2 |
| Sequencer memory V2.1 | `FTDI-VCC` | open while the card is on the bus (section 2) | control-io 2.2 |
| Sequencer memory V2.1 | `JP2` 1x3, `CADDR14` 1x2 | **To verify:** not covered by the review; `CADDR14` is presumably the 15th control-store address bit for the doubled EEPROM (the adaptor) - read the schematic | |
| Video V1.0 | `SV3` 2x4 | board address compared by the 7485: installed = 0, open = 1; $D000 needs only SV3 5-6 | `hardware/cards/video/README.md` |
| Video V1.0 | `SV4` 1x3 | dot-clock source | control-io 6.3 |
| I/O V1.1 | `IO-ADDR-HL` 2x3, `IO-ADDR` 2x8, `DATA-ADDR` 2x8 | pick which two of the sixteen port addresses are the control latch and the data port; the ROM expects **P0 = control, P1 = data** | `firmware/abi/README.md`; control-io 3.3 |
| Bus tester v1.1 | `DTR-RESET`, `FTDI-VCC` | build notes: jumper DTR-RESET so opening the port resets the ATmega; FTDI-VCC only off-bus. The review (2.2) finds DTR-RESET's second pad unconnected on this board too - yet `busdrv.py` waits for the "DTR reset -> LED flash" on open. **To verify:** whether the flash is the DTR path or the bootloader's own start-up; meter on the ATmega reset pin when the port opens | build notes; control-io 2.2; `tools/busdrv.py` |

---

## 4. Loading the microcode into the sequencer card

What is being loaded: `firmware/microcode/ucode-generator2/test.hex`, 256 records (one per opcode) of 512 bytes = 64 steps x
8 bytes, regenerated by `make -C firmware/microcode/ucode-generator2 regen` and checked by `make check` (`firmware/microcode/README.md`).
The card keeps it in two 24Cxx I2C EEPROMs on the adaptor in IC9 (addresses $56/$57, `sequencer4/uCodeROM.ino`) and copies it to
RAM at every boot (section 2.1). `firmware/microcode/ucode-generator2/cache` is the sender's record of what the card holds.

The 2026-09-22 image is what is in the card now (`MACHINE.md`: loaded with `--all` that evening; `cache` == `test.hex`).
The procedure, from `tools/ucode_send.py`'s docstring and `embedded/sequencer-card/README.md`:

1. Build the image and make sure it is what you want to load: `make -C firmware/microcode/ucode-generator2 check` must say
   `test.hex: IDENTICAL to the committed microcode image`. `python3 tools/ucode_send.py --dry-run` lists which records differ
   from `cache` (only those go, unless `--all`).
2. On the card: `UCODE` switch to **DOWNLOAD**, then reset the card (`LOCAL-CPU-RESET`): the LOADING LED comes on.
3. **Run the sender first**, then press `START`:
   ```
   python3 tools/ucode_send.py                # finds the single /dev/cu.usbserial* or usbmodem*; --port to choose
   python3 tools/ucode_send.py --all          # every record regardless of the cache (what Ken did 2026-09-22)
   ```
   The order matters because opening the FTDI port resets the ATmega (DTR). The sender says it is waiting; press `START`;
   the card answers with a `>>` prompt before every instruction.
4. Per record the card flashes a LED for 100 ms after its prompt before it reads, and its serial buffer is 64 bytes, so the
   sender waits 250 ms after every prompt (`--settle`); without that the head of the record is lost and the card waits for
   ever (seen 2026-09-22). The record's trailing `-` in `test.hex` is **not** sent (the card reads exactly 512 byte values;
   a stray character is an "Unexpected Char" fault, FAULT LED blinking 5). The cache is rewritten record by record, so an
   interrupted load resumes by running the command again.
5. Afterwards: `UCODE` back to **run**, reset the card. Sequencer4 copies EEPROM to RAM (16 s), verifies (29 s), READY at ~54 s.
6. Prove it: `python3 tools/ucode_send.py --boot-check [--log FILE]` captures the run-mode boot transcript over the same port
   and compares the five instructions the firmware dumps (0, 1, 7, 124, 255) with `test.hex`. The clean transcript looks like
   `tests/sequencer/boot-run-mode-2026-09-22-reload.log`: the banner `Sequencer4 2026-09-21 (...)`, `Copying Instruction 0 ... 224`,
   `- done, 16 s`, `Verify RAM against EEPROM`, `- 29 s, RAM == EEPROM for all 256 instructions`, the dumps, then
   `RAM copy complete and verified, READY!!!` and a `RAW=... Ins=00 Line=.. Data=...` line showing the first control word
   on the ribbon.

What the older Processing sender did the same way: `embedded/sequencer-card/microcode-loader/simple_microcode_sender_64`
(115200, reads `test.hexz`, keeps the same `cache`); its 25 ms/char pace met the two timing needs by accident.

Firmware in the card: `embedded/sequencer-card/sequencer4` (flashed 2026-09-21 by arduino-cli as an Uno through the FTDI at
115200, per `MACHINE.md`; the DTR auto-reset dead-ends, so use the local reset button for the bootloader window - control-io 2.2).

Bench checks that the reloaded image still owes (BACKLOG, `MACHINE.md` item 6): `tests/assembler/brur/` (`ABC0123` on the
console) and `tests/ucemu/isa.asm` (the port-2 byte stream, on the machine through the UART). The first real evidence of the
2026-09-22 image working is `romcount` counting overnight into 2026-09-23 (section 6).

---

## 5. Burning the ROM (memory card 28C64)

From `firmware/rom/README.md`, `firmware/abi/README.md`, and a byte comparison of the two images done for this document.

- The image to burn is **`firmware/rom/shipped/rom.bin`**: 8,192 bytes, offset 0 = $E000; BASIC (`firmware/basic/basic.img`) at
  $E000, the monitor (`firmware/monitor/monitor.img`) at $F000; bytes the sources never write are $FF like a blank part.
  MD5 `a9fefd4ae21eb46eb21cff614376617f` (`ROM 2026-09-23B`, the 2026-09-23 evening build: the afternoon build with
  the CF driver and `O` moved from ports P8/P9 to P4/P5 for the I/O card v2.0; **not yet burned**). Programmer: Visual Minipro / `minipro`, device 28C64. It is built from `shipped/rom`
  (Intel hex) by `python3 tools/img2bin.py firmware/rom/shipped/rom firmware/rom/shipped/rom.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`.
- `tools/verify_firmware.py` (or `make -C software/assembler check`) proves the image reproduces from `firmware/monitor/monitor.asm`
  and `firmware/basic/basic.asm` before you burn it.
- **The chip in the machine holds the 2026-09-23 build since that day** (burned by Ken, first boot the same afternoon). Before, it held the 2021 build (captured 2026-09-18 through the bus tester as
  `firmware/rom/eprom-captured-2026-09-18.bin`). The 2026 image differs in the monitor half only ($F021..$FFFF);
  the BASIC half is identical. The differences that matter: the `G` command is now `JSRUR R7` (a call; the program returns
  with `RET`) instead of `BRVR R7` (an indirect jump through the word at the address, so `G AAAA` never ran the code at AAAA);
  the `T` menu tests are gone; the CompactFlash driver and the `O` boot command are in; the `:` Intel-hex loader
  (section 6a) and a no-echo console vector are in; the banner ends with the build date, `ROM 2026-09-23`. That chip
  build is MD5 `d2d7b027e7c6951d7dd93412a8fd9cd8`; its CF driver uses P8/P9. The tree's `ROM 2026-09-23B` behaves the same
  except for the CF ports and the banner (the one-byte longer banner shifts the strings after it, so about 1,400 bytes
  of the monitor half differ); burn it before the I/O card v2.0's CF interface is tested (`docs/cards/cf.md` section 7).
- **How to tell which build a chip holds**: the banner at power-up ends with `ROM 2026-09-23B` on the tree's build and
  `ROM 2026-09-23` on the chip burned 2026-09-23 (the 2021 chip and the 2026-09-22 build print `YACC 2020: HELLO WORLD`
  alone). Without a console, read back two bytes with
  the programmer or `busdrv.py`:

  | Address | 2021 chip (captured) | 2026 builds | Meaning |
  |---|---|---|---|
  | $FFEC | `00` | `04` | the CFINIT vector (`JSR` = `04`) exists from the 2026-09-22 build on |
  | $FFFC | `FF` | `04` from 2026-09-23 | UARTINNE, the sixteenth vector (2026-09-22 had a `00` end byte here) |

  The other vector bytes are `04 hi lo 05` (`JSR routine / RET`) with targets that move whenever the monitor changes,
  so compare the whole image by MD5 (`firmware/rom/README.md`) or with `tests/memory/rom_verify.py` below.

- After burning: re-capture and compare with `python3 tests/memory/rom_verify.py [port] --save` (~30 s with the blocks-1
  tester firmware): it reads $E000-$FFFF through the bus tester and diffs against the image `tools/romimage.py` assembles from
  `basic.img` + `monitor.img`. Until `ROM 2026-09-23B` is burned that test (and `memory_status.py`) reports the monitor
  half as differing - expected, not a fault (`MACHINE.md`).
- Compiled programs for the **old** chip need `y1cc.py --vector` (a first word for `BRVR` to jump through); for the new one
  `G3000` calls `main` directly (`software/emulator/README.md`, `MACHINE.md`).
- Handling (memory `Build Notes.md`): one machined 28-pin socket soldered in IC13; keep each EEPROM in its own milled socket and
  move the pair, not the bare chip.
- The write-enable hazard (section 3.1, M2): the 28C64 is written by any `-MEM-WR` while it is selected, including during
  FORCE-ROM. A scratch chip is the right one for the M2 bench experiment.

---

## 6a. Loading programs into RAM over the console (`:`, `tools/monload.py`)

From the 2026-09-23 ROM on, the monitor takes Intel-hex records at its prompt: a `:` starts load mode, each record is
stored and answered with `.` (good), `?` (bad digit or checksum) or `!` (address outside $1000-$DFFF, or it read back
differently: the second is a RAM fault worth chasing), and the end record prints `LOADED`. ESC abandons.

```
python3 tools/monload.py prog.img --port /dev/cu.usbserial-XXXX --go 3000 --listen 5
```

sends a y1cc or assembler image (compile without `--boot`; programs start at $3000 and return with RET), runs it and
prints its output; `--term` then leaves a plain terminal open (Ctrl-] quits). The console is the I/O card's UART at 38400
8N1 through a USB-RS232 adapter on the DB9; the sequencer card's FTDI is excluded from the automatic port choice.
**Pacing**: the monitor needs about 1,600 CPU clocks per received character and the UART FIFO is off, so the default
3 ms between characters assumes a clock of 1 MHz or more; slower clocks need `--delay` raised in proportion
(delay_ms >= 3.2 / clock_MHz). A `?` on a record that is right on disk means characters are being lost: raise
`--delay`. Checked on both emulators and through a pseudo-terminal (`tests/monload/run.py`), not yet on the machine.

## 6. The ROM test programs (proving the CPU without the monitor)

Three small programs in `tests/assembler/` exercise the machine from ROM (or from the switch card) with nothing but LEDs as
output. Each has a `README.md`, an `.asm`, the assembler output and, for the two 28C64 ones, an 8K `.bin` to burn instead of the
monitor. All three are also run on the microcode emulator by `make check` (see `TESTING.md`).

### 6.1 `ledcount` - the 16-byte switch-ROM counter (Mem Switch card, 2026-09-21)

Ten bytes at $0000, set on the Mem Switch card's DIP switches (one row of 8 per byte, bit 7 first; the table with the
switch positions is in `tests/assembler/ledcount/README.md`): `LDAI 0` / `OUTI P0,SWITCHLED` / `OUTA P1` / `ADDI 1` / `BR $0002`.
The I/O card's LEDs count 00, 01, ... FF, 00 at one count per four instructions. This is the program the CPU ran on
2026-09-21 on the function-generator clock with the ALU and one index card (`MACHINE.md`). It uses only PC-relative addressing,
so it proves fetch, `OUTI/OUTA`, `ADDI` and `BR` - and nothing about the index registers, the stack or the ROM card.

Caution from `DESIGN-REVIEW-NOTES-datapath.md` M4: the memory card's low RAM cannot be removed from the map, so with the
memory card **and** a bring-up card on the bus every read of $0000-$001F has two drivers (three under FORCE-ROM). Use the
bring-up cards without the memory card. **To verify:** whether the 2026-09-21 switch-ROM run had the memory card fitted
(`MACHINE.md` lists the cards refitted, not the ones removed).

### 6.2 `romcount` - the EPROM tool chain (2026-09-22)

Burn `tests/assembler/romcount/romcount.bin` (41 bytes at $F000, rest $FF) instead of the monitor and reset:

1. With the I/O card's **input-switch line low** the LED board and the TIL311s follow the eight switches (ON/OFF LED off).
2. Flip the input switch high: the ON LED lights and the machine counts up from the switch value on LEDs and TIL311s,
   wrapping $FF -> $00. Reset (input switch low first) to go again.

The delay word at ROM offset $101B-$101C ($F01B-$F01C, big-endian) is $2000 = ~590,000 clocks per count (~0.6 s at 1 MHz);
patch it in the programmer's buffer for a slow clock (the README suggests $0010 for a few-hertz generator).

**The register-card lesson (2026-09-22 evening).** The first build kept the count in R6 and the delay in R7. On the bench
it mirrored the switches and then lit every LED: the bring-up machine had **one** index-register card (R0..R3), and a read of an
absent register leaves the bus to its pull-ups ($FF) while loads to it vanish - so the count showed FF and the delay loop
never ended. `romdiag` (next) found it in one run; `y1ucemu -R 1` reproduces it. The shipped build uses R3 and TMP and runs
with one card or two. Card 1 was fitted the same evening and `romcount` then counted overnight into 2026-09-23 on the reloaded
microcode without a fault (`MACHINE.md`) - the first hardware evidence for the 2026-09-22 image (BRNZ, DECR, MVRHA, MVAT/MVTA,
ADDI, OUTA/INP, BRINL all on the board).

What a failure tells you (`tests/assembler/romcount/README.md`): nothing on the LEDs after reset = the ROM is not read at
$F000 (FORCE-ROM, chip select, socket) or the first bytes are wrong - read the chip back and look at offset $1000; switches
mirrored but no count = the input line is not reaching the condition mux, or the switch rests high; skipped/repeated values =
`ADDI`, `MVARL/MVRLA` or the LED latch; ON LED never lights = the OUT-ON control line.

### 6.3 `romdiag` - one instruction per stage, paced by the input switch (2026-09-22)

Burn `tests/assembler/romdiag/romdiag.bin`, reset with the input switch low, then flip the switch once per stage and read the
LEDs (the full table with the "if wrong" column is in its README):

| Stage | LEDs | Proves |
|---|---|---|
| 0 | the switches | switch read / LED path |
| 1 | AA | `LDAI` to LEDs, `JSR`/`RET` (stack at $0EFF) |
| 2, 3 | 20, 11 | `MVIW R3` + `MVRHA` / `MVRLA` (FF = no register answered) |
| 4 | 03 | `DECR` |
| 5, 6 | 01, 02 | `BRNZ` not taken on zero / taken on non-zero (F0/F1 = the opposite) |
| 7 | FF | `ADDI` |
| 8 | 33 | TMP round trip |
| 9 | 20 | R7 readable = **register card 1 fitted** (FF = it is not) |
| 10 | 55 | the delay loop exits |
| 11 | 00 01 02 ... | the count |

The ON LED lights when stage 0 ends. Stage 9 is the one to look at first on a machine whose card set is in doubt.

### 6.4 `brur` - the new BRUR $AD (emulator-proven only)

`tests/assembler/brur/brur.asm` prints `ABC0123` on the console then HALTs; it needs the 2026-09-22 microcode (section 4) and
a way to get the program into RAM. **Not yet run on the machine**: loading RAM needs the monitor `E`-command loader
(`tools/monload.py`, BACKLOG) or a burn at a ROM address. What to check on the bench when it runs: the register-to-branch-register
path (`-REG-RD-HI/LO` + `-HL-SWAP` into `BRANCH-LD-HI/LO` with `-2-BYTE-OPERAND-SEL`, the steps JSRUR also uses).

---

## 6b. The bench test set (`tests/bench/run.py --port`)

Once the 2026-09-23 ROM is in and `tools/monload.py` can load `hello`, one command runs the whole set on the machine:

```
python3 tests/bench/run.py --port /dev/cu.usbserial-XXXX          # all 15, in order; --only hello,brur,isa for a subset
```

Each program is loaded through the `:` loader, run with `G3000`, and its output compared with the transcript the
microcode-level emulator produced for the same image (`tests/bench/expected/NAME.uc.out`). Every transcript, with the
expected text beside each failure, goes to `tests/bench/logs/bench-DATE.log`; commit it: it is the record of what the
machine has proven. Read the results in this order, because each step assumes the ones before it:

| Program | What it proves | A failure points at |
|---|---|---|
| `hello` | the loader, `G`, RET back to the monitor, the console vectors | the UART path, the `:` loader, JSRUR/RET |
| `brur` | `BRUR Rn` ($AD, loaded 2026-09-22): prints `ABC0123` | the new microcode record, the register-to-branch-register path |
| `isa` | every arithmetic, logic, shift, compare, register, memory and stack instruction: 62 hex bytes, 16 per line | compare byte by byte with `expected/isa.uc.out`; the byte's position names the instruction in `tests/ucemu/isa.asm` (results in order). `CD AB` = PUSHR/POPR (H-1), the `59 4E` pairs = taken/not-taken branches (H-2) |
| `arith` ... `syscall` | compiled C: `rt_sub`, `rt_mul`, `rt_divmod`, shifts, compares, calls, arrays, structs, switch tables | the runtime helper the failing line exercises (`tests/compiler/NAME.c`) |

The emulators already agree with these transcripts (`make check` runs the set on both, and the `--port` path itself
through a pseudo-terminal); a difference on the machine is therefore the machine's. Loading the whole set takes a few
minutes at the default 3 ms per character.

## 7. The bus tester

### 7.1 Hardware and firmware

The Bus Test Card v1.1 (`hardware/cards/bus-tester/README.md`) is an ATmega328P with MCP23017 port expanders on every bus line,
8 switches, LEDs and an FTDI header. It can **drive** any line (bus-driver), **watch** the bus (bus-monitor), and test for
shorts (bus-test). The sketches are in `embedded/bus-tester/`, one loaded at a time; all compile with `tools/verify_embedded.py`.

The card runs `bus-driver` firmware **blocks-1 (2026-09-21)**, flashed by arduino-cli as an Uno at 115200 through the FTDI
(`MACHINE.md`). Its banner before the first prompt is `bus-driver blocks-1 2026-09-21`; the host looks for `blocks-` in it.
The previous flash (the 2020 bus-driver) was read out to `embedded/bus-tester/readback/` first. **Never send `RDBLK`/`WRBLK` to
the 2020 firmware: it halts on an unknown opcode** (`embedded/bus-tester/README.md`); `busdrv.py` falls back to the per-byte
idiom when the banner has no `blocks-`.

### 7.2 The wire protocol (from `bus-driver.ino`, `tools/busdrv.py`)

```
host -> card :  CMD:OPERAND#          operand DECIMAL on the wire, no line ending
card -> host :  Data: <n>  (reads)    then the prompt  >>
                Error: ...            (the card HALTS after a bad opcode on the old firmware; blocks-1 only halts on those,
                                       block errors reply "Error: ..." and continue)
```
Signal names are the bus names from `embedded/libraries/YACC/YACC_Common_header.h`; a leading `-` marks an active-low line and
the firmware inverts it, so `-RESET:1#` asserts reset (the pin goes low). Special opcodes (not bus lines): `RD-DATABUS`,
`RD-DATABUS-L/-H`, `WR-DATABUS`, `RD-ADDRBUS`, `WR-ADDRBUS`, `DATABUS-RD-MODE`, `DATABUS-WR-MODE`, `ADDRBUS-RD-MODE`,
`ADDRBUS-WR-MODE`, `RBR-COND`, `RD-IN`, `READ-SWITCHES`, `SET-LEDS`; blocks-1 adds `RDBLK:addr,count#` (1..64 bytes back as
`Data: hh hh ...`) and `WRBLK:addr,count,hh...#` (1..32 bytes, two hex digits each) - one round trip per block instead of four
per byte (~0.16 s per byte before, mostly USB latency). Serial: 19200 baud (`BAUD` in the sketch; `busdrv.py` and the
Processing sender must match).

The memory idioms every script and tool uses (`busdrv.py`, copied from `command_sender_8.pde`): **always** `-BUS-EN:1#` and
`-VMA:1#` before driving memory; `ADDRBUS-WR-MODE:1#`; then read = `WR-ADDRBUS:a` / `-MEM-RD:1` / `RD-DATABUS-L` / `-MEM-RD:0`
with `DATABUS-RD-MODE:1`, write = `WR-ADDRBUS:a` / `WR-DATABUS:v` / `-MEM-WR:1` / `-MEM-WR:0` with `DATABUS-WR-MODE:1`.

Two behaviours to plan around: opening the serial port resets the tester (LED flash ~1 s, then the banner and `>>`), so every
tool waits for the prompt first and **the port must stay open** for as long as the bus state must hold (`tests/video/hold_address.py`);
and a USB glitch drops the port mid-run - `busdrv.py` waits up to 30 minutes for it to come back, reopens, re-runs the caller's
`on_reopen` setup and resends (that is what `tests/memory/full-run-2026-09-21-attempt1-linkdrop.log` records).

### 7.3 The script language (the PDF, `docs/procedures/BUS Driver Commands - Google Docs.pdf`)

The Processing host `embedded/command-sender/command_sender_8` sends script files to the card and adds a small language on top
of the wire protocol. From the PDF (a Google Docs export; the command list is readable, page 1):

| Line | Meaning |
|---|---|
| `COMMAND:OPERAND#` | send to the card (`-RESET:1#` sets reset active; since -RESET is active low the line goes low) |
| `COMMAND:OPERAND#EXPECTED!` | send, and compare the returned decimal value with EXPECTED |
| `COMMAND:OPERAND#EXPECTED!VARIABLE` | ... and store the returned value in VARIABLE |
| `COMMAND:VA#` | an operand starting with `V` is a variable (VA = variable A) |
| `LET VARIABLE=VALUE` | assign (decimal) |
| `FOR VARIABLE=initial,final,increment` / `NEXT VARIABLE` | loop |
| `:Label` / `GOTO Label` | jump |
| `WAIT` | wait for a key or mouse click |
| `DUMP:start-end#` | dump memory (hex addresses) |
| `DUMPVARS` / `DUMPLABELS` | list variables / labels |
| `//` | comment |

Hex in the scripts, decimal on the wire (`embedded/command-sender/README.md`). Note that `tests/basic/test` (LET/FOR/NEXT/
`:loop`/DUMPVARS/DUMPLABELS) is a program in **this** language, not BASIC - its README says the interpreter had not been identified.

**To verify:** the PDF's later pages (the extraction gives only the command list and a page-2 header "BUS-DRIVER COMMAND FOR..."):
open it in a viewer for any note on expected-value failures or the `WAIT` behaviour.

### 7.4 The script library, `tests/bus-tester-scripts/`

| Folder | For | Notes |
|---|---|---|
| `Memory Card Tests/` | memory card: low/high RAM and EPROM tests, dumps (2020-07/08) | the pattern above: reset, `-VMA`, `ADDRBUS-WR-MODE`, dump $0000/$8000/$F000, fill, dump again; `dump-eprom.txt` |
| `ALU/*.new` | ALU V3.2: add, and, or, sub, branch, zero test (2020) | `.new` = converted to the 2020 signal names by `deprecated/gen1-2016/fix` |
| `IO/` | I/O card: `basic-out`, `serialin`, `serialout` | UART through P0/P1 |
| `Index Register/commands-1 copy.txt` | Index Registers 1.1 (2020-10-09, 372 lines) | |
| `Gen Test Vectors/` | a C generator for the **2016** register card - stale signal names, kept as a template | |
| `ramtest.logicsettings` | a Saleae Logic capture set-up for the RAM test | |

Sent by `command_sender_8` (file dialog; it still opens at the old `../tests/Test Vectors/` path) or, command by command, with
`python3 tools/busdrv.py --raw "-RESET:1" "-RESET:0" ...`. A Python interpreter for the script language is planned (BACKLOG;
`busdrv.py` has the wire protocol, not the labels/loops).

### 7.5 The Python bench tests (all through `tools/busdrv.py`, port default `/dev/cu.usbserial-AB6WZCQX`)

| Tool | What it proves | Time | Result on record |
|---|---|---|---|
| `tools/busdrv.py --probe` | port, banner, `READ-SWITCHES`, `RD-IN`, `RBR-COND` | seconds | |
| `tools/busdrv.py --dump FFC0 FFFF` | any memory range (hex) | | |
| `tests/memory/memory_status.py [port]` | boot remap after `-RESET`, every ROM byte vs `basic.img`+`monitor.img`, 8 low-RAM spots, and a class for every 4K block $8000-$FFFF (RAM / ROM / VIDEO / undecoded) against the jumper table | ~1 min | 2026-09-18: the jumper map as fitted |
| `tests/memory/rom_verify.py [port] [--save]` | the chip against the tree's ROM image | ~30 s | until the reburn: monitor half differs (expected) |
| `tests/memory/memory_full_test.py [port] [--log F]` | A ROM; B address lines (unique byte at $0000 and every 1<<n); C/D RAM $0000-$CFFF, address-derived then inverted pattern, written in one sweep and verified in a second (retention); E video RAM; F ROM again + nothing answers at $D800-$DFFF | ~20 min with blocks-1 (~10 h per byte) | `full-run-2026-09-21.log`: **14/14 PASS**, 53,248 cells x2, 0 bad; the earlier logs are the link-drop attempt, the run stopped for the reflash, and 13/14 (F2 failed before the test learned no CRTC is fitted) |
| `tests/video/video_ram_test.py [port] [--quick]` | the 1K display RAM at $D000-$D3FF: patterns, inverse, neighbour isolation, the block-0/9 write-through check, read stability with unrelated traffic in between | full ~14 min, quick ~1 min | **8/8** on 2026-09-21 after the +5V/VCC join; before it the write-through reproduced |
| `tests/video/hold_address.py HEXADDR [--rd]` | holds one address (with `-VMA`, optionally `-MEM-RD`) so a meter or scope can sit on the video card's decode pins; Enter releases | | |
| `tools/alias_min.py` | the minimal write-through reproduction: write $0010, expect $D010 unchanged (11), fault = 22 | seconds | no fault since 2026-09-21 |

Why the video tests are written the way they are (`tests/video/video_ram_test.py`): the memory card leaves $D000 undecoded, so a
read of an address nothing drives returns the last value on the bus - a cell that "reads back what was written" is only proof when
other traffic came between the write and the read. `memory_status.py` uses the same fact to classify undecoded blocks.

### 7.6 Bus-tester etiquette on a running machine

- The tester and the CPU share the bus. While the sequencer is READY the logic card drives every control line; the tester
  must not drive them too (a fight, `DESIGN-REVIEW-NOTES-datapath.md` M4/M5 style). Hold the CPU in RESET or take the
  tester's outputs to inputs (bus-monitor) before scripting, and **keep the tester quiet during the 54 s microcode copy** (section 2.1).
- `-BUS-EN` from the tester takes the bus away from the logic card (its 374s tri-state, control-io 1.8); that is the state the
  memory scripts assume.
- Undecoded reads echo the last bus value; ROM writes are silently ignored above $E000 by the emulator but **not** by the
  hardware (M2) - never script a write into $E000-$FFFF with the real monitor chip fitted.

---

## 8. Reading a sequencer boot transcript (`tests/sequencer/`)

The sequencer-memory ATmega prints its progress on the FTDI port at boot; `ucode_send.py --boot-check` captures it. Four
transcripts are kept:

| Log | What it shows |
|---|---|
| `boot-run-mode-2026-09-21.log` | Sequencer3 firmware, **bus tester holding `-BUS-EN`**: every dumped line `00 00 ...` - the clobbered copy (section 2.1) |
| `boot-run-mode-2026-09-21-bus-quiet.log` | Sequencer3, bus quiet: dumps equal `test.hex` (`Ins=0 LINE:00 03 d4 ff 00 85 57 03 d1`), `RAM copy complete, READY!!!` after ~156 s; note the `test pattern` fill Sequencer3 did first |
| `boot-run-mode-2026-09-21-sequencer4.log` | Sequencer4 banner, copy 16 s, verify 29 s, `RAM == EEPROM for all 256 instructions` |
| `boot-run-mode-2026-09-22-reload.log` | the same after the 2026-09-22 reload (BRUR + H-1/H-2); the last line `RAW=c002 ... Ins=00 Line=02 Data= 03: d4: fe: 00: 85: 57: 23: d1:` is the control word the ribbon carried when the dump ended |

`tests/sequencer/run.py` checks the 2026-09-21 Sequencer4 transcript against the tree's `test.hex` and expects exactly the
pre-fix `$07` (PUSHR) lines to differ - a transcript taken **after** the reload must match with no exceptions.

---

## 9. Video card checks (`tests/video/`, `hardware/cards/video/README.md`)

State: on the bus, 6845 socket empty, RN2 = 10k (the design value; it was 1k during the 2026-09-18 tests), +5V wired to VCC.
What is proven: the 1K display RAM through the bus (8/8, section 7.5) and, in `memory_full_test.py` F2, that nothing answers at
$D800-$DFFF without the CRTC. What is known to be wrong before the 6845 goes in:

1. The 6845 data register is unreachable as drawn (-CS includes /A0 while RS = A0): move RS from A0 to A1 per
   `hardware/cards/video/docs/fix-6845-register-select.md` (then $D400 = address register, $D402 = data register). The
   tempting fix (tie IC1 pin 13 high) is wrong: odd addresses would put the JP1 read-back latch on the bus.
2. The 7416 open-collector outputs (IC27) have no pull-ups; N$5 only reads high when floating. Add pull-ups.
3. (control-io 6.1) The E-pulse one-shot R1/C1 has nothing to recharge C1 except IC1's input current; at run speed E is short,
   ragged or absent. Confirm without a 6845: run any loop, scope IC1 pin 2 (expect it stuck below ~1.5 V) and pin 3.
4. (6.2) CHARCLOCK is a self-clearing runt from the 74HC160: with a slow dot clock the 74LS166 never loads and the output is
   blank. Confirm: scope IC19 pin 8 against IC28 pin 2; look for glyph bits on IC24 pin 13.
5. (6.3) 74LS outputs driving 74HC inputs (IC28): measure the high level at IC28 pin 2.

Design master is now `hardware/cards/video/kicad/v1.1/` (Ken, 2026-09-21); the Eagle folder is the record of the built board.

---

## 10. When a step fails: what to scope and where

Bus pin numbers are the V3.2 connector (`docs/system/connector/YACC1 Connector - V3.2.pdf`; the ones below are the ones the
design review quotes). IC numbers are per card, as in the schematics and `docs/bom/<card>.md`.

| Symptom | Look at | Expect / meaning | Source |
|---|---|---|---|
| Nothing runs after power-up | sequencer-memory READY LED; then bus `-RESET` (C30) after a cold start before touching the panel | READY must be on (54 s); C30 is arbitrary until RESET is operated - no power-on reset | control-io 2.1; datapath S1 |
| READY never comes, FAULT blinks 6 | the verify pass failed: RAM != EEPROM | reload (section 4); check the bus was quiet during the copy | `sequencer4` |
| Everything reads as zeros in the boot dump | the tester was asserting `-BUS-EN` during the copy | see `tests/sequencer/boot-run-mode-2026-09-21.log` | `embedded/sequencer-card/README.md` |
| Control lines at ~1.5-1.9 V | bus B24 (`-MEM-WR`), any row-B/C control line with READY low or `-BUS-EN` high | floating 374 outputs: expected while un-READY, a problem only if something latches on them | datapath M5, control-io 1.8 |
| First fetch is not from ROM / boot goes wrong | memory IC12 pin 5 (FORCE-ROM) against pin 3 on the first cycle after reset | FORCE-ROM must stay set until the first `-VMA` cycle with A15 high; it drops early if the address bus floats during `-VMA` (the microcode holds `-VMA` in every line to prevent this) | datapath M1 |
| ROM contents change over time | memory IC13 pin 27 (`-WE`) follows bus B24 one-for-one; scope B24 and C12 (`-VMA`) at power-up and with RESET held | any `-MEM-WR` while the ROM is selected writes the 28C64 | datapath M2, control-io 1.3 |
| A register reads $FF / a load vanishes | `romdiag` stage 9 (R7) | card 1 (R4..R7) not fitted, or J1/J2/J3 not set to its ID code | section 6.3 |
| Register card flaky / clears registers on a weak reset | register IC34 (CD4077) pins 2, 6, 9, 12, 13 when the line is inactive: anything under 3.5 V is out of spec; scope pin 11 vs 12 for the ~100 ns delay | LS outputs driving a CMOS 4077 | datapath R1 |
| A register increments when it should not | bus tester: `-BUS-EN` low, `-REG-FUNC-RD` with ID = R1, `-REG-UP` low, change ID to R0, release: R1 has counted | count strobe ORed with the read select | datapath R2 |
| TMP holds the wrong value | tester: value on DATA, `-TMP-REG-LD0` low, change DATA while low, release, read with `-TMP-REG-RD0`: the **first** value comes back | 374s latch on the leading edge; the microcode asserts the source one line early | datapath M3 |
| Two drivers on DATA0-7 during a read of $0000-$001F | meter on any DATA line: ~1-2 V | memory card + a bring-up card both on the bus | datapath M4 |
| Branch taken/not taken wrong | bus C24 (`BR-COND`) with `-ALU-FUNC` high and ALU JP1 on pin 1 | floats: move JP1 to GND or accept the convention | datapath A1 |
| SP-, IR- or Rn-relative instructions misbehave (JSR, RET, PUSH*, POP*, LDA/STA, ...) | bus C3 (`ADDR-REG-ID0`) during a single-stepped `PUSH`, steps 7..9 | a clean TTL high = the board differs from the drawing; ~0.5-1.5 V = sequencer IC11 gate B is fighting the pipeline (H-5). **The 10-second check that decides the most** | `MICROCODE-REVIEW-NOTES.md` H-5, section 7 |
| `BRZ`/`BRNZ` mis-target (pre-2026-09-22 image) | DATA0..7 at steps 16..18 of a taken `BRZ` with AC = 0 to a target with a non-zero low byte, and the fetch address after | the ALU was still driving during the PC load (H-2, fixed in the loaded image) | MRN H-2, section 7 |
| `PUSHR` pushes garbage | `PUSHR R3` with R3 = $ABCD into the Mem Register RAM, read back (was $21CC under the fight) | H-1, fixed in the loaded image | MRN H-1 |
| An illegal opcode ($80 etc.) | COUNT-FAULT and every strobe low | 38 all-zero records assert every active-low signal at once (H-4) | MRN H-4 |
| Machine works at a low clock, fails as the clock rises | note the frequency at which `BR` mis-targets or `INP` reads $FF | the one-step latches set the limit, not the ALU | MRN section 7 item 6 |
| Sequencer step sequence skips lines / COUNT-FAULT after 40 steps | read the markings on logic IC33/IC34 (and the register cards' counters) | the BOM says 74LS192 (decade); the fetch needs binary (193) - the machine runs, so binary is probably fitted. `tests/sequencer` could dump the step address on JP4 pin 3 / SV1 CADDR while single-stepping | control-io 1.2 |
| The sequencer-memory card is held in reset | logic JP2 | must be open | control-io 1.4 |
| Interrupt fires at once or never | logic JP3 / `-INT-PULLUP`; scope IC36 pin 13 | two jumpers needed; edge mode registers on the **release** of `-INT` | control-io 1.6 |
| Doubled LCD characters / slow strobe edges on the I/O card | IC8 pin 4 rise time (the 74LS06 open-collector strobe inverter, pull-up RN2 of unknown value) | a slow rise through the LS10/LS00 inputs can double the LCD E transition | control-io 3.2 |
| RAM control lines undefined at power-up on the sequencer-memory card | IC15 pin 14 (`-CMEMWR`) during power-up | floats until `setup()`; repaired by the copy + verify | control-io 2.1 |
| Video: no CRTC access, blank output, HC/LS level margin | section 9 items 3-5 | | control-io 6.1-6.3 |

Bench order that settles the most (`docs/isa/MICROCODE-REVIEW-NOTES.md` section 7): H-5 (C3 during PUSH) first, then H-2, H-1,
M-1 (DATA0 during fetch step 4 and VCC ripple), H-4 (fetch $80), then the clock-limit experiment, then the L-1 microcode
shortening. H-1 and H-2 are already fixed in the loaded image (status 2026-09-23: fixed and loaded; H-3 BR16Z/NZ open; M2 open);
`romcount` running overnight is the first evidence for the fixed image, the scope look at the old image's fight was skipped.

---

## 11. Open items from this document (all **To verify:**)

1. Bench supply rating/current for the full card set (section 2).
2. Which bus-tester button (`BUS-RESET`, `CPU-RESET`) drives bus `-RESET` and whether its DTR-RESET path is live (sections 3.1, 3.3).
3. External single-step wiring: which JP4 pin the `clocker` sketch's pin 12 reads, and the STEP-CLK / SS/WAIT / SS-SEL positions
   for external stepping (section 3.2).
4. The maximum clock frequency (section 3.2).
5. ALU JP1 position as fitted; ALU JP2, sequencer-memory JP2 and CADDR14 functions (section 3.3).
6. Whether the memory card was on the bus during the 2026-09-21 switch-ROM run (section 6.1, M4).
7. The remaining pages of the BUS Driver Commands PDF (section 7.3).
8. Whether the sequencer-logic step counters are 74LS192 (BOM) or 74LS193 (what the fetch sequence needs) - read the chips (section 10).
