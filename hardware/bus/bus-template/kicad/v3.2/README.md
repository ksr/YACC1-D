# bus-template-v3.2 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Bus Template V3.2` in `hardware/bus/bus-template/eagle/v3.2/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was never fabricated (or its build status is unknown, see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `bus-template-v3.2.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `bus-template-v3.2.kicad_sch` | root sheet; 1 sub-sheet(s) `bus-template-v3.2-sheetN.kicad_sch` mirror the Eagle sheets |
| `bus-template-v3.2-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `reports/` | ERC (`erc.json`), schematic PDF |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **n/a (schematic only)**

## Residual ERC / DRC

ERC by type: footprint_link_issues 98, isolated_pin_label 84.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

Converter: converted: 100 symbols, 113 wires, 87 labels, 11 junctions, 1 bus lines, 0 no-connects
