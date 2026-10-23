# Design re-review — video card V2.0 after its review fixes (2026-10-23)

The focused re-review the first review (`hardware/DESIGN-REVIEW-video-v2.0.md`, `fb5dd48`) asked for before ordering:
the changed slot logic, direct mode (GFX-ON = 0), the text-only build, the INT gate and the ATmega fixes, the 28C64
character generator, the HCT/LS mix, the rebuilt board, the MD-60SM footprint and the BOM, as committed in `7d3c054`,
`1f1c213`, `fc71ec4` and `ed5333e`. Findings only: no design file is changed by this review; every finding carries a
concrete fix.

**Status 2026-10-23: R2-1, R2-2, R2-3 and R2-14 are fixed in `560977b`** (the board rebuilt and routed anew,
order 6: 0 unrouted, 328 vias; netlist proof MATCH 216/216, DRC clean, `verify` PASS with 189 connections). The order
gate below is lifted; the rest are documentation, the BOM, the test model, the firmware and bench measurements.

Read and re-derived: `hardware/cards/video/kicad/v2.0/v20_netlist.py` gate by gate against the TI pinouts (every
section of IC1, IC19, IC26, IC27, IC32, IC44-IC48, IC54, the 157 sections, IC39-IC43, IC55, IC25, IC33/IC34, IC49-IC53);
`reports/netlist-compare.txt`, `drc.json`, `erc.json`; the board through KiCad 10's `pcbnew` (pad positions, track
lengths per net, the outline); `gen_v20.py` (`PLACE`, the footprint writer, `verify`'s `KEY` list); `BOM.md`; the README;
`BACKLOG.md`; `docs/cards/video.md` 7a; `embedded/video-ps2/video-ps2.ino`; `tests/video/v20_timing.py` and the
microcode image `firmware/microcode/ucode-generator2/test.hex` (decoded with `tools/ucode_wavedrom.py`'s reader, every
`-MEM-WR` and every read window re-listed independently of the test); `firmware/video/chargen-v20.bin`;
`tools/vidsim.py` V20Card. The README's claims, the commit messages and the first review's status table were not taken
as evidence.

**Data-sheet values.** AS6C62256-55 from the tree's `docs/datasheets/AS6C62256.pdf` (tAA 55, tOE 30, tOLZ 5, tOH 10,
tOHZ / tWHZ 20, tWP 45, tDW 25, tAS = tWR = tDH = 0). The MD-60SM from the Same Sky data sheet "SERIES: MD-SM", **rev
1.09 of 2024-09-12, fetched 2026-10-23** from `sameskydevices.com/product/resource/md-sm.pdf` (page 3, its drawings
read at full resolution). 74LS figures are the TI data-book typical / maximum at 5 V, 25 °C, 15 pF; 74HCT the NXP sheets
at 4.5 V (25 °C maximum, and -40..85 °C where marked); the register card's fitted 74HC193 / 74HC244 the TI SN74HC
values; none of these logic sheets was fetched for this review and the ones that decide a margin are marked **To
verify**. LS minimum delays are not specified: as in the first review, one third of typical is assumed where a race
depends on them. Delays used (typ / max, ns): 74LS163 CLK->Q rise 13/24, fall 18/27, CLK->RCO fall 18/35; LS00 9-10/15;
LS04 9-10/15; LS08 8-10/15-20; LS32 14/22; LS86 12/23; LS20 9-10/15; LS157 select->Y 15-18/23-27, data->Y 9/14; LS74
CLK->Q 13-25/25-40; ALS08 -/14; HCT08 11/24 (30 at 85 °C); HCT244 A->Y 13/25 (31), enable 15/30 (38); HCT374 set-up
12 (15), hold 5; HC244 (register card) A->Y -/30 (38), enable -/38 (48); HC193 UP->Q -/43, UP->CO -/30 (To verify).

## Summary

| ID | Sev | Finding | Fix (short) |
|---|---|---|---|
| R2-1 | MED | MD-60SM side-leg slots: by the data sheet's own leg dimensions (0.54 mm legs, 13.2 mm between their inner faces) a 0.8 mm slot on the 13.5 mm centres leaves **0.01 mm** at the outer face, before tolerances | side slots 1.2 x 2.6 mm (plated), pads 1.9 x 3.3, same centres; check against a real jack - **fixed `560977b`** |
| R2-2 | LOW | IC55 lies on its side 2.7 mm (pin row to end pins) from IC19 and IC1: their sockets collide with IC55's, and the BOM says "every IC in a socket" | move IC55 0.6 mm up (y = 78.7) in the rebuild, or no sockets on IC55 / IC19 / IC1 - **fixed `560977b`** (3.30 / 3.22 mm) |
| R2-3 | LOW | The bus -RESET gains 2.8 mA on this card (7416 1.6, LS74 CLR 0.8, LS08 0.4) on top of ~4 mA elsewhere, from one LS04 (8 mA, VOL 0.5 V max) | feed IC27/E from spare IC54/C (HCT, buffer): the bus sees an HCT input; measure C30's low level - **fixed `560977b`** (net RESETB) |
| R2-4 | LOW | 6-dot slot reads: IC41's set-up is **~2 ns** worst case (54 ns typical), not 30-40 ns; a -70 RAM fails the corner | make "GFX-ON = 0 in 6-dot mode" a driver rule that is enforced (refuse GFX-ON = 1 when IN PC bit 0 = 1) |
| R2-5 | LOW | `v20_timing.py` models the address only through the register select with LS244 figures: the fitted HC244 and a counted register (HC193 ripple) are slower; at 6 MHz the read margin is 38-60 ns on a selected register, ~0 after a count, negative when a count crosses into the window | add the count path and the HC values to the test; rule for 6 MHz: no stack and no BRVR vector in the window |
| R2-6 | LOW | IC41 and IC55 drive the backplane with 74HCT outputs (6 mA) where V2.0's first IC41 was a 74LS374 (24 mA) | measure DATA0's low level during a window read; 74ACT374 / 74ACT244 if it is above 0.5 V |
| R2-7 | LOW | BOM: IC17's value "MC6845" against its note; HD6845SP is (To verify) the 1 MHz bus grade of Hitachi's HD6845S / HD68A45S / HD68B45S, so not a "2 MHz grade"; C16 has no voltage | value HD68B45SP / MC68B45P, the plain grades for a 1 MHz CPU only; C16 47 uF 16 V |
| R2-8 | LOW | README / BOM slips: "IN PC = $58 / $59" (bits 1 and 2 are VSYNC and DE, live); the -55 RAM's stated reasons (6-dot slot reads are ruled out; direct reads at 6 MHz need tOE, not tAA 55) | the text in the finding |
| R2-9 | LOW | Silkscreen: 41 overlaps, among them "KBD (PURPLE)" on J2's reference, C58 on IC54, C59 on IC55, the R16 / C57 / R23 cluster | move the reference fields |
| R2-10 | LOW *(firmware)* | V2-18's open item (a key typed while `send_leds()` waits for $FA is taken as the answer) is still open; `feed_cpu()`'s overlap test also re-sends a byte a CPU read within ~4 us of the load | `ps2_wait()` for a reply only ($FA/$FE/$EE/$AA/$00), queue the rest; driver rule: read PE only after PD showed FULL = 1 |
| R2-11 | INFO | The switching character: GFX-ON 0 -> 1 shows the two pipeline bytes latched in direct mode ($FF from RN3) as 16 lit (OR) or inverted (XOR) dots | the driver switches GFX-ON in vertical blanking |
| R2-12 | INFO | MRST's high level rests on the 7416's off-state current (specified only at 15 V, 250 uA max) through R16 10k | measure MRST >= 4.5 V with -RESET high |
| R2-13 | INFO | `chargen-v20.bin`'s copy at $1000 is unreachable (A12 = GND) and harmless; the reached ranges $0000-$01FF / $0400-$05FF hold the two fonts | - |
| R2-14 | INFO | `gen_v20.py verify`'s 173 connections skip some nets of the fixes (J2/J3 shield pads, the MEMWR path, IC44.1, IC53/A); `text_only_check()` silently passes a left-off IC that has no `OUTPUTS` entry | add them to `KEY`; make `check()` fail on a left-off IC without an entry - **done `560977b`** (KEY 173 -> 189) |
| R2-15 | INFO | Route lengths: CRTCCLOCK 267 mm (4 vias), CHARCLOCK 220, DOTCLOCK 182, GWE 226 (7 vias), NMUX 186, GFXON 252: below the critical length for LS edges | scope the far ends (IC41.11, IC44.3, IC39.27) |
| R2-16 | INFO | F1 (MF-RHT050) drops ~0.1-0.2 V at 0.2 A; R17-R20 hang on VCC, not on PS2VCC | measure PS2VCC under load (>= 4.6 V) |

**Counts: HIGH 0, MED 1, LOW 9 (one firmware), INFO 6.**

## Verdict

**Order after the fix of R2-1** (the side-leg slots of the MD-60SM footprint: a copper change that cannot be made on a
finished board). The changed slot logic, direct mode and the text-only build are right: no logic error was found, the
V2-4 hold race is gone (>= 9 ns at the corners, ~40 ns typical, against -29 ns before), the GD bus has no driver overlap
in either mode by construction (a dot apart), direct-mode writes meet every 62256 parameter at 1 and 6 MHz with the
address and data held a whole step each side (re-derived from `test.hex`), and IC41 / IC55 can never both drive DATA.
Fold R2-2 (IC55's position) and R2-3 (IC54/C in front of IC27/E) into the same rebuild, since R2-1 needs a re-route
anyway; the rest are documentation, the BOM, the test model, the driver and bench measurements.

---

## Timing tables (12 MHz dot clock, re-derived for this review)

### Slot mode, 8-dot (counts 8..15, dot 83.3 ns, character 667 ns); t = 0 at the DOTCLOCK edge that ends count 15

| t (ns), typ (range) | Event | Check |
|---|---|---|
| 18 (6-35) | RCO and QC fall | |
| 28 (9-50) | CHARCLOCK rises (IC19/C): IC42, IC23, IC22 latch, IC44 samples GWR | |
| 32 (11-57) / 41 (14-72) | QCR falls (IC32/C) / NMUX rises (IC19/D) | |
| 59 (19-99) | GA = the CPU address (157 select->Y) | **IC42 hold**: GA moves RCO + OR + NAND + 157 + tOH 10 after RCO, the clock RCO + NAND: margin = OR + 157 + tOH = 42 typ, >= 21 with LS minima, >= 9 with the two NANDs at opposite extremes; LS374 hold 0 |
| 41 (13-90) | WRQ valid (IC44) | |
| 59 (19-116), +20 | WSLOT rises (IC54/A, IC1/B) if WRQ; RAM outputs off by 136 at most | |
| 108 (91-130) / 122 (96-152) / 132 (99-167) | count 9: WEPH (IC26/D) / WEPH2 (IC32/D) / -WE falls (IC45/A) | tAS: GA valid 59 (<= 99) before -WE falls (>= 99): >= 0 |
| ~147 (102-197) | IC40 drives GD (enable after -WE) | GD hand-over: RAM off ~70 typ against IC40 on ~147: a dot apart by construction (WEPH starts a count after NMUX) |
| 298 (266-334) | count 11: -WE rises | **tWP** 166 typ, >= 99 (45); **tDW** >= 69 (25), ~150 typ |
| 346 (337-357) | count 12: QC rises: IC41 loads (8-dot reads) | **IC41 set-up**: data at GA <= 99 + tAA 55 = 154, + 15 = 169: margin >= 168, 220 typ (the first review: 190) |
| 370 (345-394) / 388 (351-421) | NMUX falls / GA = the display address | **tWR**: >= 17 after -WE's rise; IC41 hold: >= 24 after QC (5 needed) |
| ~390 (354-433) | WSLOT falls: RAM -OE on | IC40 off by -WE + disable (<= 364, ~313 typ): a dot apart again |
| 476 at most | display byte valid at GD | IC42 at 695 (676-717): set-up >= 200 |

### Slot mode, 6-dot (counts 10..15, character 500 ns); t = 0 at the edge that ends count 15

| t (ns), typ (range) | Event | Check |
|---|---|---|
| 41 (14-72) / 59 (19-99) | NMUX rises / GA = CPU | |
| 30 (6-50) / 44 (11-72) | WEPH rises (QA falls into count 10) / WEPH2 | |
| ~51 (17-105) | -WE falls (the last of NMUX, WRQ, WEPH2) | |
| 131 (99-167) | count 11: -WE rises | width ~80 typ, none at the corners (V2-13): the 6-dot rule |
| 180 (171-191) | count 12: QC rises, IC41 loads | **IC41 set-up 2 ns worst, 54 typ** (R2-4) |
| 204 (179-228) / 222 (185-255) | NMUX falls / GA = display | |
| 310 at most | display byte valid | IC42 at 528 (509-550): set-up >= 199 |

### Direct mode (GFX-ON = 0); t = 0 at the step edge that asserts the strobe; a step is two clocks

From `test.hex` (re-listed here, not taken from the test): all 59 `-MEM-WR` strobes are one step long; in the step
before and the step after, ADDR-REG-ID, REG-RD-ID, every data source, -HL-SWAP, the ALU code, -VMA and the operand
select are the same as in the strobe step; none sits in a reset step; none has `-2-BYTE-OPERAND-SEL`; no address
register is counted or loaded in the step before or in the strobe step. No data driver starts in the step after a
memory read except after reads of [PC] (BR*, LDIVR), which never address the window.

| | 1 MHz (step 2000 ns) | 6 MHz (step 333 ns) | the test's 6 MHz figure |
|---|---|---|---|
| -WE falls after the step edge (pipeline 28 + LS04 + LS08 + LS20) | <= 78 | <= 78 | 78 |
| tWP (45) | >= 1938 | >= 271 | 255 |
| tDW (25): IC40 on 30 after -WE | >= 1908 | >= 241 | 225 |
| tAS / tWR (0): address stable since the previous step edge + ~118 / until the next step edge + ~30 | >= 1880 / >= 1950 | >= 215 / >= 285 | 333 / 255 |
| read, register selected in the step (register card LS139 + **HC244** enable 38, S85, LS08, LS00, HCT08, ALS08, tOE 30, HCT244, bus 5, set-up 20) | margin ~1.7 us | **60 ns** (25 °C maxima), **38 ns** (85 °C HC/HCT) | 72 |
| read, register counted at the step edge (HC193 ripple to the 4th chip, ~215 ns to the bus) | ~1.6 us | **~0** (address path 334); **-51** if the count crosses into the window (GSEL path) | not modelled (R2-5) |
| IC55 enabled (GSEL + LS20 + HCT244 enable) | 185 | 185 (before the byte: it passes $FF from RN3 first) | 177 |
| AS6C62256-70 / -100 instead of -55 (tOE 35 / ~50) | fine | select path 55 / ~40 ns | - |

---

## MEDIUM

### R2-1 MED — The MD-60SM's side-leg slots are too narrow for the legs the data sheet draws

**Evidence.** `gen_v20.py` `MINIDIN_SLOTS`: side slots `(-5.5, +-6.75, 2.3, 0.8)` (drill 2.3 front-to-back x 0.8
across, pad +0.7), i.e. 13.5 mm between centres, 5.5 mm behind the face; on the board J2's at (230.67, 63.25) and
(230.67, 76.75), J3's at 81.25 / 94.75, all on GND. The data sheet (rev 1.09, page 3), read at full resolution:

- *Recommended PCB Layout, Top View (Date Codes after 03/03/2022)*: six holes, dia 0.9 +0.1/-0; pins 6 / 5 at 11.0 behind
  the datum line, 4 / 2 / 1 / 3 at 8.5; outer pins 6.8 apart, pins 2 and 1 2.6 apart; the earth slot 2.2 +0.1 x 0.7
  +0.1, centre 4.7 behind the line; the two side slots 13.5 apart (centres), 5.5 behind the line, **drawn but not
  dimensioned**; the datum line is the front of the housing.
- *Front view* (MD-60SM): the shield's legs are **0.54** thick, **13.2** between their inner faces (so 13.74 between
  their centres and 14.28 across their outer faces), 3.5 +-0.5 below the board line; general tolerance +-0.3, PCB
  +-0.1.
- *Side view*: each side leg is **2.0** wide front-to-back, centred at 5.5; the earth terminal is a thin blade at 4.7.

A leg spans 6.60..7.14 mm from the centre line; the slot 6.35..7.15. At the outer face that is **0.01 mm** nominal,
less the fab's plated-slot tolerance (typically +-0.1-0.15) and the part's +-0.3. Lengthwise 2.0 in 2.3 is 0.15 a side.
The earth slot (0.8 x 2.3 for a ~0.45 x 2.0 blade) and the 1.0 mm signal holes (0.4 mm pins) are fine.

**Consequence.** The legs are likely to bind: the jack then has to be pressed in with the legs bent inwards, or the
legs trimmed, which leaves the plug's insertion force on the six signal pins and the earth blade. Not repairable in
copper after fabrication.

**Fix.** In `MINIDIN_SLOTS` make the side slots `(-5.5, +-6.75, 2.6, 1.2)`: drill 2.6 x 1.2 plated, pads 3.3 x 1.9
(J2's lower and J3's upper pad stay 2.6 mm apart), centres unchanged (the data sheet's 13.5; the legs then sit 0.21 mm
inside the outer wall and 0.45 mm inside the inner). Before ordering, if a jack is at hand, measure the outer span of
the legs (14.28 expected), their thickness and width; Same Sky's downloadable footprint ("PCB Footprint" on the data
sheet) gives a second opinion on the slot size. Keep the rest of the footprint: it matches the drawing (positions,
numbering, earth slot, datum at the board edge; see Verified OK).

---

## LOW

### R2-2 LOW — IC55's socket does not fit between IC19 and IC1

**Evidence.** `PLACE["IC55"] = (156.0, 79.3, 90)`: on the board IC55's lower pin row is at y = 79.3, the end pins of
IC19 (156.0, 82.0) and IC1 (170.0, 82.0) 2.7 mm below. A 300-mil DIP socket's side wall is 1.2-1.3 mm outside its pin
row, a socket's end wall 1.3-1.9 mm beyond its last pin: 2.5-3.2 mm needed. The courtyard check passes because KiCad's
DIP courtyards are ~1 mm. `BOM.md`: "every IC in a socket".

**Consequence.** With most sockets IC55's and IC19's / IC1's sockets touch or overlap; the build stops at assembly.

**Fix.** In the R2-1 rebuild move IC55 0.6 mm up (`(156.0, 78.7, 90)`): IC42's last pin (67.86) then leaves 1.9 + 1.3
mm above and 1.9 + 1.3 below as well. Otherwise solder IC55 (or IC19 and IC1) without sockets and say so in `SOCKETS`.

### R2-3 LOW — V2.0's load on the bus -RESET

**Evidence.** `-RESET` (C30) is one 74LS04 output on the sequencer-logic card (BUS.md). V2.0 puts on it IC27/E's input
(7416, standard TTL: 1.6 mA), IC44/A's -CLR (LS74: 0.8 mA), IC47/D (LS08: 0.4 mA), IC33's -CLR (HCT) and the 6845: 2.8
mA, where V1.x had the 6845 only. The other cards: the memory card's LS74 preset (0.8), the ALU's clear, the I/O card's
7406 input (1.6), the sequencer's two 74*175 clears; the register cards' CD4077 draws nothing: about 4 mA.

**Consequence.** ~7 mA against the LS04's 8 mA, where its VOL is 0.5 V maximum: within the specification, with less
margin on the machine's one reset line than before.

**Fix.** Buffer IC27/E's input with the spare IC54/C (74HCT08): IC54.9 = -RESET, IC54.10 = VCC, IC54.8 = new net
RESETB -> IC27.11 (instead of -RESET); the bus then sees 1.2 mA from this card. At the bench, measure C30's low level
with every card fitted (below 0.5 V).

### R2-4 LOW — Slot reads in 6-dot mode have no set-up margin at the corners

**Evidence.** The 6-dot table: GA reaches the CPU address 99 ns after the edge at the latest (RCO 35 + OR 22 + NAND 15 +
157 27), the -55 RAM's data 154, IC41 (74HCT374) needs 15 ns of set-up at 85 °C, and QC rises 171 ns after the edge at
the earliest (167 + a third of 13). **2 ns** worst case, 54 typical. The first review's "30-40 ns" left out the max
path through the new select (V2-4 added the OR and the NAND).

**Consequence.** Only with GFX-ON = 1 in 6-dot mode, where the layer is never shown; the README's rule ("software keeps
GFX-ON = 0 there") avoids it, and the 6-dot write pulse (V2-13) needs the same rule. A -70 RAM fails this corner.

**Fix.** Make the rule a hard one in the ROM driver: never set GFX-ON while IN PC bit 0 = 1 (6 dots). Then neither 6-dot
item needs hardware, and the -55 grade is no longer needed for it (R2-8).

### R2-5 LOW — The direct-mode test models only the selected-register address path

**Evidence.** `tests/video/v20_timing.py` `T`: `reg=38 + 30` (74LS139 and a 74LS244 enable) for every read window, from
the step edge at which the address became stable. The register cards are fitted with SN74HC244N address buffers (enable
38 ns at 25 °C, 48 at 85 °C, TI) and SN74HC193N counters (register.md). In the one-step windows the test finds, many
start with a **count** of the address register at the step edge (`-REG-UP/-DN` released): PC for the fetches
(BR*, JSR, ADDIW, IADDR, the operand reads), **SP for RET:9-10, IRET:9-10, POPR:19-20**, and **Rn for BRVR Rn's second
byte ($D9-$DF:6-7)**. After a count the address reaches the bus through the HC193 ripple (pipeline 28 + the card's OR
~20 + up to three UP->CO stages and a UP->Q, ~133 + the HC244 30): ~215 ns, not 96. The temperature range of the HC/HCT
parts is not in the test either.

**Consequence.** At 6 MHz: 60 ns of margin on a selected register at 25 °C maxima, 38 ns at 85 °C (the README's 72);
**about 0** for a data read right after a count, and **-51 ns** if the count crosses into the window ($D7FF -> $D800,
GSEL's path). Code fetches never address the window; the cases that matter are a stack or a BRVR vector table in the
window at 6 MHz. At 1 MHz everything has more than 1.5 us.

**Fix.** Add a `count` term (and the HC244 / HCT 85 °C values) to `T`, compute the counted windows separately (the test
already knows them: `moves_addr`) and print both margins. Driver / OS rule for 6 MHz: no stack and no BRVR vectors in
$D800-$DFFF. (The main memory card has the same count windows; review M-2's ~6 MHz limit is the same effect.)

### R2-6 LOW — IC41 and IC55 are 6 mA drivers on the backplane

**Evidence.** IC41 74HCT374 and IC55 74HCT244 put the window byte on DATA0..7 (`v20_netlist.py` lines 315-323). NXP
74HCT374 / 74HCT244: IOL 6 mA at VOL 0.33 V (25 °C) / 0.4 V (85 °C). V2.0 as first designed had a 74LS374 (24 mA) at
IC41; the change to HCT (for the GD side) also changed the bus side. A DATA line carries several mA of LS inputs on the
other cards (the first review's V2-12 estimate: ~15 inputs).

**Consequence.** A DC low level near 0.4 V on a loaded bus, less noise margin than the memory card's 74LS245 gives. Still
stronger than the 6845 (1.6 mA) and the IDT7134 (4 mA) on the same lines, which work.

**Fix.** At the bench (step 6 below) measure DATA0's low level during a window read in each mode; above 0.5 V fit
74ACT374 / 74ACT244 (TTL inputs, 24 mA) in the same sockets.

### R2-7 LOW — BOM: the 6845's grade and value, C16

**Evidence.** `v20_netlist.PARTS["IC17"]` value "MC6845"; `BUY["IC17"]`: "HD6845SP (Hitachi) or MC68B45P (2 MHz grades,
...)". Hitachi grades its 6845 like Motorola: HD6845S, HD68A45S, HD68B45S for 1.0, 1.5 and 2.0 MHz bus timing (To
verify against the sheet of the part bought); a 6 MHz CPU's `OUT` gives E 333 ns high, which needs the B grade's
PWEH (220 ns), not the 1 MHz grade's 450 ns. C16 "47u" has no voltage.

**Fix.** Value "HD68B45SP / MC68B45P"; note: "HD6845SP / MC6845P only with a 1 MHz CPU (and V2-11's clock-low check in
6-dot mode)". C16: 47 uF, 16 V or more, 6.3 mm radial. With R2-2: the socket note.

### R2-8 LOW — Two README / BOM statements

- README, at the bench step 3 and 7a: "`IN PC` = $58 / $59 on the text-only build". Bits 1 and 2 are VSYNC and DE
  (IC34 pins 4 and 6), live: the value is $58-$5F (graphics build $50-$57). Write "IN PC AND $F9 = $58 / $59".
- README / `BUY["IC39"]`: "the -55 grade is needed (slot reads in 6-dot mode, direct-mode reads at 6 MHz)". With R2-4's
  rule the 6-dot slot reads do not occur; the direct read at 6 MHz is set by tOE and keeps 55 ns with a -70 and ~40 ns
  with a -100 part. Write: "-55 recommended (current production); a slower 62256 works in direct mode up to the machine's
  6 MHz and in slot mode in 8-dot mode".

### R2-9 LOW — Silkscreen overlaps

**Evidence.** `drc.json`: 41 `silk_overlap`, among them PCB text "KBD (PURPLE)" with J2's reference, C58's reference
with IC54's outline, C59's with IC55's, R16 / C57 / R23 / C43, R17 / R18 / C54, IC49 / R12, IC53 / IC49, IC25 / IC39,
C19 / SV3, JP2 / "DOTS", JP3 / "INT-EN"; 10 `silk_edge_clearance` (X1, X2, J1, J2, J3 outlines at the edge).

**Fix.** Move the reference fields clear in `gen_v20.py` (the cosmetic ones only slow the build; "KBD (PURPLE)" and the
J4 legend are the ones that matter).

### R2-10 LOW (firmware) — `video-ps2`: the open V2-18 item, and a re-sent byte

**Evidence.** `send_leds()` -> `ps2_command()` -> `ps2_wait(kb, 50)` takes the next byte from the keyboard ring,
whatever it is (V2-18, still open). `feed_cpu()` lines 182-186: after LDDATA's rising edge it calls `md_release()` and
reads FULL ~3-4 us later; FULL = 0 is taken as "a read strobe overlapped the load" and the byte is loaded again. A CPU
`IN PE` that starts inside those microseconds and clears FULL also gives FULL = 0: the byte arrives twice.

**Consequence.** A lost key with Caps / Num / Scroll Lock; a doubled byte only for a CPU that reads PE without first
seeing FULL = 1 in PD (a reader that waited for FULL, or for -INT, cannot reach `IN PE` in 4 us even at 6 MHz).

**Fix.** In `ps2_wait()` used by `ps2_command()` accept only $FA, $FE, $EE, $AA and the mouse's $00 and pass every other
byte to `keyboard_byte()`; driver rule (README protocol): `IN PE` only after `IN PD` showed FULL.

---

## INFO

### R2-11 INFO — The picture in the character where GFX-ON changes

In direct mode IC42 keeps latching GD at every CHARCLOCK, and GD is $FF (RN3) except during window accesses. When GFX-ON
goes 0 -> 1 the combine (IC1/D) passes the graphics dots at once while the pipeline still holds two of those bytes: 16
lit dots (OR mode) or 16 inverted dots (XOR mode) at the beam's position, once. 1 -> 0 removes the layer at once. The
driver should switch GFX-ON during vertical blanking (IN PC bit 1).

### R2-12 INFO — MRST's high level

With -RESET high IC27/F's output is off and R16 (10k) pulls MRST up; TI specifies the 7416's off-state current only at
VOH = 15 V (250 uA maximum), which through 10k would leave 2.5 V against the ATmega328P's RESET VIH of 0.9 VCC. At 5 V
the real leakage is microamps, and the ATmega's own reset pull-up is in parallel. Measure MRST with -RESET high (>= 4.5
V) at the bench (step 5); if it is low, R16 4.7k.

### R2-13 INFO — The character generator image

`chargen-v20.bin` (8 192 bytes): $0000-$0FFF = `chargen-v13.bin` (byte-identical), $1000-$1FFF a copy. The card's address
is A10 = DOTS, A9 = A11 = A12 = 0, A8..A3 = the code, A2..A0 = RA: only $0000-$01FF (DOTS = 0, jumper fitted: the 8-dot
font) and $0400-$05FF (DOTS = 1: the 6-dot font) are read, and both hold glyphs (393 and 388 non-zero bytes); the copy
can never be reached and does no harm. `minipro -p AT28C64B -u -P -w` (unprotect, write, protect) is right; -WE is tied
high on the card, so the protection does not matter there.

### R2-14 INFO — What the build's own checks cover

`gen_v20.py verify` checks 173 hand-listed connections in the schematic and on the board. The whole circuit is covered
by `netlist-compare.txt` (215 of 215 net groups) and `v20_netlist.check()`, but both start from `v20_netlist.py`; the
hand list is the only independent statement of intent, and it leaves out nets the fixes rest on: the J2 / J3 shield pads
(GND), IC46.5 / IC46.6 / IC47.10 (MEMWR into GWR), IC44.1 (-RESET), IC53.1 / IC53.3 / IC53.5 (FULL's clear, clock,
output), IC40's A / Y pins. `text_only_check()` uses the hand-made `OUTPUTS` table (correct for every part listed: the
157 Y pins, the 62256 DQ, the 244 Y and 374 Q pins, IC43 pin 13, IC44 pins 5/6/8/9, IC45 pins 6/8, RN3) and
`OUTPUTS.get(ref, ())`, so a part added to `TEXT_ONLY_LEFT_OFF` without an entry passes silently. Add the nets to `KEY`;
in `check()` report every IC in `TEXT_ONLY_LEFT_OFF` that has no `OUTPUTS` entry.

### R2-15 INFO — Route lengths (from the board)

CRTCCLOCK 267 mm / 4 vias, CHARCLOCK 220 / 3, DOTCLOCK 182 / 3, NMUX 186 / 3, GWE 226 / 7, WSLOT 137 / 3, GFXON 252,
NGFX 227, MEMRD 233, -RESET 277, -INT 231, GD0-7 142-190, GA0-14 24-89, MRST 40, RESETH 11, INTG 87, LDDATA 116, RDCMD
128, KCLK 32, MCLK 76. Over the solid planes, 270 mm is ~1.8 ns of flight against LS edges of 5-10 ns: no
termination. A ring on GWE or CRTCCLOCK would at worst repeat a write or a latch load with the same address and data.
Look at IC41.11, IC44.3 and IC39.27 at the bench.

### R2-16 INFO — PS/2 power

F1 Bourns MF-RHT050: 0.5 A hold, ~0.5-1.2 ohm: 0.1-0.2 V at a keyboard and a mouse (~0.2 A); PS/2 devices want 4.5 V or
more, so PS2VCC should read >= 4.6 V with both plugged in. R17-R20 pull up from VCC, not PS2VCC: with F1 tripped the
lines still idle high (a device is back-fed ~1 mA through them, harmless).

---

## Verified OK

- **The slot select** (IC32/C, IC19/D): NMUX = NAND(QC OR RCO, GFX-ON) to all four 157 selects (S = 1 = I1 = the CPU,
  checked on every section: a (3/2/4), b (6/5/7), c (10/11/9), d (13/14/12), IC38's d tied to GND, Y open); GA0-10 =
  ADDR / MA, GA11-13 = PLANE / RA, GA14 = CPAGE / DPAGE. The IC42 hold now starts from the same RCO edge as CHARCLOCK
  (table above). NMUX's load: four 157 selects (2 LS loads each) + IC45 + an HCT input = 3.6 mA from an LS00.
- **-WE** (IC45/A) = NAND(WRQ, NMUX, WEPH OR NOT GFX-ON, GWR); GWR = GSEL AND MEMWR (IC47/C), GSEL = BOARDSEL AND ADDR11
  (IC47/B). In slot mode a write starts only at a sampled slot, ends with the strobe or the phase; the 9 -> 10 WEPH glitch
  and a runt at the strobe's end only repeat the write of the same byte at the same address (IC40 re-enables within the
  same count; tDW still >= 80 ns before the final rise).
- **-OE** = WSLOT = WRQ AND NMUX AND GRDOE (IC54/A, IC1/B): off only in a CPU half with a pending write and no window
  read; on in every display half; in direct mode = GRDOE (on only for a window read).
- **IC40** on only during -WE; the RAM's outputs are off from a dot before (-OE follows NMUX, -WE follows WEPH) to a dot
  after; data hold at the RAM: IC40's disable, then RN3 and the line capacitance (tDH 0).
- **Direct mode writes and reads** against the real microcode (the table above; an independent listing of `test.hex`, including
  the fields the test does not compare: -HL-SWAP, ALU code, operand select, -VMA); `-MEM-WR` is a pipeline 74LS374
  output with no gating, so it is clean at both edges, and the address never moves within a step of it.
- **IC41 / IC55**: SRDOE = NAND(GSEL, MEMRD, GFX-ON) (IC48/C), DRDOE = NAND(GSEL, MEMRD, NOT GFX-ON) (IC45/B, pin 13 on
  VCC): never both, except for one LS04 delay at a GFX-ON edge, which can meet a window read only if code runs from the
  window. Neither drives DATA outside a window read; after a window read no other driver starts in the next step.
- **GD and RN3** in direct mode: driven only by the RAM (window read) or IC40 (window write), never both (`test.hex`: no
  -MEM-RD next to a -MEM-WR); idle at 4.8 V (10k against IC42's 20 uA); low level with the RAM driving: 0.9 mA (RN3 +
  IC42), within the AS6C62256's 2.1 mA.
- **WRQ preset by GFX-ON = 0** (IC44 pin 4): the OUT PC records contain no window access (every memory strobe in them
  addresses PC, test 4, confirmed); a slot write is complete within its own strobe (2-3 slots at 1 MHz), so leaving slot
  mode loses nothing; entering it, WRQ stays 1 for at most one character (667 / 500 ns + the LS74), during which -WE still
  needs GWR and -OE is high only in CPU halves: nothing is written or doubled, and at 1 MHz the next window access is
  microseconds away. The rule "no code in the window" is sufficient; "do not touch the window in the OUT PC
  instruction" follows from it. -PRE released next to a CHARCLOCK edge can leave WRQ undecided for a few ns, with GWR = 0:
  harmless.
- **Reset and power-up**: -RESET clears IC33 (GFX-ON = 0: direct mode, IC41 off); IC44/A then has -PRE and -CLR both
  low, Q = 1, and stays preset after -RESET rises; -MEM-RD, -MEM-WR and -VMA float while the pipeline is tri-stated
  (-BUS-EN) and read high at the LS inputs: no -WE, no IC55. Without a reset (the machine has no power-on reset) IC33 is
  random: GFX-ON and the planes only choose which buffer answers a window read; nothing drives the bus.
- **The text-only build**, re-derived from the netlist (every net shared by a left-off and a fitted part): the only
  fitted inputs that lose their driver are IC1.12 (GDOT: R25), IC1.4 (WRQ: R26) and IC34.8 (TXTONLY: R27); every other
  shared net is driven by a fitted part (NMUX, GSEL, MEMRD, NGFX, GWR, WEPH2, GFXON, the address and data lines, the
  clocks) or is a fitted output into nothing (SRDOE, WSLOT). No fitted gate input floats (IC1, IC19, IC32, IC46-IC48,
  IC54 checked pin by pin). IN PC bit 3: IC44/B (-CLR on GND, -PRE on VCC) Q = 0 sinking R27's 0.5 mA + IC34's 0.2 mA;
  without IC44, R27 against IC34's 20 uA: 4.8 V. R25 / R26 (1k) into ALS08 inputs (0.1 mA): 0.1 V.
- **-INT**: INTG = INTREQ AND FULL (IC54/B, HCT) into IC27/D (7416 input 1.6 mA, within the HCT08's 4 mA); R24 holds
  INTREQ low through the ATmega's reset and bootloader; FULL cleared by -RESET (IC47/D) and by the PE read; -INT is
  released while the CPU's `IN PE` strobe is on.
- **MRST** through IC27/E, F: -RESET low -> RESETH high (R21 4.7k against one TTL input: 4.8 V) -> MRST low; -RESET high
  -> MRST released to R16; the DTR pulse through C57 still resets; the bus line only ever pulls down. (R2-12 for the
  level.)
- **Optiboot** (the Uno build: `LED_START_FLASHES = 3`, no LED_DATA_FLASH): it starts the sketch at once after a
  power-on or watchdog reset and runs only after an external reset; then it drives PB5 (its LED: now SRC, an input of
  IC52 only) and, through the UART, PD1 (J4's RXD only); every other pin is an input: PB3 = BUSY (IC53/B drives it
  alone), PB4 = INTREQ (R24), PD6 = LDDATA (R22), PD7 = RDCMD (R23), MD0..7 (floating CMOS inputs for ~1 s, IC51's
  outputs off: harmless). The sketch's `setup()` takes LDDATA high before making it an output (no edge), drops a command
  latched before the reset, and drives INTREQ low.
- **Firmware fixes** read in the code: V2-1 (`PIN_BUSY 11`, `PIN_SRC 13`), V2-3 (the clock pulled low, then the transmitter
  armed after 120 us under `noInterrupts()`; the host's edge reaches the receive branch with data high and is ignored;
  10 falling edges for 8 data bits, parity and stop, the 11th reads the acknowledge), V2-7 (LDDATA idle high, low pulse),
  V2-9 (`md_release()` with pull-ups), V2-18 (data bit read first, 64-byte rings, VT100 sequences whole, E0 7E and E0 59,
  the strobe comment). Every pin number against the netlist (KCLK PD2, MCLK PD3, KDAT PD4, MDAT PD5, LDDATA PD6, RDCMD
  PD7, MD0-5 PC0-5, MD6-7 PB0-1, FULL PB2, BUSY PB3, INTREQ PB4, SRC PB5); IN PD bits 0 FULL, 1 SRC, 2 BUSY.
- **The 28C64**: every pin the 2732's + 2 (A0-A2 = RA on 10/9/8, A3-A8 = the code on 7..3 and 25, A10 = DOTS on 21, A9 /
  A11 / A12 / -CE / -OE on 24 / 23 / 2 / 20 / 22 to GND, -WE 27 to VCC, O0-O7 on 11-13 / 15-19 to the 166's A-H, 1 and 26
  open, VCC 28, GND 14). 6-dot budget: IC23 output <= 80 ns into the character, + 150 ns access, against the 166's load
  at 500 ns less 20 ns set-up: 250 ns spare (8-dot: 417).
- **HCT / LS levels** on every new or changed net: HCT and CMOS outputs into LS inputs at <= 2.1 mA a net (GFXON the
  heaviest: two LS74 preset loads + three LS + one ALS); LS outputs into HCT inputs (VIH 2.0) and into the 62256 (VIH 2.2,
  LS VOH >= 2.7); no LS output into the ATmega any more (MD from IC51, FULL / BUSY from IC53, both HCT); the ATmega's
  outputs into LS / HCT inputs. Pull-ups: R22 / R23 10k against LS / HCT inputs, RN3 10k, R27 10k, R21 4.7k (above).
- **The board**: 4 layers, planes GND (In1) and VCC (In2), no power track; DRC 0 unconnected, no clearance, short or
  parity finding (cosmetic silk only); ERC 6 off-grid; netlist proof 215 of 215 groups. Decoupling: every 100 nF within
  5.1 mm of its VCC pin (C18 at the 6845's pin 20 5.1 mm, C59 at IC55 5.0, C58 at IC54 4.1, C49 and C22 3.4; V2-16 done);
  C16 47 uF at the bus connector. IC54 by J4 leaves 1.3 mm to an FTDI plug's housing.
- **The MD-60SM footprint** against the data sheet (rev 1.09, page 3, date codes after 03/03/2022): signal holes at
  (-8.5, +-1.3 / +-3.4) and (-11.0, +-3.4) from the face (6.8 and 2.6 mm spans), 1.0 mm drills (the 0.9 +0.1 upper
  limit), 1.6 mm pads; the earth slot (-4.7, 0) 0.8 x 2.3 (the 0.7 x 2.2 +0.1 limit); the view (component side) and
  the numbering: in the drawing's top view, face down, pins 6 / 4 / 2 are on the left; turned so that the face points
  to +x, they land at +y, as in the footprint, and the face view (6 5 / 4 3 / 2 1, looking into the jack) is the PS/2
  receptacle's. On the board pin 1 KDAT / MDAT, 3 GND, 4 PS2VCC, 5 KCLK / MCLK, 2 and 6 open, the three S pads on GND; the
  face (x = 0) exactly on the board edge (236.167) for both jacks, as the drawing's datum line; bodies 14.0 wide 18 mm
  apart (3-4 mm between). The older pattern (before 03/03/2022: round 2.5 mm holes 13.4 apart at 4.7, 1.0 mm holes,
  a 2.5 x 1.0 earth slot) differs: the BOM's date-code note is needed.
- **BOM** against `PARTS`: every reference and value, the HCT parts (IC33, IC40, IC41, IC51, IC53, IC54, IC55), the
  AT28C64B-15, the AS6C62256-55 600-mil, F1, J2 / J3 with the date code, the 5 V FTDI cable; the text-only column (25 off:
  IC35-IC45, IC55, RN3, C35-C45, C59; R25 / R26 only).

## At the bench (additions to the README's order)

The README's order (text-only first, the ATmega, then graphics in direct mode before slot mode) stands. Add:

1. Before soldering J2 / J3: the jack's legs into the slots (R2-1), and the sockets of IC55, IC19, IC1 side by side
   (R2-2).
2. With the card in the machine: C30's low level during a reset (R2-3, below 0.5 V).
3. Step 5 (the ATmega): MRST >= 4.5 V with -RESET high (R2-12); PS2VCC >= 4.6 V with both devices (R2-16).
4. Step 6 (graphics): DATA0's low level during a window read in each mode (R2-6); switch GFX-ON during VSYNC and watch
   for the 16-dot flash otherwise (R2-11); IC41.11, IC44.3 and IC39.27 for ringing (R2-15). At 6 MHz, a window read
   pattern with the stack outside the window (R2-5).
