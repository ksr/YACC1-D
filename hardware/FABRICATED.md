# Fabricated boards

Generated 2026-09-20 by `tools/gen_fabricated.py` from `tools/fabricated.py` (edit the table, then re-run).
Every revision folder under `hardware/` is listed; the ones with status **in-machine** or **fabricated** also carry a `FABRICATED` marker file.
"presumed" means the only evidence is that the folder sat in `PCB/Production` in the old tree.
Fabrication output (gerber zips, CAM jobs, drill/photoplotter logs, order invoices) lives in `hardware/fab/<card>/<rev>/`; the Eagle folder keeps only the design. Where the tree holds no fab output the board was most likely ordered by uploading the `.brd` straight to OSH Park, so the `.brd` in the design folder IS what was sent.

## In the machine

| Card | Revision | Design | Files sent to fab | Confirmed by | Note |
|---|---|---|---|---|---|
| backplane | V2.0 | `bus/backplane/eagle/v2.0` | `bus/backplane/eagle/v2.0/fab/` CAMOutputs/ | Ken 2026-09-20 | PCB/Production, 2021-07-26 (sch) / 2021-08-03 (brd): adds an 8th slot X8 and bulk electrolytics C7/C8 to V1.1. Folder also holds the DXF/SVG/PDF exports. CAMOutputs in fab/ |
| alu | V3.2 | `cards/alu/eagle/v3.2` | `cards/alu/eagle/v3.2/fab/` CAMOutputs/ | Ken 2026-09-20 | PCB/Production, 2020-11-29, the ALU in the machine; CAMOutputs in v3.2/fab. The Working 'ALU-V3.3' folder was this design with the bus label reverted - nothing new, folded 2026-09-20. Notes end with NEXT VERSION 3.3 but no 3.3 design was ever started. The Sept-2021 16-bit ALU (V3.3-16) was deleted from this tree on Ken's instruction 2026-09-20 (still in YACCS) |
| bus-tester | V1.1 | `cards/bus-tester/eagle/v1.1` | `cards/bus-tester/eagle/v1.1/fab/` gerbers.zip | Ken 2026-09-20 | the 2016 TESTER-PROD-V1.1 board (gerbers identical); Eagle folder was called 'Bus Tester orig' |
| sequencer-memory | adaptor | `cards/sequencer-memory/accessories/eeprom-adaptor` | `cards/sequencer-memory/accessories/eeprom-adaptor/fab/` oshpark-order-invoice-rmD8XYsD.pdf | Ken 2026-09-20 | EEPROM adaptor: plugs into IC9 (24Cxx I2C EEPROM socket) and carries two 24Cxx at I2C addresses 7 and 6 - doubles the microcode storage. Design 2020-12-19/21; OSH Park order rmD8XYsD 2024-06-19, 3 boards (invoice in fab/; the .brd was the upload) |
| io | V1.1 | `cards/io/eagle/v1.1` | `cards/io/eagle/v1.1/fab/` CAMOutputs/ | Ken 2026-09-19 | PCB/Production, 2020-11-29 (the Working copy of 2020-07-31 was the same board with the old Bus V3.1 net names; folded in 2026-09-20, only its Notes.rtf kept: it adds the never-done V1.2 ideas - directional data-bus buffer driven by -IO-RD, IC5 pin 5 to -BUS-EN). CAMOutputs in v1.1/fab |
| memory | v1.3 | `cards/memory/eagle/v1.3` | `cards/memory/eagle/v1.3/fab/` Memory V1_2025-06-27.zip, CAMOutputs/ | Ken 2026-09-19 | ordered 2025-06-27 (Memory V1_2025-06-27.zip) from the 2021-03-17 design; never moved to PCB/Production. KiCad conversion in cards/memory/kicad. The Working folder also held V1.0 files (= revision 1.1) and an earlier save of V1.2 - removed 2026-09-20, only V1.3 stays here |
| register | 1.1 | `cards/register/eagle/v1.1` | `cards/register/eagle/v1.1/fab/` CAMOutputs/ | Ken 2026-09-20 | PCB/Production, 2020-08-31; CAMOutputs in v1.1/fab. The Working 'Index Registers 1.2' folder held byte-identical copies of the 1.1 files renamed 1.2 plus a notes file asking whether bus direction should follow -RD-SEL; folded in here 2026-09-20 (only the notes were new). No 1.2 design exists |
| sequencer-logic | v2.1 | `cards/sequencer-logic/eagle/v2.1` | `cards/sequencer-logic/eagle/v2.1/fab/` CAMOutputs/ | Ken 2026-09-20 | PCB/Production, 2020-12-01, 218x114 mm ('V2.1l' = the lengthened board); CAMOutputs in fab/. 'orig size/' = the V2.1 circuit on the original 178 mm outline (silk still says V2.0) plus an unrouted 'copy' - intermediates, never ordered. The old-YACC1/ gen-1 files were dropped 2026-09-20 (identical to archive/gen1-2015-2018) |
| sequencer-memory | V2.1 | `cards/sequencer-memory/eagle/v2.1` | `cards/sequencer-memory/eagle/v2.1/fab/` CAMOutputs/ | Ken 2026-09-20 | PCB/Production, 2020-12-01; CAMOutputs in fab/. Carries the microcode EEPROM (IC9; see accessories/eeprom-adaptor) and the ATmega328 loader. old-YACC1/ gen-1 files dropped 2026-09-20 (identical to archive/gen1-2015-2018) |
| video | V1.0 | `cards/video/eagle/v1.0-fusion-export-2026-09-18` | **none in tree** | Ken 2026-09-18 | built from the Fusion 360 design (Fusion is the master; this folder is the 2026-09-18 Eagle export). Installed for bring-up, no CRTC fitted yet. The board file was exported as Blank V3.1.brd (the template it was started from) and is stored here as Video_1.0.brd. Inherits Blank V3.1's stale C3-C6 names (unused) |

## Every revision, by card

### backplane

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V2.0 | in-machine (Ken 2026-09-20) | `bus/backplane/eagle/v2.0` | `bus/backplane/eagle/v2.0/fab/` CAMOutputs/ | PCB/Production, 2021-07-26 (sch) / 2021-08-03 (brd): adds an 8th slot X8 and bulk electrolytics C7/C8 to V1.1. Folder also holds the DXF/SVG/PDF exports. CAMOutputs in fab/ |
| V1.1 | fabricated | `bus/backplane/eagle/deprecated/v1.1` | `bus/backplane/eagle/deprecated/v1.1/fab/` gerbers.zip | 2016-06-16, the gen-1 backplane (also in archive/gen1-2015-2018); still in PCB/Production in 2021, gerbers in fab/. A 2020 Eagle-9 re-save of it was dropped 2026-09-20 (identical) |

### blank-card

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V3.1 | fabricated | `bus/blank-card/eagle/v3.1` | `bus/blank-card/eagle/v3.1/fab/` Blank V3_2025-06-27.zip | 2020-08-23 design = Bus Template V3.1 schematic + card outline/connectors; ordered 2025-06-27 (zip + Fusion CAM in fab/). Base of the video card. CAUTION: carries Bus V3.1 names on C3-C6 (-ADDR-REG-RD0/LD0/RD1/LD1); the machine is Bus V3.2 (ADDR-REG-ID0..3) - make a Blank V3.2 before drawing the next card |
| V3.2 | design-only | `bus/blank-card/eagle/v3.2` | - | DERIVED 2026-09-20 from V3.1 by tools/make_blank_v32.py: the four C3-C6 nets renamed to Bus V3.2 (ADDR-REG-ID0..3), bus label and silk title updated, nothing else. Not fabricated. Use THIS as the template for new cards |

### bus-template

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V3.2 | design-only | `bus/bus-template/eagle/v3.2` | - | Eagle template, not a board |

### bus-jumper-horizontal

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V3.2 | fabricated (Ken 2026-09-20) | `bus/bus-jumper-horizontal/eagle/v3.2` | `bus/bus-jumper-horizontal/eagle/v3.2/fab/` CAMOutputs/ | PCB/Production, 2020-07-20: 231x115 mm, 4-layer, 10 mil traces. NOT FITTED - the jumper boards belong to an older bus arrangement and are obsolete (Ken 2026-09-20). Shares its schematic byte-for-byte with the vertical jumper; the .brd.orig here is the unrouted V3.1 intermediate |
| V3.0 | fabricated | `bus/bus-jumper-horizontal/eagle/deprecated/v3.0` | `bus/bus-jumper-horizontal/eagle/deprecated/v3.0/fab/` CAMOutputs/ | PCB/Production until 2021-01 (Old & obsolete), 2020-06-16: 231x70 mm, 2-layer, 6 mil traces - the first horizontal jumper, replaced by the taller 4-layer V3.2 a month later |

### bus-jumper-vertical

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V3.0 | fabricated (Ken 2026-09-20) | `bus/bus-jumper-vertical/eagle/v3.0` | `bus/bus-jumper-vertical/eagle/v3.0/fab/` CAMOutputs/ | PCB/Production, 2020-06-16: 76x114 mm, 2-layer. NOT FITTED - obsolete with the older bus arrangement (Ken 2026-09-20). Jumper Board Vertical V3.1.brd = identical copper, silk text corrected |

### address-tmp

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V1.0 | fabricated | `cards/address-tmp/eagle/deprecated/v1.0` | `cards/address-tmp/eagle/deprecated/v1.0/fab/` CAMOutputs/ | 2020-06-20, fabricated (PCB/Production until 2021-01, then retired: 'Old designs do not use'). Two 16-bit address registers + TMP built from eight 74373 latches, driven by the Bus V3.0/V3.1 strobes -ADDR-REG-RD0/LD0/RD1/LD1 on C3-C6; replaced by the Index Registers card + ADDR-REG-ID0..3 (Bus V3.2). CAMOutputs in fab/. A Working copy differing only by a stray 'test text' element was dropped 2026-09-20 |

### alu

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V3.2 | in-machine (Ken 2026-09-20) | `cards/alu/eagle/v3.2` | `cards/alu/eagle/v3.2/fab/` CAMOutputs/ | PCB/Production, 2020-11-29, the ALU in the machine; CAMOutputs in v3.2/fab. The Working 'ALU-V3.3' folder was this design with the bus label reverted - nothing new, folded 2026-09-20. Notes end with NEXT VERSION 3.3 but no 3.3 design was ever started. The Sept-2021 16-bit ALU (V3.3-16) was deleted from this tree on Ken's instruction 2026-09-20 (still in YACCS) |
| V3.1 | fabricated | `cards/alu/eagle/deprecated/v3.1` | `cards/alu/eagle/deprecated/v3.1/fab/` gerbers/ | Working/Old and obsolete; Production 2021-01 held resubmit + buried-vias variants |
| V3.1 | fabricated | `cards/alu/eagle/deprecated/v3.1-resubmit` | `cards/alu/eagle/deprecated/v3.1-resubmit/fab/` gerbers/ | PCB/Production until 2021-01 |
| V3.1 | fabricated | `cards/alu/eagle/deprecated/v3.1-buried-vias` | `cards/alu/eagle/deprecated/v3.1-buried-vias/fab/` gerbers/ | PCB/Production until 2021-01 |
| V3.0 | fabricated | `cards/alu/eagle/deprecated/v3.0-2layer` | `cards/alu/eagle/deprecated/v3.0-2layer/fab/` alu4_2020-06-14.zip | PCB/Production until 2021-01 (20 files incl. CAM outputs) |

### bus-tester

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V1.1 | in-machine (Ken 2026-09-20) | `cards/bus-tester/eagle/v1.1` | `cards/bus-tester/eagle/v1.1/fab/` gerbers.zip | the 2016 TESTER-PROD-V1.1 board (gerbers identical); Eagle folder was called 'Bus Tester orig' |
| V3.1 | design-only | `cards/bus-tester/eagle/v3.1` | - | 2020-07-15 redesign of the 2016 tester (latches IC11-IC15 drive the bus instead of the MCP23017 directly, -BUF-EN / -SOFT-BUS-EN / -SOFT-RESET, bypass caps, no reset switch); 114x178 mm 4-layer, routed, CAM run, NEVER ORDERED (Ken 2026-09-20: the board in use is v1.1). Folder v3.11-horizontal-unrouted/ = the next-day reshape to 243x114 mm, routing removed; Notes.rtf is the V3.11 superset |

### sequencer-memory

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| adaptor | in-machine (Ken 2026-09-20) | `cards/sequencer-memory/accessories/eeprom-adaptor` | `cards/sequencer-memory/accessories/eeprom-adaptor/fab/` oshpark-order-invoice-rmD8XYsD.pdf | EEPROM adaptor: plugs into IC9 (24Cxx I2C EEPROM socket) and carries two 24Cxx at I2C addresses 7 and 6 - doubles the microcode storage. Design 2020-12-19/21; OSH Park order rmD8XYsD 2024-06-19, 3 boards (invoice in fab/; the .brd was the upload) |
| V2.1 | in-machine (Ken 2026-09-20) | `cards/sequencer-memory/eagle/v2.1` | `cards/sequencer-memory/eagle/v2.1/fab/` CAMOutputs/ | PCB/Production, 2020-12-01; CAMOutputs in fab/. Carries the microcode EEPROM (IC9; see accessories/eeprom-adaptor) and the ATmega328 loader. old-YACC1/ gen-1 files dropped 2026-09-20 (identical to archive/gen1-2015-2018) |
| V2.0 | fabricated | `cards/sequencer-memory/eagle/deprecated/v2.0` | `cards/sequencer-memory/eagle/deprecated/v2.0/fab/` CAMOutputs/ | PCB/Production until 2021-01 |

### io

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V1.1 | in-machine (Ken 2026-09-19) | `cards/io/eagle/v1.1` | `cards/io/eagle/v1.1/fab/` CAMOutputs/ | PCB/Production, 2020-11-29 (the Working copy of 2020-07-31 was the same board with the old Bus V3.1 net names; folded in 2026-09-20, only its Notes.rtf kept: it adds the never-done V1.2 ideas - directional data-bus buffer driven by -IO-RD, IC5 pin 5 to -BUS-EN). CAMOutputs in v1.1/fab |
| V1.0 | fabricated | `cards/io/eagle/deprecated/v1.0` | `cards/io/eagle/deprecated/v1.0/fab/` CAMOutputs/ | PCB/Production until 2021-01 |

### mem-register

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V1.0 | fabricated (Ken 2026-09-20) | `cards/mem-register/eagle/v1.0` | `cards/mem-register/eagle/v1.0/fab/` CAMOutputs/ | PCB/Production 2021-07-19, the 16-byte RAM card used for bring-up (at $0010), removed from the bus once the memory card worked (Ken 2026-09-20); CAMOutputs in fab/. Drawn on Blank V3.1 (old RD/LD names on C3-C6, unused) |

### mem-switch

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V1.1 | fabricated (Ken 2026-09-20) | `cards/mem-switch/eagle/v1.1` | `cards/mem-switch/eagle/v1.1/fab/` CAMOutputs/ | PCB/Production 2021-07-19, the switch-programmed ROM card used for bring-up (at $0000), removed from the bus once the memory card worked (Ken 2026-09-20); CAMOutputs in fab/. Notes.rtf = what changed from 1.0 (bypass caps, 74240, switch orientation, LEDs, 16-byte block select). Drawn on Blank V3.1 so C3-C6 carry the old RD/LD names (unused) |
| V1.0 | fabricated | `cards/mem-switch/eagle/deprecated/v1.0` | `cards/mem-switch/eagle/deprecated/v1.0/fab/` CAMOutputs/ | PCB/Production 2021-06-23, built ('Version 1.0 works' per the 1.1 notes); superseded a month later by 1.1 (+60 parts: 74244 buffers, BRD-SEL, caps). Its Notes.rtf was the blank template's and was dropped 2026-09-20 |

### memory

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| v1.3 | in-machine (Ken 2026-09-19) | `cards/memory/eagle/v1.3` | `cards/memory/eagle/v1.3/fab/` Memory V1_2025-06-27.zip, CAMOutputs/ | ordered 2025-06-27 (Memory V1_2025-06-27.zip) from the 2021-03-17 design; never moved to PCB/Production. KiCad conversion in cards/memory/kicad. The Working folder also held V1.0 files (= revision 1.1) and an earlier save of V1.2 - removed 2026-09-20, only V1.3 stays here |
| v1.2 | fabricated | `cards/memory/eagle/deprecated/v1.2` | `cards/memory/eagle/deprecated/v1.2/fab/` CAMOutputs/ | PCB/Production, 2020-11-29 (also built). Memory V1.2.brd.old.brd = an earlier 31-part layout of V1.2 (2020-09-01) |
| v1.1 | fabricated | `cards/memory/eagle/deprecated/v1.1` | `cards/memory/eagle/deprecated/v1.1/fab/` CAMOutputs/ | PCB/Production until 2021-01; files still NAMED V1.0 (2020-06-19) but this is revision 1.1: adds the boot ROM remap (IC11 74157 + IC12 7474 FORCE-ROM) to 1.0 |
| v1.0 | fabricated | `cards/memory/eagle/deprecated/v1.0` | `cards/memory/eagle/deprecated/v1.0/fab/` CAMOutputs/ | PCB/Production until 2021-01 |

### protocard

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V1.0 | fabricated | `cards/protocard/eagle/v1.0` | `cards/protocard/eagle/v1.0/fab/` gerbers.zip | PCB/Production, gerbers |

### register

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| 1.1 | in-machine (Ken 2026-09-20) | `cards/register/eagle/v1.1` | `cards/register/eagle/v1.1/fab/` CAMOutputs/ | PCB/Production, 2020-08-31; CAMOutputs in v1.1/fab. The Working 'Index Registers 1.2' folder held byte-identical copies of the 1.1 files renamed 1.2 plus a notes file asking whether bus direction should follow -RD-SEL; folded in here 2026-09-20 (only the notes were new). No 1.2 design exists |
| 1.0 | fabricated | `cards/register/eagle/deprecated/v1.0` | `cards/register/eagle/deprecated/v1.0/fab/` CAMOutputs/ | PCB/Production until 2020-08 |
| 1.0 | fabricated | `cards/register/eagle/deprecated/v1.0-no-address` | `cards/register/eagle/deprecated/v1.0-no-address/fab/` CAMOutputs/ | PCB/Production until 2021-01 ("no address" variant) |

### sequencer-logic

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| v2.1 | in-machine (Ken 2026-09-20) | `cards/sequencer-logic/eagle/v2.1` | `cards/sequencer-logic/eagle/v2.1/fab/` CAMOutputs/ | PCB/Production, 2020-12-01, 218x114 mm ('V2.1l' = the lengthened board); CAMOutputs in fab/. 'orig size/' = the V2.1 circuit on the original 178 mm outline (silk still says V2.0) plus an unrouted 'copy' - intermediates, never ordered. The old-YACC1/ gen-1 files were dropped 2026-09-20 (identical to archive/gen1-2015-2018) |
| v2.0 | fabricated | `cards/sequencer-logic/eagle/deprecated/v2.0` | `cards/sequencer-logic/eagle/deprecated/v2.0/fab/` CAMOutputs/ | PCB/Production until 2021-01 |

### video

| Revision | Status | Design | Files sent to fab | Note |
|---|---|---|---|---|
| V1.0 | in-machine (Ken 2026-09-18) | `cards/video/eagle/v1.0-fusion-export-2026-09-18` | **none in tree** | built from the Fusion 360 design (Fusion is the master; this folder is the 2026-09-18 Eagle export). Installed for bring-up, no CRTC fitted yet. The board file was exported as Blank V3.1.brd (the template it was started from) and is stored here as Video_1.0.brd. Inherits Blank V3.1's stale C3-C6 names (unused) |

