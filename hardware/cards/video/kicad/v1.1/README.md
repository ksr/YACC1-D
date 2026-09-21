# video-v1.1 — KiCad design master for the video card

**This is the master. Hand-maintained in KiCad 10 since 2026-09-21; Fusion 360 is abandoned for this card (Ken).**
Started as a copy of the proven conversion of the built card (`../v1.0-fusion-export-2026-09-18/`, which stays as the
record of what was built) with the project renamed to `video-v1.1`. `tools/eagle_to_kicad_all.py` never writes here
(`MASTER` marker file).

## Changes since the built V1.0

1. **One 5 V rail.** The built card had two nets, `+5V` (IC1, IC2, IC15 pin 2, RN2, R10, R12, every decoupling cap) and
   `VCC` (bus, the implicit power pins of IC17–IC28), with nothing joining them: the `+5V` rail had no source (found by the
   KiCad netlist proof; the bench wire of 2026-09-21 cured the write-through fault). Here `+5V` is gone: every former
   `+5V` symbol, label, pad and track is `VCC`, and a 0.254 mm track on F.Cu from (67.28, 112.56) to (66.01, 111.30), next
   to C28, joins the two former copper islands. Netlist proof vs the board: **MATCH, 116/116 nets**; DRC has no clearance,
   short or dangling-track finding; 0 unconnected items.

Still to do in this master (see BACKLOG): move the 6845 RS from A0 to A1 (`../../docs/fix-6845-register-select.md`),
pull-ups on the 7416 outputs.

## Files

| File | What it is |
|---|---|
| `video-v1.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `video-v1.1.kicad_sch` + `-sheet1/2` | schematic (two sheets, as the Eagle original) |
| `video-v1.1.kicad_pcb` | 2-layer board |
| `video-v1.1-eagle.kicad_sym`, `video-v1.1-eagle.pretty/` | project libraries (from the conversion; edit freely) |
| `reports/` | netlist + `netlist-compare.txt` (proof), `erc.json`, `drc.json`, schematic PDF, top/bottom renders — regenerate after edits |

Residual ERC: endpoint_off_grid 35, isolated_pin_label 56, pin_not_driven 2, pin_to_pin 9 (`isolated_pin_label` = the conversion's per-net global labels,
`endpoint_off_grid` = the same labels/pins on Eagle's 0.1-inch grid; both cosmetic).
Residual DRC: items_not_allowed 2, silk_edge_clearance 8, lib_footprint_mismatch 3, text_height 2, silk_overlap 15, silk_over_copper 199 (silk findings are the Eagle drawing as it was;
`lib_footprint_mismatch` = board copies of X1/Q2/IC1 differ cosmetically from the extracted library copies).

Regenerate the reports:
```
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K sch export netlist --format kicadsexpr -o reports/netlist.net video-v1.1.kicad_sch
$K sch erc --format json --severity-all -o reports/erc.json video-v1.1.kicad_sch
$K pcb drc --format json --severity-all -o reports/drc.json video-v1.1.kicad_pcb
$K sch export pdf -o reports/video-v1.1-schematic.pdf video-v1.1.kicad_sch
python3 ../../../../../tools/kicad/compare_netlists.py reports/netlist.net video-v1.1.kicad_pcb > reports/netlist-compare.txt
```
