# sequencer-memory-v2.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Sequencer-Memory-V2.0` in `hardware/cards/sequencer-memory/eagle/deprecated/v2.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `sequencer-memory-v2.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `sequencer-memory-v2.0.kicad_sch` | root sheet; 4 sub-sheet(s) `sequencer-memory-v2.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `sequencer-memory-v2.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `sequencer-memory-v2.0.kicad_pcb` | the board: 4 copper layers, 62 footprints, 1872 track segments, 169 vias |
| `sequencer-memory-v2.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (105/105 nets)**

```
  same connectivity, different net name: [('/Sheet 1/CMEMSEL', 'CMEMSEL'), ('/Sheet 1/VPGM', 'VPGM'), ('/Sheet 3/ARD-RXIN', 'ARD-RXIN'), ('/Sheet 3/ARD-TXOUT', 'ARD-TXOUT'), ('/Sheet 3/FAULT', 'FAULT'), ('/Sheet 3/LD', 'LD'), ('Net-(C13-Pad1)', 'N$8'), ('Net-(FAULT0-C)', 'N$27'), ('Net-(IC9-WP)', 'N$32'), ('Net-(IC10-AREF)', 'N$17'), ('Net-(IC10-PB6(XTAL1{slash}TOSC1))', 'N$6'), ('Net-(IC10-PB7(XTAL2{slash}TOSC2))', 'N$7'), ('Net-(IC10-PC0(ADC0))', 'N$30'), ('Net-(IC10-PC2(ADC2))', 'N$39'), ('Net-(JP3-DTR)', 'N$33'), ('Net-(JP3-VCC)', 'N$34'), ('Net-(LOADING0-C)', 'N$26'), ('Net-(PWR1-PadA)', 'N$1'), ('Net-(READY0-C)', 'N$25')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 5, text over a symbol body 10, text crossed by a line 15, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: unconnected_wire_endpoint 13.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: lib_footprint_mismatch 2, shorting_items 2, silk_edge_clearance 7, silk_over_copper 199, silk_overlap 80, text_height 7, text_thickness 1, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 114 symbols, 591 wires, 400 labels, 225 junctions, 3 bus lines, 26 no-connects
