# mem-switch-v1.1 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Mem Switch V1.1` in `hardware/cards/mem-switch/eagle/v1.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `mem-switch-v1.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `mem-switch-v1.1.kicad_sch` | root sheet; 3 sub-sheet(s) `mem-switch-v1.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `mem-switch-v1.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `mem-switch-v1.1.kicad_pcb` | the board: 2 copper layers, 112 footprints, 2568 track segments, 129 vias |
| `mem-switch-v1.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (199/199 nets)**

## Residual ERC / DRC

ERC by type: endpoint_off_grid 38, isolated_pin_label 57.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 2, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 70, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 283 symbols, 1247 wires, 505 labels, 324 junctions, 1 bus lines, 3 no-connects
