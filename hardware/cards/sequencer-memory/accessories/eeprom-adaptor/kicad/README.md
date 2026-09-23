# sequencer-memory-eeprom-adaptor — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `eeprom adaptor` in `hardware/cards/sequencer-memory/accessories/eeprom-adaptor/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `sequencer-memory-eeprom-adaptor.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `sequencer-memory-eeprom-adaptor.kicad_sch` | root sheet; 1 sub-sheet(s) `sequencer-memory-eeprom-adaptor-sheetN.kicad_sch` mirror the Eagle sheets |
| `sequencer-memory-eeprom-adaptor-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `sequencer-memory-eeprom-adaptor.kicad_pcb` | the board: 2 copper layers, 2 footprints, 37 track segments, 0 vias |
| `sequencer-memory-eeprom-adaptor-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (5/5 nets)**

```
  same connectivity, different net name: [('/Sheet 1/SCL', 'SCL'), ('/Sheet 1/SDA', 'SDA'), ('/Sheet 1/WP', 'WP')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 0, text crossed by a line 0, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: pin_not_driven 1, power_pin_not_driven 2.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: silk_over_copper 16; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 2 symbols, 30 wires, 8 labels, 7 junctions, 0 bus lines, 0 no-connects
