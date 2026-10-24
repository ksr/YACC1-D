# cards/video — Video card (memory-mapped alphanumeric display)

MC6845 CRTC + IDT7134 dual-port RAM. The CPU sees 2K: the low half is display RAM (A11R grounded), the high
half addresses the CRTC. Decoded by a 7485 comparator against jumpers SV3 (installed = 0, open = 1; $D000 needs
only SV3 5–6), cascaded from -VMA, into the memory card's undecoded $D000 block. Character ROM, dot clock
and sync on the card; the LM1881 sync-converter Eagle project in `archive/eagle-projects/` is the related
composite-video experiment.

**KiCad is the master design: `kicad/v2.0/` (2026-10-22, generated from `v20_netlist.py` by `gen_v20.py` / `build.sh`;
`kicad/v1.3/`, `kicad/v1.2/` and `kicad/v1.1/` before it) — Fusion 360 abandoned for this card.**
`eagle/v1.0-fusion-export-2026-09-18/` is the Fusion export of the BUILT card (`Video_1.0.sch/.brd`, exported by Fusion as
"Blank V3.1.brd" because the design started from the blank template) and `kicad/v1.0-fusion-export-2026-09-18/` its
generated, proven conversion; both are the record of what was built. One version built, in the machine for bring-up
since 2026-10-21 with a CRTC and working. v1.1: the two 5 V nets merged into `VCC` with a joining track. v1.2 (not
ordered): v1.1 plus every bench fix up to 2026-10-21 - RS on ADDR1, LPSTB to GND, 4.7k pull-ups on N$16 and N$5 (R13,
R14), E straight from the strobe (the R1/C1 one-shot removed), IC28 a 74163, Q2 11.0592 MHz (see its README). v1.3 (not
ordered): 6 or 8 dots a character chosen by one jumper (DOTS, JP2: 80 x 24 or 64 x 24 from a 12 MHz crystal, both fonts
in one EPROM, the mode readable at `$D801` bit 0, the card ID on bit 2 = 0: latch 3D tied low; the card in the
machine reads bit 2 = 1 through a jumper on JP1 3-4; `ROM 2026-10-22` picks its geometry from them), on a new 4-layer board (In1 GND plane, In2 VCC plane) routed from
scratch (`kicad/v1.3/README.md`, `build.sh`). **V2.0** (not ordered): v1.3 plus a graphics layer (512 x 192 in 8-dot mode,
a time-shared 62256 behind the window $D800-$DFFF), the 6845 and every register on I/O ports PA-PE, two PS/2 ports on an
ATmega328P (`embedded/video-ps2`) and an INT jumper; 218 mm long, 4 layers (`kicad/v2.0/README.md`, `docs/cards/video-v2.md`).

Known issues and findings:
- **+5V rail unpowered as designed (found 2026-09-20 by the KiCad netlist proof, confirmed on the bench 2026-09-21).**
  The design has two 5 V nets with nothing joining them: `VCC` (bus pins, the implicit power pins of IC17–IC28) and `+5V`
  (IC1 74ALS08, IC2 74LS373, IC15 pin 2, RN2, R10, R12 and every decoupling cap). `+5V` reaches no connector pin, so IC1,
  IC2 and the SV3 pull-ups ran on phantom power through input clamp diodes. The two rails were joined with a wire
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
  pin-by-pin procedure in `docs/fix-6845-register-select.md`; then $D800 = address register, $D802 = data register (video RAM $D000-$D7FF, 6845 half $D800-$DFFF; confirmed 2026-09-25).
- 7416 open-collector outputs (IC27) drive IC1, IC2 and IC26 with no pull-ups; N$5 above only reads high when floating. 4.7k pull-ups fitted on the bench 2026-10-21: IC2 pin 1 to pin 20 (N$16, the latch's -OC) and IC27 pin 8 to pin 14 (N$5, /A0); the 10k on IC27 pin 12 (N$3) covers the E one-shot.
- Inherits the Blank V3.1 template's pre-V3.2 names on bus pins C3–C6 (unused by the card).

Bench state: RN2 back to the design's 10k (2026-09-21; it had been 1k since the 2026-09-18 tests — with the rail
unpowered the value never mattered; quick RAM test 8/8 with 10k); +5V and VCC joined by a wire (2026-09-21). Since 2026-10-21: the MC6845 fitted (RS on A1, LPSTB to GND),
an 11.0592 MHz crystal in Q2 (SV4 1-2; 9 MHz first, which fits only 64 columns), the pull-ups above, IC2 a 74LS373; an 80 x 24 picture with the CPU out
(`docs/procedures/VIDEO-BRINGUP.md`).

Reference: `docs/BYTE 6845.pdf` - a BYTE magazine article on the 6845 CRTC (a personal copy, added 2026-09-26).
