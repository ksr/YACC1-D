# tests/assembler

- `yacc1test.asm` (2020-10-31) – the CPU test program assembled with `software/assembler` and run through the
  bus tester / emulator during bring-up; `test_output.txt` – a 2026-05-26 run.
- `history-2020/` – 15 dated snapshots of that program from 2020-08-26 to 2020-10-20 (serial-out, ROM, RAM,
  push/pop, ring-shift, "major test"...), the record of how bring-up progressed. `yacc1testorig.asm` (2017) is the
  gen-1 original.
- `ledcount/` – the 16-byte switch-ROM LED counter (2026-09-21); `brur/` – the BRUR $AD test (2026-09-22, emulator: `ABC0123`).
