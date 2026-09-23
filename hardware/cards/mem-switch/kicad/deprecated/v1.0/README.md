# mem-switch-v1.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `Mem Switch V1.0` in `hardware/cards/mem-switch/eagle/deprecated/v1.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `mem-switch-v1.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `mem-switch-v1.0.kicad_sch` | root sheet; 3 sub-sheet(s) `mem-switch-v1.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `mem-switch-v1.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `mem-switch-v1.0.kicad_pcb` | the board: 2 copper layers, 71 footprints, 2166 track segments, 96 vias |
| `mem-switch-v1.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (175/175 nets)**

```
  same connectivity, different net name: [('Net-(IC1A-A1)', 'N$9'), ('Net-(IC1A-A2)', 'N$8'), ('Net-(IC1A-A3)', 'N$7'), ('Net-(IC1A-A4)', 'N$5'), ('Net-(IC1B-A1)', 'N$4'), ('Net-(IC1B-A2)', 'N$3'), ('Net-(IC1B-A3)', 'N$2'), ('Net-(IC1B-A4)', 'N$1'), ('Net-(IC2A-A1)', 'N$18'), ('Net-(IC2A-A2)', 'N$17'), ('Net-(IC2A-A3)', 'N$16'), ('Net-(IC2A-A4)', 'N$15'), ('Net-(IC2B-A1)', 'N$14'), ('Net-(IC2B-A2)', 'N$13'), ('Net-(IC2B-A3)', 'N$12'), ('Net-(IC2B-A4)', 'N$10'), ('Net-(IC3A-A1)', 'N$27'), ('Net-(IC3A-A2)', 'N$26'), ('Net-(IC3A-A3)', 'N$25'), ('Net-(IC3A-A4)', 'N$24'), ('Net-(IC3B-A1)', 'N$23'), ('Net-(IC3B-A2)', 'N$22'), ('Net-(IC3B-A3)', 'N$21'), ('Net-(IC3B-A4)', 'N$20'), ('Net-(IC4A-A1)', 'N$36'), ('Net-(IC4A-A2)', 'N$35'), ('Net-(IC4A-A3)', 'N$34'), ('Net-(IC4A-A4)', 'N$33'), ('Net-(IC4B-A1)', 'N$32'), ('Net-(IC4B-A2)', 'N$31'), ('Net-(IC4B-A3)', 'N$30'), ('Net-(IC4B-A4)', 'N$29'), ('Net-(IC5A-A1)', 'N$45'), ('Net-(IC5A-A2)', 'N$44'), ('Net-(IC5A-A3)', 'N$43'), ('Net-(IC5A-A4)', 'N$42'), ('Net-(IC5B-A1)', 'N$41'), ('Net-(IC5B-A2)', 'N$40'), ('Net-(IC5B-A3)', 'N$39'), ('Net-(IC5B-A4)', 'N$38'), ('Net-(IC6A-A1)', 'N$54'), ('Net-(IC6A-A2)', 'N$53'), ('Net-(IC6A-A3)', 'N$52'), ('Net-(IC6A-A4)', 'N$51'), ('Net-(IC6B-A1)', 'N$50'), ('Net-(IC6B-A2)', 'N$49'), ('Net-(IC6B-A3)', 'N$48'), ('Net-(IC6B-A4)', 'N$47'), ('Net-(IC7A-A1)', 'N$63'), ('Net-(IC7A-A2)', 'N$62'), ('Net-(IC7A-A3)', 'N$61'), ('Net-(IC7A-A4)', 'N$60'), ('Net-(IC7B-A1)', 'N$59'), ('Net-(IC7B-A2)', 'N$58'), ('Net-(IC7B-A3)', 'N$57'), ('Net-(IC7B-A4)', 'N$56'), ('Net-(IC8A-A1)', 'N$72'), ('Net-(IC8A-A2)', 'N$71'), ('Net-(IC8A-A3)', 'N$70'), ('Net-(IC8A-A4)', 'N$69'), ('Net-(IC8B-A1)', 'N$68'), ('Net-(IC8B-A2)', 'N$67'), ('Net-(IC8B-A3)', 'N$66'), ('Net-(IC8B-A4)', 'N$65'), ('Net-(IC9A-A1)', 'N$81'), ('Net-(IC9A-A2)', 'N$80'), ('Net-(IC9A-A3)', 'N$79'), ('Net-(IC9A-A4)', 'N$78'), ('Net-(IC9B-A1)', 'N$77'), ('Net-(IC9B-A2)', 'N$76'), ('Net-(IC9B-A3)', 'N$75'), ('Net-(IC9B-A4)', 'N$74'), ('Net-(IC10A-A1)', 'N$90'), ('Net-(IC10A-A2)', 'N$89'), ('Net-(IC10A-A3)', 'N$88'), ('Net-(IC10A-A4)', 'N$87'), ('Net-(IC10B-A1)', 'N$86'), ('Net-(IC10B-A2)', 'N$85'), ('Net-(IC10B-A3)', 'N$84'), ('Net-(IC10B-A4)', 'N$83'), ('Net-(IC11A-A1)', 'N$99'), ('Net-(IC11A-A2)', 'N$98'), ('Net-(IC11A-A3)', 'N$97'), ('Net-(IC11A-A4)', 'N$96'), ('Net-(IC11B-A1)', 'N$95'), ('Net-(IC11B-A2)', 'N$94'), ('Net-(IC11B-A3)', 'N$93'), ('Net-(IC11B-A4)', 'N$92'), ('Net-(IC12A-A1)', 'N$108'), ('Net-(IC12A-A2)', 'N$107'), ('Net-(IC12A-A3)', 'N$106'), ('Net-(IC12A-A4)', 'N$105'), ('Net-(IC12B-A1)', 'N$104'), ('Net-(IC12B-A2)', 'N$103'), ('Net-(IC12B-A3)', 'N$102'), ('Net-(IC12B-A4)', 'N$101'), ('Net-(IC13A-A1)', 'N$117'), ('Net-(IC13A-A2)', 'N$116'), ('Net-(IC13A-A3)', 'N$115'), ('Net-(IC13A-A4)', 'N$114'), ('Net-(IC13B-A1)', 'N$113'), ('Net-(IC13B-A2)', 'N$112'), ('Net-(IC13B-A3)', 'N$111'), ('Net-(IC13B-A4)', 'N$110'), ('Net-(IC14A-A1)', 'N$126'), ('Net-(IC14A-A2)', 'N$125'), ('Net-(IC14A-A3)', 'N$124'), ('Net-(IC14A-A4)', 'N$123'), ('Net-(IC14B-A1)', 'N$122'), ('Net-(IC14B-A2)', 'N$121'), ('Net-(IC14B-A3)', 'N$120'), ('Net-(IC14B-A4)', 'N$119'), ('Net-(IC15A-A1)', 'N$135'), ('Net-(IC15A-A2)', 'N$134'), ('Net-(IC15A-A3)', 'N$133'), ('Net-(IC15A-A4)', 'N$132'), ('Net-(IC15B-A1)', 'N$131'), ('Net-(IC15B-A2)', 'N$130'), ('Net-(IC15B-A3)', 'N$129'), ('Net-(IC15B-A4)', 'N$128'), ('Net-(IC16A-A1)', 'N$144'), ('Net-(IC16A-A2)', 'N$143'), ('Net-(IC16A-A3)', 'N$142'), ('Net-(IC16A-A4)', 'N$141'), ('Net-(IC16B-A1)', 'N$140'), ('Net-(IC16B-A2)', 'N$139'), ('Net-(IC16B-A3)', 'N$138'), ('Net-(IC16B-A4)', 'N$137'), ('Net-(IC17-G1)', 'N$37'), ('Net-(IC17-G2B)', 'N$19'), ('Net-(IC18-G2B)', 'N$28'), ('Net-(PWR0-PadA)', 'N$11')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 0, text over a symbol body 16, text crossed by a line 4, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: endpoint_off_grid 35, isolated_pin_label 59, unconnected_wire_endpoint 4.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: items_not_allowed 2, lib_footprint_mismatch 1, silk_edge_clearance 4, silk_over_copper 199, silk_overlap 1, text_height 2; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 222 symbols, 1185 wires, 262 labels, 286 junctions, 1 bus lines, 7 no-connects
