# memory-v1.3 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Memory V1.3` in `hardware/cards/memory/eagle/v1.3/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was never fabricated (or its build status is unknown, see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `memory-v1.3.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `memory-v1.3.kicad_sch` | root sheet; 6 sub-sheet(s) `memory-v1.3-sheetN.kicad_sch` mirror the Eagle sheets |
| `memory-v1.3-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `memory-v1.3.kicad_pcb` | the board: 4 copper layers, 52 footprints, 968 track segments, 80 vias |
| `memory-v1.3-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (115/115 nets)**

```
  same connectivity, different net name: [('/Sheet 3/-LO-RAM', '-LO-RAM'), ('Net-(IC1-~{OE})', 'N$3'), ('Net-(IC1-~{WE})', 'N$4'), ('Net-(IC4-I0)', 'N$5'), ('Net-(IC4-I1)', 'N$6'), ('Net-(IC4-I2)', 'N$7'), ('Net-(IC4-I3)', 'N$8'), ('Net-(IC4-I4)', 'N$9'), ('Net-(IC4-I5)', 'N$10'), ('Net-(IC4-I6)', 'N$26'), ('Net-(IC4-I7)', 'N$27'), ('Net-(IC4-O)', 'N$14'), ('Net-(IC6A-I)', 'MEM-RD'), ('Net-(IC6B-I)', 'N$2'), ('Net-(IC7-G2B)', 'N$24'), ('Net-(IC7-Y0)', 'N$43'), ('Net-(IC7-Y1)', 'N$42'), ('Net-(IC7-Y2)', 'N$41'), ('Net-(IC7-Y3)', 'N$40'), ('Net-(IC7-Y4)', 'N$39'), ('Net-(IC7-Y5)', 'N$38'), ('Net-(IC7-Y6)', 'N$37'), ('Net-(IC7-Y7)', 'N$36'), ('Net-(IC10A-I0)', 'N$13'), ('Net-(IC10A-I1)', 'N$12'), ('Net-(IC10B-I1)', 'N$22'), ('Net-(IC10B-O)', 'N$20'), ('Net-(IC10C-O)', 'N$19'), ('Net-(IC10D-I0)', 'N$25'), ('Net-(IC11-1A)', 'N$15'), ('Net-(IC11-2A)', 'N$16'), ('Net-(IC11-3A)', 'N$17'), ('Net-(IC11-4A)', 'N$18'), ('Net-(IC14A-O)', 'N$33'), ('Net-(IC14F-O)', 'N$47'), ('Net-(IC18-I0)', 'N$32'), ('Net-(IC18-I1)', 'N$34'), ('Net-(IC18-I2)', 'N$35'), ('Net-(IC18-I3)', 'N$44'), ('Net-(IC18-I4)', 'N$31'), ('Net-(IC18-I5)', 'N$30'), ('Net-(IC18-I6)', 'N$29'), ('Net-(IC18-I7)', 'N$28'), ('Net-(IC18-O)', 'N$1'), ('Net-(PWR0-PadA)', 'N$11')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 73, text crossed by a line 22, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 33, isolated_pin_label 43, missing_input_pin 1, missing_power_pin 1, missing_unit 1, pin_not_connected 2, unconnected_wire_endpoint 22.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 24, text_height 2, text_thickness 1, track_dangling 17; unconnected items 100; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 197 symbols, 620 wires, 290 labels, 117 junctions, 11 bus lines, 8 no-connects
