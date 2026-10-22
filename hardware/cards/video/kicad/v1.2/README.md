# video-v1.2 — KiCad design master for the video card

**Superseded by `../v1.3/` (2026-10-22), the master now; v1.2 stays as the record of the bench state: the built V1.0 card with every fix up to 2026-10-21, on v1.1's 2-layer board.** Hand-maintained in KiCad 10. It is `../v1.1/` (one 5 V rail) with every
change the built V1.0 card needed on the bench up to 2026-10-21, so a card built from it starts where the bench card
ended: register access through the CPU at 1 MHz, the test card, the ROM's driver and the console mirrored on screen
(`docs/procedures/VIDEO-BRINGUP.md`, `docs/cards/video.md`). Not ordered. `tools/eagle_to_kicad_all.py` never writes here
(`MASTER` marker file).

## Changes since v1.1

| # | Change | Why (finding / bench date) | In the design |
|---|---|---|---|
| 1 | **6845 RS on ADDR1** | RS was ADDR0 while -CS needs A0 = 0: the data register was unreachable (`../../docs/fix-6845-register-select.md`; bench wire 2026-10-21) | IC17 pin 24 on `ADDR1` (with IC15 pin 41 and X1 A4); `ADDR0` re-joined beside the pin by a via, so its other four pads are untouched |
| 2 | **LPSTB to GND** | finding 6.5: an NMOS input left floating | IC17 pin 3 on `GND` (was a no-connect) |
| 3 | **R13 4.7k, `N$16` to VCC** | the JP1 latch's -OC (IC2 pin 1) is an open-collector 7416 output with no pull-up: floating, it let the latch drive the data bus on every memory read in the machine (bench 2026-10-21) | R13 (0207) beside IC2, right of pin 1 |
| 4 | **R14 4.7k, `N$5` to VCC** | /A0 (IC27 pin 8, into IC1 pin 13: the 6845's select) only read high because it floated | R14 (0207) right of IC1 |
| 5 | **E without the one-shot** | finding 6.1: C1 (1 uF) was discharged by every memory cycle and recharged through 20k, so at 1 MHz E never rose (`crtcreg.img` read FF; bench fix 2026-10-21: IC1 pin 2 to VCC) | IC1 pin 2 on `VCC`, so E = IC1/A = the strobe XOR (IC26/C); R1, C1 and net `N$3` removed; IC27 pin 12 (IC27/F's output) unconnected, its input still on `N$1` |
| 6 | **IC28 74163** | synchronous clear: a clean one-dot CHARCLOCK and divide by 6 (finding 6.2; fitted 2026-10-18) | value text only: same DIL16 pinout, same wiring (-CLR on CHARCLOCK) |
| 7 | **Q2 11.0592 MHz** | 80 x 24 at 15.75 kHz / 60.1 Hz on a TV-rate monitor (2026-10-21) | value text; SV4 on 1-2 |
| 8 | Silkscreen title "YACC1 Video Card V1.2" | | |

Not in v1.2 (the next revision, `BACKLOG.md`): the graphics overlay, 8-dot characters, the PS/2 keyboard, an IBM
monitor DB9, the 6845 on I/O ports.

## Proof

- Schematic vs board (`tools/kicad/compare_netlists.py`): **MATCH, 114/114 nets** (v1.1: 116; `N$3` and `N$4` are gone).
- DRC: **0 unconnected**, no clearance, short or dangling-track finding; the residue is v1.1's cosmetic set, unchanged by
  type and count: silk_over_copper 199, silk_overlap 15, silk_edge_clearance 8, lib_footprint_mismatch 3,
  items_not_allowed 2, text_height 2.
- ERC: endpoint_off_grid 35, isolated_pin_label 56, pin_to_pin 9 (v1.1's cosmetic set; its two `pin_not_driven` are
  gone - the inputs v1.2 ties).
- Each change checked pin by pin from the exported netlist: IC17.24 = ADDR1, IC17.3 = GND, R13 = N$16/VCC (with IC2.1,
  IC27.10), R14 = N$5/VCC (with IC27.8, IC1.13), IC1.2 = VCC, no R1/C1/N$3.

The board edit kept v1.1's routing: R1, C1 and their tracks were deleted, IC17 pin 24 was taken out of the `ADDR0` route
(three branches met at its pad; they now meet at a via 2.2 mm to its left, at (79.02, 88.44)), and the seven new
connections (IC17 24 and 3, IC1 2, R13, R14) were routed by Freerouting 1.9 with every existing track fixed, 0.2 mm
tracks.

## Files

| File | What it is |
|---|---|
| `video-v1.2.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `video-v1.2.kicad_sch` + `-sheet1/2` | schematic (two sheets, as the Eagle original) |
| `video-v1.2.kicad_pcb` | 2-layer board |
| `video-v1.2-eagle.kicad_sym`, `video-v1.2-eagle.pretty/` | project libraries (from the conversion; edit freely) |
| `reports/` | netlist + `netlist-compare.txt` (proof), `erc.json`, `drc.json`, schematic PDF, top/bottom renders — regenerate after edits |

Regenerate the reports:
```
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K sch export netlist --format kicadsexpr -o reports/netlist.net video-v1.2.kicad_sch
$K sch erc --format json --severity-all -o reports/erc.json video-v1.2.kicad_sch
$K pcb drc --format json --severity-all -o reports/drc.json video-v1.2.kicad_pcb
$K sch export pdf -o reports/video-v1.2-schematic.pdf video-v1.2.kicad_sch
$K pcb render --side top --width 1568 --height 1176 -o reports/video-v1.2-top.png video-v1.2.kicad_pcb
$K pcb render --side bottom --width 1568 --height 1176 -o reports/video-v1.2-bottom.png video-v1.2.kicad_pcb
python3 ../../../../../tools/kicad/compare_netlists.py reports/netlist.net video-v1.2.kicad_pcb > reports/netlist-compare.txt
```
