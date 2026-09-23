# alu-v3.0-2layer — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `alu4` in `hardware/cards/alu/eagle/deprecated/v3.0-2layer/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `alu-v3.0-2layer.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `alu-v3.0-2layer.kicad_sch` | root sheet; 9 sub-sheet(s) `alu-v3.0-2layer-sheetN.kicad_sch` mirror the Eagle sheets |
| `alu-v3.0-2layer-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `alu-v3.0-2layer.kicad_pcb` | the board: 2 copper layers, 84 footprints, 2932 track segments, 295 vias |
| `alu-v3.0-2layer-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (158/158 nets)**

```
  same connectivity, different net name: [('-ADD{slash}SUB', '-ADD/SUB'), ('/Sheet 1/AC-LD', 'AC-LD'), ('/Sheet 1/ACI-DATA0', 'ACI-DATA0'), ('/Sheet 1/ACI-DATA1', 'ACI-DATA1'), ('/Sheet 1/ACI-DATA2', 'ACI-DATA2'), ('/Sheet 1/ACI-DATA3', 'ACI-DATA3'), ('/Sheet 1/ACI-DATA4', 'ACI-DATA4'), ('/Sheet 1/ACI-DATA5', 'ACI-DATA5'), ('/Sheet 1/ACI-DATA6', 'ACI-DATA6'), ('/Sheet 1/ACI-DATA7', 'ACI-DATA7'), ('/Sheet 3/-ALU-IO-EN', '-ALU-IO-EN'), ('/Sheet 3/-BUS-OUT', '-BUS-OUT'), ('/Sheet 6/SR-LD', 'SR-LD'), ('CO{slash}BO', 'CO/BO'), ('C{slash}SHIFT', 'C/SHIFT'), ('Net-(IC1B-O)', 'SUB'), ('Net-(IC4A-O)', 'N$3'), ('Net-(IC6B-I1)', 'N$52'), ('Net-(IC6C-O)', 'N$5'), ('Net-(IC7A-O)', 'N$7'), ('Net-(IC14A-O)', 'N$94'), ('Net-(IC14B-O)', 'N$95'), ('Net-(IC14C-O)', 'N$96'), ('Net-(IC14D-O)', 'N$97'), ('Net-(IC15A-O)', 'N$99'), ('Net-(IC15B-O)', 'N$100'), ('Net-(IC15C-O)', 'N$101'), ('Net-(IC15D-O)', 'N$98'), ('Net-(IC18A-O)', 'N$86'), ('Net-(IC18B-O)', 'N$87'), ('Net-(IC18C-O)', 'N$88'), ('Net-(IC18D-O)', 'N$89'), ('Net-(IC19A-O)', 'N$91'), ('Net-(IC19B-O)', 'N$92'), ('Net-(IC19C-O)', 'N$93'), ('Net-(IC19D-O)', 'N$90'), ('Net-(IC21A-O)', 'N$77'), ('Net-(IC21B-O)', 'N$78'), ('Net-(IC21C-O)', 'N$79'), ('Net-(IC21D-O)', 'N$81'), ('Net-(IC22A-O)', 'N$82'), ('Net-(IC22B-O)', 'N$83'), ('Net-(IC22C-O)', 'N$84'), ('Net-(IC22D-O)', 'N$85'), ('Net-(IC24-A<B_O)', 'N$46'), ('Net-(IC24-A=B_O)', 'N$45'), ('Net-(IC24-A>B_O)', 'N$43'), ('Net-(IC25-A<B_O)', 'N$47'), ('Net-(IC25-A=B_O)', 'N$48'), ('Net-(IC25-A>B_O)', 'N$49'), ('Net-(IC26-D4)', 'N$6'), ('Net-(IC26-D6)', 'N$55'), ('Net-(IC26-Y)', 'N$56'), ('Net-(IC27A-I0)', 'N$8'), ('Net-(IC27A-O)', 'N$2'), ('Net-(IC27B-I0)', 'N$1'), ('Net-(IC28-1Y)', 'N$75'), ('Net-(IC28-2Y)', 'N$76'), ('Net-(IC29-QA)', 'N$57'), ('Net-(IC29-QB)', 'N$66'), ('Net-(IC29-QC)', 'N$69'), ('Net-(IC29-QD)', 'N$70'), ('Net-(IC30-QA)', 'N$71'), ('Net-(IC30-QB)', 'N$72'), ('Net-(IC30-QC)', 'N$73'), ('Net-(IC30-QD)', 'N$74'), ('Net-(IC32-1Y)', 'N$11'), ('Net-(IC33A-O)', 'N$28'), ('Net-(IC33B-O)', 'N$12'), ('Net-(IC33C-O)', 'N$26'), ('Net-(IC33D-O)', 'N$27'), ('Net-(IC34A-O)', 'N$29'), ('Net-(IC34B-O)', 'N$13'), ('Net-(IC34C-O)', 'N$31'), ('Net-(IC34D-O)', 'N$32'), ('Net-(IC35-C4)', 'N$41'), ('Net-(IC35-S1)', 'N$33'), ('Net-(IC35-S2)', 'N$34'), ('Net-(IC35-S3)', 'N$35'), ('Net-(IC35-S4)', 'N$36'), ('Net-(IC36-S1)', 'N$37'), ('Net-(IC36-S2)', 'N$38'), ('Net-(IC36-S3)', 'N$39'), ('Net-(IC36-S4)', 'N$40'), ('Net-(PWR0-PadA)', 'N$14')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 20, text over a symbol body 20, text crossed by a line 47, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 90, isolated_pin_label 55, unconnected_wire_endpoint 58.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 199, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 277 symbols, 900 wires, 437 labels, 156 junctions, 31 bus lines, 13 no-connects
