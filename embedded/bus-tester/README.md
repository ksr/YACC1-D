Bus Test Card Software

bus-driver
    Command line interface to drive/read bus signals
    see BUS Driver Commands (gdoc) for more information

bus-monitor
    Listens to bus and reports changes

bus-test
    Tests for shorts on bus

led-switch-test
    Simple test of LEDs & Switchs
    Read switches, adds 1, displays on LEDS

Test EEPROM
    Simple test to verify onboard controller can read/write onboard EEPROM chip

BUS Driver commands
    Command format for bus-driver program


---
*YACC1-D note (2026-09-19): the text above is the original Readme.md migrated from `YACC1-2024/Software-vs/Bus Test Card/Readme.md`. Placeholder description from the tree layout:*

# embedded/bus-tester

bus-driver (drive), bus-monitor (listen), bus-test, led-switch-test, test-eeprom. Separate sketches, loaded one at a time.

_Contents migrated 2026-09-19; MIGRATION.md at the repo root says which copy each item came from._

## Block memory commands (bus-driver, 2026-09-21)

The per-byte idiom costs 4 round trips per byte (~0.16 s at 19200 baud, mostly USB latency). `bus-driver.ino` now also
answers `RDBLK:addr,count#` (1–64 bytes back as `Data: hh hh ...`) and `WRBLK:addr,count,hh...#` (1–32 bytes in, 2 hex
digits each): one round trip per block, the same -MEM-RD / -MEM-WR pulses as before, data-bus direction switched by the
card. It prints `bus-driver blocks-1 2026-09-21` before its first prompt; `tools/busdrv.py` looks for `blocks-` in that
banner and uses `read_block()` / `write_block()` (falling back to the per-byte commands on the older firmware, which
would HALT on an unknown opcode - never send RDBLK to it). Block errors reply `Error: ...` without halting. Baud is the
`BAUD` define (19200; busdrv.py and the Processing sender must match). **The card in use still runs the older firmware
until it is re-flashed from this folder** (BACKLOG).
