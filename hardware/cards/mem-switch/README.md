# cards/mem-switch — Switch-programmed ROM card

Bring-up card: toggle switches present a small hand-entered program on the data bus at $0000, so the CPU can be
exercised before any EEPROM exists. Address selection on the card; 1.1 added 74244 buffers, a BRD-SEL header,
bypass caps and (per the notes) inverted-output 74240s and switch orientation fixes.

- `eagle/v1.1/` – **the built card (2021-07-19)**; CAM output in `fab/`. `Notes.rtf` = the 1.0→1.1 change list.
- `eagle/deprecated/v1.0/` – 2021-06-23, built and worked; superseded a month later.
- Drawn on the Blank V3.1 template, so bus pins C3–C6 carry the pre-V3.2 names; the card does not use them.

Status (Ken 2026-09-20): built and used for bring-up; **not on the bus now** — removed once the memory card worked.
