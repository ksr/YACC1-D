# Backplane V2.0, bus template, blank card and jumper boards — theory of operation

The bus itself: the eight-slot DIN 41612 backplane, the schematic template that defines the 96-pin signal
assignment (Bus V3.2), the blank card that new designs start from, the two obsolete bus-jumper boards, and the
mechanical bits.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/bus/backplane/eagle/v2.0/yacc2buss.sch` and `.brd` (parts and nets parsed from the Eagle XML),
`hardware/bus/backplane/README.md`, `hardware/bus/bus-template/eagle/v3.2/Bus Template V3.2.sch` (the canonical
signal table), `hardware/bus/bus-template/README.md`, `hardware/bus/blank-card/eagle/v3.1/Blank V3.1.sch` and
`eagle/v3.2/Blank V3.2.sch` (compared), `hardware/bus/blank-card/README.md`, `eagle/v3.1/Notes.md`,
`eagle/v3.2/README.md`, `hardware/bus/bus-jumper-horizontal/eagle/v3.2/Jumper Board Horizontal V3.1.sch`,
`hardware/bus/bus-jumper-horizontal/README.md`, `eagle/v3.2/Notes.md`, `hardware/bus/bus-jumper-vertical/README.md`,
`hardware/bus/README.md`, `hardware/mechanical/README.md`, `docs/system/connector/README.md`,
`hardware/cards/address-tmp/README.md` via `hardware/FABRICATED.md`, `firmware/microcode/yaccsignaldata2.h`,
`embedded/libraries/YACC/YACC_Common_header.h`, `hardware/DESIGN-REVIEW.md`,
`hardware/DESIGN-REVIEW-NOTES-control-io.md` (1.1, 1.8, 4.1, 5, cross-card notes),
`hardware/DESIGN-REVIEW-NOTES-datapath.md` (M5/S3), `docs/isa/MICROCODE-REVIEW-NOTES.md` (1.1, 1.2),
`docs/system/MACHINE.md`, `hardware/FABRICATED.md`, `BACKLOG.md`, `docs/procedures/System Build Notes.md`.

## 1. Purpose and place in the machine

Every card of the YACC1 is a 96-pin DIN 41612 plug-in; the backplane is eight sockets wired pin-for-pin in
parallel plus power. There is no logic on it: no termination, no pull-ups, no arbitration. What makes it a *bus*
rather than a ribbon cable is the convention the cards share — which pin carries which signal (the template), which
card drives it and when (the sequencer's pipeline for the control lines, the register cards for the address bus,
whoever is strobed for the data bus), and the active-low naming (a leading `-`).

```
   +5V, GND wire pads --> C1..C8 bulk electrolytics, PWR LED --> six VCC + six GND pins of each slot
   X1 ... X8  FABC96S sockets: rows a, b, c x 32 pins; 84 signal pins in parallel (SIG0..SIG83 in the drawing)
       |         |         |         |         |         |         |         |
     card      card      card      card      card      card      card      card      (slot assignment: not recorded)
```

## 2. The bus: the Bus V3.2 signal table

`hardware/bus/bus-template/eagle/v3.2/Bus Template V3.2.sch` (2020-11-29) is the canonical assignment; the
machine-readable copies are `firmware/microcode/yaccsignaldata2.h` (what the sequencer's control word drives) and
`embedded/libraries/YACC/YACC_Common_header.h` (what the bus tester drives). The PDF is
`docs/system/connector/YACC1 Connector - V3.2.pdf` (2020-09-10). Direction is from the sequencer's point of view
except where noted; "pipeline" means a 74LS374 output on the sequencer-logic card whose output enable is -BUS-EN
(`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1).

Row a (address and data):

| Pin | Signal | Driven by | Notes |
|---|---|---|---|
| a1, a32 | GND | backplane | with b1, b32, c1, c32 |
| a2, a31 | VCC | backplane | with b2, b31, c2, c31 |
| a3..a18 | ADDR0..15 | the index register selected by ADDR-REG-ID0..3, while -VMA is asserted (register card 74LS244s) | floats between cycles; the bus tester in ADDRBUS-WR-MODE |
| a19..a30 | DATA0..11 | memory (DATA0..7 only), TMP0/1, the ALU (-AC-RD: DATA0..7 = AC, DATA8..15 = $FF), the register cards, the branch and INT-vector registers, the I/O card's UART/switches (DATA0..7) | 16-bit; memory and I/O use the low byte |

Row b:

| Pin | Signal | Driven by | Notes |
|---|---|---|---|
| b3..b6 | DATA12..15 | as above | |
| b7 | -REG-FUNC-RD | pipeline | register read function (with the ID and lane strobes) |
| b8 | -REG-FUNC-LD | pipeline | register load function |
| b9..b12 | REG-RD-ID0..3 | sequencer IC4/IC5 (74LS244, enabled by the operand-select bits, **not** by -BUS-EN) | source register number; from the operand byte when -2-BYTE-OPERAND-SEL |
| b13..b16 | REG-LD-ID0..3 | same | destination register number |
| b17 | -REG-RD-LO | pipeline | low-byte lane of a register read |
| b18 | -REG-LD-LO | sequencer IC31 (LS04 totem pole, gated by the branch-taken latch for R0) | low-byte load strobe; the signal table stores it as `REG-LD-LO` ("active low on the bus") |
| b19 | -REG-RD-HI | pipeline | high-byte lane |
| b20 | -REG-LD-HI | sequencer IC31 | high-byte load strobe |
| b21 | -REG-DN | pipeline | count down (with -REG-FUNC-RD + ID) |
| b22 | -REG-UP | pipeline | count up |
| b23 | -MEM-RD | pipeline | memory read strobe (`docs/cards/memory.md`) |
| b24 | -MEM-WR | pipeline | memory write strobe |
| b25 | -IO-RD | pipeline | I/O read strobe (`docs/cards/io.md`) |
| b26 | -IO-WR | pipeline | I/O write strobe |
| b27 | -TMP-REG-RD0 | pipeline | TMP0 onto DATA0..15 |
| b28 | -TMP-REG-LD0 | pipeline | TMP0 latches (leading edge) |
| b29 | -TMP-REG-RD1 | pipeline | TMP1 read |
| b30 | -TMP-REG-LD1 | pipeline | TMP1 load |

Row c:

| Pin | Signal | Driven by | Notes |
|---|---|---|---|
| c3..c6 | ADDR-REG-ID0..3 | sequencer IC18/IC11 (74LS244) | which register drives the address bus; V3.1 called these -ADDR-REG-RD0/LD0/RD1/LD1 (section 6) |
| c7..c10 | IO-ADDR0..3 | pipeline (`IOADDR0..3` field) | the I/O port number |
| c11 | -IO-ADDR-LD | pipeline | no consumer on any card (I/O card decodes combinationally) |
| c12 | -VMA | pipeline | valid memory address; added in V3.1; asserted in every microcode step today (the memory card's M1 hack) |
| c13 | -INT | I/O card IC8/F (open collector) | interrupt request; the sequencer's JP3 selects edge/level |
| c14 | -INTA | pipeline | never asserted by any record |
| c15 | -ALU-FUNC | pipeline | enables the ALU's bus transceivers |
| c16..c19 | ALU0..3 | pipeline | ALU function / shift mode / condition select |
| c20 | -AC-LD-INV | pipeline | load the accumulator inverted (also flips BR-COND) |
| c21 | -AC-RD | pipeline | accumulator onto the bus |
| c22 | -AC-LD | pipeline | accumulator latches (leading edge) |
| c23 | -SR-LD | pipeline | shift register clock |
| c24 | BR-COND | ALU card IC27 (74LS86) | the selected condition, sampled by the sequencer's BR-TEST latch; input to the tester |
| c25 | -HL-SWAP | pipeline | byte-swap transceiver on the register cards |
| c26 | IN | I/O card (the IN switch through the INPUT header) | active high; condition mux input 5 |
| c27 | OUT | sequencer IC22 (SR latch, totem pole) | the OUT LED on the I/O card; ON/OFF |
| c28 | -BUS-EN | sequencer IC36 (LS04 from the sequencer-memory READY line) | output enable of the pipeline 374s and the microcode-address 244s; also read by the memory, register and ALU cards. The bus tester drives it too (section 5) |
| c29 | -RUN | — | connector-only on every card ("unconnected everywhere", control/IO review) |
| c30 | -RESET | sequencer IC36 (LS04 totem pole, from the front-panel RS latch) | active low; presets FORCE-ROM, clears the register counters and ALU flags; no power-on reset (S1) |

The backplane drawing itself names these nets SIG0..SIG83 in connector-pin order and knows nothing of the signal
names — it is the same board whichever template a card was drawn to.

## 3. Schematic walkthrough

### 3.1 Backplane V2.0 (`yacc2buss.sch`)

Parts: X1..X8 `FABC96S` (the socket half of the DIN 41612 pair; the cards carry `FABC96R`), wire pads `5V` and `GND`
(`WIREPAD 4,16O1,6`), PWR LED with R1 330 Ω, C1..C8 electrolytic (`E5-6` footprint, value empty — the review's
"BOM/value gaps" list). Nets: `5V` = the six power pins of every slot (A2, A31, B2, B31, C2, C31) plus the pads,
R1 and the capacitors' positive ends; `GND` = A1, A32, B1, B32, C1, C32 of every slot; 84 signal nets each joining
the same pin of the eight sockets and nothing else. The mechanical review: "20 parts, 87 nets, 1 ICs, 86 bus-
connector nets" (it counts the LED as an IC and the two power nets among the connector nets); the only item is the
LOW "0 100 nF-class caps for 1 ICs", i.e. no ceramic decoupling on the backplane — the cards carry their own.

**To verify:** C1..C8's value (bulk electrolytics per slot), and the current rating of the wire-pad feed.

### 3.2 Bus Template V3.2 (`Bus Template V3.2.sch`)

Three parts (X1, PWR LED, R2) and 84 named nets: a schematic, not a board. Every 2020-generation card starts from
it; the ribbon label in each card schematic is copied from it. `archive/superseded-revisions/` holds V3.0/V3.1.

### 3.3 Blank card V3.1 and V3.2 (`Blank V3.1.sch`, `Blank V3.2.sch`)

The template on the card outline with mounting: the connector, the LED, the outline. V3.1 (2020-08-23) was ordered
as a bare board 2025-06-27 and is the base the video card was built on. Parsed side by side, the two schematics
differ in exactly four net names (C3..C6, section 6); parts and connectivity are identical — V3.2 was produced by
`tools/make_blank_v32.py` as a text substitution on 2026-09-20 and checked with `tools/compare_eagle.py`. V3.2 has
never been opened in Eagle/Fusion or fabricated; `BACKLOG.md`: re-save it and use it for every new card.

### 3.4 Bus jumper boards (`Jumper Board Horizontal V3.1.sch`, byte-identical to the vertical's)

Two `MABC96R` connectors X3 and X4 wired pin-for-pin (nets N$4.. joining X3.An to X4.An etc.), GND common, and two
5 V rails V1 (X3's six power pins, PWR1 through R1) and V2 (X4's, PWR2 through R2) joined only through the solder
jumper JP1 (`JP1Q`): each side has its own power LED and the rails can be split. The horizontal board is 231 x 115 mm,
4-layer (V3.2, "Increase trace width spacing and add layers" over the 2-layer V3.0); the vertical 76 x 114 mm 2-layer
(V3.0; a V3.1 board file corrects only the silkscreen). They linked two backplane connectors in an older bus
arrangement; **built, not fitted, obsolete** (Ken 2026-09-20, both READMEs). `media/double bus.jpeg` shows the
arrangement they belonged to.

### 3.5 Mechanical (`hardware/mechanical/`)

`clip.skp`, `clip12.skp`/`clip12.stl` (card divider clips, SketchUp source and print files) and `divider.stl`. The
README also lists "switch template (.svg), spacers, layout specs", which are not in the folder as of this tree.
**To verify:** whether those files exist elsewhere (the Mem Switch build notes refer to a switch template for
aligning the toggles).

## 4. Timing conventions and the design-review findings that live on the bus

The bus has no clock line. Timing is set entirely by the sequencer: one microcode step is two clock periods; the
control word for a step is latched into the pipeline 374s at the step boundary and every control line changes
together (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1). Cards therefore see clean, simultaneous edges on all strobes
and select lines, and the *ordering* of set-up, strobe and hold steps in the generator is what makes each transfer
work. The latch-edge summary (1.6 there) is the contract: leading-edge latches (IR, operand, branch/INT registers,
TMP, accumulator, shift register) need their data on the bus *before* the strobe step; trailing-edge actions
(register loads and counts, RAM/EEPROM and I/O writes) need it *through* the strobe step.

| ID | Severity | Finding | Status 2026-09-23 |
|---|---|---|---|
| 5.1 (`DESIGN-REVIEW-NOTES-control-io.md`), M5/S3 (datapath) | LOW, system-wide | **No pull-ups anywhere on the bus.** Whenever the pipeline's 374s are off (READY low for ~54 s at every boot; the tester holding -BUS-EN high) every control line floats. LS inputs read that as high — inactive for every active-low strobe, which is why the memory and I/O cards sit quietly during the microcode load — but the active-high lines (REG-*-ID, ADDR-REG-ID, IO-ADDR, ALU0..3, BR-COND, OUT, IN) are undefined and CMOS inputs (the register card's CD4077, the video card's 74HC160) see mid-rail | Open; "a pull-up bank on a future revision is the usual answer" |
| 1.1 / 4.1 | HIGH | 17 lines (B9..B16, C3..C6, B18, B20, C27, C28, C30) are driven by the sequencer-logic card regardless of -BUS-EN, and the bus tester's firmware drives all of them push-pull from `setup()`: two totem-pole drivers per line whenever both are fitted. The tester cannot load RAM with the logic card in | Open; the sequencer v2.2 "CPU off" switch + open-collector -BUS-EN (BACKLOG). Today: unplug the logic card to use the tester |
| 1.3 | MED | during reset the pipeline holds a stale word (it reloads on reset *release*), so the bus is driven with whatever was executing, FORCE-ROM active | Open (sequencer) |
| 1.8 | LOW | pipeline outputs float with -BUS-EN high; -BRANCH-RD/-INT-JMP could put the branch/INT registers on the data bus against the tester on noise | By convention |
| S1 (datapath) | MED | no power-on reset: -RESET (c30) is a manual RS latch; every card's reset-dependent state is undefined until the button | Open |
| M-1 (microcode review) | MED | `-REG-FUNC-RD` without lane strobes puts $FFFF on DATA0..15 through the register card's transceivers in 327 steps while memory also drives (fetch step 4 of every instruction): a permanent, functionally harmless contention that the emulator counts as "weak" drives | Open; "the machine lives with it" |
| H-1 / H-2 | HIGH | the two real data-bus fights (PUSHR; BRZ/BRNZ/BR16Z/BR16NZ) | **Fixed** in the generator and loaded 2026-09-22; H-3 (BR16Z/NZ) stands |
| H-4 | HIGH | 38 all-zero opcode records assert every active-low line at once for 61 steps | Open in the generator |
| H-5 | HIGH (to check on the board) | sequencer IC11 gate B may drive ADDR-REG-ID0..3 low permanently against IC18 | **To verify:** scope c3 during a single-stepped `PUSH` (bench item 1 of the microcode review) |
| -RUN (c29) | doc | unconnected on every card | spare pin |
| backplane values | LOW | C1..C8 value blank | To record |

## 5. Who drives what, and the rules for a new card

1. **Address bus:** only the register cards, only while -VMA is low (their 74LS244 enables are -BUS-EN OR -VMA); the
   bus tester in ADDRBUS-WR-MODE. A memory-mapped card must qualify its select with -VMA (the memory card's IC7 G2A,
   the video card's comparator cascade) — and must not depend on the address being stable *before* -VMA falls (M1).
2. **Data bus:** 16 bits. Memory and I/O use DATA0..7 only; TMP, the branch/INT registers, the register cards and the
   ALU drive all 16 (the ALU with $FF on the high byte). A card that reads a 16-bit value must know which strobe pairs
   deliver both bytes (`-REG-RD-LO` + `-REG-RD-HI`, TMP, BRANCH). Pull-downs RN5/RN6 on the memory card and pull-ups
   RN1-RN4 on the tester are the only passive loads, values unknown.
3. **Control lines:** inputs only for every card but the sequencer, the I/O card (-INT, IN) and the ALU (BR-COND).
   Treat them as undefined while -BUS-EN is high. Any new open-collector driver (the CF card's status lines, a second
   -INT source) needs its own pull-up — the bus has none.
4. **Strobes:** -MEM-RD/-MEM-WR/-IO-RD/-IO-WR are one-step pulses (two clock periods) inside multi-step records that
   set the address/port a step earlier and hold the source a step later (`docs/cards/memory.md` section 4,
   `docs/cards/io.md` section 2). A device that latches on the trailing edge gets a full step of set-up; one that
   latches on the leading edge gets none and must be fast.
5. **Reset:** -RESET is active low, totem-pole from the sequencer, manual only. Invert it on the card if the part
   needs an active-high reset (the I/O card does for the 16550); never drive it from a card.
6. **Ports:** IO-ADDR0..3 are static during the whole I/O record, so a port decoder needs no latch (-IO-ADDR-LD is
   unused); qualify every device action with -IO-RD or -IO-WR. New devices follow "select port + data port"
   (`docs/system/OS-PLAN.md` decision 3).
7. **Start from Blank V3.2**, not V3.1 (section 6), and copy the ribbon label from the template.

## 6. The V3.1 to V3.2 change on C3-C6

Bus V3 (June 2020) gave pins C3..C6 to the **Address+TMP card**: two 16-bit address registers and TMP built from
eight 74373 latches (`hardware/cards/address-tmp`, fabricated 2020-06-20), driven by four strobes
`-ADDR-REG-RD0`, `-ADDR-REG-LD0`, `-ADDR-REG-RD1`, `-ADDR-REG-LD1` (read/load register 0/1). V3.1 (August 2020) added
-VMA on C12 (`blank-card/eagle/v3.1/Notes.md`) and kept those names. When the Index Register card (1.1, 2020-08-31)
replaced the Address+TMP card, the address source became "any of the eight index registers", selected by a 4-bit
number — **ADDR-REG-ID0..3**, active high — and TMP moved to the memory card. Bus Template V3.2 (2020-09-10 per the
connector README; the template file is dated 2020-11-29) renamed the four pins accordingly; the built cards were
re-saved with V3.2 names on 2020-11-29 (`hardware/FABRICATED.md`), but the connector PDF beside them and the Blank
V3.1 board were not. Cards drawn on Blank V3.1 afterwards — Mem Switch 1.1, Mem Register 1.0, the video card —
therefore carry the old labels on nets they do not use (MACHINE.md fault 4: "harmless, documented"). The one card
that would have been *wrong* is the retired Address+TMP card itself ("Old designs do not use").

| Pin | V3.1 name | V3.2 name | Now driven by |
|---|---|---|---|
| C3 | -ADDR-REG-RD0 | ADDR-REG-ID0 | sequencer IC18 B / IC11 (74LS244) |
| C4 | -ADDR-REG-LD0 | ADDR-REG-ID1 | same |
| C5 | -ADDR-REG-RD1 | ADDR-REG-ID2 | same (register-card select, with J3 on each card) |
| C6 | -ADDR-REG-LD1 | ADDR-REG-ID3 | same |

The two index-register cards decode ADDR-REG-ID2..3 with their J3 headers to know which of them holds R0-R3 and
R4-R7 (MACHINE.md).

## 7. Settings, bring-up and revision history

Settings: none on the backplane. Slot assignment of the cards is not recorded in the tree (**To verify** — a photo,
`media/system1.jpeg`, exists). The bus jumper boards are not fitted.

Bring-up (`docs/procedures/System Build Notes.md` build order: bus tester, bus card, memory, prototype, register 1,
ALU, register 2, sequencer memory, sequencer logic): the first thing on a new backplane is the connector check
that every card's build notes repeat (three GND at each end of every row, three VCC beside them, no short), then the
tester's `bus-test` sketch for shorts between signal pins.

| Rev | Date | Status | Notes (`hardware/FABRICATED.md`, READMEs) |
|---|---|---|---|
| V1.1 | 2016-06-16 | fabricated (gen-1, 7 slots), still listed as Production in 2021 | `bus/backplane/eagle/deprecated/v1.1`; `Build Notes.rtf` there is the bus-card check procedure; `media/bus v1.0 top.jpeg`, `bus v1.1 solder.jpeg` |
| V2.0 | 2021-07-26 (sch) / 2021-08-03 (brd) | **in the machine** | adds the 8th slot X8 and C7/C8; DXF/SVG/PDF exports beside the design, CAM in `fab/` |
| Bus Template V3.2 | 2020-11-29 | schematic only | canonical names |
| Blank V3.1 | 2020-08-23, ordered 2025-06-27 | bare boards fabricated | stale C3-C6 names; base of the video card |
| Blank V3.2 | derived 2026-09-20 | design only | the template for the next card |
| Jumper horizontal V3.0 / V3.2, vertical V3.0 | 2020-06 / 2020-07 | fabricated, not fitted | obsolete |

What a next backplane should change (from the findings): a pull-up bank on the control lines (and defined
terminations for the active-high select lines), decoupling capacitor values recorded, and — if the sequencer v2.2
"CPU off" change is made — nothing else, since the bus-ownership problem is on the cards, not on the board.
