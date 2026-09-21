# cards/memory — Memory card

Two 62256 SRAMs (low 32K, high 32K) + one 28C64 EEPROM (8K at $E000–$FFFF). The high half is decoded per 4K
block by IC7 (74LS138) into a 3x8 jumper header: jumper up = high RAM, down = ROM, none = undecoded (the $D000
block is left undecoded for the video card). Boot remap: FORCE-ROM (74LS74 + 74LS157) makes the ROM appear at
every address until the first access with ADDR15 high. Also carries the 16-bit TMP registers (IC26–IC29).
Verified on hardware 2026-09-18 with the bus tester; the burned EEPROM is `firmware/rom/`.

- `eagle/v1.3/` – **the card in the machine** (design 2021-03-17, ordered 2025-06-27: zip + CAM in `fab/`).
  `Notes.rtf` = the full change history 1.0→1.3 plus open ideas. `ROM ZSelect.circ` = Logisim model of the
  ROM-select logic. The KiCad conversion of this revision (proven, netlist 115/115) is in `../kicad/v1.3/` (generated, see `hardware/KICAD.md`).
  The old Working folder also held V1.0 and V1.2 files; they were duplicates of the revisions below and were
  removed 2026-09-20.
- `eagle/deprecated/v1.2/` – Production 2020-11-29 (built): -VMA gating of all chip selects, 7400 LOW-RAM -CS.
  `Memory V1.2.brd.old.brd` is an earlier 31-part layout of it. `Build Notes.rtf` = bring-up procedure.
- `eagle/deprecated/v1.1/` – 2020-06-19, files still named V1.0: adds the boot ROM remap to 1.0. Built, retired 2021-01.
- `eagle/deprecated/v1.0/` – 2020-06-18, the first card. Built, retired 2021-01.
