# embedded/sequencer-card/readback — flash read out of the sequencer card's ATmega328P

`sequencer-flash-2026-09-21.hex` is the whole 32K flash as read through the Arduino bootloader on 2026-09-21 (Intel hex, unused
bytes $FF). It is a Sequencer3 build (older avr-gcc), still running on the card.

Read with:
```
AVR=$(ls -d ~/Library/Arduino15/packages/arduino/tools/avrdude/*/bin/avrdude | tail -1)
CONF=$(ls ~/Library/Arduino15/packages/arduino/tools/avrdude/*/etc/avrdude.conf | tail -1)
$AVR -C $CONF -p atmega328p -c arduino -P /dev/cu.usbserial-AB6WZCQX -b 115200 -U flash:r:sequencer-flash-2026-09-21.hex:i
```

**Restore** (puts this exact binary back; the bootloader itself is not touched, it is what does the writing):
```
$AVR -C $CONF -p atmega328p -c arduino -P /dev/cu.usbserial-AB6WZCQX -b 115200 -U flash:w:sequencer-flash-2026-09-21.hex:i
```
avrdude verifies after writing. The FTDI's DTR resets the chip into the bootloader; if it reports "not in sync",
try again or press reset on the card as the command starts.
