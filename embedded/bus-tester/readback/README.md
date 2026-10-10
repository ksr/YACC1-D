# embedded/bus-tester/readback — flash read out of the bus tester's ATmega328P

`bus-tester-flash-2026-09-21.hex` is the whole 32K flash as read through the Arduino bootloader on 2026-09-21 (Intel hex, unused
bytes $FF). It is the 2020 bus-driver build; replaced 2026-09-21 by blocks-1 from bus-tester/bus-driver.

`bus-tester-flash-2026-10-09-bus-monitor.hex` is the flash as found on 2026-10-09: the card had been switched to the
listening sketch (bus-monitor: it prints `Setup Start` / `Setup Done` and a status line, no `>>` prompt). Read out the
same way, then replaced by blocks-1 from `bus-tester/bus-driver` (`arduino-cli compile/upload --fqbn
arduino:avr:uno`, 12,710 bytes; the card answers `bus-driver blocks-1 2026-09-21`).

Read with:
```
AVR=$(ls -d ~/Library/Arduino15/packages/arduino/tools/avrdude/*/bin/avrdude | tail -1)
CONF=$(ls ~/Library/Arduino15/packages/arduino/tools/avrdude/*/etc/avrdude.conf | tail -1)
$AVR -C $CONF -p atmega328p -c arduino -P /dev/cu.usbserial-AB6WZCQX -b 115200 -U flash:r:bus-tester-flash-2026-09-21.hex:i
```

**Restore** (puts this exact binary back; the bootloader itself is not touched, it is what does the writing):
```
$AVR -C $CONF -p atmega328p -c arduino -P /dev/cu.usbserial-AB6WZCQX -b 115200 -U flash:w:bus-tester-flash-2026-09-21.hex:i
```
avrdude verifies after writing. The FTDI's DTR resets the chip into the bootloader; if it reports "not in sync",
try again or press reset on the card as the command starts.
