# video-ps2 — the PS/2 keyboard and mouse controller of the video card V2.0

The firmware of the ATmega328P on the video card V2.0 (`hardware/cards/video/kicad/v2.0`, design note in `BACKLOG.md`
"Video card V2.0", theory in `docs/cards/video.md`). Designed 2026-10-22; the card is not built, so the sketch has run
on no hardware yet. `tools/verify_embedded.py` compiles it with every other sketch (`make check`): 5,500 bytes of flash,
470 bytes of RAM (Arduino Uno target = the ATmega328P at 16 MHz).

## What it does

Two PS/2 ports, both received under interrupt (the clock lines are on INT0 and INT1): 11-bit frames, odd parity, a
2 ms gap restarts a broken frame. Host-to-device commands (the keyboard LEDs, the resets, the mouse's enable) use the
standard request-to-send: clock low 120 us, data low, then one bit per device clock and the device's acknowledge.

- **Keyboard**: scan code set 2 to ASCII. Shift, Caps Lock (with its LED), Ctrl (Ctrl-letter = $01-$1A), Num Lock and
  the keypad (digits with Num Lock, the editing keys without), Enter = CR ($0D), Backspace = $08, Tab, Esc, Delete
  = $7F, the arrows / Home / End / Page Up / Page Down as VT100 sequences (ESC `[A`..`[D`, `[H`, `[F`, `[5~`, `[6~`).
  Break codes ($F0) end a key; the extended prefix ($E0) is honoured; Pause ($E1 ...) and Print Screen are swallowed.
  Function keys and Alt give nothing.
- **Mouse**: at start (and on command $04) reset ($FF -> $FA $AA $00) and enable data reporting ($F4). Its 3-byte
  packets (byte 1: buttons, signs, overflows, bit 3 always 1; byte 2: X movement; byte 3: Y movement) are queued whole,
  never interleaved with keyboard bytes; a byte 1 without bit 3 resynchronises.
- **One queue to the CPU** (64 bytes), each byte tagged keyboard or mouse.

## The bus interface (latches on the card; the CPU never waits for the ATmega)

| Port | CPU | Card | Firmware |
|---|---|---|---|
| **IN PE** | the next byte | a 74LS374 the firmware loads: MD0..7, then a rising edge on LDDATA (PD6), which also sets **FULL** (a 74LS74); the CPU's read clears FULL (-RD_PE AND -RESET on its CLR) | loads the next byte only when FULL (PB2) reads 0 twice, 5 us apart (a read strobe holds FULL clear while it lasts), with SRC (PB3) set first; reloads if FULL did not set |
| **IN PD** | status: bit 0 FULL, 1 SRC (0 keyboard, 1 mouse), 2 BUSY, 7..3 = 0 | a 74LS244 | SRC is a pin |
| **OUT PD** | a command | a 74LS374 latches DATA0..7 on the strobe's rising edge and sets **BUSY** (74LS74) | sees BUSY (PB5), pulls -RDCMD (PD7) low: the latch drives MD0..7 and BUSY clears |

The local bus MD0..7 is PC0-PC5 and PB0, PB1 (PD0/PD1 stay the serial port, PD2/PD3 the PS/2 clocks).

**Commands** (OUT PD): `$01` interrupts on, `$02` off, `$03` acknowledge (-INT released until the next byte), `$04`
mouse on (reset + enable reporting), `$05` mouse off, `$06` flush both queues, `$07` keyboard reset, `$10`-`$17`
keyboard LEDs (bit 0 Scroll, 1 Num, 2 Caps Lock), `$FE` debug output on the FTDI console on/off, `$FF` start again.

**INT**: INTREQ (PB4) = interrupts on AND not acknowledged AND FULL. It drives the bus -INT (C13) through IC27/D (7416,
open collector) and jumper **JP3 INT-EN**: with the jumper off the card never touches -INT. Reading PE clears FULL, so
-INT goes away with the last waiting byte and comes back with the next. A handler reads PD first: FULL = 0 means the
interrupt came from another card (the I/O card's UART shares -INT).

## Reading the keyboard from a program

```
wait:  INP PD        ; status
       ANDI 01h      ; FULL?
       BRZ wait
       INP PD        ; again: bit 1 says keyboard (0) or mouse (1)
       ...
       INP PE        ; the byte (clears FULL)
```

## Pins

| ATmega328P | Arduino | Net | |
|---|---|---|---|
| PD0, PD1 | D0, D1 | FTX, FRX | the FTDI header J4 (38400 8N1 debug console, the bootloader) |
| PD2 (INT0) | D2 | KCLK | keyboard clock, J2 pin 5 |
| PD3 (INT1) | D3 | MCLK | mouse clock, J3 pin 5 |
| PD4 | D4 | KDAT | keyboard data, J2 pin 1 |
| PD5 | D5 | MDAT | mouse data, J3 pin 1 |
| PD6 | D6 | LDDATA | data latch clock + FULL set |
| PD7 | D7 | -RDCMD | command latch output enable + BUSY clear |
| PC0-PC5, PB0, PB1 | A0-A5, D8, D9 | MD0-MD7 | the local bus |
| PB2 | D10 | FULL | in |
| PB3 | D11 | SRC | out |
| PB4 | D12 | INTREQ | out |
| PB5 | D13 | BUSY | in |
| RESET | | MRST | 10k pull-up; 100 nF from the FTDI DTR; 1N4148 to the bus -RESET (a bus reset restarts the firmware) |

Flash it through the FTDI header (Optiboot, as an Uno): `arduino-cli compile --fqbn arduino:avr:uno --libraries
embedded/libraries -u -p /dev/cu.usbserial-XXXX embedded/video-ps2`. A blank ATmega328P needs the Uno bootloader
burned once with an ISP programmer (there is no ISP header on the card: burn it before fitting).
