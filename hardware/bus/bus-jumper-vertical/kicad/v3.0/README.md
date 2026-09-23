# bus-jumper-vertical-v3.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Jumper Board V3.0` in `hardware/bus/bus-jumper-vertical/eagle/v3.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `bus-jumper-vertical-v3.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `bus-jumper-vertical-v3.0.kicad_sch` | root sheet; 1 sub-sheet(s) `bus-jumper-vertical-v3.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `bus-jumper-vertical-v3.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `bus-jumper-vertical-v3.0.kicad_pcb` | the board: 2 copper layers, 7 footprints, 354 track segments, 0 vias |
| `bus-jumper-vertical-v3.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (89/89 nets)**

```
  same connectivity, different net name: [('/Sheet 1/GND', 'GND'), ('/Sheet 1/V1', 'V1'), ('/Sheet 1/V2', 'V2'), ('Net-(PWR1-PadA)', 'N$35'), ('Net-(PWR2-PadA)', 'N$36'), ('Net-(X3AA-S)', 'N$29'), ('Net-(X3AB-S)', 'N$30'), ('Net-(X3AC-S)', 'N$31'), ('Net-(X3AD-S)', 'N$32'), ('Net-(X3AI-S)', 'N$37'), ('Net-(X3AJ-S)', 'N$38'), ('Net-(X3AK-S)', 'N$39'), ('Net-(X3AL-S)', 'N$40'), ('Net-(X3AM-S)', 'N$41'), ('Net-(X3AN-S)', 'N$42'), ('Net-(X3AO-S)', 'N$43'), ('Net-(X3AP-S)', 'N$44'), ('Net-(X3AQ-S)', 'N$45'), ('Net-(X3AR-S)', 'N$46'), ('Net-(X3AS-S)', 'N$47'), ('Net-(X3AT-S)', 'N$48'), ('Net-(X3AU-S)', 'N$49'), ('Net-(X3AV-S)', 'N$50'), ('Net-(X3AW-S)', 'N$51'), ('Net-(X3AX-S)', 'N$52'), ('Net-(X3AY-S)', 'N$53'), ('Net-(X3AZ-S)', 'N$54'), ('Net-(X3BA-S)', 'N$55'), ('Net-(X3BB-S)', 'N$56'), ('Net-(X3BC-S)', 'N$57'), ('Net-(X3BD-S)', 'N$58'), ('Net-(X3BE-S)', 'N$59'), ('Net-(X3BF-S)', 'N$60'), ('Net-(X3BG-S)', 'N$61'), ('Net-(X3BH-S)', 'N$62'), ('Net-(X3BI-S)', 'N$63'), ('Net-(X3BJ-S)', 'N$64'), ('Net-(X3BO-S)', 'N$69'), ('Net-(X3BP-S)', 'N$70'), ('Net-(X3BQ-S)', 'N$71'), ('Net-(X3BR-S)', 'N$72'), ('Net-(X3BS-S)', 'N$73'), ('Net-(X3BT-S)', 'N$74'), ('Net-(X3BU-S)', 'N$75'), ('Net-(X3BV-S)', 'N$76'), ('Net-(X3BW-S)', 'N$77'), ('Net-(X3BX-S)', 'N$78'), ('Net-(X3BY-S)', 'N$79'), ('Net-(X3BZ-S)', 'N$80'), ('Net-(X3C-S)', 'N$4'), ('Net-(X3CA-S)', 'N$81'), ('Net-(X3CB-S)', 'N$82'), ('Net-(X3CC-S)', 'N$83'), ('Net-(X3CD-S)', 'N$84'), ('Net-(X3CE-S)', 'N$85'), ('Net-(X3CF-S)', 'N$86'), ('Net-(X3CG-S)', 'N$87'), ('Net-(X3CH-S)', 'N$88'), ('Net-(X3CI-S)', 'N$89'), ('Net-(X3CJ-S)', 'N$90'), ('Net-(X3CK-S)', 'N$91'), ('Net-(X3CL-S)', 'N$92'), ('Net-(X3CM-S)', 'N$93'), ('Net-(X3CN-S)', 'N$94'), ('Net-(X3CO-S)', 'N$95'), ('Net-(X3CP-S)', 'N$96'), ('Net-(X3D-S)', 'N$6'), ('Net-(X3E-S)', 'N$7'), ('Net-(X3F-S)', 'N$8'), ('Net-(X3G-S)', 'N$9'), ('Net-(X3H-S)', 'N$10'), ('Net-(X3I-S)', 'N$11'), ('Net-(X3J-S)', 'N$12'), ('Net-(X3K-S)', 'N$13'), ('Net-(X3L-S)', 'N$14'), ('Net-(X3M-S)', 'N$15'), ('Net-(X3N-S)', 'N$16'), ('Net-(X3O-S)', 'N$17'), ('Net-(X3P-S)', 'N$18'), ('Net-(X3Q-S)', 'N$19'), ('Net-(X3R-S)', 'N$20'), ('Net-(X3S-S)', 'N$21'), ('Net-(X3T-S)', 'N$22'), ('Net-(X3U-S)', 'N$23'), ('Net-(X3V-S)', 'N$24'), ('Net-(X3W-S)', 'N$25'), ('Net-(X3X-S)', 'N$26'), ('Net-(X3Y-S)', 'N$27'), ('Net-(X3Z-S)', 'N$28')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 0, text crossed by a line 0, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: none.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 4, lib_footprint_mismatch 2, silk_over_copper 4; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 197 symbols, 112 wires, 22 labels, 0 junctions, 0 bus lines, 0 no-connects
