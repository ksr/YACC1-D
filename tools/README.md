# tools

Host scripts: busdrv.py (bus-tester client), alias_min.py, ROM capture/compare, inventory.py, the migration and audit tools,
the PDF generators, and the KiCad conversion:

- `eagle_to_kicad_all.py` — converts EVERY Eagle design under hardware/ into `<item>/kicad/<rev>/` KiCad 10 projects and
  writes `hardware/KICAD.md`; per design it runs the three tools in `kicad/` (`eagle_sch_to_kicad.py` schematic converter,
  `finish_board.py` board finisher on KiCad's Eagle board import, `compare_netlists.py` schematic-vs-board proof), then ERC,
  DRC, a schematic PDF and board renders into `reports/`. `kicad/project-template.kicad_pro` carries the OSH Park rules.
- `kicad/sch_overlaps.py` — readability check for any `.kicad_sch` (or a folder of them): text over text, text over a
  symbol body, text crossed by a wire/pin/graphic line, and anything off the drawing frame or on the title block, with
  the worst offenders per sheet (`--summary`, `--detail N`, `--pairs N`, `--json`; `--calibrate SVG` checks its text
  boxes against a `kicad-cli sch export svg` render). `eagle_to_kicad_all.py` puts its counts in each README and in
  `hardware/KICAD.md`.
- `verify_fab_vs_brd.py` — proves an Eagle `.brd` is the design a fab house received: every hole against the Excellon
  drill file, every Top/Bottom track against the copper gerbers, inner-layer planes, part list and pick-and-place,
  optionally byte-compares two gerber sets. Takes a gerber zip or a whole order archive (nested zips are searched).
  First used 2026-09-24 on the memory card (`hardware/cards/memory/eagle/v1.3/README.md`).
- `verify_processing.py` — builds the Processing command sender with the Processing 4 CLI and re-compiles it with warnings on.
- `gen_y1_optab.py` — generates `os/asm_optab.c`, the instruction table of the native assembler `/BIN/ASM`, from
  `software/assembler/yacc1.def` (2026-09-25; `os/Makefile` runs it, `--check` fails when the file is stale:
  `tests/asm/run.py`). It compiles each `.def` construction line with a copy of RC/asm's `Translate()`.
- `y1kermit.py` — a small standard Kermit for the Mac side of the console line (2026-09-26): `send FILE...` to
  `/BIN/KERMIT`'s `kermit -r` (or its `-x` server), `receive [DIR]` from `kermit -s`, `get NAME... [DIR]`, `finish` /
  `bye` for the server, `term` (a plain terminal, Ctrl-] quits). The same protocol subset as `/BIN/KERMIT`: short
  packets, window 1, block checks 1-3 (`--check`, 3 by default), control prefixing, repeat counts (`--norpt`),
  8th-bit prefixing only when asked (`--ebq` asks), attribute packets (`--noattr`), text mode (`--text`: LF as CR
  LF). `--port` (default: the one USB serial port that is not the sequencer's FTDI; the port is opened with
  `monload.py`'s `Link`, pyserial), `--baud 38400`, `--maxl` (94), `--time` (the timeout it asks the other side to use,
  10 s), `--timeout` (its own, 20 s), `-q`. Fault injection for the tests: `--corrupt N`, `--drop N`, `--nak N`,
  `--mute N` (the Nth packet of the run damaged, not sent, NAKed, not answered). It prints what it sent and received
  and a summary (packets, retries, NAKs, timeouts, repeats); exit 1 on failure. The fallback when C-Kermit is not at
  hand, and what `tests/kermit/run.py` drives both emulators with; `docs/procedures/KERMIT.md` is the how-to.
- `y1.ksc` — C-Kermit's settings for the same line (`kermit tools/y1.ksc` opens `/dev/cu.usbserial-AB0MVHSQ` at
  38400, no flow control, carrier-watch off, binary, prefixing all, autodownload, and connects;
  `docs/procedures/KERMIT.md` explains each).

_Contents migrated 2026-09-19; MIGRATION.md at the repo root says which copy each item came from._

## Already here (written during the 2026-09 bring-up session; they existed nowhere else)

- `busdrv.py` — Python client for the Bus Test Card (19200 baud, `CMD:OPERAND#`); readmem/writemem/dump helpers
- `alias_min.py` — minimal reproduction of the video card block-0/9 write-through fault
- `inventory.py` — hashes every file under YACCS and reports what is unique where (used to build MIGRATION.md)

`../firmware/rom/eprom-captured-2026-09-18.{bin,hex}` is the 8K image read out of the memory card's
28C64 through the bus tester; it is byte-identical to `Software-vs/Assembler/rom` (git ff7d85a).
