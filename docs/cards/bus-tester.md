# Bus Test Card v1.1 (and the unbuilt v3.1) — theory of operation

An ATmega328 and six MCP23017 I2C port expanders that can drive or read every line of the backplane from a serial
console, so that each card can be exercised without a CPU. It is the instrument behind every 2026-09 memory, ROM
and video test.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/bus-tester/eagle/v1.1/tester.sch` and `.brd` (the board in use; parts and nets parsed from
the Eagle XML), `hardware/cards/bus-tester/eagle/v3.1/tester.sch` (the 2020 redesign, never ordered),
`hardware/cards/bus-tester/README.md`, `eagle/v1.1/Notes.md`, `eagle/v1.1/Build Notes.md`, `eagle/v3.1/Notes.md`,
`embedded/bus-tester/README.md`, `embedded/bus-tester/bus-driver/bus-driver.ino`,
`embedded/libraries/YACC/YACC_Common_header.h` (the signal table), `tools/busdrv.py`, `tools/alias_min.py`,
`docs/procedures/BUS Driver Commands - Google Docs.pdf`, `tests/bus-tester-scripts/README.md` and the scripts,
`tests/memory/memory_full_test.py`, `rom_verify.py`, `memory_status.py`, `tests/video/*.py`,
`hardware/DESIGN-REVIEW-NOTES-control-io.md` (sections 1.1, 4, 5.1, cross-card), `docs/system/MACHINE.md`,
`hardware/FABRICATED.md`, `BACKLOG.md`.

## 1. Purpose and place in the machine

The tester plugs into any backplane slot and pretends to be the rest of the machine. Six MCP23017 expanders give
96 GPIO lines; 32 of them are the address and data buses, 52 are the control signals of the Bus V3.2 pinout, and
the remaining 12 serve an on-card switch/LED byte. The ATmega runs the `bus-driver` sketch: it reads one command
at a time from an FTDI serial cable (`CMD:OPERAND#`, 19200 baud, no line ending), sets or reads the named line
through the expander, and answers with an optional `Data: n` line and a `>>` prompt. A host script (`tools/busdrv.py`
on the Mac; formerly the Processing `command_sender_8`) strings commands into memory reads, writes, dumps and tests.

It is a *static* instrument: it sets levels and leaves them; there is no clock, no timing. That is enough to prove
decoding, storage and data paths (the memory card's block map, the ROM contents, the video RAM, the I/O card's UART
registers in 2020), and it is why some hazards that depend on edges (the memory card's M1 race) pass the tester and
would not pass the CPU.

```
   FTDI (JP1, 19200) <--> IC10 ATMEGA328P (16 MHz Q1) --I2C (SCL/SDA, R10/R12 2.2k)--+--> IC1 0x20  ADDR0..15   (A3..A18)  RN3/RN4 pull-ups
                              |  PB1..PB5: LED1..5 (error blink codes)                |--> IC2 0x21  DATA0..15   (A19..B6)  RN1/RN2 pull-ups
                              |  PC0/PC1: S-A, S-B switches; PC2: BUS-RESET button    |--> IC3 0x22  B7..B22
                              |  PC6: local -RESET (CPU-RESET button, R8)             |--> IC4 0x23  B23..C10
                              |                                                       |--> IC5 0x24  C11..C26
                              +--> IC7 24AA01 EEPROM 0x57 (JP2 write-protect)         +--> IC6 0x25  C27..C30 + OUT-LED, IN-SWITCH,
                                                                                                        LEDS-LD, SWITCHES-RD, BIT0..7
   BIT0..7 <--> IC8 74LS374 (LEDS-LD) --> L0..L7;  S0..S7 --> IC9 74LS244 (SWITCHES-RD) --> BIT0..7;  IN switch --> IC6 GPA5
```

## 2. Bus signals used

Every signal pin of the DIN 41612 connector is an expander GPIO — there is no buffer and no enable between the
MCP23017 and the bus (v1.1). The card's schematic names the nets by **connector pin** (A3, B23, C30 ...), and the
signal names live only in the firmware table `embedded/libraries/YACC/YACC_Common_header.h` (chip, port, pin per
name). The design review checked that all 52 bus entries of that table land on the DIN pin that carries the same
signal in the V3.2 pinout ("checked, no issue (bus tester)").

| Chip (I2C address) | Bus pins | Signals (V3.2 names) | Notes |
|---|---|---|---|
| IC1 (0x20: A0..A2 = GND) | A3..A18 | ADDR0..15 | pull-ups RN3 (A3..A10), RN4 (A11..A18), value empty |
| IC2 (0x21) | A19..A30, B3..B6 | DATA0..15 | pull-ups RN1, RN2 |
| IC3 (0x22) | B7..B22 | -REG-FUNC-RD, -REG-FUNC-LD, REG-RD-ID0..3, REG-LD-ID0..3, -REG-RD-LO, -REG-LD-LO, -REG-RD-HI, -REG-LD-HI, -REG-DN, -REG-UP | table chip 2 |
| IC4 (0x23) | B23..C10 | -MEM-RD, -MEM-WR, -IO-RD, -IO-WR, -TMP-REG-RD0/LD0/RD1/LD1, ADDR-REG-ID0..3, IOADDR0..3 | table chip 3 |
| IC5 (0x24) | C11..C26 | -IO-ADDR-LD, -VMA, -INT, -INTA, -ALU-FUNC, ALU0..3, -AC-LD-INV, -AC-RD, -AC-LD, -SR-LD, BR-COND, -HL-SWAP, IN | table chip 4; BR-COND, -INT and IN are the three the firmware leaves as inputs |
| IC6 (0x25) | C27..C30 | OUT, -BUS-EN, -RUN, -RESET | table chip 5 pins 0..3; GPA4..7 and GPB0..7 are the local lines |

The firmware's table entry `ACTIVE_LOW` convention: a name with a leading `-` is inverted by `setCntlPin()`, so
`-RESET:1#` drives C30 low. Address/data bus direction is a per-bus mode (`ADDRBUS-WR-MODE`, `DATABUS-RD-MODE` ...)
that switches all 16 expander pins between input and output at once.

Power: VCC and GND on the six connector pins each; the FTDI-VCC solder jumper can instead feed the card from the
cable (never with the card on a powered bus — `Build Notes.md`, and the review's 2.2 note).

## 3. Schematic walkthrough, IC by IC (v1.1)

Values from `tester.sch`/`tester.brd`: IC10 ATMEGA328P-PDIP with Q1 16 MHz and C6/C7 20 pF; IC1-IC6 MCP23017SP;
IC7 24AA01P; IC8 74LS374N; IC9 74LS244N; R10/R12 2.2k (I2C pull-ups); R2-R8, R25 10k; R1, R9, R11, R13-R24 330 Ω;
RN1-RN4 RNX8 (RN-9), value empty; C1-C5, C8-C13 0.1 µF.

### 3.1 The controller: IC10, Q1, JP1, the buttons and switches

The ATmega runs at 16 MHz from Q1 (the build notes: C6/C7 22 pF are packaged with the crystal, and an insulator goes
under it). Serial: PD0/PD1 to the FTDI header JP1 (RXI/TXO/VCC/GND/DTR/CTS). DTR-RESET is a solder jumper from the
FTDI's DTR to N$9, whose only other node is C10 — the auto-reset path dead-ends (review 2.2), so flashing uses the
CPU-RESET button; the 2026-09-21 flash went through arduino-cli "as an Uno at 115200 through the FTDI" (MACHINE.md).

Local reset: the net -RESET joins IC10's PC6 (/RESET), all six expanders' /RESET, the CPU-RESET button and the pull-
ups R2..R8; it does **not** reach the bus (the bus -RESET is IC6 GPA3 = C30). The build notes say R2-R7 need not be
fitted (R8 alone pulls the net up). BUS-RESET is a second momentary button on PC2 with R25 as pull-up; `bus-driver.ino`
does not read PC2 anywhere (no `digitalRead` of that pin), so as flashed it does nothing. S-A and S-B (`9070-1W`
slide switches) go to PC0/PC1 and are read as inputs (pins 14/15 in `setup()`); their use in the sketch is not
visible from the grep. **To verify:** what the current sketch does with S-A/S-B.

LED1..LED5 hang on PB5..PB1 (D13..D9) through R9/R11/R13/R14/R15. `doError()` prints `Error: ...` and then blinks
one of them forever (`BAD_OPCODE` 9, `BAD_PARAMTER` 10, `ADDR_BUS_MODE` 11, `DATA_BUS_MODE` 12 are Arduino pin
numbers: D9 = LED5 ... D12 = LED2); the card must then be reset. The 2026-09-21 block commands report errors without
halting.

### 3.2 The expanders: IC1-IC6, I2C

SCL/SDA are shared by the six MCP23017s and IC7 with R10/R12 (2.2k) pull-ups. Addresses come from A0..A2 straps:
IC1 000, IC2 001 (A0 = VCC), IC3 010, IC4 011, IC5 100, IC6 101 — matching `mcp[i].begin(i)`. Each expander's 16
GPIO lines go straight to DIN pins (or, on IC6, to the local lines). The firmware's `setup()` puts every pin in INPUT
with the 100k internal pull-up, then walks the signal table and makes each named control line an OUTPUT at its
inactive level (`HIGH` for `-` names, `LOW` otherwise), sets both buses to write mode, and finally returns BR-COND,
-INT and IN to inputs.

### 3.3 The local byte: IC8, IC9, S0-S7, L0-L7, IN, OUT

BIT0..7 is an 8-bit local bus on IC6's GPB. IC9 (74LS244, enable = SWITCHES-RD on IC6 GPA7) puts the eight toggle
switches S0..S7 (`M9040P`, VCC or GND) onto it; IC8 (74LS374, clock = LEDS-LD on IC6 GPA6, -OC = GND) latches it to
LEDs L0..L7 through R17..R24. `READ-SWITCHES` and `SET-LEDS` are the commands; the firmware sets SWITCHES-RD high at
setup and makes GPB inputs before pulling it low (`read_switches`), so the only possible fight is a firmware bug
(review). The IN switch drives IC6 GPA5 (IN-SWITCH), the OUT LED hangs on GPA4 (OUT-LED) through R16 — a copy of the
I/O card's front-panel pair for testing without the I/O card. The May-2020 rework "join R21 to R9 to GND, 8 LEDs"
(`Notes.md`) is on the PCB as a jumper and in the schematic as drawn.

### 3.4 The EEPROM: IC7 (24AA01), JP2

A 128-byte I2C EEPROM at 0x57 (A0..A2 = VCC) with WP on JP2 (1 = GND, 3 = VCC). `Build Notes.md` tests it with the
`mem` sketch; the bus-driver sketch does not use it.

### 3.5 Pull-ups: RN1-RN4

RN1..RN4 (common pin 1 = VCC) pull up all 32 address and data lines. Their value is empty in both files; the v3.1
notes say "Removing pull-ups of which currently are on Data and Address lines", so they were known to be a load. If
they are 1k, every bus driver sinks 5 mA per line (review 4.2). **To verify:** measure RN1 pin 1 to pin 2.

## 4. The serial protocol and the host tools

Wire protocol (`bus-driver.ino` header, `tools/busdrv.py` docstring, the PDF):

- Host to card: `COMMAND:OPERAND#` — operand **decimal** on the wire, no line ending (Arduino monitor set to "No
  Line Ending"). `1` = on (asserted), `0` = off; the firmware inverts `-` names.
- Card to host: optional `Data: n` (decimal) then `Complete`, then the prompt `>>`. Since 2026-09-21 the firmware
  prints the banner `bus-driver blocks-1 2026-09-21` before its first prompt; `busdrv.py` looks for `blocks-` in it.
- Control lines: any name from the table (`-MEM-RD:1#`, `IOADDR0:1#`, `-VMA:1#` ...).
- Buses: `WR-ADDRBUS:n#`, `RD-ADDRBUS`, `WR-DATABUS:n#`, `RD-DATABUS` (16 bits), `RD-DATABUS-L`, `RD-DATABUS-H`,
  and the direction modes `ADDRBUS-RD-MODE`, `ADDRBUS-WR-MODE`, `DATABUS-RD-MODE`, `DATABUS-WR-MODE` (a write to a bus
  in read mode is refused with `Error: ... Bus Mode is READ` and, on the old firmware, a halt).
- Inputs: `RBR-COND`, `RD-IN`; local: `READ-SWITCHES`, `SET-LEDS:n#`.
- Blocks (2026-09-21): `RDBLK:addr,count#` (1..64 bytes back as `Data: hh hh ...`) and `WRBLK:addr,count,hh...#`
  (1..32 bytes); one round trip instead of four per byte (~0.16 s per byte at 19200 was mostly USB latency); the card
  switches the data-bus direction itself; -VMA, -BUS-EN and ADDRBUS-WR-MODE remain the caller's job.

The script language of the Processing sender (the PDF `BUS Driver Commands`): `//` comments, `:label` and `GOTO`,
`LET V=n`, `FOR V=start,end,step` / `NEXT V`, `WAIT`, `DUMP:start-end#`, `DUMPVARS`, `DUMPLABELS`, and
`CMD:OP#EXPECTED!VAR` (compare the returned value, store it). `Vname` as an operand substitutes a variable. Hex in the
scripts, decimal on the wire. `BACKLOG.md` wants these features in `busdrv.py` so the Processing sender can retire.

The memory idiom every test uses (`busdrv.py` `readmem`/`writemem`):

```
-RESET:1#  -RESET:0#          pulse reset (FORCE-ROM set on the memory card)
-BUS-EN:1#  -VMA:1#           enable the bus, valid address
ADDRBUS-WR-MODE:1#  DATABUS-RD-MODE:1#
WR-ADDRBUS:F000#  -MEM-RD:1#  RD-DATABUS-L  -MEM-RD:0#      read (and this first read releases FORCE-ROM)
DATABUS-WR-MODE:1#  WR-ADDRBUS:a#  WR-DATABUS:v#  -MEM-WR:1#  -MEM-WR:0#   write
```

What **-BUS-EN** does here: the tester asserts C28 so that the cards that gate their bus drivers with it (the memory
card's FORCE-ROM clock and, through JP1, its decoder; the register cards' address buffers; the ALU's transceivers)
behave as they would with the sequencer READY. Conversely, holding -BUS-EN high is meant to silence the sequencer's
pipeline — but see section 5: the sequencer generates -BUS-EN itself and drives 17 lines regardless of it.

Host scripts: `tools/busdrv.py` (`BusDriver` class: `cmd`, `pulse`, `readmem`, `writemem`, `read_block`,
`write_block`, `dump`; retries on a reply timeout and survives the USB port vanishing, reopening it and re-running
the caller's setup), `tools/alias_min.py`, `tests/memory/{memory_status,rom_verify,memory_full_test}.py`,
`tests/video/{video_ram_test,hold_address}.py`. The port is `/dev/cu.usbserial-AB6WZCQX` (`busdrv.py` `PORT`);
opening it resets the card, which is why `hold_address.py` keeps it open.

## 5. Timing and the design-review findings

The tester has no timing of its own; its findings are about *contention*.

| ID | Severity | Finding | Status 2026-09-23 |
|---|---|---|---|
| 4.1 / 1.1 (`DESIGN-REVIEW-NOTES-control-io.md`) | HIGH | nothing on the card can make the expanders passive: from `setup()` every table line is a push-pull output, including -RESET (C30), -BUS-EN (C28), -RUN, OUT and the register-card ID/strobe lines. The sequencer-logic card drives 17 of those lines regardless of -BUS-EN (IC4/IC5/IC18 select buffers, -REG-LD-LO/HI, -RESET, OUT, -BUS-EN itself). Two totem-pole drivers per line; an LS output high into an MCP23017 output low (25 mA absolute maximum per pin) can kill the expander pin. This is why "the tester cannot load RAM with the logic card fitted" | Open. Rule today: **unplug the sequencer-logic card before using the tester**, or use the ROM monitor over the UART. The planned fix is the sequencer v2.2 "CPU off" switch covering all 17 lines plus an open-collector -BUS-EN driver (BACKLOG) |
| 4.2 | LOW | RN1-RN4 pull up all 32 address/data lines, value unrecorded | Open (section 3.5) |
| 2.2 | LOW | DTR auto-reset dead-ends (N$9 single node); FTDI-VCC would parallel the FTDI 5 V with the rail | Housekeeping |
| 5.1 | LOW | no pull-ups on the backplane: when the tester tri-states a bus, the lines float | By convention |
| checked | — | signal table vs wiring vs V3.2 pinout 52/52; local reset does not reach C30; switch/LED port fight-free; I2C addresses distinct | — |

A subtlety worth knowing when interpreting results: the tester drives the address **before** it lowers -VMA and
holds it after, so the memory card's FORCE-ROM race (M1 in `docs/cards/memory.md`) never shows here; and a read of
an undecoded address returns the last value the bus held, so "reads back what I wrote" is only proof after other
traffic (`tests/video/video_ram_test.py`'s ordering).

## 6. Jumpers, switches, LEDs, connectors

| Item | Meaning | Setting |
|---|---|---|
| JP1 FTDI header (GRN..BLK: GND, CTS, VCC, TXO, RXI, DTR) | the console, 19200 | the Mac's FTDI cable, port `usbserial-AB6WZCQX` |
| FTDI-VCC (solder jumper) | power the card from the cable | **open** when on the bus (`Build Notes.md`) |
| DTR-RESET (solder jumper) | intended auto-reset on port open | dead-ends (2.2); irrelevant |
| JP2 (1x3) | IC7 write protect: 1 GND (WP low = writable), 3 VCC | **To verify** |
| CPU-RESET button | resets the ATmega and the six expanders (local) | — |
| BUS-RESET button | PC2 input, not read by the sketch | — |
| S-A, S-B | PC0/PC1 inputs | — |
| S0-S7, IN toggles; L0-L7, OUT, LED1-5, PWR | the local byte, the IN copy, the error/status LEDs, power | — |
| RN1-RN4 | address/data pull-ups | fitted, value unknown |
| X1 DIN 41612 | any slot; the card was in for the 2026-09-18/21 sessions and is "plugged in for bring-up sessions" (MACHINE.md) | — |

Firmware in the chip: `embedded/bus-tester/bus-driver` **blocks-1 (2026-09-21)**; before the flash it held the 2020
bus-driver (same strings and table, older toolchain), read out to `embedded/bus-tester/readback/`. The other sketches
(`bus-monitor` listens and reports changes, `bus-test` checks for shorts, `led-switch-test`, the EEPROM `mem` test)
are loaded one at a time when needed; `tools/verify_embedded.py` compiles all of them against the vendored
`embedded/libraries/` (Adafruit_MCP23017 1.1.0).

## 7. Bring-up and test

Building and proving the card itself (`eagle/v1.1/Build Notes.md`): power check on the connector's six GND and six
VCC pins; ICs in height order; the ATmega with Blink first; IC7 with the `mem` sketch; IC8/IC9 with
`led-switch-test` (reads the switches, adds one, shows it on the LEDs); the rest, then `bus-test` for shorts.

Proving other cards with it: the `Memory Card Tests` scripts (2020), the IO scripts (UART init byte by byte), the ALU
and Index Register scripts (2020 signal names; the `Gen Test Vectors` generator still emits 2016 names and needs a
rewrite — `tests/bus-tester-scripts/README.md`, BACKLOG), and the 2026 Python tests:

| Test | What it proves | Result |
|---|---|---|
| `tests/memory/memory_status.py` | FORCE-ROM, ROM bytes, low RAM spots, the 4K block map | expected map confirmed 2026-09-18 (MACHINE.md) |
| `tests/memory/rom_verify.py` | the 28C64 against `basic.img` + `monitor.img` | identical to the 2021 build on 2026-09-18; differs from the 2026-09-22 rebuild until reburned |
| `tests/memory/memory_full_test.py` | address lines, two RAM sweeps over 53,248 cells, video RAM, ROM again | 14/14 on 2026-09-21 (~16 min with blocks-1; the earlier per-byte firmware was ~10 h) |
| `tests/video/video_ram_test.py` | the video card's display RAM | 8/8 on 2026-09-21 after the rail wire |
| `tests/video/hold_address.py` | a meter on decode pins | tool for the RS fix |

If the tester misbehaves: a blinking LED1-5 after an error is the halted old-style `doError()` — power-cycle or
CPU-RESET; a port that vanishes mid-run is the USB link (the 2026-09-21 attempt-1 log: "linkdrop"), which
`busdrv.py` now rides out; `Error: Addr Bus Mode is READ` means the mode commands were skipped after a reset (the
card resets when the port opens, so re-send the setup — `memory_full_test.py`'s `on_reopen`).

## 8. Revision history and the v3.1 redesign

| Rev | Date | Status | Notes |
|---|---|---|---|
| V1.0 / V1.1 (gen-1, `TESTER-PROD-V1.1`) | 2016; board dated 2018-03-15 | **in use** | gerbers in `fab/` identical to the 2016 ones; schematic re-saved 2020-08-15; May-2020 rework (R21/R9 to GND for the eight LEDs). `media/test board v1.1 top.jpeg`, `solder.jpeg` |
| V3.1 | 2020-07-15 | routed, CAM run, **never ordered** | see below |
| V3.11 | 2020-07-16 | unrouted reshape to 243 x 114 mm | folded into v3.1's folder |

**What v3.1 changes** (`eagle/v3.1/tester.sch`, parsed): the six expanders stay, but their outputs no longer touch
the bus. Eleven 74LS373 transparent latches (IC11-IC21) sit between expander pins (`BUF-A3` ... `BUF-C30` nets) and
the DIN pins, and all eleven output enables are one net, **-BUF-EN**, driven by the ATmega's PD7. So the firmware can
take the whole card off the bus with one pin — the answer to finding 4.1, designed six years before the review
wrote it down. Two 1x3 headers add **-SOFT-BUS-EN** (PD5 to the `-BUS-EN` header, pin 2 = C28) and **-SOFT-RESET**
(PD6 to the `-RESET` header, pin 2 = C30), so -BUS-EN and -RESET can be driven from the ATmega directly instead of
through an expander, or left to the header. The BUS-RESET button becomes SOFT-RESET on PC2; the CPU-RESET button
stays local. Bypass capacitors were added (C14-C24), the pull-ups RN1-RN4 remain in the drawing (the notes wanted
them gone), and the V3.11 notes add "bypass cap for ATmega" and "should IN/INT support read mode, reportable
through the CLI". Because the 373s are one-way (D from the expander, Q to the bus), reading a bus line back would
need the expander pin on the bus side — v3.1 keeps that only for the lines that stay direct; **To verify** from the
v3.1 board which lines (BR-COND, -INT, IN) remain readable.

Decision pending (`BACKLOG.md`): build v3.1 (with the 2020 pull-up removal and the review's notes) or keep v1.1 for
good and rely on the sequencer v2.2 "CPU off" switch. Either way the firmware needs `-BUF-EN`/soft-reset support
that `bus-driver.ino` does not have today, and the `bus-driver-mcp23x17-wip` port to the Adafruit 2.x library is
two lines in.
