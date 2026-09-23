# sequencer-logic-v2.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Sequencer-Logic-Prod-V2.0` in `hardware/cards/sequencer-logic/eagle/deprecated/v2.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `sequencer-logic-v2.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `sequencer-logic-v2.0.kicad_sch` | root sheet; 9 sub-sheet(s) `sequencer-logic-v2.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `sequencer-logic-v2.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `sequencer-logic-v2.0.kicad_pcb` | the board: 4 copper layers, 106 footprints, 3764 track segments, 516 vias |
| `sequencer-logic-v2.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (274/274 nets)**

```
  same connectivity, different net name: [('/Sheet 1/-DO-INT', '-DO-INT'), ('/Sheet 1/CNT-CLK', 'CNT-CLK'), ('/Sheet 1/COUNT-FAULT', 'COUNT-FAULT'), ('/Sheet 1/DO-HALT', 'DO-HALT'), ('/Sheet 1/HALT-CLR', 'HALT-CLR'), ('/Sheet 1/LD-INS-REG1', 'LD-INS-REG1'), ('/Sheet 1/UCODE-CLK', 'UCODE-CLK'), ('/Sheet 2/SPARE1', 'SPARE1'), ('/Sheet 2/SPARE2', 'SPARE2'), ('/Sheet 3/INT-EDGE', 'INT-EDGE'), ('/Sheet 4/-BRANCH-HI-SELECTED', '-BRANCH-HI-SELECTED'), ('/Sheet 5/-FP-HALT', '-FP-HALT'), ('/Sheet 5/-HALT-CONT', '-HALT-CONT'), ('/Sheet 5/EXTERNAL-SINGLESTEP-CLK', 'EXTERNAL-SINGLESTEP-CLK'), ('/Sheet 5/FP-CLKL', 'FP-CLKL'), ('/Sheet 5/FP-SINGLE-STEP-CLK', 'FP-SINGLE-STEP-CLK'), ('/Sheet 5/FP-SS', 'FP-SS'), ('/Sheet 6/TMP', 'TMP'), ('Net-(-INT-PULLUP0-Pad1)', 'N$49'), ('Net-(.0-PadA)', 'N$59'), ('Net-(IC1A-A1)', 'N$2'), ('Net-(IC1A-A2)', 'N$3'), ('Net-(IC1A-A3)', 'N$10'), ('Net-(IC1A-A4)', 'N$23'), ('Net-(IC1B-A1)', 'N$34'), ('Net-(IC1B-A2)', 'N$35'), ('Net-(IC1B-A3)', 'N$36'), ('Net-(IC1B-A4)', 'N$37'), ('Net-(IC2A-A1)', 'N$7'), ('Net-(IC2A-A2)', 'N$8'), ('Net-(IC2A-A3)', 'N$9'), ('Net-(IC2A-A4)', 'N$11'), ('Net-(IC2B-A1)', 'N$12'), ('Net-(IC2B-A2)', 'N$13'), ('Net-(IC2B-A3)', 'N$14'), ('Net-(IC2B-A4)', 'N$15'), ('Net-(IC3-D1)', 'N$19'), ('Net-(IC3-D2)', 'N$20'), ('Net-(IC3-D3)', 'N$21'), ('Net-(IC3-D4)', 'N$22'), ('Net-(IC4-D1)', 'N$5'), ('Net-(IC4-D2)', 'N$6'), ('Net-(IC4-D3)', 'N$17'), ('Net-(IC4-D4)', 'N$18'), ('Net-(IC5-UP)', 'N$1'), ('Net-(IC7A-O)', 'N$31'), ('Net-(IC7C-I0)', 'N$40'), ('Net-(IC10A-I1)', 'N$55'), ('Net-(IC10A-O)', 'COUNT-RESET'), ('Net-(IC10B-I0)', 'N$39'), ('Net-(IC10B-I1)', 'N$38'), ('Net-(IC10D-O)', 'N$26'), ('Net-(IC11B-I)', 'N$27'), ('Net-(IC11B-O)', 'N$29'), ('Net-(IC11E-I)', 'N$42'), ('Net-(IC11E-O)', 'N$46'), ('Net-(IC11F-I)', 'N$43'), ('Net-(IC11F-O)', 'N$41'), ('Net-(IC12B-I0)', 'N$53'), ('Net-(IC12C-I0)', 'N$28'), ('Net-(IC12C-I1)', 'N$24'), ('Net-(IC12D-O)', 'N$54'), ('Net-(IC21A-I1)', 'N$25'), ('Net-(IC21C-O)', 'N$48'), ('Net-(IC22B-CLK)', 'N$33'), ('Net-(IC23A-I0)', 'FP-RESET'), ('Net-(IC23B-I1)', 'FP-EXECUTE'), ('Net-(IC23C-O)', 'N$32'), ('Net-(IC24B-I0)', 'N$56'), ('Net-(IC24B-I1)', 'N$52'), ('Net-(IC24D-O)', 'N$47'), ('Net-(IC29A-O)', 'N$50'), ('Net-(IC29B-I1)', 'N$4'), ('Net-(IC29C-I0)', 'N$51'), ('Net-(IC30A-O)', 'N$44'), ('Net-(IC31A-I0)', 'FP-FREERUN'), ('Net-(IC31C-I1)', 'HARD-RESET1'), ('Net-(IC31D-I1)', 'FP-CLKH'), ('Net-(IC33A-A1)', 'N$62'), ('Net-(IC33A-A2)', 'N$63'), ('Net-(IC33A-A3)', 'N$64'), ('Net-(IC33A-A4)', 'N$65'), ('Net-(IC33B-A1)', 'N$66'), ('Net-(IC33B-A2)', 'N$68'), ('Net-(IC33B-A3)', 'N$69'), ('Net-(IC33B-A4)', 'N$70'), ('Net-(IC35A-O)', 'N$45'), ('Net-(IC36C-O)', 'N$16'), ('Net-(PWR0-PadA)', 'N$30'), ('SINGLE-STEP{slash}WAIT', 'SINGLE-STEP/WAIT')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 4, text over a symbol body 25, text crossed by a line 49, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 87, isolated_pin_label 21, pin_not_driven 1, unconnected_wire_endpoint 19.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: clearance 4, items_not_allowed 2, lib_footprint_mismatch 3, shorting_items 14, silk_edge_clearance 25, silk_over_copper 199, silk_overlap 199, starved_thermal 1, text_height 38, text_thickness 36, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 275 symbols, 1047 wires, 501 labels, 221 junctions, 1 bus lines, 29 no-connects
