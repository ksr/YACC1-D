# cards/register — Index Registers

Four 16-bit index registers per card (R0..R3 on card 0, R4..R7 on card 1), selected on the address bus by
ADDR-REG-ID0..3 (C3–C6): IC38 decodes bits 0–1 to the register and bits 2–3, through jumper J3, to the card.
Loaded/read in 8-bit halves (-REG-LD-HI/LO, -REG-RD-HI/LO) with up/down counting (-REG-UP/-REG-DN).

- `eagle/v1.1/` – **the built card (2020-08-31)**, in the machine; `fab/` holds its CAM output.
  `Notes.rtf` is the later note from the "1.2" folder: it lists the 1.0→1.1 changes and asks whether bus direction
  should be based on -RD-SEL – that question is the entire content of "1.2"; the 1.2 design files were the 1.1 files renamed
  (folded in 2026-09-20).
- `eagle/deprecated/v1.0/` and `v1.0-no-address/` – the June-2020 first versions (fabricated, retired).
- Gen-1 (2016) REGISTER-PROD-V1.2 is a different card: `archive/gen1-2015-2018/`.
