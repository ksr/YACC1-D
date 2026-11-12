# Video card V3.0 (HD63484, VGA) - the circuit and the schematic

Not a board yet. `v30_netlist.py` is the card's circuit as data (parts, nets, the pins left open), written
2026-11-11 from the design note `docs/cards/video-v3.md` (sections 5, 10a and 10b: the ports, the parts, the memory
cycle and every control equation). `python3 v30_netlist.py` checks it: every pin of every part on a net or listed as
unconnected, no net with a single pin, no two outputs on one net.

In it: the bus and the six ports' strobes, the chip, the dot counter that keeps step with the chip's memory cycle,
the address latches, two 128K RAMs and the font EPROM with their control, the shift registers, the control register
from the chip's attribute byte (colours, sync polarity, the text layer), the VGA output, the PS/2 keyboard and
mouse section of the V2.0 card, and text method A: eight sockets (`TEXT_A`) that the first build leaves empty - a
character screen of 80 x 30 laid over the graphics. 138 parts, 47 ICs.

`tests/video/v30_netsim.py` (in `make check`) runs this netlist as a circuit against a model of the chip's memory
cycles and against the microcode's I/O records, with every part's delays from its data sheet at both ends of their
ranges (the design note's section 10d). It is the proof that the wiring does what sections 10b and 10c say, and the
timing check: the parts in the netlist are the ones it was run with.

## The schematic (2026-11-11)

`gen_v30.py` (made from the V2.0 card's `gen_v20.py`; run it with KiCad's Python) draws the schematic from the netlist:

| | |
|---|---|
| `gen_v30.py sch` | the local libraries, `video-v3.0.kicad_sch` (the root) and its eight sheets `video-v3.0-<block>.kicad_sch` |
| `gen_v30.py project` | `video-v3.0.kicad_pro` and `.kicad_dru`: 0.25 mm tracks, 0.2 mm clearance, GND and VCC as planes |
| `gen_v30.py checknet reports/netlist.net` | the netlist KiCad exports from the schematic against `v30_netlist.py`, net by net |
| `gen_v30.py bom` | `BOM.md` |

| Sheet | What is on it |
|---|---|
| 2 Bus and ports | the bus connector, the two port decoders, CS, the latch that holds RS and R/W, the data buffer |
| 3 ACRTC and timing | the HD63484, the oscillator, the dot counter, P56 and VALID |
| 4 Frame memory | the address latches, the two RAMs, the font and its copy, the MAD buffers, MOE and -WE |
| 5 Dots | the shift registers and their load, the delay line, the two layers mixed, the dot retimed |
| 6 Control and video | the control register from the attribute byte, the guns, the syncs, the VGA socket |
| 7 Text A | text method A's eight sockets |
| 8 PS2 | the ATmega328P, its latches, flags and status, the two jacks, the FTDI header |
| 9 Power | the power units, the decoupling capacitors, the LED |

State: the schematic's exported netlist matches `v30_netlist.py` (233 nets) and KiCad's ERC reports nothing
(`reports/netlist.net`, `reports/erc.json`); the sheets as a PDF are `reports/video-v3.0-schematic.pdf`. Local symbols
(`video-v3.0-local`): the HD63484, the 32-pin static RAM, the Mini-DIN. Local footprint: the Mini-DIN (Same Sky
MD-60SM, drawn from its data sheet as on V2.0). The DE-15 socket has KiCad's own footprint for the common right-angle
part; **its row spacing is to be verified against the part bought before any order.**

## The board: waiting for its length

`gen_v30.py board reports/netlist.net <out.kicad_pcb>` writes an unrouted four-layer board, but the placement in it is
a first trial and `gen_v30.py place` does not pass. The reason is the card's size. At the V2.0 card's spacing (columns
of sockets 14 mm apart with a capacitor beside each chip, 6.3 mm between the chips of a column) the 47 ICs, with the
0.9-inch DIP-64 and four 0.6-inch parts, need about 250 mm; the outline the long cards have is 218 mm, which V2.0
filled with 40 ICs. Without text method A's eight sockets, or without the PS/2 section, the rest comes to about
218 mm. `LENGTH` in `gen_v30.py` is 250 for the trial. The choice is in `BACKLOG.md`.

Then: the placement, `build.sh` (routing, DRC, the PDFs), `pcb-check`, a design review. Nothing here is ordered or
built.
