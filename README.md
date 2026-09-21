# YACC1-D — the definitive YACC1 tree

**Status: tree created at ~/Developer/YACC1-D on 2026-09-19. Nothing migrated yet. No git yet. The copy under YACCS/YACC1-D is the retired strawman.**

YACC1 ("Yet Another Custom CPU") is the hand-built TTL computer: a 96-pin bus, a memory card, an
ALU card, register cards, an I/O card, a two-board sequencer, a bus tester, and (in progress) a
6845 video card; plus the microcode, monitor, BASIC, assembler, emulator and the Arduino tooling
that bring it up. Over the years that work spread across nine overlapping copies under `YACCS/`
(three Eagle "Software" variants, four git clones with different histories, eight backups, an empty
2026 skeleton). YACC1-D is meant to be the single place where the *current* version of every board,
program, tool, test and document lives, with everything superseded kept but clearly frozen.

The layout below is derived from a file-by-file inventory of the whole `YACCS/` tree
(`MIGRATION.md` lists, for every item, which copy is the newest and how that was established).

## Prerequisites before any migration

1. **Download the iCloud placeholders.** 2,753 of the 7,566 files under `YACCS/` are iCloud-evicted
   (no data on this Mac): most of the backups, most of `Utilities/Eagle`, the mechanical parts,
   `Required Applications`, and scattered photos and notes. They read as "Operation timed out"
   until downloaded. Select `YACCS` in Finder and choose *Download Now*, then re-run the inventory.
2. **Decide where the repo lives.** A git repository inside iCloud Drive (which `~/Documents` is on
   this Mac) is a known way to corrupt `.git` and is also why files keep getting evicted. Proposal:
   keep `YACC1-D` here only while the structure is settled, then move it to `~/Developer/YACC1-D`
   (next to the P8X tree) before `git init`.
3. **Install git-lfs on every machine that will touch the repo, or avoid LFS entirely.** The 2020
   and 2024 clones are broken today because they use LFS for `.pptx` and git-lfs is not installed.

## The tree

```
YACC1-D/
├── README.md                 this file (becomes the project front page)
├── MIGRATION.md              source → destination map; which copy is authoritative and why
├── docs/                     everything written about the machine (all Markdown going forward)
│   ├── system/               architecture, memory map, ISA/opcode table, bus & connector spec,
│   │                         control signals & microcode format, boot/remap, status, glossary
│   ├── cards/<card>/         theory of operation, build notes, bring-up, jumper tables (one per card)
│   ├── procedures/           system build order, EEPROM programming, microcode load, bus-tester use
│   ├── history/              dated design notes kept verbatim (2016–2021 rtf/txt), presentations
│   ├── datasheets/           third-party PDFs used by the designs
│   └── references/           external papers/books the design drew on
├── hardware/
│   ├── bus/                  the bus is its own thing: backplane, bus template, jumpers, blank card,
│   │                         and the ONE canonical signal/pinout table everything else derives from
│   ├── cards/<card>/         one folder per card (see "Card folder layout")
│   ├── libraries/            shared KiCad symbols/footprints (bus connector, card outline, TTL);
│   │                         eagle/ subfolder keeps the Eagle .lbr/.dru files, deprecated
│   ├── mechanical/           card divider clips, switch template, spacers, layout specs
│   ├── FABRICATED.md         generated index: active/in-machine version per card, what was built, fab files
│   ├── SCHEMATICS.md         generated index of every schematic PDF (active and deprecated)
│   └── NEWER-DESIGNS-vs-ACTIVE.txt  tools/compare_eagle.py report: does each newer-than-active design change anything electrically?
├── firmware/                 code that runs INSIDE the machine
│   ├── monitor/              monitor.asm (+ the 2025 monnew.asm draft)
│   ├── basic/                basic.asm (uBASIC port)
│   ├── rom/                  ROM images: shipped/ (what is burned), builds/, makerom, verify script
│   ├── microcode/            uCode-Generator2 sources, signal table, generated hex, loader format
│   └── abi/                  BIOS entry vectors ($FFC0..), zero-page/variable map, port map
├── software/                 host-side toolchain (runs on the Mac)
│   ├── assembler/            RC/asm + yacc1.def + asm.txt docs; old/ keeps its lineage
│   ├── emulator/             emulator (the reference model of the ISA)
│   ├── disassembler/         disasm2 (and disasm)
│   ├── ubasic-c/             the C uBASIC the asm BASIC was ported from
├── embedded/                 Arduino/Processing code for the support cards
│   ├── bus-tester/           bus-driver, bus-monitor, bus-test, led-switch-test, test-eeprom
│   ├── sequencer-card/       Sequencer3 (current), Sequencer2, Sequencer, downloader, RAM/ROM tests
│   ├── clocker/              external single-step clock
│   ├── command-sender/       Processing host for bus-tester scripts (v8 current, old/ kept)
│   └── libraries/            VENDORED deps: Adafruit_MCP23017 1.1.0, YACC_Common_header.h (bus table)
├── tools/                    host scripts: bus-driver Python client, ROM capture/compare,
│                             Eagle→KiCad converter, netlist proof, board finisher, tree inventory
├── tests/                    test plans, vectors and scripts, by card; hardware findings/logs
├── vm/                       manifests (name, OS, contents, checksum, where stored) for virtual
│                             machines and legacy installers — the images live outside git
├── media/                    photos and videos of the hardware
└── archive/                  frozen, read-only, never edited:
    ├── gen1-2015-2018/       first-generation YACC1: Logisim simulation + 74x library, Python
    │                         assembler/microcode generator, the original ALU/register/SP-PC/
    │                         tester/bus-1.x/sequencer-1.0 boards, Keynote docs, Tiny BASIC ports
    ├── superseded-revisions/ 2020-era board revisions replaced by later ones (ALU 3.0/3.1,
    │                         sequencer 2.0, index registers 1.0/1.1, IO 1.0, memory 1.0–1.2 ...)
    └── eagle-projects/       any Eagle project not attached to a card above (e.g. the LM1881
                              sync converter "video/conv")
```

## Card folder layout (`hardware/cards/<card>/`)

```
<card>/
├── README.md        what the card is, current revision, what is built/in the machine, open issues
├── kicad/           KiCad 10 projects, one per revision (v1.3/, deprecated/v1.2/ ...), GENERATED from the Eagle
│                    files by tools/eagle_to_kicad_all.py with a schematic-vs-board netlist proof (hardware/KICAD.md);
│                    once a card is edited in KiCad it leaves the generator's list and this becomes the design
├── eagle/           the Eagle originals (frozen)
│   ├── v1.3/            the ACTIVE version (the card in the machine) + any newer design never ordered
│   │   ├── fab/         what was sent to the board house (gerber zips, CAM jobs, invoices)
│   │   ├── pdf/         GENERATED schematic + board PDFs (tools/sch_to_pdf.py, tools/brd_to_pdf.py via KiCad); indexes hardware/SCHEMATICS.md, BOARDS.md
│   │   └── bom/         BOM exports
│   └── deprecated/      every version below the active one, same shape (v1.2/, v1.1/ ... each with fab/, bom/)
├── docs/            theory of operation, build notes, bring-up (Markdown; the old .rtf goes to
│                    docs/history until rewritten)
└── bom/             bill of materials per revision
```

Cards: `memory` (v1.3, KiCad conversion already done and proven), `alu` (V3.2), `sequencer-logic` (v2.1), `sequencer-memory` (V2.1), `register` (Index Registers 1.2),
`io` (V1.1), `bus-tester` (V3.11), `video` (V1.0), `mem-switch` (V1.1), `mem-register` (V1.0),
`protocard`; the EEPROM adaptor (plugs into the sequencer-memory card's IC9 for a larger EEPROM) lives under
`sequencer-memory/accessories/eeprom-adaptor/`. Bus items (`backplane` BUS-PROD V2.0, `bus-template` V3.2,
`bus-jumper-horizontal` V3.2, `bus-jumper-vertical` V3.1, `blank-card` V3.1) live under `hardware/bus/`.

## Conventions

- Every `.rtf` note has a generated Markdown twin beside it (`tools/rtf_to_md.py`); the `.rtf` is the original until it is retired.
- Lower-case, hyphenated directory names; no spaces (the Eagle tree's spaces broke scripts repeatedly).
- One authoritative copy of anything. Duplicates were the whole problem.
- Binary images (ROM, microcode hex) are committed **with** the source and a script that rebuilds
  them and diffs against the committed file.
- Third-party code and libraries are vendored under a folder that says so, with their licence.
- Anything under `archive/` is never edited; it can be read, copied out, or deleted, not changed.
- Large binaries (the 142 MB `yacc1.pptx`, the 593 MB installers in `Required Applications`,
  VM images) do **not** go in as plain files: either LFS (only if git-lfs is guaranteed) or an
  external store referenced from `vm/` and `docs/history/`.

## Decisions

Decided 2026-09-19:
- Repo location: `~/Developer/YACC1-D` (beside P8X). This copy under `YACCS/` is the strawman only;
  the real tree is created there when Ken says so, after the iCloud download completes.
- No git LFS. Large binaries (presentation, installers, VM images) live outside git with manifests.

Still open:
7. Build environment: the C tools (assembler, emulator, disassemblers, microcode generator, test-vector
   generator) are NetBeans 8.2 projects and their `nbproject/` definitions are kept beside the sources for that
   reason. Ken intends to move off NetBeans eventually; when that happens the `nbproject/` folders get replaced
   by plain Makefiles (several tools already carry one) and the NetBeans/JDK 8 installers in `vm/` become history.
3. History: start the new repo fresh, and archive `ksr/YACC1-2020` on GitHub read-only; or graft
   the 2020–2021 history in with a subtree merge. Recommendation: fresh, with the old repo archived.
4. Whether datasheets are committed (14–19 MB of third-party PDFs) or listed with URLs.
5. Whether Eagle per-revision history stays with each card (`eagle/vX.Y/`) or all goes to `archive/`.
   Recommendation: the current revision stays with the card; older ones go to
   `archive/superseded-revisions/`.
6. Which of the three monitor/BASIC sources is "current": the burned July-2021 build (ff7d85a) or the
   never-burned August-2021 one with ON/OFF and break-in (8afde21). Recommendation: ship ff7d85a as
   current, keep 8afde21 as a branch/feature to test.
```
