# cards/io — I/O card

16 I/O ports (IO-ADDR[0..3], -IO-RD/-IO-WR): 16550-style UART behind P0/P1, switch/LED port, LCD, TIL311
displays. Port map in `firmware/abi/`.

- `kicad/v1.2/` – **V1.2, designed and routed 2026-11-18, not ordered**: V1.1 to software, with a data buffer, a
  DS12885 clock on ports 6 and 7, a TTL serial header, the DB9 at the top edge and the panel under it; 218 mm, four
  layers. `io12_netlist.py` is the circuit, `gen_io12.py` and `build.sh` make the schematic, the board and the
  order's files; its `README.md` has the build and the checks, `docs/cards/io.md` section 8 the changes.
- `eagle/v1.1/` – **the built card (2020-11-29)**, in the machine; `fab/` holds its CAM output. `Notes.rtf`
  lists the 1.0→1.1 changes (TIL311 latch/VCC fixes, LED bit order, LCD keep-out, DB9 + null-modem routing,
  TIL311 broken out to its own control) and the never-done "V1.2" ideas: a directional data-bus buffer driven by
  -IO-RD, and IC5 (74138) pin 5 tied to -BUS-EN. The Working copy of this revision (2020-07-31) was the same
  board with the pre-V3.2 bus net names; folded in 2026-09-20.
- `eagle/deprecated/v1.0/` – the July-2020 first version (fabricated, retired 2021-01): no IC9 latch / IC11,
  two 1x10 headers instead of the 2x3 jumper.
