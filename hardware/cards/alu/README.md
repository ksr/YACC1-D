# cards/alu — ALU

8-bit ALU with the accumulator (AC) and TMP registers, add/subtract via an XOR array into the adders, logic
functions selected by ALU[0..3]/-ALU-FUNC, carry/borrow gated by -ADD/SUB.

- `eagle/v3.2/` – **the built card (2020-11-29)**, in the machine; `fab/` holds its CAM output. The notes
  list the changes since 3.1 (IC32 pins 4/5 flipped, AC/BDATA swapped into the add/sub circuit, CO/BO gating).
  A Working folder called "ALU-V3.3" was this same design with the bus ribbon label reverted to the pre-V3.2
  signal names and nothing else changed; it was folded away 2026-09-20. No 3.3 design was ever started.
- The Sept-2021 16-bit ALU experiment ("ALU-V3.3-16", three snapshots) and its assembler/emulator were deleted from
  this tree on Ken's instruction 2026-09-20 ("useless"); they remain only in the old YACCS tree.
- `eagle/deprecated/` – fabricated then superseded: `v3.0-2layer` (June 2020, 2-layer, CAM output in `fab/`),
  `v3.1`, `v3.1-resubmit`, `v3.1-buried-vias` (July 2020 variants). Gen-1 ALU-PROD-V1.0 (2016) is in `archive/`.
