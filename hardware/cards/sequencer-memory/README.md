# cards/sequencer-memory — Sequencer (memory half)

Holds the microcode: 64 steps x 8 bytes per opcode in EEPROM/RAM (IC9 is the EEPROM socket – see
`accessories/eeprom-adaptor/` for the larger-EEPROM adaptor) loaded by the on-card ATmega328 from
`embedded/sequencer-card/` (Sequencer3.ino); the microcode image itself comes from `firmware/microcode/`.

- `eagle/v2.1/` – **the built card (2020-12-01)**; CAM output in `fab/`, BOM export in `bom/`.
- `eagle/deprecated/v2.0/` – 2020-07-25, built, retired 2021-01 (V2.1 reworked the ATmega section and jumpers).
- `accessories/eeprom-adaptor/` – plugs into IC9 to take a larger EEPROM (OSH Park invoice in its `fab/`).
- Gen-1 (2016) SEQUENCER-MEMORY-Prod-V1.0 files that used to sit in `old-YACC1/` subfolders here are
  byte-identical to `archive/gen1-2015-2018/` and were dropped from the card folders 2026-09-20.
