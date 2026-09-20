# tools

Host scripts: busdrv.py (bus-tester client), alias_min.py, ROM capture/compare, eagle_sch_to_kicad.py, compare_netlists.py, finish_board.py, inventory.py.

_Contents migrated 2026-09-19; MIGRATION.md at the repo root says which copy each item came from._

## Already here (written during the 2026-09 bring-up session; they existed nowhere else)

- `busdrv.py` — Python client for the Bus Test Card (19200 baud, `CMD:OPERAND#`); readmem/writemem/dump helpers
- `alias_min.py` — minimal reproduction of the video card block-0/9 write-through fault
- `inventory.py` — hashes every file under YACCS and reports what is unique where (used to build MIGRATION.md)

`../firmware/rom/eprom-captured-2026-09-18.{bin,hex}` is the 8K image read out of the memory card's
28C64 through the bus tester; it is byte-identical to `Software-vs/Assembler/rom` (git ff7d85a).
