# protocard-v1.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `ProtoCard-Prod-V1.0` in `hardware/cards/protocard/eagle/v1.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

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
  same connectivity, different net name: [('/Sheet 1/AC-IN-INV', 'AC-IN-INV'), ('/Sheet 1/ADDR-REG-CLK', 'ADDR-REG-CLK'), ('/Sheet 1/ADDR-REG-OUT', 'ADDR-REG-OUT'), ('/Sheet 1/ADDR0', 'ADDR0'), ('/Sheet 1/ADDR1', 'ADDR1'), ('/Sheet 1/ADDR2', 'ADDR2'), ('/Sheet 1/ADDR3', 'ADDR3'), ('/Sheet 1/ADDR4', 'ADDR4'), ('/Sheet 1/ADDR5', 'ADDR5'), ('/Sheet 1/ADDR6', 'ADDR6'), ('/Sheet 1/ADDR7', 'ADDR7'), ('/Sheet 1/ADDR8', 'ADDR8'), ('/Sheet 1/ADDR9', 'ADDR9'), ('/Sheet 1/ADDR10', 'ADDR10'), ('/Sheet 1/ADDR11', 'ADDR11'), ('/Sheet 1/ADDR12', 'ADDR12'), ('/Sheet 1/ADDR13', 'ADDR13'), ('/Sheet 1/ADDR14', 'ADDR14'), ('/Sheet 1/ADDR15', 'ADDR15'), ('/Sheet 1/ALU-FUNC', 'ALU-FUNC'), ('/Sheet 1/ALU0', 'ALU0'), ('/Sheet 1/ALU1', 'ALU1'), ('/Sheet 1/ALU2', 'ALU2'), ('/Sheet 1/ALU3', 'ALU3'), ('/Sheet 1/BR-COND', 'BR-COND'), ('/Sheet 1/BR-REG-LD-HI', 'BR-REG-LD-HI'), ('/Sheet 1/BR-REG-LD-LO', 'BR-REG-LD-LO'), ('/Sheet 1/BR-REG-OUT', 'BR-REG-OUT'), ('/Sheet 1/BRD-ADDR-REG0', 'BRD-ADDR-REG0'), ('/Sheet 1/BRD-ADDR-REG1', 'BRD-ADDR-REG1'), ('/Sheet 1/BRD-IN-ID0', 'BRD-IN-ID0'), ('/Sheet 1/BRD-IN-ID1', 'BRD-IN-ID1'), ('/Sheet 1/BRD-OUT-ID0', 'BRD-OUT-ID0'), ('/Sheet 1/BRD-OUT-ID1', 'BRD-OUT-ID1'), ('/Sheet 1/DATA-REG-IN-ID0', 'DATA-REG-IN-ID0'), ('/Sheet 1/DATA-REG-IN-ID1', 'DATA-REG-IN-ID1'), ('/Sheet 1/DATA-REG-OUT-ID0', 'DATA-REG-OUT-ID0'), ('/Sheet 1/DATA-REG-OUT-ID1', 'DATA-REG-OUT-ID1'), ('/Sheet 1/DATA-REG-RD-HI', 'DATA-REG-RD-HI'), ('/Sheet 1/DATA-REG-RD-LO', 'DATA-REG-RD-LO'), ('/Sheet 1/DATA-REG-WR-HI', 'DATA-REG-WR-HI'), ('/Sheet 1/DATA-REG-WR-LO', 'DATA-REG-WR-LO'), ('/Sheet 1/DATA0', 'DATA0'), ('/Sheet 1/DATA1', 'DATA1'), ('/Sheet 1/DATA2', 'DATA2'), ('/Sheet 1/DATA3', 'DATA3'), ('/Sheet 1/DATA4', 'DATA4'), ('/Sheet 1/DATA5', 'DATA5'), ('/Sheet 1/DATA6', 'DATA6'), ('/Sheet 1/DATA7', 'DATA7'), ('/Sheet 1/DATA8', 'DATA8'), ('/Sheet 1/DATA9', 'DATA9'), ('/Sheet 1/DATA10', 'DATA10'), ('/Sheet 1/DATA11', 'DATA11'), ('/Sheet 1/DATA12', 'DATA12'), ('/Sheet 1/DATA13', 'DATA13'), ('/Sheet 1/DATA14', 'DATA14'), ('/Sheet 1/DATA15', 'DATA15'), ('/Sheet 1/DIR', 'DIR'), ('/Sheet 1/H{slash}L-SWAP', 'H/L-SWAP'), ('/Sheet 1/INT', 'INT'), ('/Sheet 1/INT-ACK', 'INT-ACK'), ('/Sheet 1/IO-ADDR', 'IO-ADDR'), ('/Sheet 1/I{slash}D-REG-DN', 'I/D-REG-DN'), ('/Sheet 1/I{slash}D-REG-LD', 'I/D-REG-LD'), ('/Sheet 1/I{slash}D-REG-OUT', 'I/D-REG-OUT'), ('/Sheet 1/I{slash}D-REG-UP', 'I/D-REG-UP'), ('/Sheet 1/I{slash}O-RD', 'I/O-RD'), ('/Sheet 1/I{slash}O-WR', 'I/O-WR'), ('/Sheet 1/LD-AC', 'LD-AC'), ('/Sheet 1/MEM-RD', 'MEM-RD'), ('/Sheet 1/MEM-WR', 'MEM-WR'), ('/Sheet 1/RD-AC', 'RD-AC'), ('/Sheet 1/REG-FUNC', 'REG-FUNC'), ('/Sheet 1/RESET', 'RESET'), ('/Sheet 1/SP{slash}PC-ADDR-OUT', 'SP/PC-ADDR-OUT'), ('/Sheet 1/SP{slash}PC-DATA-OUT-HI', 'SP/PC-DATA-OUT-HI'), ('/Sheet 1/SP{slash}PC-DATA-OUT-LO', 'SP/PC-DATA-OUT-LO'), ('/Sheet 1/SP{slash}PC-DN', 'SP/PC-DN'), ('/Sheet 1/SP{slash}PC-LD-HI', 'SP/PC-LD-HI'), ('/Sheet 1/SP{slash}PC-LD-LO', 'SP/PC-LD-LO'), ('/Sheet 1/SP{slash}PC-SEL', 'SP/PC-SEL'), ('/Sheet 1/SP{slash}PC-UP', 'SP/PC-UP'), ('/Sheet 1/SR-LD', 'SR-LD'), ('Net-(PWR0-PadA)', 'N$10')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 7, text over a symbol body 14, text crossed by a line 0, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: none.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 5, silk_over_copper 199, silk_overlap 59, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 106 symbols, 141 wires, 84 labels, 23 junctions, 0 bus lines, 0 no-connects
