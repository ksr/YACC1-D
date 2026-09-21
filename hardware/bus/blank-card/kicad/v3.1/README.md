# blank-card-v3.1 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Blank V3.1` in `hardware/bus/blank-card/eagle/v3.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `blank-card-v3.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `blank-card-v3.1.kicad_sch` | root sheet; 1 sub-sheet(s) `blank-card-v3.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `blank-card-v3.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `blank-card-v3.1.kicad_pcb` | the board: 2 copper layers, 3 footprints, 21 track segments, 0 vias |
| `blank-card-v3.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (3/3 nets)**

## Residual ERC / DRC

ERC by type: isolated_pin_label 84.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 100 symbols, 113 wires, 87 labels, 11 junctions, 1 bus lines, 0 no-connects
