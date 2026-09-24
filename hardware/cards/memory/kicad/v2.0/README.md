# memory-v2.0 — the built memory card v1.3 + the CompactFlash interface (KiCad design)

**Status 2026-09-24 (rebuilt on the built card): schematic done and proven. PLACEMENT BLOCKED: the CF section does not
fit on the built card with the built card's copper kept. None of the three placement options is legal on the real
board, so nothing is routed. Not ordered.** See "Why nothing fits" below; a decision is needed (end of this file).

v2.0 is the memory card v1.3 **as built** (`../v1.3-fusion-export-2026-09-24`: the KiCad conversion of Ken's Fusion
export of the card JLCPCB fabricated on 2025-06-27, proven against the order's gerbers; 62256 x 2, 28C64, IC7 block
decode, FORCE-ROM, IC15 buffer enable, TMP0/TMP1) plus the CompactFlash interface of the CF card v1.0
(`../../../cf/kicad/v1.0/`), **as drawn**: its own 74LS138 decoding **I/O ports P8 (register-select latch, write) and
P9 (data, read/write)**, enabled by IO-ADDR3. The ROM in the machine and both emulators (`software/cfmodel.h`,
`firmware/monitor/monitor.asm`) already talk to P8/P9: no firmware change. The CF card's own bus connector goes; the CF
section shares the memory card's X1. Theory of the CF circuit: `docs/cards/cf.md`; of the memory card:
`docs/cards/memory.md`.

`MASTER` marks this folder as hand-maintained (not written by `tools/eagle_to_kicad_all.py`).

History: the first v2.0 (commit 0c2e15e) was built on `../v1.3`, the tree's older Eagle save. That save has no IC15
and keeps the TMP registers IC26-IC29 and RN5/RN6 off the board, unrouted; the generator put them where the fabricated
card has them, dropped 101 of the save's copper items that no longer made sense, and reserved IC15's spot. On
2026-09-24 Ken exported the real design from Fusion; this folder is now generated from that, and all of the questions
about IC15 are answered by it (below). The price: the real card's TMP routing occupies the space the old options used.

## What v2.0 is, relative to the built card

- **Schematic.** Sheets 1-6 are the built card's, copied unchanged except: on sheet 1 the six X1-only local labels
  IO-ADDR0-3, -IO-RD, -IO-WR became global labels (sheet 7 uses them) and a note says so; title blocks say v2.0.
  **Sheet 7** is the CF section, drawn with the CF card's own sheet writer (`gen_cf.py`, class `Sheet`), nets shared
  with sheets 1-6 as boxed global labels. **IC15** (74ALS11, gate A = AND(-LO-RAM, -HI-RAM, -ROM-CS) -> IC5 pin 19,
  the 74LS245's enable) is simply part of the built card's schematic now: nothing reserved, nothing to add.
- **Bus pins now used** (same backplane pinout as the CF card v1.0; checked pin by pin against the built card's X1 by
  `check_netlist.py`): IO-ADDR0-3 = C7-C10, -IO-RD = B25, -IO-WR = B26 (unused on v1.3, now wired to the CF
  section); -RESET = C30 (v1.3: IC12 PRE, now also IC32 CLR and IC33); DATA0-7 = A19-A26 (also IC34 A side, IC32 D1-D4).
- **Board.** Same outline (177.8 x 114.0 mm), X1 at the same place, **4 layers with the built card's stack-up**: In1 =
  GND plane, In2 = VCC plane (both polygons already cover the whole board, x 17.7-194.4 / y 10.9-124.1, so the CF
  pads join the planes on a refill), signals on F.Cu/B.Cu. **All 1,377 copper items of the built card (1,263 track
  segments, 114 vias) are kept unchanged** in every board (`gen_mem_v2.py locked` proves it per option:
  `reports/option-X-locked.txt`); a move of a built-card part that has a track on a pad is refused.
- **Design rules** = the built card's: the project's (0.1524 mm tracks, 0.127 mm clearance, 0.4572/0.254 mm vias,
  0.381 mm copper to edge) plus the two Eagle rules that are stricter, in `memory-v2.0.kicad_dru`: track to track
  0.4572 mm (18 mil, Eagle mdWireWire; the built card's closest pair of tracks is 0.483 mm apart) and track to pad
  0.254 mm (10 mil, mdWirePad). Every track on the built card is 0.1524 mm.

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

## Why nothing fits (read this first)

The built card routes the TMP registers' high byte, **DATA8-15, as a bundle of eight B.Cu tracks** from the bus
connector along the bottom edge and then diagonally up across the lower right of the board to IC27/IC29 (plus F.Cu runs
under the ROM). In the earlier save those tracks did not exist, which is why the old options looked free. On the real
card the bundle runs straight through the "three empty IC slots" beside C20-C22 and the band under the ROM, where the
options put the CF chips. A through-hole pad cannot sit on a track, and the built copper is kept, so:

- **Every option's board has CF pads on built-card tracks** (DRC under the card's rules, beyond the built card's own
  list): option A 11 shorts + 4 clearance + 63 solder-mask bridges, option B 12 + 1 + 50, option C 12 + 3 + 63
  (`reports/option-X-drc-summary.txt`; the renders and placement plots show the CF parts on the bundle).
- **There is no legal placement at all** (`space_check.py`, `reports/space-check.txt`,
  `memory-v2.0-free-space.png`): with every pad at least 0.3 mm clear of the built copper (and pads, bodies and the
  edge respected) a CF DIP can only go in the triangle right of the bundle, courtyards within x 157.8-195.2 /
  y 68.7-123.3. **At most 4 of the 5 CF DIPs fit there even with no IDE header and none of the 16 other CF parts**;
  with J2 where option C puts it (the free top edge, lower half) only 2 fit, with J2 where option A puts it 4. J2
  itself fits only along the top edge beside IC26-IC29, flush against their outlines.

What the old option texts said about space (the "three empty IC slots", the band under the ROM, "nothing of v1.3
moves") was true of the earlier save only.

## Placement options (the record; none is legal on the built card)

Coordinates are board mm (y down). The card stands on X1 in the cage, so **x = 195.55 is the card's free top edge**,
y = 10 and y = 124 its two free side edges. The options are unchanged from 0c2e15e (`placements.py`), now drawn on the
built card; the TMP registers and IC15 are simply the built card's. `gen_mem_v2.py check` still passes (no body
overlaps, pads clear of the edge, no tall part in the TAODAN keep-low zone): the failure is copper, not bodies.

| | J2 | built-card parts moved | CF pads on built copper (shorts / clearance / mask bridges) | CF airwire (straight-line) |
|---|---|---|---|---|
| **A** | top edge, upper half, beside IC26-IC29 | none | 11 / 4 / 63 | ~3.1 m |
| **B** | y = 124 side edge under the ROM | C23 up 7.5 mm (no tracks on its pads; planes only) | 12 / 1 / 50 | ~3.1 m |
| **C** | top edge, lower half, beside the CF chips (Ken's choice) | none | 12 / 3 / 63 | ~2.7 m |

Renders: `memory-v2.0-option-{a,b,c}-render-top.png`; 2D plots with the ratsnest: `memory-v2.0-option-{a,b,c}-placement.png`.

### DRC (all under the built card's rules; the built card's own list is the baseline)

| | built card | A | B | C |
|---|---|---|---|---|
| shorting_items / clearance / solder_mask_bridge | 0 / 0 / 0 | 11 / 4 / 63 | 12 / 1 / 50 | 12 / 3 / 63 |
| items_not_allowed (inherited) | 2 | 2 | 2 | 2 |
| unrouted connections (ratsnest) | 0 | 61 | 61 | 61 |
| silk_overlap / silk_edge_clearance | 45 / 4 | 46 / 6 | 45 / 4 | 48 / 4 |
| schematic parity items (all inherited Eagle values/fields) | 220 | 53 | 53 | 53 |

The built card itself is clean under its rules (no copper violation, 0 unconnected; the rest is the Eagle drawing's
silk). ERC: 99 = the built card's 104 + the designed-in one-pin `SRST` label - the six "isolated label" warnings of the
labels that became global.

## The CF-to-IDE adapter

- **TAODAN CF-IDE40 V2.0** (70 x 63 mm, female 40-pin socket along a 70 mm edge) plugs straight onto J2 and stands
  **perpendicular to the card, out of the component side**, its lower edge ~9-10 mm above the card, overhanging each
  end of the 50.8 mm pin row by ~10 mm; +5 V from IDE pin 20 through JP2. Each option draws on User.Drawings (and on
  the silk of the render copy) the adapter strip (solid, 70 x 8 mm) and a keep-low zone (dashed: 12 mm past each end
  of the pin row, 7 mm either side of the header centre line) that must hold nothing taller than ~8 mm.
- **The card needs free space on its component side** when the TAODAN is used (~75 mm).
- **SinLoon CF-to-IDE** (60 x 43 mm, male 40-pin) on a short ribbon: J2 is shrouded and at a free edge.

## Files

| File | What it is |
|---|---|
| `mem_v2_netlist.py` | **the delta** (single source): CF card v1.0 -> v2.0 reference map, dropped parts, shared nets, `check()`, `expected()` |
| `gen_mem_v2.py` | writes the schematic (`sch`), the option boards (`board`), proves the built copper kept (`locked`), refills the planes (`refill`), checks the placement (`check`), makes review copies (`review`) |
| `placements.py` | the options (plain data) |
| `space_check.py` | where CF parts can sit on the built card at all; packs the five DIPs (`reports/space-check.txt`, `memory-v2.0-free-space.png`) |
| `check_netlist.py` | the netlist proof: schematic = built v1.3 + CF section, every board = the schematic |
| `build.sh` | the whole pipeline; exit 0 = every gate passed (today it exits 1: the options conflict with the built copper) |
| `memory-v2.0.kicad_sch`, `-sheet1..7.kicad_sch`, `.kicad_pro`, `.kicad_dru` | schematic (sheets 1-6 built v1.3, sheet 7 CF), project, the built card's extra design rules |
| `memory-v2.0-option-{a,b,c}.kicad_pcb` / `.kicad_pro` / `.kicad_dru` | the three placement options (ratsnest only) |
| `memory-v2.0-option-{a,b,c}-render-top.png`, `-placement.png` | 3D render with the adapter zones; 2D plot with copper, silk, zones, airwires |
| `memory-v2.0-free-space.png` | the built card's copper, where a CF DIP may sit (blue haze) and the best packing found (4 DIPs) |
| `memory-v2.0-schematic.pdf`, `memory-v2.0-bom.csv` | schematic plot, bill of materials |
| `memory-v1.3-fusion-export-2026-09-24-eagle.kicad_sym`, `.pretty/`, `sym-lib-table`, `fp-lib-table` | the built card's converted libraries, copied (same nickname) |
| `reports/` | ERC (`.rpt`, `.json`, `erc-summary.txt`), netlist (`.net`), `netlist-proof.txt`, `base-summary.txt`, `space-check.txt`, per option `option-X-drc.json`, `-drc-summary.txt`, `-placement-check.txt`, `-locked.txt` |

## Rebuild

    hardware/cards/memory/kicad/v2.0/build.sh                 # ~5 minutes; OPTIONS="a c" for a subset

It reads `../v1.3-fusion-export-2026-09-24` (through a scratch copy) and `../../../cf/kicad/v1.0/cf_netlist.py` +
`gen_cf.py` (read-only). Steps: schematic; ERC vs the built card; the reference board (the built card with v2.0 net
names) and its DRC under the v2.0 rules; per option: board, locked-copper proof, plane refill, placement check, DRC with
schematic parity, render + plot; space check; netlist proof; PDF + BOM.

## Results (build of 2026-09-24)

- **Netlist proof: MATCH.** v2.0 schematic = the built v1.3 (53 parts, 169 nets, IC15 included) + CF section (21
  parts, 27 own nets, 69 pins on 17 shared nets): 74 parts, 186 nets, 695 pins, 33 unconnected pins (10 v1.3 + 23
  documented CF no-connects). The CF card's 27 dropped X1 pins are each on the same-named net of the memory card's X1.
  All three option boards equal the schematic pad for pad (`reports/netlist-proof.txt`).
- **ERC: PASS** (99 vs the built card's 104, all explained).
- **Built copper: kept**, 1,377 of 1,377 items unchanged on every board.
- **Placement: FAIL** in every option, and no legal placement exists (above).

## Decision needed (Ken)

The CF section needs about as much free board as the built card has left, and the free part is a triangle in the
bottom right corner. Ways forward, none taken:

1. **Re-route the built card's DATA8-15 bundle** (and whatever else crosses the lower right), keeping every other
   built-card track: the circuit stays the built card's, but its copper would no longer be the fabricated copper in
   that area. This frees the "three empty slots" and the band under the ROM that the options were designed for;
   option C could then be placed and routed as planned.
2. **Keep the CF on its own card**: the CF card v1.0 (`hardware/cards/cf/kicad/v1.0/`) is routed and checked, costs a
   backplane slot, and needs no change to the memory card.
3. **Smaller packages** for the CF logic (SOIC 74LS/HCT parts on the bottom or top side) would fit into the triangle
   with J2 at the top edge; the card is through-hole today.
4. A fresh layout of the whole memory card (built circuit, new copper) with the CF section designed in from the start.

Open items that stay whatever is chosen: J2 pin 1 / key vs the chosen adapter (TAODAN plugs straight on and stands
perpendicular, SinLoon via ribbon); J3 pinout (1 +5 V, 2/3 GND, 4 n/c) against the adapter's cable; socket heights
under a TAODAN overhang; which backplane slot (a TAODAN needs ~75 mm free on the component side); whether to keep
both C20-C22 (the built card's caps with no IC beside them) and C27-C29.
