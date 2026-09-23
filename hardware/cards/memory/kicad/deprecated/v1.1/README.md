# memory-v1.1 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Memory V1.0` in `hardware/cards/memory/eagle/deprecated/v1.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `memory-v1.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `memory-v1.1.kicad_sch` | root sheet; 5 sub-sheet(s) `memory-v1.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `memory-v1.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `memory-v1.1.kicad_pcb` | the board: 2 copper layers, 19 footprints, 884 track segments, 43 vias |
| `memory-v1.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (75/75 nets)**

```
  same connectivity, different net name: [('Net-(IC1-~{OE})', 'N$3'), ('Net-(IC1-~{WE})', 'N$4'), ('Net-(IC4-I1)', 'N$10'), ('Net-(IC4-I2)', 'N$9'), ('Net-(IC4-I3)', 'N$8'), ('Net-(IC4-I4)', 'N$7'), ('Net-(IC4-I5)', 'N$6'), ('Net-(IC4-I6)', 'N$5'), ('Net-(IC4-I7)', 'N$1'), ('Net-(IC4-O)', 'N$14'), ('Net-(IC6A-I)', 'MEM-RD'), ('Net-(IC6B-I)', 'N$2'), ('Net-(IC10A-I0)', 'N$12'), ('Net-(IC10A-O)', 'N$13'), ('Net-(IC11-1A)', 'N$15'), ('Net-(IC11-2A)', 'N$16'), ('Net-(IC11-3A)', 'N$17'), ('Net-(IC11-4A)', 'N$18'), ('Net-(PWR0-PadA)', 'N$11')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 38, text crossed by a line 0, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 21, isolated_pin_label 57, unconnected_wire_endpoint 24.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 172 symbols, 414 wires, 214 labels, 67 junctions, 7 bus lines, 6 no-connects
