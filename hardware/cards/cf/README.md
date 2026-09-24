# CF card (YACC1 CompactFlash interface) — superseded

**Superseded 2026-09-23 by the I/O card v2.0** (`hardware/cards/io/kicad/v2.0/`, being designed): the backplane has
only eight slots, so the CF interface moved onto the I/O card, whose own 74LS138 (IC5, strapped to P0-P7) decodes it
on Y4/Y5 = **P4/P5**. The ROM (from build `ROM 2026-09-23B`) and both emulators use P4/P5. The v1.0 design below was
never ordered and still decodes **P8/P9**; if it were ever built, its decode would have to change to match the ROM
(U1 G1 = VCC, G2A = IO-ADDR3, G2B low, selects from Y4/Y5 instead of Y0/Y1). Its files are kept as they are. Theory of
operation of the interface as it is now: [`docs/cards/cf.md`](../../../docs/cards/cf.md).

The v1.0 card, as designed: a CompactFlash card for the YACC1 bus: the CF card sits in a commercial CF-to-IDE adapter on a 40-pin header and is
driven in 8-bit True IDE mode through two I/O ports - P8 (write) latches the ATA register number and a CF-reset bit,
P9 (read/write) is the selected ATA register through a 74LS245 - decoded by a 74LS138 and a 74LS32 from IO-ADDR0-3 and
the bus -IO-RD / -IO-WR strobes. It is the disk of the Y1/OS (`docs/system/OS-PLAN.md`; the software model is
`software/cfmodel.h`). Theory of operation: [`docs/cards/cf.md`](../../../docs/cards/cf.md).

| Revision | Where | Status |
|---|---|---|
| v1.0 | [`kicad/v1.0/`](kicad/v1.0/) | designed 2026-09-23: circuit `cf_netlist.py`, generated KiCad schematic + routed 2-layer board (177.83 x 114.02 mm, the blank V3.2 outline), netlist proof MATCH, DRC 0 errors / 0 unconnected, ERC 0 errors; **never fabricated; superseded 2026-09-23 by the I/O card v2.0** (ports P4/P5) |

Rebuild: `hardware/cards/cf/kicad/v1.0/build.sh`. (Its "Before ordering" checks in `kicad/v1.0/README.md` apply only
if the standalone card is revived.)
