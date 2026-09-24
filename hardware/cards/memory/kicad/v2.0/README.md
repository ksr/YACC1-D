# memory-v2.0 — the built memory card v1.3 + the CompactFlash interface (KiCad design)

**Status 2026-09-24 (re-layout): schematic done and proven. Ken decided to LAY OUT THE WHOLE CARD AGAIN with the CF
section designed in (the built card's placement and copper are discarded; circuit, outline, bus connector and 4-layer
stack-up kept). Three re-layout placement options, each with a trial autoroute: all three route completely (0
unrouted, 43 vias, no DRC copper violation). Recommended: option B. Waiting for Ken's pick; the final routing polish
(finisher, silk tidy, fab outputs) comes after that. Not ordered.**

v2.0 is the memory card v1.3 **as built** (`../v1.3-fusion-export-2026-09-24`: the KiCad conversion of Ken's Fusion
export of the card JLCPCB fabricated on 2025-06-27, proven against the order's gerbers; 62256 x 2, 28C64, IC7 block
decode, FORCE-ROM, IC15 buffer enable, TMP0/TMP1) plus the CompactFlash interface of the CF card v1.0
(`../../../cf/kicad/v1.0/`), **as drawn**: its own 74LS138 decoding **I/O ports P8 (register-select latch, write) and
P9 (data, read/write)**, enabled by IO-ADDR3. The ROM in the machine and both emulators (`software/cfmodel.h`,
`firmware/monitor/monitor.asm`) already talk to P8/P9: no firmware change. The CF card's own bus connector goes; the CF
section shares the memory card's X1. Theory of the CF circuit: `docs/cards/cf.md`; of the memory card:
`docs/cards/memory.md`.

`MASTER` marks this folder as hand-maintained (not written by `tools/eagle_to_kicad_all.py`).

History: the first v2.0 (0c2e15e) was drawn on `../v1.3`, an earlier save of the design without IC15 and without the
TMP registers' copper. Rebuilt on the real design (Ken's Fusion export, 4365de6), the CF section no longer fitted
beside the built card's copper (its DATA8-15 bundle crosses the free area): options A/B/C with the built copper kept
were all blocked. **Ken's decision, 2026-09-24: re-lay the whole card** (way 4 of that list). The blocked options are
kept as a record in `options-keep-copper/` (below).

## What v2.0 is, relative to the built card

- **Schematic.** Sheets 1-6 are the built card's, copied unchanged except: on sheet 1 the six X1-only local labels
  IO-ADDR0-3, -IO-RD, -IO-WR became global labels (sheet 7 uses them) and a note says so; title blocks say v2.0.
  **Sheet 7** is the CF section, drawn with the CF card's own sheet writer (`gen_cf.py`, class `Sheet`), nets shared
  with sheets 1-6 as boxed global labels. **IC15** (74ALS11, gate A = AND(-LO-RAM, -HI-RAM, -ROM-CS) -> IC5 pin 19,
  the 74LS245's enable) is part of the built card's schematic. The circuit is unchanged by the re-layout.
- **Bus pins now used** (same backplane pinout as the CF card v1.0; checked pin by pin against the built card's X1 by
  `check_netlist.py`): IO-ADDR0-3 = C7-C10, -IO-RD = B25, -IO-WR = B26 (unused on v1.3, now wired to the CF
  section); -RESET = C30 (v1.3: IC12 PRE, now also IC32 CLR and IC33); DATA0-7 = A19-A26 (also IC34 A side, IC32 D1-D4).

### Port assignment

| Port | Dir | What |
|---|---|---|
| P8 | write | IC32 74LS175 latch: bits 0-2 = ATA register (CF DA0-2), bit 3 = CF reset (1 = held), 4-7 ignored |
| P9 | read/write | the ATA register P8 selected, 8-bit True IDE, through IC34 74LS245 |

IC30 (74LS138) takes IO-ADDR0-2, G1 = IO-ADDR3, G2A/G2B low: Y0 = P8, Y1 = P9, Y2-Y7 unused. The I/O card must keep
its IO-ADDR-HL strap at P0-P7 (it would otherwise also answer P8/P9).

### Part-list delta (built v1.3 -> v2.0)

Added (reference designators clear of the built card's IC1-IC15, IC18, IC26-IC29, C1-C24, R2, RN5-RN8, JP1, PWR0,
U$1, X1):

| v2.0 | CF card v1.0 | Part | Footprint |
|---|---|---|---|
| IC30 | U1 | 74LS138 port decode | DIP-16 |
| IC31 | U2 | 74LS32 strobe gating | DIP-14 |
| IC32 | U3 | 74LS175 P8 latch | DIP-16 |
| IC33 | U4 | 74LS08 buffer enable / CF reset / ACT driver | DIP-14 |
| IC34 | U5 | 74LS245 P9 data buffer | DIP-20 |
| J2 | J1 | 40-pin IDE header, 2x20 2.54 mm, shrouded (pin 20 kept) | IDC-Header_2x20_P2.54mm_Vertical |
| J3 | J2 | adapter power 1x4 (1 +5 V, 2/3 GND, 4 n/c) | PinHeader_1x04 |
| JP2 | JP1 | IDE pin 20 = +5 V jumper | PinHeader_1x02 |
| RN9 | RN1 | 10k x8 SIP, CF D0-7 pull-ups | R_Array_SIP9 |
| R10-R13 | R1-R4 | 10k: IORDY, -PDIAG, -DASP pull-ups, -DMACK high | axial 10.16 mm |
| R14, LED1 | R5, LED2 | 1k + yellow ACT LED (any P9 access) | axial, LED 5 mm |
| C25-C29 | C1-C5 | 100 nF, one per new IC | disc 5 mm |
| C30 | C6 | 10 uF bulk beside J3 | radial D5 |

Dropped from the CF card: X1 (bus connector, shared), **LED3 + R6 (DASP LED, Ken)**, **LED1 + R7 (PWR LED: the
memory card already has PWR0 + R2 330R)**. Everything through-hole. BOM: `memory-v2.0-bom.csv` (35 lines; built-card
parts keep their converted Eagle values, e.g. `74*32`, `C-US`).

## The re-layout (Ken, 2026-09-24)

**Kept from the built card:** the board outline (177.8 x 114.0 mm, x 17.72-195.55 / y 10.00-124.02), the bus
connector X1 (FABC96R, same position and orientation, its two mounting holes and keepouts: the card plugs into the same
backplane; there are no card guides in the cage) and the 4-layer stack-up: **In1 = solid GND plane, In2 = solid VCC
plane** (the built card's plane outlines), signals on F.Cu and B.Cu only. **Discarded:** every one of the built card's
1,377 tracks and vias, and the placement of every part but X1. All parts through-hole, no SMD.

**Orientation.** The card stands on X1 in the cage, so board +x is UP: the **x = 195.55 edge is the free top edge**
(J2 goes there), y = 10 and y = 124 are the two free side edges. The block-map jumpers U$1 and JP1 stay at the
y = 10 side edge where the built card has them; the LEDs, JP2 and J3 sit at the top edge.

**Power.** No power track anywhere: every GND/VCC pin (ICs, caps, headers, X1's six + six supply pins) is a
through-hole pad that reaches its plane through a thermal relief (0.4 mm gap, 0.5 mm spokes; antipads 0.3 mm). The
DRC's "0 unrouted" of the trial boards includes every power pin reaching its plane. **Decoupling:** one 100 nF per
IC, standing beside the IC's pin-1 / VCC end (the built card's arrangement): C1-C19, C24 for the built card's 20 ICs
(same pairs as built), C25-C29 for the CF chips; C30 (10 uF) at J3. C20-C23 (the built card's four caps with no IC
beside them) are kept as plane-to-plane decoupling: C20/C21 at X1's two power groups, C22/C23 at the far end of the
planes (open item).

### Design rules (`memory-v2.0-relayout-X.kicad_pro` net classes + `.kicad_dru`)

| | re-layout | the built card |
|---|---|---|
| signal track width | **0.25 mm (10 mil)**, every trial-route track | 0.1524 mm (6 mil) |
| clearance | **0.2 mm** (8 mil) | 0.127 mm, Eagle 0.4572 mm track-track, 0.254 mm track-pad |
| vias | **0.8 / 0.4 mm** (pad / drill) | 0.4572 / 0.254 mm |
| copper to board edge | 0.5 mm | 0.381 mm |
| hole to hole / hole clearance | 0.5 / 0.25 mm | 0.254 / 0.127 mm |
| power | net class Power (GND, VCC): not routed, planes only | same planes |
| planes | clearance 0.3 mm, thermal gap 0.4 mm, spoke 0.5 mm | 0.2 mm spokes |

With these rules one 0.25 mm track fits between two X1 pins, one between two KiCad DIP pins (1.6 mm round pads) and two
between two pins of the Eagle DIL footprints the built card's parts keep (1.22 x 2.44 mm oval pads). The track pitch
(0.45 mm) is finer than the built card's effective 0.61 mm (6 mil tracks at its 18 mil Eagle spacing), so the
re-layout is no harder to route than the built card was; only the vias are bigger.

### Placement grid and footprints

Every pad of the card is on one 1.27 mm grid, the grid of X1's pins (anchor X1 A1 = 22.83, 106.22). The built card's
parts keep their converted Eagle footprints (the netlist proof requires the schematic's footprints); the CF parts use
the KiCad standard libraries as on the CF card v1.0. ICs are in columns of horizontal DIPs (pin 1 bottom left, as on
the built card), row pitch 13.97 mm, 5-8 mm channels between columns. J2 (Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical,
shrouded, pin 20 present) is at rotation 0 in every option: pads at x = 189.20 (odd pins, inboard: almost every IDE
signal is on an odd pin) and 191.74, shroud 0.6 mm inside the top edge, pin 1 toward y = 10.

## Placement options

Every option: same circuit (netlist proof MATCH, board and trial route), no body overlap, every pad 0.5 mm inside the
edge, X1 exactly as built, the TAODAN keep-low zone (12 mm past each end of J2's pin row, 7 mm either side of its
centre line) holding no IC and nothing tall (`reports/relayout-X-placement-check.txt`). Column 3 is the memories
(IC1 low RAM, IC2 high RAM, IC13 EEPROM) under the block-map jumper group, which keeps the built card's exact pad
positions (RN7, U$1, RN8, IC18, C24; its ROM / RAM / 0X8000 / 0XF000 labels move with U$1). Column 1 is next to X1.

| | idea | J2 (top edge) / adapter overhang | LEDs, JP2, J3 |
|---|---|---|---|
| **A** | the built card's topology, re-flowed: col 1 bus side (IC14, IC6, IC5, IC9, IC3, IC8, RN5/RN6), col 2 decode (IC7, IC4, IC15, IC11, IC12, IC10, IC30), col 3 memories + IC31, col 4 TMP registers IC26-IC29 above the CF chips IC34, IC32, IC33 | lower half, pins y 64.3-112.6; strip y 53.4-123.4 | PWR, ACT, JP2, J3 in the other top corner (y = 10 side) |
| **B** | TMP registers IC27/IC29/IC26/IC28 **right at the bus connector** (they use nothing but the data bus and four strobes, all entering at X1's upper half), address buffers IC9/IC8 below them; col 2 strobes, data buffer IC5, FORCE-ROM glue; col 3 memories + IC15; col 4 = the CF column (IC7/IC4 at its top beside IC18 and the jumpers, then IC33, IC34, IC31, IC32, IC30) with RN9 and R10-R13 between it and J2 | **centred**, pins y 50.3-98.6; strip y 39.5-109.5 | PWR LED **where the built card has it** (y = 124 corner), ACT beside it; JP2, J3, C30 at the y = 10 corner |
| **C** | option A's columns 1-3; column 4 turned round: CF chips IC33, IC34, IC32 at the top, TMP registers below | upper half, pins y 21.1-69.4; strip y 10.3-80.3 | PWR LED where built, ACT beside it, JP2/J3 between them and J2 |

### Trial autoroute (build of 2026-09-24)

Freerouting 1.9 on a two-signal-layer copy of each board (planes dropped, class Power not routed, 30 passes, one
optimisation pass `-oit 100`, one thread), the session imported back onto the 4-layer board, planes refilled, DRC with
schematic parity under the re-layout rules. **This proves routability only**: no finisher, no clean-up, no silk tidy.
Freerouting is not deterministic: a new run gives other numbers (the previous full build, same placements but for a few
silk labels, C22 in A and LED1 in B: A 0 unrouted / 47 vias / 12.8 m, B 0 / 45 / 11.9 m, C 0 / 40 / 12.5 m).

| | airwire (placement, MST of the 146 signal nets) | unrouted after Freerouting | vias | total track length (F.Cu / B.Cu) | DRC copper violations | Freerouting time |
|---|---|---|---|---|---|---|
| **A** | 11,438 mm | **0** | 43 | 12,873 mm (7,004 / 5,869) | **0** | 90 s |
| **B** | **10,496 mm** | **0** | 43 | **11,779 mm** (6,858 / 4,921) | **0** | 125 s |
| **C** | 11,173 mm | **0** | 43 | 12,429 mm (7,409 / 5,019) | **0** | 97 s |

Every trial board: all tracks 0.25 mm; DRC copper violations 0 (clearance, shorts, track width, via size, hole
clearance, edge clearance, starved thermals, dangling items, unconnected); the only non-cosmetic DRC items are X1's two
mounting holes inside X1's own via keepout, which the built card's DRC has too; the rest is silkscreen and the Eagle
library texts (`reports/relayout-X-trial.txt`, `-trial-drc.json`). Schematic parity: the built card's 53 inherited
Eagle value/field items, nothing new.

Images per option: `memory-v2.0-relayout-X-render-top.png` (3D, the TAODAN strip solid and the keep-low zone dashed on
the silk of a review copy), `memory-v2.0-relayout-X-placement.png` (2D: outline, silk, adapter zones, airwires),
`memory-v2.0-relayout-X-trial.png` (the trial route: F.Cu red, B.Cu blue).

### Recommendation: option B

- **Shortest wiring**: the lowest airwire (-8 % against A) and the shortest trial route (11.8 m against 12.4-12.9 m)
  at the same via count. The TMP registers, the part that sank the keep-the-copper attempt, sit where their only
  signals enter: the 16-bit data bus and the four TMP strobes come straight off X1's upper half into them, and DATA0-7
  continues in one bundle through IC5 to the CF buffer IC34 / latch IC32.
- **The CF section is one column** at the top edge with its passives between it and J2, ordered by J2's pin sequence
  (IC33 reset/enable, IC34 data, IC31 strobes, IC32 DA0-2, IC30 decode nearest the IO-ADDR pins).
- **J2 centred on the top edge**: the TAODAN's 70 mm board stays 29.5 / 14.5 mm inside the two side edges, the keep-low zone is
  clear of everything tall with 5 mm to spare, and a SinLoon ribbon leaves straight off the top edge.
- **The PWR LED stays where the built card has it**; ACT is next to it; both visible from the top edge; JP2 (pin-20
  power) and J3 (adapter power) are at the other end of the top edge, reachable with the card in the cage and outside
  the adapter overhang.
- Cost: IC7 and IC4 (block decode) sit at the top of the CF column, ~35 mm from the U$1 jumpers they serve (the
  trial route runs them along the y = 10 side without trouble); IC15 is alone under the memories.

A is the most familiar (the built card's column order) but the longest; C has the same topology as A with the CF chips
at the top and leaves the adapter strip 0.3 mm inside the y = 10 edge.

## The CF-to-IDE adapter

- **TAODAN CF-IDE40 V2.0** (70 x 63 mm, female 40-pin socket along a 70 mm edge) plugs straight onto J2 and stands
  **perpendicular to the card, out of the component side**, its lower edge ~9-10 mm above the card, overhanging each
  end of the 50.8 mm pin row by ~10 mm; +5 V from IDE pin 20 through JP2, or by cable from J3. Each option draws on
  User.Drawings (and on the silk of the render copy) the adapter strip (solid, 70 x 8 mm) and the keep-low zone
  (dashed): nothing taller than ~8 mm within 12 mm of either end of the pin row, and nothing tall within 7 mm of the
  header centre line (both sides: which way the adapter board faces is not known until it is in hand).
- **The card needs free space on its component side** when the TAODAN is used (~75 mm): see "which slot" below.
- **SinLoon CF-to-IDE** (60 x 43 mm, male 40-pin) on a short ribbon: J2 is shrouded and at the free top edge.

## Open items (for the option Ken picks)

1. **J2 pin 1 / key vs the adapter.** J2 has pin 1 toward y = 10, odd pins inboard, in every option (check on which
   side of the shroud the key slot falls). For the TAODAN, the socket's pin 1 decides which way its board then stands and whether its
   components face the card or away; check against the adapter in hand before ordering (a 180 degree turn of J2
   puts the odd pins outboard, which costs routing). For the SinLoon only the ribbon's twist matters.
2. **J3 pinout** (1 +5 V, 2/3 GND, 4 n/c, the CF card v1.0's) against the adapter's floppy-style power cable.
3. **Socket heights under a TAODAN overhang**: no IC is inside the keep-low zone, but IC sockets + chips beside it
   (IC34 5.4 mm from the zone in every option) are ~8-9 mm tall; the adapter's lower edge is ~9-10 mm up. Measure.
4. **Which backplane slot**: the TAODAN needs ~75 mm free on the component side, i.e. the neighbouring slot on that
   side empty (or a SinLoon on a ribbon).
5. **C20-C22 vs C27-C29 duplication**: the built card's C20-C22 (and C23) had no IC; the CF chips have their own
   C25-C29. The re-layout keeps all of them (the circuit is the netlist), C20-C23 as spare plane decoupling; delete them
   from the schematic if Ken prefers.
6. **Final polish after the pick** (not done here, on purpose): route with a finisher/clean-up pass, silkscreen tidy
   (reference texts: 4-8 per option still touch a pad, e.g. the built card's own RN7/RN8/IC18 texts, a few KiCad
   resistor/cap texts), fab outputs (gerbers, drill, placement PDF, renders).

## The keep-the-built-copper record (`options-keep-copper/`)

The three options of 4365de6 (the CF section added to the built card with all 1,377 built tracks and vias kept),
moved here unchanged with their renders, plots and reports. None is legal: every one puts CF pads on the built card's
DATA8-15 bundle (DRC: A 11 shorts / 4 clearance / 63 mask bridges, B 12 / 1 / 50, C 12 / 3 / 63), and
`space_check.py` found no legal spot for all five CF DIPs (best packing 4 of 5, `options-keep-copper/reports/space-check.txt`,
`options-keep-copper/memory-v2.0-free-space.png`). Regenerated only on request: `KEEPCOPPER="a b c" build.sh`
(`placements.py`, `gen_mem_v2.py board/locked/check`, `space_check.py`).

## Files

| File | What it is |
|---|---|
| `mem_v2_netlist.py` | **the delta** (single source): CF card v1.0 -> v2.0 reference map, dropped parts, shared nets, `check()`, `expected()` |
| `gen_mem_v2.py` | writes the schematic (`sch`); the keep-copper record boards (`board`, `locked`, `check`); `refill`, `review` (review images) |
| `relayout_placements.py` | **the re-layout options** (plain data + helpers: `row()` = a DIP and its cap, `j2()`, `labels()`) |
| `gen_relayout.py` | re-layout boards (`board`), `check`, `airwire`, trial route (`dsn` two-signal-layer export, `ses` import, `stats`) |
| `check_netlist.py` | the netlist proof: schematic = built v1.3 + CF section, every board = the schematic |
| `build.sh` | the whole pipeline; exit 0 = every gate passed |
| `memory-v2.0.kicad_sch`, `-sheet1..7.kicad_sch`, `.kicad_pro`, `.kicad_dru` | schematic (sheets 1-6 built v1.3, sheet 7 CF), project, the built card's rules (used by the record) |
| `memory-v2.0-relayout-{a,b,c}.kicad_pcb` / `.kicad_pro` / `.kicad_dru` | the three re-layout placements (unrouted) with the re-layout rules |
| `memory-v2.0-relayout-{a,b,c}-trial.kicad_pcb` / `.kicad_pro` / `.kicad_dru` | their trial routes (Freerouting output, not polished) |
| `memory-v2.0-relayout-{a,b,c}-render-top.png`, `-placement.png`, `-trial.png` | 3D render with adapter zones; 2D airwire plot; trial-route copper plot |
| `memory-v2.0-schematic.pdf`, `memory-v2.0-bom.csv` | schematic plot, bill of materials |
| `memory-v1.3-fusion-export-2026-09-24-eagle.kicad_sym`, `.pretty/`, `sym-lib-table`, `fp-lib-table` | the built card's converted libraries, copied (same nickname) |
| `placements.py`, `space_check.py`, `options-keep-copper/` | the blocked keep-the-built-copper options (record, above) |
| `reports/` | ERC (`.rpt`, `.json`, `erc-summary.txt`), netlist (`.net`), `netlist-proof.txt`; per re-layout option `relayout-X-placement-check.txt`, `-drc.json`, `-trial.txt`, `-trial-drc.json`, `-freerouting.log` |

## Rebuild

    hardware/cards/memory/kicad/v2.0/build.sh                     # ~10 minutes, new trial routes
    NOROUTE=1 hardware/cards/memory/kicad/v2.0/build.sh           # keep the committed trial routes, re-check them
    RELAYOUT="b" hardware/cards/memory/kicad/v2.0/build.sh        # one option
    KEEPCOPPER="a b c" hardware/cards/memory/kicad/v2.0/build.sh  # also regenerate the keep-copper record

It reads `../v1.3-fusion-export-2026-09-24` (through a scratch copy) and `../../../cf/kicad/v1.0/cf_netlist.py` +
`gen_cf.py` (read-only); Freerouting from `~/freerouting/freerouting.jar` (`FRJAR=`), watchdog `WATCHDOG=` s.

## Results (build of 2026-09-24)

- **Netlist proof: MATCH.** v2.0 schematic = the built v1.3 (53 parts, 169 nets, IC15 included) + CF section (21
  parts, 27 own nets, 69 pins on 17 shared nets): 74 parts, 186 nets, 695 pins, 33 unconnected pins (10 v1.3 + 23
  documented CF no-connects). All three re-layout boards, their three trial routes and the three record boards equal
  the schematic pad for pad (`reports/netlist-proof.txt`).
- **ERC: PASS** (99 vs the built card's 104, all explained: `reports/erc-summary.txt`).
- **Placement: OK** for A, B and C (`reports/relayout-X-placement-check.txt`).
- **Trial routes: complete** for A, B and C (0 unrouted, 43 vias each, 0 DRC copper violations; table above).
- **Next:** Ken picks the option; then the final routing polish, silk tidy and fab outputs.
