# Protocard V1.0 — theory of operation

A bus card with nothing on it but the connector, a power LED and every bus pin brought out to 0.1-inch header
rows: the place to breadboard the next circuit against the live backplane.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/protocard/eagle/v1.0/ProtoCard-Prod-V1.0.sch` (parts and nets parsed from the Eagle XML),
`hardware/cards/protocard/README.md`, `hardware/FABRICATED.md`, `docs/system/connector/README.md`,
`hardware/bus/bus-template/eagle/v3.2/Bus Template V3.2.sch`, `hardware/DESIGN-REVIEW.md`,
`docs/procedures/System Build Notes.md`.

## 1. Purpose and place in the machine

Nine parts: X1 (the 96-pin DIN 41612, `FABC96R`), PWR LED with R1 330 Ω, and six single-row headers — SV1, SV2, SV3
(`MA20-1`, 20 pins each) and SV4, SV5, SV6 (`MA12-1`, 12 pins each). Each header pin is one connector pin, and the
first two pins of SV1-SV3 (and the last two of SV4-SV6) are GND and VCC so a prototype can be powered from the row it
plugs into. 178 x 114 mm, two layers, designed 2016-07-14 for the gen-1 bus; the connector, the outline and the
power pins are unchanged in the 2020 machine, so the board still fits (README). The build order in
`docs/procedures/System Build Notes.md` lists it as "4) Optional Prototype card".

```
   X1 DIN 41612 ---- 84 signal pins ----> SV1..SV3 (20-pin rows), SV4..SV6 (12-pin rows)
                     6 x GND, 6 x VCC ---> pins 1/2 of SV1..3, pins 12/11 of SV4..6, PWR LED
```

## 2. Bus signals

All of them, passively. **The schematic's net names are the 2016 gen-1 names** (INT-ACK on A3, ADDR0..15 on
A4..A19, DATA0 on A20, ALU-FUNC on B27, BR-REG-LD-LO on C3, SP/PC-* on C15..C22, I/O-RD on C12 ...), which is a
different assignment from the Bus V3.2 the machine is built to (ADDR0 on A3, DATA0 on A19, -VMA on C12 ...). The
copper does not care — every pin is a wire to a header — but a prototype must be wired from the **V3.2 table**
(`docs/cards/backplane.md` section 2, `docs/system/connector/YACC1 Connector - V3.2.pdf`), not from this
schematic's labels. **To verify:** whether the silkscreen beside the headers prints the 2016 names; if it does, tape
a V3.2 legend over it.

Header-to-pin mapping (from the schematic; the useful part is the row order, which is by connector pin number):

| Header | Connector pins | Power pins |
|---|---|---|
| SV1 | A3..A20 (pins 3..20) | 1 = GND, 2 = VCC |
| SV4 | A21..A30 (pins 1..10) | 11 = VCC, 12 = GND |
| SV2 | B3..B20 | 1 = GND, 2 = VCC |
| SV5 | B21..B30 | 11 = VCC, 12 = GND |
| SV3 | C3..C20 | 1 = GND, 2 = VCC |
| SV6 | C21..C30 | 11 = VCC, 12 = GND |

So SV1 pin n (n = 3..20) is connector pin A n, SV4 pin n (1..10) is A (n+20), and likewise for rows B and C.

## 3. Findings, settings, tests

The design review's mechanical pass: "9 parts, 87 nets, 0 ICs, 86 bus-connector nets ... no findings". Nothing to
set. There is no test beyond the connector check every card gets (`Build Notes`: the three far-left and three far-
right pins of each row are GND, the next three in are VCC; VCC not shorted to GND).

Anything built on it inherits the bus conventions: control lines are 74LS374 outputs on the sequencer with -BUS-EN
as their enable and no pull-ups anywhere (`hardware/DESIGN-REVIEW-NOTES-control-io.md` 5.1), the data bus is 16
bits with pull-downs on the memory card (value unknown) and pull-ups on the bus tester, and a memory-mapped device
must qualify its select with -VMA (`docs/cards/memory.md`, `docs/cards/video.md`).

## 4. Revision history

| Rev | Date | Status | Notes |
|---|---|---|---|
| V1.0 | 2016-07-14 | **built** (gerbers in `fab/`, sent to the board house in 2016), the only version | a gen-1 "ProtoCard-V1.1" working folder has a byte-identical schematic (README) |

The next circuit that could use a prototype stage is the CompactFlash interface (`docs/cards/cf.md`: 74LS138 decode
of P8/P9, 74LS32 strobe gating, 74LS175 latch, 74LS08, 74LS245; planned 2026-09-24 onto the memory card) — small
enough to build here before the KiCad board is ordered. For a new
*card* design, start from Blank V3.2 (`hardware/bus/blank-card/eagle/v3.2`), which carries the current names.
