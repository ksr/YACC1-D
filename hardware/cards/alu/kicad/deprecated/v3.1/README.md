# alu-v3.1 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `ALU V3.1` in `hardware/cards/alu/eagle/deprecated/v3.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `alu-v3.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `alu-v3.1.kicad_sch` | root sheet; 9 sub-sheet(s) `alu-v3.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `alu-v3.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `alu-v3.1.kicad_pcb` | the board: 4 copper layers, 85 footprints, 2256 track segments, 147 vias |
| `alu-v3.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (159/159 nets)**

```
  same connectivity, different net name: [('-ADD{slash}SUB', '-ADD/SUB'), ('CO{slash}BO', 'CO/BO'), ('C{slash}SHIFT', 'C/SHIFT')]
```

## Residual ERC / DRC

ERC by type: endpoint_off_grid 90, isolated_pin_label 55.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: clearance 35, items_not_allowed 2, lib_footprint_mismatch 1, shorting_items 56, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 199, text_height 2, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 278 symbols, 904 wires, 539 labels, 156 junctions, 31 bus lines, 13 no-connects
