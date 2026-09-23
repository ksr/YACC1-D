# Mem Switch card V1.1 — theory of operation

A 16-byte "ROM" made of toggle switches, at $0000-$000F: the first program the CPU ever ran was entered on it.
Bring-up card, not part of the running machine.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/mem-switch/eagle/v1.1/Mem Switch V1.1.sch` and `.brd` (parts and nets parsed from the Eagle
XML), `hardware/cards/mem-switch/eagle/v1.1/Notes.md`, `hardware/cards/mem-switch/README.md`,
`hardware/DESIGN-REVIEW-NOTES-datapath.md` (B1, B2, M4 and "checked, no issue (bring-up cards)"),
`tests/assembler/ledcount/README.md`, `docs/system/MACHINE.md`, `hardware/FABRICATED.md`, `BACKLOG.md`.

## 1. Purpose and place in the machine

Before the memory card worked there was no way to give the CPU an instruction stream. This card answers reads of
sixteen consecutive addresses with sixteen bytes set on DIP switches — a program small enough to toggle in by hand
(`tests/assembler/ledcount` is ten bytes: count on the I/O card's LEDs). Together with the Mem Register card (sixteen
bytes of RAM at $0010) it let the sequencer, the ALU and one register card be proven with a function-generator
clock (MACHINE.md 2026-09-21: "the CPU executes the 16-byte switch-ROM program as expected").

Decoding is done on the card: a 74LS85 compares ADDR4..7 with a 4-position DIP switch, a 4078 NOR requires
ADDR8..15 = 0, and two 74LS138s turn ADDR0..3 into one of sixteen byte selects. Each selected byte is a 74LS244
driving the eight switch levels onto DATA0..7.

```
   ADDR8..15 --> V1 4078 NOR --W--> IC4 74LS85 A=B_in
   ADDR4..7  --> IC4 A0..3   vs   B0..3 <-- SW1 (DIP-4, RN1 pull-downs) --> A=B_out = BRD-SEL (N$6)
   -VMA, -BUS-EN, -MEM-RD --> IC1/A 74ALS27 NOR --> IC1/C --> G2A of IC2, IC3
   ADDR3 --> IC2 G2B;  /ADDR3 (IC1/B) --> IC3 G2B;  ADDR0..2 --> A,B,C
   IC2 Y0..7 = SW0..7 ($0000..$0007), IC3 Y0..7 = SW8..15 ($0008..$000F)
   SWn --> enables IC(5+n) 74LS244 (both halves) --> DATA0..7;  RDn LED lights while SWn is low
   DIP-8 "0000".."1111": pins 1..8 to the 244 inputs (pull-ups RN2..RN17), pins 9..16 to GND: switch ON = 0
```

## 2. Bus signals used

| Signal | Bus pin | Dir | Use |
|---|---|---|---|
| ADDR0..2 | A3..A5 | in | IC2/IC3 A, B, C |
| ADDR3 | A6 | in | IC2 G2B directly; IC1/B (three inputs tied) inverts it for IC3 G2B |
| ADDR4..7 | A7..A10 | in | IC4 A0..A3 |
| ADDR8..15 | A11..A18 | in | V1 (74*4078 8-input NOR) A..H |
| DATA0..7 | A19..A26 | out | the sixteen 74LS244s (one enabled at a time) |
| -VMA | C12 | in | IC1/A I0 |
| -BUS-EN | C28 | in | IC1/A I1 |
| -MEM-RD | B23 | in | IC1/A I2 |
| VCC / GND | power pins | — | C1-C21 decoupling, PWR LED with R17 |

C3-C6 carry Blank V3.1's stale names (`-ADDR-REG-RD0` ...); connector only. No write strobe, no reset input.

## 3. Schematic walkthrough

Chips from the board file: IC1 74ALS27N, IC2/IC3 74LS138N, IC4 74LS85N, IC5-IC20 74LS244N, V1 744078N. Resistor
networks: RN1 SIL5 (common pin 1 on **GND**), RN2-RN17 SIL9 (common on VCC); values empty.

- **Page and block match.** V1's output W is high only when ADDR8..15 are all zero (page 0). IC4 compares A = ADDR4..7
  with B = SW1's four bits and takes W as its A=B cascade input (A<B and A>B inputs grounded), so N$6 = A=B_out is high
  when the address is in page 0 and its bits 7..4 equal the switch code. SW1's common pins 1-4 are on VCC and RN1
  pulls B0..B3 to GND: a closed switch makes that bit 1. For $0000-$000F all four are open. (The datapath review's
  description "RN1 pull-ups" differs from the schematic, where RN1 pin 1 is on the GND net.) N$6 also goes to the
  single-pin header **BRD-SEL** — a test point for the match, not a jumper.
- **Read qualification.** IC1/A (74ALS27 3-input NOR) takes -VMA, -BUS-EN and -MEM-RD: N$19 is high only while all
  three are asserted. IC1/C (inputs tied) inverts it into N$82, the active-low G2A of both decoders. G1 of both is
  N$6. IC2's G2B is ADDR3 (so it decodes $x0-$x7), IC3's is /ADDR3 from IC1/B ($x8-$xF). Exactly one of SW0..SW15 is
  low during a qualified read of a matching address; none otherwise.
- **The bytes.** SWn enables both halves of one 74LS244 (IC5 for byte 0 ... IC20 for byte 15) whose inputs come from
  the DIP switch named by the byte's binary address (`0000` ... `1111`): switch pin 1 to the input that drives DATA0
  (`IC5/B.A4` to `Y4` = DATA0), pin 8 to DATA7; pins 9-16 to GND; RN2..RN17 pull the inputs up. A switch **ON is a 0
  bit**, OFF is 1. The `ledcount` README's table ("Switches 7..0", bit 7 first) is written for this card.
- **LEDs.** RD0..RD15 (cathode on SWn, anode through R1..R16 to VCC) light while a byte is selected — "Add leds per
  address byte" from the 1.0 notes, done in 1.1.

The 1.1 notes say "Change to 74240 (inverted output)", and the README repeats it, but the schematic and board fit
74LS244N (finding B2): if 74LS240s were ever fitted every bit would read inverted. **To verify:** the marking on
IC5-IC20; document whichever is true.

## 4. Timing and findings

The card is combinational: data appears one 74ALS27 + 74LS138 + 74LS244 delay after the last of -VMA/-BUS-EN/-MEM-RD
falls (the comparator path from the address settles earlier, during the sequencer's address set-up step). The
review: "Exactly one of SW0-15 / RD0-15 low per read; each enables one 74LS244 onto DATA0-7. DATA8-15 are not
driven" — fine, because the sequencer's instruction register takes DATA0..7 only.

| ID | Severity | Finding | Status 2026-09-23 |
|---|---|---|---|
| B1 / M4 | MED (configuration) | overlaps the memory card's low RAM, which cannot be jumpered out; after reset the memory card's FORCE-ROM also answers $0000 — two or three drivers on DATA0..7 | Open by design: **do not fit this card and the memory card together** unless the memory card is out of the slot or its -VMA gating is respected. MACHINE.md: removed once the memory card worked, re-fitted 2026-09-21 for CPU bring-up |
| B2 | LOW | 74240 vs 74244 documentation | **To verify** (section 3) |
| review | — | read qualification and decode checked, no issue | — |

## 5. Jumpers, switches, LEDs

| Item | Meaning | Setting |
|---|---|---|
| SW1 (DIP-4) | the 16-byte block within page 0: ADDR7..4 | all open for $0000 (the address every test assumes) |
| DIP-8 `0000`..`1111` | the sixteen program bytes, ON = 0 | the program (`tests/assembler/ledcount/README.md` gives the switch rows for the LED counter) |
| BRD-SEL (1-pin) | test point: high while the card's block is addressed | — |
| RD0..RD15 | byte-selected indicators | — |
| PWR | power | — |

Which end of a DIP block is bit 7 on the silkscreen ("Rotate switches (on up)" was a 1.1 change) is not in the
tree. **To verify:** the physical orientation before entering a program.

## 6. Bring-up and test

- The card's own proof is the CPU running `tests/assembler/ledcount` from it (MACHINE.md 2026-09-21, function-
  generator TTL clock in the logic card's oscillator socket): the I/O card's LEDs count 00, 01, 02 ... at one count
  per four instructions.
- With the bus tester: `-BUS-EN:1#`, `-VMA:1#`, `ADDRBUS-WR-MODE`, `DATABUS-RD-MODE`, then `DUMP:0000-000F#` should
  print the switch settings; the RD LED of the addressed byte lights while `-MEM-RD` is held.
- If a byte reads wrong: the RD LED tells whether the decode is right (if it lights, the fault is in that byte's
  244 or switch/pull-up; if not, SW1, V1, IC4 or the strobe NOR). All bits inverted: B2. Two bytes light at once:
  IC2/IC3 enables.

## 7. Revision history and next

| Rev | Date | Status | Notes (`Notes.md`, `hardware/FABRICATED.md`) |
|---|---|---|---|
| V1.0 | 2021-06-23 | built, worked ("Version 1.0 works"), superseded | no buffers, no bypass caps |
| V1.1 | 2021-07-19 | **built**, off the bus except for bring-up sessions | +60 parts: 74244 buffers, BRD-SEL, bypass caps, switch orientation, per-byte LEDs, the SW1 16-byte block select. Drawn on Blank V3.1 |

Ideas left in the notes: "Add additional address selection to locate with 16 byte blocks" (done as SW1) and the
74240 question. The card has no future in the running machine; its remaining job is CPU bring-up whenever the
memory card is out, and `docs/isa/MICROCODE-REVIEW-NOTES.md` section 7 lists the bench confirmations (H-2 `BRZ`
from the switch ROM, H-4 "put $80 in the switch ROM") that still want it.
