# KiCad conversions

Generated 2026-09-23 by `tools/eagle_to_kicad_all.py`: every Eagle design under `hardware/` (active and deprecated revisions) converted to a KiCad 10 project in the matching `kicad/<rev>/` folder. The Eagle files remain the record of what was built; these projects are derived and regenerated from scratch by the tool. **Proof** = the schematic netlist extracted by KiCad compared pad-for-pad with the netlist embedded in the imported Eagle board (`tools/kicad/compare_netlists.py`). Each project's README has the details and the residual ERC/DRC counts.

**Overlaps** = `tools/kicad/sch_overlaps.py` over all sheets: text/text + text/body + text/line collisions, and items off the drawing frame.

| Eagle design | KiCad project | Built | Proof | ERC | DRC | Overlaps | Off frame | Status |
|---|---|---|---|---|---|---|---|---|
| `bus/backplane/eagle/deprecated/v1.1/yacc2buss` | [`backplane-v1.1`](bus/backplane/kicad/deprecated/v1.1/) | yes | MATCH (87/87 nets) | - | 22 + 0 unconnected | 500 | 0 | ok |
| `bus/backplane/eagle/v2.0/yacc2buss` | [`backplane-v2.0`](bus/backplane/kicad/v2.0/) | yes | MATCH (87/87 nets) | - | 123 + 0 unconnected | 575 | 0 | ok |
| `bus/blank-card/eagle/v3.1/Blank V3.1` | [`blank-card-v3.1`](bus/blank-card/kicad/v3.1/) | yes | MATCH (3/3 nets) | 84 | 9 + 0 unconnected | 0 | 0 | ok |
| `bus/blank-card/eagle/v3.2/Blank V3.2` | [`blank-card-v3.2`](bus/blank-card/kicad/v3.2/) | no | MATCH (3/3 nets) | 84 | 9 + 0 unconnected | 0 | 0 | ok |
| `bus/bus-jumper-horizontal/eagle/deprecated/v3.0/Jumper Board V3.0` | [`bus-jumper-horizontal-v3.0`](bus/bus-jumper-horizontal/kicad/deprecated/v3.0/) | yes | MATCH (89/89 nets) | - | 28 + 0 unconnected | 0 | 0 | ok |
| `bus/bus-jumper-horizontal/eagle/v3.2/Jumper Board Horizontal V3.1` | [`bus-jumper-horizontal-v3.2`](bus/bus-jumper-horizontal/kicad/v3.2/) | yes | MATCH (89/89 nets) | - | 29 + 1 unconnected | 0 | 0 | ok |
| `bus/bus-jumper-vertical/eagle/v3.0/Jumper Board V3.0` | [`bus-jumper-vertical-v3.0`](bus/bus-jumper-vertical/kicad/v3.0/) | yes | MATCH (89/89 nets) | - | 10 + 0 unconnected | 0 | 0 | ok |
| `bus/bus-template/eagle/v3.2/Bus Template V3.2` | [`bus-template-v3.2`](bus/bus-template/kicad/v3.2/) | no | n/a (schematic only) | 182 | - | 0 | 0 | ok |
| `cards/address-tmp/eagle/deprecated/v1.0/Address and TMP V1.0` | [`address-tmp-v1.0`](cards/address-tmp/kicad/deprecated/v1.0/) | yes | MATCH (47/47 nets) | 74 | 208 + 0 unconnected | 36 | 0 | ok |
| `cards/alu/eagle/deprecated/v3.0-2layer/alu4` | [`alu-v3.0-2layer`](cards/alu/kicad/deprecated/v3.0-2layer/) | yes | MATCH (158/158 nets) | 203 | 407 + 0 unconnected | 87 | 0 | ok |
| `cards/alu/eagle/deprecated/v3.1/ALU V3.1` | [`alu-v3.1`](cards/alu/kicad/deprecated/v3.1/) | yes | MATCH (159/159 nets) | 203 | 697 + 0 unconnected | 90 | 0 | ok |
| `cards/alu/eagle/deprecated/v3.1-buried-vias/ALU V3.1` | [`alu-v3.1-buried-vias`](cards/alu/kicad/deprecated/v3.1-buried-vias/) | yes | MATCH (159/159 nets) | 203 | 697 + 0 unconnected | 90 | 0 | ok |
| `cards/alu/eagle/deprecated/v3.1-resubmit/ALU V3.1` | [`alu-v3.1-resubmit`](cards/alu/kicad/deprecated/v3.1-resubmit/) | yes | MATCH (159/159 nets) | 203 | 608 + 0 unconnected | 90 | 0 | ok |
| `cards/alu/eagle/v3.2/ALU V3.2` | [`alu-v3.2`](cards/alu/kicad/v3.2/) | yes | MATCH (162/162 nets) | 206 | 606 + 0 unconnected | 84 | 0 | ok |
| `cards/bus-tester/eagle/v1.1/tester` | [`bus-tester-v1.1`](cards/bus-tester/kicad/v1.1/) | yes | MATCH (149/149 nets) | 32 | 250 + 0 unconnected | 78 | 0 | ok |
| `cards/bus-tester/eagle/v3.1/tester` | [`bus-tester-v3.1`](cards/bus-tester/kicad/v3.1/) | no | MATCH (239/239 nets) | 123 | 494 + 0 unconnected | 96 | 0 | ok |
| `cards/io/eagle/deprecated/v1.0/IO V1.0` | [`io-v1.0`](cards/io/kicad/deprecated/v1.0/) | yes | MATCH (101/101 nets) | 130 | 359 + 0 unconnected | 94 | 0 | ok |
| `cards/io/eagle/v1.1/IO V1.1` | [`io-v1.1`](cards/io/kicad/v1.1/) | yes | MATCH (104/104 nets) | 130 | 292 + 0 unconnected | 92 | 0 | ok |
| `cards/mem-register/eagle/v1.0/Mem Register V1.0` | [`mem-register-v1.0`](cards/mem-register/kicad/v1.0/) | yes | MATCH (107/107 nets) | 179 | 299 + 0 unconnected | 171 | 0 | ok |
| `cards/mem-switch/eagle/deprecated/v1.0/Mem Switch V1.0` | [`mem-switch-v1.0`](cards/mem-switch/kicad/deprecated/v1.0/) | yes | MATCH (175/175 nets) | 98 | 209 + 0 unconnected | 20 | 0 | ok |
| `cards/mem-switch/eagle/v1.1/Mem Switch V1.1` | [`mem-switch-v1.1`](cards/mem-switch/kicad/v1.1/) | yes | MATCH (199/199 nets) | 99 | 279 + 0 unconnected | 72 | 0 | ok |
| `cards/memory/eagle/deprecated/v1.0/Memory V1.0` | [`memory-v1.0`](cards/memory/kicad/deprecated/v1.0/) | yes | MATCH (69/69 nets) | 102 | 208 + 0 unconnected | 38 | 0 | ok |
| `cards/memory/eagle/deprecated/v1.1/Memory V1.0` | [`memory-v1.1`](cards/memory/kicad/deprecated/v1.1/) | yes | MATCH (75/75 nets) | 102 | 208 + 0 unconnected | 38 | 0 | ok |
| `cards/memory/eagle/deprecated/v1.2/Memory V1.2` | [`memory-v1.2`](cards/memory/kicad/deprecated/v1.2/) | yes | MATCH (99/99 nets) | 111 | 208 + 0 unconnected | 93 | 0 | ok |
| `cards/memory/eagle/deprecated/v1.3-do-not-use/Memory V1.3` | [`memory-v1.3-do-not-use`](cards/memory/kicad/deprecated/v1.3-do-not-use/) | no | MATCH (115/115 nets) | 103 | 250 + 100 unconnected | 95 | 0 | ok |
| `cards/memory/eagle/v1.3/Memory V1.3` | [`memory-v1.3`](cards/memory/kicad/v1.3/) | yes | MATCH (116/116 nets) | 104 | 254 + 0 unconnected | 98 | 0 | ok |
| `cards/protocard/eagle/v1.0/ProtoCard-Prod-V1.0` | [`protocard-v1.0`](cards/protocard/kicad/v1.0/) | yes | MATCH (87/87 nets) | - | 268 + 0 unconnected | 21 | 0 | ok |
| `cards/register/eagle/deprecated/v1.0/Index Registers - 1.0` | [`register-v1.0`](cards/register/kicad/deprecated/v1.0/) | yes | MATCH (192/192 nets) | 163 | 212 + 0 unconnected | 110 | 0 | ok |
| `cards/register/eagle/deprecated/v1.0-no-address/Index Registers - 1.0` | [`register-v1.0-no-address`](cards/register/kicad/deprecated/v1.0-no-address/) | yes | MATCH (192/192 nets) | 163 | 212 + 0 unconnected | 110 | 0 | ok |
| `cards/register/eagle/v1.1/Index Registers - 1.1` | [`register-v1.1`](cards/register/kicad/v1.1/) | yes | MATCH (223/223 nets) | 169 | 440 + 0 unconnected | 46 | 0 | ok |
| `cards/sequencer-logic/eagle/deprecated/v2.0/Sequencer-Logic-Prod-V2.0` | [`sequencer-logic-v2.0`](cards/sequencer-logic/kicad/deprecated/v2.0/) | yes | MATCH (274/274 nets) | 128 | 720 + 0 unconnected | 78 | 0 | ok |
| `cards/sequencer-logic/eagle/v2.1/Sequencer-Logic-Prod-V2.1l` | [`sequencer-logic-v2.1`](cards/sequencer-logic/kicad/v2.1/) | yes | MATCH (282/282 nets) | 121 | 712 + 0 unconnected | 86 | 0 | ok |
| `cards/sequencer-logic/eagle/v2.1/orig size/Sequencer-Logic-Prod-V2.1` | [`sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1`](cards/sequencer-logic/kicad/v2.1/orig-size/sequencer-logic-prod-v2.1/) | no | MATCH (282/282 nets) | 121 | 772 + 4 unconnected | 86 | 0 | ok |
| `cards/sequencer-logic/eagle/v2.1/orig size/Sequencer-Logic-Prod-V2.1 copy` | [`sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1-copy`](cards/sequencer-logic/kicad/v2.1/orig-size/sequencer-logic-prod-v2.1-copy/) | no | n/a (schematic only) | 358 | - | 88 | 0 | ok |
| `cards/sequencer-memory/accessories/eeprom-adaptor/eeprom adaptor` | [`sequencer-memory-eeprom-adaptor`](cards/sequencer-memory/accessories/eeprom-adaptor/kicad/) | yes | MATCH (5/5 nets) | 3 | 16 + 0 unconnected | 0 | 0 | ok |
| `cards/sequencer-memory/eagle/deprecated/v2.0/Sequencer-Memory-V2.0` | [`sequencer-memory-v2.0`](cards/sequencer-memory/kicad/deprecated/v2.0/) | yes | MATCH (105/105 nets) | 13 | 497 + 0 unconnected | 30 | 0 | ok |
| `cards/sequencer-memory/eagle/v2.1/Sequencer-Memory-V2.1` | [`sequencer-memory-v2.1`](cards/sequencer-memory/kicad/v2.1/) | yes | MATCH (106/106 nets) | 11 | 461 + 0 unconnected | 28 | 0 | ok |
| `cards/video/eagle/v1.0-fusion-export-2026-09-18/Video_1.0` | [`video-v1.0-fusion-export-2026-09-18`](cards/video/kicad/v1.0-fusion-export-2026-09-18/) | yes | MISMATCH (115/117 nets) | 122 | 229 + 0 unconnected | 25 | 0 | ok |

**Label styles in the converted schematics** (Ken looked, 2026-09-23, and kept them): a boxed global label marks a net the card also uses on another sheet (only global labels connect across KiCad sheets); plain text on a wire marks a net that appears on that sheet only, e.g. a bus signal the card does not use, drawn from the connector pin to the bus. Eagle drew both the same way, since its labels connect across sheets by name.

## Hand-maintained masters (not generated; `MASTER` marker file)

- [`cards/cf/kicad/v1.0`](cards/cf/kicad/v1.0/) — see its README (not ordered; its circuit is the CF section of `cards/memory/kicad/v2.0`)
- [`cards/memory/kicad/v2.0`](cards/memory/kicad/v2.0/) — see its README (the built memory v1.3 + the CF interface on P8/P9; schematic proven; whole card RE-LAID (Ken 2026-09-24), option B picked: `memory-v2.0.kicad_pcb` routed (0 unrouted, 43 vias, DRC 0 copper violations), fab files ready (gerbers + drill zip, renders, placement PDF, BOM); C20-C23 (four spare 100 nF with no IC) removed (Ken 2026-09-24): 70 parts, proof = v1.3 - C20-C23 + CF; not ordered)
- [`cards/video/kicad/v1.1`](cards/video/kicad/v1.1/) — see its README
