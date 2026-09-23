# CF card (YACC1 CompactFlash interface)

A CompactFlash card for the YACC1 bus: the CF card sits in a commercial CF-to-IDE adapter on a 40-pin header and is
driven in 8-bit True IDE mode through two I/O ports - P8 (write) latches the ATA register number and a CF-reset bit,
P9 (read/write) is the selected ATA register through a 74LS245 - decoded by a 74LS138 and a 74LS32 from IO-ADDR0-3 and
the bus -IO-RD / -IO-WR strobes. It is the disk of the Y1/OS (`docs/system/OS-PLAN.md`; the software model is
`software/cfmodel.h`). Theory of operation: [`docs/cards/cf.md`](../../../docs/cards/cf.md).

| Revision | Where | Status |
|---|---|---|
| v1.0 | [`kicad/v1.0/`](kicad/v1.0/) | designed 2026-09-23: circuit `cf_netlist.py`, generated KiCad schematic + routed 2-layer board (177.83 x 114.02 mm, the blank V3.2 outline), netlist proof MATCH, DRC 0 errors / 0 unconnected, ERC 0 errors; **not yet fabricated** |

Rebuild: `hardware/cards/cf/kicad/v1.0/build.sh`. Before ordering, check the CF-to-IDE adapter's fit and power
input against J1/J2/JP1 (see `kicad/v1.0/README.md`, "Before ordering").
