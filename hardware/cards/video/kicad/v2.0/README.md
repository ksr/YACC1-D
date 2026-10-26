# video-v2.0 — KiCad design master for the video card

**The master since 2026-10-22. Ready to order since 2026-10-23 (re-reviewed, every re-review finding applied); not
ordered; gerbers exported 2026-10-24** with the board-layout rules' silkscreen (copper and drills as routed
2026-10-23; `video-v2.0-gerbers.zip`, what to upload: "Ordering" below). V2.0 is the v1.3 card (`../v1.3/`: 6845, IDT7134 text RAM,
the DOTS jumper, 12 MHz, both fonts in one character generator) plus a **graphics layer**, **every register on I/O ports
PA-PE** and **two PS/2 ports** on an ATmega328P with an **INT jumper**. The design note is `BACKLOG.md` "Video card
V2.0"; the theory `docs/cards/video-v2.md`; the ATmega's firmware `embedded/video-ps2`; the picture and the CPU
side `tools/vidsim.py --card v2.0`.

**Revised 2026-10-22 after the design review** (`hardware/cards/video/reviews/v2.0.md`, its status table at the top):
every HIGH and MEDIUM finding is in the circuit or the firmware, and two features were added - **direct mode** (with
GFX-ON = 0 the CPU owns the graphics RAM: a plain SRAM at any clock the machine runs) and the **text-only build** (the
graphics chips left off, a status bit saying so). **Re-reviewed 2026-10-23** (`hardware/cards/video/reviews/v2.0-r2.md`,
HIGH 0, MED 1, LOW 9, INFO 6; its status table at the top): the MD-60SM side-leg slots widened (R2-1), IC55's socket
clear of its neighbours (R2-2), the bus -RESET buffered (R2-3), the BOM, the README's statements, the silkscreen, the
timing test and the firmware; the rest are driver rules and bench measurements.

Unlike v1.x (Eagle conversions edited in KiCad) this design is **generated**: `v20_netlist.py` is the circuit,
`gen_v20.py` draws the schematic (since 2026-10-24 a root sheet and eight functional sheets with the nets drawn as
wires: "The schematic" below), builds the board and writes `BOM.md`; `build.sh` routes and checks it. Change the circuit in
`v20_netlist.py`, the placement in `gen_v20.py` (`PLACE`), then run `./build.sh` (KiCad 10, Freerouting 1.9 in `FRJAR`,
default `~/freerouting/freerouting.jar`, which opens a window while it runs; `SEEDS="..."` and `MP=` choose the
component orders and passes). `tools/eagle_to_kicad_all.py` never writes here (`MASTER` marker).

## The board

- **218.42 x 113.97 mm** (x 17.747-236.167): the blank V3.2 card's outline lengthened to the sequencer logic V2.1l's
  218 mm, so it needs the same slot space; X1 (DIN 41612) exactly where every card has it, copper keepouts round its
  two screws.
- **4 layers**, the v1.3 / memory card v2.0 stack-up and rules: In1.Cu a solid GND plane, In2.Cu a solid VCC plane, GND
  and VCC never routed (every power pin is a through-hole pad on its plane); signals 0.25 mm, clearance 0.2 mm, vias
  0.8 / 0.4 mm.
- **Placement** (`gen_v20.py` `PLACE`; pin 1 of every DIP at the top left, each 100 nF beside its IC's VCC pin):
  row A (top) the port decode, strobes, the inverters IC46 (beside the control register they mostly serve), the control
  register, status buffers, the PS/2 and graphics latches, WRQ and the video driver IC27; on the left the 600-mil parts (IC15 text RAM, IC17 6845, IC39 62256, IC25 28C64) and IC18 with SV3 /
  RN2; row B the graphics address muxes, display latch and shifter, the ATmega, with the GD pull-ups RN3 standing between
  IC38 and IC42; under IC42 / IC43, on its side, the direct-mode read buffer IC55 (the band under the muxes is left to
  the routing); row C the text pipeline and the gates, with the text-only pads R25 / R26 in the gaps beside IC1; row D
  the clock chain (IC28, IC21, IC20 with Q2, SV4), the remaining gates (IC32 among them, beside the counter whose QC and
  RCO it ORs) and IC54 (turned round, beside J4); the right
  edge DB9 (X2), RCA (J1), the keyboard (J2) and mouse (J3) Mini-DINs with their faces at the board edge, F1, the FTDI header J4 (a legend
  at every pin), the PWR LED. `gen_v20.py place` checks that no two courtyards overlap and, since the re-review (R2-2),
  that every DIP **socket** fits: each socket's outline (the pin rows + 1.3 mm at the sides, the end pins + 1.9 mm at
  the ends: the widest stamped sockets) clear of every other socket and of every other part's pads and body. The
  closest are IC55 (on its side between IC42 above and IC19 / IC1 below) with 0.02 mm to IC42's and 0.10 to IC19's /
  IC1's, IC55 / C59 0.17, IC49 / R12 0.17, IC25 / IC39 0.18 mm; with turned-pin sockets (1.27 mm end walls) IC55 has
  ~0.65 mm. RN3 and C59 stand 0.3 mm left of the middle of their gap for it.
- **Silkscreen** (R2-9; the board-layout rules since 2026-10-24, below): `gen_v20.py silk` writes every legend afresh
  and places it and every reference clear of the other silk, the pads, the edge and every part's body, its own
  included (`silk_texts()`, `silk_place()`). Each IC's type stands on the reference's line ("IC30 74LS138"); the
  jumpers and the LED carry their function and the jumpers each position's meaning. The jack legends "KBD (PURPLE)" and
  "MOUSE (GREEN)" stand turned beside each jack's body; the Mini-DIN outline is broken round its side-leg pads and stops
  short of the board edge. The card's name stands in the band under the graphics muxes.

## The board-layout rules (2026-10-24)

The rules for every YACC1 board (switches, buttons, LEDs and outside-cable connectors on the front edge, the edge
farthest from the bus connector; every reference readable with the parts fitted, never under a chip, socket or module,
an IC's type beside it; every switch, button and LED labelled with its function, each position of a switch with what
it selects) came after this board was routed and before it was ordered. V2.0 takes them on the **silkscreen only**:
no part moves, the copper and the drills are the route of 2026-10-23 (`ed7c060`, order 5, 285 vias).

| Rule | On this board |
|---|---|
| front edge | the DB9 X2, the RCA J1, the PS/2 jacks J2 / J3 and the PWR LED stand at the right-hand edge, opposite X1. The FTDI header J4 (the ATmega's programming port) stays where it is, 24 mm in from that edge, with its pin legend: moving it would mean a new route |
| IC type beside the reference | all 40 ICs, on one line with the reference ("IC30 74LS138"): the value of each, shortened where it is long - IC17 **6845** (HD68B45SP / MC68B45P), IC25 **28C64** (AT28C64B-15), IC49 **ATmega328P** (ATmega328P-P). Above the IC where there is room (29), else below it (7: IC1, IC20, IC21, IC25, IC32, IC45, IC54), else turned in the gap beside it (IC19, IC28, IC49 on the left, IC53 on the right) |
| no reference under a part | every text is kept off every part's body, its own included: a DIP's body is the outline of the widest stamped socket (`socket_check`: the pin rows + 1.3 mm, the end pins + 1.9 mm), X1's the DIN 41612 housing (its silk, pads and 2.5 mm past its ends), J1's its outline and pads. R10, R25, R26 and R27 had their references inside their own outline: they now stand beside it. X1's reference left the housing's end (now at the top-left corner, x 18.9, y 16.1); J1's, hidden by the RCA library footprint, is shown left of the jack. Checked by the texts' ink against every body and socket outline: before, 37 references stood on one - 26 capacitors' on a neighbouring IC's socket wall, IC1's on IC55's socket, IC19's, IC25's and IC54's on their own socket, J2's on J1, R15's and RN3's on IC25's / IC38's socket, R10's, R25's, R26's and R27's on their own body; now none |
| functions and positions | **LED1 PWR**. **JP2 DOTS**, "ON=8 OFF=6" (fitted: 8 dots a character, 64 x 24 with graphics; open: 6 dots, 80 x 24). **JP3 INT-EN**, "ON: PS/2 -INT" / "OFF: NO -INT" (fitted: IC27/D's open collector drives the bus -INT; open: the card never touches -INT). **SV3 BLOCK**, "A15" .. "A12" beside the pairs 1-2 .. 7-8 and "ON=0" (each pair sets the address bit the board select IC18 compares, fitted = 0, open = 1 through RN2; $D000 = 5-6 only). **SV4 DOTCLK**, "XTAL" over pin 1 and "XTAL/2" over pin 3 (1-2: DOTCLOCK the crystal; 2-3: half of it). The meanings are those of `v20_netlist.py` and `docs/cards/video.md` (sections 3.1, 3.4) and `docs/cards/video-v2.md` |
| text size | every reference and legend 1.0 mm high with 0.15 mm strokes, JLCPCB's standard legend (the card's name 1.5 mm); "DOTS", "INT-EN" and "TEXT-ONLY" were 0.8 mm. X1's library pin numbers "1" and "32" stay 0.8 mm (0.15 mm strokes; at 1.0 mm "32" meets the housing's outline), JLCPCB's high-precision legend size |

`gen_v20.py silk` places the texts by their ink (not KiCad's taller text box), 0.15 mm from other silk (1.0 mm after an
IC's label), 0.2 mm from pads, 0.4 mm from the edge; an IC's label goes above it, else below, else turned in the gap at
its right, then its left, along that side and within its length. A second run leaves every text where it is.

**Proofs (2026-10-24)**, the silkscreen placed again on the committed board and nothing else rebuilt (no Freerouting,
no `build.sh`):

| Check | Result |
|---|---|
| the board, item by item (pcbnew: 120 footprints' place, orientation, value and footprint; 1,040 pads with their nets, sizes and drills; 5,069 tracks and vias; the zones and keepouts; the outline) | **identical**; the file's changes are the silkscreen texts and the reference fields' places and sizes |
| Gerbers (the commands under "Ordering"), against the export of 2026-10-23 | **only `video-v2.0-F_Silkscreen.gbr` differs**; F_Cu, In1_Cu, In2_Cu, B_Cu, F_Mask, B_Mask, B_Silkscreen, Edge_Cuts, the PTH and NPTH drill files, both drill maps and the job file are identical apart from their date lines |
| `tools/kicad/compare_netlists.py` (schematic vs board) | **MATCH, 216 of 216** net groups |
| `gen_v20.py verify` | **PASS**, 189 key connections |
| `gen_v20.py place` | 120 footprints clear; **sockets PASS** (40), the closest IC42 / IC55 0.02 mm as before |
| DRC (`reports/drc.json`) | 0 unconnected, schematic parity 0, no copper findings; **silk_overlap 0, silk_over_copper 8, silk_edge_clearance 8** (J1's, X1's and X2's library outlines, as before), text_height / text_thickness 0 |
| `v20_netlist.py`, the schematic | unchanged |

## The schematic (redrawn 2026-10-24)

The schematic is drawn by function: the root sheet `video-v2.0.kicad_sch` holds one sheet symbol per block, and each
block is a sheet of its own whose parts are placed by ELK and whose nets are wires. Until 2026-10-23 it was one A0
sheet of functional boxes in which every pin was a short stub to a net label or a power symbol (no pin was wired to
another). The circuit, the board and the fab files are unchanged by the redraw (the proofs below).

| Sheet | File | Paper | What is on it |
|---|---|---|---|
| 1 (root) | `video-v2.0.kicad_sch` | A1 | the eight sheet symbols, a pin and a net label for every net of each sheet, the list of sheets |
| 2 Bus and ports | `video-v2.0-bus.kicad_sch` | A3 | X1 (rows a, b, c), the port decode IC30, the strobes IC31/A-D and IC32/A, the control register IC33, the status IC34, R27 |
| 3 CRTC | `video-v2.0-crtc.kicad_sch` | A4 | the 6845 IC17, its -CS (IC1/A) and E (IC26/C) |
| 4 Text | `video-v2.0-text.kicad_sch` | A2 | the board select IC18 with SV3 / RN2, IC20/E,F (NADDR11, VMA), IC19/B (-CER), the text RAM IC15, the code latch IC23, the character generator IC25, the shifter IC24, the delays IC22, IC26/A,B |
| 5 Clocks | `video-v2.0-clock.kicad_sch` | A3 | the oscillator Q2, R8, R9, IC20/A-D, the divider IC21 and SV4, the character counter IC28 with R10, JP2, R15, IC19/C (CHARCLOCK), IC26/D (WEPH) |
| 6 Graphics | `video-v2.0-gfx.kicad_sch` | A1 | the muxes IC35-IC38, the RAM IC39, RN3, IC40, IC41, IC55, the display latch IC42 and shifter IC43, WRQ (IC44), -WE (IC45), IC46/A-C, IC47/B,C, IC1/B, IC19/A,D, IC32/C,D, IC48/C, IC54/A, the text-only pads R25 / R26 |
| 7 Video out | `video-v2.0-video.kicad_sch` | A3 | the combine IC1/C,D, IC47/A, IC46/D,E, IC32/B, IC48/A,B; the drivers IC27/A-C, R11, R12, X2, J1 |
| 8 PS2 | `video-v2.0-ps2.kicad_sch` | A2 | the ATmega IC49 with Y1, C55, C56, R16, C57 and J4; the latches IC50-IC52, the flags IC53, IC47/D, IC54/B, IC27/D, JP3; the reset path IC54/C, IC27/E,F, R21; F1, J2, J3, R17-R20, R22-R24 |
| 9 Power | `video-v2.0-power.kicad_sch` | A3 | every power unit, the decoupling and C16, R2 / LED1, the spare gates IC46/F and IC54/D, the PWR_FLAGs |

**How it is drawn** (`gen_v20.py sch`: the blocks in `SHEETS`; the drawing in `tools/kicad/sch_wire.py`, which the
memory card v2.0's sheet 7 uses too; modelled on the P8X project's ELK-wired sheets). Each symbol unit is an ELK node
whose box holds its body, its fields and its stubs; a net with two or more pins on a sheet that is neither power nor a
bus signal (X1's) is a wire, run from the pin on a symbol's right-hand edge (a driver first) to the others, so a sheet
reads left to right. A wired net that also reaches other sheets gets a hierarchical label of its own on the wiring,
on the left where another sheet drives it and on the right where this one does; the other wired nets carry their name
once, on a short stub. The bus signals, power and a sheet's one-pin nets keep the stub to a label or a power symbol.
Everything is on the 1.27 mm grid; after ELK every route is pinned to its pins and checked (no point shared by two nets
but a plain crossing, no wire through a pin, a label or a symbol), and a sheet falls back to labels on every pin if no
spacing routes it cleanly (none does). ELK's layering is chosen per sheet: of four, the one that fits the smallest
paper, then the fewest wires. The output is the same on every run. It needs node and elkjs (`cd tools/kicad && npm
install`; `tools/setup_check.py` checks both).

**Net names.** The board and its Gerbers (their X2 net attributes) carry the flat sheet's net names, `/NAME`. KiCad
gives a net that name only from a label on the root sheet, so every net of a sub-sheet ends in a hierarchical label,
each is a pin of the sheet's symbol on the root, and a local label at each pin names the net. Above the dashed line in
a sheet symbol: the nets it shares with other sheets (left: it reads them; right: it drives them). Below it: the nets
drawn on that sheet only, with a pin on each side - KiCad's ERC counts a root label as connected only when another
label of its name stands on the root sheet (138 label_dangling errors otherwise).

| | Before (one A0 sheet) | After (root + 8 sheets) |
|---|---|---|
| nets drawn as wires | 0 | **153** (895 wire segments, 205 junctions) |
| stubs (a pin to a label or power symbol) | 945 | 534 |
| labels | 669 local | 413 hierarchical on the sheets; 491 local at the 491 sheet pins of the root |
| power symbols | 276 | 276 |

**Proofs (2026-10-24)**, the schematic redrawn and nothing else rebuilt (no Freerouting, no `build.sh`):

| Check | Result |
|---|---|
| `gen_v20.py checknet` (the schematic's netlist vs `v20_netlist.py`) | **MATCH, 216 nets** |
| `tools/kicad/compare_netlists.py` (schematic vs board) | **MATCH, 216 of 216** net groups (`reports/netlist-compare.txt`) |
| net names, pad by pad | the schematic names all 1034 pads on nets exactly as the board does (`/NAME`, `VCC`, `GND`, `unconnected-(...)`) |
| `gen_v20.py verify` | **PASS**, 189 key connections |
| DRC (`reports/drc.json`) | 0 unconnected, **schematic parity 0**; silk_edge_clearance 8, silk_over_copper 8, as before |
| ERC (`reports/erc.json`) | **no errors, no warnings** (before: endpoint_off_grid 6, the PWR_FLAG wires) |
| the board file | only the footprints' `(path ...)` lines differ: 105 now carry the sheet's UUID before the symbol's, and the 15 multi-unit parts, which had no link, have one (`gen_v20.py link`: the links that "Update PCB from Schematic" would set, written as text, nothing else touched) |
| Gerbers | re-exported with the commands under "Ordering" into a scratch folder: all 14 files equal `gerbers/` apart from their date / time lines; `gerbers/` and `video-v2.0-gerbers.zip` were as exported 2026-10-23 (exported again 2026-10-24 for the silkscreen: "The board-layout rules") |

To redraw the schematic only (the board stays): `gen_v20.py sch`, export the netlist
(`kicad-cli sch export netlist --format kicadsexpr -o reports/netlist.net video-v2.0.kicad_sch`), `gen_v20.py checknet
reports/netlist.net`, then `gen_v20.py link reports/netlist.net video-v2.0.kicad_pcb` (the links only) and the proofs
above. `build.sh` remakes the board as well (`gen_v20.py board` sets the same links from the netlist).

## Results (`./build.sh`, 2026-10-23, after the re-review)

| Check | Result |
|---|---|
| schematic netlist vs `v20_netlist.py` | **MATCH, 216 nets** (`gen_v20.py checknet`); `v20_netlist.check()` OK: 120 parts, 943 connections, no pin on two nets, the text-only check (exactly GDOT, WRQ, TXTONLY; every left-off IC has an `OUTPUTS` entry) |
| netlist proof, schematic vs board (`tools/kicad/compare_netlists.py`) | **MATCH, 216 of 216 net groups** |
| placement | 120 footprints, no courtyard overlaps; **sockets PASS**: 40 DIP socket outlines (+1.3 mm sides, +1.9 mm ends) clear of each other and of every part's pads and body, the closest IC42 / IC55 0.02 mm, IC19 / IC55 and IC1 / IC55 0.10, IC55 / C59 0.17, IC49 / R12 0.17, IC25 / IC39 0.18 (`gen_v20.py place`) |
| route (Freerouting 1.9, component order 5, 60 passes; the re-review rebuild of 2026-10-23) | **0 unrouted, 285 vias, 22.1 m of 0.25 mm track** (F.Cu 10.1 m, B.Cu 12.0 m). Orders 6 (331 vias) and 5 completed, order 4 left 2 unrouted; earlier runs of a placement with IC55 0.04 mm lower and R10 0.5 mm left (orders 6, 5, 3, 4) left 1-6 unrouted or ran past the watchdog on a machine busy with other jobs. A repeat of order 5 on the same files left 2 unrouted (Freerouting is not repeatable here), so the board is that build's route; the silkscreen texts were then placed again by `gen_v20.py silk` (texts only, after keeping them out of other parts' bodies) and the reports and checks of `build.sh` run on it. Before the re-review: order 6, 328 vias (`560977b`), order 3, 308 vias (`fc71ec4`) |
| DRC | **0 unconnected, no clearance / short / dangling findings**, schematic parity 0; cosmetic only: **silk_overlap 0** (40 before R2-9), **silk_over_copper 8** (89 before: J1's and X2's library outlines over their own pads), **silk_edge_clearance 8** (10: X1, X2, J1 at the edge), text_height / text_thickness 0 (2 / 3) |
| planes | In1.Cu GND, In2.Cu VCC, one zone each over the whole board, filled as one piece (GND 20,058 mm2, VCC 20,031 mm2 of copper after the antipads) besides 7 / 4 pad-sized islands (at most 2.5 mm2) as before; every GND / VCC pin reaches its plane (0 unconnected with no power tracks) |
| ERC | endpoint_off_grid 6 (cosmetic), nothing else; since the redraw of 2026-10-24 none |
| `gen_v20.py verify` | **PASS**: 189 key connections pin by pin in the schematic and on the board (the port decode and strobes, the 6845 on PA/PB, the card ID and the TEXT-ONLY bit, the mux select NMUX and its QC OR RCO, the slot logic and direct mode (WRQ preset, WEPH2, -WE, the -OE term, IC40 on -WE, IC41 / IC55 enables, RN3), the text-only pads, the 28C64's wiring, the combine, the DOTS divider and font select, the ATmega's bus interface with BUSY / SRC swapped, -INT = INTREQ AND FULL, the reset through IC54/C and IC27/E,F, the PS/2 lines and F1; since R2-14 also the MEMWR path, IC44.1, FULL's clear / clock / output, IC40's A / Y pins and the jacks' shield pads), 4 copper layers, the two planes, no track on GND/VCC |

`./build.sh` takes 40-90 minutes with up to four component orders in parallel (`SEEDS="6 5 4"`): Freerouting's passes take
several minutes each on this board, and a completed route is then optimised for up to 40 minutes; the watchdog
(`WATCHDOG=`, seconds) stops runs that go on longer (on a machine busy with other jobs give it `WATCHDOG=10800`).

## Parts V2.0 adds (references continue v1.x's; IC2, JP1, R13, R14 are gone)

| Ref | Part | Job |
|---|---|---|
| IC30 | 74LS138 | port decode: Y2..Y7 = PA..PF when IO-ADDR3 = 1 |
| IC31, IC32 | 74LS32 | port strobes (PC write/read, PD write/read, PE read); IC32/B text OR graphics, IC32/C QC OR RCO, IC32/D WEPH OR NOT GFX-ON |
| IC33 | **74HCT273** | control register, OUT PC: PLANE0-2, CPAGE, DPAGE, TEXT-OFF, GFX-ON, XOR (cleared by -RESET) |
| IC34 | 74LS244 | card status, IN PC: DOTS, VSYNC, DE, TEXT-ONLY, ID 0101 |
| IC35-IC38 | 74LS157 | graphics RAM address: the CPU (I1, NMUX = 1) or the display (I0, NMUX = 0) |
| IC39 | 62256 (AS6C62256-55) | graphics RAM, two 16K pages |
| IC40 | **74HCT244** | write buffer DATA -> GD, enabled by the RAM's -WE (GWE) |
| IC41 | **74HCT374** | slot-mode CPU read latch GD -> DATA (loads on QC's rise; enabled with GFX-ON = 1) |
| IC55 | **74HCT244** | direct-mode read buffer GD -> DATA (enabled with GFX-ON = 0) |
| RN3 | 10k x 8 | GD0-7 pull-ups: in direct mode nothing drives GD between accesses |
| IC42, IC43 | 74LS374, 74LS166 | display latch (CHARCLOCK) and graphics dot shifter |
| IC44 | 74LS74 | A: WRQ, a CPU write pending, sampled on CHARCLOCK, preset while GFX-ON = 0; B: held cleared, its Q is IN PC bit 3 (0 = graphics fitted) |
| IC45 | 74LS20 | A: the RAM's -WE = NAND(WRQ, NMUX, WEPH2, GWR); B: IC55's enable = NAND(GSEL, MEMRD, NOT GFX-ON) |
| IC46, IC47, IC48 | 74LS04, 74LS08, 74LS10 | inverters (NOT GFX-ON among them), graphics select / write / FULL clear, XOR term, the video NAND3 and IC41's enable |
| IC54 | **74HCT08** | A: the RAM's -OE term NMUX AND GRDOE; B: -INT = INTREQ AND FULL; C: the bus -RESET buffered for IC27/E (RESETB, R2-3); D spare |
| IC49, Y1 | ATmega328P, 16 MHz | the PS/2 controller (`embedded/video-ps2`), C55/C56 22 pF |
| IC50, IC51, IC52, IC53 | 74LS374, **74HCT374**, 74LS244, **74HCT74** | PS/2 data latch (IN PE), command latch (OUT PD), status (IN PD), FULL/BUSY |
| J2, J3 | **Same Sky MD-60SM** | keyboard, mouse (R17-R20 4.7k pull-ups); +5 V through F1 |
| F1 | Bourns MF-RHT050 | 0.5 A resettable fuse in the PS/2 +5 V (PS2VCC) |
| J4 | 1x6 header | FTDI: GND, CTS, (VCC not connected), TXD, RXD, DTR -> C57 -> reset |
| R16, R21 | 10k, 4.7k | the ATmega's reset pull-up; RESETH, between IC27/E and IC27/F |
| R22, R23, R24 | 10k | LDDATA and RDCMD pull-ups, INTREQ pull-down (defined while the ATmega is in reset or its bootloader) |
| R25, R26 | 1k | **text-only build only**: GDOT and WRQ pull-downs |
| R27 | 10k | TEXT-ONLY pull-up (IN PC bit 3 = 1 when IC44 is not fitted) |
| JP3 | 1x2 header | INT-EN: IC27/D's open collector to the bus -INT |
| C30-C54, C58, C59 | 100 nF | decoupling, one per new IC (C54 the ATmega's AVCC) |

Changed v1.3 parts: IC25 a 28-pin **AT28C64B-15** in place of the 2732 (below); IC1 (74ALS08) the 6845 -CS (PA OR PB),
WSLOT and the dot gates; IC19/A the window-read NAND, IC19/D NMUX; IC26/C E = -IO-RD XOR -IO-WR, IC26/D QA XOR QB;
IC27/D INTG -> -INT, IC27/E,F the bus -RESET to MRST (IC27/E's input through IC54/C, an HCT08 section used as a
buffer: R2-3); IC17 RS = IO-ADDR0, R/-W = -IO-WR, -CS from IC1/A; C16 47 uF.
Spare after all changes: IC46/F (input on GND), IC54/D (inputs on GND), IC38's fourth section (both inputs on GND);
every other gate is used once (`v20_netlist.check()`: no pin on two nets; ERC: no input unconnected). Pin by pin:
`v20_netlist.py`.

## The design review's fixes in the circuit (2026-10-22)

| Finding | In the circuit |
|---|---|
| V2-1 | SRC on IC49 pin 19 (PB5, Optiboot's LED pin), BUSY on pin 17 (PB3); the firmware's two pin numbers swapped. During the bootloader PB5 drives SRC, an output only the ATmega drives (IC52's input) |
| V2-2 | J2 / J3 footprint `MiniDIN6_MD-60SM`, drawn from the Same Sky data sheet (below) |
| V2-4 | the muxes' select from QC OR RCO (IC32/C, then IC19/D with GFX-ON): the display address is held until RCO has fallen, the edge IC42 takes the display byte on |
| V2-5 | IC40 (the write buffer) enabled by GWE, the RAM's -WE: it drives GD only while the RAM's outputs are off |
| V2-6 | D1 removed: the bus -RESET reaches MRST through IC27/E and IC27/F (7416, open collector, R21 4.7k between them); the bus line only ever pulls MRST low |
| V2-7 / V2-8 | -INT = INTREQ AND FULL (IC54/B into IC27/D): released the moment the CPU reads PE, and released while the ATmega is in reset (FULL is cleared by -RESET); R22 / R23 pull LDDATA and RDCMD high, R24 pulls INTREQ low |
| V2-9 / V2-12 | IC33 74HCT273, IC40 74HCT244, IC41 74HCT374, IC51 74HCT374, IC53 74HCT74 (and IC54, IC55 HCT): no LS input load on DATA0..7 left on the card beyond the 6845 and the text RAM, and rail-to-rail levels into the ATmega |
| V2-10 | IC25 a 28-pin socket for an **AT28C64B-15** (150 ns): the 2732's pins + 2; A12 (2), A11 (23), A9 (24), -CE (20), -OE (22) on GND, -WE (27) on VCC, A10 (21) = DOTS (the font), pins 1 and 26 open. Image `firmware/video/chargen-v20.bin` (8K: the v1.3 fonts at $0000, a copy at $1000), burned like the ROM: `minipro -p AT28C64B -u -P -w`. It also saves ~80 mA against the NMOS 2732 |
| V2-11 | the 6845 grade in the BOM: the B grade, HD68B45SP or MC68B45P (no circuit change; the grade letters corrected by R2-7) |
| V2-16 | C18 at the 6845's VCC (pin 20), C49 at the ATmega's pins 7 / 8, C22 at the 74LS90's pin 5; C16 47 uF |
| V2-17 | F1, a 0.5 A PTC, in the PS/2 +5 V |
| V2-20 | the FTDI header's legend: one 1 mm label per pin, "1 GND (BLK)" first |
| V2-21 | `BOM.md` (`gen_v20.py bom`) |

## Direct mode: the CPU owns the graphics RAM while GFX-ON = 0

GFX-ON (control bit 6, OUT PC) used to switch only the display combine; the RAM was time-shared with the display
whether the layer was shown or not, so every graphics access was limited to a CPU clock of about 1.8 MHz (review V2-24).
Now GFX-ON also chooses how the RAM is run:

| | GFX-ON = 1: **slot mode** (the layer shown) | GFX-ON = 0: **direct mode** (the layer hidden) |
|---|---|---|
| address (NMUX = NAND(QC OR RCO, GFX-ON)) | CPU in counts 8-11 (10-11), display in 12-15 | the CPU's, all the time |
| -WE (IC45/A: NAND(WRQ, NMUX, WEPH OR NOT GFX-ON, GWR)) | counts 9-10 of a slot whose start saw the write | NOT GWR (WRQ preset by GFX-ON = 0, the other two terms forced high) |
| the RAM's -OE (WSLOT = WRQ AND NMUX AND GRDOE) | off while a write is pending in the CPU half | on only while the CPU reads the window |
| the byte to the bus | IC41, the latch loaded on every QC rise (enabled by NAND(GSEL, MEMRD, GFX-ON), IC48/C) | IC55, a buffer straight from GD (enabled by NAND(GSEL, MEMRD, NOT GFX-ON), IC45/B) |
| the picture | text and graphics combined | text only (GDG needs GFX-ON, as before) |
| CPU clock for the window | up to ~1.8 MHz | anything the machine runs (below) |

A 74HCT244 bypass was chosen over making IC41 a transparent latch: a 74HCT373 with its LE held open in direct mode would
need, in slot mode, an LE pulse that closes before the muxes switch to the display address; derived from the counter
it closes on the same dot edge as the switch, a hold race at the corners like V2-4's, and an LE open for the whole CPU
half would pass the settling RAM output to the bus for ~150 ns of every character. The buffer leaves the slot path exactly
as it was. RN3 holds GD high in direct mode when neither the RAM nor IC40 drives it (no floating CMOS inputs on IC41,
IC55 and the RAM).

**Timing against the machine** (`tests/video/v20_timing.py`, in `make check`, reads the microcode image
`firmware/microcode/ucode-generator2/test.hex`): all 59 `-MEM-WR` strobes are one step (two clocks) long with the address
(ADDR-REG-ID) and the data source unchanged one step before and one step after, and the address register is neither
counted nor loaded around them; no `-MEM-RD` is next to a `-MEM-WR`; the shortest read window, from the address becoming
stable to the edge that takes the byte, is one step (JSR). With the maxima of the parts (74LS: TI, 25 °C; 74HCT: NXP,
25 °C and 85 °C; the register cards' SN74HC244N / SN74HC193N: TI, the HC193 at 85 °C assumed 1.25 x its 25 °C figures
(To verify); the AS6C62256-55's tAA 55, tOE 30, tWP 45, tDW 25, tAS = tWR = tDH = 0). Since the re-review (R2-5) every
read window is classed by how its address reached the bus at the window's first edge:

| read window (margin, ns: 25 °C / 85 °C) | 1 MHz (a step 2000 ns) | 6 MHz (a step 333 ns) |
|---|---|---|
| one step, the register **selected** in that step (pipeline 28 + 74LS139 38 + HC244 enable 38 / 48: address 104 / 114; the RAM's -OE 194 / 209; the byte at the destination with the bus and its set-up 274 / 295) | 1726 / 1705 | **59 / 38** |
| one step, the register **counted** at that edge, the count staying inside the window (the 74LS32 count gate, the HC193 carry to A8-A10, the HC244: address 183 / 218) - only the code fetch (PC), a pop (SP: RET, IRET, POPR) and BRVR's second vector byte | 1698 / 1657 | 31 / **-10** |
| one step, **counted into** the window (A11-A15 change: three carries, then the board-select path) - the same records | 1617 / 1563 | **-50 / -104** |
| two steps or more, any address path (LDAVR, POP, LDTI, LDR, LDZ ...) | >= 3563 | >= 230 |

| write | 1 MHz | 6 MHz |
|---|---|---|
| -WE width (step less the 78 ns -WE path) against tWP 45 | 1922 ns | 255 ns |
| data at the RAM (IC40 enabled 30 ns after -WE) to -WE's rise, against tDW 25 | 1892 ns | 225 ns |
| address set-up / hold (tAS, tWR 0) | stable 2000 ns before, 1922 ns after | stable 333 ns before, 255 ns after |

So -WE straight from the strobe needs no trimming: the microcode never moves the address or the data within a step of a
write. The read of a selected register alone would allow about 6.8 MHz (85 °C); the counted one-step windows fail at
6 MHz, so the software keeps them out of the window (the rules below), and the test fails if a window the rules permit
has a negative margin. The card is not the limit: the machine's one-step memory windows with the 28C64 ROM fail first,
at about 6 MHz (review M-2, the same count effect on the main memory card).

**The software rules for the window $D800-$DFFF** (the ROM / OS driver; `tests/video/v20_timing.py` checks the timing
side of 1-3):

1. **No code in the window**, at any clock (a fetch reads through a counted PC).
2. **At 6 MHz: no stack in the window** (RET, IRET, POPR read a byte through SP one step after counting it).
3. **At 6 MHz: no BRVR vector table in the window** (BRVR Rn reads the vector's second byte one step after counting Rn).
4. **Above ~1.8 MHz the window only in direct mode** (GFX-ON = 0; slot mode's limit, V2-24).
5. **Never GFX-ON = 1 in 6-dot mode** (IN PC bit 0 = 1): the driver refuses it (R2-4) - the 6-dot slot read has ~2 ns of
   set-up at the corners and the 6-dot write pulse no width (V2-13); the layer is never shown there anyway.
6. **The instruction that writes PC does not access the window** (below), and GFX-ON is switched in vertical blanking
   (IN PC bit 1), so the two pipeline bytes latched in direct mode ($FF) do not show as a 16-dot flash (R2-11).
7. **IN PE only after IN PD showed FULL = 1** (the PS/2 data latch; `embedded/video-ps2`, R2-10).

**Switching modes** (OUT PC): IC33 takes the new value at the end of the -IO-WR strobe; every memory strobe in the
records that write a port addresses PC (test 4), so no window access can meet the switch unless code runs from the
window (it must not). Entering slot mode, WRQ stays preset until the next CHARCLOCK (at most one character, 667 ns); a
window write that started in that time could open -WE mid-slot. **Rule: do not access the window in the instruction that
writes PC** - at 1 MHz the next instruction's first window access comes at least 6 us later; in slot mode the 1.8 MHz
limit applies anyway. Leaving slot mode takes effect at once (WRQ preset, the address held).

**Clock limits**: graphics hidden (GFX-ON = 0) - limited only by the rest of the machine (~6 MHz); graphics shown
(GFX-ON = 1) - ~1.8 MHz for window accesses (review V2-24). The text RAM (dual port) and the ports have no such limit
(the 6845 needs the B grade, HD68B45S / MC68B45, above 1 MHz, V2-24, R2-7). After a reset GFX-ON = 0: the window is in
direct mode. In 6-dot mode the layer is never shown, and the driver refuses GFX-ON = 1 there (rule 5), so the slot mode's
6-dot read and write margins (V2-13, R2-4) never arise.

## The text-only build (the recommended first build)

Leave off the graphics parts and fit two resistors; everything else is the same board:

| Left off | Fitted only in this build |
|---|---|
| IC35-IC38 (74LS157), IC39 (62256), IC40 (74HCT244), IC41 (74HCT374), IC42 (74LS374), IC43 (74LS166), IC44 (74LS74), IC45 (74LS20), IC55 (74HCT244), RN3; their capacitors C35-C45, C59 | **R25** 1k (GDOT to GND: the graphics dot input of IC1/D), **R26** 1k (WRQ to GND: IC1/B's input) |

`v20_netlist.text_only_check()` (run by `check()`, so by every build) lists every net a left-off part drives into a
fitted one: exactly GDOT and WRQ (the two pull-downs) and TEXT-ONLY (the status bit, by design), besides the 3-state
outputs of IC41 / IC55 onto DATA0..7, which an absent chip simply releases. R25 and R26 must not be fitted with the
graphics chips: 1k would load IC43's and IC44's outputs.

**IN PC bit 3 = TEXT-ONLY**: IC44's second flip-flop is held cleared (-CLR on GND), so with IC44 fitted its Q drives bit 3
low; without it R27 (always fitted) pulls it high. The card ID stays $5x either way: a full card reads bit 3 = 0, as
before; a text-only card reads 1. The ROM / OS reads it once at reset and leaves GFX-ON at 0 on a text-only card (the
window then reads the floating bus and writes go nowhere; `vidsim.V20Card(text_only=True)`).

**Bring-up order**: build text-only first (text RAM, 6845, the ports, PS/2), prove it on the bench, then fit the
graphics chips and remove R25 / R26.

## The Mini-DIN jack: Same Sky MD-60SM (V2-2)

**Buy: Same Sky (formerly CUI Devices) MD-60SM**, a 6-pin right-angle shielded through-hole Mini-DIN jack, in production,
stocked by the large distributors. The footprint (`video-v2.0-local.pretty/MiniDIN6_MD-60SM.kicad_mod`, written by
`gen_v20.py`) is drawn from the data sheet "SERIES: MD-SM", rev 1.09 of 2024-09-12, page 3, "Recommended PCB Layout, Top
View (Date Codes after 03/03/2022)". Parts with an older date code have another pattern: check the date code on the
reel / bag before soldering. The review's check list:

1. **Pins and drills**: six 0.9 (+0.1/-0) mm holes - pins 4, 2, 1, 3 in a row 8.5 mm behind the mating face at -3.4,
   -1.3, +1.3, +3.4 mm (6.8 and 2.6 mm spans), pins 6 and 5 11.0 mm behind it at -3.4 / +3.4; drilled 1.0 mm, 1.6 mm pads.
2. **View**: the drawing is a top (component side) view, as the footprint.
3. **Numbering**: looking into the jack pins 6, 4, 2 are on the left and 5, 3, 1 on the right - the PS/2 face numbering
   (1 data, 3 GND, 4 +5 V, 5 clock; 2, 6 unused). Confirm with a meter on the first jack before soldering.
4. **Shell and earth**: the earth terminal a 2.2 x 0.7 (+0.1) mm slot 4.7 mm behind the face on the centre line; the
   shield's two side legs (0.54 mm thick, 2.0 mm wide, 13.2 mm between their inner faces) slots 13.5 mm apart (centres),
   5.5 mm behind the face; all three plated, on GND. The earth slot is drilled 0.8 x 2.3 mm; the side slots **1.2 x 2.6
   mm, pads 1.9 x 3.3** (R2-1, 2026-10-23: a 0.8 mm slot left 0.01 mm at the legs' outer face; now 0.21 mm outside and
   0.45 mm inside). Measure a real jack's leg span (14.28 mm across the outer faces expected) before ordering.
5. **Board edge**: the mating face (the drawing's datum) is at the board edge, x = 236.17.
6. **Spacing**: the body is 14.0 mm wide (13.0 deep, 12.8 high); J2 and J3 are 18 mm apart: 4 mm between the bodies.
7. **Silk**: "KBD (PURPLE)" and "MOUSE (GREEN)", the PS/2 colours, turned, beside each jack's body (R2-9). The
   outline is broken round the side-leg pads and stops 0.5 mm short of the face (the board edge).

## Bill of materials

`BOM.md` (generated from `v20_netlist.PARTS` and `BUY`; the text-only column marks the build above). The parts that
need a note:

- **HCT**: IC33 74HCT273, IC40 and IC55 74HCT244, IC41 and IC51 74HCT374, IC53 74HCT74, IC54 74HCT08 - no LS
  substitutes (V2-9, V2-12).
- **IC17**: **HD68B45SP** (Hitachi) or **MC68B45P** (Motorola), the 2 MHz (B) bus grade (R2-7): a 6 MHz CPU's `OUT`
  gives E 333 ns high, which needs the B grade's PWEH (220 ns), not the 1 MHz grade's 450 ns, and 6-dot mode needs its
  clock-low time (V2-11). The 1 MHz grades (HD6845SP, MC6845P) only with a 1 MHz CPU, and with V2-11's clock-low check
  in 6-dot mode. Hitachi grades the part like Motorola - HD6845S / HD68A45S / HD68B45S for 1.0 / 1.5 / 2.0 MHz; a
  secondary source (an Acorn manual quoted on the 6845 page of theoddys.com) names the HD68B45S as the 2 MHz bus part;
  no Hitachi data sheet was found 2026-10-23: **to verify** on the data sheet of the part bought. (The value on the
  schematic and the board: "HD68B45SP / MC68B45P".)
- **IC25**: **AT28C64B-15PU**, burned with `firmware/video/chargen-v20.bin`.
- **IC39**: **AS6C62256-55PCN** (600-mil DIP-28, not a 300-mil 62256). The -55 grade is recommended (current
  production); a slower 62256 works in direct mode up to the machine's 6 MHz (the read of a selected register is set by
  tOE: 55 ns of margin with a -70, ~40 with a -100, 25 °C) and in slot mode in 8-dot mode. The 6-dot slot reads that
  would need -55 never happen (rule 5, R2-4; R2-8).
- **IC41, IC55** (74HCT374, 74HCT244) drive the backplane's DATA0..7 with 6 mA outputs where the memory card has a
  74LS245 (R2-6): measure DATA0's low level during a window read (bench step 6); above 0.5 V fit a **74ACT374 /
  74ACT244** (TTL inputs, 24 mA) in the same sockets. Keep both on hand.
- **C16**: 47 uF electrolytic, **16 V or more**, radial 6.3 mm, 2.5 mm pitch (R2-7).
- **IC49**: ATmega328P-PU with the Uno bootloader burned by ISP before fitting (no ISP header on the card).
- **IC18**: the 74S85 of the V1.x card; a 74LS85 (~60 mA less, V2-19) adds ~20 ns to the window decode, which the
  direct-mode read still fits at 6 MHz.
- **J2, J3**: Same Sky MD-60SM (above). **F1**: Bourns MF-RHT050. **J4**: a 5 V FTDI cable (TTL-232R-5V) or 5 V FTDI Basic.
- Sockets for every IC (the 6845, the IDT7134, the 28C64, the 62256 and the ATmega at least): 40 sockets: 300 mil 15 x
  14-pin, 11 x 16, 9 x 20, 1 x 28 (IC49); 600 mil IC15 48-pin, IC17 40, IC25 and IC39 28 (the text-only build leaves
  12 of them empty). The placement
  leaves room for stamped sockets with end walls up to 1.9 mm (R2-2).

## At the bench, in this order

1. **Before the chips**: a jack's side legs into J2 / J3's slots (R2-1; the legs' outer span 14.28 mm expected) and the
   sockets of IC55, IC19, IC1 and IC42 side by side (R2-2) before soldering them; VCC-GND resistance; power with
   sockets only, then the text-only set without the ATmega: the supply current.
2. **The bus stays quiet**: with the card in the machine, `tests/memory/memory_full_test.py` and
   `tests/video/video_ram_test.py`, a scope on DATA0 during ROM reads. Check the I/O card's IO-ADDR-HL strap (P0-P7).
3. **Ports**: `IN PC AND $F9` = $58 / $59 on the text-only build (bit 3 = 1, bit 0 = DOTS; bits 1 and 2 are VSYNC and
   DE, live: R2-8), $50 / $51 with the graphics chips; `OUT PC` patterns at IC33's outputs. With every card fitted,
   C30 (-RESET)'s low level during a reset below 0.5 V (R2-3).
4. **The 6845 through PA/PB**: scope E against R/-W (V2-15); in 6-dot mode the low width of QC at IC17 pin 21 (V2-11);
   the test card in both modes; the low level on DATA0 during `IN PB` (V2-12).
5. **The ATmega**: MRST with -RESET high and low (V2-6; with -RESET high MRST >= 4.5 V, else R16 4.7k: R2-12), PS2VCC
   >= 4.6 V with both devices plugged in (R2-16), -INT during a bus reset with JP3 fitted (V2-7: stays high), the
   keyboard, then the mouse (`$04` answers `$FA $AA $00`, then `$FA`), and only then JP3 with the sequencer in level mode.
6. **Graphics**: fit IC35-IC45, IC55, RN3, remove R25 / R26; `IN PC` bit 3 = 0. **Direct mode first** (GFX-ON = 0): a
   write / read-back pattern over both 16K pages at 1 MHz, then at 6 MHz if the machine runs there (the stack outside
   the window: rule 2, R2-5). **DATA0's low level during a window read** in each mode, against 0.5 V (R2-6: else
   74ACT374 / 74ACT244 for IC41 / IC55). Then **slot mode** (GFX-ON = 1) at 1 MHz: the same pattern; scope -WE (IC45 pin
   6), WSLOT (IC39 pin 22) and a GD line for contention (V2-5), IC42 pin 11 against a GD line at the character boundary
   (V2-4); IC41.11, IC44.3 and IC39.27 for ringing (R2-15); GFX-ON switched outside vertical blanking shows the 16-dot
   flash (R2-11); a graphics test picture for sparkle.

## Ordering

Nothing blocks the order. Before it, if a jack is at hand: the MD-60SM's leg span and thickness against the slots
(R2-1, 14.28 mm across the outer faces, 0.54 mm legs in 1.2 mm slots), and its date code (after 2022-03-03). The
gerbers (`gerbers/`, zipped as `video-v2.0-gerbers.zip`; the order parameters in `video-v2.0-jlcpcb-order.txt`) were
exported 2026-10-24 from the board as committed in `d42fc33` (the route of `ed7c060` with the board-layout rules'
silkscreen; against the export of 2026-10-23 only `video-v2.0-F_Silkscreen.gbr` differs), with the memory card v2.0's
export options
(`../../memory/kicad/v2.0/finish_v2.py fab`, JLCPCB order 2000765A-Y52). The build makes none: after any rebuild of
the board, export them again from this folder:

```
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
rm -rf gerbers && mkdir gerbers
$CLI pcb export gerbers --no-protel-ext --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts \
    -o gerbers/ video-v2.0.kicad_pcb
$CLI pcb export drill --format excellon --excellon-units mm --generate-map --map-format gerberx2 \
    --excellon-separate-th -o gerbers/ video-v2.0.kicad_pcb
rm -f video-v2.0-gerbers.zip && (cd gerbers && zip -X ../video-v2.0-gerbers.zip *)
```

The drill file checked against the board: 285 vias of 0.4 mm (the board's 285), six plated slots, two NPTH holes.

**Upload `video-v2.0-gerbers.zip`** with the memory card v2.0's settings: FR-4, **4 layers, 218.42 x 113.97 mm, 1.6 mm,
outer copper 1 oz, inner 0.5 oz**, green mask, white silk, HASL with lead, vias plugged; no impedance control, no
castellations or gold fingers. Layer order L1 F.Cu (signals), L2 In1.Cu (GND plane), L3 In2.Cu (VCC plane), L4 B.Cu
(signals). The PTH drill file carries the Mini-DIN jacks' six plated slots (0.8 x 2.3 and 1.2 x 2.6 mm); the NPTH file
X1's two mounting holes. Every part is through-hole (no SMD, no assembly, no stencil). Buy from `BOM.md` (the
text-only build's column marks what to leave off at first) with the notes above, the sockets, a 74ACT374 / 74ACT244
pair (R2-6) and a 5 V FTDI cable; burn the 28C64 and the ATmega's bootloader before fitting.

The software the card needs is not written yet: the ROM's V2.0 driver (with the rules above) and the emulators' V2.0
card model (`BACKLOG.md`).

## Files

| File | What it is |
|---|---|
| `v20_netlist.py` | **the circuit**: parts, nets (pin by pin), no-connects, `BUY`, the text-only build, `check()` |
| `gen_v20.py` | schematic (`SHEETS`: the blocks), local libraries, project rules, the unrouted board, the board's schematic links (`link`), placement check, verify, `BOM.md` |
| `../../../../../tools/kicad/sch_wire.py`, `elk_layout.js`, `package.json` | the wired sheets (ELK), shared with the memory card v2.0 |
| `build.sh` | the whole build: schematic -> board -> Freerouting seeds -> reports -> checks |
| `BOM.md` | the bill of materials (generated) |
| `video-v2.0.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, `.kicad_dru` | the generated design (`.kicad_sch` the root sheet) |
| `video-v2.0-{bus,crtc,text,clock,gfx,video,ps2,power}.kicad_sch` | the eight functional sheets ("The schematic") |
| `video-v2.0-local.kicad_sym` / `.pretty/` | IDT7134, RCA, DE9 and Mini-DIN symbols; F09HP and RCA footprints (from v1.x), MiniDIN6_MD-60SM |
| `blank-card-v3.2-eagle.kicad_sym` / `.pretty/` | the bus connector FABC96R (from the CF card / blank V3.2) |
| `reports/` | netlist, `netlist-compare.txt` (proof), `erc.json`, `drc.json`, schematic PDF (9 pages), top / bottom renders |
| `gerbers/`, `video-v2.0-gerbers.zip` | the fab files (4 copper layers, masks, silk, outline, PTH / NPTH drill and maps), exported 2026-10-24 |
| `video-v2.0-jlcpcb-order.txt` | the PCB order parameters |
