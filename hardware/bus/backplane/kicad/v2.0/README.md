# backplane-v2.0 — KiCad conversion

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py` from the Eagle design `yacc2buss` in `hardware/bus/backplane/eagle/v2.0/`. **The Eagle files are the record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). This revision was FABRICATED (see `hardware/FABRICATED.md`).

## Files

| File | What it is |
|---|---|
| `backplane-v2.0.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `backplane-v2.0.kicad_sch` | root sheet; 1 sub-sheet(s) `backplane-v2.0-sheetN.kicad_sch` mirror the Eagle sheets |
| `backplane-v2.0-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |
| `backplane-v2.0.kicad_pcb` | the board: 4 copper layers, 29 footprints, 8523 track segments, 1388 vias |
| `backplane-v2.0-eagle.pretty/` | project footprint library extracted from the imported board |
| `reports/` | ERC (`erc.json`), DRC (`drc.json`), schematic PDF, board renders (`-top.png`, `-bottom.png`), netlist + `netlist-compare.txt` |

## Proof

Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **MATCH (87/87 nets)**

```
  same connectivity, different net name: [('/Sheet 1/SIG0', 'SIG0'), ('/Sheet 1/SIG1', 'SIG1'), ('/Sheet 1/SIG2', 'SIG2'), ('/Sheet 1/SIG3', 'SIG3'), ('/Sheet 1/SIG4', 'SIG4'), ('/Sheet 1/SIG5', 'SIG5'), ('/Sheet 1/SIG6', 'SIG6'), ('/Sheet 1/SIG7', 'SIG7'), ('/Sheet 1/SIG8', 'SIG8'), ('/Sheet 1/SIG9', 'SIG9'), ('/Sheet 1/SIG10', 'SIG10'), ('/Sheet 1/SIG11', 'SIG11'), ('/Sheet 1/SIG12', 'SIG12'), ('/Sheet 1/SIG13', 'SIG13'), ('/Sheet 1/SIG14', 'SIG14'), ('/Sheet 1/SIG15', 'SIG15'), ('/Sheet 1/SIG16', 'SIG16'), ('/Sheet 1/SIG17', 'SIG17'), ('/Sheet 1/SIG18', 'SIG18'), ('/Sheet 1/SIG19', 'SIG19'), ('/Sheet 1/SIG20', 'SIG20'), ('/Sheet 1/SIG21', 'SIG21'), ('/Sheet 1/SIG22', 'SIG22'), ('/Sheet 1/SIG23', 'SIG23'), ('/Sheet 1/SIG24', 'SIG24'), ('/Sheet 1/SIG25', 'SIG25'), ('/Sheet 1/SIG26', 'SIG26'), ('/Sheet 1/SIG27', 'SIG27'), ('/Sheet 1/SIG28', 'SIG28'), ('/Sheet 1/SIG29', 'SIG29'), ('/Sheet 1/SIG30', 'SIG30'), ('/Sheet 1/SIG31', 'SIG31'), ('/Sheet 1/SIG32', 'SIG32'), ('/Sheet 1/SIG33', 'SIG33'), ('/Sheet 1/SIG34', 'SIG34'), ('/Sheet 1/SIG35', 'SIG35'), ('/Sheet 1/SIG36', 'SIG36'), ('/Sheet 1/SIG37', 'SIG37'), ('/Sheet 1/SIG38', 'SIG38'), ('/Sheet 1/SIG39', 'SIG39'), ('/Sheet 1/SIG40', 'SIG40'), ('/Sheet 1/SIG41', 'SIG41'), ('/Sheet 1/SIG42', 'SIG42'), ('/Sheet 1/SIG43', 'SIG43'), ('/Sheet 1/SIG44', 'SIG44'), ('/Sheet 1/SIG45', 'SIG45'), ('/Sheet 1/SIG46', 'SIG46'), ('/Sheet 1/SIG47', 'SIG47'), ('/Sheet 1/SIG48', 'SIG48'), ('/Sheet 1/SIG49', 'SIG49'), ('/Sheet 1/SIG50', 'SIG50'), ('/Sheet 1/SIG51', 'SIG51'), ('/Sheet 1/SIG52', 'SIG52'), ('/Sheet 1/SIG53', 'SIG53'), ('/Sheet 1/SIG54', 'SIG54'), ('/Sheet 1/SIG55', 'SIG55'), ('/Sheet 1/SIG56', 'SIG56'), ('/Sheet 1/SIG57', 'SIG57'), ('/Sheet 1/SIG58', 'SIG58'), ('/Sheet 1/SIG59', 'SIG59'), ('/Sheet 1/SIG60', 'SIG60'), ('/Sheet 1/SIG61', 'SIG61'), ('/Sheet 1/SIG62', 'SIG62'), ('/Sheet 1/SIG63', 'SIG63'), ('/Sheet 1/SIG64', 'SIG64'), ('/Sheet 1/SIG65', 'SIG65'), ('/Sheet 1/SIG66', 'SIG66'), ('/Sheet 1/SIG67', 'SIG67'), ('/Sheet 1/SIG68', 'SIG68'), ('/Sheet 1/SIG69', 'SIG69'), ('/Sheet 1/SIG70', 'SIG70'), ('/Sheet 1/SIG71', 'SIG71'), ('/Sheet 1/SIG72', 'SIG72'), ('/Sheet 1/SIG73', 'SIG73'), ('/Sheet 1/SIG74', 'SIG74'), ('/Sheet 1/SIG75', 'SIG75'), ('/Sheet 1/SIG76', 'SIG76'), ('/Sheet 1/SIG77', 'SIG77'), ('/Sheet 1/SIG78', 'SIG78'), ('/Sheet 1/SIG79', 'SIG79'), ('/Sheet 1/SIG80', 'SIG80'), ('/Sheet 1/SIG81', 'SIG81'), ('/Sheet 1/SIG82', 'SIG82'), ('/Sheet 1/SIG83', 'SIG83'), ('Net-(PWR0-PadA)', 'N$2')]
```

## Readability

`tools/kicad/sch_overlaps.py` over every sheet: text over text 7, text over a symbol body 559, text crossed by a line 9, items off the drawing frame or on the title block 0. What is left is mostly the Eagle drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins.

## Residual ERC / DRC

ERC by type: none.
`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. `unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.

DRC by type: clearance 3, items_not_allowed 16, lib_footprint_mismatch 8, shorting_items 16, silk_over_copper 4, silk_overlap 76; unconnected items 0; schematic parity 0.
Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).

Converter: converted: 56 symbols, 891 wires, 672 labels, 135 junctions, 8 bus lines, 0 no-connects
