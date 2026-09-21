# sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1-copy — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Sequencer-Logic-Prod-V2.1 copy` in `hardware/cards/sequencer-logic/eagle/v2.1/orig size/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was never fabricated (or its build status is unknown, see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1-copy.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1-copy.kicad_sch` | root sheet; 9 sub-sheet(s) `sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1-copy-sheetN.kicad_sch` mirror the Eagle sheets |
| `sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1-copy-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `reports/` | ERC (`erc.json`), schematic PDF |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **n/a (schematic only)**

## Residual ERC / DRC

ERC by type: endpoint_off_grid 89, footprint_link_issues 234, isolated_pin_label 18, missing_unit 1.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

Converter: converted: 260 symbols, 1033 wires, 611 labels, 220 junctions, 1 bus lines, 29 no-connects
