# io-v1.1 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `IO V1.1` in `hardware/cards/io/eagle/v1.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `io-v1.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `io-v1.1.kicad_sch` | root sheet; 6 sub-sheet(s) `io-v1.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `io-v1.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `io-v1.1.kicad_pcb` | the board: 2 copper layers, 71 footprints, 1409 track segments, 158 vias |
| `io-v1.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (104/104 nets)**

```
  same connectivity, different net name: [('/Sheet 2/ICLK', 'ICLK'), ('/Sheet 2/RX', 'RX'), ('/Sheet 2/RX-IN', 'RX-IN'), ('/Sheet 2/TX-OUT', 'TX-OUT'), ('/Sheet 5/-IO-ADDRSEL', '-IO-ADDRSEL'), ('/Sheet 5/-IO-DATASEL', '-IO-DATASEL'), ('/Sheet 5/-IO-SEL0', '-IO-SEL0'), ('/Sheet 5/-IO-SEL1', '-IO-SEL1'), ('/Sheet 5/-IO-SEL2', '-IO-SEL2'), ('/Sheet 5/-IO-SEL3', '-IO-SEL3'), ('/Sheet 5/-IO-SEL4', '-IO-SEL4'), ('/Sheet 5/-IO-SEL5', '-IO-SEL5'), ('/Sheet 5/-IO-SEL6', '-IO-SEL6'), ('/Sheet 5/-IO-SEL7', '-IO-SEL7'), ('Net-(HI0A-D0)', 'N$70'), ('Net-(HI0A-D1)', 'N$69'), ('Net-(HI0A-D2)', 'N$68'), ('Net-(HI0A-D3)', 'N$28'), ('Net-(IC1-INT)', 'N$57'), ('Net-(IC1-TX)', 'N$37'), ('Net-(IC1-XTAL1)', 'N$31'), ('Net-(IC2-C1+)', 'N$63'), ('Net-(IC2-C1-)', 'N$62'), ('Net-(IC2-C2+)', 'N$52'), ('Net-(IC2-C2-)', 'N$51'), ('Net-(IC2-V+)', 'N$64'), ('Net-(IC2-V-)', 'N$65'), ('Net-(IC3A-A1)', 'N$1'), ('Net-(IC3A-A2)', 'N$2'), ('Net-(IC3A-A3)', 'N$3'), ('Net-(IC3A-A4)', 'N$4'), ('Net-(IC3A-G)', 'N$32'), ('Net-(IC3B-A1)', 'N$5'), ('Net-(IC3B-A2)', 'N$6'), ('Net-(IC3B-A3)', 'N$7'), ('Net-(IC3B-A4)', 'N$8'), ('Net-(IC4-CLK)', 'N$41'), ('Net-(IC4-Q1)', 'N$26'), ('Net-(IC4-Q2)', 'N$25'), ('Net-(IC4-Q3)', 'N$24'), ('Net-(IC4-Q4)', 'N$23'), ('Net-(IC4-Q5)', 'N$22'), ('Net-(IC4-Q6)', 'N$21'), ('Net-(IC4-Q7)', 'N$20'), ('Net-(IC4-Q8)', 'N$19'), ('Net-(IC5-G1)', 'N$29'), ('Net-(IC5-G2A)', 'N$27'), ('Net-(IC6C-O)', 'N$33'), ('Net-(IC7A-O)', 'N$30'), ('Net-(IC7B-I0)', 'N$67'), ('Net-(IC8F-I)', 'N$66'), ('Net-(IC9-Q1)', 'N$74'), ('Net-(IC9-Q2)', 'N$73'), ('Net-(IC9-Q3)', 'N$72'), ('Net-(IC9-Q4)', 'N$71'), ('Net-(IC10-CLK)', 'N$40'), ('Net-(IC11A-O)', 'N$75'), ('Net-(IN0-P)', 'N$34'), ('Net-(J1-Pad2)', 'N$35'), ('Net-(J1-Pad3)', 'N$36'), ('Net-(OUT0-PadA)', 'N$9'), ('Net-(PWR0-PadA)', 'N$11'), ('Net-(R3-Pad1)', 'N$14'), ('Net-(R4-Pad1)', 'N$15'), ('Net-(R5-Pad1)', 'N$10'), ('Net-(R6-Pad1)', 'N$12'), ('Net-(R7-Pad1)', 'N$13'), ('Net-(R8-Pad1)', 'N$16'), ('Net-(R9-Pad1)', 'N$18'), ('Net-(R10-Pad1)', 'N$17'), ('Net-(TM1-S)', 'N$44')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 13, text over a symbol body 57, text crossed by a line 22, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 38, isolated_pin_label 66, pin_not_connected 8, pin_not_driven 1, unconnected_wire_endpoint 17.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 22, lib_footprint_mismatch 2, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 60, text_height 4, text_thickness 1; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 214 symbols, 595 wires, 204 labels, 103 junctions, 8 bus lines, 17 no-connects
