# video-v1.3 — KiCad design master for the video card

**This is the master (since 2026-10-22). Not ordered.** v1.3 is `../v1.2/` (the bench state of 2026-10-21) with one
jumper that chooses **6 or 8 dots a character**, and a new board: **4 layers, routed from scratch** - In1.Cu a solid GND
plane, In2.Cu a solid VCC plane, every signal routed anew, GND and VCC never routed (every power pin is a through-hole
pad on its plane). The outline, the bus connector X1 and the placement are v1.2's; the parts v1.3 adds sit beside IC28.
`tools/eagle_to_kicad_all.py` never writes here (`MASTER` marker file). `./build.sh` rebuilds the board and every report
and checks them (needs KiCad 10 and Freerouting 1.9).

## The two modes

One 12 MHz crystal (Q2, SV4 on 1-2) serves both:

| DOTS jumper (JP2) | IC28 divides by | character clock | screen | 6845 R0..R9 | dots across | EPROM time a character |
|---|---|---|---|---|---|---|
| open (R15 pulls DOTS high) | 6 | 2.0 MHz | **80 x 24** | 126, 80, 98, 10, 31, 6, 24, 27, 0, 7 | 480 | 500 ns |
| fitted (DOTS to GND) | 8 | 1.5 MHz | **64 x 24** | 94, 64, 75, 8, 31, 6, 24, 27, 0, 7 | 512 | 667 ns |

Both 15.75 kHz / 60 Hz. The 64 x 24 table is the one proven on a TV-rate monitor on 2026-10-21 (9 MHz / 6 = the same
1.5 MHz); the 80 x 24 table is centred in that monitor's measured visible window (about 10.3-58.3 us after the sync
starts: the text runs 14.5-54.5 us). `python3 tools/vidsim.py testcard --card v1.3 --dots 6|8 --png card.png` draws
each mode; `vidsim.py chargen --card v1.3` writes the EPROM (`firmware/video/chargen-v13.bin`).

## Changes since v1.2 (schematic)

| # | Change | Pins |
|---|---|---|
| 1 | **IC28 (74163) divides by 16 - P, loading P on its carry** | -CLR (1) to VCC; data A (3) GND, B (4) **DOTS**, C (5) GND, D (6) VCC: P = 8 (/8) or 10 (/6); -LOAD (9) = CHARCLOCK; RCO (15) = net `RCO`; QA (14) unconnected; ENT/ENP (10, 7) stay on N$73 (R10). CRTCCLOCK stays QC (12) -> IC17 21 |
| 2 | **CHARCLOCK = NOT RCO** | IC19/C both inputs (9, 10) on `RCO` (were QA and CRTCCLOCK): one dot low at count 15 in both modes, the same pulse the 74LS166 load and IC22/IC23 get in v1.2 |
| 3 | **DOTS jumper JP2** (2-pin header, silk "DOTS: ON=8") + **R15 4.7k** pull-up | JP2 1 = DOTS, 2 = GND; R15 VCC - DOTS. Fitted = 8 dots, open = 6 dots |
| 4 | **Font select: DOTS on EPROM A10** | IC25 pin 19 (was GND): the 8-dot font at $000, the 6-dot font at $400; A9, A11 stay GND |
| 5 | **DOTS readable at `$D801` bit 0** | latch IC2 1D (pin 3) on DOTS (was JP1 pin 1, now unconnected): 1 = 6 dots, 0 = 8. IC2 LE (pin 11) to VCC (was JP1 pin 13, which floated): the latch is transparent by design; JP1 pin 13 unconnected |
| 5a | **Card ID at `$D801` bit 2** (2026-10-22) | latch IC2 3D (pin 7) to GND (was JP1 pin 4, now unconnected, no-connect flag): bit 2 = 0 says "V1.3" to `ROM 2026-10-22` and later, which then reads DOTS on bit 0 for 80 x 24 or 64 x 24; the V1.0-V1.2 card reads bit 2 = 1 (a jumper on its JP1 3-4) and keeps its 11.0592 MHz table |
| 6 | **IC24 (74LS166) loads all eight bits** | A, B, C (2, 3, 4; were GND) to EPROM O0, O1, O2 (IC25 9, 10, 11) on nets `CG0..CG2`. In 6-dot mode the next load comes after 6 shifts, so only O7..O2 are seen |
| 7 | values, title | Q2 **12MHz**; IC25 **2732 (chargen-v13)**; silkscreen "YACC1 Video Card V1.3" |

Unchanged from v1.2: RS on ADDR1, LPSTB to GND, the R13 / R14 4.7k pull-ups, E without the one-shot (IC1 pin 2 on VCC).
Characters stay 8 scan lines tall in both modes (R9 = 7): taller ones need RA3 to the EPROM and would break the
proposed graphics overlay's 8-plane addressing (`BACKLOG.md`).

**The 6845's clock in 6-dot mode.** QC over counts 10..15 is low for 2 dots and high for 4: **167 ns low / 333 ns high**
at 12 MHz (8-dot mode: 333 / 333 ns). Motorola's MC6845 data sheet gives a minimum clock pulse width of 160 ns low and
200 ns high (**To verify:** from the data sheet as remembered - the tree's `docs/BYTE 6845.pdf` is a scan without the
timing table). 167 ns against 160 ns is a margin of only 7 ns. Fit a faster grade (MC68A45 / MC68B45, or an HD6845S) for
the 6-dot mode, or check the fitted part's sheet; 8-dot mode has ample margin. The ROM's support (read `$D801` bit 0 at
reset, pick 80 or 64 columns and the table) is the next step (`BACKLOG.md`, "Video v1.3").

**The EPROM in 6-dot mode** gets 500 ns a character; the MBM2732A is a 450 ns part: it works with little slack. A faster
part (a 2732A-25, or a 27C32/2764 at 250 ns with a socket adapter) removes the worry.

## The board

| | |
|---|---|
| Layers | 4, 1.6 mm (JLCPCB-style 4-layer): F.Cu signals, **In1.Cu GND plane**, **In2.Cu VCC plane**, B.Cu signals |
| Rules (`video-v1.3.kicad_dru`, the project's net classes) | as the memory card v2.0: signal tracks 0.25 mm, clearance 0.2 mm, vias 0.8 / 0.4 mm, copper to edge 0.5 mm; plane antipads 0.3 mm, thermal reliefs 0.4 mm gap / 0.5 mm spokes; class Power = GND, VCC: not routed |
| Outline, X1, placement | v1.2's (177.8 x 114.0 mm); **JP2** at (179.7, 116.6), pads horizontal, right of IC28; **R15** vertical at x = 185.4 (pads at y 113.0 / 120.62); the "DOTS: ON=8" label below JP2 |
| Route | Freerouting 1.9 on a 2-signal-layer copy (planes dropped, `-inc Power`), one run per DSN component order (seeds 0-7, in parallel), the best kept: **seed 7: 0 unrouted, 39 vias, 8.41 m of 0.25 mm track** (F.Cu 4.29 m, B.Cu 4.13 m; rebuilt 2026-10-22 with the card ID). The other seeds: 39-52 vias, seed 1 with 3 clearance findings |
| Planes | each one solid piece (GND 17,737 mm², VCC 17,724 mm² of the 20,270 mm² board; the rest antipads), plus a few 0.8 mm² slivers between X1's pins |

## Proof

- Schematic vs board (`tools/kicad/compare_netlists.py`): **MATCH, 115/115 nets** (116 before the card ID: N$13 is gone).
- DRC: **0 unconnected** (every GND/VCC pad reaches its net through its plane only: the planes connect), no clearance,
  short or dangling-track finding; the residue is v1.2's cosmetic set, unchanged by type and count: silk_over_copper
  199, silk_overlap 15, silk_edge_clearance 8, lib_footprint_mismatch 3, items_not_allowed 2 (X1's mounting holes in
  X1's own keepout), text_height 2. Schematic parity: footprint_symbol_mismatch 16 and net_conflict 29, the conversion's
  inherited value texts and its "unconnected-(...)" pins, as v1.2; the three net_conflict items v1.2 lacks are the pins
  v1.3 leaves unconnected (IC28 14, JP1 1, JP1 4, JP1 13), and v1.2's for IC28 15 and IC25 9-11 are gone (now used).
- ERC: endpoint_off_grid 35, isolated_pin_label 56, pin_to_pin 9 - v1.2's cosmetic set, unchanged.
- `gen_v13.py verify`: every change above checked pin by pin in the schematic netlist **and** on the board's pads; no
  track on GND or VCC; copper layers F.Cu, In1.Cu, In2.Cu, B.Cu; one plane each.

## Files

| File | What it is |
|---|---|
| `video-v1.3.kicad_pro`, `video-v1.3.kicad_dru` | project and rules (written by `gen_v13.py project`) |
| `video-v1.3.kicad_sch` + `-sheet1/2` | schematic (two sheets, as the Eagle original) |
| `video-v1.3.kicad_pcb` | the 4-layer board (written by `build.sh`) |
| `video-v1.3-eagle.kicad_sym`, `video-v1.3-eagle.pretty/` | project libraries; v1.3 adds the symbol `con-lstb_MA02-1` and KiCad's `PinHeader_1x02_P2.54mm_Vertical` footprint |
| `gen_v13.py`, `build.sh` | the board generator (project, board, dsn, shuffle, ses, stats, silk, verify) and the build |
| `reports/` | netlist + `netlist-compare.txt` (proof), `erc.json`, `drc.json`, schematic PDF, top/bottom renders |
