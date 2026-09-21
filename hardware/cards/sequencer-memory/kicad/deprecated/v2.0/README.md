# sequencer-memory-v2.0 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Sequencer-Memory-V2.0` in `hardware/cards/sequencer-memory/eagle/deprecated/v2.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `sequencer-memory-v2.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `sequencer-memory-v2.0.kicad_sch` | root sheet; 4 sub-sheet(s) `sequencer-memory-v2.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `sequencer-memory-v2.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `sequencer-memory-v2.0.kicad_pcb` | the board: 4 copper layers, 62 footprints, 1872 track segments, 169 vias |
| `sequencer-memory-v2.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (105/105 nets)**

## Residual ERC / DRC

ERC by type: none.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: lib_footprint_mismatch 2, shorting_items 2, silk_edge_clearance 7, silk_over_copper 199, silk_overlap 80, text_height 7, text_thickness 1, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 114 symbols, 591 wires, 486 labels, 225 junctions, 3 bus lines, 26 no-connects
