# Video card V4.0 (6845, VGA, 16 dots a count) - the circuit

The circuit as data, and nothing else yet: no schematic, no board, and **not simulated**. `v40_netlist.py` is the
card's circuit (parts, nets, the pins left open), written 2026-11-12 from the design note `docs/cards/video-v4.md`
(section 5 the clock and the stage, 6 the text, 7 the graphics RAM's two modes, 8 the dot path, 9 the ports).

`python3 v40_netlist.py` checks it (in `make check`): every pin of every part on a net or listed as open, no net
with a single pin, no two outputs on one net, an output on every net of ICs, a capacitor for every IC, and the
text-only build. That is a proof that the wiring is complete, not that it is right: the simulation with the parts'
data-sheet delays is the next step, as `tests/video/v30_netsim.py` was for the V3 design, which found five faults
in a netlist that had passed this kind of check.

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

## What the netlist settles that the note left open

- **The read latch's clock** is a flip-flop's pulse in dots 8 and 0 (RDCK, IC35/B), so the latch takes the RAM's byte
  as a CPU slot ends with the whole slot for the access. Its edge and the address's change come from the same clock
  edge: the latch is a 74ACT574 for its 1 ns hold time.
- **The cursor flag** is taken with each code (IC20/A); only DE is delayed (SDE2, as dot 8 begins).
- **The -WE pulse** is IC35/A's (dots 5-6 and 13-14); -WE is NAND(WRQ AND GWR, P56 OR NOT GFX-ON).
- **The status's VSYNC and DE** (IN PC bits 1 and 2) are the stage's, a count behind the 6845's pins.
- **The vertical sync** at the connector lasts from the staged VSYNC's rise to the second HSYNC after it: about 1.8
  lines, with either maker's 6845.
- **The text-only build** needs no resistor of its own: R8, R9 and R10 are fitted in both builds.
- **46 ICs**, where the note's estimate was 42 or 43: four 74F74 where it counted two, and an inverter and an AND
  package more.

## Next

1. The simulation: this netlist run as a circuit with the parts' delays at both ends of their ranges, the 6845 and
   the bus as test benches (`tests/video/v30_netsim.py` has the models of most of these parts).
2. Then the generator for the schematic and the board, from V2.0's `gen_v20.py`, the placement (which says whether
   46 ICs fit the 218 mm card or want the 250 mm one), `pcb-check`, a review.
