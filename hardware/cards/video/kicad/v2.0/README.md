# video-v2.0 — KiCad design master for the video card

**The master since 2026-10-22. Not ordered; no gerbers.** V2.0 is the v1.3 card (`../v1.3/`: 6845, IDT7134 text RAM,
the DOTS jumper, 12 MHz, both fonts in one EPROM) plus a **graphics layer**, **every register on I/O ports PA-PE** and
**two PS/2 ports** on an ATmega328P with an **INT jumper**. The design note is `BACKLOG.md` "Video card V2.0"; the theory
`docs/cards/video.md` section 7a; the ATmega's firmware `embedded/video-ps2`; the picture `tools/vidsim.py --card v2.0`.

Unlike v1.x (Eagle conversions edited in KiCad) this design is **generated**: `v20_netlist.py` is the circuit,
`gen_v20.py` draws the schematic (one A0 sheet, the CF card's sheet writer: every pin a stub to a label or a power
symbol, functional boxes) and builds the board, `build.sh` routes and checks it. Change the circuit in
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
- **Placement** (`gen_v20.py` `PLACE`; pin 1 of every DIP at the top left, each 100 nF beside its IC's VCC corner):
  row A (top) the port decode, strobes, control register, status buffers, the PS/2 and graphics latches, WRQ and the
  video driver IC27; on the left the 600-mil parts (IC15 text RAM, IC17 6845, IC39 62256, IC25 EPROM) and IC18 with SV3 /
  RN2; row B the graphics address muxes, display latch and shifter, the ATmega; row C the text pipeline and the gates;
  row D the clock chain (IC28, IC21, IC20 with Q2, SV4) and the remaining gates; the right edge DB9 (X2), RCA (J1), the
  keyboard (J2) and mouse (J3) Mini-DINs, the FTDI header J4, the PWR LED. `gen_v20.py place` checks that no two
  courtyards overlap.

## Results (`./build.sh`, 2026-10-22)

| Check | Result |
|---|---|
| schematic netlist vs `v20_netlist.py` | **MATCH, 206 nets** (`gen_v20.py checknet`) |
| netlist proof, schematic vs board (`tools/kicad/compare_netlists.py`) | **MATCH** |
| placement | 108 footprints, no courtyard overlaps (`gen_v20.py place`) |
| route (Freerouting 1.9, component order 17, 60 passes) | **0 unrouted, 273 vias, 20.8 m of 0.25 mm track** (F.Cu 9.9 m, B.Cu 10.9 m). Of 20 component orders tried, 17 was the only one that routed completely without copper errors (the best of the first eight left GOR, IC32 to IC48, unrouted). Its first run gave 249 vias, the rerun that made this board 273: on this board Freerouting does not repeat itself exactly, but order 17 completed both times |
| DRC | **0 unconnected, no clearance / short / dangling findings**, schematic parity 0; cosmetic only: silk_over_copper 76, silk_overlap 28, silk_edge_clearance 8, text_height 3, text_thickness 3 (footprint texts) |
| planes | In1.Cu GND, In2.Cu VCC, one zone each over the whole board; every GND / VCC pin reaches its plane (0 unconnected with no power tracks) |
| ERC | endpoint_off_grid 6 (cosmetic), nothing else |
| `gen_v20.py verify` | **PASS**: 82 key connections pin by pin in the schematic and on the board (the port decode and strobes, the 6845 on PA/PB, the card ID, the slot logic, the combine, the DOTS divider and font select, the ATmega's bus interface and PS/2 lines, the INT path), 4 copper layers, the two planes, no track on GND/VCC |

`./build.sh` takes about 20 minutes (one Freerouting run); `SEEDS="0 1 2 ..."` searches more component orders (each
run up to an hour at 60 passes; the watchdog stops them).

## Parts V2.0 adds (references continue v1.x's; IC2, JP1, R13, R14 are gone)

| Ref | Part | Job |
|---|---|---|
| IC30 | 74LS138 | port decode: Y2..Y7 = PA..PF when IO-ADDR3 = 1 |
| IC31, IC32 | 74LS32 | port strobes (PC write/read, PD write/read, PE read); IC32/B: text OR graphics |
| IC33 | 74LS273 | control register, OUT PC: PLANE0-2, CPAGE, DPAGE, TEXT-OFF, GFX-ON, XOR (cleared by -RESET) |
| IC34 | 74LS244 | card status, IN PC: DOTS, VSYNC, DE, 0, ID 0101 |
| IC35-IC38 | 74LS157 | graphics RAM address: CPU (QC = 0) or display (QC = 1) |
| IC39 | 62256 | graphics RAM, two 16K pages |
| IC40 | 74LS244 | write buffer DATA -> GD (WSLOT) |
| IC41 | 74LS374 | CPU read latch GD -> DATA (loads on QC's rise) |
| IC42, IC43 | 74LS374, 74LS166 | display latch (CHARCLOCK) and graphics dot shifter |
| IC44 | 74LS74 | WRQ: a CPU write pending, sampled on CHARCLOCK |
| IC45 | 74LS20 | the RAM's -WE = NAND(WRQ, NOT QC, QA XOR QB, GWR) |
| IC46, IC47, IC48 | 74LS04, 74LS08, 74LS10 | inverters, graphics select / write / FULL clear, XOR term and the video NAND3 |
| IC49, Y1 | ATmega328P, 16 MHz | the PS/2 controller (`embedded/video-ps2`), C55/C56 22 pF |
| IC50, IC51, IC52, IC53 | 74LS374, 74LS374, 74LS244, 74LS74 | PS/2 data latch (IN PE), command latch (OUT PD), status (IN PD), FULL/BUSY |
| J2, J3 | Mini-DIN-6 | keyboard, mouse (R17-R20 4.7k pull-ups) |
| J4 | 1x6 header | FTDI: GND, CTS, (VCC not connected), TXD, RXD, DTR -> C57 -> reset |
| D1, R16 | 1N4148, 10k | the bus -RESET resets the ATmega; its reset pull-up |
| JP3 | 1x2 header | INT-EN: IC27/D's open collector to the bus -INT |
| C30-C54 | 100 nF | decoupling, one per new IC (C54 the ATmega's AVCC) |

Changed v1.3 parts: IC1 (74ALS08) now the 6845 -CS (PA OR PB), WSLOT and the dot gates; IC19/A the CPU read latch's
-OE, IC19/D spare; IC26/C E = -IO-RD XOR -IO-WR, IC26/D QA XOR QB; IC27/D INTREQ -> -INT, IC27/E/F spare; IC17 RS =
IO-ADDR0, R/-W = -IO-WR, -CS from IC1/A. Pin by pin: `v20_netlist.py`.

## To check before ordering

- **The Mini-DIN footprint is approximate** (`video-v2.0-local.pretty/MiniDIN6_PS2.kicad_mod`: pins on a 2.6 mm grid,
  three shell tags): redraw it from the data sheet of the jack actually bought (CUI MD-60SM, Kycon KMDGX-6S-BS or similar).
- The 6-dot mode's 6845 clock (167 ns low at 12 MHz, as v1.3) and the EPROM's 500 ns a character.
- Graphics reads need a CPU read strobe of at least ~1.4 us (fine at 1 MHz; above ~1.5 MHz they fail).
- The ATmega needs its bootloader burned once with an ISP programmer before fitting (no ISP header on the card).
- The ROM's V2.0 driver and the emulators' V2.0 model do not exist yet (`BACKLOG.md`).

## Files

| File | What it is |
|---|---|
| `v20_netlist.py` | **the circuit**: parts, nets (pin by pin), no-connects, `check()` |
| `gen_v20.py` | schematic, local libraries, project rules, the unrouted board, placement check, verify |
| `build.sh` | the whole build: schematic -> board -> Freerouting seeds -> reports -> checks |
| `video-v2.0.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, `.kicad_dru` | the generated design |
| `video-v2.0-local.kicad_sym` / `.pretty/` | IDT7134, 2732, RCA, DE9 and Mini-DIN symbols; F09HP and RCA footprints (from v1.x), MiniDIN6_PS2 |
| `blank-card-v3.2-eagle.kicad_sym` / `.pretty/` | the bus connector FABC96R (from the CF card / blank V3.2) |
| `reports/` | netlist, `netlist-compare.txt` (proof), `erc.json`, `drc.json`, schematic PDF, top / bottom renders |
