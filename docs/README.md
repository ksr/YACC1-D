# docs

Start with `system/ARCHITECTURE.md`; `DOC-PLAN.md` says how the 2026-09-23 documents were written and what **To verify:** means in them.

| Folder | Contents |
|---|---|
| `isa/` | GENERATED timing diagram per opcode from the microcode (`make isa`, `tools/ucode_wavedrom.py`): control levels per step + bus behaviour from an assumed LS timing model; index in its README |
| `system/` | **`ARCHITECTURE.md`, `MICROCODE.md`, `BUS.md`** (2026-09-23: the machine, the control store, the backplane), `MACHINE.md` (what is fitted), `OS-PLAN.md`, the bus connector specs (`connector/`), the opcode table PDF (2023-11), index-register timing diagrams (`waveforms/`) |
| `cards/` | one theory-of-operation per card (2026-09-23): purpose, bus signals, IC-by-IC schematic walkthrough, timing and review findings, jumpers, bring-up, history; index in its README |
| `programming/` | the programmer's guides (2026-09-23): ISA reference, assembler, C compiler, monitor/BIOS, Y1/OS, memory map, I/O ports, emulators, tool chain |
| `bom/` | GENERATED bills of material per board and consolidated (`make bom`, `tools/gen_bom.py`) |
| `procedures/` | `BRING-UP.md` (the bench book, 2026-09-23), `TESTING.md` (every test and what it proves), bus tester command reference (PDF), system build notes |
| `history/` | the 2021 repo front page and status, the PCB folder readme, 2017–2020 design notes, verbatim |
| `datasheets/` | third-party datasheets used by the designs (28 files, ~19 MB; committed as decided) |
| `references/` | external papers |
| `../media/` | photos of the built cards and the system |
