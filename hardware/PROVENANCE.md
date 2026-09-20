# Provenance of every board version

Generated %s by `tools/gen_provenance.py`. **Source** = the YACCS folder the files were copied from. **Real date** = the oldest modification date of any byte-identical copy anywhere in YACCS: git checkouts (gitversion = 2025-03-06, newgit = 2026-05-21) stamp their own date on every file, so a version whose oldest copy is 2020 was made in 2020 whatever the checkout says. **Copies** = identical copies and the YACCS folders holding them (2020/2024 = the non-git working copies with real dates; YACC1-2020-ORIG = Aug-2020 snapshot, YACC1-2020-OLD = Jan-2021, July 2021 backup, YACC1A/A1/B/BACKUP = 2016-18 gen-1 backups).

| Version folder | Source in YACCS | Design file | Real date (oldest identical copy) | Copies |
|---|---|---|---|---|
| `bus/backplane/eagle/deprecated/v1.1` | `YACC gitversion/YACC1-2020/PCB/Production/BUS-PROD-V1.1` | `yacc2buss.brd` | 2016-06-16 | 13 in YACC1-2020 July 2021 backup, YACC1-2020-ORIG, YACC1-BACKUP, YACC1A, YACC1A1, gitversion, newgit |
|  |  | `yacc2buss.sch` | 2016-06-14 | 20 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, YACC1-BACKUP, YACC1A, YACC1A1, gitversion, newgit |
| `bus/backplane/eagle/v2.0` | `YACC gitversion/YACC1-2020/PCB/Production/BUS-PROD-V2.0` | `yacc2buss.brd` | 2021-08-03 | 5 in 2020, gitversion, newgit |
|  |  | `yacc2buss.sch` | 2021-07-26 | 5 in 2020, gitversion, newgit |
| `bus/blank-card/eagle/v3.1` | `YACC gitversion/YACC1-2020/PCB/Working - Under Develolpment/Blank-V3.1` | `Blank V3.1.brd` | 2020-08-23 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Blank V3.1.sch` | 2020-08-23 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `bus/bus-jumper-horizontal/eagle/deprecated/v3.0` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/Bus Jumper V3.0-horiz` | `Jumper Board V3.0.brd` | 2020-06-16 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
|  |  | `Jumper Board V3.0.sch` | 2020-06-16 | 22 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `bus/bus-jumper-horizontal/eagle/v3.2` | `YACC gitversion/YACC1-2020/PCB/Production/Bus Jumper Horizontal V3.2` | `Jumper Board Horizontal V3.1.brd` | 2020-07-20 | 11 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `Jumper Board Horizontal V3.1.sch` | 2020-06-16 | 22 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `bus/bus-jumper-vertical/eagle/v3.0` | `YACC gitversion/YACC1-2020/PCB/Production/Bus Jumper Vertical V3.0` | `Jumper Board V3.0.brd` | 2020-06-16 | 6 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-ORIG, gitversion, newgit |
|  |  | `Jumper Board V3.0.sch` | 2020-06-16 | 22 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `Jumper Board Vertical V3.1.brd` | 2020-06-18 | 7 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `bus/bus-template/eagle/v3.2` | `YACC gitversion/YACC1-2020/PCB/Working - Under Develolpment/Bus Template V3.2` | `Bus Template V3.2.sch` | 2020-11-29 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/address-tmp/eagle/deprecated/v1.0` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/Address and TMP-V1.0` | `Address and TMP V1.0.brd` | 2020-06-20 | 9 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `Address and TMP V1.0.sch` | 2020-06-20 | 4 in YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup |
| `cards/alu/eagle/deprecated/v3.0-2layer` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/ALU-V3.0-2 layer` | `alu4.brd` | 2020-06-13 | 3 in YACC1-2020-OLD, YACC1-2020-ORIG, YACC1B |
|  |  | `alu4.sch` | 2020-06-14 | 3 in YACC1-2020-OLD, YACC1-2020-ORIG, YACC1B |
| `cards/alu/eagle/deprecated/v3.1-buried-vias` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/ALU-V3.1-buried-vias` | `ALU V3.1.brd` | 2020-07-07 | 9 in YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `ALU V3.1.sch` | 2020-07-07 | 11 in YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `cards/alu/eagle/deprecated/v3.1-resubmit` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/ALU-V3.1 resubmit` | `ALU V3.1.brd` | 2020-07-08 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
|  |  | `ALU V3.1.sch` | 2020-07-07 | 11 in YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `cards/alu/eagle/deprecated/v3.1` | `YACC gitversion/YACC1-2020/PCB/Working - Under Develolpment/Old and obsolete/ALU-V3.1` | `ALU V3.1.brd` | 2020-07-07 | 9 in YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `ALU V3.1.sch` | 2020-07-07 | 11 in YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `cards/alu/eagle/v3.2` | `YACC gitversion/YACC1-2020/PCB/Production/ALU-V3.2` | `ALU V3.2.brd` | 2020-11-29 | 8 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `ALU V3.2.sch` | 2020-11-29 | 5 in 2020, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/bus-tester/eagle/v1.1` | `YACC gitversion/YACC1-2020/PCB/Production/Bus Tester orig` | `tester.brd` | 2018-03-15 | 6 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `tester.sch` | 2020-08-15 | 6 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `cards/bus-tester/eagle/v3.1` | `YACC gitversion/YACC1-2020/PCB/Production/Bus Tester V3.1` | `tester.brd` | 2020-07-15 | 11 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `tester.sch` | 2020-07-15 | 16 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `cards/io/eagle/deprecated/v1.0` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/IO-V-1.0` | `IO V1.0.brd` | 2020-07-13 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
|  |  | `IO V1.0.sch` | 2020-07-13 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
| `cards/io/eagle/v1.1` | `YACC gitversion/YACC1-2020/PCB/Production/IO-V-1.1` | `IO V1.1.brd` | 2020-11-29 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `IO V1.1.sch` | 2020-11-29 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/mem-register/eagle/v1.0` | `YACC gitversion/YACC1-2020/PCB/Production/Mem Register V1.0` | `Mem Register V1.0.brd` | 2021-07-19 | 5 in 2020, gitversion, newgit |
|  |  | `Mem Register V1.0.sch` | 2021-07-19 | 5 in 2020, gitversion, newgit |
| `cards/mem-switch/eagle/deprecated/v1.0` | `YACC gitversion/YACC1-2020/PCB/Production/Mem Switch V1.0` | `Mem Switch V1.0.brd` | 2021-06-23 | 7 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Mem Switch V1.0.sch` | 2021-06-23 | 7 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/mem-switch/eagle/v1.1` | `YACC gitversion/YACC1-2020/PCB/Production/Mem Switch V1.1` | `Mem Switch V1.1.brd` | 2021-07-19 | 5 in 2020, gitversion, newgit |
|  |  | `Mem Switch V1.1.sch` | 2021-07-19 | 5 in 2020, gitversion, newgit |
| `cards/memory/eagle/deprecated/v1.0` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/Memory v1.0` | `Memory V1.0.brd` | 2020-06-18 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
|  |  | `Memory V1.0.sch` | 2020-06-18 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
| `cards/memory/eagle/deprecated/v1.1` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/Memory v1.1` | `Memory V1.0.brd` | 2020-06-19 | 9 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
|  |  | `Memory V1.0.sch` | 2020-06-19 | 9 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup, gitversion, newgit |
| `cards/memory/eagle/deprecated/v1.2` | `YACC gitversion/YACC1-2020/PCB/Production/Memory v1.2` | `Memory V1.2.brd` | 2020-11-29 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Memory V1.2.brd.old.brd` | 2020-09-01 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Memory V1.2.sch` | 2020-11-29 | 6 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit, test |
| `cards/memory/eagle/v1.3` | `YACC gitversion/YACC1-2020/PCB/Working - Under Develolpment/Memory v1.3` | `Memory V1.3.brd` | 2021-03-17 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Memory V1.3.sch` | 2021-03-17 | 6 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit, test |
| `cards/protocard/eagle/v1.0` | `YACC gitversion/YACC1-2020/PCB/Production/PROTOCARD-PROD-V1.0` | `ProtoCard-Prod-V1.0.brd` | 2016-07-14 | 11 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-BACKUP, YACC1A, YACC1A1, gitversion, newgit |
|  |  | `ProtoCard-Prod-V1.0.sch` | 2016-07-14 | 11 in 2020, 2024, YACC1-2020 July 2021 backup, YACC1-BACKUP, YACC1A, YACC1A1, gitversion, newgit |
| `cards/register/eagle/deprecated/v1.0-no-address` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/Index Registers - no address1.0` | `Index Registers - 1.0.brd` | 2020-06-18 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
|  |  | `Index Registers - 1.0.sch` | 2020-06-18 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
| `cards/register/eagle/deprecated/v1.0` | `YACCS-OLD/YACC1-2020-ORIG/PCB/Production/Index Registers 1.0` | `Index Registers - 1.0.brd` | 2020-06-18 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
|  |  | `Index Registers - 1.0.sch` | 2020-06-18 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
| `cards/register/eagle/v1.1` | `YACC gitversion/YACC1-2020/PCB/Production/Index Registers 1.1` | `Index Registers - 1.1.brd` | 2020-08-31 | 11 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Index Registers - 1.1.sch` | 2020-08-31 | 11 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/sequencer-logic/eagle/deprecated/v2.0` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/Sequencer-Logic-v2.0` | `Sequencer-Logic-Prod-V2.0.brd` | 2020-07-25 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
|  |  | `Sequencer-Logic-Prod-V2.0.sch` | 2020-07-25 | 2 in YACC1-2020-OLD, YACC1-2020-ORIG |
| `cards/sequencer-logic/eagle/v2.1` | `YACC gitversion/YACC1-2020/PCB/Production/Sequencer-Logic-v2.1` | `Sequencer-Logic-Prod-V2.1l.brd` | 2020-12-01 | 8 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Sequencer-Logic-Prod-V2.1l.sch` | 2020-12-01 | 8 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/sequencer-memory/accessories/eeprom-adaptor` | `YACC1-2024/PCB/Working - Under Develolpment/eeprom adaptor` | `eeprom adaptor.brd` | 2020-12-21 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `eeprom adaptor.sch` | 2020-12-19 | 5 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/sequencer-memory/eagle/deprecated/v2.0` | `YACCS-OLD/YACC1-2020-OLD/PCB/Production/Old & obsolete/Sequencer-Memory-V2.0` | `Sequencer-Memory-V2.0.brd` | 2020-07-25 | 4 in YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup |
|  |  | `Sequencer-Memory-V2.0.sch` | 2020-07-25 | 4 in YACC1-2020-OLD, YACC1-2020-ORIG, YACC1-2020-backup-pre-git-backup |
| `cards/sequencer-memory/eagle/v2.1` | `YACC gitversion/YACC1-2020/PCB/Production/Sequencer-Memory-V2.1` | `Sequencer-Memory-V2.1.brd` | 2020-12-01 | 8 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
|  |  | `Sequencer-Memory-V2.1.sch` | 2020-12-01 | 8 in 2020, 2024, YACC1-2020 July 2021 backup, gitversion, newgit |
| `cards/video/eagle/v1.0-fusion-export-2026-09-18` | `video` | `Video_1.0.brd` | 2026-09-18 | 1 in video |
|  |  | `Video_1.0.sch` | 2026-09-18 | 1 in video |
