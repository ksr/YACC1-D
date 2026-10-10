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
`BAUD` define (19200; busdrv.py and the Processing sender must match). **Flashed to the card 2026-09-21** (arduino-cli, Uno, 115200 through the FTDI); the previous flash - the 2020 bus-driver - was read out first to `readback/`.

## bus-stepper (2026-10-10)

The card as a single-step clock for the sequencer that reads the whole bus after every edge: IC6 GPA4 (the OUT-LED pin,
which only drives the card's own LED through R16) becomes the clock output, jumpered to the sequencer's JP4 pin 2
(EXTERNAL-SINGLESTEP-CLK, SS-SEL on 2-3); with the sequencer's SS/WAIT toggle on FREERUN the machine runs from its
oscillator, on SS from the tester. 115200 baud; commands `p`, `t`, `nN`, `qN`, `l0|1`, `fAAAA,BB[,M]` (step until the
opcode BB is fetched from AAAA) - the sketch's header has the details. `tools/busstep.py` sends them and decodes each
line (address, data, the register-select fields, the asserted strobes). Built to single-step POPR, which loads wrong
values at 1 MHz and right ones at 6 MHz (`tests/bench/diag/poprloop.asm`, `BACKLOG.md`). Flash with `arduino-cli
compile --fqbn arduino:avr:uno --libraries embedded/libraries -u -p /dev/cu.usbserial-AB6WZCQX
embedded/bus-tester/bus-stepper`; back to listening with the saved bus-monitor image (`readback/`).
