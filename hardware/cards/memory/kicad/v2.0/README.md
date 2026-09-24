# memory-v2.0 — memory card v1.3 + the CompactFlash interface (KiCad design, placement review)

**Status 2026-09-24: schematic done and proven, three placement options for review. NOT routed, not ordered.**

v2.0 is the memory card v1.3 (the card in the machine: 62256 x 2, 28C64, IC7 block decode, FORCE-ROM, TMP0/TMP1)
plus the CompactFlash interface of the CF card v1.0 (`../../../cf/kicad/v1.0/`), **as drawn**: its own 74LS138
decoding **I/O ports P8 (register-select latch, write) and P9 (data, read/write)**, enabled by IO-ADDR3. The ROM in
the machine and both emulators (`software/cfmodel.h`, `firmware/monitor/monitor.asm`) already talk to P8/P9: no
firmware change. The CF card's own bus connector goes; the CF section shares the memory card's X1. Theory of the CF
circuit: `docs/cards/cf.md`; of the memory card: `docs/cards/memory.md`.

`MASTER` marks this folder as hand-maintained (not written by `tools/eagle_to_kicad_all.py`).

## What changed from v1.3

- **Schematic.** Sheets 1-6 are v1.3's, copied unchanged except: on sheet 1 the six X1-only local labels
  IO-ADDR0-3, -IO-RD, -IO-WR became global labels (sheet 7 uses them) and a note says so; title blocks say v2.0.
  **Sheet 7** is the CF section, drawn with the CF card's own sheet writer (`gen_cf.py`, class `Sheet`), nets shared
  with sheets 1-6 as boxed global labels.
- **Bus pins now used** (same backplane pinout as the CF card v1.0; checked pin by pin against v1.3's X1 by
  `check_netlist.py`): IO-ADDR0-3 = C7-C10, -IO-RD = B25, -IO-WR = B26 (unused on v1.3, now wired to the CF
  section); -RESET = C30 (v1.3: IC12 PRE, now also IC32 CLR and IC33); DATA0-7 = A19-A26 (also IC34 A side, IC32 D1-D4).
- **Board.** Same outline, X1 at the same place, 4 layers, v1.3's copper kept where it is valid (see "The
  fabricated v1.3" below). Silkscreen title "YACC1 MEMORY BOARD V2.0" (v1.3's text, same place and size) and
  "CF: P8/P9" beside the IDE header.

### Port assignment

| Port | Dir | What |
|---|---|---|
| P8 | write | IC32 74LS175 latch: bits 0-2 = ATA register (CF DA0-2), bit 3 = CF reset (1 = held), 4-7 ignored |
| P9 | read/write | the ATA register P8 selected, 8-bit True IDE, through IC34 74LS245 |

IC30 (74LS138) takes IO-ADDR0-2, G1 = IO-ADDR3, G2A/G2B low: Y0 = P8, Y1 = P9, Y2-Y7 unused. The I/O card must keep
its IO-ADDR-HL strap at P0-P7 (it would otherwise also answer P8/P9).

### Part-list delta (v1.3 -> v2.0)

Added (reference designators chosen clear of v1.3's IC1-IC14, IC18, IC26-IC29, C1-C24, R2, RN5-RN8, JP1, PWR0,
U$1, X1 **and** of the fabricated card's IC15, see below):

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

Dropped from the CF card: X1 (bus connector, shared), **LED3 + R6 (DASP LED, Ken)**, **LED1 + R7 (PWR LED: v1.3
already has PWR0 + R2 330R)**. Everything through-hole. BOM: `memory-v2.0-bom.csv` (34 lines; v1.3 parts keep
their converted Eagle values, e.g. `74*32`, `C-US`).

## The fabricated v1.3 is not the tree's v1.3 (read this first)

`../v1.3` is converted from the tree's Eagle board, `eagle/v1.3/Memory V1.3.brd`. That file is an **earlier save** than
the card that was fabricated on 2025-06-27 (Fusion "Memory V1.3 v4": `eagle/v1.3/fab/Memory V1_2025-06-27.zip`,
gerbers + pick-and-place). Comparing the drill file and the copper of that zip with the converted board:

1. **IC26-IC29 (TMP registers) and RN5/RN6 sit OUTSIDE the board outline** in the tree board, unrouted. On the
   fabricated card they are on the board: IC26-IC29 in a column at the top edge (x 172.7, beside C14-C17), RN5/RN6
   along the bottom edge. Every v2.0 option puts them exactly there (`placements.FAB_MOVES`); every other v1.3 pad
   position matches a drill hole of the fabricated card (0 missing).
2. **The fabricated card has a 15th logic chip no schematic in the tree has: IC15, 74ALS11N** (pick-and-place:
   Eagle (151.13, 53.34) -> KiCad (168.85, 70.68), beside C19). Traced on the fabricated copper: gate 1 inputs =
   -LO-RAM (IC1.20), -HI-RAM (IC2.20), -ROM-CS (IC13.20); output 1Y (pin 12) = **IC5 pin 19**, the 74LS245's enable.
   So on the real card the data buffer is enabled only when one of the three memory chips is selected, not by -VMA
   as the tree schematic (and therefore v1.3 and v2.0) draws it. The other two gates are unused. This matters: with
   -VMA asserted in every microcode step (the M1 "hack"), the tree's wiring would drive the bus from undecoded blocks
   (e.g. the video card's $D000) during reads. **v2.0 as proven here inherits the tree's wiring; every option keeps
   IC15's footprint area free** (`placements.IC15_SPOT`, dashed box on User.Comments) so the fix can be added.
3. **Stale copper.** The tree board's tracks in the TMP area and along the bottom edge were routed for an earlier
   TMP placement. With IC26-IC29 where the fabricated card has them: 65 track/via items (1,300 mm; DATA1, 3, 5-8,
   12-15) reach no second pad and are dropped as dead copper, and 36 more collide with the TMP pads and are trimmed.
   The **reference board** (v1.3 + fabricated positions, no CF section) therefore keeps 947 of v1.3's 1,048 copper
   items and has 91 unrouted v1.3 connections (the four TMP registers are essentially unrouted). None of that is the
   CF section's doing; each option is measured against this reference.

**Recommendation:** if the Fusion "Memory V1.3 v4" design can still be exported, v2.0 should start from it (IC15,
the real TMP routing), not from the tree's older Eagle save. That is `BACKLOG.md`'s "overlay the 2025 gerbers" item.

## Placement options (not routed)

Coordinates are board mm (y down). The card stands on X1 in the cage, so **x = 195.55 is the card's free top edge**,
y = 10 and y = 124 its two free side edges. In all three options three CF chips sit in the **three empty IC slots**
below IC15 (right of the pre-placed caps C20/C21/C22, which were already on v1.3 with no IC beside them): IC34
(245), IC32 (175), IC33 (08), with R10-R13 between the rows, C27/C28 at the right ends and C29 above IC34; pin 1 at x 159.1 so v1.3's
DATA0 track (B.Cu, x 160.3) runs between pins 1 and 2 with clearance. No v1.3 copper is removed by any option
beyond the reference board. Airwire figures from DRC (straight-line, so only for comparison).

| | J2 | v1.3 parts moved (besides the six fabricated positions) | CF airwire | of which to J2 | bus -> CF chips |
|---|---|---|---|---|---|
| **A** | top edge, upper half (beside TMP registers) | none | ~3.3 m | ~1.05 m | ~1.4 m |
| **B** | y = 124 side edge, under the ROM | C23 (up 7.5 mm) | ~3.2 m | ~1.02 m | ~1.4 m |
| **C** | top edge, lower half (beside the CF chips) | none | ~2.8 m | ~0.48 m | ~1.4 m |

- **Option A** — `memory-v2.0-option-a-render-top.png`, `memory-v2.0-option-a-placement.png`. J2 vertical along the
  top edge at y 16.5-64.8, pin 1 at the bottom (data pins nearest IC34), beside IC26-IC29. IC30/IC31 under the ROM,
  RN9/J3/C30 in the line below them; JP2, R14 and the ACT LED in the top-edge strip below J2, ACT next to PWR0.
  Nothing of v1.3 moves. J2's shroud is 0.6 mm from IC26-IC29's sockets (tight, legal; their silk outlines touch).
  Longest IDE runs of the two top-edge options.
- **Option B** — `memory-v2.0-option-b-*.png`. J2 horizontal along the y = 124 edge under the ROM, pin 1 at the right
  end (data pins toward IC34); IC30/IC31 squeezed between v1.3's BADDR3-5 tracks and J2; C23 moves up 7.5 mm out of
  J2's way; RN9, J3, C30, R14 in the top-edge strip; JP2 just past J2's end. The adapter/ribbon leaves at a side
  edge of the card instead of the top. J2 is 0.1 mm (courtyard) from the edge.
- **Option C** — `memory-v2.0-option-c-*.png`. J2 vertical along the top edge at y 56-104, level with the CF chips:
  data pins just above IC34, DA0-2 level with IC32. Shortest IDE wiring (half of A/B). ACT LED, R14 and JP2 in the
  top corner; RN9/J3/C30 under the ROM as in A. Nothing of v1.3 moves. The TAODAN keep-low zone ends 0.6 mm short of
  PWR0 (5 mm LED), so this is the tightest option for the adapter overhang at J2's lower end.

Every option passes `gen_mem_v2.py check`: no new body overlaps, pads >= 0.5 mm from the edge, bodies inside the
outline, the IC15 spot free, and no tall part (LEDs, C30, JP2, J3, headers) in the TAODAN keep-low zone.

### DRC (copper items; cosmetic ones listed for completeness)

| | v1.3 | A | B | C |
|---|---|---|---|---|
| non-cosmetic violations beyond v1.3's | — | **0** | **0** | **0** |
| track_dangling | 17 | 3 | 3 | 3 |
| items_not_allowed (inherited) | 2 | 2 | 2 | 2 |
| unrouted connections (ratsnest) | 100 | 152 | 152 | 152 |
| silk_overlap | 24 | 37 | 36 | 39 |
| silk_edge_clearance | 4 | 6 | 4 | 4 |
| schematic parity items (all inherited Eagle values/fields) | 217 | 52 | 52 | 52 |

Unrouted is expected (the CF section is ratsnest only: 64 airwires; the rest are v1.3's, mostly the TMP registers).
The extra silk overlaps are IC26-IC29's Eagle reference texts over C14-C17 at the fabricated positions (+12) and a few
CF reference texts; the two extra silk_edge items in A are J2's shroud outline at the edge.

## The CF-to-IDE adapter

- **TAODAN CF-IDE40 V2.0** (70 x 63 mm, female 40-pin socket along a 70 mm edge) plugs straight onto J2 and stands
  **perpendicular to the card, out of the component side**, its lower edge ~9-10 mm above the card, overhanging each
  end of the 50.8 mm pin row by ~10 mm; +5 V from IDE pin 20 through JP2. Each option draws on User.Drawings (and on
  the silk of the render copy): the adapter strip (solid, 70 x 8 mm) and a **keep-low zone** (dashed: 12 mm past each
  end of the pin row, 7 mm either side of the header centre line) that must hold nothing taller than ~8 mm. Both sides
  are kept low because which way the adapter faces depends on its socket's key, not known until it is in hand. Only
  DIPs (assumed <= ~7.5 mm in sockets), disc caps and axial resistors are in the zones.
- **The card needs free space on its component side** when the TAODAN is used: 63 mm of adapter stands into the
  space of the next slot(s). Plan the card's slot accordingly (end slot, or empty neighbour slots).
- **SinLoon CF-to-IDE** (60 x 43 mm, male 40-pin) on a short ribbon: J2 is shrouded and at a free edge in every
  option, so the IDC plug fits and the ribbon leaves the card over the edge (top edge in A and C, side edge in B).
  No mounting holes for either adapter (Ken). Adapter power then from J3.

## Files

| File | What it is |
|---|---|
| `mem_v2_netlist.py` | **the delta** (single source): CF card v1.0 -> v2.0 reference map, dropped parts, shared nets, `check()`, `expected()` |
| `gen_mem_v2.py` | writes the schematic (`sch`), the option boards (`board`), trims broken v1.3 copper (`trim`), refills the planes (`refill`), checks the placement (`check`), makes review copies (`review`) |
| `placements.py` | the options (plain data), the fabricated positions `FAB_MOVES`, the reserved `IC15_SPOT` |
| `check_netlist.py` | the netlist proof: schematic = v1.3 + CF section, every board = schematic |
| `build.sh` | the whole pipeline; exit 0 = every gate passed |
| `memory-v2.0.kicad_sch`, `-sheet1..7.kicad_sch`, `.kicad_pro` | schematic (sheets 1-6 v1.3, sheet 7 CF) |
| `memory-v2.0-option-{a,b,c}.kicad_pcb` / `.kicad_pro` | the three placement options (ratsnest only) |
| `memory-v2.0-option-{a,b,c}-render-top.png` | 3D render, adapter zones and IC15 spot copied onto silk |
| `memory-v2.0-option-{a,b,c}-placement.png` | 2D plot: copper, silk, adapter zones, IC15 spot, airwires (light green) |
| `memory-v2.0-schematic.pdf`, `memory-v2.0-bom.csv` | schematic plot, bill of materials |
| `memory-v1.3-eagle.kicad_sym`, `.pretty/`, `sym-lib-table`, `fp-lib-table` | v1.3's converted libraries, copied (same nickname) |
| `reports/` | ERC (`.rpt`, `.json`, `erc-summary.txt`), netlist (`.net`), `netlist-proof.txt`, `base-summary.txt`, per option `option-X-drc.json`, `-drc-summary.txt`, `-placement-check.txt` |

## Rebuild

    hardware/cards/memory/kicad/v2.0/build.sh                 # ~2 minutes; OPTIONS="a c" for a subset

It reads `../v1.3` (through a scratch copy, so nothing is written there) and `../../../cf/kicad/v1.0/cf_netlist.py` +
`gen_cf.py` (read-only). Steps: schematic; ERC vs v1.3; the reference board; per option: board, trim, plane refill,
placement check, DRC with schematic parity, render + plot; netlist proof; PDF + BOM. To change the circuit edit
`mem_v2_netlist.py`; to change a placement edit `placements.py`; then re-run. Once the files are edited by hand in
KiCad, stop running the generator.

## Results (build of 2026-09-24)

- **Netlist proof: MATCH.** v2.0 schematic = v1.3 (52 parts, 166 nets) + CF section (21 parts, 27 own nets, 69 pins
  on 17 shared nets): 73 parts, 185 nets, 683 pins, 31 unconnected pins (8 v1.3 + 23 documented CF no-connects).
  The CF card's 27 dropped X1 pins are each on the same-named net of the memory card's X1. All three option boards
  equal the schematic pad for pad (`reports/netlist-proof.txt`).
- **ERC: 98 violations vs v1.3's 103** — exactly v1.3's Eagle-conversion residue, plus the designed-in one-pin
  `SRST` label (IC32 Q4, a probe point, as on the CF card), minus the six "isolated label" warnings of the labels that
  became global. Sheet 7: 0 text overlaps; sheet 1: one new text touch (the IO-ADDR3 global-label flag against the
  neighbouring -IO-ADDR-LD label at 2.54 mm pitch).
- **DRC:** no copper violation beyond v1.3's in any option; details above.

## Open questions for Ken

1. **The fabricated card** (section above): can the Fusion "Memory V1.3 v4" design be exported, so v2.0 starts from
   the real card? Otherwise, should v2.0 add IC15 (74ALS11: IC5 G = -LO-RAM AND -HI-RAM AND -ROM-CS) to the
   schematic? Its spot is kept free.
2. **Which option** (A, B or C)? Then routing (as the I/O v2.0 was routed from its chosen option).
3. **Adapter facing / J2 pin 1:** which side the TAODAN's board is on relative to the socket key; the zones keep
   both sides low, but the silk pin-1 orientation should be checked against the real adapter before ordering.
4. **J3 pinout** (1 +5 V, 2/3 GND, 4 n/c, floppy order) against the cable the adapter takes; fit JP2 only for
   adapters powered on IDE pin 20.
5. **Heights:** the keep-low rule assumes DIPs in sockets <= ~8 mm; check the sockets Ken uses (machined sockets are
   taller than stamped ones) for IC26-IC29 (A) or IC28/IC29/IC32-IC34 (C) under the adapter overhang.
6. **Slot:** with the TAODAN plugged straight on, the memory card needs free space on its component side (63 mm).
7. C20-C22 (v1.3's pre-placed caps at the three empty slots) now sit beside CF chips that also have their own
   C27-C29; keep both, or drop one set?
