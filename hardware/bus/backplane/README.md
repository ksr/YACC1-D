# bus/backplane

The 96-pin DIN 41612 bus backplane ("yacc2buss"): power rails, bulk decoupling, one connector per card slot.
Signal/pin assignment: `docs/system/YACC1 Connector - V3.2.pdf` and the table in `embedded/libraries/YACC/`.

- `eagle/v2.0/` – **the backplane in the machine** (2021-07/08): V1.1 plus an 8th slot (X8) and two bulk
  electrolytics (C7, C8). DXF/SVG/PDF exports beside the design; CAM output in `fab/`.
- `eagle/deprecated/v1.1/` – the 2016 gen-1 backplane (7 slots), built, still listed as Production in 2021;
  gerbers in `fab/`, `Build Notes.rtf` = the bus-card check procedure. The same design sits in `archive/gen1-2015-2018/`.
  A 2020 re-save of it in Eagle 9 (identical, one silk label removed) was dropped 2026-09-20.
