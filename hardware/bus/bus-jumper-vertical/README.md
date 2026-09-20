# bus/bus-jumper-vertical

Vertical bus jumper: links two backplane connectors (X3, X4) with a power LED per side. One design, made
2020-06-16, in the machine as **V3.0**.

- `eagle/v3.0/` – schematic, `Jumper Board V3.0.brd` (the boards you have) and `Jumper Board Vertical V3.1.brd`
  (2020-06-18: identical copper, silkscreen text corrected to "VERTICAL V3.1" – the file to send if reordering).
  V3.1 was never a separate design; its folder, identical schematic and empty change note were folded in here 2026-09-20.
- The schematic is byte-identical to the horizontal jumper's; only the board differs (76 x 114 mm vertical vs 231 mm horizontal).
- `fab/` – CAM output as found in the old tree; `pdf/` – generated drawings.

Status (Ken 2026-09-20): built, **not fitted** — the jumper boards were for an older bus arrangement and are obsolete.
