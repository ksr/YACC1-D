# docs

| Folder | Contents |
|---|---|
| `isa/` | GENERATED timing diagram per opcode from the microcode (`make isa`, `tools/ucode_wavedrom.py`): control levels per step + bus behaviour from an assumed LS timing model; index in its README |
| `system/` | the bus connector specs (`connector/`), the opcode table PDF (2023-11), index-register timing diagrams (`waveforms/`). Architecture / memory map / microcode format write-ups are still to be written; the facts are in the card READMEs, `firmware/`, and `software/opcodes.h` |
| `cards/` | placeholder for per-card theory-of-operation write-ups; today each card's README under `hardware/cards/<card>/` is the write-up |
| `procedures/` | bus tester command reference (PDF), system build notes; bring-up sequences are in the card folders' `Build Notes.rtf` |
| `history/` | the 2021 repo front page and status, the PCB folder readme, 2017–2020 design notes, verbatim |
| `datasheets/` | third-party datasheets used by the designs (28 files, ~19 MB; committed as decided) |
| `references/` | external papers |
| `../media/` | photos of the built cards and the system |
