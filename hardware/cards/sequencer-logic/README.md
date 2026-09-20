# cards/sequencer-logic — Sequencer (logic half)

Instruction decode and microcode sequencing: latches the opcode, counts microcode steps, drives the control
signals onto the bus from the microcode word supplied by the sequencer-memory card (SV1/SV2 ribbon), front-panel
halt/continue, branch-condition flip-flop.

- `eagle/v2.1/` – **the built card (2020-12-01)**, the lengthened 218 x 114 mm board (file name "V2.1l"); CAM
  output in `fab/`. `Notes.rtf` = the V2.0→V2.1 change list (branch-condition SR flip-flop, split 2-byte reg/IO
  opcodes, FP-HALT/CONT naming, debugger exposure ideas).
  `orig size/` = the V2.1 circuit on the original 178 mm outline (silk still reads V2.0) and an unrouted "copy"
  with the connector moved – intermediates on the way to V2.1l, never ordered.
- `eagle/deprecated/v2.0/` – 2020-07-25, built, retired 2021-01.
- The gen-1 (2016) SEQUENCER-PROD-V1.0 / SEQUENCER-LOGIC-V1.0 material that used to sit in `old-YACC1/`
  subfolders here is byte-identical to `archive/gen1-2015-2018/` and was dropped from the card folders 2026-09-20.
