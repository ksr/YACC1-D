# cards/video — Video card (memory-mapped alphanumeric display)

MC6845 CRTC + IDT7134 dual-port RAM. The CPU sees 2K: the low half is display RAM (A11R grounded), the high
half addresses the CRTC. Decoded by a 7485 comparator against jumpers SV3 (installed = 0, open = 1; $D000 needs
only SV3 5–6), cascaded from -VMA, into the memory card's undecoded $D000 block. Character ROM, dot clock
and sync on the card; the LM1881 sync-converter Eagle project in `archive/eagle-projects/` is the related
composite-video experiment.

**KiCad is the master design (Ken, 2026-09-21): `kicad/v1.1/` — hand-maintained, Fusion 360 abandoned for this card.**
`eagle/v1.0-fusion-export-2026-09-18/` is the Fusion export of the BUILT card (`Video_1.0.sch/.brd`, exported by Fusion as
"Blank V3.1.brd" because the design started from the blank template) and `kicad/v1.0-fusion-export-2026-09-18/` its
generated, proven conversion; both are the record of what was built. One version built, in the machine for bring-up
without a CRTC fitted. v1.1 so far: the two 5 V nets merged into `VCC` with a joining track (see its README).

Known issues and findings:
- **+5V rail unpowered as designed (found 2026-09-20 by the KiCad netlist proof, confirmed on the bench 2026-09-21).**
  The design has two 5 V nets with nothing joining them: `VCC` (bus pins, the implicit power pins of IC17–IC28) and `+5V`
  (IC1 74ALS08, IC2 74LS373, IC15 pin 2, RN2, R10, R12 and every decoupling cap). `+5V` reaches no connector pin, so IC1,
  IC2 and the SV3 pull-ups ran on phantom power through input clamp diodes. Ken joined the two rails with a wire
  (2026-09-21); after that the write-through fault below was gone. The KiCad conversion's `reports/netlist-compare.txt`
  shows the two nets.
- **Write-through fault — RESOLVED 2026-09-21.** On 2026-09-18 a write to block 0 or block 9 (A0 = 0, A11 = 0, -MEM-WR
  falling edge, -VMA asserted) landed in the video RAM regardless of the board-select comparator. Cause: the unpowered
  `+5V` rail (IC1 drives BOARDSEL into the 7485, RN2 pulls the SV3 jumper inputs up to that rail). With the rails joined,
  `tests/video/video_ram_test.py` passes 8/8 over all 1K (patterns, inverse, neighbour isolation, writes from $0010/$9010/
  $0011/$1010 never reach $D010, read stability) and `tools/alias_min.py` reports no fault.
- **6845 data register unreachable as drawn.** -CS (IC17 pin 25) = NAND(BOARDSEL, A11 AND /A0): IC19 pin 3, from IC1 pin 11
  (A11 AND N$5) where N$5 = IC27 pin 8 = /A0. RS is A0. So the chip is only selected with A0 = 0, which is always RS = 0:
  only the address register is reachable, the data register never. Bench fix: lift IC1 pin 13 off IC27 pin 8 and tie it
  high is WRONG (odd addresses drive the JP1 read-back latch IC2 onto the bus). Correct fix: move RS from A0 to A1 —
  pin-by-pin procedure in `docs/fix-6845-register-select.md`; then $D400 = address register, $D402 = data register.
- 7416 open-collector outputs (IC27) drive IC1, IC2 and IC26 with no pull-ups; N$5 above only reads high when floating.
- Inherits the Blank V3.1 template's pre-V3.2 names on bus pins C3–C6 (unused by the card).

Bench state: RN2 back to the design's 10k (Ken 2026-09-21; it had been 1k since the 2026-09-18 tests — with the rail
unpowered the value never mattered; quick RAM test 8/8 with 10k); +5V and VCC joined by a wire (Ken 2026-09-21). No 6845 fitted.
