# cards/memory — Memory card

Two 62256 SRAMs (low 32K, high 32K) + one 28C64 EEPROM (8K at $E000–$FFFF). The high half is decoded per 4K
block by IC7 (74LS138) into a 3x8 jumper header: jumper up = high RAM, down = ROM, none = undecoded (the $D000
block is left undecoded for the video card). Boot remap: FORCE-ROM (74LS74 + 74LS157) makes the ROM appear at
every address until the first access with ADDR15 high. Also carries the 16-bit TMP registers (IC26–IC29).
Verified on hardware 2026-09-18 with the bus tester; the burned EEPROM is `firmware/rom/`.

- `eagle/v1.3/` – **the card in the machine**: Ken's Fusion 360 export (2026-09-24) of the design
  JLCPCB fabricated on 2025-06-27 (order 2000765A, 4 layers; the order archive is in `fab/`). Proven against the order's
  gerbers by `tools/verify_fab_vs_brd.py` (every hole, every track, part list, pick-and-place; see its README). Adds
  **IC15 74ALS11**: the 74245 data buffer (IC5) is enabled by AND(-LO-RAM, -HI-RAM, -ROM-CS), i.e. only while one of
  the card's own chips is selected, instead of by -VMA, so it stays off the bus in undecoded blocks (the video card's
  $D000). The TMP registers IC26–IC29 and RN5/RN6 are placed and routed. KiCad conversion (proven): `kicad/v1.3/`.
  (Filed first as `eagle/v1.3-fusion-export-2026-09-24/`, renamed to `v1.3` the same day.)
- `kicad/v2.0/` – memory card v2.0 design: the built v1.3 + the CompactFlash interface on P8/P9. Schematic proven. With the
  built card's copper kept the CF section did not fit, so Ken decided (2026-09-24) to lay the whole card out again:
  three re-layout options with J2 at the top edge; B was picked and routed (fab files), then Ken decided the same day
  that the CF adapter (HX-2118P) mounts on two M3 standoffs on the card with J2 parallel to X1: standoff options A / B,
  trial-routed complete, with 1:1 check prints; Ken picks (the top-edge board is kept in `options-top-edge-J2/`).
- `eagle/deprecated/v1.3-do-not-use/` – **DO NOT USE: earlier save (notes 2025-03-06, board 2021-03-17), NOT the built
  card** (found 2026-09-24; it was `eagle/v1.3/` until Ken renamed and deprecated it the same day): no IC15
  (IC5 pin 19 on -VMA), TMP registers and RN5/RN6 off the board and unrouted. Kept for its history: `Notes.rtf`/`.md`
  = the full change history 1.0→1.3 plus open ideas; `ROM ZSelect.circ` = Logisim model of the ROM-select logic.
  `fab/Memory V1_2025-06-27.zip` is the built card's gerber set (byte-identical to the one in the order archive);
  `fab/CAMOutputs/` are older CAM runs. Its KiCad conversion is `kicad/deprecated/v1.3-do-not-use/`.
  The old Working folder also held V1.0 and V1.2 files; they were duplicates of the revisions below and were
  removed 2026-09-20.
- `eagle/deprecated/v1.2/` – Production 2020-11-29 (built): -VMA gating of all chip selects, 7400 LOW-RAM -CS.
  `Memory V1.2.brd.old.brd` is an earlier 31-part layout of it. `Build Notes.rtf` = bring-up procedure.
- `eagle/deprecated/v1.1/` – 2020-06-19, files still named V1.0: adds the boot ROM remap to 1.0. Built, retired 2021-01.
- `eagle/deprecated/v1.0/` – 2020-06-18, the first card. Built, retired 2021-01.
