#!/usr/bin/env python3
"""Dry-run migration from the YACCS tree into YACC1-D. Writes NOTHING except reports.

usage: migrate_dryrun.py <index.json from inventory.py> <report dir>

The RULES table is MIGRATION.md in executable form: (source copy, source path prefix, destination,
mode). First matching rule wins. Modes:
  copy      the authoritative copy of this item
  archive   goes to archive/, deduplicated by content
  manifest  not copied; only listed in a manifest (large binaries)
  skip      unwanted content, deliberately not migrated - its bytes never resurface from any backup either
  drop      this path is a duplicate of content kept elsewhere (e.g. gen-1 files inside a 2020 card folder):
            not copied from here or from the same path in a snapshot, but other holders of the bytes are unaffected
Every file of the four current copies must be claimed by some rule, else it is UNCLASSIFIED.
DEDUP: the source tree is never modified. After the plan is built, every archive-mode file whose
content (md5) is already going somewhere else is dropped from the copy and recorded in
dedup-dropped.tsv (source -> the destination that holds the same bytes), so nothing is lost, it is
just not copied twice. Copy-mode files are never dropped (a card folder must stay complete);
identical content at two copy destinations is only reported. Priority when the same bytes appear
in several archive sources: rule-based archive from the current copies first, then the backups in
ARCHIVE_SOURCES order (YACC1A1 is the fullest gen-1 backup, so it comes first).
PRODUCTION: a board folder under PCB/Production (or PCB-PRODUCTION / PRODUCTION in the backups)
is a board that was fabricated; production-boards.txt lists them next to what the rules call current.
For every copied file, the same relative path in the other current copies is checked: identical
content is fine, different content is a CONFLICT that a human must resolve.
"""
import sys, os, json, collections, time, fnmatch, re

SRC_ROOT = os.path.expanduser("~/Documents/YACCS")
GV, NG, C24, C20 = "YACC gitversion/YACC1-2020", "newgit/YACC1-2020", "YACC1-2024", "YACC1-2020"
CUR = [C20, C24, NG, GV]
OLD = "YACCS-OLD/"
W = "PCB/Working - Under Develolpment/"
OLDSNAP, ORIGSNAP = OLD + "YACC1-2020-OLD", OLD + "YACC1-2020-ORIG"
OP = "PCB/Production/Old & obsolete/"
P = "PCB/Production/"

RULES = [
    # ---- bus connector spec PDFs: one copy per version in docs/system/connector/ (they sat in 20 card folders; the per-card table is in that folder's README)
    ("ANY", "*YACC1 Connector - V3 - June-18-2020.pdf", "docs/system/connector/", "copy"),
    ("ANY", "*YACC1 Connector - V3.1.pdf", "docs/system/connector/", "copy"),
    ("ANY", "*YACC1 Connector - YACC 3.0-old.pdf", "docs/system/connector/", "copy"),
    ("ANY", "*YACC1 Connector - V3.2.pdf", "docs/system/connector/", "copy"),
    # ---------------- hardware: bus
    (GV, P + "BUS-PROD-V2.0/test.ctl", "hardware/libraries/eagle/", "copy"),   # the one kept copy of the autorouter control file
    (GV, P + "BUS-PROD-V2.0/", "hardware/bus/backplane/eagle/v2.0/", "copy"),
    (GV, P + "BUS-PROD-V1.1/", "hardware/bus/backplane/eagle/v1.1/", "copy"),                 # fabricated
    (GV, W + "Bus Template V3.2/", "hardware/bus/bus-template/eagle/v3.2/", "copy"),
    (GV, W + "Bus Template V3.1/", "archive/superseded-revisions/bus-template-v3.1/", "archive"),
    (GV, W + "Bus Template V3.0/", "archive/superseded-revisions/bus-template-v3.0/", "archive"),
    (GV, P + "Bus Jumper Horizontal V3.2/", "hardware/bus/bus-jumper-horizontal/eagle/v3.2/", "copy"),
    (GV, W + "Bus Jumper Horizontal V3.2/", "hardware/bus/bus-jumper-horizontal/eagle/v3.2/", "copy"),   # byte-identical to Production; only adds the unrouted V3.1 .brd.orig
    (GV, W + "Bus Jumper Vertical V3.1/Jumper Board Vertical V3.1.brd", "hardware/bus/bus-jumper-vertical/eagle/v3.0/", "copy"),   # same copper as V3.0, silk text only -> lives beside the V3.0 board
    (GV, W + "Bus Jumper Vertical V3.1/", "", "skip"),   # its .sch is byte-identical to V3.0's, its Notes.rtf lists no changes
    (GV, P + "Bus Jumper Vertical V3.0/", "hardware/bus/bus-jumper-vertical/eagle/v3.0/", "copy"),   # fabricated
    (GV, W + "Blank-V3.1/", "hardware/bus/blank-card/eagle/v3.1/", "copy"),
    (GV, W + "Blank-V1.0/", "archive/superseded-revisions/blank-v1.0/", "archive"),
    (GV, W + "BUS-PROD-V1.1/", "", "drop"),   # the 2016 board re-saved in Eagle 9.6.2 (2020-06-18): identical sch/copper, only a stray "V1.0" text removed
    (GV, W + "Notes - BUS.rtf", "", "skip"),   # byte-identical to Blank-V3.1/Notes.rtf, which is copied
    # ---------------- hardware: cards
    # The Working "Memory v1.3" folder was a working pile: V1.0 files (byte-identical to the v1.1 revision's), an earlier
    # save of V1.2 (electrically/physically identical to Production V1.2, old bus names) and V1.3 itself. Keep only V1.3 here.
    (GV, W + "Memory v1.3/Memory V1.0.sch", "", "skip"),
    (GV, W + "Memory v1.3/Memory V1.0.brd", "", "skip"),
    (GV, W + "Memory v1.3/Memory V1.0.pro", "", "skip"),
    (GV, W + "Memory v1.3/Memory V1.2.sch", "", "skip"),
    (GV, W + "Memory v1.3/Memory V1.2.brd", "", "skip"),
    (GV, W + "Memory v1.3/Memory V1.2.pro", "", "skip"),
    (GV, W + "Memory v1.3/Memory V1.2.pdf", "", "skip"),   # Eagle print of the earlier V1.2 state; Production v1.2 has its own
    (GV, W + "Memory v1.3/Memory V1.2.brd.old.brd", "hardware/cards/memory/eagle/v1.2/", "copy"),   # earlier V1.2 layout (31 parts, 2020-09-01) -> with V1.2
    (GV, W + "Memory v1.3/", "hardware/cards/memory/eagle/v1.3/", "copy"),
    (GV, P + "Memory v1.2/", "hardware/cards/memory/eagle/v1.2/", "copy"),                     # fabricated
    (GV, P + "Memory v1.1/", "archive/superseded-revisions/memory-v1.1/", "archive"),
    (GV, P + "Memory v1.0/", "archive/superseded-revisions/memory-v1.0/", "archive"),
    (GV, P + "Basic Memory/", "archive/gen1-2015-2018/boards/basic-memory/", "archive"),
    # 16-bit ALU experiment (Sept 2021): DELETED from YACC1-D on Ken's instruction 2026-09-20 ("all of the -16 work is useless");
    # the originals stay in YACCS (YACC1-2020/2024 Working, three snapshots: 'ok' routed 09-24, 'copy' + main unrouted 09-29)
    (None, W + "ALU-V3.3-16/", "", "skip"),
    (None, W + "ALU-V3.3-16 ok/", "", "skip"),
    (None, W + "ALU-V3.3-16 copy/", "", "skip"),
    (GV, W + "ALU-V3.3/", "", "skip"),   # NOTHING NEW: brd, notes, .pro and CAMOutputs byte-identical to V3.2; the .sch only reverts the bus ribbon label to the old Bus V3.1 names (folded 2026-09-20)
    (GV, P + "ALU-V3.3-notused/", "archive/superseded-revisions/alu-v3.3-notused/", "archive"),
    (GV, P + "ALU-V3.2/", "hardware/cards/alu/eagle/v3.2/", "copy"),                           # fabricated = ALU in the machine
    (GV, P + "ALU-V3.1/", "archive/superseded-revisions/alu-v3.1/", "archive"),
    (GV, P + "ALU-V3.1 resubmit/", "archive/superseded-revisions/alu-v3.1-resubmit/", "archive"),
    (GV, P + "ALU-V3.1-buried-vias/", "archive/superseded-revisions/alu-v3.1-buried-vias/", "archive"),
    (GV, P + "ALU-V3.0/", "archive/superseded-revisions/alu-v3.0/", "archive"),
    (GV, P + "ALU-V3.0-2 layer/", "archive/superseded-revisions/alu-v3.0-2layer/", "archive"),
    (GV, P + "ALU-V1.1/", "archive/gen1-2015-2018/boards/alu-v1.1/", "archive"),
    (GV, P + "ALU-PROD-V1.0/", "archive/gen1-2015-2018/boards/alu-prod-v1.0/", "archive"),
    # old-YACC1/ inside the sequencer folders = gen-1 (2016) Sequencer V1.0 files, byte-identical to the gen-1 backups in archive/ -> not duplicated here
    (GV, P + "Sequencer-Logic-v2.1/old-YACC1/", "", "drop"),
    (GV, W + "Sequencer-Logic-v2.1/old-YACC1/", "", "drop"),
    (GV, P + "Sequencer-Memory-V2.1/old-YACC1/", "", "drop"),
    (GV, W + "Sequencer-Memory-V2.1/old-YACC1/", "", "drop"),
    (OLDSNAP, OP + "Sequencer-Logic-v2.0/old-YACC1/", "", "drop"),
    (ORIGSNAP, "PCB/Production/Sequencer-Logic-v2.0/old-YACC1/", "", "drop"),
    (OLDSNAP, OP + "Sequencer-Memory-V2.0/old-YACC1/", "", "drop"),
    (ORIGSNAP, "PCB/Production/Sequencer-Memory-V2.0/old-YACC1/", "", "drop"),
    (GV, W + "Sequencer-Logic-v2.1/", "hardware/cards/sequencer-logic/eagle/v2.1/", "copy"),
    (GV, P + "Sequencer-Logic-v2.1/", "hardware/cards/sequencer-logic/eagle/v2.1/", "copy"),   # fabricated; == Working copy
    (GV, W + "Sequencer-Memory-V2.1/", "hardware/cards/sequencer-memory/eagle/v2.1/", "copy"),
    (GV, P + "Sequencer-Memory-V2.1/", "hardware/cards/sequencer-memory/eagle/v2.1/", "copy"), # fabricated; == Working copy
    (GV, W + "Index Registers 1.2/Notes.rtf", "hardware/cards/register/eagle/v1.1/", "copy"),   # = 1.1's notes + the 'next version 1.2' question
    (GV, W + "Index Registers 1.2/", "", "skip"),   # every other file is byte-identical to 1.1's (the '1.2' sch/brd are 1.1's renamed)
    (GV, P + "Index Registers 1.1/Notes.rtf", "", "skip"),   # superseded by the 1.2 notes above (a strict superset)
    (GV, P + "Index Registers 1.1/", "hardware/cards/register/eagle/v1.1/", "copy"),           # fabricated
    (GV, P + "IO-V-1.1/Notes.rtf", "", "skip"),   # superseded by the Working notes (strict superset)
    (GV, P + "IO-V-1.1/", "hardware/cards/io/eagle/v1.1/", "copy"),            # the built card (Ken 2026-09-19)
    # The Working IO-V-1.1 (sch/brd bytes 2020-07-31) is electrically and physically the Production board; only 4 net names differ
    # (old Bus V3.1 names). Its Notes.rtf is the richer one (adds the 'next version V1.2' ideas) -> keep just that.
    (GV, W + "IO-V-1.1/Notes.rtf", "hardware/cards/io/eagle/v1.1/", "copy"),
    (GV, W + "IO-V-1.1/", "", "skip"),
    # V3.11 (2020-07-16) = V3.1's schematic byte-for-byte + the board reshaped to 243x114 mm with the routing removed (airwires only)
    (GV, W + "Bus Tester V3.11/Notes.rtf", "hardware/cards/bus-tester/eagle/v3.1/", "copy"),   # V3.1 notes + 2 lines (ATmega bypass cap, IN/INT read mode)
    (GV, W + "Bus Tester V3.11/tester.brd", "hardware/cards/bus-tester/eagle/v3.1/v3.11-horizontal-unrouted/", "copy"),
    (GV, W + "Bus Tester V3.11/", "", "skip"),   # identical sch/switch template; CAMOutputs of an unrouted board
    (GV, P + "Bus Tester V3.1/Notes.rtf", "", "skip"),   # superseded by the V3.11 notes (strict superset)
    (GV, P + "Bus Tester V3.1/", "hardware/cards/bus-tester/eagle/v3.1/", "copy"),             # fabricated
    (GV, W + "Bus Tester V3.1/", "", "skip"),   # identical to Production V3.1 incl. the same CAM run; only two pick-and-place .txt differ (timestamps)
    (GV, P + "Bus Tester orig/", "hardware/cards/bus-tester/eagle/v1.1/", "copy"),             # = TESTER-PROD-V1.1 (2016) gerbers; the test board in use (Ken 2026-09-20)
    (GV, P + "Mem Switch V1.1/test.ctl", "", "drop"),    # generic Eagle autorouter control file; one copy kept in hardware/libraries/eagle/
    (GV, P + "Mem Switch V1.1/", "hardware/cards/mem-switch/eagle/v1.1/", "copy"),
    (GV, P + "Mem Switch V1.0/Notes.rtf", "", "drop"),   # = the Blank V3.1 template's own note (adding -VMA to the bus), not about this card
    (GV, P + "Mem Switch V1.0/", "hardware/cards/mem-switch/eagle/v1.0/", "copy"),             # fabricated
    (GV, P + "Mem Register V1.0/test.ctl", "", "drop"),
    (GV, P + "Mem Register V1.0/", "hardware/cards/mem-register/eagle/v1.0/", "copy"),
    # EEPROM adaptor = accessory of the sequencer-memory card: plugs into IC9 (EEPROM) to take a larger EEPROM (Ken 2026-09-20)
    (C24, W + "eeprom adaptor/oshpark-order-invoice-rmD8XYsD.pdf", "hardware/cards/sequencer-memory/accessories/eeprom-adaptor/fab/", "copy"),
    (C24, W + "eeprom adaptor/", "hardware/cards/sequencer-memory/accessories/eeprom-adaptor/", "copy"),
    (GV, P + "PROTOCARD-PROD-V1.0/", "hardware/cards/protocard/eagle/v1.0/", "copy"),
    (GV, W + "Old and obsolete/ALU-V3.1/", "hardware/cards/alu/eagle/v3.1/", "copy"),                       # was in PCB/Production until 2021-01
    (GV, W + "Old and obsolete/Address and TMP-V1.0/", "", "drop"),   # identical to the 2021-01 Production copy except one stray "test text" element added 2020-09-22
    (GV, W + "Old and obsolete/", "archive/superseded-revisions/working-old-and-obsolete/", "archive"),
    # Boards that sat in PCB/Production before 2021-01 ("Old & obsolete", readme: "Old designs do not use") = fabricated, then superseded.
    # They survive only in the two 2020/2021 snapshots. OLD (2021-01) is newer; ORIG (2020-08) adds a few files.
    (OLDSNAP, OP + "ALU-V3.0-2 layer/", "hardware/cards/alu/eagle/v3.0-2layer/", "copy"),
    (ORIGSNAP, "PCB/Production/ALU-V3.0-2 layer/", "hardware/cards/alu/eagle/v3.0-2layer/", "copy"),
    (OLDSNAP, OP + "ALU-V3.1 resubmit/", "hardware/cards/alu/eagle/v3.1-resubmit/", "copy"),
    (ORIGSNAP, "PCB/Production/ALU-V3.1 resubmit/", "hardware/cards/alu/eagle/v3.1-resubmit/", "copy"),
    (OLDSNAP, OP + "ALU-V3.1-buried-vias/", "hardware/cards/alu/eagle/v3.1-buried-vias/", "copy"),
    (ORIGSNAP, "PCB/Production/ALU-V3.1-buried-vias/", "hardware/cards/alu/eagle/v3.1-buried-vias/", "copy"),
    (OLDSNAP, OP + "Address and TMP-V1.0/", "hardware/cards/address-tmp/eagle/v1.0/", "copy"),
    (ORIGSNAP, "PCB/Production/Address and TMP-V1.0/", "hardware/cards/address-tmp/eagle/v1.0/", "copy"),
    (OLDSNAP, OP + "Bus Jumper V3.0-horiz/", "hardware/bus/bus-jumper-horizontal/eagle/v3.0/", "copy"),
    # The 2020-08 snapshot filed the two jumper boards the wrong way round ("-horiz" holds the 76x114 vertical board,
    # "-vert" the 231x70 horizontal one). Route each to its real card; identical files collapse, differing ones would conflict.
    (ORIGSNAP, "PCB/Production/Bus Jumper V3.0-horiz/", "hardware/bus/bus-jumper-vertical/eagle/v3.0/", "copy"),
    (ORIGSNAP, "PCB/Production/Bus Jumper V3.0-vert/", "hardware/bus/bus-jumper-horizontal/eagle/deprecated/v3.0/", "copy"),
    (OLDSNAP, OP + "IO-V-1.0/", "hardware/cards/io/eagle/v1.0/", "copy"),
    (ORIGSNAP, "PCB/Production/IO-V-1.0/", "hardware/cards/io/eagle/v1.0/", "copy"),
    (OLDSNAP, OP + "Index Registers - no address1.0/", "hardware/cards/register/eagle/v1.0-no-address/", "copy"),
    (ORIGSNAP, "PCB/Production/Index Registers 1.0/", "hardware/cards/register/eagle/v1.0/", "copy"),
    (OLDSNAP, OP + "Memory v1.0/", "hardware/cards/memory/eagle/v1.0/", "copy"),
    (ORIGSNAP, "PCB/Production/Memory v1.0/", "hardware/cards/memory/eagle/v1.0/", "copy"),
    (OLDSNAP, OP + "Memory v1.1/", "hardware/cards/memory/eagle/v1.1/", "copy"),
    (ORIGSNAP, "PCB/Production/Memory v1.1/", "hardware/cards/memory/eagle/v1.1/", "copy"),
    (OLDSNAP, OP + "Sequencer-Logic-v2.0/", "hardware/cards/sequencer-logic/eagle/v2.0/", "copy"),
    (ORIGSNAP, "PCB/Production/Sequencer-Logic-v2.0/", "hardware/cards/sequencer-logic/eagle/v2.0/", "copy"),
    (OLDSNAP, OP + "Sequencer-Memory-V2.0/", "hardware/cards/sequencer-memory/eagle/v2.0/", "copy"),
    (ORIGSNAP, "PCB/Production/Sequencer-Memory-V2.0/", "hardware/cards/sequencer-memory/eagle/v2.0/", "copy"),
    (OLDSNAP, OP + "readme.md", "hardware/cards/PRODUCTION-OLD-AND-OBSOLETE-readme-2021-01.md", "copy"),
    (GV, P + "Old & obsolete/", "archive/superseded-revisions/production-old-and-obsolete/", "archive"),
    (GV, "PCB/System Build Notes.rtf", "docs/procedures/", "copy"),
    (GV, "PCB/Readme.md", "docs/history/pcb-readme-2021.md", "copy"),
    (GV, "PCB/", "archive/superseded-revisions/pcb-misc/", "archive"),
    (C20, "YACC1-2020 Opcodes - Sheet1-3.pdf", "docs/system/", "copy"),
    (C20, "pinhead_3row-2.lbr", "hardware/libraries/eagle/", "copy"),
    (C20, "oshpark-2layer-auto-routing.dru", "hardware/libraries/eagle/", "copy"),
    (C20, "Utilities/Eagle/", "hardware/libraries/eagle/", "copy"),
    (NG, "mech parts/", "hardware/mechanical/", "copy"),
    # ---------------- firmware
    (C24, "Software-vs/Assembler/monitor.asm", "firmware/monitor/", "copy"),
    (C24, "Software-vs/Assembler/monitor.lst", "firmware/monitor/", "copy"),
    (C24, "Software-vs/Assembler/monitor.img", "firmware/monitor/", "copy"),
    (C24, "Software-vs/Assembler/basic.asm", "firmware/basic/", "copy"),
    (C24, "Software-vs/Assembler/basic.lst", "firmware/basic/", "copy"),
    (C24, "Software-vs/Assembler/basic.img", "firmware/basic/", "copy"),
    (C24, "Software-vs/Assembler/basic.asmold.asm", "firmware/basic/candidates/", "copy"),
    (C24, "Software-vs/Assembler/rom", "firmware/rom/shipped/", "copy"),
    (C24, "Software-vs/Assembler/makerom", "firmware/rom/", "copy"),
    (C24, "Software pre vs/Assembler/monitor.asm", "firmware/monitor/candidates/2021-09-8afde21/", "copy"),
    (C24, "Software pre vs/Assembler/basic.asm", "firmware/basic/candidates/2021-09-8afde21/", "copy"),
    (NG, "Software/Assembler/monitor.asm", "firmware/monitor/candidates/2021-09-02-3bcacf3-not-working/", "copy"),
    (NG, "Software/Assembler/basic.asm", "firmware/basic/candidates/2021-09-02-3bcacf3-not-working/", "copy"),
    (C20, "Software/Assembler/monnew.asm", "firmware/monitor/monnew-2025/", "copy"),
    (C20, "Software/Assembler/monnew.img", "firmware/monitor/monnew-2025/", "copy"),
    (C20, "Software/Assembler/xx", "firmware/monitor/monnew-2025/monnew.lst", "copy"),
    (C20, "Software/Assembler/yacc1.def", "software/assembler/", "copy"),           # 2025-03-14: the 2020 def + lowercase 'equ' -> THE assembler definition
    (C24, "Software/Sequencer Card/uCode-Generator2/cache.old", "", "drop"),        # byte-identical to cache
    (C24, "Software/Sequencer Card/uCode-Generator2/Makefile", "firmware/microcode/ucode-generator2/Makefile.netbeans", "copy"),
    (C24, "Software/Sequencer Card/uCode-Generator2/", "firmware/microcode/ucode-generator2/", "copy"),
    (C24, "Software/Sequencer Card/yaccsignaldata2.h", "firmware/microcode/", "copy"),
    (C24, "Software/Sequencer Card/yaccsignaldata.h", "archive/superseded-revisions/ucode-generator-v1/", "archive"),   # the v1 signal table (SPARE1/-BRANCH-RD-LO/HI) belongs with the v1 generator
    (C24, "Software/Sequencer Card/yaccsignaldefine.h", "firmware/microcode/", "copy"),
    (C24, "Software/Sequencer Card/uCode-Generator/", "archive/superseded-revisions/ucode-generator-v1/", "archive"),
    (C24, "Software/Sequencer Card/old & obselete/", "archive/superseded-revisions/sequencer-card-old/", "archive"),
    # ---------------- software (host)
    # ---- software/assembler = the YACC1 port of RC/asm v2.2 (Michael Riley). Only the TOOL lives here (cleanup 2026-09-20):
    (GV, "Software/Assembler/yacc1test.asm", "tests/assembler/", "copy"),                # the CPU test program assembled with it
    (GV, "Software/Assembler/old/yacc2test.asm", "", "drop"),                            # byte-identical to yacc1test.asm
    (GV, "Software/Assembler/old/yacc1test*", "tests/assembler/history-2020/", "copy"),  # 15 dated snapshots of the bring-up test program (Aug-Oct 2020)
    (GV, "Software/Assembler/old/rcasm-orig/asm.txt", "", "drop"),                       # the manual stays with the tool (identical)
    (GV, "Software/Assembler/old/rcasm-orig/asm.doc", "", "drop"),
    (GV, "Software/Assembler/old/rcasm-orig/", "software/assembler/upstream/rcasm-2.2/", "copy"),   # unmodified upstream RC/asm 2.2 + its other CPU .def files
    (GV, "Software/Assembler/old/a18-xcode/a18/c_standard_headers_indexer.c", "", "drop"),        # Xcode artefact
    (GV, "Software/Assembler/old/a18/", "archive/third-party/a18-cug149/", "archive"),   # Riley's A18 1802 cross-assembler (CUG149): RC/asm's ancestor, not YACC1 work
    (GV, "Software/Assembler/old/a18-xcode/", "archive/third-party/a18-cug149-xcode/", "archive"),
    (GV, "Software/Assembler/old/rcasm/a18", "", "drop"),                                # compiled x86_64 binaries
    (GV, "Software/Assembler/old/rcasm-old/a18", "", "drop"),
    (GV, "Software/Assembler/old/rcasm/", "archive/superseded-revisions/assembler-port-2020/rcasm/", "archive"),          # intermediate stages of the YACC1 port
    (GV, "Software/Assembler/old/rcasm-old/", "archive/superseded-revisions/assembler-port-2020/rcasm-old/", "archive"),
    (GV, "Software/Assembler/abc", "", "drop"),                                          # symbol-table listing from an assembly run
    (GV, "Software/Assembler/list", "", "drop"),                                         # a captured assembler run log
    (GV, "Software/Assembler/c_standard_headers_indexer.c", "", "drop"),                 # Xcode artefact
    (GV, "Software/Assembler/basic.asm", "", "drop"),                                    # firmware sources live under firmware/ (these = 3bcacf3, held as candidates)
    (GV, "Software/Assembler/monitor.asm", "", "drop"),
    (GV, "Software/Assembler/makerom", "", "drop"),                                      # = firmware/rom/makerom
    (GV, "Software/Assembler/basic.asmold.asm", "", "drop"),                             # = firmware/basic/candidates/basic.asmold.asm
    (GV, "Software/Assembler/basic.asmtmp copy", "firmware/basic/candidates/2020-11-10-port-draft/", "copy"),
    (GV, "Software/Assembler/basic.lst", "firmware/basic/candidates/2021-09-02-3bcacf3-not-working/", "copy"),      # git-HEAD build products
    (GV, "Software/Assembler/basic.img", "firmware/basic/candidates/2021-09-02-3bcacf3-not-working/", "copy"),
    (GV, "Software/Assembler/monitor.lst", "firmware/monitor/candidates/2021-09-02-3bcacf3-not-working/", "copy"),
    (GV, "Software/Assembler/monitor.img", "firmware/monitor/candidates/2021-09-02-3bcacf3-not-working/", "copy"),
    (GV, "Software/Assembler/rom", "firmware/rom/builds/2021-09-02-3bcacf3-not-working/", "copy"),
    (GV, "Software/Assembler/yacc1.def", "", "drop"),                                    # superseded by the 2025 def (adds 'equ'), routed below
    (GV, "Software/Assembler/Makefile", "software/assembler/Makefile.netbeans", "copy"),   # the NetBeans-generated one, kept byte-identical; a hand-written Makefile takes the plain name
    (GV, "Software/Assembler/", "software/assembler/", "copy"),
    (NG, "Software/Assembler/test_output.txt", "tests/assembler/", "copy"),
    (C24, "Software/emulator/main.c", "software/emulator/", "copy"),
    (C24, "Software/opcodes.h", "software/", "copy"),                                  # the ISA opcode table, shared by emulator / disasm2 / ucode-generator2
    (C24, "Software/Sequencer Card/disasm2/Makefile", "software/disassembler/disasm2/Makefile.netbeans", "copy"),
    (C24, "Software/Sequencer Card/disasm2/", "software/disassembler/disasm2/", "copy"),
    (C24, "Software/Sequencer Card/disasm/", "archive/superseded-revisions/disasm-v1/", "archive"),   # 32-step microcode version, pairs with ucode-generator-v1
    (C24, "Software-vs/ubasic-master/tokenizer copy.c", "", "drop"),                    # 2020-11-06 intermediate
    (C24, "Software-vs/ubasic-master/use-ubasic", "", "drop"),                          # compiled arm64 binaries
    (C24, "Software-vs/ubasic-master-orig/use-ubasic", "", "drop"),
    (C24, "Software-vs/ubasic-master/Makefile", "software/ubasic-c/ubasic-master/Makefile.netbeans", "copy"),
    (C24, "Software-vs/ubasic-master/", "software/ubasic-c/ubasic-master/", "copy"),
    (C24, "Software-vs/ubasic-master-orig/", "software/ubasic-c/ubasic-master-orig/", "copy"),
    # 16-bit software experiment (Sept 2021): DELETED on Ken's instruction 2026-09-20; originals stay in YACCS
    (None, "Software/Assembler-16/", "", "skip"),
    (None, "Software/emulator-16/", "", "skip"),
    (None, "Software/opcodes-16.h", "", "skip"),
    (None, "Software pre vs/Assembler-16/", "", "skip"),
    (None, "Software pre vs/emulator-16/", "", "skip"),
    (None, "Software pre vs/opcodes-16.h", "", "skip"),
    (C20, "Software pre vs/Division_algorithm.pdf", "docs/references/", "copy"),
    # ---------------- embedded
    # ---- tests cleanup 2026-09-20: 2016 gen-1 scripts (old signal names: RESET, ALU-FUNC, RD-AC, WDATA...) -> deprecated/gen1-2016/;
    #      the 2020 '.new' conversions (fix = the sed converter) stay current; ad-hoc junk dropped
    (None, "Software*/Bus Test Card/Command sender/tests/ALU/xx", "", "drop"),
    (None, "Software*/Bus Test Card/Command sender/tests/ALU/comands.txt", "", "drop"),
    (None, "Software*/Bus Test Card/Command sender/tests/IO/and", "", "drop"),
    (None, "Software*/Bus Test Card/Command sender/tests/Test Vectors/Registers/commands.txt", "", "drop"),
    (None, "Software*/Bus Test Card/Command sender/tests/Test Vectors/SP-PC/commands2.txt", "", "drop"),
    (None, "Software*/Bus Test Card/Command sender/tests/test", "tests/basic/", "copy"),
    (None, "Software*/Bus Test Card/Command sender/tests/ALU/fix", "tests/bus-tester-scripts/deprecated/gen1-2016/", "copy"),
    (None, "Software*/Bus Test Card/Command sender/tests/ALU/*.new", "tests/bus-tester-scripts/ALU/", "copy"),
    (None, "Software*/Bus Test Card/Command sender/tests/ALU/*", "tests/bus-tester-scripts/deprecated/gen1-2016/ALU/", "copy"),
    (None, "Software*/Bus Test Card/Command sender/tests/commands-1.txt", "tests/bus-tester-scripts/deprecated/gen1-2016/", "copy"),
    (None, "Software*/Bus Test Card/Command sender/tests/commands-2.txt", "tests/bus-tester-scripts/deprecated/gen1-2016/", "copy"),
    (GV, "Software/Bus Test Card/Command sender/tests/Test Vectors/", "tests/bus-tester-scripts/deprecated/gen1-2016/Test Vectors/", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/tests/Test Vectors/", "tests/bus-tester-scripts/deprecated/gen1-2016/Test Vectors/", "copy"),
    (GV, "Software/Bus Test Card/Command sender/tests/Address Register/", "tests/bus-tester-scripts/deprecated/address-register-2020-07/", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/tests/Address Register/", "tests/bus-tester-scripts/deprecated/address-register-2020-07/", "copy"),
    (None, "Software*/Bus Test Card/Command sender/tests/Gen Test Vectors/gen test vectors/Makefile", "tests/bus-tester-scripts/Gen Test Vectors/gen test vectors/Makefile.netbeans", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/tests/", "tests/bus-tester-scripts/", "copy"),
    (GV, "Software/Bus Test Card/Command sender/tests/", "tests/bus-tester-scripts/", "copy"),
    # ---- embedded cleanup 2026-09-20: current sketch/app at the top, superseded generations under deprecated/
    (GV, "Software/Bus Test Card/Command sender/old/command_sender_[23]/Untitled.rtf", "", "drop"),   # 3 identical copies of a 2016 ideas note; one kept
    (C24, "Software-vs/Bus Test Card/Command sender/old/command_sender_[23]/Untitled.rtf", "", "drop"),
    (GV, "Software/Bus Test Card/Command sender/command_sender_5/", "embedded/command-sender/deprecated/command_sender_5/", "copy"),
    (GV, "Software/Bus Test Card/Command sender/command_sender_6/", "embedded/command-sender/deprecated/command_sender_6/", "copy"),
    (GV, "Software/Bus Test Card/Command sender/command_sender_7/", "embedded/command-sender/deprecated/command_sender_7/", "copy"),
    (GV, "Software/Bus Test Card/Command sender/old/", "embedded/command-sender/deprecated/old/", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/command_sender_5/", "embedded/command-sender/deprecated/command_sender_5/", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/command_sender_6/", "embedded/command-sender/deprecated/command_sender_6/", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/command_sender_7/", "embedded/command-sender/deprecated/command_sender_7/", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/old/", "embedded/command-sender/deprecated/old/", "copy"),
    (C24, "Software-vs/Bus Test Card/BUS Driver Commands - Google Docs.pdf", "docs/procedures/", "copy"),   # the command reference is documentation
    (C24, "Software-vs/Bus Test Card/Test EEPROM/", "embedded/sequencer-card/deprecated/test-eeprom-2020-09/", "copy"),   # 'EEPROM connected to the AT328' = the sequencer card's; superseded by the Dec-2020 test
    (C24, "Software/Sequencer Card/Microcode loader send to sequencer/simple_microcode_sender/", "embedded/sequencer-card/deprecated/microcode-loader/simple_microcode_sender/", "copy"),
    (C24, "Software/Sequencer Card/Microcode loader send to sequencer/simple_microcode_sender_2/", "embedded/sequencer-card/deprecated/microcode-loader/simple_microcode_sender_2/", "copy"),
    (GV, "Software/Bus Test Card/Command sender/", "embedded/command-sender/", "copy"),
    (C24, "Software-vs/Bus Test Card/Command sender/", "embedded/command-sender/", "copy"),
    (C24, "Software-vs/Bus Test Card/", "embedded/bus-tester/", "copy"),
    (C20, "Software-vs/Bus Test Card/bus-driver/bus-driver.ino", "embedded/bus-tester/bus-driver-mcp23x17-wip/", "copy"),
    (C24, "Software/Sequencer Card/Sequencer3/", "embedded/sequencer-card/sequencer3/", "copy"),
    (C24, "Software/Sequencer Card/Sequencer2/", "embedded/sequencer-card/deprecated/sequencer2/", "copy"),
    (C24, "Software pre vs/Sequencer Card/Sequencer/download/download.ino", "embedded/sequencer-card/deprecated/sequencer1/", "copy"),   # a tab of the sketch that was filed in a subfolder; Arduino needs it beside Sequencer.ino
    (C24, "Software pre vs/Sequencer Card/Sequencer/", "embedded/sequencer-card/deprecated/sequencer1/", "copy"),
    (C24, "Software/Sequencer Card/Microcode loader send to sequencer/", "embedded/sequencer-card/microcode-loader/", "copy"),
    (C24, "Software/Sequencer Card/Test EEPROM/", "embedded/sequencer-card/test-eeprom/", "copy"),
    (C24, "Software/Sequencer Card/dumpram/", "embedded/sequencer-card/dumpram/", "copy"),
    (GV, "Utilities/clocker/", "embedded/clocker/", "copy"),
    (GV, "Utilities/arduino/", "embedded/libraries/", "copy"),
    # ---------------- docs / media / vm
    (GV, "README.md", "docs/history/readme-2021.md", "copy"),
    (GV, "Status.md", "docs/history/status-2021.md", "copy"),
    (GV, "General Notes/", "docs/history/general-notes/", "copy"),
    (C20, "Other-do-not-git/NOTES Jan 2:17 orig.rtf", "docs/history/", "copy"),
    (C20, "Other-do-not-git/", "docs/references/", "copy"),
    (GV, "Utilities/Waveforms/", "", "skip"),   # Safari webarchives of the WaveDrom editor (600 KB of site JS each, incl. a Google public API key that GitHub flagged); the two diagrams live on as docs/system/waveforms/*.json + .svg, extracted 2026-09-21
    (None, "*Data Sheets/1802 Microprocessor Instructions-1.pdf", "", "drop"),   # second download of the same 5-page sheet
    (GV, "Data Sheets/", "docs/datasheets/", "copy"),
    (GV, "Photos & Videos/", "media/", "copy"),
    (GV, "Presentations/", "docs/history/presentations/", "manifest"),
    (C24, "Required Applications/", "vm/legacy-installers/", "manifest"),
    (C24, "Dear TSA.docx", "", "skip"),
    # ---------------- everything else in the current copies: duplicates of the above, or junk
    (None, "Software-vs/Old-obselete/", "archive/superseded-revisions/software-old-obsolete/", "archive"),
    (None, "Software/Sequencer Card/old & obselete/", "archive/superseded-revisions/sequencer-card-old/", "archive"),
]
# lower-priority "duplicate" rules: the same content from other copies is expected; report only if it differs
DUP_OK_PREFIXES = ["Software", "Software-vs", "Software pre vs", "PCB/", "Utilities/", "Data Sheets/", "Photos & Videos/",
                   "Presentations/", "General Notes/", "mech parts/", "Other-do-not-git/", "README.md", "Status.md",
                   "YACC1-2020 Opcodes - Sheet1-3.pdf", "YACC1 Connector - V3.2.pdf", "pinhead_3row-2.lbr",
                   "oshpark-2layer-auto-routing.dru", "Software-g/", "Required Applications/"]
JUNK = ("*.b#?", "*.s#?", "*.l#?", ".DS_Store", "*.o", "*.dSYM", ".dep.inc", "*.gitattributes", ".gitignore", "*.pyc")
JUNK_DIRS = ("build/", "dist/", "nbproject/private/", ".vscode/", "CAMOutputs 2/", ".git/")
ARCHIVE_SOURCES = {   # ORDER = dedup priority (first holder of a given content keeps it)
    OLD + "YACC1A1": "archive/gen1-2015-2018/YACC1A1/",
    OLD + "YACC1A": "archive/gen1-2015-2018/YACC1A/",
    OLD + "YACC1B": "archive/gen1-2015-2018/YACC1B/",
    OLD + "YACC1-BACKUP": "archive/gen1-2015-2018/YACC1-BACKUP/",
    "YACC1-master": "archive/gen1-2015-2018/YACC1-master-python-2015/",
    OLD + "YACC1-2020 July 2021 backup": "archive/superseded-revisions/snapshot-2021-07/",
    OLD + "YACC1-2020-OLD": "archive/superseded-revisions/snapshot-2021-01-old/",
    OLD + "YACC1-2020-ORIG": "archive/superseded-revisions/snapshot-2020-08-orig/",
    OLD + "YACC1-2020-backup-pre-git-backup": "archive/superseded-revisions/snapshot-2020-08-pre-git/",
}
ARCHIVE_PRIORITY = {sb: i + 2 for i, sb in enumerate(ARCHIVE_SOURCES)}
PROD_DIRS = ("PCB/Production/", "PCB-PRODUCTION/", "/PRODUCTION/", "PCB/yacc1 production/")

# Which revisions were fabricated: tools/fabricated.py (hardware/FABRICATED.md is generated from it)
import importlib.util as _ilu
_spec=_ilu.spec_from_file_location('fabricated', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabricated.py'))
_fab=_ilu.module_from_spec(_spec); _spec.loader.exec_module(_fab)
FABRICATED = {}
for _c,_f,_r,_st,_cf,_n in _fab.FABRICATED:
    if _st == 'in-machine': FABRICATED[_c] = (_r, _n)

# ACTIVE version per card (Ken 2026-09-20). Anything numerically lower is deprecated.
ACTIVE = {"memory": 1.3, "mem-switch": 1.1, "mem-register": 1.0, "bus-tester": 1.1, "video": 1.0, "alu": 3.2, "io": 1.1,
          "register": 1.1, "sequencer-memory": 2.1, "sequencer-logic": 2.1, "backplane": 2.0,
          # not in Ken's list - assumed (only one, or the Production one):
          "protocard": 1.0, "blank-card": 3.1, "bus-template": 3.2,
          "bus-jumper-horizontal": 3.2, "bus-jumper-vertical": 3.0, "address-tmp": 99}   # address-tmp: retired card, everything deprecated
def rev_num(rev):
    m = re.match(r"^v(\d+(?:\.\d+)?)", rev)
    return float(m.group(1)) if m else None

def is_production(src):
    return any(d in "/" + src for d in PROD_DIRS)

EXTRA_SOURCES = {   # other top-level folders under YACCS/ that the index knows about
    "video": ("hardware/cards/video/eagle/v1.0-fusion-export-2026-09-18/", "copy"),   # Fusion 360 export of the REAL video card
    "test":  ("archive/superseded-revisions/test-folder/", "archive"),               # Memory V1.3.txt = copy of the v1.3 .sch
}
RENAMES = {   # (base, file) -> new name in the tree; only where the original name is actively misleading
    ("video", "Blank V3.1.brd"): "Video_1.0.brd",   # the routed video board, exported from Fusion under the template's name; pairs with Video_1.0.sch
}
SHORT = {C20: "YACC1-2020", C24: "YACC1-2024", NG: "newgit", GV: "gitversion"}

SKIP_PREFIXES = [(prefix, mode) for copy, prefix, dest, mode in RULES if mode in ("skip", "drop")]

def is_junk(rel):
    parts = rel.split("/")
    if any(p + "/" in JUNK_DIRS for p in parts[:-1]) or any(rel.count("/" + d) for d in JUNK_DIRS):
        return True
    return any(fnmatch.fnmatch(parts[-1], pat) for pat in JUNK)

def main(index_path, outdir):
    idx = json.load(open(index_path))
    os.makedirs(outdir, exist_ok=True)
    plan = []          # (dest, src, mode, md5)
    claimed = set()
    unclassified = []
    for src, e in sorted(idx.items()):
        base = e["base"]
        if base in CUR:
            rel = os.path.relpath(src, base)
        else:
            rel = None
        if rel is not None:
            if is_junk(rel):
                claimed.add(src); continue
            hit = None
            for copy, prefix, dest, mode in RULES:
                if (copy in (None, "ANY") or copy == base) and (rel == prefix or (prefix.endswith("/") and rel.startswith(prefix)) or (any(c in prefix for c in "*?[") and fnmatch.fnmatch(rel, prefix))):
                    hit = (copy, prefix, dest, mode); break
            if hit:
                copy, prefix, dest, mode = hit
                if prefix.endswith("/"):
                    d = dest + rel[len(prefix):]
                elif dest.endswith("/"):
                    d = dest + os.path.basename(rel)
                else:
                    d = dest
                plan.append((d, src, mode, e["md5"])); claimed.add(src)
            else:
                # is it a duplicate of a claimed path in another copy?
                if any(rel.startswith(pfx) for pfx in DUP_OK_PREFIXES):
                    claimed.add(src)   # evaluated below by content
                else:
                    unclassified.append(src)
        elif base in EXTRA_SOURCES:
            dest, mode = EXTRA_SOURCES[base]
            relx = os.path.relpath(src, base)
            relx = RENAMES.get((base, relx), relx)
            plan.append((dest + relx, src, mode, e["md5"])); claimed.add(src)
        else:
            relb = os.path.relpath(src, base)
            hit = None
            for copy, prefix, dest, mode in RULES:
                isglob = any(c in prefix for c in "*?[")
                if (copy == base or copy == "ANY") and (relb == prefix or (prefix.endswith("/") and relb.startswith(prefix)) or (isglob and fnmatch.fnmatch(relb, prefix))):   # copy 'ANY' = applies to every source incl. the snapshots (None = the four live copies only)
                    hit = (dest + relb[len(prefix):] if prefix.endswith("/") else (dest + os.path.basename(relb) if dest.endswith("/") else dest), mode); break
            if hit and not is_junk(relb):
                plan.append((hit[0], src, hit[1], e["md5"])); claimed.add(src); continue
            relx = relb.split("/", 1)[1] if relb.startswith("YACC1-2020/") else relb    # pre-git backup nests one level deeper
            pm = [mode for pfx, mode in SKIP_PREFIXES if relx == pfx or (pfx.endswith("/") and relx.startswith(pfx)) or (any(c in pfx for c in "*?[") and fnmatch.fnmatch(relx, pfx))]
            if pm:
                plan.append(("", src, pm[0], e["md5"])); claimed.add(src); continue       # same decision (skip or drop) as the live copies
            if fnmatch.fnmatch(relb, "*/CAMOutputs/Assembly/PnP_*.txt"):
                claimed.add(src); continue                                                # pick-and-place exports differ only by timestamp; regenerable
            for sb, dest in ARCHIVE_SOURCES.items():
                if base == sb:
                    if is_junk(os.path.relpath(src, base)):
                        break
                    plan.append((dest + os.path.relpath(src, base), src, "archive", e["md5"])); claimed.add(src); break
    # ---- LAYOUT PASS (Ken 2026-09-20): hardware/<cards|bus>/<card>/eagle/<rev>/...
    #      rev below the ACTIVE version  -> .../eagle/deprecated/<rev>/...
    #      rev == active or newer design -> stays at .../eagle/<rev>/...
    #      fab output (gerber zips/dirs, CAM jobs, drill/photoplot logs, invoices) -> <that rev folder>/fab/X
    #      Eagle BOM exports (.csv, *bom*)                                        -> <that rev folder>/bom/X
    #      (subfolders named old-YACC1 are gen-1 history kept inside the revision folder and are left alone)
    import re as _re
    for i, (d, src, m, hsh) in enumerate(plan):
        mm = _re.match(r"hardware/(cards|bus)/([^/]+)/eagle/([^/]+)/(.+)$", d)
        if m != "copy" or not mm: continue
        kind, card, rev, sub = mm.groups()
        if rev == "deprecated" or "." not in rev and not rev.startswith("v"):
            continue
        if rev_num(rev) is not None and rev_num(rev) < ACTIVE.get(card, 0):
            plan[i] = ("hardware/%s/%s/eagle/deprecated/%s/%s" % (kind, card, rev, sub), src, m, hsh)
    FAB = _re.compile(r"(^|/)(gerbers?|CAMOutputs)(/|\.zip$)|\.(zip|cam|dri|gpi|job|xln|gbr|drd|drl|cmp|sol|st[cs]|pl[cs]|g[tb][lso]|gko)$|invoice", _re.I)
    BOM = _re.compile(r"bom|\.csv$", _re.I)
    moved = []
    for i, (d, src, m, hsh) in enumerate(plan):
        mm = _re.match(r"hardware/(cards|bus)/([^/]+)/eagle(?:/(deprecated/[^/]+|[^/]+))?/(.+)$", d)
        if m != "copy" or not mm or "old-YACC1/" in d: continue
        kind, card, rev, sub = mm.groups()
        if sub.startswith(("fab/", "bom/")): continue
        base = "hardware/%s/%s/eagle%s" % (kind, card, ("/" + rev) if rev else "")
        if FAB.search(sub):
            nd = "%s/fab/%s" % (base, sub)
        elif BOM.search(sub):
            nd = "%s/bom/%s" % (base, sub)
        else:
            continue
        plan[i] = (nd, src, m, hsh); moved.append((d, nd))
    # ---- inside a fab/ folder, files whose bytes are already inside a zip in that same folder are dropped (the zip that
    #      was sent to the board house is the record; its extraction beside it is a duplicate). Verified by hashing zip entries.
    import zipfile, hashlib as _hl
    fabzips = {}
    for d, src, m, h in plan:
        if m == "copy" and "/fab/" in d and d.lower().endswith(".zip"):
            fabzips.setdefault(os.path.dirname(d), []).append(src)
    unzipped = 0
    if fabzips:
        zip_md5 = {}
        for fabdir, zips in fabzips.items():
            entries = set()
            for zsrc in zips:
                zp = zsrc if os.path.isabs(zsrc) else os.path.join(SRC_ROOT, zsrc)
                try:
                    with zipfile.ZipFile(zp) as zf:
                        for n in zf.namelist():
                            if not n.endswith("/"): entries.add(_hl.md5(zf.read(n)).hexdigest())
                except Exception: pass
            zip_md5[fabdir] = entries
        for i, (d, src, m, h) in enumerate(plan):
            if m == "copy" and "/fab/" in d and not d.lower().endswith(".zip"):
                fabdir = d[:d.index("/fab/") + 4]
                if h in zip_md5.get(fabdir, ()):
                    plan[i] = ("", src, "skip", h); unzipped += 1     # 'skip': an extraction of a kept zip is a duplicate wherever it turns up
    # ---- portable names: ':' is illegal on Windows and trailing spaces in folder names break tools; sanitise destinations
    def portable(d):
        return "/".join(c.rstrip(" ").replace(":", "-") for c in d.split("/"))
    plan = [(portable(d), src, m, h) for d, src, m, h in plan]
    # ---- content deliberately skipped in the live copies must not resurface from a snapshot under another path
    skipped_md5 = {h for d, src, m, h in plan if m == "skip"}          # 'drop' rows deliberately excluded
    resurfaced = 0
    for i, (d, src, m, h) in enumerate(plan):
        if m == "archive" and h in skipped_md5:
            plan[i] = ("", src, "skip", h); resurfaced += 1
    # ---- same relative path across the four current copies with different content (whatever the rules say)
    rel_versions = collections.defaultdict(dict)
    for src, e in idx.items():
        if e["base"] in CUR:
            rel = os.path.relpath(src, e["base"])
            if not is_junk(rel):
                rel_versions[rel][e["base"]] = (e["md5"], e["size"], e["mtime"])
    rel_conf = {r: v for r, v in rel_versions.items() if len({h for h, _, _ in v.values()}) > 1}
    copied_md5 = {h for d, s_, m, h in plan if m == "copy"}
    losers = 0
    for r, v in rel_conf.items():
        seen = set()
        for b, (h, sz, mt) in sorted(v.items(), key=lambda kv: -kv[1][2]):
            if h in copied_md5 or h in seen: continue
            seen.add(h); losers += 1
            plan.append(("archive/conflict-losers/%s/%s" % (SHORT[b], r), b + "/" + r, "archive", h))
    # ---- DEDUP by content: never copy the same bytes twice into archive/
    def prio(entry):
        d, src, m, h = entry
        if m in ("copy", "manifest"): return 0
        return ARCHIVE_PRIORITY.get(idx[src]["base"], 1)   # rule-based archive from CUR = 1
    holder = {}            # md5 -> destination that will hold these bytes
    dropped = []           # (source, kept destination, would-have-been destination)
    kept = []
    copy_dups = collections.defaultdict(list)   # md5 -> copy destinations (reported, never dropped)
    seen_copy = set()
    skipped_rows = [e for e in plan if e[2] in ("skip", "drop")]   # classification only: never copied, never dedup'd, never 'restored'
    plan = [e for e in plan if e[2] not in ("skip", "drop")]
    for entry in sorted(plan, key=lambda e: (prio(e), e[0])):
        d, src, m, h = entry
        if m == "copy":
            if (d, h) in seen_copy: continue
            seen_copy.add((d, h))
            copy_dups[h].append(d)
            holder.setdefault(h, d); kept.append(entry); continue
        if m == "manifest" or h.startswith(("big", "dataless")) or idx[src]["size"] == 0:
            holder.setdefault(h, d); kept.append(entry); continue
        if h in holder:
            dropped.append((src, holder[h], d))
        else:
            holder[h] = d; kept.append(entry)
    # Eagle project folders stay whole: if a .sch/.brd was dropped but its twin (same stem) is kept in
    # the same destination folder, put it back (an Eagle project with only half its files is useless).
    kept_keys = {(os.path.dirname(d), os.path.basename(d)) for d, _, _, _ in kept}
    restored = []
    for src, kept_at, d in list(dropped):
        stem, ext = os.path.splitext(d)
        if ext.lower() in (".sch", ".brd"):
            twin = stem + (".brd" if ext.lower() == ".sch" else ".sch")
            for cand in (twin, twin.upper(), twin.lower()):
                if (os.path.dirname(cand), os.path.basename(cand)) in kept_keys:
                    kept.append((d, src, "archive", idx[src]["md5"])); restored.append((src, kept_at, d)); break
    for r in restored: dropped.remove(r)
    # No LFS, GitHub refuses files > 100 MB and warns > 50 MB: anything that big is manifest-only
    BIG = 50e6
    kept = [(d, src, ("manifest" if (m in ("copy", "archive") and idx[src]["size"] > BIG) else m), h) for d, src, m, h in kept]
    plan_full = plan
    plan = kept + skipped_rows
    copy_dups = {h: v for h, v in copy_dups.items() if len(v) > 1}
    dropped_bytes = sum(idx[s]["size"] for s, _, _ in dropped)
    dropped_pairs = sum(1 for s, _, _ in dropped if s.lower().endswith((".sch", ".brd")))
    # ---- PRODUCTION: which board folders sit under a production directory
    prod = collections.defaultdict(lambda: collections.defaultdict(set))   # board folder -> base -> {dest area}
    for d, src, m, h in plan_full:
        if is_production(src):
            parts = src.split("/")
            for i, pp in enumerate(parts[:-1]):
                if any(pp == x.strip("/").split("/")[-1] for x in PROD_DIRS) and i + 1 < len(parts) - 1:
                    prod[parts[i + 1]][idx[src]["base"]].add(("%s: %s" % (m, "/".join(d.split("/")[:4]))))
                    break
    # ---- conflicts: same destination from different sources with different content
    by_dest = collections.defaultdict(dict)
    for d, s, m, h in plan:
        if m in ("skip", "drop"): continue          # skip/drop rows share the empty destination; nothing is written for them
        by_dest[d][s] = h
    conflicts = {d: v for d, v in by_dest.items() if len(set(v.values())) > 1}
    # ---- same basename, different content, anywhere in the tree
    by_name = collections.defaultdict(dict)
    for src, e in idx.items():
        if is_junk(src) or e["md5"].startswith(("big", "dataless")):
            continue
        by_name[e["name"]].setdefault(e["md5"], []).append(src)
    name_conf = {n: v for n, v in by_name.items() if len(v) > 1}
    # ---- reports
    dests = collections.Counter(); modes = collections.Counter(); size = collections.Counter()
    for d, s, m, h in plan:
        dests[d.split("/")[0] + ("/" + d.split("/")[1] if d.count("/") else "")] += 1; modes[m] += 1; size[m] += idx[s]["size"]
    with open(os.path.join(outdir, "dryrun-summary.txt"), "w") as f:
        f.write("DRY RUN %s  (nothing written)\n\n" % time.strftime("%Y-%m-%d %H:%M"))
        f.write("planned files by mode: %s\n" % dict(modes))
        f.write("planned bytes by mode: %s\n\n" % {k: "%.1f MB" % (v / 1e6) for k, v in size.items()})
        f.write("planned files by destination area:\n")
        for d, n in sorted(dests.items()): f.write("  %5d  %s\n" % (n, d))
        f.write("\ndedup: %d archive files NOT copied because identical bytes already go elsewhere (%.1f MB saved; %d of them are .sch/.brd)\n"
                % (len(dropped), dropped_bytes / 1e6, dropped_pairs))
        f.write("dedup: %d Eagle .sch/.brd files restored so no archive project folder loses half its pair\n" % len(restored))
        f.write("dedup: %d distinct contents appear at more than one copy destination (kept, see copy-duplicates.txt)\n" % len(copy_dups))
        f.write("fab output / BOM files routed into <rev>/fab and <rev>/bom: %d\n" % len(moved))
        f.write("archive files dropped because their bytes were deliberately skipped in the live copies: %d\n" % resurfaced)
        f.write("fab files dropped because a zip in the same fab/ folder already contains them: %d\n" % unzipped)
        f.write("\nunclassified files in the four current copies: %d\n" % len(unclassified))
        f.write("destination conflicts (same target, different content): %d\n" % len(conflicts))
        f.write("same relative path, different content across the four current copies: %d (newest copied; %d losing versions archived under archive/conflict-losers/)\n" % (len(rel_conf), losers))
        f.write("same file NAME with more than one distinct content anywhere in the tree: %d names\n" % len(name_conf))
    with open(os.path.join(outdir, "dryrun-plan.tsv"), "w") as f:
        f.write("mode\tdestination\tsource\tmd5\n")
        for d, s, m, h in sorted(plan): f.write("%s\t%s\t%s\t%s\n" % (m, d, s, h))
    with open(os.path.join(outdir, "dedup-dropped.tsv"), "w") as f:
        f.write("source\tsame bytes kept at\twould have gone to\n")
        for row in sorted(dropped): f.write("%s\t%s\t%s\n" % row)
    with open(os.path.join(outdir, "copy-duplicates.txt"), "w") as f:
        for h, v in sorted(copy_dups.items(), key=lambda kv: kv[1]):
            f.write("%s\n" % h[:8]); [f.write("    %s\n" % d) for d in v]
    with open(os.path.join(outdir, "production-boards.txt"), "w") as f:
        f.write("IN-MACHINE revision per card (from tools/fabricated.py; full table = hardware/FABRICATED.md):\n")
        for c, (rev, note) in sorted(FABRICATED.items()): f.write("    %-24s %-6s %s\n" % (c, rev, note))
        f.write("\nBoard folders found under a production directory (folder -> per source copy: mode and destination area)\n\n")
        for b in sorted(prod, key=str.lower):
            f.write("%s\n" % b)
            for base, areas in sorted(prod[b].items()):
                f.write("    %-45s %s\n" % (base, "; ".join(sorted(areas))))
    with open(os.path.join(outdir, "unclassified.txt"), "w") as f:
        f.write("\n".join(sorted(unclassified)) + "\n")
    with open(os.path.join(outdir, "conflicts-destination.txt"), "w") as f:
        for d in sorted(conflicts):
            f.write("%s\n" % d)
            for s, h in sorted(conflicts[d].items()):
                e = idx[s]; f.write("    %s  %8d  %s  %s\n" % (h[:8], e["size"], time.strftime("%Y-%m-%d", time.localtime(e["mtime"])), s))
    with open(os.path.join(outdir, "conflicts-relative-path.txt"), "w") as f:
        for r in sorted(rel_conf):
            f.write("%s\n" % r)
            for b, (h, sz, mt) in sorted(rel_conf[r].items(), key=lambda kv: -kv[1][2]):
                f.write("    %s  %8d  %s  %s\n" % (h[:8], sz, time.strftime("%Y-%m-%d", time.localtime(mt)), b))
    with open(os.path.join(outdir, "same-name-different-content.txt"), "w") as f:
        for n in sorted(name_conf, key=str.lower):
            f.write("%s   (%d distinct contents)\n" % (n, len(name_conf[n])))
            for h, paths in sorted(name_conf[n].items(), key=lambda kv: -max(idx[p]["mtime"] for p in kv[1])):
                p0 = max(paths, key=lambda p: idx[p]["mtime"]); e = idx[p0]
                f.write("    %s  %9d  %s  %s%s\n" % (h[:8], e["size"], time.strftime("%Y-%m-%d", time.localtime(e["mtime"])), p0,
                                                    ("  (+%d identical copies)" % (len(paths) - 1)) if len(paths) > 1 else ""))
    print(open(os.path.join(outdir, "dryrun-summary.txt")).read())

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
