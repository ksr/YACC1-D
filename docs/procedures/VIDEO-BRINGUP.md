# Video card V1.0 — bring-up plan

The plan for getting a picture out of the built V1.0 card, from the bench checks to the console mirrored on a monitor.
Written 2026-10-10. The card's theory of operation is [`docs/cards/video.md`](../cards/video.md); this document is the
order of work and the tools for each step.

## Where the card stands

- In the machine since 2026-09-18, in the $D000 block (SV3 5-6). **No 6845 fitted.**
- The +5V/VCC rails joined by a wire (2026-09-21); RN2 back to 10k.
- The display RAM's lower 1K tested through the bus tester: `tests/video/video_ram_test.py` 8/8 (2026-09-21). The
  upper 1K ($D400-$D7FF) has never been tested.
- The ROM in the machine (`ROM 2026-10-07`) has the video unit: the probe at reset (`VIDEO CARD FOUND`), the monitor's
  `V` commands and console mirroring, with `VIDAUTO` off.
- Open findings that stand between the card and a picture (`docs/cards/video.md` section 4):
  - **RS**: the 6845's data register cannot be reached as built. Fix: IC17 pin 24 to ADDR1
    (`hardware/cards/video/docs/fix-6845-register-select.md`).
  - **6.1, E one-shot**: C1 has no charging path except IC1's input current, so after one access E may stay away. Fix:
    a pull-up (10k) from IC27 pin 12 (N$3) to +5V.
  - **6.2, CHARCLOCK runt**: the 74LS166 load may be missed below a ~16-20 MHz dot clock, giving a blank screen with
    good sync.
  - **7416 outputs without pull-ups**: the video output (IC27/A to DB9 pin 7) can only pull low. It needs a pull-up
    (e.g. 470 Ω to +5V at DB9 pin 7) to give a monitor a TTL high.
  - **6.5, LPSTB floating** (IC17 pin 3): tie it to GND.
- Unknowns to settle at the bench: the crystal (Q2), SV4's position (crystal or crystal/2), the character EPROM's
  contents (IC25), and **which monitor** (see "Monitors" below).

## The tools

| Tool | Where it runs | What it does |
|---|---|---|
| `tests/video/video_ram_test.py` | bus tester, CPU out | display RAM $D000-$D3FF, patterns, isolation, write-through (2026-09-21) |
| `tests/video/crtc_regs.py [--gap S]` | bus tester, CPU out | the latch, R14/R15 write and read back, repeated accesses (finding 6.1), R12/R13 readability |
| `tests/video/crtc_picture.py [--regs ..] [--png]` | bus tester, CPU out | writes the test card and programs the 6845, then lets go: **a picture with no CPU** |
| `tests/video/hold_address.py D800 [--rd]` | bus tester, CPU out | parks an address for the meter (-CS, RS, E pins) |
| `tests/video/asm/vram.img` | CPU, `monload.py --go 3000` | the whole 2K at full speed, four patterns |
| `tests/video/asm/crtcreg.img` | CPU | the register path at full speed, 256 back-to-back accesses |
| `tests/video/asm/testcard.img` | CPU | programs the 6845 from a table at $3003 (patch it with `E 3003`), draws the test card |
| `tests/video/asm/vstress.img` | CPU (after testcard) | rolls the whole screen through the character set while the 6845 reads it; any key stops it |
| `tests/video/asm/estrobe.img` | CPU | an endless loop of 6845 accesses for the scope (reset stops it) |
| the monitor's `V` commands | CPU | `VS VF VD VC VW VB VR VI VM` (`docs/cards/video.md` section 8) |
| `tools/vidsim.py` | the Mac | the picture the card makes, from the emulator, a state file or the real card's RAM; timing for any crystal; the character EPROM image |

The bus-tester scripts need the **bus-driver** firmware on the tester (`embedded/bus-tester/bus-driver`; the bus-stepper
or bus-monitor is on it otherwise - `embedded/bus-tester/README.md`). They were written 2026-10-10 against the same
`tools/busdrv.py` calls as the memory and register tests and **have not been run on the machine yet**.

## Phase 0 — at the bench, power off

1. **Read the crystal Q2** and **SV4** (pin 1-2 = the crystal is the dot clock, 2-3 = half of it). That gives the dot
   clock. `python3 tools/vidsim.py timing --dotclock HZ` shows what the ROM's table makes of it.
2. **Read the character EPROM** (IC25, a 2732) in the TL866:
   ```bash
   minipro -p 2732A@DIP24 -r chargen-read.bin
   ```
   Draw it with `tools/vidsim.py render ... --chargen chargen-read.bin` (or `run tests/video/asm/testcard.img
   --chargen chargen-read.bin --png card.png`). The card uses the low 512 bytes: code × 8 + row, dots in D7..D3. If it
   is blank, foreign or wired differently, burn `firmware/video/chargen.bin` (a 2513-style 64-character set drawn for
   this wiring). **Done 2026-10-18:** the fitted chip is a 128-character ASCII set whose letters sit at $200-$2FF,
   beyond the card's reach (A9 grounded): letters would show blank. `firmware/video/chargen-remapped.bin` is its own
   font moved into the card's layout (`firmware/video/README.md`) - burn that into a 2732A:
   ```bash
   minipro -p 2732A@DIP24 -w firmware/video/chargen-remapped.bin
   ```
3. **The RS fix**: bend the 6845's pin 24 out and wire it to IC15 pin 41 (ADDR1), as in
   `hardware/cards/video/docs/fix-6845-register-select.md`. Fit the 6845.
4. Recommended before powering, each a single wire or part:
   - 10k from IC27 pin 12 to +5V (finding 6.1)
   - IC17 pin 3 (LPSTB) to GND (6.5)
   - 470 Ω from DB9 pin 7 to +5V (the video line's high level)

   Without the 10k, phase A step 2 shows whether 6.1 bites.

## Phase A — the bus tester, CPU out

Sequencer card out, bus tester in with the bus-driver firmware, the clock irrelevant (the 6845 runs on the card's own
crystal).

1. `python3 tests/memory/memory_status.py --rom <the chip's image>` and `python3 tests/video/video_ram_test.py --quick`:
   the memory card and the display RAM as before.
2. `python3 tests/video/crtc_regs.py`:
   - **ALL PASS**: the register path works (-CS, RS on A1, E).
   - **R14/R15 read 00 or FF**: the 6845 does not answer. `hold_address.py D800` and `D802` with a meter: IC17 pin 25
     (-CS) low at both, pin 24 (RS) low at $D800 and high at $D802. With `--rd` and a scope, look at pin 23 (E).
   - **Repeat failures that go away with `--gap 0.5`**: finding 6.1 (fit the 10k on IC27 pin 12).
   - **R12/R13**: `00 00` = a Motorola MC6845, `12 34` = a part that reads them. Both are fine.
3. `python3 tests/video/crtc_picture.py --dotclock HZ --png expected.png --verify`: the test card in the RAM and the
   6845 programmed; the tester lets go and the 6845 keeps scanning. With a scope:
   - DOTCLOCK at SV4 pin 2.
   - CRTCCLOCK at IC17 pin 21: dot/5.
   - CHARCLOCK at IC19 pin 8: a short low pulse each character (6.2: it must still be low at the next DOTCLOCK edge).
   - HSYNC at IC17 pin 39: the line rate the timing report gives.
   - VSYNC at pin 40: the frame rate.
   - DE at pin 18.
   - The dots at IC24 pin 13.
   - The video at DB9 pin 7.

   `tools/vidsim.py timing` prints the expected rates. `--png` draws what the monitor should show, and
   `tools/vidsim.py render STATE --raster` draws the whole frame with the sync and blanking periods, for comparing
   with the scope.
4. A monitor on the DB9 (see "Monitors"). Nothing at all: the sync rates against the monitor's. Sync but a blank
   screen: the dots (6.2, the EPROM, DE). Garbage characters: the EPROM's contents or the code/row wiring (A3..A8 / A0..A2).
5. To change the timing without the CPU: `crtc_picture.py --regs 126,80,98,10,31,6,24,28,0,7` with the numbers that
   `vidsim.py timing --regs ...` approves.

## Phase B — the CPU, at speed

Sequencer card back, the bus tester on bus-monitor or bus-stepper, the clock at 1 MHz (then try 6 MHz). Each program
is loaded with `python3 tools/monload.py --delay 6 --go 3000 tests/video/asm/NAME.img`. Its expected output on the
microcode emulator is checked in `make check` (`tests/video/asm/run.py`).

1. **`vram.img`**: four passes over all 2K, each ends `ERRORS 0000`. Run it twice, with the 6845 stopped (before any
   CRTC programming) and running (after testcard). An error only with the 6845 running points at the IDT7134's
   arbitration.
2. **`crtcreg.img`**: R14 and R15 `OK`, `REPEAT R15 X256: 0000 FAILED OK`, R12/R13 as in phase A. Here the accesses are
   microseconds apart, so finding 6.1 shows harder than with the tester.
3. **`testcard.img`**: the test card on the monitor. Its table is at $3003-$3012. Change a register with the monitor
   (`E 3003`, new bytes, Esc) and `G3000` again. The expected picture is
   `python3 tools/vidsim.py run tests/video/asm/testcard.img --png card.png`. The characters touch each other: the
   card's character is 5 dots with no gap column (IC28 divides by 5). That is the design, not a fault.
4. **`vstress.img`**, after testcard: the text rolls through every code and row 23 counts the passes. Watch for snow
   or characters that stay wrong (the two ports at once). Any key returns to the monitor.
5. **`estrobe.img`** with the scope on IC17: -CS (pin 25) low for each access, RS (pin 24) low then high, E (pin 23)
   at least 450 ns (280 ns on faster grades) every time. Reset stops it.
6. **The ROM's driver**: `VS`, `VI` (the ROM's table), `VC`, `VW0000 HELLO`, then `VM1`. From then on the console's
   output appears on the screen too (`docs/cards/video.md` section 8).
7. When all of it works: `VIDAUTO EQU 1` in `firmware/monitor/monitor.asm`, rebuild, burn. The card starts at reset.
   If the timing changed, put the new table in `vcrtab` too.

## Away from the machine

- `python3 tools/vidsim.py run tests/video/asm/testcard.img --png card.png`: runs any program on the microcode
  emulator and draws the screen it leaves, with the timing report. `--raster` draws the whole frame, `--chargen FILE`
  uses a real EPROM image, `--dotclock HZ` sets the crystal.
- `python3 tools/vidsim.py timing --regs R0,R1,... --dotclock HZ`: the raster any register table makes, checked
  against a TV-rate monitor, an IBM 5151 and an IBM 5153.
- Both emulators model the card (`software/videomodel.h`):
  - `-V` prints the screen.
  - `-W` logs every CRTC write, and every write to the latch (a bus fight on the real card).
  - `-N` takes the card away.
  - `Y1VIDSTATE=FILE` with `-V` saves the state that `vidsim.py render` draws.
  - `Y1VID_R12READ=1` models a 6845 that reads R12/R13.
- `python3 tests/video/asm/run.py` and `tests/video/emu.py` check it all (both in `make check`).

## Monitors

The card's DB9 is wired MDA-style: pin 7 video, 8 HSYNC (positive), 9 VSYNC (positive), 1 GND. The video output is an
open-collector 7416 through 33 Ω with no pull-up. The ROM's table is TV-rate: 15.75 kHz and 60 Hz for an assumed 10 MHz
dot clock.

| Monitor | What it needs | With this card |
|---|---|---|
| a TV-rate TTL monitor, or a composite one through the RCA (combined sync only) | 15.7 kHz, 60 Hz | the ROM's table, if the crystal gives 10 MHz (or adjust R0..R7 for the real crystal) |
| IBM 5153 (CGA colour) | 15.7 kHz / 60 Hz, TTL R G B I on DB9 3-6, +H 8, +V 9 | timing fits; the card's video is on pin 7, so an adapter must take it to a colour pin (e.g. 4, green) |
| IBM 5151 (MDA mono) | 18.432 kHz / 50 Hz, video 7, intensity 6, +H 8, **−V** 9 | the line rate needs a new table and a dot clock near 9.2 MHz (dot/5/(R0+1) = 18.4 kHz). The VSYNC polarity is wrong (the 6845's is positive), so it may need inverting. A real MDA picture (9-dot characters, 720 dots) is the next revision's job |

`tools/vidsim.py timing` reports the match for each.

## When it misbehaves

| Symptom | Look at |
|---|---|
| `VIDEO CARD FOUND` missing at reset | the $55/$AA probe at $D000: `E D000` by hand; `docs/cards/video.md` section 6 |
| vram.img errors only in $D400-$D7FF | the upper 1K, never tested before: A10 (IC15 pin 40) |
| vram.img errors only with the 6845 running | the dual-port arbitration; -BUSY is not used on this card |
| R14/R15 read 00 or FF | -CS, RS (the bench fix), E: phase A step 2 |
| registers write once, then not | finding 6.1: the 10k on IC27 pin 12 |
| sync right, screen blank | finding 6.2 (CHARCLOCK at IC19 pin 8 against DOTCLOCK), the EPROM, DE at IC17 pin 18, the 470 Ω on DB9 pin 7 |
| characters wrong but stable | the EPROM's contents (`vidsim.py --chargen`), IC23 (the code latch), RA0..2 |
| everything inverse or a solid bar | bit 7 of the bytes (inverse), the cursor registers R10/R11 |
| picture rolls or tears | the sync rates against the monitor (`vidsim.py timing`), R0-R7 |
| snow while vstress runs | dual-port contention on the IDT7134 |

Note: the ROM's comment calls R10 = $67 "blinking 1/16"; bits 6-5 = 11 is the 1/32 rate (harmless).
