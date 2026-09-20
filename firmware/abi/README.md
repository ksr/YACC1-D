# firmware/abi

BIOS entry vectors ($FFC0..), monitor/BASIC variable map, I/O port map (derived from the asm headers).

_Contents migrated 2026-09-19; MIGRATION.md at the repo root says which copy each item came from._

Status 2026-09-20: not yet written. Sources of truth: the header comments of `../basic/basic.asm` (BIOS vectors at $FFC0..)
and `../monitor/monitor.asm` (ports, variables), plus `software/opcodes.h` for the ISA.
