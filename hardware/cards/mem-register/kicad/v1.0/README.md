# mem-register-v1.0 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Mem Register V1.0` in `hardware/cards/mem-register/eagle/v1.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `mem-register-v1.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `mem-register-v1.0.kicad_sch` | root sheet; 3 sub-sheet(s) `mem-register-v1.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `mem-register-v1.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `mem-register-v1.0.kicad_pcb` | the board: 2 copper layers, 90 footprints, 1651 track segments, 107 vias |
| `mem-register-v1.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (107/107 nets)**

## Residual ERC / DRC

ERC by type: endpoint_off_grid 27, isolated_pin_label 56.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 91, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 203 symbols, 664 wires, 491 labels, 83 junctions, 33 bus lines, 3 no-connects
