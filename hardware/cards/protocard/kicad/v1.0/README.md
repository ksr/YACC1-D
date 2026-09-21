# protocard-v1.0 — KiCad conversion

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py` from the Eagle design `ProtoCard-Prod-V1.0` in `hardware/cards/protocard/eagle/v1.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `protocard-v1.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `protocard-v1.0.kicad_sch` | root sheet; 1 sub-sheet(s) `protocard-v1.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `protocard-v1.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `protocard-v1.0.kicad_pcb` | the board: 2 copper layers, 9 footprints, 319 track segments, 0 vias |
| `protocard-v1.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (87/87 nets)**

```
  same connectivity, different net name: [('H{slash}L-SWAP', 'H/L-SWAP'), ('I{slash}D-REG-DN', 'I/D-REG-DN'), ('I{slash}D-REG-LD', 'I/D-REG-LD'), ('I{slash}D-REG-OUT', 'I/D-REG-OUT'), ('I{slash}D-REG-UP', 'I/D-REG-UP'), ('I{slash}O-RD', 'I/O-RD'), ('I{slash}O-WR', 'I/O-WR'), ('SP{slash}PC-ADDR-OUT', 'SP/PC-ADDR-OUT'), ('SP{slash}PC-DATA-OUT-HI', 'SP/PC-DATA-OUT-HI'), ('SP{slash}PC-DATA-OUT-LO', 'SP/PC-DATA-OUT-LO'), ('SP{slash}PC-DN', 'SP/PC-DN'), ('SP{slash}PC-LD-HI', 'SP/PC-LD-HI'), ('SP{slash}PC-LD-LO', 'SP/PC-LD-LO'), ('SP{slash}PC-SEL', 'SP/PC-SEL'), ('SP{slash}PC-UP', 'SP/PC-UP')]
```

## Residual ERC / DRC

ERC by type: none.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 5, silk_over_copper 199, silk_overlap 59, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 106 symbols, 141 wires, 97 labels, 23 junctions, 0 bus lines, 0 no-connects
