# yacc1-cf-card v1.0 — KiCad design (generated from `cf_netlist.py`)

> **Superseded 2026-09-23, never ordered.** The CF interface moved onto the I/O card v2.0
> (`hardware/cards/io/kicad/v2.0/`), decoded by that card's IC5 on Y4/Y5 = **P4/P5**; the ROM (from `ROM 2026-09-23B`)
> and both emulators use P4/P5. This design still decodes **P8/P9** (U1 G1 = IO-ADDR3, Y0/Y1). If it were ever built,
> change the decode to match the ROM first: U1 G1 (pin 6) = VCC, G2A (pin 4) = IO-ADDR3, G2B (pin 5) low, and take the
> selects from Y4 (pin 11) and Y5 (pin 10). The files below are kept unchanged as the reference for the circuit after
> the decoder, which v2.0 reuses. Theory: [`docs/cards/cf.md`](../../../../../docs/cards/cf.md).

The YACC1 CompactFlash card: a CF card in a commercial CF-to-IDE adapter, driven in 8-bit True IDE mode through two
I/O ports. P8 (write) is a 74LS175 latch holding the ATA register number (DA0-2) and a CF-reset bit; P9 (read/write)
is the selected ATA register through a 74LS245. A 74LS138 decodes the port and a 74LS32 gates the bus strobes. Theory of
operation: [`docs/cards/cf.md`](../../../../../docs/cards/cf.md).

**The circuit lives in `cf_netlist.py`** (parts, nets, no-connects, `check()`). `gen_cf.py` draws the schematic and
places the board from it; `build.sh` routes, checks and makes the fab files. To change the card, edit `cf_netlist.py`
and re-run `build.sh`. If you hand-edit the schematic or board in KiCad instead, stop running `gen_cf.py` (it rewrites
both) and say so here: from then on the KiCad files are the master and `compare_netlist.py` tells you whether they
still match `cf_netlist.py`.

`MASTER` marks this folder as hand-maintained (not written by `tools/eagle_to_kicad_all.py`).

## Files

| File | What it is |
|---|---|
| `cf_netlist.py` | **the circuit** (single source): 26 parts, 46 nets, 23 documented no-connect pins |
| `gen_cf.py` | writes the schematic, the placed board, the project and the local libraries (KiCad's Python) |
| `build.sh` | the whole pipeline, below; exit status 0 = every gate passed |
| `compare_netlist.py` | the netlist proof: schematic and board vs `cf_netlist.py`, pin for pin |
| `yacc1-cf-card.kicad_pro` | project: design rules (0.25 mm min track/clearance; net class Default 0.3 mm track / 0.25 mm clearance, via 0.8/0.4; class Power = VCC, GND, PIN20: 0.6 mm track / 0.3 mm clearance, via 1.0/0.5; 0.5 mm copper-to-edge) |
| `yacc1-cf-card.kicad_sch` | schematic, one A3 sheet in functional groups (bus connector, decode + strobe gating, P8 latch, data buffer, IDE header + pull-ups + adapter power, LEDs, power + decoupling, design notes); no text overlaps anything and nothing leaves the frame (`tools/kicad/sch_overlaps.py`: 0 / 0 / 0, frame 0) |
| `yacc1-cf-card.kicad_pcb` | the routed 2-layer board |
| `yacc1-cf-card.ses` | the Freerouting result imported into the board |
| `blank-card-v3.2-eagle.kicad_sym` | local symbol `FABC96R`: the bus connector as three 32-pin units (rows a/b/c), pin numbers A1..C32, pin names = the V3.2 bus signals (from the blank card's pads); 5.08 mm pins so the three-character pin numbers clear the body and the no-connect flags |
| `blank-card-v3.2-eagle.pretty/FABC96R.kicad_mod` | the bus connector footprint, copied unchanged from `hardware/bus/blank-card/kicad/v3.2/` |
| `sym-lib-table`, `fp-lib-table` | the two local libraries (`${KIPRJMOD}`, nothing outside this folder) |
| `yacc1-cf-card-schematic.pdf` | schematic plot |
| `yacc1-cf-card-placement.pdf` | parts placement (silk + fab + outline) |
| `yacc1-cf-card-render-top.png` | 3D render, top |
| `yacc1-cf-card-bom.csv` | bill of materials from the schematic (grouped by value + footprint) |
| `gerbers/`, `yacc1-cf-card-gerbers.zip` | F/B copper, mask, silk, Edge.Cuts, Excellon drill (mm) + drill map, job file |
| `reports/` | DRC and ERC (`.rpt` + `.json`), the schematic netlist (`.net`), `netlist-proof.txt`, Freerouting logs |

## Rebuild

    hardware/cards/cf/kicad/v1.0/build.sh            # ~1 minute; NOROUTE=1 skips routing and fab files

1. `gen_cf.py`: local libraries; the schematic (KiCad standard symbols from `74xx`, `Device`, `Connector_Generic`,
   `power`, embedded in `lib_symbols`; every pin gets a short wire stub to a net label or a power symbol, no-connect
   flags on the `NO_CONNECT` pins and the 69 bus pins the card does not use; Reference/Value go where the library puts
   them unless that is on the body (the 74xx gates) or drawn rotated (R, C, LED): then above/below the body, or beside
   it for parts with pins only top and bottom (`auto_fields()`); KiCad re-saves it with
   `kicad-cli sch upgrade`); the board, started from a copy of the blank V3.2 card (outline, X1 at its place, the
   site text; its own power LED and 330R removed because their footprints and values differ from the netlist's
   LED1/R7), every footprint from `PARTS`, every pad on its net, GND pours on both layers, 4 mm copper keepouts
   round the two DIN mounting screws; each footprint linked to its symbol (DRC schematic parity is clean).
2. Specctra DSN without the pours (`tools/kicad/kicad_route.py export_dsn`), so GND is routed as tracks.
3. Freerouting 1.9 (`-mt 1`, 20-minute watchdog). About 30-40 s here (auto-route ~4 s, then the optimizer).
4. Import, straight-stitch any trivial 2-pad net the router missed, pull edge-hugging tracks in, fill the pours,
   and give any GND pad whose thermal spokes land on a local fill island a solid pad-level connection (such a pad
   is already track-routed; the build log names them, typically 3-7 IC/cap GND pins; the set varies run to run).
5. DRC with schematic parity. 6. ERC. 7. Netlist proof. 8. Gerbers, drill, zip, placement PDF, render, BOM,
   schematic PDF.

Freerouting is not fully deterministic: each rebuild gives a slightly different (equally valid) routing.

## Results (build of 2026-09-23)

- **Netlist proof: MATCH.** The netlist KiCad exports from the schematic and the pad nets of the board each equal
  `cf_netlist.py` exactly: 46 nets, 171 net pins, same names; the 92 unconnected pins are exactly the 23 `NO_CONNECT`
  pins plus the 69 unused bus pins; all 26 parts with their values and footprints (`reports/netlist-proof.txt`).
- **DRC: 0 errors, 0 unconnected, schematic parity 0.** 8 cosmetic warnings, all inherited from the blank card's
  connector footprint: 4 `silk_edge_clearance` (X1's outline silk reaches the board edge) and 2 + 2 `text_height` /
  `text_thickness` (X1's 0.73 mm "1"/"32" row markers).
- **ERC: 0 errors, 1 warning:** `isolated_pin_label` on `SRST`, U3 Q3 (latch bit 3, true output), which is a
  one-pin net by design (a probe point; the card uses -Q3 = `-SRST`).
- Board **177.83 x 114.02 mm** (the blank V3.2 card outline), **2 layers**, through-hole only; 26 parts (5 ICs,
  X1, J1, J2, JP1, RN1, R1-R7, LED1-3, C1-C6); ~500 track segments, ~20 vias; signals 0.3 mm, VCC/GND/PIN20 0.6 mm,
  GND pour both sides.

## Notes on names

- `PARTS` names `Device:CP` for C6; KiCad 10 calls that symbol `Device:C_Polarized` (same pins, 1 = +), which the
  schematic uses.
- Schematic label nets are named `/NAME` by KiCad (sheet prefix); the board uses the same names so "Update PCB from
  Schematic" is a no-op. `compare_netlist.py` strips the `/`.

## Before ordering (for a human)

1. **Check the CF-to-IDE adapter against J1**: which way the adapter plugs on (pin 1 is the square pad, top left,
   marked "1" on the silk; the shroud key faces the ICs), how far its body overhangs the board and whether it clears
   R1-R4, RN1, JP1 and the LEDs, and whether it needs the card-edge side free.
2. **Check the adapter's power input**: J2 is a plain 1x4 0.1" header, pin 1 = +5 V, 2 and 3 = GND, 4 = not
   connected; confirm the cable/connector Ken's adapter takes (floppy Berg vs. 0.1") and the pin order. Fit JP1 only
   if the adapter takes +5 V on IDE pin 20 (many do not, and pin 20 is the key position on keyed cables).
3. LED colours and the 1k series resistors (~2.5 mA) to taste.
4. Optional hand tidying: placement is functional, not beautiful (IC row at the connector, pull-ups beside J1, LEDs
   bottom right); the router's track layout can be cleaned up in pcbnew. Re-run DRC and `compare_netlist.py` after
   any hand edit, and stop using `gen_cf.py` once you do.
5. Check the X1 footprint's position against a real blank V3.2 card / backplane (it is copied from the blank card
   conversion, which was not fabricated).
