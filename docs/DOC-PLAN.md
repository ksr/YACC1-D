# Documentation plan and conventions (started 2026-09-23)

Ken asked for complete hardware documentation of the YACC1: theory of operation, programming guides, bills of
material, procedures. The tree already holds the facts (schematics, card READMEs, the design review, the microcode
generator and its signal tables, the microcode-level emulator, the monitor source, the compiler, the tests); this
work turns them into readable documents. Written from tree commit b77c299 onward.

## Where things go

| Folder | Contents | Written by |
|---|---|---|
| `docs/system/ARCHITECTURE.md` | the machine as a whole: block diagram, datapath, registers, instruction cycle, boot, interrupts, I/O | hand |
| `docs/system/MICROCODE.md` | the control store: format, signal map, sequencing, the generator, adding an instruction, loading the card | hand |
| `docs/system/BUS.md` | the backplane: every signal, who drives it, timing conventions | hand |
| `docs/cards/<card>.md` | one theory-of-operation per card (all cards under `hardware/cards/` and `hardware/bus/`) | hand |
| `docs/programming/*.md` | ISA reference, assembler, C compiler, monitor/BIOS, Y1/OS, memory map, I/O ports, emulators, tool chain | hand |
| `docs/bom/*.md` | bills of material per card + consolidated, **generated** by `tools/gen_bom.py` from the Eagle schematics | generated |
| `docs/procedures/BRING-UP.md`, `TESTING.md` | bench procedures, test inventory | hand |

## Rules for every document

1. **Facts come from the tree, and every section says where.** Schematics (`hardware/cards/<card>/eagle/<active rev>/*.sch`,
   Eagle XML: `<part>` and `<net>/<segment>/<pinref>` are parseable with Python's xml module), card READMEs and Notes,
   `hardware/DESIGN-REVIEW*.md`, `firmware/microcode/` (generator + `yaccsignaldefine.h`/`yaccsignaldata2.h`),
   `software/ucemu/y1ucemu.c` (the hardware model that runs the microcode), `firmware/monitor/monitor.asm`,
   `software/opcodes.h`, `software/assembler/yacc1.def`, `docs/isa/*.json` (per-opcode step timing),
   `docs/system/connector/`, `docs/system/MACHINE.md`, `BACKLOG.md`. Cite paths in the text.
2. **Never invent.** A pinout, a timing figure, a part number or a behaviour that is not in the tree is written as
   **To verify:** with what would settle it. Better a gap than a wrong statement.
3. The active revision of each card is the one in the machine (`docs/system/MACHINE.md`, `hardware/FABRICATED.md`);
   deprecated revisions get a paragraph of history, not a write-up.
4. Explain, do not just list: this is a learning project. Why a circuit is built the way it is, what the
   alternatives were, what went wrong and how it was found. Tables for signals, registers, jumpers, BOM lines;
   ASCII block diagrams are fine; Markdown throughout.
5. Header of every document: title, one-line purpose, `Written 2026-09-23 from the YACC1-D tree`, sources list.
6. Do not edit anything outside your assigned files; do not run git; do not touch `~/Documents/YACCS`.
7. Known findings from the design review (H-1, H-2, H-3, M2, the video 6845 register select, etc.) are stated
   where they belong, with their status on 2026-09-23 (H-1/H-2 fixed in the microcode and loaded; H-3 open; M2 open).
