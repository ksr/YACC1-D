# embedded — Arduino / Processing code for the support cards

| Folder | Runs on | Current | Superseded (`deprecated/`) |
|---|---|---|---|
| `bus-tester/` | Bus Test Card v1.1 (ATmega328 + 4 MCP23017) | `bus-driver` (drive the bus, FTDI 19200 – the sketch `tools/busdrv.py` talks to), `bus-monitor` (listen), `bus-test`, `led-switch-test`; `bus-driver-mcp23x17-wip` = 2026-09-18 start of a port to the Adafruit MCP23X17 2.x API (2 lines) | – |
| `command-sender/` | Mac (Processing) | `command_sender_8` (2020-08-16): GUI that sends test scripts to the bus tester; scripts in `tests/bus-tester-scripts/` | `command_sender_5..7`, `old/command_sender..4` (2016-12 → 2020-07), one 2016 ideas note |
| `sequencer-card/` | Sequencer-Memory card ATmega328 | `sequencer3` (2021-08-25, IO.ino edit 2024-07-10: MCP pull-ups off) = the loader firmware in the card; `microcode-loader/simple_microcode_sender_64` (Processing, 115200, reads `firmware/microcode/.../test.hexz`, keeps `cache`); `dumpram`; `test-eeprom` | `sequencer1` (2020-08), `sequencer2` (2020-12), senders 1 and 2 (19200, v1 generator), the Sept-2020 EEPROM test |
| `clocker/` | a spare Arduino | `clocker.ino` – external single-step / slow clock | – |
| `libraries/` | – | VENDORED: `Adafruit_MCP23017_Arduino_Library` 1.1.0 (the 1.x API every sketch here uses), `extEEPROM` 3.4.1 (the deprecated sequencer2 only) and `YACC/YACC_Common_header.h` (the bus signal table the tester sketches include; `-pre3-2.h` = its previous version). Install both in `~/Documents/Arduino/libraries/` | – |

Build check: `tools/verify_embedded.py` compiles every sketch here with arduino-cli (Uno / ATmega328) against ONLY the
vendored `libraries/`; 12 sketches, all compile with zero sketch warnings (`--warnings all`) as of 2026-09-20 except the MCP23X17 work-in-progress, which is expected
(it needs the 2.x Adafruit library). Manual build: copy `libraries/*` into `~/Documents/Arduino/libraries/` and use the IDE. The sequencer sketches carry their own copy of the signal subset
(`YACC_Common_headera.h`, per generation) beside the .ino.
