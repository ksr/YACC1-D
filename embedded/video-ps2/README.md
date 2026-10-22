# video-ps2 — the PS/2 keyboard and mouse controller of the video card V2.0

The firmware of the ATmega328P on the video card V2.0 (`hardware/cards/video/kicad/v2.0`, design note in `BACKLOG.md`
"Video card V2.0", theory in `docs/cards/video.md`). Designed 2026-10-22; the card is not built, so the sketch has run
on no hardware yet. `tools/verify_embedded.py` compiles it with every other sketch (`make check`): 5,618 bytes of flash
(Arduino Uno target = the ATmega328P at 16 MHz).

**Revised 2026-10-22 after the design review** (`hardware/DESIGN-REVIEW-video-v2.0.md`), together with the board:

| Finding | Change |
|---|---|
| V2-1 | **BUSY and SRC swapped**: BUSY is PB3 (D11, ATmega pin 17), SRC is PB5 (D13, pin 19). PB5 is the Uno bootloader's LED pin, which Optiboot drives as an output for about 1.4 s after every external reset; on SRC (an output the firmware drives anyway, read only with FULL) that is harmless, on BUSY it fought IC53's output. |
| V2-3 | `ps2_send()` pulls the clock low first and arms the transmitter (`sending`, the bit counter) only after the 120 us: INT0/INT1 fire on the host's own falling edge, which used to count as the device's first clock, so every command went out one bit late (the mouse never started, the LEDs never changed). The edge now reaches the receive side with the data line high and is ignored. The ISR is the only place the firmware's own edges reach; nothing else drives a clock line. |
| V2-7 | LDDATA idles **high** (a 10k pull-up R22 holds it there through the reset and the bootloader); a byte is loaded with a low pulse, the latch and FULL take its rising edge. RDCMD has a 10k pull-up (R23). |
| V2-8 | -INT = INTREQ AND FULL in hardware (IC54/B): reading PE releases -INT at once, whatever the firmware is doing; INTREQ has a 10k pull-down (R24). |
| V2-9 | MD0..7 are released with the pull-ups on (no floating inputs between transfers); IC51 / IC53 are 74HCT parts on the card. |
| V2-18 | the data bit is read first in the ISR; the receive rings are 64 bytes (the mouse's packets during LED commands); a VT100 key sequence is queued whole or not at all; E0 7E (Ctrl-Break) no longer toggles Scroll Lock, E0 59 no longer sets right shift; the FULL comment says 7 us (INP's -IO-RD). Still open: a scan code typed while `send_leds()` waits for $FA is taken as the answer. |

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
| **IN PE** | the next byte | a 74LS374 the firmware loads: MD0..7, then a low pulse on LDDATA (PD6, idle high), whose rising edge also sets **FULL** (a 74HCT74); the CPU's read clears FULL (-RD_PE AND -RESET on its CLR) | loads the next byte only when FULL (PB2) reads 0 twice, 5 us apart (a read strobe holds FULL clear while it lasts), with SRC (PB5) set first; reloads if FULL did not set |
| **IN PD** | status: bit 0 FULL, 1 SRC (0 keyboard, 1 mouse), 2 BUSY, 7..3 = 0 | a 74LS244 | SRC is a pin |
| **OUT PD** | a command | a 74HCT374 latches DATA0..7 on the strobe's rising edge and sets **BUSY** (74HCT74) | sees BUSY (PB3), pulls -RDCMD (PD7) low: the latch drives MD0..7 and BUSY clears |

The local bus MD0..7 is PC0-PC5 and PB0, PB1 (PD0/PD1 stay the serial port, PD2/PD3 the PS/2 clocks).

**Commands** (OUT PD): `$01` interrupts on, `$02` off, `$03` acknowledge (-INT released until the next byte), `$04`
mouse on (reset + enable reporting), `$05` mouse off, `$06` flush both queues, `$07` keyboard reset, `$10`-`$17`
keyboard LEDs (bit 0 Scroll, 1 Num, 2 Caps Lock), `$FE` debug output on the FTDI console on/off, `$FF` start again.

**INT**: INTREQ (PB4) = interrupts on AND not acknowledged AND FULL. The card ANDs it with FULL once more (IC54/B,
74HCT08) and drives the bus -INT (C13) through IC27/D (7416, open collector) and jumper **JP3 INT-EN**: with the jumper
off the card never touches -INT. Reading PE clears FULL, so -INT goes away with the last waiting byte at once (not when
the firmware's loop comes round) and comes back with the next; during the ATmega's reset and bootloader FULL is 0, so
-INT stays released. A handler reads PD first: FULL = 0 means the
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
| PD6 | D6 | LDDATA | data latch clock + FULL set (idle high, R22 10k pull-up) |
| PD7 | D7 | -RDCMD | command latch output enable + BUSY clear (R23 10k pull-up) |
| PC0-PC5, PB0, PB1 | A0-A5, D8, D9 | MD0-MD7 | the local bus |
| PB2 | D10 | FULL | in |
| PB3 | D11 | BUSY | in |
| PB4 | D12 | INTREQ | out (R24 10k pull-down) |
| PB5 | D13 | SRC | out (the Uno bootloader's LED pin) |
| RESET | | MRST | 10k pull-up R16; 100 nF from the FTDI DTR; the bus -RESET through IC27/E and IC27/F (7416, two open-collector inverters, R21 4.7k between them): a bus reset pulls MRST low, a high -RESET leaves it to R16 |

Flash it through the FTDI header (Optiboot, as an Uno): `arduino-cli compile --fqbn arduino:avr:uno --libraries
embedded/libraries -u -p /dev/cu.usbserial-XXXX embedded/video-ps2`. A blank ATmega328P needs the Uno bootloader
burned once with an ISP programmer (there is no ISP header on the card: burn it before fitting).
