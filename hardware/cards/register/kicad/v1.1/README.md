# register-v1.1 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Index Registers - 1.1` in `hardware/cards/register/eagle/v1.1/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `register-v1.1.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `register-v1.1.kicad_sch` | root sheet; 8 sub-sheet(s) `register-v1.1-sheetN.kicad_sch` mirror the Eagle sheets |
| `register-v1.1-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `register-v1.1.kicad_pcb` | the board: 4 copper layers, 102 footprints, 3591 track segments, 544 vias |
| `register-v1.1-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (223/223 nets)**

```
  same connectivity, different net name: [('/Sheet 6/-ADDRSEL', '-ADDRSEL'), ('/Sheet 6/-ARD0', '-ARD0'), ('/Sheet 6/-RLD0', '-RLD0'), ('/Sheet 6/-RRD0', '-RRD0'), ('/Sheet 7/BUS-DIR', 'BUS-DIR'), ('Net-(IC1A-O)', 'N$17'), ('Net-(IC1B-O)', 'N$18'), ('Net-(IC1C-O)', 'N$16'), ('Net-(IC1D-O)', 'N$22'), ('Net-(IC2A-O)', 'N$20'), ('Net-(IC2B-O)', 'N$21'), ('Net-(IC3-BO)', 'N$10'), ('Net-(IC3-CO)', 'N$11'), ('Net-(IC3-QA)', 'N$115'), ('Net-(IC3-QB)', 'N$116'), ('Net-(IC3-QC)', 'N$117'), ('Net-(IC3-QD)', 'N$118'), ('Net-(IC4-BO)', 'N$12'), ('Net-(IC4-CO)', 'N$13'), ('Net-(IC4-QA)', 'N$119'), ('Net-(IC4-QB)', 'N$120'), ('Net-(IC4-QC)', 'N$121'), ('Net-(IC4-QD)', 'N$122'), ('Net-(IC5-BO)', 'N$14'), ('Net-(IC5-CO)', 'N$15'), ('Net-(IC10-BO)', 'N$4'), ('Net-(IC10-CO)', 'N$5'), ('Net-(IC10-DN)', 'N$2'), ('Net-(IC10-LD)', 'N$8'), ('Net-(IC10-QA)', 'N$32'), ('Net-(IC10-QB)', 'N$33'), ('Net-(IC10-QC)', 'N$34'), ('Net-(IC10-QD)', 'N$35'), ('Net-(IC10-UP)', 'N$3'), ('Net-(IC11-BO)', 'N$6'), ('Net-(IC11-CO)', 'N$7'), ('Net-(IC11-LD)', 'N$27'), ('Net-(IC11-QA)', 'N$36'), ('Net-(IC11-QB)', 'N$38'), ('Net-(IC11-QC)', 'N$39'), ('Net-(IC11-QD)', 'N$40'), ('Net-(IC12-QA)', 'N$54'), ('Net-(IC12-QB)', 'N$55'), ('Net-(IC12-QC)', 'N$56'), ('Net-(IC12-QD)', 'N$57'), ('Net-(IC13A-G)', 'N$25'), ('Net-(IC13B-A1)', 'N$28'), ('Net-(IC13B-A2)', 'N$29'), ('Net-(IC13B-A3)', 'N$30'), ('Net-(IC13B-A4)', 'N$31'), ('Net-(IC14A-G)', 'N$26'), ('Net-(IC15A-O)', 'N$9'), ('Net-(IC15B-O)', 'N$23'), ('Net-(IC19-BO)', 'N$58'), ('Net-(IC19-CO)', 'N$59'), ('Net-(IC19-DN)', 'N$66'), ('Net-(IC19-LD)', 'N$64'), ('Net-(IC19-QA)', 'N$70'), ('Net-(IC19-QB)', 'N$71'), ('Net-(IC19-QC)', 'N$72'), ('Net-(IC19-QD)', 'N$73'), ('Net-(IC19-UP)', 'N$65'), ('Net-(IC20-BO)', 'N$60'), ('Net-(IC20-CO)', 'N$61'), ('Net-(IC20-QA)', 'N$74'), ('Net-(IC20-QB)', 'N$75'), ('Net-(IC20-QC)', 'N$76'), ('Net-(IC20-QD)', 'N$77'), ('Net-(IC21-BO)', 'N$62'), ('Net-(IC21-CO)', 'N$63'), ('Net-(IC21-LD)', 'N$69'), ('Net-(IC21-QA)', 'N$78'), ('Net-(IC21-QB)', 'N$79'), ('Net-(IC21-QC)', 'N$80'), ('Net-(IC21-QD)', 'N$81'), ('Net-(IC22-QA)', 'N$82'), ('Net-(IC22-QB)', 'N$83'), ('Net-(IC22-QC)', 'N$84'), ('Net-(IC22-QD)', 'N$85'), ('Net-(IC23A-G)', 'N$67'), ('Net-(IC24A-G)', 'N$68'), ('Net-(IC26C-O)', 'N$95'), ('Net-(IC26D-O)', 'N$96'), ('Net-(IC29-BO)', 'N$86'), ('Net-(IC29-CO)', 'N$87'), ('Net-(IC29-DN)', 'N$94'), ('Net-(IC29-LD)', 'N$92'), ('Net-(IC29-QA)', 'N$98'), ('Net-(IC29-QB)', 'N$99'), ('Net-(IC29-QC)', 'N$100'), ('Net-(IC29-QD)', 'N$101'), ('Net-(IC29-UP)', 'N$93'), ('Net-(IC30-BO)', 'N$88'), ('Net-(IC30-CO)', 'N$89'), ('Net-(IC30-QA)', 'N$102'), ('Net-(IC30-QB)', 'N$103'), ('Net-(IC30-QC)', 'N$104'), ('Net-(IC30-QD)', 'N$105'), ('Net-(IC31A-O)', 'N$19'), ('Net-(IC31B-O)', 'N$24'), ('Net-(IC31C-I0)', 'N$41'), ('Net-(IC31C-I1)', 'N$42'), ('Net-(IC31C-O)', 'N$1'), ('Net-(IC31D-O)', 'N$37'), ('Net-(IC32A-Y1)', 'N$43'), ('Net-(IC32A-Y2)', 'N$46'), ('Net-(IC32A-Y3)', 'N$47'), ('Net-(IC32B-Y1)', 'N$48'), ('Net-(IC32B-Y2)', 'N$49'), ('Net-(IC32B-Y3)', 'N$50'), ('Net-(IC38B-G)', 'N$45'), ('Net-(IC38B-Y1)', 'N$51'), ('Net-(IC38B-Y2)', 'N$52'), ('Net-(IC38B-Y3)', 'N$53'), ('Net-(IC42A-A1)', 'N$123'), ('Net-(IC42A-A2)', 'N$124'), ('Net-(IC42A-A3)', 'N$125'), ('Net-(IC42A-A4)', 'N$126'), ('Net-(IC42B-A1)', 'N$127'), ('Net-(IC42B-A2)', 'N$128'), ('Net-(IC42B-A3)', 'N$129'), ('Net-(IC42B-A4)', 'N$130'), ('Net-(IC43-BO)', 'N$90'), ('Net-(IC43-CO)', 'N$91'), ('Net-(IC43-LD)', 'N$97'), ('Net-(IC43-QA)', 'N$106'), ('Net-(IC43-QB)', 'N$107'), ('Net-(IC43-QC)', 'N$108'), ('Net-(IC43-QD)', 'N$109'), ('Net-(IC44-QA)', 'N$110'), ('Net-(IC44-QB)', 'N$111'), ('Net-(IC44-QC)', 'N$112'), ('Net-(IC44-QD)', 'N$113'), ('Net-(PWR0-PadA)', 'N$44')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 18, text crossed by a line 28, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 89, isolated_pin_label 28, unconnected_wire_endpoint 52.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: clearance 30, items_not_allowed 2, lib_footprint_mismatch 1, shorting_items 2, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 1, text_height 2, track_width 199; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 276 symbols, 1273 wires, 445 labels, 239 junctions, 21 bus lines, 11 no-connects
