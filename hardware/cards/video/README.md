# cards/video — Video card (memory-mapped alphanumeric display)

MC6845 CRTC + IDT7134 dual-port RAM. The CPU sees 2K: the low half is display RAM (A11R grounded), the high
half addresses the CRTC. Decoded by a 7485 comparator against jumpers SV3 (installed = 0, open = 1; $D000 needs
only SV3 5–6), cascaded from -VMA, into the memory card's undecoded $D000 block. Character ROM, dot clock
and sync on the card; the LM1881 sync-converter Eagle project in `archive/eagle-projects/` is the related
composite-video experiment.

**Fusion 360 is the master design.** `eagle/v1.0-fusion-export-2026-09-18/` is the Eagle export taken that day:
`Video_1.0.sch` and `Video_1.0.brd` (exported by Fusion as "Blank V3.1.brd" because the design was started from the
blank card template; stored here under the matching name so Eagle links the pair). One version, built, in the
machine for bring-up without a CRTC fitted.

Known issues (bus-driver tests 2026-09-18):
- as drawn, the 6845 data register is unreachable: CS needs A0 = 0 while RS = A0;
- 7416 open-collector outputs drive lines with no pull-ups;
- write-through fault: a write to block 0 or block 9 (A0 = 0, A11 = 0, -MEM-WR falling edge, -VMA asserted)
  lands in the video RAM regardless of the board-select comparator; independent of the memory card and of the
  RN2 value. Needs a logic-analyser capture on IC18 pin 6 (see the ADP2230 plan) or a 7485 swap.
- Inherits the Blank V3.1 template's pre-V3.2 names on bus pins C3–C6 (unused by the card).

Bench state: RN2 is currently 1k (design: 10k), changed during the 2026-09-18 tests and left in (Ken 2026-09-20).
