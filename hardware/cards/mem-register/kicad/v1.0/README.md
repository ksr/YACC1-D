# mem-register-v1.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Mem Register V1.0` in `hardware/cards/mem-register/eagle/v1.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `mem-register-v1.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `mem-register-v1.0.kicad_sch` | root sheet; 3 sub-sheet(s) `mem-register-v1.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `mem-register-v1.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `mem-register-v1.0.kicad_pcb` | the board: 2 copper layers, 90 footprints, 1651 track segments, 107 vias |
| `mem-register-v1.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (107/107 nets)**

```
  same connectivity, different net name: [('Net-(IC1A-O)', 'N$19'), ('Net-(IC1B-O)', 'N$37'), ('Net-(IC1C-O)', 'N$82'), ('Net-(IC2-G1)', 'N$6'), ('Net-(IC4-A=B_I)', 'N$8'), ('Net-(IC4-B0)', 'N$28'), ('Net-(IC4-B1)', 'N$46'), ('Net-(IC4-B2)', 'N$64'), ('Net-(IC4-B3)', 'N$73'), ('Net-(IC5-G2A)', 'N$4'), ('Net-(IC6-G2B)', 'N$3'), ('Net-(IC7A-O)', 'N$2'), ('Net-(PWR0-PadA)', 'N$11'), ('Net-(RD1-PadA)', 'N$1'), ('Net-(RD2-PadA)', 'N$7'), ('Net-(RD3-PadA)', 'N$5'), ('Net-(RD4-PadA)', 'N$10'), ('Net-(RD5-PadA)', 'N$12'), ('Net-(RD6-PadA)', 'N$15'), ('Net-(RD7-PadA)', 'N$13'), ('Net-(RD8-PadA)', 'N$14'), ('Net-(RD9-PadA)', 'N$9'), ('Net-(RD10-PadA)', 'N$16'), ('Net-(RD11-PadA)', 'N$17'), ('Net-(RD12-PadA)', 'N$18'), ('Net-(RD13-PadA)', 'N$20'), ('Net-(RD14-PadA)', 'N$21'), ('Net-(RD15-PadA)', 'N$22'), ('Net-(RD16-PadA)', 'N$23'), ('Net-(RN3-Pad2)', 'N$24'), ('Net-(RN3-Pad3)', 'N$25'), ('Net-(RN3-Pad4)', 'N$26'), ('Net-(RN3-Pad5)', 'N$27'), ('Net-(RN3-Pad6)', 'N$30'), ('Net-(RN3-Pad7)', 'N$29'), ('Net-(RN3-Pad8)', 'N$31'), ('Net-(RN3-Pad9)', 'N$32'), ('Net-(RN5-Pad2)', 'N$33'), ('Net-(RN5-Pad3)', 'N$41'), ('Net-(RN5-Pad4)', 'N$34'), ('Net-(RN5-Pad5)', 'N$40'), ('Net-(RN5-Pad6)', 'N$35'), ('Net-(RN5-Pad7)', 'N$39'), ('Net-(RN5-Pad8)', 'N$36'), ('Net-(RN5-Pad9)', 'N$38')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 4, text over a symbol body 77, text crossed by a line 90, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 27, isolated_pin_label 56, unconnected_wire_endpoint 96.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 91, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 203 symbols, 664 wires, 430 labels, 83 junctions, 33 bus lines, 3 no-connects
