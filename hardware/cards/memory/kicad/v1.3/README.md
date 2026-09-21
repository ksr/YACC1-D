# memory-v1.3 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Memory V1.3` in `hardware/cards/memory/eagle/v1.3/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `memory-v1.3.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `memory-v1.3.kicad_sch` | root sheet; 6 sub-sheet(s) `memory-v1.3-sheetN.kicad_sch` mirror the Eagle sheets |
| `memory-v1.3-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `memory-v1.3.kicad_pcb` | the board: 4 copper layers, 52 footprints, 968 track segments, 80 vias |
| `memory-v1.3-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (115/115 nets)**

## Residual ERC / DRC

ERC by type: endpoint_off_grid 33, isolated_pin_label 43, missing_input_pin 1, missing_power_pin 1, missing_unit 1, pin_not_connected 2.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 24, text_height 2, text_thickness 1, track_dangling 17; unconnected items 100; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 197 symbols, 620 wires, 353 labels, 117 junctions, 11 bus lines, 8 no-connects
