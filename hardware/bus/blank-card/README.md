# bus/blank-card

Starting point for a new card: the bus connector(s), card outline and mounting, with every bus signal named.
`eagle/v3.1/` (2020-08-23) = the Bus Template V3.1 schematic on the card outline; ordered 2025-06-27 as a bare
board (zip + Fusion CAM output in `fab/`) and used as the base of the video card.

**Caution:** it carries the Bus V3.1 signal names, i.e. C3–C6 are labelled -ADDR-REG-RD0/LD0/RD1/LD1. The machine
is built to Bus V3.2, where those pins are ADDR-REG-ID0..3 (see `hardware/FABRICATED.md` notes and
`docs/system/`). Any card drawn on this template inherits the stale names (Mem Switch, Mem Register and the video
card did). `eagle/v3.2/` (derived 2026-09-20, see its README) is V3.1 with those four nets renamed to the V3.2 names: **start new cards from V3.2.**
