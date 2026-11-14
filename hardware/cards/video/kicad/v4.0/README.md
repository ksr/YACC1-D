# Video card V4.0 (6845, VGA, 16 dots a count) - the circuit, the schematic, the routed board

The circuit as data, checked and simulated; its schematic; and the board, 250 mm long, every part placed and
**every connection routed** (2026-11-12; reviewed, changed and routed again 2026-11-13). Not ordered, not built: the
pre-order check is still to come. `v40_netlist.py` is the card's circuit (parts, nets, the pins left open), written from the design note
`docs/cards/video-v4.md` (section 5 the clock and the stage, 6 the text, 7 the graphics RAM's two modes, 8 the dot
path, 9 the ports).

`python3 v40_netlist.py` checks the wiring (in `make check`): every pin of every part on a net or listed as open, no
net with a single pin, no two outputs on one net, an output on every net of ICs, a capacitor for every IC, and the
text-only build.

`tests/video/v40_netsim.py` (in `make check`, about two minutes) runs the netlist as a circuit, gate for gate, with every
part's delays from its data sheet at both ends of their ranges: the proof that the wiring does what the note says,
and the timing check. The parts in the netlist are the ones it was run with: a 74HCT or 74LS part in place of a 74F
or 74ACT one is another circuit.

**134 parts, 46 ICs** (V2.0 has 40, the V3 design 47).

| Block | ICs | |
|---|---|---|
| Bus, ports, registers | IC1-IC9 | block select (74S85), port decode (74LS138), the strobes (2 x 74LS32), control 1 and control 2 (2 x 74HCT273), the status (74LS244), inverters and ANDs (74HCT04, 74HCT08) |
| The 6845 and the clock | IC10-IC13, OSC1, R20-R23 | the 6845, the 25.175 MHz oscillator, the dot counter (74F163A), the 6845's clock and DE's delay (74F74), inverters (74ACT04); 33 ohm in series with the dot clock (R20), D2 (R21), D3 (R22) and the stage's clock (R23) |
| Text | IC14-IC23 | the text RAM (IDT7134), the stage (2 x 74ACT574), the code register (74ACT574), the character generator (AT28C64B-15), the shifter (74F299), the cursor flag and the retimed dot (74F74), the load (74F21), 74ACT86, 74ACT08 |
| Graphics, left off in the text-only build | IC24-IC34, RN2 | the address multiplexers (4 x 74ACT157), the RAM (AS6C1008-55), the write buffer (74ACT244), the read latch (74ACT574), direct mode's read buffer (74HCT244), the byte latch (74ACT574), the shifter (74F299), WRQ and TXTONLY (74F74) |
| Slot logic, dots, syncs | IC35-IC40 | P56 and the read latch's clock (74F74), 74ACT32, 74ACT00, 74ACT11, the guns (74ACT02), the vertical sync's length (74HCT74) |
| PS/2 | IC41-IC46 | V2.0's section: ATmega328P, two latches, the status, the flags, the 7416 |

The references are new (this card keeps none of V1.3's or V2.0's numbers); the PS/2 section's nets are V2.0's.

## The simulation (2026-11-12; the hold margins and the counted addresses 2026-11-13)

The simulator and the models of the 74F and 74ACT parts and of the 128K RAM are the V3 check's
(`tests/video/v30_netsim.py`); added are the 74ACT157, the 74ACT244 with its enable times, the text RAM's display
port, the character generator, a 6845 that steps a script of counts and checks the clock it is given, and the bus
as the microcode drives it, started at every phase of the dot counter. Eight corners: the 6845 slow or fast, the
parts all slow or all fast, and the two mixed corners that set rising outputs against falling ones. A clock's
series resistor (R20-R23) is a part with a delay of 0.3 to 2 ns: the resistor, its net's load and the wire, as one.

51 runs, none failing: the picture (every count's two characters and two bytes, the cursor's half, blanking, OR and
XOR, the pages, the colour bits), the window in slot mode at 3.5 MHz and in direct mode at 6 MHz (a write and two
reads at each of 32 phases of the count, the picture going on undisturbed; once more at 160 phases, 4 ns apart),
a read whose address was counted in the step before (a stack or a BRVR vector table in the window) at 2.8 MHz,
switching the mode at every phase with nothing written, the text-only build, the ports and the status, the syncs.

| Closest margins, all runs | To spare |
|---|---|
| Hold: the 6845's clock flip-flop takes the counter's D3 (IC12 pin 2) | 2.0 ns |
| Hold: the vertical sync's second flip-flop takes the first's output (IC40 pin 12) | 2.0 ns |
| Hold: the shifters' data, as the code register and the byte latch take the next byte | 2.5 ns |
| Hold: the shifters' load, as it ends | 3.7 ns |
| The retimed dot: a shifter's output through two gates to the flip-flop (set-up) | 5.6 ns |
| Hold: the 74ACT574s (the byte latch the closest) | 9.6 ns |
| Hold: the read latch | 10.7 ns |
| The shifters' load (the mode input's set-up) | 14.7 ns |
| The RAM's write pulse, 69.6 ns at its shortest | 24.6 ns over the 45 wanted |
| The RAM's data before the pulse ends | 34.6 ns |
| A byte read in slot mode at 3.5 MHz, on the bus before it is taken (160 phases) | 40 ns |
| The RAM to the read latch (set-up) | 52.1 ns |
| The text RAM (as the 70 ns grade) to the code register | 61.9 ns |
| A byte read in direct mode at 6 MHz, on the bus before it is taken | 88 ns |

The holds of 2 to 4 ns are all of one kind: a flip-flop takes what another, on the same clock edge, is changing.
They rest on the senders' least delays (2.7 ns for the 74F163A, 1.5 ns for a 74ACT574) and do not shrink with the
frequency; what they need is a clock that reaches the taker no later than the sender. The simulation prints the
least hold of each kind since the design review (its V4-5), which found that the first table here left them out.

`--limits`: the window works down to a microcode step of 531 ns in slot mode (a CPU clock of 3.76 MHz) and 248 ns in
direct mode (8.07 MHz), the parts slow, for an address that a register selected in the step puts on the bus. For an
address counted in the step before - a stack or a BRVR vector table in the window - slot mode works to 3.15 MHz
(the count within the window) and 2.97 MHz (into it), direct mode to 5.69 and 5.15 MHz: the note's rule 2.
`--faults`: 23 wiring faults put into the netlist in memory, one at a time (crossed bits, a missing gate input, the
wrong polarity): every one is reported by a run.

Not in it: the 6845's own minimum delays (its sheet gives none; 20 ns assumed, and the stage has 19 ns of hold from
a 6845 that answers in no time), Hitachi's 6845 (the figures are Motorola's sheet), a delay for each wire (the four
clock nets have one each, with their resistors; the others none), signal quality on the bus, and a bench.

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

## What the design review changed (2026-11-13)

`../../reviews/v4.0.md`: HIGH 0, MED 4, LOW 12, INFO 7. Nothing found says the card will not work; its status table
has what was done with each finding. In the circuit and on the board:

- **A 33 ohm resistor in series with each of the four clocks that cross the board**: R20 at the oscillator (the dot
  clock, seven 74F clock inputs), R21 and R22 at the counter's outputs (D2, D3), R23 at the inverter that makes the
  stage's clock. The nets between a source and its resistor are OSCO, QC, QD and STGO. A long track with several
  inputs along it and nothing at its end rings; the resistor damps it at the source.
- **The clock's column moved** two columns towards the bus connector, 30 mm: next to the multiplexers and the
  RAM's latches, and that much nearer the stage and the code register. It had been left behind when the columns
  were reordered for the first route.
- **The VGA socket is a part**: Kycon K61X-E15S-NJ, whose drawing's hole pattern is KiCad's footprint within
  0.06 mm; its fifteen signal holes are drilled 1.1 mm, as the drawing asks (the footprint: 1.0).
- **On the silk**: a "1" at the oscillator's pin 1 (turned round, the can has VCC on its ground pin); the text-only
  legend names the capacitors too; labels 0.2 mm farther from the sockets' frames.
- **In the parts list**: an oscillator rated for the load, with a socket; two shunts; the jacks to be laid on their
  footprint before soldering.
- **In the simulation and the note**, no change to the board: the hold margins, the finer phases, the reads whose
  address is counted (a stack or a vector table in the window: rule 2 of the note's section 7).

Not changed: the shifters' load stays where it is (the review weighed moving it a dot earlier, for a hold that does
not rest on the parts' least delays: it would leave the load's set-up about 6 ns where it has 14.7).

## The schematic (2026-11-12)

`gen_v40.py` (made from the V3 design's `gen_v30.py`, itself from the V2.0 card's; run it with KiCad's Python)
draws the schematic from the netlist: `video-v4.0.kicad_sch`, the root, and eight sheets. KiCad's own netlist of it
equals `v40_netlist.py` net for net (254 nets), and its electrical rules check finds nothing
(`reports/netlist.net`, `reports/erc.json`, `reports/video-v4.0-schematic.pdf`).

| Sheet | What is on it |
|---|---|
| 2 Bus and ports | the bus connector, the block select and its jumper, the port decode and strobes, the two control registers, the status |
| 3 CRTC and clock | the 6845, the oscillator, the dot counter, the 6845's clock, the stage registers, the clocks' series resistors |
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
| `gen_v40.py verify reports/netlist.net <pcb>` | 432 key connections pin by pin, in the schematic and on the board; the layers; the planes |
| `gen_v40.py drawing <pcb>` | `video-v4.0-placement.pdf` |
| `gen_v40.py bom` | `BOM.md` |
| `build.sh` | all of it, with the routing, the reports and the checks |

## The board (2026-11-12): 250 mm, placed and routed

`build.sh` makes everything from `v40_netlist.py`: the schematic, the unrouted board, the routing, the reports and
the checks. `video-v4.0.kicad_pcb` is the board: four layers (GND and VCC planes inside, the signals on the two
outer layers), the blank card's connector, 250.00 x 113.97 mm, 134 parts. `video-v4.0-placement.pdf` is its
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
multiplexers, the oscillator under them; the clock, its counter at the bottom of the column beside the oscillator
(since the design review: it stood two columns farther on); the RAM's latches and buffers; the two shifters; the
slot logic; the dots' and syncs' gates; the control registers and the status; the PS/2 latches; the ATmega (turned
so that its crystal pins face the front).

**The layout rules** (2026-10-24 and after) are kept from the start. At the front edge, facing out: the VGA
socket, the two PS/2 jacks; beside them the INT jumper, the FTDI header and the power LED. The block jumper at the
bottom edge. Every reference with its type or value on the silk outside its part, placed by the generator clear of
every body and socket: none is under a part, none had to go into a legend. Each jumper position and the FTDI
header's pins labelled; `cottageworker.com` beside the card's name and revision. Bypass capacitors on 0.1-inch
leads.

**The routing.** Freerouting 1.9, the two outer layers, GND and VCC left to the planes; one run for each of four
orders of the components (`SEEDS`), at most 100 passes, then its optimiser (`MT=1`). Of the clean results - every
connection routed, no clearance or short of Freerouting's own making - the one with the fewest vias is kept.

| | The board (2026-11-13, with the review's changes) | Before the review's changes (`feb171b`) | That one before optimising |
|---|---|---|---|
| Connections | 519 routed, 0 left | 515 routed, 0 left | 515 routed, 0 left |
| Vias | 377 | 350 | 469 |
| Track, all 0.25 mm | 27.4 m: 11.3 m on the front, 16.0 m on the back | 26.2 m | 27.2 m |
| Planes | GND and VCC, one piece each | the same | the same |

The four orders of the board's run: order 0, 377 vias and 27.4 m, clean (kept); order 1, 378 vias and 27.0 m,
clean; order 2, 362 vias, routed to the end with four shorts and a clearance error of the router's making; order 3
gave up with one connection open (IO-ADDR0 at IC2 pin 1, beside the bus connector). About 40 minutes of routing
and up to 90 of optimising, 2 h 12 min of running time in all. Before the review's changes all four orders routed
to the end, in 18 to 28 minutes: the placement is a little harder to route now. (V2.0's board, 40 ICs on 218 mm,
has 285 vias.) Freerouting does not route the same file the same way twice: a repeat gives other figures of this
size.

The connections were given as 499 here before. That is the most KiCad's rule check lists of one kind of error;
its connectivity count, which has no limit, says 515 for the first board and 519 for this one. Both boards have 0
open by that count too.

**The four clocks on this route** (measured on the board: track, and the copper's length from the series resistor
to each input):

| Net | Track | Vias | From its resistor to each input |
|---|---|---|---|
| CK (R20; 10 mm from OSC1 pin 8 to R20) | 231 mm | 2 | IC11.2 16, IC12.3 37, IC20.11 75, IC19.12 94, IC33.12 130, IC35.3 180, IC35.11 188 mm |
| D2 (R21) | 246 mm | 3 | IC34.3 17, IC20.3 33, IC13.3 60, IC21.9 72, IC38.11 73, IC32.11 78, IC17.11 96, IC36.1 101 mm |
| D3 (R22) | 232 mm | 5 | IC12.2 53, IC12.11 63, IC13.1 83, IC24.2 106, IC14.6 117 mm |
| STG (R23) | 237 mm | 5 | IC22.4 99, IC16.11 122, IC15.11 153 mm |

Before the review's changes: CK 177 mm (its farthest input at 166), D2 267 (197), D3 241 (128), STG 239 (200). So
D2's inputs are half as far away as they were and the stage a quarter nearer, and the dot clock's are farther: the
counter moved away from the shifters and the slot logic's flip-flops, which stayed. And the router treats a clock
as any net: order 1 of the same run has CK's farthest input at 137 mm and D2's at 228. **The clocks are not routed
first and kept**, which would make them short by construction: open, see Next.

**The checks, all passing** (`build.sh: ALL CHECKS PASS`): KiCad's netlist of the schematic equal to
`v40_netlist.py`; ERC nothing; DRC no unconnected item, no copper violation, schematic parity 0 (four warnings
where the bus connector's own silk crosses the edge, as on every card); the board's nets equal to the schematic's
(`reports/netlist-compare.txt`: MATCH); the placement clear (134 footprints, 47 sockets); 432 key connections
right in the schematic and on the pads.

**How it got there.**
- The placement check found the VGA socket turned with its face into the board, carried over from the V3 design's
  placement, which was never checked. It faces the edge now.
- The first placement had the 6845 and the graphics RAM between the text RAM and its code register. Its routing
  left 7 of the 515 connections open in the best of four orders: three of the code's lines (VD5-VD7) in the 5 mm
  channel between the two columns of 600-mil sockets; the FTDI header's FTX, shut in by the resistors under the
  ATmega; and three ground pins of the VGA socket, which the GND plane cannot reach through thermal reliefs among
  the socket's other pins. The columns were put in the present order, the resistors moved aside, and the socket's
  ground pins connected solid to the plane: every order then routed.
- Two runs of the first routing had finished their passes and were lost to the watchdog while optimising:
  Freerouting saves only at its end. The search for a placement that routes was therefore made without the
  optimiser (`MT=0`: an answer in about half an hour), and the optimiser run on the placement that did.

**The design review (2026-11-13): `hardware/cards/video/reviews/v4.0.md`. HIGH 0, MED 4, LOW 12, INFO 7.** Its
four MED findings: the dot clock on 177 mm of branched, unterminated track to seven inputs (V4-1); D2, D3 and STG
240 to 270 mm long, the counter far from the registers it clocks (V4-2); no part named for the VGA socket to check
its footprint against (V4-3); a stack or a BRVR vector table in the window fails in slot mode above about 2.8 MHz,
which the note's rules allowed (V4-4). **Its changes are made and the board is routed again (2026-11-13)**: "What
the design review changed" above, and the review's status table for each finding. V4-3 and V4-4 are closed. V4-1
and V4-2 have their resistors; the clocks' lengths are as the table above shows, not all shorter.

Not done: `pcb-check` (it wants the order's files).

## Next

1. To decide: the four clocks routed first and kept (a change to `build.sh` and one more routing run), or the board
   as it is, with every clock behind its series resistor.
2. `pcb-check` with the order's files, before any order. The VGA socket laid on a 1:1 print of the board.
3. Beside it: the emulators' model and the ROM driver (on the branch `video-v2`).
