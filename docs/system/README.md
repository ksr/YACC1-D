# docs/system

- `MACHINE.md` — **what is physically in the machine and what is loaded into it** (2026-09-20), with the items still to confirm.

- `connector/` — the bus pinout/signal spec, all four versions, V3.2 canonical; which card used which (README there).
- `YACC1-2020 Opcodes - Sheet1-3.pdf` — the opcode table (2023-11-03 export); machine-readable = `software/opcodes.h`,
  assembler syntax = `software/assembler/yacc1.def`.
- `waveforms/` — `REG-LD` / `REG-RD` index-register load/read timing diagrams (2020-08, WaveDrom: `.json` source + `.svg`).
- To write: architecture overview, memory map (facts: memory card README), microcode word format
  (`firmware/microcode/yaccsignaldefine.h`), boot/remap, BIOS ABI (`firmware/abi/`).
