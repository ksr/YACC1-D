# address-tmp-v1.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Address and TMP V1.0` in `hardware/cards/address-tmp/eagle/deprecated/v1.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `address-tmp-v1.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `address-tmp-v1.0.kicad_sch` | root sheet; 3 sub-sheet(s) `address-tmp-v1.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `address-tmp-v1.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `address-tmp-v1.0.kicad_pcb` | the board: 2 copper layers, 16 footprints, 731 track segments, 57 vias |
| `address-tmp-v1.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (47/47 nets)**

```
  same connectivity, different net name: [('Net-(IC1-ENC)', 'N$1'), ('Net-(IC3-ENC)', 'N$2'), ('Net-(IC5C-O)', 'N$3'), ('Net-(IC5D-O)', 'N$4'), ('Net-(PWR0-PadA)', 'N$11')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 36, text crossed by a line 0, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 14, isolated_pin_label 44, unconnected_wire_endpoint 16.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 155 symbols, 357 wires, 220 labels, 52 junctions, 9 bus lines, 2 no-connects
