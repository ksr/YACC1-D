# docs/procedures

System build order, EEPROM programming, microcode loading, bus-tester usage (from BUS Driver Commands + build notes).

| File | Contents |
|---|---|
| `BRING-UP.md` | the bench procedure book (written 2026-09-23 from the tree): power and reset, the clock, jumpers per card, loading the microcode (`tools/ucode_send.py`), burning the ROM and telling the 2021 chip from the 2026 image, the ROM test programs (`ledcount`, `romcount`, `romdiag`, `brur`), the bus tester (protocol, script language, script library, the Python bench tests), reading a sequencer boot transcript, the video card checks, and a symptom -> what-to-scope table from the design review |
| `TESTING.md` | the complete test inventory (written 2026-09-23): every test under `tests/`, the root `make check`, the `tools/verify_*.py` / `audit_tree.py` / `gen_bom.py --check` tools, the emulators' scripted modes, and what the machine has proven on the bench so far |
| `System Build Notes.md` (+ `.rtf`) | Ken's 2025 build order for the boards (the .rtf is the original) |
| `BUS Driver Commands - Google Docs.pdf` | the bus-tester script language as sent by `embedded/command-sender` (LET/FOR/NEXT, labels, expected values, DUMP) |

_The PDF and the build notes were migrated 2026-09-19; MIGRATION.md at the repo root says which copy each item came from._
| `CF-CARD.md` | putting Y1/OS on a real CompactFlash card from the Mac (`tools/cfcard.py`), reading one back, safety (2026-09-23) |
