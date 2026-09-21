# Video card V1.0 — bench fix for the unreachable 6845 data register

Written 2026-09-21 from the board netlist (`kicad/.../reports/netlist.net`, proven against the Eagle board).

## What is wrong

The 6845 (IC17, DIP-40) has -CS on pin 25 and RS on pin 24. RS = 0 addresses the CRTC's address register,
RS = 1 its data register. On the card:

| Signal | Comes from | Logic |
|---|---|---|
| IC17 pin 24 RS | ADDR0 (bus A0) directly | RS = A0 |
| IC17 pin 25 -CS | IC19 (74LS00) pin 3 = NAND(pin 1, pin 2) | -CS = NOT(BOARDSEL · N$2) |
| IC19 pin 2 (N$2) | IC1 (74ALS08) pin 11 = AND(pin 12, pin 13) | N$2 = A11 · /A0 |
| IC1 pin 13 (N$5) | IC27 (7416) pin 8, input pin 9 = ADDR0 | /A0 (open collector, no pull-up) |

So the CRTC is selected only while A0 = 0, and A0 = 0 is always RS = 0. Only the address register can ever be
accessed; the data register never.

The odd addresses are not free either: IC2 (74LS373) is a read-back latch whose eight D inputs come from JP1
(pins 1, 2, 4, 6, 8, 10, 12, 14; latch enable from JP1 pin 13) and whose outputs sit on DATA0–7. Its -OE (pin 1)
is IC27 pin 10 = NOT(IC1 pin 8), and IC1 pin 8 = AND(IC1 pin 9, ADDR0) with IC1 pin 9 = IC1 pin 6 = AND(BOARDSEL,
A11). So **odd addresses in the high half of the block drive the latch onto the bus**. Simply removing /A0 from the
CRTC select (tying IC1 pin 13 high) would put the CRTC data register and the latch on the bus together at every odd
address: a bus fight. Don't do that.

## The fix: move RS from A0 to A1

Keep the decode as it is (CRTC at even addresses, latch at odd ones) and let A1 pick the CRTC register:

| Address (repeats every 4 bytes through $D7FF) | A1 | A0 | What answers |
|---|---|---|---|
| $D400 | 0 | 0 | 6845 address register |
| $D401 | 0 | 1 | JP1 read-back latch (IC2) |
| $D402 | 1 | 0 | 6845 data register |
| $D403 | 1 | 1 | JP1 read-back latch (IC2) |

One connection changes: **IC17 pin 24 leaves ADDR0 and goes to ADDR1**. ADDR1 is on exactly two pins of the
board: bus connector X1 pin A4 and the dual-port RAM IC15 pin 41. Nothing else on the card uses A1, and nothing
else is on the IC17 pin 24 pad except the ADDR0 track, so no other pin is disturbed.

### Steps (chip in a socket, no board cutting)

1. Card out of the bus, power off.
2. Take the 6845 you are going to fit. **Bend pin 24 straight out** so it stays outside the socket when the chip is
   plugged in. Pin 24 is on the side opposite the notch end's pin 1 row: pins 21–40 run up that side, pin 21 at the
   end nearest pin 20, so pin 24 is the **4th pin from that end**; pin 25 (-CS) is the 5th, right beside it.
   Double-check with the datasheet pinout before bending: pin 24 = RS, pin 25 = -CS, pin 23 = E, pin 22 = R/W.
3. Plug the 6845 in with pin 24 sticking out. The socket's pin-24 contact (ADDR0) is now unused; it stays wired to
   A0 for the other chips, which is fine.
4. Solder a wire (30 AWG wire-wrap is ideal) from the **bent-out pin 24** to **IC15 pin 41** (ADDR1). IC15 is the
   48-pin dual-port RAM; pin 41 is on the pin 25–48 side, 8th pin from the pin-48 end (pins 48, 47, … 41). Solder to the
   pin where it leaves the socket or IC body, not to the board pad. If IC15's pin 41 is awkward, the alternative pickup
   is bus connector X1 pin A4 on the solder side.
5. Confirm with a meter, card still out: continuity IC17 pin 24 ↔ IC15 pin 41 (and ↔ X1 A4); **no** continuity
   IC17 pin 24 ↔ IC17 socket pin 24 / X1 A3 (that would mean the pin went into the socket after all).

If you would rather not bend a chip pin: lift socket pin 24 instead (desolder that one socket pin and bend it up, or
cut the ADDR0 track at the pad) and wire the socket pin to IC15 pin 41. Same result; more work.

### Verifying with the bus tester (before a 6845 is fitted, or with it fitted)

`tests/video/hold_address.py HEX [--rd]` parks an address on the bus and waits, so a meter can sit on the socket:

| Command | IC17 pin 25 (-CS) | IC17 pin 24 (RS) |
|---|---|---|
| `hold_address.py D400` | low | low |
| `hold_address.py D402` | low | **high** (this is the new behaviour; before the fix it read low) |
| `hold_address.py D401` | high | (latch selected instead) |
| `hold_address.py D001` | high | — (A11 = 0: video RAM half) |
| `hold_address.py C400` | high | — (BOARDSEL off) |

With a 6845 fitted, the software test is: write R12/R13 (start address, registers 12 and 13) through $D400/$D402 and read
them back, or write a value to the data register and read it back at $D402 after re-selecting the register at $D400. The
6845's registers 12–17 are readable; 0–11 are write-only, so read back R12 or R14.

Software note: `firmware/` has no CRTC code yet; when it is written, the register access is
`$D400 ← register number`, then `$D402 ← value` (or `value ← $D402`). Odd addresses read the JP1 latch.

## Design change for the next revision (not a bench item)

- RS (IC17 pin 24) to A1 in the schematic, as above.
- Pull-ups on the 7416 outputs (IC27 pins 2, 4, 6, 8, 10, 12); N$5 today only reads high because it floats.
- Join the +5V and VCC nets (see the card README: the +5V rail had no source).
