# video-v1.0-fusion-export-2026-09-18 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Video_1.0` in `hardware/cards/video/eagle/v1.0-fusion-export-2026-09-18/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `video-v1.0-fusion-export-2026-09-18.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `video-v1.0-fusion-export-2026-09-18.kicad_sch` | root sheet; 2 sub-sheet(s) `video-v1.0-fusion-export-2026-09-18-sheetN.kicad_sch` mirror the Eagle sheets |
| `video-v1.0-fusion-export-2026-09-18-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `video-v1.0-fusion-export-2026-09-18.kicad_pcb` | the board: 2 copper layers, 47 footprints, 1180 track segments, 96 vias |
| `video-v1.0-fusion-export-2026-09-18-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MISMATCH (115/117 nets)**

```
  ONLY IN SCHEMATIC +5V        [('C16', '+'), ('C17', '1'), ('C18', '1'), ('C19', '1'), ('C20', '1'), ('C21', '1'), ('C22', '1'), ('C23', '1'), ('C24', '1'), ('C25', '1'), ('C26', '1'), ('C27', '1'), ('C28', '1'), ('C29', '1'), ('C3', '1'), ('IC15', '2'), ('R10', '2'), ('R12', '1'), ('RN2', '1')]
  ONLY IN SCHEMATIC VCC        [('IC1', '14'), ('IC15', '48'), ('IC17', '20'), ('IC18', '16'), ('IC19', '14'), ('IC2', '20'), ('IC20', '14'), ('IC21', '5'), ('IC22', '16'), ('IC23', '16'), ('IC24', '16'), ('IC25', '24'), ('IC26', '14'), ('IC27', '14'), ('IC28', '16'), ('JP1', '3'), ('R2', '2'), ('X1', 'A2'), ('X1', 'A31'), ('X1', 'B2'), ('X1', 'B31'), ('X1', 'C2'), ('X1', 'C31')]
  ONLY ON BOARD     +5V        [('C16', '+'), ('C17', '1'), ('C18', '1'), ('C19', '1'), ('C20', '1'), ('C21', '1'), ('C22', '1'), ('C23', '1'), ('C24', '1'), ('C25', '1'), ('C26', '1'), ('C27', '1'), ('C28', '1'), ('C29', '1'), ('C3', '1'), ('IC1', '14'), ('IC15', '2'), ('IC2', '20'), ('R10', '2'), ('R12', '1'), ('RN2', '1')]
  ONLY ON BOARD     VCC        [('IC15', '48'), ('IC17', '20'), ('IC18', '16'), ('IC19', '14'), ('IC20', '14'), ('IC21', '5'), ('IC22', '16'), ('IC23', '16'), ('IC24', '16'), ('IC25', '24'), ('IC26', '14'), ('IC27', '14'), ('IC28', '16'), ('JP1', '3'), ('R2', '2'), ('X1', 'A2'), ('X1', 'A31'), ('X1', 'B2'), ('X1', 'B31'), ('X1', 'C2'), ('X1', 'C31')]
  same connectivity, different net name: [('/Sheet 1/BOARDSEL', 'BOARDSEL'), ('/Sheet 1/CHARCLOCK', 'CHARCLOCK'), ('/Sheet 1/CLK', 'CLK'), ('/Sheet 1/CRTCCLOCK', 'CRTCCLOCK'), ('/Sheet 1/DOTCLOCK', 'DOTCLOCK'), ('/Sheet 1/VADDR0', 'VADDR0'), ('/Sheet 1/VADDR1', 'VADDR1'), ('/Sheet 1/VADDR2', 'VADDR2'), ('/Sheet 1/VADDR3', 'VADDR3'), ('/Sheet 1/VADDR4', 'VADDR4'), ('/Sheet 1/VADDR5', 'VADDR5'), ('/Sheet 1/VADDR6', 'VADDR6'), ('/Sheet 1/VADDR7', 'VADDR7'), ('/Sheet 1/VADDR8', 'VADDR8'), ('/Sheet 1/VADDR9', 'VADDR9'), ('/Sheet 1/VADDR10', 'VADDR10'), ('/Sheet 1/VADDR11', 'VADDR11'), ('/Sheet 1/VDATA0', 'VDATA0'), ('/Sheet 1/VDATA1', 'VDATA1'), ('/Sheet 1/VDATA2', 'VDATA2'), ('/Sheet 1/VDATA3', 'VDATA3'), ('/Sheet 1/VDATA4', 'VDATA4'), ('/Sheet 1/VDATA5', 'VDATA5'), ('/Sheet 1/VDATA7', 'VDATA7'), ('/Sheet 1/VROWS0', 'VROWS0'), ('/Sheet 1/VROWS1', 'VROWS1'), ('/Sheet 1/VROWS2', 'VROWS2'), ('Net-(IC1A-I0)', 'N$1'), ('Net-(IC1A-I1)', 'N$4'), ('Net-(IC1B-O)', 'N$17'), ('Net-(IC1C-O)', 'N$6'), ('Net-(IC1D-I1)', 'N$5'), ('Net-(IC2-1D)', 'N$15'), ('Net-(IC2-2D)', 'N$14'), ('Net-(IC2-3D)', 'N$13'), ('Net-(IC2-4D)', 'N$12'), ('Net-(IC2-5D)', 'N$10'), ('Net-(IC2-6D)', 'N$9'), ('Net-(IC2-7D)', 'N$8'), ('Net-(IC2-8D)', 'N$7'), ('Net-(IC2-ENC)', 'N$18'), ('Net-(IC2-OC)', 'N$16'), ('Net-(IC15-~{CER})', 'N$52'), ('Net-(IC17-CS)', 'N$91'), ('Net-(IC17-CURSOR)', 'N$74'), ('Net-(IC17-DE)', 'N$79'), ('Net-(IC17-HS)', 'N$83'), ('Net-(IC17-VS)', 'N$82'), ('Net-(IC18-A0)', 'N$48'), ('Net-(IC18-A1)', 'N$49'), ('Net-(IC18-A2)', 'N$50'), ('Net-(IC18-A3)', 'N$51'), ('Net-(IC18-A=B_I)', 'N$89'), ('Net-(IC19A-I1)', 'N$2'), ('Net-(IC19B-I1)', 'N$87'), ('Net-(IC19C-I0)', 'N$60'), ('Net-(IC19D-I0)', 'N$80'), ('Net-(IC19D-I1)', 'N$81'), ('Net-(IC19D-O)', 'N$84'), ('Net-(IC20A-I)', 'N$54'), ('Net-(IC20A-O)', 'N$56'), ('Net-(IC20B-O)', 'N$55'), ('Net-(IC20C-O)', 'N$57'), ('Net-(IC20D-I)', 'N$58'), ('Net-(IC20D-O)', 'N$59'), ('Net-(IC22-CLR)', 'N$73'), ('Net-(IC22-D1)', 'N$75'), ('Net-(IC22-D2)', 'N$61'), ('Net-(IC22-D4)', 'N$78'), ('Net-(IC22-Q2)', 'N$76'), ('Net-(IC23-Q1)', 'N$67'), ('Net-(IC23-Q2)', 'N$68'), ('Net-(IC23-Q3)', 'N$69'), ('Net-(IC23-Q4)', 'N$70'), ('Net-(IC23-Q5)', 'N$71'), ('Net-(IC23-Q6)', 'N$72'), ('Net-(IC24-D)', 'N$62'), ('Net-(IC24-E)', 'N$63'), ('Net-(IC24-F)', 'N$64'), ('Net-(IC24-G)', 'N$65'), ('Net-(IC24-H)', 'N$66'), ('Net-(IC24-QH)', 'N$77'), ('Net-(IC27A-O)', 'N$86'), ('Net-(IC27B-O)', 'N$85'), ('Net-(IC27F-O)', 'N$3'), ('Net-(PWR0-PadA)', 'N$11')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 19, text crossed by a line 6, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 35, isolated_pin_label 56, pin_not_driven 2, pin_to_pin 8, unconnected_wire_endpoint 21.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 3, silk_edge_clearance 8, silk_over_copper 199, silk_overlap 15, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 192 symbols, 549 wires, 189 labels, 90 junctions, 10 bus lines, 30 no-connects
