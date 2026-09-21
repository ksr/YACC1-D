# sequencer-card — firmware for the ATmega328 on the sequencer-memory card

- `sequencer4/` — **the firmware in the card (flashed 2026-09-21)**. Sequencer3 with four changes: I2C at 400 kHz (set after
  the expanders' `begin()`, which resets it), the EEPROM read in 32-byte blocks and written in page writes, the test-pattern
  fill removed from the boot, and the whole EEPROM-to-RAM copy read back and compared before READY is raised (on a mismatch
  it reports, blinks FAULT 6 times and never raises READY). Every serial literal is in flash (`F()`): the plain-string
  version crashed at boot because the ATmega had ~500 bytes of RAM left. Measured on the card: copy 16 s, verify 29 s,
  READY 54 s after reset (Sequencer3: 156 s, unverified). Same download protocol and switches as before.
- `deprecated/sequencer3/` — the 2021-08 firmware that was in the card until 2026-09-21 (IO.ino 2024-07-10 turns the
  MCP23017 pull-ups off); still compiles and still works, just slow. Receives the microcode over serial (`download.ino`)
  and writes it to the EEPROM one byte per transaction (`EEPROM.ino`) or the microcode RAM (`uCodeRAM.ino`/`uCodeROM.ino`).
  `YACC_Common_headera.h` = the signal subset it needs.
- `microcode-loader/simple_microcode_sender_64/` — the Processing sender that feeds it (115200 baud): reads
  `firmware/microcode/ucode-generator2/test.hexz`, compares with `cache` (what was sent last) and sends the differences.
- `dumpram/` — diagnostic: dumps the whole microcode RAM (then the EEPROM) over serial, all 256 instructions; a 2024
  copy of the sequencer3 sources with a different `loop()`. Sequencer4's verify pass covers its usual purpose.
- `deprecated/` — also `test-eeprom-2020-12` (Dec-2020 bench test of the card's I2C EEPROM at $57, the socket the EEPROM
  adaptor plugs into), `sequencer1` (Aug 2020, for the V2.0 cards; its `download.ino` tab was filed in a subfolder in the old tree and is now beside the sketch) and `sequencer2` (Dec 2020), the 19200-baud senders for
  the v1 generator's 32-step format, and the Sept-2020 EEPROM test that was filed under the bus tester.

Flash read-out of the card's ATmega328P, 2026-09-21 (`readback/`, with the restore command): a Sequencer3 build (identical
message strings to a build of `deprecated/sequencer3`; older compiler, 13,290 vs 11,186 bytes today). Re-flashed from the tree
the same day (byte-identical read-back), then replaced by `sequencer4` (see `tests/sequencer/` for the boot transcripts).

Run-mode boots captured 2026-09-21 (`tests/sequencer/`): with the bus tester still asserting -BUS-EN the RAM dumps were all
zero (the logic card drove the address lines; every write hit address 0); with bus-monitor on the tester and the bus quiet,
RAM == EEPROM == `firmware/microcode/ucode-generator2/test.hex` for every dumped instruction. The EEPROM holds the tree's
microcode.
