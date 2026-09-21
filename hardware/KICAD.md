# KiCad conversions

Generated 2026-09-20 by `tools/eagle_to_kicad_all.py`: every Eagle design under `hardware/` (active and deprecated revisions) converted to a KiCad 10 project in the matching `kicad/<rev>/` folder. The Eagle files remain the record of what was built; these projects are derived and regenerated from scratch by the tool. **Proof** = the schematic netlist extracted by KiCad compared pad-for-pad with the netlist embedded in the imported Eagle board (`tools/kicad/compare_netlists.py`). Each project's README has the details and the residual ERC/DRC counts.

| Eagle design | KiCad project | Built | Proof | ERC | DRC | Status |
|---|---|---|---|---|---|---|
| `bus/backplane/eagle/deprecated/v1.1/yacc2buss` | [`backplane-v1.1`](bus/backplane/kicad/deprecated/v1.1/) | yes | MATCH (87/87 nets) | - | 22 + 0 unconnected | ok |
| `bus/backplane/eagle/v2.0/yacc2buss` | [`backplane-v2.0`](bus/backplane/kicad/v2.0/) | yes | MATCH (87/87 nets) | - | 125 + 0 unconnected | ok |
| `bus/blank-card/eagle/v3.1/Blank V3.1` | [`blank-card-v3.1`](bus/blank-card/kicad/v3.1/) | yes | MATCH (3/3 nets) | 84 | 9 + 0 unconnected | ok |
| `bus/blank-card/eagle/v3.2/Blank V3.2` | [`blank-card-v3.2`](bus/blank-card/kicad/v3.2/) | no | MATCH (3/3 nets) | 84 | 9 + 0 unconnected | ok |
| `bus/bus-jumper-horizontal/eagle/deprecated/v3.0/Jumper Board V3.0` | [`bus-jumper-horizontal-v3.0`](bus/bus-jumper-horizontal/kicad/deprecated/v3.0/) | yes | MATCH (89/89 nets) | - | 28 + 0 unconnected | ok |
| `bus/bus-jumper-horizontal/eagle/v3.2/Jumper Board Horizontal V3.1` | [`bus-jumper-horizontal-v3.2`](bus/bus-jumper-horizontal/kicad/v3.2/) | yes | MATCH (89/89 nets) | - | 29 + 1 unconnected | ok |
| `bus/bus-jumper-vertical/eagle/v3.0/Jumper Board V3.0` | [`bus-jumper-vertical-v3.0`](bus/bus-jumper-vertical/kicad/v3.0/) | yes | MATCH (89/89 nets) | - | 10 + 0 unconnected | ok |
| `bus/bus-template/eagle/v3.2/Bus Template V3.2` | [`bus-template-v3.2`](bus/bus-template/kicad/v3.2/) | no | n/a (schematic only) | 182 | - | ok |
| `cards/address-tmp/eagle/deprecated/v1.0/Address and TMP V1.0` | [`address-tmp-v1.0`](cards/address-tmp/kicad/deprecated/v1.0/) | yes | MATCH (47/47 nets) | 58 | 208 + 0 unconnected | ok |
| `cards/alu/eagle/deprecated/v3.0-2layer/alu4` | [`alu-v3.0-2layer`](cards/alu/kicad/deprecated/v3.0-2layer/) | yes | MATCH (158/158 nets) | 145 | 407 + 0 unconnected | ok |
| `cards/alu/eagle/deprecated/v3.1/ALU V3.1` | [`alu-v3.1`](cards/alu/kicad/deprecated/v3.1/) | yes | MATCH (159/159 nets) | 145 | 697 + 0 unconnected | ok |
| `cards/alu/eagle/deprecated/v3.1-buried-vias/ALU V3.1` | [`alu-v3.1-buried-vias`](cards/alu/kicad/deprecated/v3.1-buried-vias/) | yes | MATCH (159/159 nets) | 145 | 697 + 0 unconnected | ok |
| `cards/alu/eagle/deprecated/v3.1-resubmit/ALU V3.1` | [`alu-v3.1-resubmit`](cards/alu/kicad/deprecated/v3.1-resubmit/) | yes | MATCH (159/159 nets) | 145 | 608 + 0 unconnected | ok |
| `cards/alu/eagle/v3.2/ALU V3.2` | [`alu-v3.2`](cards/alu/kicad/v3.2/) | yes | MATCH (162/162 nets) | 145 | 606 + 0 unconnected | ok |
| `cards/bus-tester/eagle/v1.1/tester` | [`bus-tester-v1.1`](cards/bus-tester/kicad/v1.1/) | yes | MATCH (149/149 nets) | 3 | 250 + 0 unconnected | ok |
| `cards/bus-tester/eagle/v3.1/tester` | [`bus-tester-v3.1`](cards/bus-tester/kicad/v3.1/) | no | MATCH (239/239 nets) | 14 | 507 + 0 unconnected | ok |
| `cards/io/eagle/deprecated/v1.0/IO V1.0` | [`io-v1.0`](cards/io/kicad/deprecated/v1.0/) | yes | MATCH (101/101 nets) | 112 | 359 + 0 unconnected | ok |
| `cards/io/eagle/v1.1/IO V1.1` | [`io-v1.1`](cards/io/kicad/v1.1/) | yes | MATCH (104/104 nets) | 113 | 292 + 0 unconnected | ok |
| `cards/mem-register/eagle/v1.0/Mem Register V1.0` | [`mem-register-v1.0`](cards/mem-register/kicad/v1.0/) | yes | MATCH (107/107 nets) | 83 | 299 + 0 unconnected | ok |
| `cards/mem-switch/eagle/deprecated/v1.0/Mem Switch V1.0` | [`mem-switch-v1.0`](cards/mem-switch/kicad/deprecated/v1.0/) | yes | MATCH (175/175 nets) | 94 | 209 + 0 unconnected | ok |
| `cards/mem-switch/eagle/v1.1/Mem Switch V1.1` | [`mem-switch-v1.1`](cards/mem-switch/kicad/v1.1/) | yes | MATCH (199/199 nets) | 95 | 279 + 0 unconnected | ok |
| `cards/memory/eagle/deprecated/v1.0/Memory V1.0` | [`memory-v1.0`](cards/memory/kicad/deprecated/v1.0/) | yes | MATCH (69/69 nets) | 76 | 208 + 0 unconnected | ok |
| `cards/memory/eagle/deprecated/v1.1/Memory V1.0` | [`memory-v1.1`](cards/memory/kicad/deprecated/v1.1/) | yes | MATCH (75/75 nets) | 78 | 208 + 0 unconnected | ok |
| `cards/memory/eagle/deprecated/v1.2/Memory V1.2` | [`memory-v1.2`](cards/memory/kicad/deprecated/v1.2/) | yes | MATCH (99/99 nets) | 78 | 208 + 0 unconnected | ok |
| `cards/memory/eagle/v1.3/Memory V1.3` | [`memory-v1.3`](cards/memory/kicad/v1.3/) | yes | MATCH (115/115 nets) | 81 | 250 + 100 unconnected | ok |
| `cards/protocard/eagle/v1.0/ProtoCard-Prod-V1.0` | [`protocard-v1.0`](cards/protocard/kicad/v1.0/) | yes | MATCH (87/87 nets) | - | 268 + 0 unconnected | ok |
| `cards/register/eagle/deprecated/v1.0/Index Registers - 1.0` | [`register-v1.0`](cards/register/kicad/deprecated/v1.0/) | yes | MATCH (192/192 nets) | 158 | 212 + 0 unconnected | ok |
| `cards/register/eagle/deprecated/v1.0-no-address/Index Registers - 1.0` | [`register-v1.0-no-address`](cards/register/kicad/deprecated/v1.0-no-address/) | yes | MATCH (192/192 nets) | 158 | 212 + 0 unconnected | ok |
| `cards/register/eagle/v1.1/Index Registers - 1.1` | [`register-v1.1`](cards/register/kicad/v1.1/) | yes | MATCH (223/223 nets) | 117 | 440 + 0 unconnected | ok |
| `cards/sequencer-logic/eagle/deprecated/v2.0/Sequencer-Logic-Prod-V2.0` | [`sequencer-logic-v2.0`](cards/sequencer-logic/kicad/deprecated/v2.0/) | yes | MATCH (274/274 nets) | 109 | 720 + 0 unconnected | ok |
| `cards/sequencer-logic/eagle/v2.1/Sequencer-Logic-Prod-V2.1l` | [`sequencer-logic-v2.1`](cards/sequencer-logic/kicad/v2.1/) | yes | MATCH (282/282 nets) | 107 | 712 + 0 unconnected | ok |
| `cards/sequencer-logic/eagle/v2.1/orig size/Sequencer-Logic-Prod-V2.1` | [`sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1`](cards/sequencer-logic/kicad/v2.1/orig-size/sequencer-logic-prod-v2.1/) | no | MATCH (282/282 nets) | 107 | 772 + 4 unconnected | ok |
| `cards/sequencer-logic/eagle/v2.1/orig size/Sequencer-Logic-Prod-V2.1 copy` | [`sequencer-logic-v2.1-orig-size-sequencer-logic-prod-v2.1-copy`](cards/sequencer-logic/kicad/v2.1/orig-size/sequencer-logic-prod-v2.1-copy/) | no | n/a (schematic only) | 342 | - | ok |
| `cards/sequencer-memory/accessories/eeprom-adaptor/eeprom adaptor` | [`sequencer-memory-eeprom-adaptor`](cards/sequencer-memory/accessories/eeprom-adaptor/kicad/) | yes | MATCH (5/5 nets) | 3 | 16 + 0 unconnected | ok |
| `cards/sequencer-memory/eagle/deprecated/v2.0/Sequencer-Memory-V2.0` | [`sequencer-memory-v2.0`](cards/sequencer-memory/kicad/deprecated/v2.0/) | yes | MATCH (105/105 nets) | - | 497 + 0 unconnected | ok |
| `cards/sequencer-memory/eagle/v2.1/Sequencer-Memory-V2.1` | [`sequencer-memory-v2.1`](cards/sequencer-memory/kicad/v2.1/) | yes | MATCH (106/106 nets) | - | 461 + 0 unconnected | ok |
| `cards/video/eagle/v1.0-fusion-export-2026-09-18/Video_1.0` | [`video-v1.0-fusion-export-2026-09-18`](cards/video/kicad/v1.0-fusion-export-2026-09-18/) | yes | MISMATCH (115/117 nets) | 101 | 229 + 0 unconnected | ok |
