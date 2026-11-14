# Video card V4.0 (6845, VGA, 16 dots a count) - the circuit, the schematic, the routed board

The circuit as data, checked and simulated; its schematic; and the board, 250 mm long, every part placed and
**every connection routed** (2026-11-12; reviewed, changed and routed again 2026-11-13; routed once more
2026-11-14, its four clocks laid first). Not ordered, not built. The pre-order check (`pcb-check`, 2026-11-14)
finds no failure and leaves one warning: "The pre-order check", below. `v40_netlist.py` is the card's circuit (parts, nets, the pins left open), written from the design note
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
- **The four clocks are laid before the rest of the board** (decided 2026-11-13, on the board since 2026-11-14):
  by `gen_v40.py clockroute`, as trees from their resistors, locked while Freerouting routes everything else. "The
  routing", below.
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
| `gen_v40.py clockroute <unrouted.kicad_pcb> <out.kicad_pcb>` | the four clocks, and the stubs from their sources to the series resistors, laid as locked tracks and vias; nothing else touched |
| `gen_v40.py clocks <pcb> [report.txt]` | the clock nets as they are on a board: track, vias, the copper's length from each source to every input (`reports/clocks.txt`). Fails if an input is not reached or a clock's track is not locked |
| `gen_v40.py verify reports/netlist.net <pcb>` | 432 key connections pin by pin, in the schematic and on the board; the layers; the planes |
| `gen_v40.py drawing <pcb>` | `video-v4.0-placement.pdf` |
| `gen_v40.py bom` | `BOM.md` |
| `gen_v40.py fab <pcb>` | the order's files: `gerbers/` and `video-v4.0-gerbers.zip`. It orders nothing |
| `build.sh` | all of it, with the routing, the reports, the checks and, when they pass, the order's files |
| `SILK=1 build.sh` | the routed board kept: its silkscreen texts written and placed afresh, then the reports, the checks and the order's files |

## The board (2026-11-12): 250 mm, placed and routed

`build.sh` makes everything from `v40_netlist.py`: the schematic, the unrouted board, the clocks, the routing, the
reports and the checks. `video-v4.0.kicad_pcb` is the board: four layers (GND and VCC planes inside, the signals on the two
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

**The routing.** The four clocks first, by the generator (below). Then Freerouting 1.9 for the other 492
connections, on the two outer layers, GND and VCC left to the planes: one run for each of four orders of the
components (`SEEDS`), at most 100 passes, then its optimiser (`MT=1`). Of the clean results - every connection
routed, no clearance or short of Freerouting's own making, the clocks as they were laid - the one with the fewest
vias is kept.

| | The board (2026-11-14, the clocks laid first) | The route of 2026-11-13 (`3d9a12f`: the review's changes, the clocks the router's own) | Before the review's changes (`feb171b`) | That one before optimising |
|---|---|---|---|---|
| Connections | 519 routed, 0 left | 519 routed, 0 left | 515 routed, 0 left | 515 routed, 0 left |
| Vias | 455, nine of them the clocks' | 377 | 350 | 469 |
| Track, all 0.25 mm | 27.6 m: 11.8 m on the front, 15.8 m on the back | 27.4 m: 11.3 m and 16.0 m | 26.2 m | 27.2 m |
| Planes | GND and VCC, one piece each | the same | the same | the same |

The four orders of the board's run: order 0 routed every connection, clean, 455 vias and 27.6 m after optimising
(kept); orders 1 and 3 stopped with two connections open and order 2 with one (orders 1 and 2 with shorts and
clearance errors of the router's making besides). 40 to 57 minutes of routing each, and 1 h 56 min of optimising
for the one that was complete: 2 h 40 min of running time in all. The run of 2026-11-13, with nothing fixed, had
three orders of four complete after about 40 minutes (order 0 kept; order 1 as good, 378 vias; order 3 left
IO-ADDR0 open at IC2 pin 1), and the board before the review's changes all four in 18 to 28 minutes. Fixed clocks
cost 78 vias and leave the router less room. (V2.0's board, 40 ICs on 218 mm, has 285 vias.) Freerouting does not
route the same file the same way twice: a repeat gives other figures of this size. The clocks are the same on
every build.

The connections were given as 499 here before. That is the most KiCad's rule check lists of one kind of error;
its connectivity count, which has no limit, says 515 for the first board and 519 for this one. Both boards have 0
open by that count too.

**The four clocks: laid first, and kept** (`gen_v40.py clockroute`; decided 2026-11-13). Freerouting does not
know a clock from any other net. On the route of 2026-11-13 the dot clock's farthest input was 188 mm from its
resistor and D2's 101; on another clean route of the same run, 137 and 228. Given the clocks alone on the empty
board it strings a net's inputs into one chain and leaves connections open. So the generator lays them: each net a
tree that grows from its series resistor one input at a time, the next input always the one that is cheapest to
reach, where the price is the new track plus `CK_ALPHA` (0.6) times the distance along the tree from the resistor
to the point where the branch leaves it (0 would give the least track, 1 every input its own shortest way). The
ways are found on a 0.25 mm grid over both outer layers, round every other net's pads at the board's clearance.
The tracks and vias are locked: KiCad's Specctra export hands them to Freerouting as fixed wiring, and its session
import leaves locked items alone. `build.sh` runs KiCad's rule check on the clocks alone before the routing and
`gen_v40.py clocks` on every result after it: an input that is not reached, or a clock track that is not locked,
fails the build.

Measured on the board (`reports/clocks.txt`: track, and the copper's length from the series resistor to each
input):

| Net | Track | Vias | From its resistor to each input |
|---|---|---|---|
| CK (R20; 10 mm from OSC1 pin 8 to R20) | 187 mm | 1 | IC11.2 16, IC12.3 35, IC19.12 46, IC20.11 54, IC33.12 77, IC35.3 125, IC35.11 134 mm |
| D2 (R21; 6 mm from IC11 pin 12 to R21) | 288 mm | 5 | IC34.3 18, IC20.3 34, IC38.11 45, IC32.11 64, IC13.3 81, IC21.9 84, IC36.1 86, IC17.11 91 mm |
| D3 (R22; 5 mm from IC11 pin 11 to R22) | 185 mm | 2 | IC12.11 41, IC12.2 50, IC14.6 73, IC13.1 75, IC24.2 108 mm |
| STG (R23; 8 mm from IC13 pin 2 to R23) | 172 mm | 1 | IC22.4 70, IC15.11 71, IC16.11 102 mm |

| The way to the farthest input | The board | The route of 2026-11-13 | Before the review's changes |
|---|---|---|---|
| CK | 134 mm | 188 mm | 166 mm |
| D2 | 91 mm | 101 mm | 197 mm |
| D3 | 108 mm | 117 mm | 128 mm |
| STG | 102 mm | 153 mm | 200 mm |

On the route of 2026-11-13 the clocks had 231, 246, 232 and 237 mm of track; before the review's changes 177,
267, 241 and 239.

**The clocks follow the layers' grain** (`CK_GRAIN`, `CK_VIA`). Freerouting lays this board's tracks across the
board on the top and up and down it on the bottom (on the route of 2026-11-13, 9.2 m of the top's 11.3 m ran
across and 8.9 m of the bottom's 16.0 m up and down), so that the layers can cross anywhere. A track the other way
is a wall on its layer: whatever crosses it needs two vias, or goes round. The first clock trees (2026-11-13) had
no vias and took the shortest way on either layer: 188 mm up and down on the top and 175 mm across on the bottom,
their farthest inputs at 131, 102, 98 and 90 mm. Round them the rest did not route: 5, 4, 7 and 12 connections
open in the four orders after all 100 passes (two hours), with 580 to 680 vias. So a step across a layer's grain
costs three times its length and a slanted one one and a half times, and a clock changes sides in a via (at the
price of 3 mm of track) as well as in its own pads. The trees now have 1 mm across the grain on each layer and
nine vias; CK's, D3's and STG's farthest inputs are 3 to 12 mm farther than the first trees', D2's 11 mm nearer.

**The checks, all passing** (`build.sh: ALL CHECKS PASS`): KiCad's netlist of the schematic equal to
`v40_netlist.py`; ERC nothing; DRC no unconnected item, no copper violation, schematic parity 0 (four warnings
where the bus connector's own silk crosses the edge, as on every card); the board's nets equal to the schematic's
(`reports/netlist-compare.txt`: MATCH); the placement clear (134 footprints, 47 sockets); 432 key connections
right in the schematic and on the pads; the clocks as they were laid, every input reached and every track locked.

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
and V4-2 have their resistors, and since 2026-11-14 the clocks are laid first: each one's farthest input is nearer
than on either route before.

## The pre-order check (2026-11-14): no failures, one warning

`~/Developer/pcb-check/pcb-check video-v4.0.kicad_pcb video-v4.0-gerbers.zip --layers 4`, with the settings in
`pcb-check.ini` beside the board. The order's files are `gerbers/` and `video-v4.0-gerbers.zip`, written by
`gen_v40.py fab` (and by `build.sh` after every build whose checks pass); `video-v4.0-jlcpcb-order.txt` has the
order's parameters. **Nothing is ordered.**

What it proves from the zip alone: the four copper layers, 1630 plated holes and 1175 pads rebuilt from the gerbers
and the drill files give the schematic's 254 nets with no short and no open; each plane is one piece; the layers
are in order; the outline is closed, 250.0 x 114.0 mm; the plated and the two non-plated holes are in files of their
own. And on the board: the bus connector's 96 pins as the Bus Template V3.2 has them (`tools/bus_pins.py` reads
them from the template's schematic); every chip's footprint as the real part's; the bypass capacitors on 2.54 mm;
the name, the revision and `cottageworker.com` on the silk; every reference and value on the silk clear of the
parts; the panel parts at the front edge; one revision, 4.0, in the settings, the schematic, the job file and the
zip's name; the tree as committed.

| | |
|---|---|
| WARN, DESIGN | Two inputs with nothing on them: IC28 pin 1 and OSC1 pin 1. IC28's pin 1 is not connected inside the AS6C1008 (it is A18 of the 512K part with the same pins: the symbol calls it NC/A18). OSC1's pin 1 has no connection in a plain oscillator can and is the enable of one that has it, with its own pull-up: running when left open. **To confirm on the data sheet of the oscillator that is bought** (the note's section 13) |
| NOTE | INTOC, the PS/2 interrupt's open-collector output, has its pull-up on another card: with JP1 on it is the bus's -INT, pulled up on the I/O card (RN2) |

The first run had four more warnings, all settled the same day. No bus definition, and the front edge taken for the
bottom one: the settings `bus_pins` and `bus_edge`. The zip not committed: it is. Three values not found on the
silk: IC10, IC28 and IC41 were shortened to "68B45", "AS6C1008-55" and "ATmega328P", and now read as the parts list
has them, "HD68B45SP / MC68B45P", "AS6C1008-55PCN" and "ATmega328P-P" (the silk only, by `SILK=1 build.sh`: no
part, track or via moved, and of the gerbers only the front silkscreen differs).

With `--tests` the check also runs the system's tests (`make && make check`, the settings' `tests`): they pass
(2026-11-14).

Still by hand before an order: the check's four pictures of the copper, by eye; the zip in the fab's own gerber
viewer; the VGA socket laid on a 1:1 print of the board.

## Next

1. Before any order: `pcb-check` once more on the board as it then is, its pictures and the fab's viewer; the VGA
   socket laid on a 1:1 print of the board; the oscillator's data sheet for its pin 1.
2. The emulators' model and the ROM's text driver are on the branch `video-v2` (2026-11-14: `Y1VID_CARD=v4`,
   `ROM 2026-11-14 V4`; the note's section 12). Open there: graphics, and Y1/OS on 25 rows.
3. IC18's image is `firmware/video/chargen-v40.bin` (2026-11-14: Terminus Font's bold 8 x 16; `firmware/video/README.md`
   has the codes and the burn command). `python3 tools/vidsim.py testcard --card v4 --raster --png card.png` draws what
   the card should show.
