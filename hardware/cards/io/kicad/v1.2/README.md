# I/O card V1.2 - the circuit, the schematic, the routed board

**Designed and routed 2026-11-18; settled as drawn 2026-11-19 (four layers, 218 mm, the panel's arrangement, the
labels); that day's two changes to the silkscreen: a `+` at the cell's holder, and five labels moved. Not ordered.**
The V1.1 card in the machine (`../../eagle/v1.1`, built 2020-11-29)
with what `docs/cards/io.md` section 8 lists for a next revision: a data buffer between the bus and the card, a DS12885
real-time clock on ports 6 and 7, a TTL serial header, the DB9 at the top edge with the panel under it. **To software
it is the V1.1 card**: the ROM in the machine runs on it unchanged. `io12_netlist.py` is the card's circuit (parts,
nets, the pins left open); `gen_io12.py` draws the schematic and places the board from it; `build.sh` routes, reports
and checks. The theory of the card is `docs/cards/io.md`; the clock's note is `docs/cards/rtc.md`.

V1.1 is not changed by any of this: its files, and the card in the machine, are as they were.

## What V1.2 is, beside V1.1

| | V1.1 | V1.2 |
|---|---|---|
| Ports, control latch, UART | P0 control, P1 data; bits 0 SWITCHLED, 1 LCDENABLE, 2 LCDREGISTER, 3-5 the UART's register, 6 UARTCS, 7 TIL311 | the same, pin for pin (`io12_netlist.py`'s `v11_check()` compares every connection with the built card's board file) |
| Data lines | every device on the bus's DATA0-7 | IC12, a 74LS245: the bus on one side, the card's ID0-7 on the other. Towards the card except in a read; enabled while one of the card's four ports is addressed (IC13). RN2 holds ID0-7 high while it is off |
| Port decode | IC5's G2B on GND | on JP10: GND (as V1.1) or -BUS-EN. The bus tester drives the card with -BUS-EN high (`tests/io/io_test.py`), so it needs JP10 on GND |
| Clock | none | IC15, a DS12885+ with a 32.768 kHz crystal (6 pF) and a CR2032: port 6 the register number, port 7 its data. -IRQ to -INT through JP8; JP9 clears its RAM |
| Serial | the DB9 behind the MAX232 | the same, and J2, a TTL-level header with an FTDI cable's pins; JP2 picks where the UART's RX comes from |
| -INT | the INT header before IC8/F: open, the gate's input floats high and the gate holds -INT low | the UART's INT straight to IC8/F; JP7 between the gate's output and the bus: off, the card never touches -INT |
| The DB9 | at the side edge | at the top edge (the edge opposite the bus connector), its face on the board's edge, the D off the card |
| Small things | | the oscillator's pin 1 on +5 V; R11 in series with the LCD's backlight; the MAX232's unused inputs tied off; the DB9's shell on GND; pull-ups on the two port-select lines; every resistor's value written down (RN1 2.2k, RN2 10k, R1-R10 330) |
| Board | 177.8 x 114.0 mm, two layers, drawn in Eagle | 218.0 x 114.0 mm (every long card's length), four layers (GND and VCC planes), generated |

The device bits stay four flags, as on V1.1: a decoder in their place would change what the ROM writes to P0. The
rule that software sets one of them at a time stands (`docs/cards/io.md` 4.5). -IO-ADDR-LD is open, as on V1.1.

**The references.** V1.1's parts keep their numbers where they had one (IC1-IC11, R1-R10, C1-C4, J1, JP1, X1); the
parts that Eagle had named by their function have a reference here:

| V1.1 | V1.2 | | V1.1 | V1.2 |
|---|---|---|---|---|
| UNK0-UNK7 (the LEDs) | LED0-LED7 | | HI0, LO0 (TIL311) | DS1, DS2 |
| OUT0, PWR0 | LED8, LED9 | | X2 (LCD) | DS3 |
| S0-S7, IN0 | S0-S7, S8 | | TM1 | RV1 |
| Y1 (the oscillator can) | OSC1 | | RN2 | RN1 |
| IO-ADDR-HL0 | JP3 | | IO-ADDR0, DATA-ADDR0 | JP4, JP5 |
| INPUT0 | JP6 | | INT0 | JP7 (now behind IC8/F) |
| C5-C17 (decoupling) | C6-C21 (C5: bulk) | | | |

New: IC12 (74LS245), IC13 (74LS08), IC14 (74LS32), IC15 (DS12885+), Y1 (the crystal), BT1, RN2, R11, R12, J2, JP2,
JP8, JP9, JP10.

## The jumpers

Pin 1 of each block is the pin nearest the bus connector, or the left one with the card standing. The silkscreen has
each position's meaning beside it.

| | What | In the machine |
|---|---|---|
| JP3 HALF (2x3) | which eight ports IC5 decodes: 3-5 and 4-6 = P0-P7 (IO-ADDR3 low); 1-3 and 2-4 = P8-PF | 3-5, 4-6 |
| JP4 CTL PORT (2x8) | one jumper: the control port. 15-16 = port 0 ... 1-2 = port 7 | 15-16 (P0) |
| JP5 DATA PORT (2x8) | one jumper: the data port | 13-14 (P1) |
| JP10 DECODE (1x3) | 1-2: the ports decoded always, as on V1.1. 2-3: only while -BUS-EN is low | 1-2 (the bus tester needs it there) |
| JP1 TX PIN (2x3) | the null-modem block: 1-3 and 2-4 = the card sends on the DB9's pin 2 (a straight cable to a PC); 3-5 and 4-6 = on pin 3 | as V1.1's JP1 |
| JP2 RX FROM (1x3) | 1-2: the UART hears the DB9; 2-3: the TTL header J2 | 1-2 |
| JP6 IN-EN (1x2) | fitted: the IN switch drives the bus line IN | fitted |
| JP7 UART INT (1x2) | fitted: the UART's INT drives -INT | open |
| JP8 RTC INT (1x2) | fitted: the clock chip's -IRQ drives -INT | open |
| JP9 RAM CLR (1x2) | fitted for a moment with the power off: the clock chip's 114 bytes of RAM are cleared (never the clock) | open |

Ports 6 and 7 are the clock's: the control and the data port must not be set there.

## The circuit's own checks

`python3 io12_netlist.py` (in `make check`): 89 parts, 15 ICs, 129 nets.

- `check()`: every pin on a net or listed as open, no pin on two nets, no net with one pin, no two outputs on a net,
  an output on every net of ICs, a capacitor for every IC.
- `v11_check()`: the built V1.1 card's nets are read from its board file (`../v1.1/io-v1.1.kicad_pcb`) under V1.2's
  references; the pins of each V1.1 net must all be on one V1.2 net, except the pins on the list of intended
  changes (`V11_CHANGED`: the bus's data pins, now behind the buffer; the INT jumper; the UART's RX, now through JP2;
  the backlight, now through R11; the spare gate that is AS's inverter; IC5's G2B; the decoupling capacitors,
  numbered anew).

## The schematic

`gen_io12.py sch` (KiCad's Python; node and elkjs in `tools/kicad`) draws `io-v1.2.kicad_sch`, the root, and six
sheets. KiCad's own netlist of it equals `io12_netlist.py` net for net (129 nets), and its electrical rules check
finds nothing (`reports/netlist.net`, `reports/erc.json`, `reports/io-v1.2-schematic.pdf`).

| Sheet | What is on it |
|---|---|
| 2 Bus and ports | the bus connector, the data buffer and its enable, the port decode and its jumpers, the open-collector strobes, the control latch |
| 3 UART | the 16550, its oscillator, the MAX232, the null-modem block and the DB9, the TTL header, the UART's -INT |
| 4 Panel | the switches and their buffer, the LEDs and their latch, the TIL311s and their latch, IN and OUT |
| 5 LCD | the LCD module, its strobe, the contrast trimmer, the backlight's resistor |
| 6 Clock | the DS12885, its strobes, the crystal, the cell, the two jumpers |
| 7 Power | the power units, the decoupling capacitors, the power LED, the spare gates |

Local symbols (`io-v1.2-local.kicad_sym`): the DS12885, the TIL311, the LCD module.

## The board: 218 mm, placed and routed

Four layers: signals on the front and the back, In1.Cu a GND plane, In2.Cu a VCC plane. 89 parts.

**The footprints of the parts whose fit matters are the built V1.1 card's own** (`../v1.1/io-v1.1-eagle.pretty`),
copied into `io-v1.2-local.pretty` with a body outline and a courtyard: the DB9 (pin rows 2.84 mm apart, 10.17 mm
behind the board's edge, mounting holes 25.0 mm apart: the D reaches 5.6 mm past the edge), the M9040P toggle (three
pads 4.70 mm apart, 1.80 mm holes), the TIL311, the LCD module (80 x 36 mm, 16 pins in a row, four 2.8 mm holes) and
the trimmer. The DIPs, the resistors, the capacitors (2.5 mm leads), the headers, the LEDs, the oscillator can
(half-size, 8-pin DIP), the crystal and the cell's holder (Keystone 103) are KiCad's.

**The placement**, with the card standing in the backplane (the bus connector down, the front edge up; as drawn the
bus connector is on the left and the front edge on the right):

- **At the top edge**: the eight LEDs, bit 7 at the left, then OUT and PWR, each with its resistor under it; at the
  right the DB9, its face on the edge: the console cable plugs straight down into it.
- **Under them**: the eight switches, bit 7 at the left, 10.16 mm apart as on V1.1, up = 1; under the DB9 the IN
  switch, with the null-modem block (JP1) and JP2 between it and the DB9; the TTL header (J2) and JP6 along the right
  side edge.
- **Then** the LCD, upright, its pins along its upper edge, and at its right the two TIL311s, HI then LO.
- **Below the panel** the ICs in columns: by the LCD the panel's three (the switch buffer, the LED latch, the TIL311
  latch); the cell; the MAX232 with its four capacitors and the UART's oscillator; the UART beside the clock chip
  (turned round: its crystal pins towards the free channel); the control latch and the gates; and by the bus
  connector the buffer, the port decode and the strobes. The port jumpers, the pull-ups and the three jumpers of
  -INT and of the clock's RAM are along the right side edge.

Every silkscreen text reads upright with the card standing (KiCad angle 270); the board's name and
`cottageworker.com` run up the left side edge. Each switch has its reference and bit over it, a 1 above and a 0
under it; each LED its reference and bit; each jumper block its positions.

**The cell's `+`** (2026-11-19) stands just under the holder's positive pin (BT1 pin 1, VBAT), past the end of the
holder: the line under it reads `BT1 CR2032 +`. The footprint's own `+` is printed inside the holder's outline,
between the pin and the cell, and is covered once the holder is fitted; this one stays in sight. Its place is
narrow: the silkscreen placer and pcb-check both take the holder's body as the box round its drawing, so the bare
board beside the holder's neck counts as under it (a `+` there is moved out and pushes `BT1` and `CR2032` 5 mm
along), and a `+` a quarter of a millimetre nearer the bus connector pushes JP9's two labels away. It is 1.2 mm high
(the labels beside it 1.0).

**Five labels are given their place** (`LABEL_AT` in `gen_io12.py`, 2026-11-19). The placer keeps two texts 0.15 mm
apart and knows nothing of what they say; on the 1:1 print three places read as one label although nothing
overlapped. Each of these stands where the table puts it, before the placer places the rest (a place that is not
clear is named by the build):

| Label | It read as | Where it stands now |
|---|---|---|
| `C20 100n` (IC15's capacitor) | `C20 100nCTL PORT`: its value ended 0.33 mm before JP4's name on the same line | 1.4 mm towards C19, as far as C19's outline lets it go |
| `JP4` / `CTL PORT` | the same | a line higher, off the capacitor's line: 1.7 mm along from `100n` and a line above it |
| `RN2` / `10k x8` | `RN2 ALWAYS` over `10k x8 JP10`, in among JP10's two positions and its name | beside the network's top end, 4.6 mm above JP10's `-BUS-EN` |
| `DS1` / `TIL311 HI` | `TIL311 HI 0`: its second line stood in the row of the switches' 0s, 2.6 mm from S8's | under the display, on two lines |
| `DS2` / `TIL311 LO` | (one line under its display) | under the display, on two lines, as DS1's: the pair reads alike |

**The crystal** (`gen_io12.py xtal`, before the router): Y1 stands beside the clock chip's pins 2 and 3; its two
tracks, 2.8 mm each on the front, are drawn and locked, and keepouts hold every other track and via off the back
under them and off the front round them. The GND plane is whole under them.

**The routing** (`build.sh`, 2026-11-18): Freerouting on the two outer layers, GND and VCC as planes. All 245
connections, 69 vias, 10.8 m of 0.25 mm track. Each of four component orders routed every connection (75 s of
running time for the four); the one with the fewest vias is kept.

**The checks, all passing** (`build.sh: ALL CHECKS PASS`): KiCad's netlist of the schematic equal to
`io12_netlist.py`; ERC nothing; DRC no unconnected item, no copper violation, schematic parity 0 (29 silkscreen
warnings: the bus connector's own silk at the edge, and silk of the V1.1 footprints that crosses their pads, which
the fab clips); the board's nets equal to the schematic's (`reports/netlist-compare.txt`: MATCH); the placement clear
(89 footprints, 16 sockets); 279 key connections right in the schematic and on the pads; each plane one piece.

| | |
|---|---|
| `gen_io12.py sch` | the local libraries and the schematic |
| `gen_io12.py project` | `io-v1.2.kicad_pro` and `.kicad_dru`: 0.25 mm tracks, 0.2 mm clearance, GND and VCC as planes |
| `gen_io12.py checknet reports/netlist.net` | KiCad's netlist of the schematic against `io12_netlist.py` |
| `gen_io12.py board reports/netlist.net <out.kicad_pcb>` | the unrouted board: every part placed, every pad on its net, the silkscreen placed |
| `gen_io12.py place <pcb>` | courtyards apart, everything inside the outline, the DIP sockets clear of each other and of the other parts |
| `gen_io12.py xtal <unrouted.kicad_pcb> <out.kicad_pcb>` | the crystal's two tracks, locked, and the keepouts round them |
| `gen_io12.py verify reports/netlist.net <pcb>` | 279 key connections pin by pin, in the schematic and on the board; the layers; the planes |
| `gen_io12.py drawing <pcb>` | `io-v1.2-placement.pdf` |
| `gen_io12.py geom <pcb> <out.json>`, then `python3 print_1to1.py <out.json> io-v1.2-1to1.pdf` | the 1:1 check print (below): KiCad's Python reads the board, the system python3 (reportlab) draws the sheet |
| `gen_io12.py bom` | `BOM.md` |
| `gen_io12.py fab <pcb>` | the order's files: `gerbers/` and `io-v1.2-gerbers.zip`. It orders nothing |
| `build.sh` | all of it, with the routing, the reports, the checks and, when they pass, the order's files (about two minutes) |
| `SILK=1 build.sh` | the routed board kept: its silkscreen texts written and placed afresh, then the reports, the checks and the order's files |
| `PADS=1 build.sh` | the routed board kept through a change of the netlist that only ties open pins to GND or VCC (`gen_io12.py padnets`) |

`gen_io12.py` is made from the video card V4.0's generator (`../../../video/kicad/v4.0/gen_v40.py`): the sheet
writer's use, the silkscreen placer, the planes and the checks are its code.

## The 1:1 check print

`io-v1.2-1to1.pdf` (2026-11-19; `build.sh` makes it on every build): one US Letter sheet, portrait, with the board at
1:1, component side up, as the card stands in the backplane - X1 at the bottom, the front edge at the top, so the
silkscreen reads upright. **Print it at 100 % ("Actual size", not "Fit") and measure its two 100 mm bars, one across
and one down, before laying anything on it.**

- Black is the silkscreen as the board has it: KiCad's own outlines of every text and line, so the labels are seen
  at their real size.
- Grey is each pad, with its hole at the drilled size in white (a cross in the holes of 1.5 mm and more).
- Blue is the parts' bodies (the Fab layer's lines): the DB9's D past the front edge, the LCD module, the cell's
  holder.
- Yellow marks the five parts to lay on it, numbered. Every pin must stand in a white hole and the body inside its
  blue outline.

Beside the board the sheet lists what the board has for each of the five, measured by `print_1to1.py` from the pads
and the bodies, to hold against the part or its data sheet:

| | Part | On the board |
|---|---|---|
| 1 | J1, the DB9 socket (right angle) | 9 pins in two rows 2.84 mm apart, 2.77 mm from pin to pin, holes 1.02 mm; mounting holes 25.00 mm apart, 3.30 mm, their line 10.17 mm inside the front edge; the body 5.6 mm beyond the edge |
| 2 | S0-S8, the M9040P toggle | three lugs 4.70 mm apart, holes 1.80 mm, pads 2.71 x 5.41 mm; switch to switch 10.16 mm |
| 3 | DS1, DS2, the TIL311 | 11 pins of 14 (no pin 6, 9, 11), rows 7.62 mm apart, 2.54 mm from pin to pin, holes 0.81 mm |
| 4 | DS3, the LCD module | 16 pins in a row 2.54 mm apart, holes 0.80 mm; four mounting holes 2.80 mm, not plated, 74.92 x 30.92 mm apart; pin 1 is 5.46 mm from the nearest of them; the module 80.0 x 36.0 mm |
| 5 | BT1, the CR2032 holder (Keystone 103) | two pins 20.49 mm apart, holes 1.50 mm; + is pin 1, the square pad |

The foot of the sheet carries the first 16 digits of the board file's SHA-256 (compare them with
`shasum -a 256 io-v1.2.kicad_pcb`), so a sheet of paper can be matched to the board it was made from. Two earlier
sheets were made on 2026-11-19: `b1cadcebf2c9a4bf` is the board before the `+` at the cell's holder,
`7612b5bdf44d3f79` the board with it and before the five labels moved. The same board gives the same PDF, byte for
byte.

Seen on the first sheet, 2026-11-19, three places where two labels read as one although none overlapped:
`C20 100n` ran into JP4's `CTL PORT`; RN2's `RN2` and `10k x8` stood against JP10's `ALWAYS` and `JP10`; S8's `0`
stood beside DS1's `TIL311 HI`. Moved the same day ("Five labels are given their place", above).

## The pre-order check

`~/Developer/pcb-check/pcb-check io-v1.2.kicad_pcb io-v1.2-gerbers.zip --layers 4`, with the settings in
`pcb-check.ini` beside the board. The order's files are `gerbers/` and `io-v1.2-gerbers.zip`. **Nothing is ordered**:
the card is row 11 of pcb-check's `orders/next-order.md`.

2026-11-18, without `--tests`: **no failures.** The four copper layers, 700 plated holes and 631 pads rebuilt from
the gerbers give the schematic's 129 nets with no short and no open; each plane is one piece; the bus connector's 96
pins are the Bus Template V3.2's; no input is left open; every reference and value is on the silk clear of the
parts; the panel parts are at the front edge.

| | |
|---|---|
| WARN, FOOTPRINTS | the DS12885+ is not in pcb-check's table of chips, so its footprint is not compared with the part (as on System-5's IO panel). It is KiCad's `DIP-24_W15.24mm` |
| NOTE, DESIGN | RTC-IRQ# and UINT# are open-collector lines with no pull-up of their own: each ends at its jumper (JP8, JP7), and the pull-up, RN1 on -INT, stands on the other side of it |
| NOTE, LABELS (pcb-check `7e47352` and later) | BT1's own `+` is printed inside the holder and hidden once it is fitted. It is the library footprint's mark and is left there; the `+` under the positive pin is the one that shows |

The same evening, with `--tests` (the tree's `make && make check`, 18 minutes) on the committed board, commit
`9c96b2e`: **no failures**, the same one warning.

**2026-11-19, the `+` at the cell's holder.** pcb-check `7e47352` holds every silkscreen text to the rule that it
shows with the parts fitted, and notes that the holder's own `+` does not. The mark added for it (`SILK=1 build.sh`)
is the board's one new text: the other 651 texts, the 89 parts, their 637 pads, the 1644 tracks and vias and the
planes are as they were, and of the order's fourteen files only the front silkscreen differs, by the mark's two
strokes (9564 shapes before, the same 9564 and two more after; the other thirteen files differ in their date lines
alone). pcb-check without `--tests` on that board: **no failures**; its two notes are in the table.

**2026-11-19, the five labels moved** (`LABEL_AT`, `SILK=1 build.sh`): ten texts, the five references and what
stands with each. The other 642 texts, the parts, pads, tracks, vias and planes are as they were; of the order's
fourteen files only the front silkscreen differs, and in it the 413 strokes of those ten texts, each gone from the
text's old place and drawn at its new one (9566 shapes before and after, 9153 of them untouched). pcb-check
`f93259d` without `--tests` on that board: **no failures**, the same warning and notes. **The check with `--tests`
is to be run again on the committed board.**

**Settled 2026-11-19: the board stays as drawn and checked.** Four layers; the 218 mm length; the panel's
arrangement (the DB9 and the LEDs at the top edge, the switches, the LCD and the TIL311s under them); the labels,
each reference with its function (`S7 BIT 7`, `LED8 OUT`), as the board-layout rules have it.

## Next

1. Before any order: the check's four pictures of the copper and the zip in the fab's gerber viewer, by eye; the
   DB9, a toggle, a TIL311, the LCD module and the cell's holder laid on the 1:1 print (`io-v1.2-1to1.pdf`, above).
   `pcb-check --tests` again if the board changes.
2. To verify on the V1.1 card in the machine: whether its INT header is fitted and what -INT reads (above); the
   frequency on its oscillator can (1.8432 MHz is what the monitor's divisor says); the fitted values of RN2 and
   R3-R10, for the record.
3. The clock's software: `docs/cards/rtc.md` section 6 (a model in the emulators, `/bin/date`, Kermit's timeouts,
   file dates).
