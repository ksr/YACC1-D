# Mem Register card V1.0 — theory of operation

Sixteen bytes of RAM built from 74LS374 latches, at $0010-$001F: the scratch memory and stack that let the CPU run
programs from the Mem Switch card before the memory card existed. Bring-up card, not part of the running machine.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/mem-register/eagle/v1.0/Mem Register V1.0.sch` and `.brd` (parts and nets parsed from the
Eagle XML), `hardware/cards/mem-register/README.md`, `hardware/DESIGN-REVIEW-NOTES-datapath.md` (B1, M4, "checked,
no issue (bring-up cards)"), `docs/isa/MICROCODE-REVIEW-NOTES.md` (H-1 confirmation, 1.6),
`firmware/microcode/ucode-generator2/main.c` (write ordering, per the review), `docs/system/MACHINE.md`,
`hardware/FABRICATED.md`.

## 1. Purpose and place in the machine

The same decoder as the Mem Switch card (page-0 NOR, 74LS85 block compare on ADDR4..7, two 74LS138s on ADDR0..3),
duplicated once for reads and once for writes, selects one of sixteen 74LS374 bus registers. A register's D and Q
pins share the data lines: a write clocks the bus into it, a read enables its outputs. Sixteen bytes is enough for
a few variables and a short stack (the microcode review's H-1 bench check: "SP = $001F (Mem Register RAM) ...
`PUSHR R3`; read back $001F/$001E").

```
   ADDR8..15 --> V1 4078 --> IC4 74LS85 (A = ADDR4..7, B = SW1) --> N$6 = block match (BRD-SEL test point)
   read:  -VMA,-BUS-EN,-MEM-RD --> IC1/A NOR --> IC1/C --> G2A of IC2 (ADDR3=0) / IC3 (ADDR3=1) --> RD0..15 --> 374 -OC
   write: -VMA,-BUS-EN,-MEM-WR --> IC7/A NOR --> IC7/C --> G2A of IC5 (ADDR3=0) / IC6 (ADDR3=1) --> WR0..15 --> 374 CLK
   IC8..IC23 74LS374: D and Q on DATA0..7;  RD1..16 and WR1..16 LEDs show the selected byte
```

## 2. Bus signals used

| Signal | Bus pin | Dir | Use |
|---|---|---|---|
| ADDR0..2 | A3..A5 | in | A, B, C of all four decoders IC2, IC3, IC5, IC6 |
| ADDR3 | A6 | in | G2B of IC2 and IC5; inverted by IC1/B for IC3, by IC7/B for IC6 |
| ADDR4..7 | A7..A10 | in | IC4 A0..A3 |
| ADDR8..15 | A11..A18 | in | V1 NOR |
| DATA0..7 | A19..A26 | bidir | the sixteen 374s |
| -VMA, -BUS-EN | C12, C28 | in | both NORs (IC1/A, IC7/A) |
| -MEM-RD | B23 | in | IC1/A |
| -MEM-WR | B24 | in | IC7/A |
| VCC / GND | power pins | — | C1-C24 decoupling, PWR LED with R1 |

No reset input (the latches power up random). C3-C6 carry Blank V3.1's stale names; unused.

## 3. Schematic walkthrough

Chips from the board file: IC1, IC7 74ALS27N; IC2, IC3, IC5, IC6 74LS138N; IC4 74LS85N; IC8-IC23 74LS374N; V1
744078N. RN1 SIL5 (common on GND, the SW1 pull-downs), RN2-RN5 SIL9 (common on VCC, the LED series networks);
values empty.

- **Block match** as on the switch card: V1 W = (ADDR8..15 == 0) into IC4's A=B_in; A = ADDR4..7, B = SW1 (pins 5..8
  to B3..B0, common 1..4 on VCC, RN1 to GND: closed = 1); N$6 = match, also the BRD-SEL test pin and G1 of all four
  decoders. For $0010 SW1 = 0001: only the B0 switch closed. Two cards with the same SW1 code would collide; the
  Mem Switch card sits at 0000.
- **Read path.** IC1/A NORs -VMA, -BUS-EN, -MEM-RD; IC1/C inverts (N$82) into G2A of IC2 (G2B = ADDR3) and IC3 (G2B =
  /ADDR3 via IC1/B). Outputs RD0..RD15 are the -OC pins of IC8..IC23: the selected register drives DATA0..7 for as
  long as the strobe holds. DATA8..15 are not driven.
- **Write path.** IC7/A NORs -VMA, -BUS-EN, -MEM-WR; IC7/C inverts (N$4) into G2A of IC5 (ADDR3) and IC6 (/ADDR3 via
  IC7/B). Outputs WR0..WR15 are the CLK pins. A 74LS374 clocks on the rising edge: the decoder output falls when the
  write strobe starts and **rises when it ends**, so the register takes the bus value at the trailing edge of
  -MEM-WR — the same trailing-edge convention as the 62256 (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.6), and the
  generator holds the data source one step after -MEM-WR rises (`main.c:243-247`) so the value is still there.
- **LEDs.** RD1..RD16 and WR1..WR16 (numbered from 1 on the silkscreen, the nets from 0): cathode on RDn/WRn, anode
  through RN2/RN4 (reads) and RN3/RN5 (writes) to VCC — the byte being read or written lights.

## 4. Timing and findings

Reads: decode delay after the strobe, as on the switch card. Writes: the review checked that "the address is
stable a line before, so the decoder cannot produce a second rising edge on another WRn during the write" — a
decode glitch mid-strobe would clock a second register, which the microcode's ordering prevents.

| ID | Severity | Finding | Status 2026-09-23 |
|---|---|---|---|
| B1 / M4 | MED (configuration) | overlaps the memory card's undisableable low RAM at $0010-$001F (and FORCE-ROM after reset); a read then has two or three drivers on DATA0..7 | Open by design: not fitted together with the memory card. MACHINE.md: removed once the memory card worked; re-fitted 2026-09-21 for CPU bring-up |
| review | — | read and write qualification, decode, 374 edge, no reset inputs: checked, no issue | — |

## 5. Jumpers, switches, LEDs

| Item | Meaning | Setting |
|---|---|---|
| SW1 (DIP-4) | ADDR7..4 of the block | 0001 = $0010 (README, MACHINE.md) |
| BRD-SEL (1-pin) | test point: block match | — |
| RD1..RD16, WR1..WR16 | byte read / written | — |
| PWR | power | — |

## 6. Bring-up and test

- With the bus tester (the same idiom as the memory tests, `docs/cards/bus-tester.md` section 4): write sixteen
  distinct bytes to $0010-$001F, read them back after other traffic; each write should flash a WR LED and each read
  an RD LED. `DUMP:0010-001F#` in the Processing sender.
- With the CPU: the H-1 confirmation in `docs/isa/MICROCODE-REVIEW-NOTES.md` section 7 — stack at $001F, single-
  step `PUSHR R3`, read the two bytes back — is written for this card, and is still worth running against the
  reloaded microcode (2026-09-22) since the fix has only emulator evidence.
- Symptoms: a byte that reads as the last bus value is one whose 374 never enables (RD LED dark: IC2/IC3 or the read
  NOR; RD LED lit: the 374); a write that lands in two bytes at once is an address change during -MEM-WR.

## 7. Revision history and next

| Rev | Date | Status | Notes (`hardware/FABRICATED.md`) |
|---|---|---|---|
| V1.0 | 2021-07-19 (PCB/Production) | **built**, the only version | drawn on Blank V3.1; CAM output in `fab/` |

No next revision is planned; like the switch card it exists for CPU bring-up with the memory card out. If one were
made: a reset input to clear the latches (defined power-up contents), a jumper to disable the card while it shares
the bus with the memory card, and 16-bit width so a 16-bit read strobe pair sees defined data on DATA8..15.
