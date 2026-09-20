# MIGRATION.md — where everything comes from

EXECUTED 2026-09-19 by `tools/migrate_run.py` from the plan in `migration/dryrun-plan.tsv` (built by `tools/migrate_dryrun.py`, which is this map in executable form). 1,859 files copied and hash-verified, 3,288 duplicates recorded instead of copied, 7 large files listed in `migration/large-files-manifest.tsv`. This is the map. "Authoritative" means: the newest copy found anywhere
under `YACCS/`, established by modification time and content hash across all copies
(inventory script: `tools/inventory.py`, to be migrated from the session scratchpad).

Abbreviations for source copies:
- **GV** = `YACCS/YACC gitversion/YACC1-2020` (2025-03 checkout of the git repo, plus June-2025 PCB work)
- **NG** = `YACCS/newgit/YACC1-2020` (2026-06 clone with one extra commit)
- **24** = `YACCS/YACC1-2024`, **20** = `YACCS/YACC1-2020` (2021 clones with later uncommitted edits)
- **OLD** = `YACCS/YACCS-OLD/<backup>`

## hardware/

**Layout rule (Ken 2026-09-20):** `hardware/cards/<card>/eagle/<rev>/` holds the ACTIVE version (table `ACTIVE` in
`tools/migrate_dryrun.py`) and any newer design never ordered; every lower version goes to `eagle/deprecated/<rev>/`.
Fab output → `<rev>/fab/`, BOM exports → `<rev>/bom/`. Fabricated revisions carry a `FABRICATED` marker;
`archive/superseded-revisions/` holds only designs that were never built. The table is `tools/fabricated.py`, rendered as `hardware/FABRICATED.md`.
Boards that sat in `PCB/Production/Old & obsolete` in the 2020-08 / 2021-01 snapshots (readme: "Old designs do not use")
count as fabricated-then-superseded and were recovered from those snapshots.

| Destination | Source (authoritative) | Notes |
|---|---|---|
| bus/ signal table | `~/Documents/Arduino/libraries/YACC/YACC_Common_header.h` (2020-09-01) + GV `YACC1 Connector - V3.2.pdf` | the header is NOT in any repo copy today; it is the bus tester's and sequencer's truth |
| bus/backplane | GV `PCB/Production/BUS-PROD-V2.0` | V1.1 (fabricated) → `eagle/v1.1`, its Working copy → `v1.1-working-edits` |
| bus/bus-template | GV `PCB/Working - Under Develolpment/Bus Template V3.2` | V3.0, V3.1 → archive |
| bus/bus-jumper-horizontal | GV `PCB/Production/Bus Jumper Horizontal V3.2` | |
| bus/bus-jumper-vertical | GV Production `Bus Jumper Vertical V3.0` (fabricated) + Working V3.1 (design only) | 2020-08 snapshot copy → `v3.0-2020-08` |
| bus/blank-card | GV `PCB/Working - Under Develolpment/Blank-V3.1` (June-2025 gerbers) | |
| cards/memory | `YACCS/kicad/memory-card-v1.3` (KiCad, proven) + GV `.../Memory v1.3` (Eagle) | **v1.3 is FABRICATED and in the machine** (ordered 2025-06, never moved to PCB/Production); v1.2 (Production) → `eagle/v1.2`, v1.0/v1.1 recovered from the snapshots → `eagle/v1.0`, `v1.1`, all fabricated; `test/Memory V1.3.txt` is a duplicate of the v1.3 .sch |
| cards/alu | GV Production `ALU-V3.2` = **the built ALU** (`eagle/v3.2`) | GV Working `ALU-V3.3` = V3.2 with a stale bus label → folded (skip); fabricated V3.0-2layer, V3.1, V3.1-resubmit, V3.1-buried-vias → `eagle/deprecated/`; `ALU-V3.3-16*` (16-bit experiment) → **deleted, Ken 2026-09-20**; "notused" → archive |
| cards/sequencer-logic | GV Production + Working `Sequencer-Logic-v2.1` (identical, merged into `eagle/v2.1`) | v2.0 (fabricated, from snapshots) → `eagle/v2.0`; V1.0 → archive |
| cards/sequencer-memory | GV Production + Working `Sequencer-Memory-V2.1` (identical, merged into `eagle/v2.1`) | V2.0 (fabricated) → `eagle/v2.0`; V1.0 → archive |
| cards/register | GV Production `Index Registers 1.1` = built card (`eagle/v1.1`); Working 1.2 = design only | 1.0 and "no address 1.0" (fabricated, from snapshots) → `eagle/v1.0`, `v1.0-no-address` |
| cards/io | GV `PCB/Production/IO-V-1.1` (**the built card, in the machine**) | GV Working `IO-V-1.1` has a different sch/brd (post-fab edits, never ordered) → `eagle/v1.1-working-edits/`; IO 1.0 → archive |
| cards/bus-tester | GV Production `Bus Tester V3.1` = built card (`eagle/v3.1`); Working V3.11 = board-only design | "Bus Tester orig" = the 2016 TESTER-PROD-V1.1 board = **the test board in use** → `eagle/v1.1`; V3.1/V3.11 never ordered; gen-1 TESTER-PROD → archive |
| cards/video | `YACCS/video/Video_1.0.sch` + `Blank V3.1.brd` (Fusion export 2026-09-18) | **Fusion 360 is the master**; open issues: CS/RS on A0, missing pull-ups, the block-0/9 write-through fault |
| cards/mem-switch, mem-register | GV `PCB/Production/Mem Switch V1.1`, `Mem Register V1.0` | Mem Switch V1.0 (fabricated) → `eagle/v1.0` |
| cards/sequencer-memory/accessories/eeprom-adaptor | 24 `PCB/Working - Under Develolpment/eeprom adaptor` | accessory of the sequencer-memory card: plugs into IC9 to take a larger EEPROM (Ken 2026-09-20); only 24 has the OSH Park invoice (→ `fab/`) |
| cards/protocard | GV `PCB/Production/PROTOCARD-PROD-V1.0` | |
| cards/address-tmp | 2021-01 snapshot `Production/Old & obsolete/Address and TMP-V1.0` (fabricated, retired card) | GV Working copy (edited sch) → `eagle/v1.0-working-edits` |
| cards/io | (see above) IO 1.0 (fabricated, from snapshots) → `eagle/v1.0` | |
| libraries/eagle | 20 `Utilities/Eagle` (only copy NOT iCloud-evicted) + `pinhead_3row-2.lbr`, `oshpark-2layer-auto-routing.dru` at the copy roots | SparkFun/Adafruit libs are third-party |
| mechanical | NG or GV `mech parts` (5 files incl. `clip12~.skp`) | all evicted in 20/24 |
| fab | routed automatically by the FAB pattern in `migrate_dryrun.py`: gerber zips/dirs, `.cam`, `.dri`/`.gpi`, `.job`, invoices from every card revision folder → `<rev>/fab/`; Eagle BOM exports → `<rev>/bom/` | most boards have NO gerbers in any copy (OSH Park takes the `.brd` directly) |

## firmware/

| Destination | Source | Notes |
|---|---|---|
| monitor/monitor.asm | 24 or 20 `Software-vs/Assembler/monitor.asm` (= git ff7d85a, **what is burned**) | NG/GV copy = 3bcacf3 "not working"; `Software pre vs` = 8afde21 (ON/OFF + break-in, never burned) → keep as `monitor/candidates/` |
| monitor/monnew.asm | 20 `Software/Assembler/monnew.asm` (2025-03-14) + its `yacc1.def` | small D/M/B monitor draft; only in 20 |
| basic/basic.asm | same three-way choice as monitor; ff7d85a is burned | |
| rom/shipped | 24 `Software-vs/Assembler/rom` (byte-identical to the EPROM captured 2026-09-18) + capture files from the session scratchpad | add `verify.py` (bus-tester capture vs image) |
| rom/makerom | `Software-vs/Assembler/makerom` | |
| microcode | 24 `Software/Sequencer Card/uCode-Generator2` + `yaccsignaldata2.h`, `yaccsignaldefine.h` | v1 generator + its `yaccsignaldata.h` → archive; `test.hex` = the image (regenerated byte-identical); `cache.old` dropped |
| abi | derived from `basic.asm` header (BIOS vectors $FFC0..), `monitor.asm` header (ports, variables) | new doc |

## software/

| Destination | Source | Notes |
|---|---|---|
| assembler | GV `Software/Assembler` TOOL files only + 20's 2025 `yacc1.def` | firmware sources/builds → `firmware/`, test program → `tests/assembler/`, `old/rcasm-orig` → `upstream/`, `old/rcasm*` → archive, `old/a18*` → `archive/third-party/`, artefacts dropped (2026-09-20) |
| emulator | 24 `Software/emulator/main.c` (2026-06-03, adds -m/-f) | only in 24 |
| disassembler | 24 `Software/Sequencer Card/disasm2` (2024-06-25) | `disasm` (v1, 32-step) → archive |
| ubasic-c | 24 `Software-vs/ubasic-master` (2024-06-28) | `ubasic-master-orig` = upstream reference |
| (16-bit experiment) | `Software/Assembler-16`, `emulator-16`, `opcodes-16.h`, `PCB/.../ALU-V3.3-16*` | **NOT migrated**: deleted on Ken's instruction 2026-09-20 ("useless"); still in YACCS |
| software/opcodes.h | 24 `Software/opcodes.h` (2024-06-19) | shared by emulator, disasm2, microcode gen; `tools/layout_links.py` symlinks keep the old relative includes working |

## embedded/

| Destination | Source | Notes |
|---|---|---|
| bus-tester/* | 24 `Software-vs/Bus Test Card/*` (identical to GV/NG) | 20's `bus-driver.ino` is a half-started port to MCP23X17 2.x (only include+type changed) → keep as `bus-driver-mcp23x17-wip/` |
| sequencer-card/Sequencer3 | 24 `Software/Sequencer Card/Sequencer3` (2024-07-10) | only in 24; Sequencer2 `download/` 2024-07-09 also 24 |
| sequencer-card/deprecated | 24 `Software pre vs/Sequencer Card/Sequencer`, `Software/Sequencer Card/Sequencer2`, senders 1–2, the Sept-2020 EEPROM test | superseded generations |
| clocker | any `Utilities/clocker/clocker.ino` | identical |
| command-sender | GV/24 `.../Command sender` | `command_sender_8` current; 5–7 and `old/` → `deprecated/`; the commands PDF → `docs/procedures/` |
| libraries | `~/Documents/Arduino/old-libraries/Adafruit_MCP23017_Arduino_Library` (1.1.0) + `~/Documents/Arduino/libraries/YACC/*.h` | **not in any repo copy today** |

## tools/

From the 2026-09 session scratchpad (to be copied in): `busdrv.py`, `alias_min.py`, `eagle_sch_to_kicad.py`,
`compare_netlists.py`, `finish_board.py`, `inventory.py`. The KiCad tools already live in
`YACCS/kicad/memory-card-v1.3/tools/`.

## tests/

| Destination | Source |
|---|---|
| bus-tester scripts (ALU, memory, index register, IO/UART, SP-PC vectors, gen-test-vectors C) | GV `Software/Bus Test Card/Command sender/tests/` |
| logic analyser settings | same tree, `ramtest.logicsettings` |
| assembler test programs | GV `Software/Assembler/yacc1test.asm` + `old/yacc1test*.asm` variants; NG `test_output.txt` (2026-05-26 run) |
| EPROM/EEPROM tests | `Software-vs/Old-obselete/Memory Card/test EPROM`, `Test EEPROM/mem.ino` |
| hardware findings 2026-09 | session notes: memory-card block map, EPROM identity, video-card D1/D2 pins, block-0/9 write-through |

## docs/

| Destination | Source |
|---|---|
| system | `README.md`, `Status.md`, `YACC1-2020 Opcodes - Sheet1-3.pdf` (2023-11 copy in 20 is newer than GV's), `YACC1 Connector - V3.2.pdf`, `Utilities/Waveforms/*.webarchive`, `Software/Assembler/asm.txt` |
| cards/* | every `Notes.rtf` / `Build Notes.rtf` in the board folders (GV has the full set), `PCB/System Build Notes.rtf`, `PCB/Working.../Notes - BUS.rtf`, `Readme.md` |
| procedures | Bus Tester `Build Notes.rtf` (bring-up sequence), `BUS Driver Commands - Google Docs.pdf`, Memory `Build Notes.rtf` |
| history | `General Notes/*.rtf`, OLD `YACC1-BACKUP/Build notes and revisions.rtf`, `UPDATE to 1.21.rtf`, `Layout Specs.pdf`, `Other-do-not-git/NOTES Jan 2:17 orig.rtf`, `Presentations/yacc1.pptx` (142 MB → external/LFS) |
| datasheets | GV `Data Sheets` (29 files; the 20/24 copies have 9) |
| references | OLD `YACC1-BACKUP/External Resources`, `YACC1A/External Resources`, `Other-do-not-git/avrbeginners*.pdf`, `Software pre vs/Division_algorithm.pdf` |

## vm/ and legacy applications

`YACC1-2024/Required Applications/` (593 MB, all evicted): Parallels installer, JDK 8 + NetBeans 8.2, JDK 22.
These are what the NetBeans-era C projects were built with. Proposal: `vm/README.md` + one manifest
per image/installer (name, version, SHA-256, size, where the bytes live), nothing binary in git.

## archive/

| Destination | Source |
|---|---|
| gen1-2015-2018 | OLD `YACC1-BACKUP`, `YACC1A`, `YACC1A1`, `YACC1B` (Simulation/Logisim + 74x library, Yacc1-Assembler + microcode ROM creator in Python = `YACC1-master`, PCB-PRODUCTION gen-1 boards, SP-PC, Register V1.x/3.0, TESTER-PROD, BUS 1.x, SEQUENCER-PROD V1.0, Keynote `CPU-v1.key`, `controlbus.xlsx`, tinyBasic/tcbasic/RCA Tiny BASIC, TinyBasicC, Processing controlP5) — deduplicated by content |
| superseded-revisions | OLD `YACC1-2020-ORIG`, `-OLD`, `-backup-pre-git-backup`, `July 2021 backup` unique board revisions (ALU V3.0-2 layer, V3.1, Sequencer 2.0, Index Registers 1.0/1.1, IO 1.0, Memory 1.0/1.1/1.2, Sequencer-Memory 2.0) + everything under `PCB/*/Old and obsolete` |
| eagle-projects | `~/Documents/eagle/projects/video` (LM1881 sync converter "conv") |

## Not migrated (out of scope or junk)

- `YACC1-2026` (empty skeleton; every one of its 596 files verified byte-identical to a copy elsewhere
  or to a Finder duplicate beside it, 2026-09-19; Ken is deleting it), `dir struct` (its mkdir script)
- Eagle autosave/backup files (`*.b#N`, `*.s#N`), NetBeans `build/`, `dist/`, `nbproject/`, `*.dSYM`, `.DS_Store`
- Finder duplicates in `YACC1-2026/PCB/Production` (`... 2.brd`, `CAMOutputs 2`)
- `Dear TSA.docx`
- the 1802 ELF projects (separate project; the ELF video card is a different design from the YACC1 one)
