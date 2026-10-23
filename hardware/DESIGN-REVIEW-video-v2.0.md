# Design review — video card V2.0 before ordering (2026-10-22)

**Re-review (2026-10-23): [`DESIGN-REVIEW-video-v2.0-r2.md`](DESIGN-REVIEW-video-v2.0-r2.md)** - the fixes and direct mode checked again: HIGH 0, MED 1, LOW 9, INFO 6; order after R2-1 (the MD-60SM side-leg slots).

An independent pass over `hardware/cards/video/kicad/v2.0` (designed and generated the same day, not ordered, no
gerbers) and the ATmega firmware `embedded/video-ps2`. Findings only: the design files (`v20_netlist.py`, `gen_v20.py`,
the KiCad project) are unchanged by this review; every finding carries a proposed fix, pin by pin where it is a net
change.

Read: `v20_netlist.py` pin by pin (re-derived against the TI pinouts of every part), `reports/netlist.net` (and a diff
against `../v1.3/reports/netlist.net`), `reports/erc.json`, `reports/drc.json`, the board file through KiCad 10's
`pcbnew` Python (track lengths per net, pad positions), the v2.0 and v1.3 READMEs, `BACKLOG.md` "Video card V2.0",
`docs/cards/video.md` sections 3-7a, `docs/system/BUS.md`, `MICROCODE.md`, `ARCHITECTURE.md` sections 8-11,
`docs/cards/io.md`, `docs/cards/cf.md`, `tools/vidsim.py --card v2.0`, and the microcode image itself
(`firmware/microcode/ucode-generator2/test.hex`, decoded with `tools/ucode_wavedrom.py`'s reader: the strobe and port
windows below are measured from it, not from the generator's source).

Severity as in the earlier reviews, with one more level: **HIGH** = will not work, damages parts, or must be fixed
before ordering; **MED** = likely problem or no margin by specification; **LOW** = improvement; **INFO** = a fact the
next step (the ROM driver, the bench) needs. A finding marked *(firmware)* needs no board change.

Data-sheet values. The tree's `docs/datasheets/` holds the AS6C62256 (Alliance, -55) and the 27C64 used below; its
74374 and 7474 sheets are the HC/AHC parts, so the 74LS figures are the TI SN74LS data-book values (typ / max at
5 V, 25 °C, CL 15 pF) as commonly published, and the MC6845, MBM2732A, IDT7134 and ATmega328P figures are those
parts' published data-sheet values as commonly quoted; none of these was fetched for this review. Each such figure is
marked "(TI LS)", "(MC6845)" and so on; **the ones to confirm against the part actually bought are flagged To verify**.
LS minimum delays are not specified; where a race depends on them, one third of the typical value is assumed and said.

## Status of the findings (2026-10-22, after the fixes)

The findings below are unchanged; this table says what became of each. Commits: firmware `7d3c054`, board and circuit
`fc71ec4`. The changes, with two features added in the same rebuild (direct mode with GFX-ON = 0, the text-only
build), are in `hardware/cards/video/kicad/v2.0/README.md`; a **re-review of the changed slot logic and direct mode**
comes before ordering (`BACKLOG.md`).

| ID | Sev | Status | How |
|---|---|---|---|
| V2-1 | HIGH | applied (`7d3c054`, `fc71ec4`) | SRC on IC49 pin 19 (PB5), BUSY on pin 17 (PB3), the firmware's `#define`s swapped. Optiboot touches only PB5 (its LED, now SRC, an output nothing else drives) and the UART (PD1 to J4 only); every other pin is an input with a defined level (R22-R24, the PS/2 pull-ups) |
| V2-2 | HIGH | applied (`fc71ec4`) | Same Sky (CUI) MD-60SM, footprint from its data sheet rev 1.09 (2024-09-12), layout for date codes after 2022-03-03; the check list in the v2.0 README. The side-leg slots are drawn but not separately dimensioned on the sheet (sized like the dimensioned earth slot): confirm with the first jack |
| V2-3 | HIGH | applied (`7d3c054`) | the clock pulled low first, the transmitter armed after the 120 us |
| V2-4 | MED | applied (`fc71ec4`) | QC OR RCO (IC32/C), then NAND with GFX-ON (IC19/D) = NMUX; the 157s' CPU inputs moved to I1. Deviation: the extra NAND (for direct mode) is in the data path only, so the hold margin grows by one LS00 delay |
| V2-5 | MED | applied (`fc71ec4`) | IC40 enabled by GWE; IC46/F's -WSLOT gone |
| V2-6 | MED | applied (`fc71ec4`) | IC27/E, IC27/F and R21 4.7k; D1 removed |
| V2-7 | MED | applied, deviated (`7d3c054`, `fc71ec4`) | -INT = INTREQ AND FULL in a new 74HCT08 (IC54/B) instead of IC19/D + IC48/C, which direct mode needed; a 10k pull-down R24 on INTREQ (an HCT input); R22, R23 10k pull-ups; LDDATA idle high |
| V2-8 | MED | applied (`fc71ec4`) | by V2-7's hardware AND |
| V2-9 | MED | applied (`7d3c054`, `fc71ec4`) | IC51 74HCT374, IC53 74HCT74; MD released with the pull-ups on |
| V2-10 | MED | applied (`fc71ec4`) | a 28-pin AT28C64B-15 (pins + 2, A12/A11/A9/-CE/-OE low, -WE high, A10 = DOTS); `firmware/video/chargen-v20.bin` (8K) from `vidsim.py chargen --card v2.0` |
| V2-11 | MED | applied (BOM) | HD6845SP or MC68B45P in `BOM.md` and the README; no circuit change |
| V2-12 | MED | applied (`fc71ec4`) | IC33 74HCT273, IC40 74HCT244, IC51 74HCT374; also IC41 74HCT374 and the new IC54 / IC55 in HCT. The DATA0 low level stays a bench measurement |
| V2-13 | LOW | applied (documentation) | in 6-dot mode software keeps GFX-ON = 0: direct mode writes need no slot |
| V2-14 | LOW | open | a microcode change, machine-wide; nothing on the card |
| V2-15 | LOW | open | scope E against R/-W at the first `OUT PB` (bench order step 4) |
| V2-16 | LOW | applied (`fc71ec4`) | C18, C49, C22 beside the VCC pins; C16 47 uF |
| V2-17 | LOW | applied in part (`fc71ec4`) | F1, a 0.5 A PTC (Bourns MF-RHT050) in the PS/2 +5 V; the series resistors are not fitted |
| V2-18 | LOW | applied in part (`7d3c054`) | data bit read first, 64-byte rings, VT100 sequences whole, E0 7E / E0 59 fixed, the comment; open: a scan code typed while `send_leds()` waits for $FA is taken as the answer |
| V2-19 | LOW | applied in part | the CMOS 28C64 (V2-10) saves ~80 mA; the 74LS85 is a BOM option; the supply check is for the bench |
| V2-20 | LOW | applied in part (`fc71ec4`) | J4: a 1 mm label at every pin, "1 GND (BLK)" first; the overlapping reference texts stay (cosmetic) |
| V2-21 | LOW | applied (`fc71ec4`) | `BOM.md`, generated by `gen_v20.py bom` with the notes, the text-only build marked |
| V2-22 | LOW | open | a rule for the ROM driver (one `OUT PD` per BUSY = 0) |
| V2-23 | LOW | open | check VSYNC's low level at the bench |
| V2-24 | INFO | superseded in part | direct mode (GFX-ON = 0) has no limit of its own below the machine's ~6 MHz (`tests/video/v20_timing.py`); slot mode keeps ~1.8 MHz |
| V2-25 | INFO | noted | with V2-7 the ATmega's boot no longer asserts -INT; keep JP3 open until the V2.0 ROM all the same |
| V2-26 - V2-29 | INFO | noted | for the ROM driver and the bench (level-mode INT, the 2K wrap, the PS/2 start-up time, clock-line ringing) |

## Summary

| ID | Sev | Finding | Fix (short) |
|---|---|---|---|
| V2-1 | HIGH | The Uno's Optiboot drives PB5 (D13, its LED) as an output for ~1.4 s after every external reset; PB5 is **BUSY**, the output of IC53/B (74LS74): two outputs fight on every bus or DTR reset | swap BUSY and SRC on the ATmega (IC49 pin 19 <-> pin 17) and the two `#define`s; or burn a bootloader without the LED |
| V2-2 | HIGH | The Mini-DIN-6 footprint is approximate (pins on a 2.6 mm grid, round shell holes) | redraw from the jack bought; the check list is in the finding |
| V2-3 | HIGH *(firmware)* | `ps2_send()` arms the bit counter before pulling the clock low; the host's own falling edge (INT0/INT1 fire on outputs too) is counted as the first device clock: every host-to-device byte goes out one bit late | set `sending`/`n` after the 120 us clock-low; the mouse ($F4), the LEDs and the resets then work |
| V2-4 | MED | Display latch hold race: IC42 clocks on CHARCLOCK (RCO + a NAND) at the very edge where QC falls and the 74LS157s switch the RAM to the CPU address | the 157s' select from `QC OR RCO` (spare IC32/C) |
| V2-5 | MED | GD bus contention at both edges of WSLOT: the RAM's -OE and IC40's enable switch on the same net | enable IC40 from GWE (the RAM's -WE) instead of -WSLOT |
| V2-6 | MED | D1 lets the bus -RESET's TTL high (VOH 2.7 V min) clamp the ATmega's RESET to about VOH + 0.6 V, below its guaranteed VIH (0.9 VCC); bus noise reaches the MCU reset | drive MRST from two spare 7416 gates (open collector) |
| V2-7 | MED | The ATmega's pins float during its reset and Optiboot (~1.4 s): INTREQ floats high -> -INT asserted (JP3 fitted); LDDATA floats on two clock inputs (spurious FULL) | -INT = INTREQ AND FULL in hardware (spare IC19/D + IC48/C); pull-ups on LDDATA and RDCMD, LDDATA idle high |
| V2-8 | MED | INTREQ is recomputed only at the end of `loop()`: after the CPU reads PE it stays high for ~10 us normally, up to ~70 ms (LED commands) or ~1 s (resets) - a level-mode interrupt storm | the hardware AND of V2-7 (or a pin-change ISR on FULL) |
| V2-9 | MED | 74LS outputs into ATmega inputs: VOH min 2.4-2.7 V (TI LS) against VIH min 0.6 VCC = 3.0 V (ATmega328P) on MD0..7 (IC51), FULL and BUSY (IC53) | IC51 a 74HCT374, IC53 a 74HCT74 (and MD pull-ups in the firmware) |
| V2-10 | MED | 6-dot EPROM budget: 500 ns less CHARCLOCK, the 74LS174 and the 74LS166 set-up leaves 400-433 ns against the MBM2732A's 450 ns | a 28-pin socket for an AT28C64B-15 (the ROM's part, 150 ns) |
| V2-11 | MED | 6-dot 6845 clock low: 167 ns nominal, 145-162 ns with the 74LS163's output skew, against 160 ns (MC6845) | fit a faster grade (HD6845S, MC68B45); measure at IC17 pin 21 |
| V2-12 | MED | DC load on DATA0..7: the 6845 (1.6 mA) and the IDT7134 (4 mA) drive the backplane unbuffered; V2.0 adds ~1.1 mA of LS input current a line on its own card | IC33, IC40, IC51 in 74HCT (no DC load); measure VOL at the bench |
| V2-13 | LOW | Graphics writes in 6-dot mode: -WE is only count 10, opened by WRQ late in that count: ~70 ns typical, a few ns worst case, data barely before it | document "graphics RAM is written in 8-dot mode only" |
| V2-14 | LOW | `INP` releases -IO-RD and IO-ADDR on the same clock edge; the 1->0 transitions of PB/PD/PF pass through P9 (the CF data port) | microcode: one step without -IO-RD before the record ends (machine-wide) |
| V2-15 | LOW | 6845 R/-W (= -IO-WR) leads E by one XOR delay, against an address/R-W set-up of 70-160 ns | none needed (bench-proven on V1.2 with the same scheme); scope it |
| V2-16 | LOW | Decoupling: C18 is 48 mm from the 6845's VCC pin (20), C49 17 mm from the ATmega's pin 7, C22 13 mm from the 74LS90's pin 5; only 10 uF bulk for ~1 A | move the three; 47-100 uF bulk |
| V2-17 | LOW | PS/2 +5 V straight from the plane (no fuse), PS/2 lines straight to the ATmega | a 0.5 A PTC for J2/J3 pin 4; optional 100-220 ohm series resistors |
| V2-18 | LOW *(firmware)* | ISR on `digitalRead`/`micros` (10-15 us an edge); `ps2_wait` swallows scan codes during LED commands; the 16-byte mouse ring overflows then; MD floats when released; small key-map slips | the list in the finding |
| V2-19 | LOW | Supply ~0.85 A typical, ~1.45 A maximum, plus up to 0.55 A for two PS/2 devices; the 74S85 (73 mA) and the NMOS 2732 (~100 mA) are the hogs | check the machine's supply; 74LS85; the CMOS EEPROM of V2-10 |
| V2-20 | LOW | Silkscreen: the J4 pin legend is below the minimum text height (the FTDI cable's orientation depends on it); reference overlaps at IC49, IC53, IC25, D1, R16, JP3 | larger J4 legend with "GND/BLK" at pin 1; move the overlapping texts |
| V2-21 | LOW | No V2.0 BOM (`docs/bom/video.md` is the V1.0 Fusion export); parts that need a note (600-mil 62256, 6845 grade, sockets) | a BOM from `v20_netlist.PARTS` with the notes in the finding |
| V2-22 | LOW | BUSY clears at the *start* of the ATmega's command read (RDCMD low), ~4 us before the read is done | a software rule (one OUT PD per BUSY = 0); fine at 1 MHz |
| V2-23 | LOW | VSYNC now loads the 6845 with a 7416 input (1.6 mA), IC34 (0.2 mA) and the monitor, above the 6845's one-TTL-load rating | none needed on the bench's evidence; check its low level |
| V2-24 | INFO | The CPU-clock limit for graphics: reads need ~0.9 us from address to sample, writes ~1.1 us of strobe: about 1.8 MHz; at 6 MHz graphics fail (text works; the 6845 then needs the B grade) | - |
| V2-25 | INFO | An old ROM on V2.0: no bus fight anywhere; no picture; with JP3 fitted the ATmega's boot (V2-7) storms the monitor's ISR | leave JP3 open until the V2.0 ROM |
| V2-26 | INFO | The card needs the sequencer's INT jumper in *level* mode (edge mode registers the release); it is the first real -INT source, so review M-6 (no synchroniser) becomes live | - |
| V2-27 | INFO | Graphics take MA0..10, text MA0..11: start address + screen must stay below 2048 (no hardware scroll past 2K) | - |
| V2-28 | INFO | The keyboard is ready ~1.5-2.5 s after a bus reset (Optiboot 1 s, the keyboard's BAT, the mouse probe) | the ROM must not wait for it at reset |
| V2-29 | INFO | Clock routes: DOTCLOCK 201 mm, CHARCLOCK 194 mm, CRTCCLOCK 209 mm, over the GND plane: below the critical length for LS edges | look for ringing at the far ends |

**Counts: HIGH 3 (two board, one firmware), MED 9, LOW 11, INFO 6.**

**Verdict: order after the HIGH fixes** (V2-1, V2-2; V2-3 is firmware and only has to be fixed before the PS/2 ports are
used). Since the board is generated and not ordered, fold in the MED fixes in the same rebuild: they are net changes
on spare gates or part-type changes (V2-4, V2-5, V2-6, V2-7/V2-8, V2-9, V2-10, V2-12), plus a part grade (V2-11). Nothing
found needs rework of the architecture: the slot scheme, the port decode, the bus interface and the pipeline are right.

The netlist changes of the HIGH and MED fixes together use IC19/D, IC27/E, IC27/F, IC32/C and IC48/C (all spare today)
and free IC46/F; IC32/D, IC44/B and IC45/B stay spare.

---

## Timing tables (12 MHz, as drawn)

Times from the DOTCLOCK rising edge that loads IC28 (the end of count 15). Delays: 74LS163 CLK->Q 13/24 ns (rise),
18/27 (fall), CLK->RCO 20/35, 18/35; 74LS00 9-10/15; 74LS157 select->output 15-18/23-27, data->output 9/14; 74LS74
CLK->Q 13/25 (rise); 74LS86 12/23; 74LS20 9-10/15; 74LS244 enable 15-20/23-30; 74LS374 CLK->Q 15-19/28, set-up 20
(TI LS). AS6C62256-55: tAA 55, tOH 10 min, tOHZ 20 max, tOLZ 5 min, tWP 45 min, tAW 50, tDW 25, tDH 0, tAS 0, tWR 0
(the tree's data sheet). MC6845: MA/RA delay after CLK falling 160 ns max, DE/CURSOR 300 ns max (To verify).

### 8-dot mode (/8, counts 8..15, dot 83.3 ns, character 667 ns)

| count | t (ns) | QC (select, 6845 CLK) | WEPH = QA xor QB | RAM address | what happens |
|---|---|---|---|---|---|
| 8 | 0-83 | falls at 18-27 | 0 | CPU from 33-54 | CHARCLOCK rises at 27-50: IC23, IC22, **IC42** latch, IC44 samples GWR (WRQ at 40-90); WSLOT at 45-105 turns the RAM's -OE off, IC40 drives GD from 70-150; the 6845's MA/RA for the next character valid by 187 |
| 9 | 83-167 | 0 | 1 | CPU | -WE falls at 118-145 (WRQ AND NOT QC AND WEPH AND GWR) |
| 10 | 167-250 | 0 | 1 (a few-ns glitch at the 9->10 edge, QA falling and QB rising) | CPU | write in progress |
| 11 | 250-333 | 0 | 0 | CPU | -WE rises at 285-312: tWP ~167 ns, tDW 135 ns or more, tAW 230 ns |
| 12 | 333-417 | rises at 346-357 | 0 | display from 361-380 | **IC41** (CPU read latch) loads at QC's rise (CPU address on the RAM since 54: tAA 55 + set-up 20 met with 190 ns to spare); WSLOT falls, IC40 off, RAM -OE on |
| 13-14 | 417-583 | 1 | 1 (gated off by NOT QC) | display | display byte valid at the RAM by about 440 |
| 15 | 583-667 | 1 | 0 | display | RCO high; CHARCLOCK low from 613-633: the 74LS166s and IC28 load at 667 (shift/load set-up 33-53 ns) |
| 8 | 667 | falls | | -> CPU | IC42 takes the display byte: **the hold race of V2-4** |

### 6-dot mode (/6, counts 10..15, character 500 ns)

| count | t (ns) | QC | WEPH | RAM address | what happens |
|---|---|---|---|---|---|
| 10 | 0-83 | falls at 18-27 | 1 | CPU from 33-54 | WRQ at 40-90, so -WE falls only at 50-105 (V2-13) |
| 11 | 83-167 | 0 | 0 | CPU | -WE rises at 98-145: a pulse of ~70 ns typical, down to a few ns |
| 12 | 167-250 | rises at 180-191 | 0 | display | IC41 loads: CPU address on the RAM since 54, + tAA 55 + set-up 20 = 129 < 180 (a 100 ns RAM would fail) |
| 13-15 | 250-500 | 1 | | display | (the graphics layer is not shown in this mode); EPROM budget of V2-10; QC low 145-167 ns (V2-11) |

---

## HIGH

### V2-1 HIGH — Optiboot drives BUSY: two outputs on one net after every reset

**Evidence.** `v20_netlist.py` line 316: `c("BUSY", "IC49.19", "IC53.9", "IC52.6")` - ATmega pin 19 is **PB5** (Arduino
D13), and IC53 pin 9 is the 2Q *output* of a 74LS74. The firmware treats PB5 as an input (`PIN_BUSY 13`,
`video-ps2.ino` lines 48 and 311). But the bootloader the README prescribes (the Arduino Uno's Optiboot, burned with an
ISP programmer) runs before the sketch on every **external** reset - the bus -RESET through D1 and the FTDI DTR pulse
both are - and the Uno build of Optiboot flashes the LED on PB5 (`LED_START_FLASHES = 3`, `LED_DDR |= _BV(LED)`): PB5 is
an output for the three flashes (6 x 62.5 ms) and stays an output, low, until the bootloader times out (watchdog 1 s)
and `setup()` makes it an input. **To verify:** the bootloader actually burned (its build options), by watching D13
after a reset on an Uno.

**Consequence.** For about 1.4 s after each bus reset the ATmega pin and the LS74 output drive one net. BUSY is not
cleared by the bus reset (IC53/B's -CLR is RDCMD, which floats then), so it is 1 about half the time: an LS74 high
output into an AVR pin driven low, or (during the flashes) an AVR high into an LS74 low. Either way the current is set
by the two output stages - tens of mA, above the AVR's 40 mA absolute maximum per pin and beyond the LS74's "one
output shorted, at most one second" rule - every time the machine is reset. A CPU `OUT PD` in that window (a V2.0 ROM
sending $FF at boot) sets BUSY and starts the fight even if it was 0.

**Fix.** Swap BUSY and SRC on the ATmega: `c("SRC", "IC49.19", "IC52.4")`, `c("BUSY", "IC49.17", "IC53.9", "IC52.6")`,
and in the firmware `#define PIN_SRC 13`, `#define PIN_BUSY 11`. SRC is an output the firmware drives anyway; while
Optiboot flashes it, IC52's input just follows (harmless, SRC is valid only with FULL). Alternative without a board
change: burn a bootloader built with `LED_START_FLASHES=0` and without `LED_DATA_FLASH` - fragile, because any later
"burn bootloader" from the Arduino IDE brings the flashes back.

### V2-2 HIGH — The Mini-DIN-6 footprint is a placeholder

**Evidence.** `video-v2.0-local.pretty/MiniDIN6_PS2.kicad_mod`: "APPROXIMATE pin geometry"; pins 1-6 at (-1, +-1.3),
(-3.6, +-2.6), (-3.6, 0), (-1, 3.9), round 2.2 mm shell holes at (2, +-6.75) and (-7, 0); J2 at (228.4, 70), J3 at
(228.4, 88), the jack's face at x = 235.9 against the board edge at 236.17. The v2.0 README lists it under "To check
before ordering".

**Consequence.** If the pattern differs from the jack bought, the jacks cannot be fitted; a wrong pin map (mirror view)
swaps clock, data, +5 V and GND on the keyboard.

**Fix.** Choose the part (CUI MD-60SM, Kycon KMDGX-6S-BS or similar), then redraw the footprint from its PCB drawing
and check: (1) the six pin positions and the drill sizes; (2) the drawing's view (most are "component side"; the
footprint is drawn from the top); (3) that the PCB pin numbers are the *face* numbers of the PS/2 pinout (1 data,
3 GND, 4 +5 V, 5 clock; 2 and 6 not connected) - confirm with a meter on the jack before soldering; (4) the shell /
retention tabs: slots or round holes, plated, on GND; (5) the face position against the board edge and any panel;
(6) the spacing of J2 and J3 against the jack's body width (18 mm today); (7) purple / green or "KBD" / "MOUSE" on the
silk.

### V2-3 HIGH (firmware) — Every host-to-device byte is sent one bit late

**Evidence.** `video-ps2.ino` lines 103-109: `ps2_send()` sets `p.n = 0; p.sending = 1` and *then* pulls the clock low
(`pinMode(p.clk, OUTPUT); digitalWrite(p.clk, LOW)`). The external interrupts are attached to the clock pins with
`FALLING` (line 314), and the ATmega's INT0/INT1 trigger even when the pin is an output (ATmega328P data sheet,
External Interrupts: "the interrupts will trigger even if the INT0 and INT1 ... pins are configured as outputs"). So
the host's own falling edge runs `ps2_edge()`: the 2 ms timeout resets `n` to 0, the `sending` branch drives bit 0 and
sets `n = 1` (lines 66-75). When the device then starts clocking (well inside 2 ms for real keyboards and mice), its
first falling edge finds `n = 1` and sends bit 1 as bit 0, and so on; the device's acknowledge edge is later taken as
a start bit.

**Consequence.** Every command fails (the device answers $FE, `ps2_command` retries once and gives up): the keyboard
reset and the Caps / Num / Scroll Lock LEDs never work, and **the mouse never reports**, because a PS/2 mouse stays
with data reporting disabled until it receives $F4 - `mouse_start()` returns false and the firmware calls it "absent".
Typing still works (a keyboard sends set-2 codes without being told).

**Fix.** Pull the clock low first, then arm the transmitter just before releasing it:

```
pinMode(p.clk, OUTPUT); digitalWrite(p.clk, LOW);   // this edge now finds sending = 0 and data high: ignored
delayMicroseconds(120);
noInterrupts(); p.sendbyte = b; p.sendparity = ...; p.ack = 0; p.n = 0; p.sending = 1; interrupts();
pinMode(p.dat, OUTPUT); digitalWrite(p.dat, LOW);
pinMode(p.clk, INPUT);
```

(The early edge then reaches the receive branch with `n = 0` and the data line high, and returns without counting.)
Test on the bench with the mouse: `$04` must answer `$FA $AA $00`, then `$FA` for `$F4`.

---

## MEDIUM

### V2-4 MED — The display latch IC42 has no hold margin at the character boundary

**Evidence.** Line 209: IC42's clock (pin 11) is CHARCLOCK = NOT RCO (IC19/C, line 210). Line 265: the select of all
four 74LS157s is CRTCCLOCK = IC28's QC (pin 12). At the edge that ends count 15 the counter loads 8 (or 10): QC falls
and RCO falls on the **same** DOTCLOCK edge. The clock path is CLK->RCO + one NAND: 27 ns typical, 50 ns maximum. The
data path is CLK->QC + 157 select->output + the RAM's output hold: 18 + 16 + tOH (10 ns min, AS6C62256-55) = 44 ns
typical, and with LS minimum delays taken at a third of typical about 6 + 5 + 10 = 21 ns. The 74LS374 needs its data to
hold after the clock (TI LS: hold 0-5 ns; To verify the maker's figure).

**Consequence.** Typically 17 ns of margin; at the corners -29 ns. When it fails IC42 latches bits of the byte at the
CPU's address instead of the displayed one: graphics dots that sparkle or show another plane, depending on the part
mix. The text side (IC23 on the same edge) is safe because the NMOS 6845's MA outputs move tens of ns after its clock
falls (and the bench has shown it).

**Fix.** Hold the display address until RCO has fallen: the 157s' select = **QC OR RCO**. Spare IC32/C: pin 9 =
CRTCCLOCK, pin 10 = RCO (both off GND, line 302), pin 8 = new net MUXS -> IC35.1, IC36.1, IC37.1, IC38.1 (instead of
CRTCCLOCK, line 265). The clock and the data then start from the same RCO edge, and the data path is longer by the OR
gate, the 157 and tOH: +5 ns worst, +31 ns typical. The CPU half starts ~25 ns later; the read latch IC41 (still on QC)
keeps 190 ns of set-up in 8-dot mode and 30-40 ns in 6-dot mode (with a 55 ns RAM: buy the -55 grade). QC also loses
eight LS157 select loads, so the 6845's clock edges get faster.

### V2-5 MED — GD bus contention at each WSLOT edge

**Evidence.** Line 277: WSLOT is the RAM's -OE (IC39 pin 22); line 280: its inverse -WSLOT (IC46/F) enables the write
buffer IC40 (pins 1, 19). Rising: the RAM's output turns off up to tOHZ = 20 ns after -OE rises, while IC40 can be on
one inverter + one LS244 enable after it (no minimum: maybe 10 ns). Falling (QC rises, count 12): the RAM drives again
5 ns (tOLZ) after -OE falls while IC40 needs an inverter + a disable (TI LS244 tPHZ/tPLZ up to ~25 ns) to let go.

**Consequence.** Two overlaps of 10-30 ns per write slot, two or three slots per CPU write: an LS244 output stage
against the RAM's CMOS outputs, with current spikes on GD and the VCC/GND planes next to IC39 and the dot shifters.
Probably survivable, but avoidable at no cost.

**Fix.** Let IC40 drive only while -WE is low: IC40 pins 1 and 19 to **GWE** (IC45 pin 6) instead of -WSLOT. Keep the
RAM's -OE on WSLOT: it goes high at the start of the CPU half, -WE falls 40-70 ns later, and -WE rises a dot before
WSLOT falls, so the two drivers never overlap. Data set-up at the RAM becomes -WE's width minus IC40's enable: about
130 ns against tDW 25 ns in 8-dot mode; hold is IC40's disable time against tDH 0. IC46/F becomes spare (pin 13 to GND,
pin 12 open). During the first ~25 ns of -WE GD floats; a WE-controlled write takes the data at -WE's rise, so that is
harmless.

### V2-6 MED — D1 lets the bus -RESET clamp the ATmega's RESET pin

**Evidence.** Lines 88 and 306: D1 (1N4148) anode on MRST (IC49 pin 1, R16 10k to VCC), cathode on the bus -RESET.
-RESET is a totem-pole 74LS04 output on the sequencer-logic card (BUS.md C30): its high level is VOH, 2.7 V minimum,
~3.4 V typical (TI LS), not 5 V. With -RESET high, D1 conducts from the pull-up into that output and MRST sits at about
VOH + 0.6 V: 3.3 V worst case, ~4-4.5 V typically (the exact value depends on how little current the other LS inputs
on -RESET absorb). The ATmega328P's RESET pin has a guaranteed VIH of **0.9 VCC = 4.5 V** and a threshold anywhere
between 0.2 and 0.9 VCC (data sheet, DC characteristics and reset characteristics; To verify against the current
Microchip sheet).

**Consequence.** Out of specification by design, and a forward-biased diode couples every dip on the backplane's -RESET
line straight into the MCU reset. Typically it works (the real threshold is near mid-supply); the failure looks like a
PS/2 controller that restarts by itself.

**Fix.** Drive MRST through an open collector so that the bus line only ever pulls *down*: IC27/E (spare) input pin 11
= -RESET (off GND, line 302), output pin 10 = new net RESETH with a new 4.7k pull-up R21 to VCC; IC27/F (spare) input
pin 13 = RESETH, output pin 12 = MRST. Remove D1. -RESET low -> RESETH high -> MRST pulled to ~0.2 V; -RESET high ->
MRST released to 5 V through R16; the FTDI DTR pulse through C57 still works. -RESET gains one standard-TTL load (1.6
mA), well within the LS04's 8 mA.

### V2-7 MED — The ATmega's pins float during its reset and the bootloader

**Evidence.** While MRST is low, and for ~1.4 s of Optiboot after it, every ATmega pin except PB5 (V2-1) and TXD is a
high-impedance input. Line 315: INTREQ (PB4) is the input of IC27/D, a standard-TTL 7416 whose open input reads high,
so its output - INTOC, through JP3 the bus -INT - is pulled **low**. Line 312: LDDATA (PD6) is the clock of IC50 and
IC53/A; RDCMD (PD7) is IC51's -OE and IC53/B's -CLR: floating LS inputs, read as high but open to crosstalk from the
traces beside them (LDDATA is 124 mm long, RDCMD 142 mm).

**Consequence.** With JP3 fitted, -INT is asserted from every bus reset until the sketch's `setup()` runs. The monitor
arms interrupts at boot (`iaddr isrcode / INTE`, ARCHITECTURE.md section 8), and in level mode its ISR is re-entered
continuously for that second: the ROM appears to hang after reset. A spurious edge on LDDATA sets FULL with a random
byte in IC50: the first keyboard byte the CPU reads is garbage.

**Fix.** (a) Gate the interrupt with FULL in hardware, which also fixes V2-8: spare IC19/D pin 12 = INTREQ, pin 13 =
FULL (both off VCC, line 301), pin 11 = new net NINT; spare IC48/C pin 9 = NINT, pins 10, 11 stay on VCC, pin 8 = new
net INTG -> IC27 pin 9 (instead of INTREQ). -INT is then low only while INTREQ AND FULL, and FULL is cleared by the bus
reset. (b) A 10k pull-up on LDDATA (new R22) and make LDDATA **idle high**: the firmware writes `digitalWrite(LDDATA,
HIGH)` before `pinMode(LDDATA, OUTPUT)`, and loads with a low pulse (high -> low -> high: the 74LS374 and FULL still take
the rising edge). (c) A 10k pull-up on RDCMD (new R23). Pull-ups, not pull-downs: an LS input needs ~1k to be held low.

### V2-8 MED — INTREQ is released late: interrupt storms in level mode

**Evidence.** `video-ps2.ino` line 327: `digitalWrite(PIN_INTREQ, int_on && !acked && digitalRead(PIN_FULL))` runs
once at the end of each `loop()`. After the CPU's `INP PE` (FULL cleared by hardware) the pin stays high until the
loop comes round: ~10-20 us normally, but up to ~70 ms while `send_leds()` runs (two `ps2_command`s, each up to 20 ms
for the send and 50 ms for the answer - Caps Lock does this), ~1 s in `keyboard_reset()` and ~1.1 s in
`mouse_start()`.

**Consequence.** With JP3 fitted and the sequencer in level mode (V2-26), the CPU re-enters the handler as soon as it
IRETs, reads PD, finds FULL = 0 and returns, again and again for those tens of ms to a second: the program is starved.
Sending $03 does not help, because the firmware only reads the command at the next loop.

**Fix.** The hardware AND of V2-7(a). Without the board change: release INTREQ from a pin-change interrupt on FULL (PB2
= PCINT2, `PCMSK0 |= 1 << PCINT2; PCICR |= 1 << PCIE0;` and in `ISR(PCINT0_vect)` clear PB4 when PB2 is low), which
drops -INT within a few microseconds of the CPU's read.

### V2-9 MED — LS outputs into ATmega inputs are below the guaranteed VIH

**Evidence.** Lines 313-318: IC51 (74LS374) drives MD0..7 into PC0..PC5, PB0, PB1; IC53 (74LS74) drives FULL and BUSY
into PB2 and PB5. TI LS: VOH min 2.4 V (LS374, IOH -2.6 mA) and 2.7 V (LS74, -0.4 mA), ~3.4 V typical at light load.
ATmega328P: VIH min 0.6 VCC = 3.0 V at 5 V (DC characteristics, all I/O pins except XTAL1 and RESET; To verify).

**Consequence.** Works on typical parts, not by specification - the same class as review 6.3 (LS into HC). A slow or
marginal high on MD reads as 0: a wrong command byte.

**Fix.** IC51 a **74HCT374** and IC53 a **74HCT74** (same pinouts; TTL-level inputs, rail-to-rail outputs). In the firmware,
release MD with the pull-ups on (`md_release()`: `PORTC |= 0x3F; PORTB |= 0x03` after clearing the DDR bits), which also
stops the eight inputs floating between commands.

### V2-10 MED — The 6-dot EPROM budget is below the MBM2732A's access time

**Evidence.** IC23 (74LS174) takes the character code on CHARCLOCK's rise, 27-50 ns after the dot edge that starts a
character; the EPROM's outputs must be at IC24 (74LS166) one character later, a set-up time before the dot edge at
which it loads. In 6-dot mode: 500 - (27..50) - (20..30, LS174 CLK->Q) - 20 (LS166 data set-up) = **400-433 ns**. The
MBM2732A is a 450 ns part (v1.3 README; MBM2732A-45, To verify the marking of the chip fitted). 8-dot mode leaves
567-600 ns.

**Consequence.** Out of specification by 17-50 ns in 6-dot (80 x 24) mode; it will work with most parts because their
typical access is well below the maximum, and fail on a slow one as wrong dots in some glyph rows. (The v1.3 README's
"500 against 450, little slack" leaves out the latch delays.)

**Fix.** Make IC25 a 28-pin JEDEC socket for an **AT28C64B-15** (150 ns, current production, the part the machine's ROM
already uses and the T48 programs): pins 1 and 26 open, 2 (A12), 23 (A11), 24 (A9), 20 (-CE), 22 (-OE) to GND, 27 (-WE)
and 28 to VCC, 21 (A10) = DOTS, A8..A0 / O0..O7 as today shifted to the 28-pin positions (A8 = pin 25 ... A0 = pin 10,
O0..O2 = 11-13, O3..O7 = 15-19); `chargen-v13.bin` at $0000-$0FFF. It also saves ~80 mA (V2-19). Alternative: a 2732A-25
in the 24-pin socket.

### V2-11 MED — The 6845's clock low time in 6-dot mode

**Evidence.** Line 191: the 6845's CLK (pin 21) is QC. Over counts 10..15 QC is low for 2 dots: 167 ns nominal, but its
fall comes from the counter's load (CLK->Q fall 18/27 ns) and its rise from counting (rise 13/24 ns), so the width is
167 + t(rise) - t(fall) = ~162 ns typical and ~145 ns at the corners (rise at a third of typical). MC6845 (1 MHz part):
clock pulse width low 160 ns min, high 200 ns min (To verify; the v1.3 README quotes the same from memory).

**Consequence.** No margin with an MC6845; the high time (333 ns) is fine and 8-dot mode (333 / 333) is fine.

**Fix.** Fit a faster grade for 80 x 24 - HD6845S, MC68A45 / MC68B45 or UM6845R, rated for character clocks of 2-3.7 MHz
(check the sheet of the part bought) - and measure the low width at IC17 pin 21 in 6-dot mode at the bench. V2-4's fix
removes eight select loads from QC, which sharpens its edges.

### V2-12 MED — DC load on the data bus, with unbuffered NMOS / CMOS drivers

**Evidence.** As on v1.x the 6845 (IC17 D0-D7) and the text RAM's right port (IC15) drive the backplane directly; their
rated low-level output currents are 1.6 mA (MC6845, "one TTL load"; To verify) and 4 mA (IDT7134, VOL 0.4 V; To verify).
A backplane data line carries roughly 15 LS inputs from the other cards (the sequencer's IR, operand, branch and INT
registers, TMP0/1, the transceivers of the memory, ALU and register cards, the I/O card's latches): several mA in all.
V2.0 adds, on this card alone, IC33 (74LS273 D, 0.4 mA), IC40 (74LS244 A, 0.2 mA), IC51 (74LS374 D, 0.4 mA) and four
3-state outputs: ~1.1 mA a line (TI LS IIL).

**Consequence.** By specification the 6845 already cannot pull the loaded bus to 0.4 V; the bench shows it works (v1.2:
`crtcreg.img` read R14/R15 256 times, the text RAM 8/8), with an unknown noise margin. V2.0 should not take more of it.

**Fix.** IC33 a **74HCT273**, IC40 a **74HCT244**, IC51 a **74HCT374** (also V2-9): their inputs draw ~1 uA, so V2.0's own load
on DATA0..7 is gone. At the bench, measure the low level on DATA0 during `IN PB` and during a text-RAM read with the
whole machine fitted (below 0.8 V is a pass; above 0.5 V means a data-bus buffer for the next revision).

---

## LOW

### V2-13 LOW — Graphics writes in 6-dot mode

**Evidence.** Line 236 / the timing table: -WE = NAND(WRQ, NOT QC, QA XOR QB, GWR). In 6-dot mode the CPU half is
counts 10-11 and QA XOR QB is 1 only in count 10, which is also when WRQ is sampled (CHARCLOCK's rise): -WE opens when
WRQ arrives (50-105 ns) and closes at 98-145 ns: ~70 ns typical, a few ns at the corners, with IC40's data at the RAM
~75 ns typical.

**Consequence.** The design notes say "in 6-dot mode the graphics layer never shows; the CPU can still fill it": it
usually can, but not by specification (tWP 45, tDW 25). Reads in 6-dot mode are fine (with the -55 RAM).

**Fix.** Document "graphics RAM is written in 8-dot mode only" (the ROM driver refuses graphics in 6-dot mode). A real fix
would sample WRQ a dot earlier (on RCO's rise) - not worth a gate.

### V2-14 LOW — `INP` drops the strobe and the port number together

**Evidence.** `test.hex`, record `INP Pn` ($90-$9F, 0-based steps): IO-ADDR from step 3, -IO-RD in steps 5-8, and step 8
is the one-clock `UCODE-COUNT-RESET` step, so -IO-RD rises on the same pipeline edge that returns IO-ADDR to 0000 (the
next fetch). `OUTA`/`OUTI` hold the port number two steps after -IO-WR. Going from PB (1011), PD (1101) or PF (1111)
to 0000, the bits can pass through 1001 = **P9, the CF data port**, and from PE (1110) through 1010 (PA).

**Consequence.** A glitch read of P9 would advance the CompactFlash's sector buffer (a lost byte in a disk read if the
keyboard is polled with `IN PD` during a transfer). In practice the 74LS138s' 20-40 ns decode delay is longer than the
skew between the pipeline's outputs, so the late decode meets a strobe that has already risen; on this card the same
applies to a stray -CS of the 6845 at the end of `IN PE` (a read: harmless).

**Fix.** Machine-wide, in the microcode (`io.c` INP): one more step with the port number and without -IO-RD before the
record ends, as the OUT records have. Until then the decoders' delay is the margin; nothing on the card to change.

### V2-15 LOW — The 6845's R/-W changes with E

**Evidence.** Lines 192 and 235: R/-W = -IO-WR, E = -IO-RD XOR -IO-WR (IC26/C). On a write R/-W falls one XOR delay
(12-23 ns) before E rises; MC6845 address (RS, CS, R/-W) set-up to E rising: 70-160 ns depending on grade (To verify).
RS and -CS are set two steps (4 us) ahead.

**Consequence.** A specification violation, but the same scheme on memory strobes (V1.2 bench fix, 2026-10-21) wrote
and read every register at speed: the 6845 latches the write at E's fall, 2 us later.

**Fix.** None for ordering; scope E against R/-W at the first `OUT PB`.

### V2-16 LOW — Three decoupling capacitors are far from their VCC pins; little bulk

**Evidence.** Board pad positions: C18 at (73.4, 45.0), beside the 6845's pin 40 corner; its VCC is **pin 20** at (55.0,
93.3): 48 mm. C49 at the ATmega's pin-28 corner, 17 mm from VCC pin 7 (C54 sits 3 mm from AVCC). C22 at the 74LS90's
pin-14 corner, 13 mm from its VCC, **pin 5**. All other 100 nF are 3.2 mm from their VCC pin. Bulk: C16 10 uF only, for
~1 A (V2-19).

**Consequence.** The planes keep this from being serious; the 6845 (NMOS, the card's busiest bus driver) and the
ATmega are the two parts that most want their own capacitor.

**Fix.** Place C18 at IC17 pin 20 / 1, C49 at IC49 pins 7 / 8, C22 at IC21 pins 5 / 10 (the "VCC corner" rule in
`gen_v20.py` PLACE does not hold for these packages). Add a 47-100 uF electrolytic near X1 (or make C16 47 uF).

### V2-17 LOW — PS/2 power unfused, PS/2 lines unprotected

**Evidence.** Line 310: J2 and J3 pin 4 on VCC; lines 308-309: clock and data straight to ATmega pins with only the
4.7k pull-ups.

**Consequence.** A pinched PS/2 cable or a faulty device shorts the machine's 5 V rail; an ESD hit on a jack goes to
the ATmega's pins.

**Fix.** A 0.5 A PTC fuse (e.g. a radial 0.5 A hold) from VCC to J2.4 and J3.4, as PC motherboards have; optionally
100-220 ohm in series with the four PS/2 lines at the ATmega side of the pull-ups.

### V2-18 LOW (firmware) — Robustness of `video-ps2`

- The ISR (`ps2_edge`) calls `micros()` and `digitalRead()` through `attachInterrupt`: ~10-15 us an edge. Both ports
  and the timer-0 ISR together approach the PS/2 clock's 30 us minimum low time, inside which the data bit must be
  read. Read `PIND` directly and time-stamp with `TCNT1` (or keep `micros()` but read the data bit first).
- `ps2_wait()` takes whatever byte arrives: a scan code typed while `send_leds()` waits for $FA is consumed and the
  command reported failed (a lost key with Caps Lock).
- The mouse's 16-byte ring overflows during the up to ~140 ms of LED commands (100 packets/s); `mouse_byte()`'s bit-3
  resynchronisation is weak (X/Y bytes often have bit 3 set): an overflow can misalign packets. Drain the mouse ring
  inside `ps2_wait()` or make it 64 bytes.
- `md_release()` leaves MD0..7 floating CMOS inputs between transfers (see V2-9's fix).
- Ctrl-Break (E0 7E) toggles Scroll Lock (the `0x7E` test comes before the extended-key branch); a fake `E0 59` changes
  `rshift`. Test `e` first.
- `feed_cpu()`'s comment says the read strobe lasts ~2 us; `INP` holds -IO-RD for 7 clocks (7 us at 1 MHz). The code is
  still safe - the load happens 12 us or more after FULL clears, and a load inside a strobe is detected and repeated -
  but the comment should say so.
- A VT100 key sequence is queued byte by byte (`qput` drops a byte when full): check `qfree() >= 4` first.

### V2-19 LOW — Supply current

**Evidence.** ICC per part (TI LS; NMOS/CMOS parts To verify):

| Parts | typ (mA) | max (mA) |
|---|---|---|
| 74S85 (IC18) | 73 | 115 |
| MBM2732A (IC25, NMOS) | ~100 | ~125 |
| MC6845 (IC17, NMOS) | ~80 | ~120 |
| IDT7134 (IC15) | ~100 | ~250 |
| 62256 (IC39, AS6C62256-55, always selected and cycled) | 15-30 | 45 |
| 4 x 74LS374 (disabled outputs) | 108 | 160 |
| 3 x 74LS244 (disabled outputs) | 96 | 162 |
| 4 x 74LS157 | 39 | 64 |
| 7416 (IC27) | 30 | 51 |
| 74LS163, 2 x 74LS166, 74LS174, 74LS175, 74LS273, 74LS90 | 113 | 184 |
| the 18 small gates and flip-flops (LS00/04/08/10/20/32/74/86/138, ALS08) | 60 | 105 |
| ATmega328P at 16 MHz | 10 | 15 |
| PWR LED, video/sync pull-ups R11/R12 | 25 | 35 |
| **card** | **~0.85 A** | **~1.45 A** |
| keyboard + mouse on J2/J3 | 0.05-0.2 A | up to ~0.55 A |

X1 has six VCC and six GND pins (lines 151-152): with DIN 41612 contacts rated ~1-2 A each, the connector is not the
limit. The machine's 5 V supply is: V2.0 adds ~0.3-0.5 A to what the V1.0 card drew, plus the PS/2 devices.

**Fix.** Check the supply's rating against the whole machine. Cheap savings: IC18 a 74LS85 (the bus gives a whole step;
LS85 ~25-35 ns is plenty, -60 mA), IC25 the CMOS AT28C64B of V2-10 (-80 mA).

### V2-20 LOW — Silkscreen

**Evidence.** `reports/drc.json`: `text_height` on "GND CTS - TX RX DTR" (the J4 legend) and X1's pin numbers;
`silk_overlap` with reference fields of IC49 (R12), IC53 (IC49's outline), IC25 (IC39), D1 (R16), R16 (C57), JP3 (its
"INT-EN" label), C19 (SV3), JP2 (IC25), SV4 (Q2); 76 `silk_over_copper` (capacitor outlines over IC pads; the fab clips
them) and 8 `silk_edge_clearance` (X1, X2, J1 outlines at the edge).

**Consequence.** Only the J4 legend matters: an FTDI cable plugged the wrong way round puts its TXD on GND. The rest is
cosmetic, except that unreadable references slow down the build.

**Fix.** J4 legend at least 1.0 mm high with "GND (BLK)" at pin 1; move the overlapping reference texts; leave the
silk-over-pad and edge items.

### V2-21 LOW — No V2.0 bill of materials

**Evidence.** `docs/bom/video.md` is generated from the V1.0 Fusion export (47 parts); V2.0 has 108 footprints.
`v20_netlist.PARTS` gives: 38 ICs (14 DIP-14, 11 DIP-16, 8 DIP-20, one each DIP-24 600 mil, DIP-28 600 mil, DIP-28 300 mil,
DIP-40, DIP-48), 40 x 100 nF, 2 x 22 pF, 1 x 10 uF, resistors 3 x 1k, 33, 270, 330, 5 x 4.7k, 10k, a 10k x 4 SIP-5,
crystals 12 and 16 MHz, 1N4148, LED, DB9 F, RCA, 2 Mini-DIN-6, a 1x6, two 1x2, a 1x3 and a 2x4 header.

**Fix.** Generate `docs/bom/video-v2.0.md` from `PARTS`, with: sockets for every IC (the 6845, the 7134, the EPROM, the
62256 and the ATmega at least); the 62256 in the **600-mil** package (AS6C62256-55PCN; "skinny" 300-mil 62256s exist);
the 6845 grade (V2-11); the HCT parts (V2-9, V2-12); a 5 V FTDI adapter (the ATmega's RXD needs 3.0 V; TTL-232R-5V or a
5 V FTDI Basic). Parts to buy as new-old stock: MC6845/HD6845, IDT7134 (or move the V1.0 card's chip), 74S85 (or the
74LS85 of V2-19), MBM2732A (or the AT28C64B of V2-10); the rest is in production or in 74HCT.

### V2-22 LOW — BUSY clears when the ATmega starts reading the command

**Evidence.** Line 312 and `read_command()`: RDCMD low is both IC51's -OE and IC53/B's -CLR; the firmware holds it low
~1 us plus two `digitalWrite`s (~4 us). A CPU that sees BUSY = 0 and writes the next command at once can overwrite
IC51 while the ATmega reads it (and the CMDCLK edge then cannot set BUSY, CLR being low).

**Consequence.** None at 1 MHz: from `IN PD` to the next `OUT PD`'s strobe is tens of microseconds. At 6 MHz it can
happen.

**Fix.** A software rule for the driver: one `OUT PD`, then wait for BUSY = 0 (the README's protocol already says so).

### V2-23 LOW — VSYNC fan-out

**Evidence.** Line 196: VSYNC drives IC27.3 (7416 input, standard TTL, 1.6 mA), IC34.4 (LS244, 0.2 mA, new in V2.0) and
the DB9 pin 9 cable; the 6845's outputs are rated for one TTL load (MC6845; To verify).

**Consequence.** Slightly over the rating; the v1.x card drove the 7416 and the monitor without trouble.

**Fix.** None needed; if VSYNC's low level is poor at the bench, take IC34's bit 1 off VSYNC (tie it low) or buffer it.

---

## INFO

### V2-24 INFO — How fast the CPU may run with the graphics window

- **Reads.** IC41 reloads at every QC rise from whatever address the CPU puts on the RAM in the CPU half; nothing
  depends on the strobe. From the moment the address is valid at the card, the worst case is waiting one character for
  the next CPU half that is entirely after it: T(char) + 157 data path (14) + tAA (55) + set-up (20) + the 374's
  CLK->Q (28) + the bus (~30) = **814 ns in 8-dot mode, 647 ns in 6-dot**, plus ~70 ns for the address to arrive after the
  step edge (pipeline + register card). The shortest data-read windows in the microcode (address stable to the edge that
  takes the byte) are **2 clocks** (RET, POPR, IRET, LDT, BRVR's indirect read; all others 3 or more), so reads work up
  to about 2.2 MHz (8-dot).
- **Writes.** GWR must be high at a CHARCLOCK rise and stay high to the end of count 10: decode (~90 ns) + set-up (20) +
  up to one character (667) + counts 8-10 and -WE's rise (~310) = **~1.1 us**. Every -MEM-WR in the image is exactly 2
  clocks, so writes need a clock of **at most ~1.8 MHz**. This is the real limit; the README's "~1.4 us read strobe, fails
  above ~1.5 MHz" is on the safe side and correct in its conclusion. At 1 MHz the 2 us strobe holds two or three complete
  write slots (the byte is written two or three times) and the read margin is over 1 us.
- **At 6 MHz** (a step 333 ns): graphics reads return the byte of an earlier address and writes are lost about half
  the time or written with a runt -WE - the graphics window is unusable; the text RAM (dual port) works; the PS/2
  latches work; the 6845 needs E high for 333 ns (one -IO-WR step), below the MC6845's 450 ns: fit an MC68B45 or HD6845S.

### V2-25 INFO — An old ROM with V2.0 fitted

Verified: the $D000 probe finds the text RAM; the 6845 table goes into graphics RAM page 0, plane 0, offsets 0 and 2;
`$D801` reads a graphics byte through IC41, which drives DATA only during that -MEM-RD; nothing else on the card answers
$D800-$DFFF or any memory address, so no bus fight. No picture until the V2.0 ROM: the 6845 runs on its reset contents,
so keep a monitor that dislikes a wrong line rate (an MDA monitor) unplugged until then. With **JP3 fitted** the
ATmega's boot asserts -INT for ~1.4 s (V2-7) and the monitor's ISR runs continuously: build the card with JP3 open.

What the V2.0 driver needs: `IN PC`, (v AND $F0) = $50 (a floating bus reads the opcode $9C, or $00 / $FF, so $5x is
safe; also check bit 3 = 0), bit 0 for 80 x 24 (1) or 64 x 24 (0), the 6845 through `OUT PA` / `OUT PB`, `OUT PC` = 0 is
already the reset state (74LS273 cleared by -RESET: plane 0, pages 0, text on, graphics off, OR), the keyboard through
`IN PD` / `IN PE` behind CONST/CHARIN, `$02` (interrupts off) at boot unless the driver handles -INT. PF is spare
(IC30's Y7 unconnected: `IN PF` reads the floating bus, `OUT PF` does nothing).

### V2-26 INFO — Interrupts

-INT is open collector (IC27/D, 7416) through JP3, wired-OR with the I/O card's 7406 and pulled up by that card's RN2
(value not recorded: io.md "To verify"). The protocol is level-shaped (low while a byte waits and interrupts are on;
released by reading PE or $03), so the sequencer-logic card's JP3 must be in **level** mode; edge mode registers the
*release* of -INT (control-io review 1.6) and would enter the handler after the byte has been read. No acknowledge
cycle is needed (the INT record asserts no -INTA). This card is the first -INT source likely to be enabled, so review
M-6 (DO-INT not synchronised to the clock: an interrupt in the set-up window of LD-INS-REG can load a mixed opcode)
stops being theoretical.

### V2-27 INFO — The 2K wrap

The graphics address uses MA0..10 (lines 259-262), the text RAM MA0..11 with the CPU reaching only its lower 2K. A
start address (R12/R13) with start + R1 x R6 above 2048 makes the text show the unreachable upper half and the
graphics wrap to plane offset 0: scroll in software, as the ROM does. `vidsim.py timing` warns about it.

### V2-28 INFO — PS/2 start-up time

After a bus reset: Optiboot ~1 s (external reset), then `keyboard_reset()` (the keyboard's BAT, 0.3-1 s) and
`mouse_start()` (up to ~1.1 s; ~40 ms with no mouse). The keyboard is usable 1.5-2.5 s after reset; the ROM must poll,
not wait, and must not treat FULL = 0 at boot as "no card".

### V2-29 INFO — Clock routing

From the board: DOTCLOCK 201 mm (no vias), CHARCLOCK 194 mm (3 vias), CRTCCLOCK 209 mm (2 vias), XTAL 76 mm, the Q2
oscillator nets 33 mm each, XT1/XT2 19-20 mm (Y1 10 mm from IC49 pin 9). Over a solid GND plane, 200 mm is ~1.3 ns of
flight against LS edges of ~5-10 ns: below the critical length, no termination needed. Look for ringing at the far
ends (IC43 pin 7, IC42 pin 11, IC17 pin 21) at the bench; Q2's oscillator is the v1.x Pierce with 1k resistors, not
sensitive to 33 mm.

---

## Verified OK

- **Netlist integrity.** `v20_netlist.check()` OK (108 parts, 206 nets, 874 connections); schematic = board (206 of 206
  net groups, `netlist-compare.txt`); DRC 0 unconnected, no clearance / short findings, parity 0; ERC 6 off-grid only.
- **Every IC re-derived pin by pin** against the TI pinouts (and the MC6845, IDT7134, 2732, 62256, ATmega328P DIP
  pinouts): 74S85 A/B/cascade pins, 74LS157 sections (S = 0 -> A = CPU), 62256 A0..A14 / DQ / -CE / -OE / -WE, 74LS374
  and 74LS273 D/Q pairs, both 74LS244s' 1A/1Y and 2A/2Y halves (IC34 reads DOTS, VSYNC, DE, 0, 0101), 74LS74 halves,
  74LS20, 74LS10, 74LS138 (A/B/C = IO-ADDR0..2, G1 = IO-ADDR3, Y2..Y7 = PA..PF), 7416 sections, 74LS163 load value
  1 0 DOTS 0 = 8 / 10, 2732 A10 = DOTS, the ATmega's port pins against the firmware's table.
- **Nothing floats.** Every unused gate input is tied (IC19/D, IC32/C,D, IC27/E,F, IC44/B, IC45/B, IC48/C, IC38 section d);
  IC21 pins 4/13 and IC45 pins 3/11 are no-connect pins of the 7490 and 7420 packages; the other open pins are outputs.
  The only open inputs are the ATmega-driven nets during the ATmega's reset (V2-7) and MD between transfers (V2-18).
- **No outputs tied together** except the intended open-collector nodes (IC27/B + IC27/C on SYNC; IC27/D with the I/O
  card's 7406 on -INT) - and the bootloader case of V2-1.
- **IC2, JP1, R13, R14 are gone cleanly.** A diff of the v1.3 and v2.0 netlists shows every connection of the kept parts
  that changed, and they are exactly the README's list (IC1's four gates, IC17 RS / R-W / E / -CS, IC19/A and /D,
  IC26/C and /D, IC27/D-F, the video NAND moved from IC19/D to IC48/B); nothing dangles.
- **Bus pins** (X1) against BUS.md: ADDR0..15 A3-A18, DATA0..7 A19-A26, -MEM-RD/-MEM-WR/-IO-RD/-IO-WR B23-B26,
  IO-ADDR0..3 C7-C10, -VMA C12, -INT C13, -RESET C30, VCC A2/B2/C2/A31/B31/C31, GND A1/B1/C1/A32/B32/C32.
- **Board select.** 74S85 A = SV3 (5-6 fitted = 1101 = $D), B = ADDR12..15, A=B input = VMA (IC20/F), A<B and A>B inputs
  low: BOARDSEL only for $Dxxx with -VMA asserted.
- **Every driver of DATA0..7 has a strobe term** - the lesson of 6.4 and of the latch -OC of 2026-10-11/21: IC15 (-OER =
  -MEM-RD, with -CER), IC17 (E = the I/O strobe, with -CS), IC34 (PSEL_C OR -IO-RD), IC41 (NAND(GSEL, NOT -MEM-RD)), IC50
  (PSEL_E OR -IO-RD), IC52 (PSEL_D OR -IO-RD). A write to $D800-$DFFF or to any port turns none of them on.
- **Ports.** PA-PF are fully decoded and overlap neither the I/O card (P0-P7, its IO-ADDR-HL strap: to verify on the
  board) nor the CF interface (P8/P9 on its own 74LS138 with G1 = IO-ADDR3). In `test.hex` the port number is set two
  steps before every strobe; OUT strobes end two steps before it changes, with the data (ACC in `OUTA`, memory in `OUTI`)
  on the bus throughout; latches take the trailing edge (CTLCLK, CMDCLK = select OR -IO-WR).
- **The 6845 on PA/PB.** -CS = PSEL_A AND PSEL_B (address only, settled 4 us before E), RS = IO-ADDR0 (PA even, PB odd),
  R/-W = -IO-WR, E = -IO-RD XOR -IO-WR: high 7 us for `INP`, 2 us for `OUT` (MC6845 PWEH 450 ns), low for microseconds
  between I/O instructions (PWEL 430 ns); write data on the bus from step 3 (set-up ~195 ns needed) and two steps after
  (hold 10 ns); read data needed 2 us after E rises (access 320 ns). LPSTB to GND, -RES on -RESET (review 6.5 and the
  bench fixes carried).
- **The status buffer** IC34 and the card ID $5x; **the control register** IC33 bit order against `vidsim.V20Control`;
  reset defaults (text on, graphics off, plane / pages 0; WRQ and FULL cleared).
- **The slot logic in 8-dot mode** (timing table): -WE 167 ns (tWP 45), address set-up and recovery (tAS, tWR 0; tAW
  230 ns), data set-up 135 ns (tDW 25), the CPU read latch's set-up 190 ns, the display read in the display half, no CPU
  access ever disturbs a display read (no snow), a write never starts mid-slot (WRQ sampled at the slot start) and ends
  with the strobe (GWR in the NAND), the 2-3 repeated writes harmless.
- **Pipeline alignment.** Text: code latched at the end of character N (IC23), EPROM, loaded into IC24 at the end of N+1,
  shown in N+2. Graphics: display byte of N latched at the end of N (IC42), loaded into IC43 at the end of N+1, shown in
  N+2. DE and the cursor/attribute through IC22's two stages: the same N+2. Both shifters on the same DOTCLOCK and
  CHARCLOCK; the text and graphics combine paths differ by one gate (a few ns of an 83 ns dot).
- **The combine** (IC1/C,D, IC46/D,E, IC47/A, IC32/B, IC48/A,B) against its truth table: TDG = dot AND NOT TEXT-OFF, GDG =
  dot AND GFX-ON AND 8-dot, OR or XOR, gated by the delayed DE; both layers off = black with sync running.
- **Video levels** (IC27/A open collector, R11 33, R12 270, unchanged from v1.x): into a 75 ohm composite input sync 0 V,
  black ~0.39 V, white ~1.09 V; the TTL DB9 sees the same nodes as on the V1.0 card.
- **Fan-out on the card.** QC 10 LS unit loads (4 x 157 select at two each, IC46, IC41), CHARCLOCK 7, RCO 2, DOTCLOCK 3,
  DE 2, the MA/RA lines one LS input each; the R10 (1k) and R15 (4.7k) pull-ups hold their loads above 4.6 V.
- **PS/2 hardware.** Jack pinout (1 data, 3 GND, 4 +5 V, 5 clock, shield GND), 4.7k pull-ups, open-drain emulation
  (the firmware only ever switches a pin between input and output-low), clocks on INT0/INT1.
- **PS/2 firmware** (apart from V2-3 and V2-18): 11-bit frames, odd parity, stop bit, 2 ms frame timeout, the
  host-to-device sequence (120 us clock low, start bit, bits on the falling edges, release for the stop bit, the
  acknowledge), set-2 translation spot-checked against the standard table (letters, digits, punctuation, keypad with Num
  Lock, extended arrows / Home / End / PgUp / PgDn / Delete / keypad Enter and /, Pause and Print Screen swallowed),
  mouse reset / $F4 / 3-byte packets queued whole, the 64-byte queue, the FULL / LDDATA race (a load that overlaps a
  read strobe is detected and repeated).
- **The latch protocol at 1 MHz.** The CPU never waits; a byte loaded during an `INP PE` can only land after the ACC has
  taken the old one (the ATmega needs 12 us or more after FULL clears, the ACC samples 2 us into the strobe).
- **ATmega support.** FTDI J4 in the FTDI-cable order (GND, CTS, VCC, TXD, RXD, DTR): the cable's TXD to PD0/RXD, its
  RXD from PD1/TXD, CTS grounded, VCC not connected (the card is powered by the bus only), DTR -> 100 nF -> RESET with the
  10k pull-up (a 1 ms pulse); 16 MHz with 22 pF (the Uno's values); AVCC on VCC with its own 100 nF 3 mm away; AREF open
  (no ADC use); the ISP path off the card (and in-circuit ISP would fight the latches on PB3-PB5 anyway: socket IC49).
- **Power and planes.** Every IC has its 100 nF (39, plus C54 for AVCC); every power pin reaches its plane; no power
  track; 4 layers.

## At the bench first

1. **Before the chips:** VCC-GND resistance; then power with sockets only, then with all chips but the ATmega: the
   supply current (~0.8 A expected).
2. **The bus stays quiet:** with the card in the machine, `tests/memory/memory_full_test.py` and
   `tests/video/video_ram_test.py`, and a scope on DATA0 during ROM reads - nothing on this card may drive outside its
   strobes. Check the I/O card's IO-ADDR-HL strap (P0-P7).
3. **Ports:** `IN PC` returns $5x with bit 0 = DOTS; `OUT PC` patterns at IC33's outputs.
4. **The 6845 through PA/PB** (`crtcreg.img` moved to I/O): scope E against R/-W (V2-15); in 6-dot mode the low width of
   QC at IC17 pin 21 (V2-11); then the test card in both modes; the low level on DATA0 during `IN PB` (V2-12).
5. **Graphics at 1 MHz:** a write / read-back pattern over both 16K pages; scope -WE (IC45 pin 6), WSLOT (IC39 pin 22)
   and a GD line for contention (V2-5); IC42 pin 11 against a GD line at the character boundary (V2-4); a graphics test
   picture for sparkle.
6. **The ATmega last**, with V2-1 settled: MRST's level with -RESET high (V2-6), INTREQ / -INT during a bus reset
   (V2-7), the keyboard, then the mouse (`$04`: needs the V2-3 fix), and only then JP3 with the sequencer in level mode.
