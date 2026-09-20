# sequencer-card — firmware for the ATmega328 on the sequencer-memory card

- `sequencer3/` — **the firmware in the card** (Sequencer3.ino 2021-08-25; IO.ino 2024-07-10 turns the MCP23017
  pull-ups off). Receives the microcode over serial (`download.ino`) and writes it to the EEPROM (`EEPROM.ino`) or the
  microcode RAM (`uCodeRAM.ino`/`uCodeROM.ino`). `YACC_Common_headera.h` = the signal subset it needs.
- `microcode-loader/simple_microcode_sender_64/` — the Processing sender that feeds it (115200 baud): reads
  `firmware/microcode/ucode-generator2/test.hexz`, compares with `cache` (what was sent last) and sends the differences.
- `dumpram/` — dumps the microcode RAM back over serial; `test-eeprom/` — Dec-2020 test of the card's I2C EEPROM
  (address $57, the socket the EEPROM adaptor plugs into).
- `deprecated/` — `sequencer1` (Aug 2020, for the V2.0 cards) and `sequencer2` (Dec 2020), the 19200-baud senders for
  the v1 generator's 32-step format, and the Sept-2020 EEPROM test that was filed under the bus tester.
