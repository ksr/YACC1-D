# register-v1.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Index Registers - 1.0` in `hardware/cards/register/eagle/deprecated/v1.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `register-v1.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `register-v1.0.kicad_sch` | root sheet; 9 sub-sheet(s) `register-v1.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `register-v1.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `register-v1.0.kicad_pcb` | the board: 2 copper layers, 83 footprints, 2913 track segments, 296 vias |
| `register-v1.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (192/192 nets)**

```
  same connectivity, different net name: [('/Sheet 4/IC-12', 'IC-12'), ('/Sheet 7/-RLD0', '-RLD0'), ('/Sheet 7/-RRD0', '-RRD0'), ('/Sheet 8/BUS-DIR', 'BUS-DIR'), ('Net-(IC1A-O)', 'N$17'), ('Net-(IC1B-O)', 'N$18'), ('Net-(IC1C-O)', 'N$16'), ('Net-(IC1D-O)', 'N$22'), ('Net-(IC2A-O)', 'N$20'), ('Net-(IC2B-O)', 'N$21'), ('Net-(IC3-BO)', 'N$10'), ('Net-(IC3-CO)', 'N$11'), ('Net-(IC3-QA)', 'N$115'), ('Net-(IC3-QB)', 'N$116'), ('Net-(IC3-QC)', 'N$117'), ('Net-(IC3-QD)', 'N$118'), ('Net-(IC4-BO)', 'N$12'), ('Net-(IC4-CO)', 'N$13'), ('Net-(IC4-QA)', 'N$119'), ('Net-(IC4-QB)', 'N$120'), ('Net-(IC4-QC)', 'N$121'), ('Net-(IC4-QD)', 'N$122'), ('Net-(IC5-BO)', 'N$14'), ('Net-(IC5-CO)', 'N$15'), ('Net-(IC5-QA)', 'N$123'), ('Net-(IC5-QB)', 'N$124'), ('Net-(IC5-QC)', 'N$125'), ('Net-(IC5-QD)', 'N$126'), ('Net-(IC6-QA)', 'N$127'), ('Net-(IC6-QB)', 'N$128'), ('Net-(IC6-QC)', 'N$129'), ('Net-(IC6-QD)', 'N$130'), ('Net-(IC10A-O)', 'N$38'), ('Net-(IC10B-O)', 'N$39'), ('Net-(IC10C-O)', 'N$25'), ('Net-(IC10D-O)', 'N$26'), ('Net-(IC11-BO)', 'N$28'), ('Net-(IC11-CO)', 'N$29'), ('Net-(IC11-DN)', 'N$36'), ('Net-(IC11-LD)', 'N$34'), ('Net-(IC11-UP)', 'N$35'), ('Net-(IC12-BO)', 'N$30'), ('Net-(IC12-CO)', 'N$31'), ('Net-(IC13-BO)', 'N$32'), ('Net-(IC13-CO)', 'N$33'), ('Net-(IC13-LD)', 'N$40'), ('Net-(IC17A-O)', 'N$65'), ('Net-(IC17B-O)', 'N$66'), ('Net-(IC17C-O)', 'N$64'), ('Net-(IC17D-O)', 'N$86'), ('Net-(IC18-BO)', 'N$58'), ('Net-(IC18-CO)', 'N$59'), ('Net-(IC18-QA)', 'N$80'), ('Net-(IC18-QB)', 'N$81'), ('Net-(IC18-QC)', 'N$82'), ('Net-(IC18-QD)', 'N$83'), ('Net-(IC19-BO)', 'N$60'), ('Net-(IC19-CO)', 'N$61'), ('Net-(IC19-QA)', 'N$87'), ('Net-(IC19-QB)', 'N$88'), ('Net-(IC19-QC)', 'N$89'), ('Net-(IC19-QD)', 'N$90'), ('Net-(IC20-BO)', 'N$62'), ('Net-(IC20-CO)', 'N$63'), ('Net-(IC20-QA)', 'N$91'), ('Net-(IC20-QB)', 'N$92'), ('Net-(IC20-QC)', 'N$93'), ('Net-(IC20-QD)', 'N$94'), ('Net-(IC21-QA)', 'N$95'), ('Net-(IC21-QB)', 'N$96'), ('Net-(IC21-QC)', 'N$97'), ('Net-(IC21-QD)', 'N$98'), ('Net-(IC22A-G)', 'N$84'), ('Net-(IC23A-G)', 'N$85'), ('Net-(IC24A-O)', 'N$9'), ('Net-(IC24B-O)', 'N$23'), ('Net-(IC24C-O)', 'N$8'), ('Net-(IC24D-O)', 'N$27'), ('Net-(IC25-BO)', 'N$2'), ('Net-(IC25-CO)', 'N$3'), ('Net-(IC26-BO)', 'N$4'), ('Net-(IC26-CO)', 'N$5'), ('Net-(IC27-BO)', 'N$6'), ('Net-(IC27-CO)', 'N$7'), ('Net-(IC31A-O)', 'N$19'), ('Net-(IC31B-O)', 'N$24'), ('Net-(IC31C-I0)', 'N$41'), ('Net-(IC31C-I1)', 'N$42'), ('Net-(IC31C-O)', 'N$1'), ('Net-(IC31D-O)', 'N$37'), ('Net-(IC32A-Y1)', 'N$43'), ('Net-(IC32A-Y2)', 'N$46'), ('Net-(IC32A-Y3)', 'N$47'), ('Net-(IC32B-Y1)', 'N$48'), ('Net-(IC32B-Y2)', 'N$49'), ('Net-(IC32B-Y3)', 'N$50'), ('Net-(PWR0-PadA)', 'N$44')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 98, text crossed by a line 12, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 72, isolated_pin_label 82, pin_not_driven 4, unconnected_wire_endpoint 5.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 4, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 243 symbols, 909 wires, 462 labels, 129 junctions, 17 bus lines, 16 no-connects
