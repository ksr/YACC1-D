# bus-tester-v3.1 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `tester` in `hardware/cards/bus-tester/eagle/v3.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was never fabricated (or its build status is unknown, see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `bus-tester-v3.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `bus-tester-v3.1.kicad_sch` | root sheet; 5 sub-sheet(s) `bus-tester-v3.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `bus-tester-v3.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `bus-tester-v3.1.kicad_pcb` | the board: 4 copper layers, 110 footprints, 2473 track segments, 292 vias |
| `bus-tester-v3.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (239/239 nets)**

```
  same connectivity, different net name: [('/Sheet 3/ARD-RXIN', 'ARD-RXIN'), ('/Sheet 3/ARD-TXOUT', 'ARD-TXOUT'), ('Net-(C10-Pad1)', 'N$9'), ('Net-(IC7-WP)', 'N$2'), ('Net-(IC8-1Q)', 'N$38'), ('Net-(IC8-2Q)', 'N$31'), ('Net-(IC8-3Q)', 'N$35'), ('Net-(IC8-4Q)', 'N$32'), ('Net-(IC8-5Q)', 'N$33'), ('Net-(IC8-6Q)', 'N$34'), ('Net-(IC8-7Q)', 'N$36'), ('Net-(IC8-8Q)', 'N$37'), ('Net-(IC9A-A1)', 'N$40'), ('Net-(IC9A-A2)', 'N$43'), ('Net-(IC9A-A3)', 'N$42'), ('Net-(IC9A-A4)', 'N$41'), ('Net-(IC9B-A1)', 'N$44'), ('Net-(IC9B-A2)', 'N$46'), ('Net-(IC9B-A3)', 'N$47'), ('Net-(IC9B-A4)', 'N$45'), ('Net-(IC10-AREF)', 'N$14'), ('Net-(IC10-PB1(OC1A))', 'N$10'), ('Net-(IC10-PB2(SS{slash}OC1B))', 'N$8'), ('Net-(IC10-PB3(MOSI{slash}OC2))', 'N$7'), ('Net-(IC10-PB4(MISO))', 'N$6'), ('Net-(IC10-PB5(SCK))', 'N$1'), ('Net-(IC10-PB6(XTAL1{slash}TOSC1))', 'N$3'), ('Net-(IC10-PB7(XTAL2{slash}TOSC2))', 'N$4'), ('Net-(IC10-PC0(ADC0))', 'N$18'), ('Net-(IC10-PC1(ADC1))', 'N$19'), ('Net-(IC10-PC2(ADC2))', 'N$39'), ('Net-(IC18-2Q)', 'N$30'), ('Net-(IC18-4Q)', 'N$48'), ('Net-(JP1-DTR)', 'N$28'), ('Net-(JP1-VCC)', 'N$29'), ('Net-(L0-C)', 'N$26'), ('Net-(L1-C)', 'N$25'), ('Net-(L2-C)', 'N$24'), ('Net-(L3-C)', 'N$23'), ('Net-(L4-C)', 'N$22'), ('Net-(L5-C)', 'N$21'), ('Net-(L6-C)', 'N$20'), ('Net-(L7-C)', 'N$17'), ('Net-(LED1-C)', 'N$12'), ('Net-(LED2-C)', 'N$11'), ('Net-(LED3-C)', 'N$13'), ('Net-(LED4-C)', 'N$15'), ('Net-(LED5-C)', 'N$16'), ('Net-(OUT0-C)', 'N$27'), ('Net-(PWR0-PadA)', 'N$5')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 4, text over a symbol body 59, text crossed by a line 33, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 14, unconnected_wire_endpoint 109.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: clearance 8, items_not_allowed 2, lib_footprint_mismatch 9, shorting_items 14, silk_edge_clearance 20, silk_over_copper 199, silk_overlap 32, text_height 8, text_thickness 1, track_dangling 2, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 280 symbols, 830 wires, 454 labels, 123 junctions, 11 bus lines, 26 no-connects
