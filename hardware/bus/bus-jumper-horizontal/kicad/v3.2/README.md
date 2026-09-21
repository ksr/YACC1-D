# bus-jumper-horizontal-v3.2 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Jumper Board Horizontal V3.1` in `hardware/bus/bus-jumper-horizontal/eagle/v3.2/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `bus-jumper-horizontal-v3.2.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `bus-jumper-horizontal-v3.2.kicad_sch` | root sheet; 1 sub-sheet(s) `bus-jumper-horizontal-v3.2-sheetN.kicad_sch` mirror the Eagle sheets |
| `bus-jumper-horizontal-v3.2-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `bus-jumper-horizontal-v3.2.kicad_pcb` | the board: 4 copper layers, 7 footprints, 1130 track segments, 229 vias |
| `bus-jumper-horizontal-v3.2-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (89/89 nets)**

## Residual ERC / DRC

ERC by type: none.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: isolated_copper 1, items_not_allowed 4, lib_footprint_mismatch 2, silk_over_copper 6, silk_overlap 16; unconnected items 1; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 197 symbols, 112 wires, 114 labels, 0 junctions, 0 bus lines, 0 no-connects
