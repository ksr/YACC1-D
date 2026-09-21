# video-v1.0-fusion-export-2026-09-18 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `Video_1.0` in `hardware/cards/video/eagle/v1.0-fusion-export-2026-09-18/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `video-v1.0-fusion-export-2026-09-18.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `video-v1.0-fusion-export-2026-09-18.kicad_sch` | root sheet; 2 sub-sheet(s) `video-v1.0-fusion-export-2026-09-18-sheetN.kicad_sch` mirror the Eagle sheets |
| `video-v1.0-fusion-export-2026-09-18-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `video-v1.0-fusion-export-2026-09-18.kicad_pcb` | the board: 2 copper layers, 47 footprints, 1180 track segments, 96 vias |
| `video-v1.0-fusion-export-2026-09-18-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MISMATCH (115/117 nets)**

```
  ONLY IN SCHEMATIC +5V        [('C16', '+'), ('C17', '1'), ('C18', '1'), ('C19', '1'), ('C20', '1'), ('C21', '1'), ('C22', '1'), ('C23', '1'), ('C24', '1'), ('C25', '1'), ('C26', '1'), ('C27', '1'), ('C28', '1'), ('C29', '1'), ('C3', '1'), ('IC15', '2'), ('R10', '2'), ('R12', '1'), ('RN2', '1')]
  ONLY IN SCHEMATIC VCC        [('IC1', '14'), ('IC15', '48'), ('IC17', '20'), ('IC18', '16'), ('IC19', '14'), ('IC2', '20'), ('IC20', '14'), ('IC21', '5'), ('IC22', '16'), ('IC23', '16'), ('IC24', '16'), ('IC25', '24'), ('IC26', '14'), ('IC27', '14'), ('IC28', '16'), ('JP1', '3'), ('R2', '2'), ('X1', 'A2'), ('X1', 'A31'), ('X1', 'B2'), ('X1', 'B31'), ('X1', 'C2'), ('X1', 'C31')]
  ONLY ON BOARD     +5V        [('C16', '+'), ('C17', '1'), ('C18', '1'), ('C19', '1'), ('C20', '1'), ('C21', '1'), ('C22', '1'), ('C23', '1'), ('C24', '1'), ('C25', '1'), ('C26', '1'), ('C27', '1'), ('C28', '1'), ('C29', '1'), ('C3', '1'), ('IC1', '14'), ('IC15', '2'), ('IC2', '20'), ('R10', '2'), ('R12', '1'), ('RN2', '1')]
  ONLY ON BOARD     VCC        [('IC15', '48'), ('IC17', '20'), ('IC18', '16'), ('IC19', '14'), ('IC20', '14'), ('IC21', '5'), ('IC22', '16'), ('IC23', '16'), ('IC24', '16'), ('IC25', '24'), ('IC26', '14'), ('IC27', '14'), ('IC28', '16'), ('JP1', '3'), ('R2', '2'), ('X1', 'A2'), ('X1', 'A31'), ('X1', 'B2'), ('X1', 'B31'), ('X1', 'C2'), ('X1', 'C31')]
```

## Residual ERC / DRC

ERC by type: endpoint_off_grid 35, isolated_pin_label 56, pin_not_driven 2, pin_to_pin 8.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 3, silk_edge_clearance 8, silk_over_copper 199, silk_overlap 15, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 192 symbols, 549 wires, 267 labels, 90 junctions, 10 bus lines, 30 no-connects
