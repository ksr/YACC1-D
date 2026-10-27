# Build rules for YACC1 boards

<!-- Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026 -->

The rules the YACC1 cards follow, gathered in one place from the documents and board files that state them, with
every known exception. Nothing here is new: each rule names its source, and where two files disagree both are
listed at the end. When a rule changes, change its source and this page together.

## Scope

- **Rules for new boards** (section 1) are for future work only. They do not apply to any card already built or
  ordered: everything in [`docs/system/MACHINE.md`](../docs/system/MACHINE.md), and the memory card v2.0 (ordered
  2026-10-09). The video card V2.0 (not ordered) follows them, as silk changes only, with J4 left where it is.
- **Always ask Ken before changing a card that might be built, ordered or in production**, for any change at all.
- The other sections describe how the existing cards were built.

Source: [`CLAUDE.md`](../CLAUDE.md) (board-layout rules, 2026-10-24).

## 1. Rules for new boards (2026-10-24, all of Ken's systems)

- Switches, buttons, LEDs and the connectors for outside cables (video, D-subs, USB, network) go on the **front
  edge**, the edge farthest from the bus connector.
- Cable connectors point outwards: a right-angle part with its mating face at the board edge, so a cable plugs
  straight in.
- Jumper blocks and cable headers (ribbons, probes, ICSP) go near a board edge, never in the middle of the board.
- A plug-in module (Pico, Tang Nano, ...) goes at an edge other than the bus connector's, where possible, with its
  USB port facing that edge.
- Every reference (U12, R3, ...) stays readable with the parts fitted: printed outside the part, never under a chip,
  socket or module. ICs get their type (74LS374, ...) printed beside it.
- Every switch, button and LED is labelled with its function (RESET, STEP, RUN, ...), and each switch position with
  what it selects.
- Placement drawings (PDF) show the outline and the parts in one orientation, on a sheet shaped like the board.
- `cottageworker.com` on the silkscreen, beside the board's name and revision (2026-10-26). It replaces the old
  `onepagecomputer.com`, which stays on the boards already built or ordered and on the never-ordered designs (blank
  card V3.2, CF v1.0, bus tester V3.1) until one of them is next revised.

Silk sizes used on the video card V2.0, the first board drawn to these rules: text 1.0 mm high, 0.15 mm strokes,
card name 1.5 mm; 0.15 mm from other silk, 0.2 mm from pads, 0.4 mm from the board edge
([video V2.0 README](cards/video/kicad/v2.0/README.md)).

## 2. Size and mounting

| Rule | Source |
|---|---|
| Standard card 178 × 114 mm (177.78 mm in the board files) | [`BUS.md`](../docs/system/BUS.md), protocard and blank-card READMEs |
| Backplane V2.0: 304.8 mm square, 8 radial slots | `BUS.md` |
| The bus connector X1 sits in the same place on every card, with copper keep-outs round its two screws (4 mm on the CF card) | video V2.0 and CF v1.0 READMEs |

## 3. Bus and connector

| Rule | Source |
|---|---|
| 96-pin DIN 41612, rows a/b/c × 32: FABC96R on cards, FABC96S on the backplane; mounting holes ±44.46 mm on its centre line | `BUS.md`, [backplane README](bus/backplane/README.md) |
| GND on A1/A32/B1/B32/C1/C32, VCC on A2/A31/B2/B31/C2/C31 | `BUS.md` pinout, blank card V3.2 netlist |
| Signal names are Bus V3.2 (C3–C6 = ADDR-REG-ID0..3); start new cards from Blank V3.2 | [bus-template](bus/bus-template/README.md), [blank-card](bus/blank-card/README.md) READMEs |
| No pull-ups, terminators or series resistors on the backplane | `BUS.md` |

## 4. Layers and copper

| Rule | Source |
|---|---|
| 4-layer KiCad masters (memory v2.0, video v1.3 and V2.0): F.Cu signals, In1 solid GND, In2 solid VCC, B.Cu signals; GND and VCC never routed as tracks | memory v2.0 `gen_relayout.py`, video v1.3 and V2.0 READMEs |
| Signal tracks 0.25 mm, clearance 0.2 mm, vias 0.8/0.4 mm, copper 0.5 mm from the edge, antipads 0.3 mm, thermals 0.4 mm gap / 0.5 mm spokes | the same; the `.kicad_pro` files agree |
| Through-hole parts and through vias only | memory v2.0 JLCPCB order, video V2.0 README |
| Boards converted from Eagle are checked against OSH Park's rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular ring) | `tools/eagle_to_kicad_all.py` |

## 5. Power, decoupling, sockets and LEDs

| Rule | Source |
|---|---|
| Single 5 V rail, TTL / LS parts | [`BRING-UP.md`](../docs/procedures/BRING-UP.md) |
| One 100 nF per IC, beside its VCC pin | `BUS.md`, memory v2.0 and video V2.0 design reviews |
| Every IC in a socket. The socket check leaves room for the widest stamped sockets: pin rows +1.3 mm at the sides, end pins +1.9 mm at the ends; KiCad's courtyards (about 1 mm) are not enough | memory v2.0 and video V2.0 r2 design reviews, video V2.0 README |
| The EEPROM in its own machined socket | memory v1.2 Build Notes |
| Every card has a PWR LED | `BRING-UP.md` |
| Backplane: an electrolytic per slot, bulk C7/C8, a PWR LED through 330 Ω | `BUS.md` |

## 6. Folders, versions and checks

| Rule | Source |
|---|---|
| `hardware/cards/<card>/{eagle,kicad}/<version>/`; deprecated versions under `deprecated/`, never edited | `CLAUDE.md` |
| KiCad is current; Eagle is kept but deprecated | [`hardware/README.md`](README.md) |
| A `MASTER` file marks a hand-maintained KiCad design: the converter never writes there | [`KICAD.md`](KICAD.md) |
| A `FABRICATED` file marks a fabricated or in-machine version | [`FABRICATED.md`](FABRICATED.md) |
| A generated card's `build.sh` passes only with DRC 0 errors and 0 unconnected, schematic parity 0, ERC clean and the netlist proof; routing with Freerouting 1.9, KiCad 10 | CF v1.0 README, `CLAUDE.md` |
| JLCPCB orders: FR-4, 4 layers, 1.6 mm, 1 oz outer / 0.5 oz inner, green mask, white silk, leaded HASL, plugged vias; separate PTH and NPTH drill files | memory v2.0 order and README, video V2.0 README |

Seen on every board but not written down as a rule: the silk title reads `YACC1 <CARD> V<x.y>`; the Eagle boards use
an OSH Park design-rule set. Every board before the video card V2.0 carries `onepagecomputer.com` (section 1: new
boards carry `cottageworker.com`).

## 7. Exceptions

| Board | How it differs | Source |
|---|---|---|
| Sequencer-logic V2.1l | 218 × 114 mm (lengthened) | `FABRICATED.md` |
| Video V2.0 | 218.42 × 113.97 mm; J4 (FTDI header) 24 mm in from the front edge; C18, C22 and C49 13–48 mm from their VCC pins; HCT parts on the bus | video V2.0 README and design reviews |
| Sequencer-memory | 114 × 152 mm, no bus connector | `BUS.md` |
| Bus tester v3.1 | 114 × 178 mm, never built | `BUS.md` |
| Bus jumpers (horizontal v3.0 / v3.2, vertical) | 231 × 70, 231 × 115 and 76 × 114 mm; obsolete, not fitted | `FABRICATED.md` |
| CF v1.0 | 2-layer: 0.3 mm signal / 0.6 mm power tracks, GND pours | CF v1.0 README |
| I/O v1.1, mem-switch, mem-register, video v1.0–1.2, bus tester v1.1, protocard | 2-layer | their KiCad READMEs |
| Memory v2.0 | Two 3.2 mm standoff holes with 7 mm keep-outs; silk 0.5 mm from the edge; the PWR0 reference on F.Fab, not the silk | memory v2.0 README |
| Blank V3.1 and the cards drawn on it (video v1.0, mem-switch, mem-register) | Old C3–C6 signal names | blank-card README |
| Video v1.0 / v1.1 | Two unjoined 5 V nets (VCC and +5V), fixed with a wire | [video README](cards/video/README.md) |
| EEPROM adaptor | No power pins, no decoupling, no PWR LED | `hardware/cards/sequencer-memory/reviews/eeprom-adaptor-mechanical-2026-09-21.md` |
| Mem-switch v1.0 | Bypass caps missing (fixed in v1.1) | mem-switch v1.1 Notes |
| ALU v3.0 | 2-layer with no VCC or GND planes, scrapped | ALU v3.0 Notes |
| ALU v3.1 | Buried vias, removed in the resubmit | ALU v3.1 resubmit Notes |
| Silk versions | Blank V3.1 reads "Blank V1.0"; the original-size sequencer-logic boards read V2.0; register v1.1 has no title | the `.brd` files |

## 8. Where the files disagree (to sort out)

1. **Memory v2.0 order status:** `KICAD.md` and `cards/memory/README.md` say not ordered; `FABRICATED.md`, the
   memory v2.0 README and `CLAUDE.md` say ordered 2026-10-09.
2. **Fab output folder:** `FABRICATED.md` names `hardware/fab/<card>/<rev>/`, which does not exist; the files are in
   `eagle/<rev>/fab/`.
3. **Power pins:** `BUS.md` says "three outermost pins of each row are GND, next three VCC"; the pinout and the
   netlist have one GND and one VCC at each end of each row (12 pins in all).
4. **Signal count:** `BUS.md` says 84 signals in one place and 86 signal pins in another; the mechanical pass (`hardware/reviews/mechanical-2026-09-21.md`) counts 86.
5. **Card height:** the READMEs say 114 mm; the Eagle outline spans 164 mm (flagged "To verify" in `BUS.md`).
6. **The record:** `hardware/README.md` says KiCad is current; `KICAD.md` says the Eagle files remain the record of
   what was built.
7. **Fab house:** `FABRICATED.md` presumes OSH Park for boards with no fab output; memory v1.3 / v2.0 and register
   v1.0 went to JLCPCB.
