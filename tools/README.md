# tools

Host scripts: busdrv.py (bus-tester client), alias_min.py, ROM capture/compare, inventory.py, the migration and audit tools,
the PDF generators, and the KiCad conversion:

- `eagle_to_kicad_all.py` — converts EVERY Eagle design under hardware/ into `<item>/kicad/<rev>/` KiCad 10 projects and
  writes `hardware/KICAD.md`; per design it runs the three tools in `kicad/` (`eagle_sch_to_kicad.py` schematic converter,
  `finish_board.py` board finisher on KiCad's Eagle board import, `compare_netlists.py` schematic-vs-board proof), then ERC,
  DRC, a schematic PDF and board renders into `reports/`. `kicad/project-template.kicad_pro` carries the OSH Park rules.
- `verify_processing.py` — builds the Processing command sender with the Processing 4 CLI and re-compiles it with warnings on.

_Contents migrated 2026-09-19; MIGRATION.md at the repo root says which copy each item came from._

## Already here (written during the 2026-09 bring-up session; they existed nowhere else)

- `busdrv.py` — Python client for the Bus Test Card (19200 baud, `CMD:OPERAND#`); readmem/writemem/dump helpers
- `alias_min.py` — minimal reproduction of the video card block-0/9 write-through fault
- `inventory.py` — hashes every file under YACCS and reports what is unique where (used to build MIGRATION.md)

`../firmware/rom/eprom-captured-2026-09-18.{bin,hex}` is the 8K image read out of the memory card's
28C64 through the bus tester; it is byte-identical to `Software-vs/Assembler/rom` (git ff7d85a).
