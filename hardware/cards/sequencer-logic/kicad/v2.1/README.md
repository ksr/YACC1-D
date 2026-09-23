# sequencer-logic-v2.1 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Sequencer-Logic-Prod-V2.1l` in `hardware/cards/sequencer-logic/eagle/v2.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `sequencer-logic-v2.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `sequencer-logic-v2.1.kicad_sch` | root sheet; 10 sub-sheet(s) `sequencer-logic-v2.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `sequencer-logic-v2.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `sequencer-logic-v2.1.kicad_pcb` | the board: 4 copper layers, 108 footprints, 3126 track segments, 481 vias |
| `sequencer-logic-v2.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (282/282 nets)**

```
  same connectivity, different net name: [('/Sheet 1/-DO-INT', '-DO-INT'), ('/Sheet 1/CNT-CLK', 'CNT-CLK'), ('/Sheet 1/COUNT-FAULT', 'COUNT-FAULT'), ('/Sheet 1/DO-HALT', 'DO-HALT'), ('/Sheet 1/HALT-CLR', 'HALT-CLR'), ('/Sheet 1/LD-INS-REG1', 'LD-INS-REG1'), ('/Sheet 1/UCODE-CLK', 'UCODE-CLK'), ('/Sheet 2/SPARE3', 'SPARE3'), ('/Sheet 3/INT-EDGE', 'INT-EDGE'), ('/Sheet 3/INT-LEVEL', 'INT-LEVEL'), ('/Sheet 5/-FP-HALT', '-FP-HALT'), ('/Sheet 5/-HALT-CONT', '-HALT-CONT'), ('/Sheet 5/EXTERNAL-SINGLESTEP-CLK', 'EXTERNAL-SINGLESTEP-CLK'), ('/Sheet 5/FP-CLKL', 'FP-CLKL'), ('/Sheet 5/FP-SINGLE-STEP-CLK', 'FP-SINGLE-STEP-CLK'), ('/Sheet 5/FP-SS', 'FP-SS'), ('/Sheet 6/-ONE-OPERAND-SEL', '-ONE-OPERAND-SEL'), ('Net-(-INT-PULLUP0-Pad1)', 'N$49'), ('Net-(.0-PadA)', 'N$59'), ('Net-(IC1A-Y1)', 'N$5'), ('Net-(IC1A-Y2)', 'N$6'), ('Net-(IC1A-Y3)', 'N$17'), ('Net-(IC1A-Y4)', 'N$18'), ('Net-(IC1B-Y1)', 'N$19'), ('Net-(IC1B-Y2)', 'N$20'), ('Net-(IC1B-Y3)', 'N$21'), ('Net-(IC1B-Y4)', 'N$22'), ('Net-(IC11A-A1)', 'N$66'), ('Net-(IC11A-A2)', 'N$68'), ('Net-(IC11A-A3)', 'N$69'), ('Net-(IC11A-A4)', 'N$61'), ('Net-(IC15A-A1)', 'N$2'), ('Net-(IC15A-A2)', 'N$3'), ('Net-(IC15A-A3)', 'N$10'), ('Net-(IC15A-A4)', 'N$23'), ('Net-(IC15B-A1)', 'N$34'), ('Net-(IC15B-A2)', 'N$35'), ('Net-(IC15B-A3)', 'N$36'), ('Net-(IC15B-A4)', 'N$37'), ('Net-(IC18A-A1)', 'N$62'), ('Net-(IC18A-A2)', 'N$63'), ('Net-(IC18A-A3)', 'N$64'), ('Net-(IC18A-A4)', 'N$65'), ('Net-(IC22A-I0)', 'N$27'), ('Net-(IC22A-I1)', 'N$25'), ('Net-(IC22A-O)', 'N$24'), ('Net-(IC22C-O)', 'N$48'), ('Net-(IC23A-CLR)', 'N$29'), ('Net-(IC23A-PRE)', 'N$41'), ('Net-(IC23A-Q)', 'N$28'), ('Net-(IC23B-CLK)', 'N$33'), ('Net-(IC24B-I0)', 'N$53'), ('Net-(IC24B-O)', 'N$58'), ('Net-(IC24D-O)', 'N$54'), ('Net-(IC25A-O)', 'N$45'), ('Net-(IC25C-I1)', 'N$47'), ('Net-(IC25C-O)', 'N$56'), ('Net-(IC25D-I0)', 'N$32'), ('Net-(IC26A-I1)', 'N$55'), ('Net-(IC26A-O)', 'COUNT-RESET'), ('Net-(IC26B-I0)', 'N$39'), ('Net-(IC26B-I1)', 'N$38'), ('Net-(IC26C-I0)', 'N$72'), ('Net-(IC26C-I1)', 'N$71'), ('Net-(IC26C-O)', 'N$60'), ('Net-(IC26D-O)', 'N$26'), ('Net-(IC27B-I1)', 'N$4'), ('Net-(IC27C-I0)', 'N$51'), ('Net-(IC27C-O)', 'N$52'), ('Net-(IC27D-O)', 'N$57'), ('Net-(IC29A-I0)', 'FP-FREERUN'), ('Net-(IC29C-I1)', 'HARD-RESET1'), ('Net-(IC29D-I1)', 'FP-CLKH'), ('Net-(IC30A-I0)', 'N$70'), ('Net-(IC30A-O)', 'N$67'), ('Net-(IC31C-O)', 'N$16'), ('Net-(IC32A-I0)', 'FP-RESET'), ('Net-(IC32B-I1)', 'FP-EXECUTE'), ('Net-(IC32C-I1)', 'N$46'), ('Net-(IC33-CO)', 'N$1'), ('Net-(IC33-QA)', 'N$7'), ('Net-(IC33-QB)', 'N$8'), ('Net-(IC33-QC)', 'N$9'), ('Net-(IC33-QD)', 'N$11'), ('Net-(IC34-QA)', 'N$12'), ('Net-(IC34-QB)', 'N$13'), ('Net-(IC34-QC)', 'N$14'), ('Net-(IC34-QD)', 'N$15'), ('Net-(IC36E-I)', 'N$42'), ('Net-(IC37A-O)', 'N$44'), ('Net-(IC38A-O)', 'N$31'), ('Net-(IC38C-I0)', 'N$40'), ('Net-(PWR0-PadA)', 'N$30'), ('SINGLE-STEP{slash}WAIT', 'SINGLE-STEP/WAIT')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 13, text over a symbol body 23, text crossed by a line 50, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 89, isolated_pin_label 18, unconnected_wire_endpoint 14.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: clearance 8, items_not_allowed 2, lib_footprint_mismatch 2, silk_edge_clearance 25, silk_over_copper 199, silk_overlap 199, text_height 40, text_thickness 38, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 278 symbols, 1069 wires, 510 labels, 233 junctions, 1 bus lines, 25 no-connects
