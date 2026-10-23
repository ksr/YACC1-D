# video-v2.0 — KiCad design master for the video card

**The master since 2026-10-22. Not ordered; no gerbers.** V2.0 is the v1.3 card (`../v1.3/`: 6845, IDT7134 text RAM,
the DOTS jumper, 12 MHz, both fonts in one character generator) plus a **graphics layer**, **every register on I/O ports
PA-PE** and **two PS/2 ports** on an ATmega328P with an **INT jumper**. The design note is `BACKLOG.md` "Video card
V2.0"; the theory `docs/cards/video.md` section 7a; the ATmega's firmware `embedded/video-ps2`; the picture and the CPU
side `tools/vidsim.py --card v2.0`.

**Revised 2026-10-22 after the design review** (`hardware/DESIGN-REVIEW-video-v2.0.md`, its status table at the top):
every HIGH and MEDIUM finding is in the circuit or the firmware, and two features were added - **direct mode** (with
GFX-ON = 0 the CPU owns the graphics RAM: a plain SRAM at any clock the machine runs) and the **text-only build** (the
graphics chips left off, a status bit saying so). **Do not order before the re-review** of the changed slot logic and
direct mode (`BACKLOG.md`).

Unlike v1.x (Eagle conversions edited in KiCad) this design is **generated**: `v20_netlist.py` is the circuit,
`gen_v20.py` draws the schematic (one A0 sheet, the CF card's sheet writer: every pin a stub to a label or a power
symbol, functional boxes), builds the board and writes `BOM.md`; `build.sh` routes and checks it. Change the circuit in
`v20_netlist.py`, the placement in `gen_v20.py` (`PLACE`), then run `./build.sh` (KiCad 10, Freerouting 1.9 in `FRJAR`,
default `~/freerouting/freerouting.jar`, which opens a window while it runs; `SEEDS="..."` and `MP=` choose the
component orders and passes). `tools/eagle_to_kicad_all.py` never writes here (`MASTER` marker).

## The board

- **218.42 x 113.97 mm** (x 17.747-236.167): the blank V3.2 card's outline lengthened to the sequencer logic V2.1l's
  218 mm, so it needs the same slot space; X1 (DIN 41612) exactly where every card has it, copper keepouts round its
  two screws.
- **4 layers**, the v1.3 / memory card v2.0 stack-up and rules: In1.Cu a solid GND plane, In2.Cu a solid VCC plane, GND
  and VCC never routed (every power pin is a through-hole pad on its plane); signals 0.25 mm, clearance 0.2 mm, vias
  0.8 / 0.4 mm.
- **Placement** (`gen_v20.py` `PLACE`; pin 1 of every DIP at the top left, each 100 nF beside its IC's VCC pin):
  row A (top) the port decode, strobes, the inverters IC46 (beside the control register they mostly serve), the control
  register, status buffers, the PS/2 and graphics latches, WRQ and the video driver IC27; on the left the 600-mil parts (IC15 text RAM, IC17 6845, IC39 62256, IC25 28C64) and IC18 with SV3 /
  RN2; row B the graphics address muxes, display latch and shifter, the ATmega, with the GD pull-ups RN3 standing between
  IC38 and IC42; under IC42 / IC43, on its side, the direct-mode read buffer IC55 (the band under the muxes is left to
  the routing); row C the text pipeline and the gates, with the text-only pads R25 / R26 in the gaps beside IC1; row D
  the clock chain (IC28, IC21, IC20 with Q2, SV4), the remaining gates (IC32 among them, beside the counter whose QC and
  RCO it ORs) and IC54 (turned round, beside J4); the right
  edge DB9 (X2), RCA (J1), the keyboard (J2) and mouse (J3) Mini-DINs with their faces at the board edge, F1, the FTDI header J4 (a legend
  at every pin), the PWR LED. `gen_v20.py place` checks that no two courtyards overlap.

## Results (`./build.sh`, 2026-10-22)

| Check | Result |
|---|---|
| schematic netlist vs `v20_netlist.py` | **MATCH, 216 nets** (`gen_v20.py checknet`); `v20_netlist.check()` OK: 120 parts, 943 connections, no pin on two nets, the text-only check |
| netlist proof, schematic vs board (`tools/kicad/compare_netlists.py`) | **MATCH, 216 of 216 net groups** (RESETB added by R2-3) |
| placement | 120 footprints, no courtyard overlaps (`gen_v20.py place`) |
| route (Freerouting 1.9, component order 6, 60 passes; the R2-1/R2-2/R2-3 rebuild of 2026-10-23) | **0 unrouted, 328 vias, 22.2 m of 0.25 mm track** (F.Cu 10.1 m, B.Cu 12.0 m). Of orders 0-7 and 17 only 6 and 5 (355 vias) completed cleanly; 0 left one connection (-MEM-RD at X1), 3 and 17 shorts, the rest 2-4 unrouted (before the rebuild: order 3, 308 vias). An earlier placement with the new parts in the band under the muxes (and RN3 between the 6845 and the 62256) left 30 unrouted after 10 passes: that band and the channels round IC15 / IC17 carry the address and data lines and are kept free |
| DRC | **0 unconnected, no clearance / short / dangling findings**, schematic parity 0; cosmetic only: silk_over_copper 89, silk_overlap 40, silk_edge_clearance 10 (X1, X2, J1, the Mini-DIN outlines at the edge), text_height 2, text_thickness 3 (footprint texts) |
| planes | In1.Cu GND, In2.Cu VCC, one zone each over the whole board, filled as one piece (24,478 mm2) besides the pad-sized islands the previous board had too; every GND / VCC pin reaches its plane (0 unconnected with no power tracks) |
| ERC | endpoint_off_grid 6 (cosmetic), nothing else |
| `gen_v20.py verify` | **PASS**: 189 key connections pin by pin in the schematic and on the board (the port decode and strobes, the 6845 on PA/PB, the card ID and the TEXT-ONLY bit, the mux select NMUX and its QC OR RCO, the slot logic and direct mode (WRQ preset, WEPH2, -WE, the -OE term, IC40 on -WE, IC41 / IC55 enables, RN3), the text-only pads, the 28C64's wiring, the combine, the DOTS divider and font select, the ATmega's bus interface with BUSY / SRC swapped, -INT = INTREQ AND FULL, the reset through IC54/C and IC27/E,F, the PS/2 lines and F1; since R2-14 also the MEMWR path, IC44.1, FULL's clear / clock / output, IC40's A / Y pins and the jacks' shield pads), 4 copper layers, the two planes, no track on GND/VCC |

`./build.sh` takes 40-75 minutes with four component orders in parallel (`SEEDS="3 4 17 2"`): Freerouting's passes take
several minutes each on this board, and a completed route is then optimised for up to 40 minutes; the watchdog
(`WATCHDOG=`, seconds) stops runs that go on longer.

## Parts V2.0 adds (references continue v1.x's; IC2, JP1, R13, R14 are gone)

| Ref | Part | Job |
|---|---|---|
| IC30 | 74LS138 | port decode: Y2..Y7 = PA..PF when IO-ADDR3 = 1 |
| IC31, IC32 | 74LS32 | port strobes (PC write/read, PD write/read, PE read); IC32/B text OR graphics, IC32/C QC OR RCO, IC32/D WEPH OR NOT GFX-ON |
| IC33 | **74HCT273** | control register, OUT PC: PLANE0-2, CPAGE, DPAGE, TEXT-OFF, GFX-ON, XOR (cleared by -RESET) |
| IC34 | 74LS244 | card status, IN PC: DOTS, VSYNC, DE, TEXT-ONLY, ID 0101 |
| IC35-IC38 | 74LS157 | graphics RAM address: the CPU (I1, NMUX = 1) or the display (I0, NMUX = 0) |
| IC39 | 62256 (AS6C62256-55) | graphics RAM, two 16K pages |
| IC40 | **74HCT244** | write buffer DATA -> GD, enabled by the RAM's -WE (GWE) |
| IC41 | **74HCT374** | slot-mode CPU read latch GD -> DATA (loads on QC's rise; enabled with GFX-ON = 1) |
| IC55 | **74HCT244** | direct-mode read buffer GD -> DATA (enabled with GFX-ON = 0) |
| RN3 | 10k x 8 | GD0-7 pull-ups: in direct mode nothing drives GD between accesses |
| IC42, IC43 | 74LS374, 74LS166 | display latch (CHARCLOCK) and graphics dot shifter |
| IC44 | 74LS74 | A: WRQ, a CPU write pending, sampled on CHARCLOCK, preset while GFX-ON = 0; B: held cleared, its Q is IN PC bit 3 (0 = graphics fitted) |
| IC45 | 74LS20 | A: the RAM's -WE = NAND(WRQ, NMUX, WEPH2, GWR); B: IC55's enable = NAND(GSEL, MEMRD, NOT GFX-ON) |
| IC46, IC47, IC48 | 74LS04, 74LS08, 74LS10 | inverters (NOT GFX-ON among them), graphics select / write / FULL clear, XOR term, the video NAND3 and IC41's enable |
| IC54 | **74HCT08** | A: the RAM's -OE term NMUX AND GRDOE; B: -INT = INTREQ AND FULL; C, D spare |
| IC49, Y1 | ATmega328P, 16 MHz | the PS/2 controller (`embedded/video-ps2`), C55/C56 22 pF |
| IC50, IC51, IC52, IC53 | 74LS374, **74HCT374**, 74LS244, **74HCT74** | PS/2 data latch (IN PE), command latch (OUT PD), status (IN PD), FULL/BUSY |
| J2, J3 | **Same Sky MD-60SM** | keyboard, mouse (R17-R20 4.7k pull-ups); +5 V through F1 |
| F1 | Bourns MF-RHT050 | 0.5 A resettable fuse in the PS/2 +5 V (PS2VCC) |
| J4 | 1x6 header | FTDI: GND, CTS, (VCC not connected), TXD, RXD, DTR -> C57 -> reset |
| R16, R21 | 10k, 4.7k | the ATmega's reset pull-up; RESETH, between IC27/E and IC27/F |
| R22, R23, R24 | 10k | LDDATA and RDCMD pull-ups, INTREQ pull-down (defined while the ATmega is in reset or its bootloader) |
| R25, R26 | 1k | **text-only build only**: GDOT and WRQ pull-downs |
| R27 | 10k | TEXT-ONLY pull-up (IN PC bit 3 = 1 when IC44 is not fitted) |
| JP3 | 1x2 header | INT-EN: IC27/D's open collector to the bus -INT |
| C30-C54, C58, C59 | 100 nF | decoupling, one per new IC (C54 the ATmega's AVCC) |

Changed v1.3 parts: IC25 a 28-pin **AT28C64B-15** in place of the 2732 (below); IC1 (74ALS08) the 6845 -CS (PA OR PB),
WSLOT and the dot gates; IC19/A the window-read NAND, IC19/D NMUX; IC26/C E = -IO-RD XOR -IO-WR, IC26/D QA XOR QB;
IC27/D INTG -> -INT, IC27/E,F the bus -RESET to MRST (IC27/E's input through IC54/C, an HCT08 section used as a
buffer: R2-3); IC17 RS = IO-ADDR0, R/-W = -IO-WR, -CS from IC1/A; C16 47 uF.
Spare after all changes: IC46/F (input on GND), IC54/D (inputs on GND), IC38's fourth section (both inputs on GND);
every other gate is used once (`v20_netlist.check()`: no pin on two nets; ERC: no input unconnected). Pin by pin:
`v20_netlist.py`.

## The design review's fixes in the circuit (2026-10-22)

| Finding | In the circuit |
|---|---|
| V2-1 | SRC on IC49 pin 19 (PB5, Optiboot's LED pin), BUSY on pin 17 (PB3); the firmware's two pin numbers swapped. During the bootloader PB5 drives SRC, an output only the ATmega drives (IC52's input) |
| V2-2 | J2 / J3 footprint `MiniDIN6_MD-60SM`, drawn from the Same Sky data sheet (below) |
| V2-4 | the muxes' select from QC OR RCO (IC32/C, then IC19/D with GFX-ON): the display address is held until RCO has fallen, the edge IC42 takes the display byte on |
| V2-5 | IC40 (the write buffer) enabled by GWE, the RAM's -WE: it drives GD only while the RAM's outputs are off |
| V2-6 | D1 removed: the bus -RESET reaches MRST through IC27/E and IC27/F (7416, open collector, R21 4.7k between them); the bus line only ever pulls MRST low |
| V2-7 / V2-8 | -INT = INTREQ AND FULL (IC54/B into IC27/D): released the moment the CPU reads PE, and released while the ATmega is in reset (FULL is cleared by -RESET); R22 / R23 pull LDDATA and RDCMD high, R24 pulls INTREQ low |
| V2-9 / V2-12 | IC33 74HCT273, IC40 74HCT244, IC41 74HCT374, IC51 74HCT374, IC53 74HCT74 (and IC54, IC55 HCT): no LS input load on DATA0..7 left on the card beyond the 6845 and the text RAM, and rail-to-rail levels into the ATmega |
| V2-10 | IC25 a 28-pin socket for an **AT28C64B-15** (150 ns): the 2732's pins + 2; A12 (2), A11 (23), A9 (24), -CE (20), -OE (22) on GND, -WE (27) on VCC, A10 (21) = DOTS (the font), pins 1 and 26 open. Image `firmware/video/chargen-v20.bin` (8K: the v1.3 fonts at $0000, a copy at $1000), burned like the ROM: `minipro -p AT28C64B -u -P -w`. It also saves ~80 mA against the NMOS 2732 |
| V2-11 | the 6845 grade in the BOM: an HD6845S or MC68B45 (no circuit change) |
| V2-16 | C18 at the 6845's VCC (pin 20), C49 at the ATmega's pins 7 / 8, C22 at the 74LS90's pin 5; C16 47 uF |
| V2-17 | F1, a 0.5 A PTC, in the PS/2 +5 V |
| V2-20 | the FTDI header's legend: one 1 mm label per pin, "1 GND (BLK)" first |
| V2-21 | `BOM.md` (`gen_v20.py bom`) |

## Direct mode: the CPU owns the graphics RAM while GFX-ON = 0

GFX-ON (control bit 6, OUT PC) used to switch only the display combine; the RAM was time-shared with the display
whether the layer was shown or not, so every graphics access was limited to a CPU clock of about 1.8 MHz (review V2-24).
Now GFX-ON also chooses how the RAM is run:

| | GFX-ON = 1: **slot mode** (the layer shown) | GFX-ON = 0: **direct mode** (the layer hidden) |
|---|---|---|
| address (NMUX = NAND(QC OR RCO, GFX-ON)) | CPU in counts 8-11 (10-11), display in 12-15 | the CPU's, all the time |
| -WE (IC45/A: NAND(WRQ, NMUX, WEPH OR NOT GFX-ON, GWR)) | counts 9-10 of a slot whose start saw the write | NOT GWR (WRQ preset by GFX-ON = 0, the other two terms forced high) |
| the RAM's -OE (WSLOT = WRQ AND NMUX AND GRDOE) | off while a write is pending in the CPU half | on only while the CPU reads the window |
| the byte to the bus | IC41, the latch loaded on every QC rise (enabled by NAND(GSEL, MEMRD, GFX-ON), IC48/C) | IC55, a buffer straight from GD (enabled by NAND(GSEL, MEMRD, NOT GFX-ON), IC45/B) |
| the picture | text and graphics combined | text only (GDG needs GFX-ON, as before) |
| CPU clock for the window | up to ~1.8 MHz | anything the machine runs (below) |

A 74HCT244 bypass was chosen over making IC41 a transparent latch: a 74HCT373 with its LE held open in direct mode would
need, in slot mode, an LE pulse that closes before the muxes switch to the display address; derived from the counter
it closes on the same dot edge as the switch, a hold race at the corners like V2-4's, and an LE open for the whole CPU
half would pass the settling RAM output to the bus for ~150 ns of every character. The buffer leaves the slot path exactly
as it was. RN3 holds GD high in direct mode when neither the RAM nor IC40 drives it (no floating CMOS inputs on IC41,
IC55 and the RAM).

**Timing against the machine** (`tests/video/v20_timing.py`, in `make check`, reads the microcode image
`firmware/microcode/ucode-generator2/test.hex`): all 59 `-MEM-WR` strobes are one step (two clocks) long with the address
(ADDR-REG-ID) and the data source unchanged one step before and one step after, and the address register is neither
counted nor loaded around them; no `-MEM-RD` is next to a `-MEM-WR`; the shortest read window, from the address becoming
stable to the edge that takes the byte, is one step (JSR). With the maxima of the parts (74LS: TI; 74HCT: NXP; the
AS6C62256-55's tAA 55, tOE 30, tWP 45, tDW 25, tAS = tWR = tDH = 0):

| | 1 MHz (a step 2000 ns) | 6 MHz (a step 333 ns) |
|---|---|---|
| read: address on the bus 96 ns, the RAM's -OE 186 ns, the byte at the destination with its set-up 261 ns | margin 1739 ns | **margin 72 ns** |
| write: -WE width (step less the 78 ns -WE path) against tWP 45 | 1922 ns | 255 ns |
| write: data at the RAM (IC40 enabled 30 ns after -WE) to -WE's rise, against tDW 25 | 1892 ns | 225 ns |
| write: address set-up / hold (tAS, tWR 0) | stable 2000 ns before, 1922 ns after | stable 333 ns before, 255 ns after |

So -WE straight from the strobe needs no trimming: the microcode never moves the address or the data within a step of a
write, and the direct read path alone would allow about 7.7 MHz. The card is not the limit: the machine's one-step
memory windows with the 28C64 ROM fail first, at about 6 MHz (review M-2).

**Switching modes** (OUT PC): IC33 takes the new value at the end of the -IO-WR strobe; every memory strobe in the
records that write a port addresses PC (test 4), so no window access can meet the switch unless code runs from the
window (it must not). Entering slot mode, WRQ stays preset until the next CHARCLOCK (at most one character, 667 ns); a
window write that started in that time could open -WE mid-slot. **Rule: do not access the window in the instruction that
writes PC** - at 1 MHz the next instruction's first window access comes at least 6 us later; in slot mode the 1.8 MHz
limit applies anyway. Leaving slot mode takes effect at once (WRQ preset, the address held).

**Clock limits**: graphics hidden (GFX-ON = 0) - limited only by the rest of the machine (~6 MHz); graphics shown
(GFX-ON = 1) - ~1.8 MHz for window accesses (review V2-24). The text RAM (dual port) and the ports have no such limit
(the 6845 needs an HD6845S / MC68B45 above 1 MHz, V2-24). After a reset GFX-ON = 0: the window is in direct mode. In
6-dot mode the layer is never shown, so software keeps GFX-ON = 0 there and the slot mode's 6-dot write margins (V2-13)
do not arise.

## The text-only build (the recommended first build)

Leave off the graphics parts and fit two resistors; everything else is the same board:

| Left off | Fitted only in this build |
|---|---|
| IC35-IC38 (74LS157), IC39 (62256), IC40 (74HCT244), IC41 (74HCT374), IC42 (74LS374), IC43 (74LS166), IC44 (74LS74), IC45 (74LS20), IC55 (74HCT244), RN3; their capacitors C35-C45, C59 | **R25** 1k (GDOT to GND: the graphics dot input of IC1/D), **R26** 1k (WRQ to GND: IC1/B's input) |

`v20_netlist.text_only_check()` (run by `check()`, so by every build) lists every net a left-off part drives into a
fitted one: exactly GDOT and WRQ (the two pull-downs) and TEXT-ONLY (the status bit, by design), besides the 3-state
outputs of IC41 / IC55 onto DATA0..7, which an absent chip simply releases. R25 and R26 must not be fitted with the
graphics chips: 1k would load IC43's and IC44's outputs.

**IN PC bit 3 = TEXT-ONLY**: IC44's second flip-flop is held cleared (-CLR on GND), so with IC44 fitted its Q drives bit 3
low; without it R27 (always fitted) pulls it high. The card ID stays $5x either way: a full card reads bit 3 = 0, as
before; a text-only card reads 1. The ROM / OS reads it once at reset and leaves GFX-ON at 0 on a text-only card (the
window then reads the floating bus and writes go nowhere; `vidsim.V20Card(text_only=True)`).

**Bring-up order**: build text-only first (text RAM, 6845, the ports, PS/2), prove it on the bench, then fit the
graphics chips and remove R25 / R26.

## The Mini-DIN jack: Same Sky MD-60SM (V2-2)

**Buy: Same Sky (formerly CUI Devices) MD-60SM**, a 6-pin right-angle shielded through-hole Mini-DIN jack, in production,
stocked by the large distributors. The footprint (`video-v2.0-local.pretty/MiniDIN6_MD-60SM.kicad_mod`, written by
`gen_v20.py`) is drawn from the data sheet "SERIES: MD-SM", rev 1.09 of 2024-09-12, page 3, "Recommended PCB Layout, Top
View (Date Codes after 03/03/2022)". Parts with an older date code have another pattern: check the date code on the
reel / bag before soldering. The review's check list:

1. **Pins and drills**: six 0.9 (+0.1/-0) mm holes - pins 4, 2, 1, 3 in a row 8.5 mm behind the mating face at -3.4,
   -1.3, +1.3, +3.4 mm (6.8 and 2.6 mm spans), pins 6 and 5 11.0 mm behind it at -3.4 / +3.4; drilled 1.0 mm, 1.6 mm pads.
2. **View**: the drawing is a top (component side) view, as the footprint.
3. **Numbering**: looking into the jack pins 6, 4, 2 are on the left and 5, 3, 1 on the right - the PS/2 face numbering
   (1 data, 3 GND, 4 +5 V, 5 clock; 2, 6 unused). Confirm with a meter on the first jack before soldering.
4. **Shell and earth**: the earth terminal a 2.2 x 0.7 (+0.1) mm slot 4.7 mm behind the face on the centre line; the
   shield's two side legs (0.54 mm thick, 2.0 mm wide, 13.2 mm between their inner faces) slots 13.5 mm apart (centres),
   5.5 mm behind the face; all three plated, on GND. The earth slot is drilled 0.8 x 2.3 mm; the side slots **1.2 x 2.6
   mm, pads 1.9 x 3.3** (R2-1, 2026-10-23: a 0.8 mm slot left 0.01 mm at the legs' outer face; now 0.21 mm outside and
   0.45 mm inside). Measure a real jack's leg span (14.28 mm across the outer faces expected) before ordering.
5. **Board edge**: the mating face (the drawing's datum) is at the board edge, x = 236.17.
6. **Spacing**: the body is 14.0 mm wide (13.0 deep, 12.8 high); J2 and J3 are 18 mm apart: 4 mm between the bodies.
7. **Silk**: "KBD (PURPLE)" and "MOUSE (GREEN)", the PS/2 colours.

## Bill of materials

`BOM.md` (generated from `v20_netlist.PARTS` and `BUY`; the text-only column marks the build above). The parts that
need a note:

- **HCT**: IC33 74HCT273, IC40 and IC55 74HCT244, IC41 and IC51 74HCT374, IC53 74HCT74, IC54 74HCT08 - no LS
  substitutes (V2-9, V2-12).
- **IC17**: an **HD6845SP** or **MC68B45P**. An MC6845P (1 MHz part) has no margin on its clock-low time in 6-dot mode
  (V2-11) and cannot take a 6 MHz CPU's 333 ns E pulse (V2-24); it does only for 64 x 24 at 1 MHz.
- **IC25**: **AT28C64B-15PU**, burned with `firmware/video/chargen-v20.bin`.
- **IC39**: **AS6C62256-55PCN** (600-mil DIP-28; the -55 grade: the slot reads in 6-dot mode and the direct reads at
  6 MHz need it; not a 300-mil 62256).
- **IC49**: ATmega328P-PU with the Uno bootloader burned by ISP before fitting (no ISP header on the card).
- **IC18**: the 74S85 of the V1.x card; a 74LS85 (~60 mA less, V2-19) adds ~20 ns to the window decode, which the
  direct-mode read still fits at 6 MHz.
- **J2, J3**: Same Sky MD-60SM (above). **F1**: Bourns MF-RHT050. **J4**: a 5 V FTDI cable (TTL-232R-5V) or 5 V FTDI Basic.
- Sockets for every IC (the 6845, the IDT7134, the 28C64, the 62256 and the ATmega at least).

## At the bench, in this order

1. **Before the chips**: VCC-GND resistance; power with sockets only, then the text-only set without the ATmega: the
   supply current.
2. **The bus stays quiet**: with the card in the machine, `tests/memory/memory_full_test.py` and
   `tests/video/video_ram_test.py`, a scope on DATA0 during ROM reads. Check the I/O card's IO-ADDR-HL strap (P0-P7).
3. **Ports**: `IN PC` = $58 / $59 on the text-only build (bit 3 = 1, bit 0 = DOTS); `OUT PC` patterns at IC33's outputs.
4. **The 6845 through PA/PB**: scope E against R/-W (V2-15); in 6-dot mode the low width of QC at IC17 pin 21 (V2-11);
   the test card in both modes; the low level on DATA0 during `IN PB` (V2-12).
5. **The ATmega**: MRST with -RESET high and low (V2-6), -INT during a bus reset with JP3 fitted (V2-7: stays high), the
   keyboard, then the mouse (`$04` answers `$FA $AA $00`, then `$FA`), and only then JP3 with the sequencer in level mode.
6. **Graphics**: fit IC35-IC45, IC55, RN3, remove R25 / R26; `IN PC` bit 3 = 0. **Direct mode first** (GFX-ON = 0): a
   write / read-back pattern over both 16K pages at 1 MHz, then at 6 MHz if the machine runs there. Then **slot mode**
   (GFX-ON = 1) at 1 MHz: the same pattern; scope -WE (IC45 pin 6), WSLOT (IC39 pin 22) and a GD line for contention
   (V2-5), IC42 pin 11 against a GD line at the character boundary (V2-4); a graphics test picture for sparkle.

## Still to do before ordering

- **The re-review** of the changed slot logic, direct mode and the text-only build (`BACKLOG.md`), against this board.
- The ROM's V2.0 driver and the emulators' V2.0 card model do not exist yet (`BACKLOG.md`).

## Files

| File | What it is |
|---|---|
| `v20_netlist.py` | **the circuit**: parts, nets (pin by pin), no-connects, `BUY`, the text-only build, `check()` |
| `gen_v20.py` | schematic, local libraries, project rules, the unrouted board, placement check, verify, `BOM.md` |
| `build.sh` | the whole build: schematic -> board -> Freerouting seeds -> reports -> checks |
| `BOM.md` | the bill of materials (generated) |
| `video-v2.0.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, `.kicad_dru` | the generated design |
| `video-v2.0-local.kicad_sym` / `.pretty/` | IDT7134, RCA, DE9 and Mini-DIN symbols; F09HP and RCA footprints (from v1.x), MiniDIN6_MD-60SM |
| `blank-card-v3.2-eagle.kicad_sym` / `.pretty/` | the bus connector FABC96R (from the CF card / blank V3.2) |
| `reports/` | netlist, `netlist-compare.txt` (proof), `erc.json`, `drc.json`, schematic PDF, top / bottom renders |
