# Video card V4.0 (6845, VGA, 16 dots a count) - the circuit

The circuit as data, checked and simulated; no schematic and no board yet. `v40_netlist.py` is the card's circuit
(parts, nets, the pins left open), written 2026-11-12 from the design note `docs/cards/video-v4.md` (section 5 the
clock and the stage, 6 the text, 7 the graphics RAM's two modes, 8 the dot path, 9 the ports).

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

## Next

1. The emulators' model and the ROM driver (on the branch `video-v2`).
2. The generator for the schematic and the board, from V2.0's `gen_v20.py`; the placement (which says whether 46
   ICs fit the 218 mm card or want the 250 mm one), `pcb-check`, a review.
