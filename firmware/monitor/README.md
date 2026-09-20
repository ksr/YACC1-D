# firmware/monitor

`monitor.asm` — the YACC1 monitor as burned (git ff7d85a, 2021-07-09), with its `.img` (assembled with `software/assembler`,
reproducible: `tools/verify_firmware.py`) and `.lst`. Lives at $F000; BIOS entry vectors at $FFC0.
- `candidates/2021-09-8afde21/` — 2021-08-31/09-03: adds a `charavail` BIOS vector ($FFEC, UART data-ready) so a
  running BASIC program can be interrupted; never burned, needs a hardware test.
- `candidates/2021-09-02-3bcacf3-not-working/` — git master HEAD, marked "not working needs revert": only comments
  out a debug dump block (ROM overflowed); its `.img/.lst` and the resulting `rom/builds/...` are kept for the record.
- `monnew-2025/` — `monnew.asm` (2025-03-14), a small fresh monitor (D display / M modify / B block) assembled with the
  2025 `yacc1.def` (lowercase `equ`) that is now `software/assembler/yacc1.def`.
