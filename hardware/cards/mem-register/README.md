# cards/mem-register — 16-byte RAM card

Bring-up card: 16 bytes of register-file RAM at $0010, used with the switch ROM card to test the CPU before the
memory card. One version only.

- `eagle/v1.0/` – **the built card (2021-07-19)**; CAM output in `fab/`.
- Drawn on the Blank V3.1 template, so bus pins C3–C6 carry the pre-V3.2 names; the card does not use them.

Status (Ken 2026-09-20): built and used for bring-up; **not on the bus now** — removed once the memory card worked.
