# YACC1-D — the definitive YACC1 tree

**Status (2026-09-28):** the single source of truth for YACC1, on GitHub at `github.com/ksr/YACC1-D`, migrated from
the old `YACCS/` folders on 2026-09-19/20. What is in the machine today: `docs/system/MACHINE.md`; which board
revisions exist and were made: `hardware/FABRICATED.md`; what is open: `BACKLOG.md`.

**Working on it (either of Ken's Macs, and for Claude):** `CLAUDE.md` has the standing rules, the machine facts that
bite, where things are and how to build and test. On a new Mac: clone, `python3 tools/setup_check.py` (which tools are
missing, and the command for each), `make` (the C tools), then `make check`.

## What YACC1 is

YACC1 ("Yet Another Custom CPU") is a hand-built 8-bit TTL computer: an 8-bit accumulator and TMP register, eight
16-bit registers R0-R7, microcoded, on a 96-pin bus. The cards: backplane, a two-board sequencer (logic + microcode
memory), ALU, two index-register cards, memory (RAM, the 8K ROM, TMP registers), I/O (16550 UART console, switches,
LEDs, TIL311s), a 6845 video card in bring-up, and a bus tester for driving the bus by hand.

Around the hardware, all in this tree:

- **Firmware in the machine:** the microcode (a C generator that writes the sequencer's EEPROM image), the monitor
  ROM with its Intel-hex loader, BIOS vectors and video driver, and a Tiny BASIC.
- **Y1/OS:** a disk operating system on CompactFlash (P8XFS), with a shell, redirection and pipes, and some thirty-five
  `/BIN` commands, most ported from P8X, among them `vi`, `sed`, `awk`, `pack` and `kermit`. It exists twice and is kept
  in step: `os/y1os.asm` (the real one) and `os/y1os.c` (its specification).
- **y1cc**, a C compiler for YACC1: a Python reference, a C twin, and nine passes that run under Y1/OS. Together with
  the on-target assembler `/BIN/ASM` they rebuild themselves byte for byte on the emulator (the self-host).
- **Host tools:** the RC/asm assembler, an instruction-level emulator, a microcode-level emulator that steps the real
  EEPROM image through models of the cards, loaders for the ROM monitor and the sequencer card, Kermit, the CF-card
  writer, and the KiCad board tooling.

Before this tree the work was spread over nine overlapping copies under `YACCS/` (Eagle variants, four git clones with
different histories, backups). YACC1-D keeps the *current* version of every board, program, tool, test and document in
one place, with everything superseded kept but frozen. `MIGRATION.md` and `migration/` record where every file came
from.

## The tree

```
YACC1-D/
├── README.md  CLAUDE.md  BACKLOG.md  MIGRATION.md
├── Makefile                  make (the C tools), make check (everything, ~11 min), os-test, cc-test, native-test, ...
├── docs/
│   ├── system/               MACHINE.md (what is built), architecture, memory map, microcode, OS plan
│   ├── isa/                  a timing diagram per instruction, the microcode review
│   ├── cards/                theory of operation, one per card
│   ├── programming/          assembler, monitor, OS, C compiler, emulators, memory map, I/O ports
│   ├── procedures/           bring-up, CF card, testing, Kermit
│   ├── bom/                  bills of material, one per card
│   ├── history/              dated design notes kept verbatim (2016-2021), presentations
│   ├── datasheets/           third-party PDFs the designs use
│   └── references/           external papers and books
├── hardware/
│   ├── bus/                  backplane, bus template, bus jumpers, blank card
│   ├── cards/<card>/         one folder per card (below)
│   ├── libraries/            eagle/: the Eagle .lbr/.dru files the designs use
│   ├── mechanical/           card divider clips, switch template, spacers
│   ├── FABRICATED.md         every revision of every board: built, in the machine, or design only
│   ├── SCHEMATICS.md BOARDS.md   generated indexes of the schematic and board PDFs
│   ├── KICAD.md              the Eagle -> KiCad conversion and its netlist proof
│   └── DESIGN-REVIEW*.md     the 2026-09-21 review of the datapath, control and I/O
├── firmware/                 code that runs INSIDE the machine
│   ├── microcode/            ucode-generator2 (C) -> test.hex, the sequencer EEPROM image
│   ├── monitor/  basic/      monitor.asm, basic.asm (+ candidates never burned)
│   ├── rom/                  shipped/ (the image to burn and what is burned), builds/, captured chips
│   └── abi/                  BIOS vectors, variable and port map (still to be written)
├── os/                       Y1/OS: y1os.asm + y1os.c, commands/ (C), commands-asm/ (asm.asm), lib_*.c,
│                             man/, docs/, Makefile -> os/disk.img
├── software/                 host-side toolchain (runs on the Mac)
│   ├── assembler/            RC/asm + yacc1.def
│   ├── emulator/             instruction-level emulator (the ISA reference)
│   ├── ucemu/                microcode-level emulator (test.hex through models of the cards, CF, video)
│   ├── compiler/             y1cc.py, c/ (y1cc.c and the passes cc1..cc9), lib/
│   ├── disassembler/         disasm2
│   └── ubasic-c/             the C uBASIC the assembly BASIC was ported from
├── embedded/                 Arduino sketches for the support cards, built against libraries/ only
│   ├── sequencer-card/       sequencer4 (the microcode loader in the machine), dumpram, deprecated/
│   ├── bus-tester/           bus-driver, bus-monitor, bus-test, led-switch-test
│   ├── clocker/              external single-step clock
│   ├── command-sender/       Processing host for bus-tester scripts (to be replaced by Python)
│   └── libraries/            vendored: YACC_Common_header.h (bus table), Adafruit_MCP23017 1.1.0
├── tools/                    host scripts: setup_check, verify_firmware/embedded, ucode_send, monload, cfcard,
│                             y1kermit, p8xfs, the KiCad/Eagle tooling, the tree audit
├── tests/                    os, compiler, native (self-host), asm, bench (the machine), monload, kermit,
│                             cfcard, video, sequencer, ucemu, memory, assembler, bus-tester-scripts
├── mk/                       shared make fragments
├── migration/                the 2026-09-19/20 migration's inventory, plan and logs
├── vm/                       manifests of VMs and legacy installers (the images live outside git)
├── media/                    photos of the boards
└── archive/                  frozen, never edited: gen1-2015-2018 (the first YACC1), superseded-revisions,
                              eagle-projects, third-party, conflict-losers (older duplicates from the migration)
```

## Card folder layout (`hardware/cards/<card>/`)

```
<card>/
├── README.md        what the card is, current revision, what is built, open issues
├── kicad/<rev>/     KiCad 10 projects, GENERATED from the Eagle files by tools/eagle_to_kicad_all.py with a
│                    schematic-vs-board netlist proof (hardware/KICAD.md) - except where a MASTER marker says the
│                    KiCad project is hand-maintained and IS the design (memory v2.0, CF v1.0, video v1.1);
│                    those have a build.sh (route with Freerouting, DRC, gerbers, renders, BOM)
├── eagle/<rev>/     the Eagle originals, frozen; the active revision at the top, fab/ (what was sent to the board
│                    house), pdf/ (generated), bom/
│   └── deprecated/  every older revision, same shape
└── docs/            card-specific notes
```

| Card | In the machine | Designed, not built |
|---|---|---|
| backplane | V2.0 (8 slots) | |
| sequencer-logic | v2.1 | v2.2 "CPU off" switch (idea, BACKLOG) |
| sequencer-memory | V2.1 + EEPROM adaptor | |
| alu | V3.2 | |
| register (index registers) | 1.1, two cards (R0-R3, R4-R7) | |
| io | V1.1 | |
| memory | v1.3 | **v2.0**: v1.3 + the CompactFlash interface on P8/P9, finished for fabrication |
| video | V1.0, no 6845 fitted yet | **v1.1** (KiCad master), changes still to make before ordering |
| cf | | v1.0, a separate CF card, superseded by memory v2.0 |
| bus-tester | V1.1 (2016; a bench tool) | V3.1 (2020, never ordered) |
| mem-switch, mem-register | bring-up cards (switch ROM at $0000, 16-byte RAM at $0010), fitted when needed | |
| protocard, address-tmp | built (address-tmp retired) | |

Bus items live under `hardware/bus/`: backplane, bus-template V3.2, bus jumpers (built, obsolete, not fitted), blank
card V3.1 (built) and V3.2 (the template for new cards).

## Conventions

- One authoritative copy of anything. Duplicates were the whole problem.
- Lower-case, hyphenated directory names; no spaces (the Eagle tree's spaces broke scripts repeatedly).
- Binary images (ROM, microcode hex) are committed **with** their source and a script that rebuilds them and
  diffs against the committed file; `make check` does it for all of them.
- Every file is explained: `tools/audit_tree.py` must report 0 unexplained after every commit.
- Files that came from YACCS are edited only with a dated entry in `tools/patched_files.txt`.
- Third-party code and libraries are vendored under a folder that says so, with their licence.
- Anything under `archive/` or `deprecated/` is never edited.
- Every `.rtf` note has a generated Markdown twin beside it (`tools/rtf_to_md.py`).
- No git LFS. Very large binaries (the 142 MB presentation, installers, VM images) live outside git, listed in `vm/`.

## How the migration was settled

- Repo: `~/Developer/YACC1-D` on both Macs (out of iCloud Drive, which corrupts `.git`), on GitHub, no LFS.
- History: started fresh (the first commit is the migration); the old `ksr/YACC1-2020` repo is not grafted in.
- `archive/` is committed (about 186 MB), and so are the datasheets.
- Older board revisions that were built stay with their card under `eagle/deprecated/`;
  `archive/superseded-revisions/` holds designs never built and the old tree's snapshots.
- Monitor and BASIC: the 2026 builds in `firmware/rom/shipped` are current; the 2021 `8afde21` build (ON/OFF, break-in)
  is kept as a candidate, never burned.
- Build environment: every C tool has a plain Makefile (2026-09-20); the NetBeans `nbproject/` folders are kept but
  no longer needed.
