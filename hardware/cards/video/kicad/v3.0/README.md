# Video card V3.0 (HD63484, VGA) - the circuit, first cut

Not a board yet. `v30_netlist.py` is the card's circuit as data (parts, nets, the pins left open), written
2026-11-11 from the design note `docs/cards/video-v3.md` (sections 5, 10a and 10b: the ports, the parts, the memory
cycle and every control equation). `python3 v30_netlist.py` checks it: every pin of every part on a net or listed as
unconnected, no net with a single pin, no two outputs on one net.

In the first cut: the bus and the six ports' strobes, the chip, the dot counter that keeps step with the chip's
memory cycle, the address latches, two 128K RAMs and the font EPROM with their control, the shift registers, the
control register from the chip's attribute byte (colours, sync polarity), blanking in step with the dots, the VGA
output, the PS/2 keyboard and mouse section of the V2.0 card, and text method A: eight sockets (`TEXT_A`) that the
first build leaves empty - a character screen of 80 x 30 laid over the graphics. 46 ICs.

`tests/video/v30_netsim.py` runs this netlist as a circuit, with delays, against a model of the chip's memory
cycles (the design note's section 10d): the proof that the wiring does what section 10b and 10c say.

Still to add before a schematic and a board are generated (the netlist's `OPEN`): the cursor's place in the
video. Then: a timing check against the parts' data sheets, the generator (from V2.0's `gen_v20.py`), routing,
DRC, `pcb-check`, a design review. Nothing here is ordered or built.
