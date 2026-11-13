# Video card V4.0 (6845, VGA, 16 dots a count) - the circuit, the schematic, the routed board

The circuit as data, checked and simulated; its schematic; and the board, 250 mm long, every part placed and
**every connection routed** (2026-11-12). Not ordered, not built: the pre-order check and a design review are still
to come. `v40_netlist.py` is the card's circuit (parts, nets, the pins left open), written from the design note
`docs/cards/video-v4.md` (section 5 the clock and the stage, 6 the text, 7 the graphics RAM's two modes, 8 the dot
path, 9 the ports).

`python3 v40_netlist.py` checks the wiring (in `make check`): every pin of every part on a net or listed as open, no
net with a single pin, no two outputs on one net, an output on every net of ICs, a capacitor for every IC, and the
text-only build.

`tests/video/v40_netsim.py` (in `make check`, about 80 s) runs the netlist as a circuit, gate for gate, with every
part's delays from its data sheet at both ends of their ranges: the proof that the wiring does what the note says,
and the timing check. The parts in the netlist are the ones it was run with: a 74HCT or 74LS part in place of a 74F
or 74ACT one is another circuit.

**130 parts, 46 ICs** (V2.0 has 40, the V3 design 47).

| Block | ICs | |
|---|---|---|
| Bus, ports, registers | IC1-IC9 | block select (74S85), port decode (74LS138), the strobes (2 x 74LS32), control 1 and control 2 (2 x 74HCT273), the status (74LS244), inverters and ANDs (74HCT04, 74HCT08) |
| The 6845 and the clock | IC10-IC13, OSC1 | the 6845, the 25.175 MHz oscillator, the dot counter (74F163A), the 6845's clock and DE's delay (74F74), inverters (74ACT04) |
| Text | IC14-IC23 | the text RAM (IDT7134), the stage (2 x 74ACT574), the code register (74ACT574), the character generator (AT28C64B-15), the shifter (74F299), the cursor flag and the retimed dot (74F74), the load (74F21), 74ACT86, 74ACT08 |
| Graphics, left off in the text-only build | IC24-IC34, RN2 | the address multiplexers (4 x 74ACT157), the RAM (AS6C1008-55), the write buffer (74ACT244), the read latch (74ACT574), direct mode's read buffer (74HCT244), the byte latch (74ACT574), the shifter (74F299), WRQ and TXTONLY (74F74) |
| Slot logic, dots, syncs | IC35-IC40 | P56 and the read latch's clock (74F74), 74ACT32, 74ACT00, 74ACT11, the guns (74ACT02), the vertical sync's length (74HCT74) |
| PS/2 | IC41-IC46 | V2.0's section: ATmega328P, two latches, the status, the flags, the 7416 |

The references are new (this card keeps none of V1.3's or V2.0's numbers); the PS/2 section's nets are V2.0's.

## The simulation (2026-11-12)

The simulator and the models of the 74F and 74ACT parts and of the 128K RAM are the V3 check's
(`tests/video/v30_netsim.py`); added are the 74ACT157, the 74ACT244 with its enable times, the text RAM's display
port, the character generator, a 6845 that steps a script of counts and checks the clock it is given, and the bus
as the microcode drives it, started at every phase of the dot counter. Eight corners: the 6845 slow or fast, the
parts all slow or all fast, and the two mixed corners that set rising outputs against falling ones.

48 runs, none failing: the picture (every count's two characters and two bytes, the cursor's half, blanking, OR and
XOR, the pages, the colour bits), the window in slot mode at 3.5 MHz and in direct mode at 6 MHz (a write and two
reads at each of 32 phases of the count, the picture going on undisturbed), switching the mode at every phase with
nothing written, the text-only build, the ports and the status, the syncs.

| Closest margins, all corners | To spare |
|---|---|
| The retimed dot: a shifter's output through two gates to the flip-flop (set-up) | 5.6 ns |
| The read latch's hold | 8.7 ns |
| The shifters' load (the mode input's set-up) | 14.7 ns |
| The RAM's write pulse, 69.6 ns at its shortest | 24.6 ns over the 45 wanted |
| The RAM's data before the pulse ends | 34.6 ns |
| A byte read in slot mode at 3.5 MHz, on the bus before it is taken | 50 ns |
| The text RAM (as the 70 ns grade) to the code register | 63.9 ns |
| A byte read in direct mode at 6 MHz, on the bus before it is taken | 88 ns |

`--limits`: the window works down to a microcode step of 522 ns in slot mode (a CPU clock of 3.8 MHz) and 248 ns in
direct mode (8.1 MHz), the parts slow. `--faults`: 23 wiring faults put into the netlist in memory, one at a time
(crossed bits, a missing gate input, the wrong polarity): every one is reported by a run.

Not in it: the 6845's own minimum delays (its sheet gives none; 20 ns assumed, and the stage has a whole dot of
hold), Hitachi's 6845 (the figures are Motorola's sheet), signal quality on the bus, and a bench.

## What the simulation changed in the netlist

- **A write pulse is always whole.** As first written, -WE in slot mode contained the CPU's strobe (V2.0's way), so
  a strobe that ended inside a pulse cut it short: a -WE of any width down to nothing, at a moment when the RAM's
  data lines still hold the display's byte. Now WRQ alone opens the pulse (WEP# = NAND(WRQ, P56)) and direct mode has
  a gate of its own (WED#); the microcode's step of hold after the strobe covers the rest of the slot. WRQ is held
  clear in direct mode (it was preset), so no pulse can come as slot mode begins.
- **The -WE pulse's flip-flop** has its D from the 74F21 and the read latch's clock flip-flop from the 74ACT11
  (they were the other way round): the first had 6 ns of set-up to spare behind the inverter, and has 11 now.

## What the netlist settles that the note left open

- **The read latch's clock** is a flip-flop's pulse in dots 8 and 0 (RDCK, IC35/B), so the latch takes the RAM's byte
  as a CPU slot ends with the whole slot for the access. The latch is a 74ACT574 for its 1 ns hold time.
- **The cursor flag** is taken with each code (IC20/A); only DE is delayed (SDE2, as dot 8 begins).
- **The status's VSYNC and DE** (IN PC bits 1 and 2) are the stage's, a count behind the 6845's pins.
- **The vertical sync** at the connector lasts from the staged VSYNC's rise to the second HSYNC after it: about 1.8
  lines, with either maker's 6845.
- **The text-only build** needs no resistor of its own: R8, R9 and R10 are fitted in both builds.
- **46 ICs**, where the note's estimate was 42 or 43: four 74F74 where it counted two, and an inverter and an AND
  package more.

## The schematic (2026-11-12)

`gen_v40.py` (made from the V3 design's `gen_v30.py`, itself from the V2.0 card's; run it with KiCad's Python)
draws the schematic from the netlist: `video-v4.0.kicad_sch`, the root, and eight sheets. KiCad's own netlist of it
equals `v40_netlist.py` net for net (250 nets), and its electrical rules check finds nothing
(`reports/netlist.net`, `reports/erc.json`, `reports/video-v4.0-schematic.pdf`).

| Sheet | What is on it |
|---|---|
| 2 Bus and ports | the bus connector, the block select and its jumper, the port decode and strobes, the two control registers, the status |
| 3 CRTC and clock | the 6845, the oscillator, the dot counter, the 6845's clock, the stage registers |
| 4 Text | the text RAM, the code register, the character generator, the text shifter, the cursor flag |
| 5 Graphics RAM | the address multiplexers, the RAM, the write buffer, the two read paths, the byte latch, the shifter |
| 6 Slots | SELCPU, the write flip-flop, the -WE pulse, the RAM's -OE, the read latch's clock |
| 7 Dots and syncs | the two layers mixed, the retimed dot, the three guns, the syncs, the VGA socket |
| 8 PS2 | the ATmega328P, its latches, flags and status, the two jacks, the FTDI header |
| 9 Power | the power units, the decoupling capacitors, the LED |

| | |
|---|---|
| `gen_v40.py sch` | the local libraries and the schematic |
| `gen_v40.py project` | `video-v4.0.kicad_pro` and `.kicad_dru`: 0.25 mm tracks, 0.2 mm clearance, GND and VCC as planes |
| `gen_v40.py checknet reports/netlist.net` | KiCad's netlist of the schematic against `v40_netlist.py` |
| `gen_v40.py board reports/netlist.net <out.kicad_pcb>` | the unrouted board: every part placed, every pad on its net, the silkscreen placed |
| `gen_v40.py place <pcb>` | courtyards apart, everything inside the outline, the DIP sockets clear of each other and of the other parts |
| `gen_v40.py verify reports/netlist.net <pcb>` | 424 key connections pin by pin, in the schematic and on the board; the layers; the planes |
| `gen_v40.py drawing <pcb>` | `video-v4.0-placement.pdf` |
| `gen_v40.py bom` | `BOM.md` |
| `build.sh` | all of it, with the routing, the reports and the checks |

## The board (2026-11-12): 250 mm, placed and routed

`build.sh` makes everything from `v40_netlist.py`: the schematic, the unrouted board, the routing, the reports and
the checks. `video-v4.0.kicad_pcb` is the board: four layers (GND and VCC planes inside, the signals on the two
outer layers), the blank card's connector, 250.00 x 113.97 mm, 130 parts. `video-v4.0-placement.pdf` is its
placement drawing, on a landscape sheet as the board lies; `reports/video-v4.0-top.png` and `-bottom.png` show it
with the parts fitted.

**The length (decided 2026-11-12: 250 mm).** The 46 ICs stand in thirteen columns: eleven of 300-mil sockets and
two of 600-mil ones (the character generator over the text RAM, the graphics RAM over the 6845), a capacitor beside
every chip's VCC pin.

| | Card length |
|---|---|
| Every long card today, V2.0 with its 40 ICs among them | 218 mm |
| One column fewer, every column full to the last socket, at V2.0's spacing: no room left for the oscillator, the crystal, the jumpers or the resistors | 221 mm |
| This placement at V2.0's spacing (columns 14 mm apart) | 235 mm |
| This placement as it is: columns 15.24 mm apart | **250 mm** |

The card does not fit 218 mm. 235 mm is the shortest at V2.0's density, which routes on two signal layers only for
some component orders; the 15 mm from there to 250 are spent between the columns, as room to route.

**What stands where**, from the bus connector to the front edge: the port decode, the strobes and the block select,
with the block jumper SV1 at the bottom edge under it; the character generator over the text RAM (turned so that
its CPU port faces the bus and its display port the next column); the bus's inverters, the code register and the
stage, between the text RAM's display port and the 6845's MA pins; the graphics RAM over the 6845; the address
multiplexers; the RAM's latches and buffers; the two shifters; the clock, the counter at the bottom of its column
over the oscillator; the slot logic; the dots' and syncs' gates; the control registers and the status; the PS/2
latches; the ATmega (turned so that its crystal pins face the front).

**The layout rules** (2026-10-24 and after) are kept from the start. At the front edge, facing out: the VGA
socket, the two PS/2 jacks; beside them the INT jumper, the FTDI header and the power LED. The block jumper at the
bottom edge. Every reference with its type or value on the silk outside its part, placed by the generator clear of
every body and socket: none is under a part, none had to go into a legend. Each jumper position and the FTDI
header's pins labelled; `cottageworker.com` beside the card's name and revision. Bypass capacitors on 0.1-inch
leads.

**The routing.** Freerouting 1.9, the two outer layers, GND and VCC left to the planes; one run for each of four
orders of the components (`SEEDS`), at most 100 passes, then its optimiser (`MT=1`). All four routed every
connection (18 to 28 minutes) and were optimised (34 to 74 minutes more); three of the four had no clearance or
short of Freerouting's own making, and of those the one with the fewest vias is kept:

| | Optimised (the board) | The same order before optimising |
|---|---|---|
| Connections | 499 routed, 0 left | 499 routed, 0 left |
| Vias | 350 | 469 |
| Track, all 0.25 mm | 26.2 m: 11.0 m on the front, 15.2 m on the back | 27.2 m |
| Planes | GND and VCC, one piece each | the same |

(V2.0's board, 40 ICs on 218 mm, has 285 vias.) Freerouting does not route the same file the same way twice: a
repeat gives other figures of this size.

**The checks, all passing** (`build.sh: ALL CHECKS PASS`): KiCad's netlist of the schematic equal to
`v40_netlist.py`; ERC nothing; DRC no unconnected item, no copper violation, schematic parity 0 (four warnings
where the bus connector's own silk crosses the edge, as on every card); the board's nets equal to the schematic's
(`reports/netlist-compare.txt`: MATCH); the placement clear (130 footprints, 47 sockets); 424 key connections
right in the schematic and on the pads.

**How it got there.**
- The placement check found the VGA socket turned with its face into the board, carried over from the V3 design's
  placement, which was never checked. It faces the edge now.
- The first placement had the 6845 and the graphics RAM between the text RAM and its code register. Its routing
  left 7 of the 499 connections open in the best of four orders: three of the code's lines (VD5-VD7) in the 5 mm
  channel between the two columns of 600-mil sockets; the FTDI header's FTX, shut in by the resistors under the
  ATmega; and three ground pins of the VGA socket, which the GND plane cannot reach through thermal reliefs among
  the socket's other pins. The columns were put in the present order, the resistors moved aside, and the socket's
  ground pins connected solid to the plane: every order then routed.
- Two runs of the first routing had finished their passes and were lost to the watchdog while optimising:
  Freerouting saves only at its end. The search for a placement that routes was therefore made without the
  optimiser (`MT=0`: an answer in about half an hour), and the optimiser run on the placement that did.

Not done: `pcb-check` (it wants the order's files); a design review.

## Next

1. A design review of the board, and `pcb-check` with the order's files, before any order.
2. Beside it: the emulators' model and the ROM driver (on the branch `video-v2`).
