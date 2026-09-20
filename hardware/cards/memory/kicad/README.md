# YACC1 Memory Card v1.3 — KiCad conversion

Converted 2026-09-19 from the Eagle 9.7 design in
`YACCS/YACC gitversion/YACC1-2020/PCB/Working - Under Develolpment/Memory v1.3/`
(the newest copy of the card anywhere in the YACCS tree). **No Eagle file was modified.**
Byte-identical copies of the sources are in `eagle-source/`.

This is the pilot for moving the whole YACC1 design set off Eagle. It is the v1.3 card that
is in the machine today: 2 x 62256 RAM, 1 x 28C64 EEPROM, boot remap of ROM to $0000 until
the first A15 access, and the 3x8 jumper header that maps each 4K block of the upper half
to hi RAM, ROM, or nothing (the $D000 block is left undecoded for the video card).

## Files

| File | What it is |
|---|---|
| `memory-card-v1.3.kicad_pro` | project; OSH Park 4-layer rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |
| `memory-card-v1.3.kicad_sch` | root sheet; six sub-sheets `memory-card-v1.3-sheet1..6.kicad_sch` mirror the six Eagle sheets |
| `memory-card-v1.3.kicad_pcb` | the board, imported with `kicad-cli pcb import`, then finished (see below) |
| `memory-card-v1.3-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used |
| `memory-card-v1.3-eagle.pretty/` | project footprint library extracted from the imported board |
| `sym-lib-table`, `fp-lib-table` | point KiCad at the two project libraries |
| `eagle-source/` | the original `.sch`, `.brd`, `.pro`, `Notes.rtf`, `ROM ZSelect.circ` |
| `reports/` | ERC, DRC, netlist, netlist comparison, schematic PDF, board renders |
| `tools/` | the converter and checkers (re-runnable, deterministic) |

## How it was converted

1. **Board**: `kicad-cli pcb import --format eagle` on the `.brd`. It preserved the 4-layer stack
   (tracks on F.Cu/B.Cu, GND and VCC planes on In1.Cu/In2.Cu), 52 footprints, 968 tracks, 80 vias.
2. **Schematic**: KiCad's Eagle schematic importer is GUI-only, so `tools/eagle_sch_to_kicad.py`
   converts the Eagle XML directly: symbols become a project library (units = Eagle gates),
   unplaced 74xx power gates become hidden power pins as in Eagle, supply symbols become KiCad
   power symbols, every net segment carries a global label with the Eagle net name (Eagle nets are
   global across sheets), buses are drawn as cosmetic lines, unused gate pins get no-connect flags.
3. **Board finishing**: `tools/finish_board.py` (run with KiCad's bundled Python) extracts the
   footprints into `.pretty`, moves a stray dimension line that the bus-connector package had put
   on Edge.Cuts, applies the OSH Park rules, links every footprint to its schematic symbol, and
   refills the two power planes.

## Proof of correctness

`tools/compare_netlists.py` reduces both the KiCad schematic netlist and the pad netlist embedded
in the imported board (i.e. Eagle's own connectivity) to partitions of (reference, pad) and requires
them to be identical. Result: **115 of 115 multi-pin nets identical, no pad differs**
(`reports/netlist-compare.txt`). Two nets that Eagle had left auto-named (N$1, N$14) simply carry
KiCad auto-names.

Re-run any time:

```
python3 tools/eagle_sch_to_kicad.py "eagle-source/Memory V1.3.sch" . memory-card-v1.3
kicad-cli sch export netlist --format kicadsexpr -o reports/netlist.net memory-card-v1.3.kicad_sch
python3 tools/compare_netlists.py reports/netlist.net memory-card-v1.3.kicad_pcb
```

## What the reports still show, and why

- **ERC**: 43 *isolated pin label* warnings (a label sitting directly on a pin, Eagle style),
  hidden-power-pin notes on IC5 and IC14, and *missing unit* / *unused input* on IC14's spare
  gates. All are cosmetic; the netlist proves the connections.
- **DRC**: ~200 *silk over copper* warnings (Eagle silkscreen conventions), and 100 "unconnected"
  items that all belong to IC26–IC29, RN5, RN6, C9 and their nets. Those are the two 16-bit
  temporary registers: they are **unplaced in the Eagle v1.3 layout as well** (parked off the board
  edge with airwires), so KiCad is reporting the same incompleteness Eagle had.
- `PWR` (the power LED) became `PWR0`: KiCad references must end in a digit, and this matches what
  KiCad's own Eagle board importer chose.

## Known design facts verified on hardware (2026-09-18)

Block-select jumpers: up = hi RAM, down = ROM, none = undecoded. Current card: $8000–$CFFF RAM,
$D000 undecoded (reserved for the video card), $E000–$FFFF ROM (the 28C64 is 8K). The EEPROM
holds the Software-vs July-2021 build of monitor + BASIC (git commit ff7d85a).


---
*YACC1-D note (2026-09-20): the `tools/` folder this README mentions is not kept here; the maintained converter, netlist prover and board finisher are in `tools/kicad/` at the repo root (newer than the pilot copies).*
