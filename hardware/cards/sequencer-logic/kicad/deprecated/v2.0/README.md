# sequencer-logic-v2.0 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Sequencer-Logic-Prod-V2.0` in `hardware/cards/sequencer-logic/eagle/deprecated/v2.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `sequencer-logic-v2.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `sequencer-logic-v2.0.kicad_sch` | root sheet; 9 sub-sheet(s) `sequencer-logic-v2.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `sequencer-logic-v2.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `sequencer-logic-v2.0.kicad_pcb` | the board: 4 copper layers, 106 footprints, 3764 track segments, 516 vias |
| `sequencer-logic-v2.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (274/274 nets)**

```
  same connectivity, different net name: [('SINGLE-STEP{slash}WAIT', 'SINGLE-STEP/WAIT')]
```

## Residual ERC / DRC

ERC by type: endpoint_off_grid 87, isolated_pin_label 21, pin_not_driven 1.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: clearance 4, items_not_allowed 2, lib_footprint_mismatch 3, shorting_items 14, silk_edge_clearance 25, silk_over_copper 199, silk_overlap 199, starved_thermal 1, text_height 38, text_thickness 36, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 275 symbols, 1047 wires, 606 labels, 221 junctions, 1 bus lines, 29 no-connects
