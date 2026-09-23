# Address and TMP register card (V1.0) — RETIRED 2021

A short history page: this card was the first 2020 way of putting a 16-bit address on the bus and of holding two
temporary 16-bit values. It was fabricated in June 2020, used during early bring-up, superseded within months by the
Index Registers card (address) and the memory card (TMP), and retired in January 2021. No active revision exists.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/address-tmp/eagle/deprecated/v1.0/Address and TMP V1.0.sch` (parsed with Python's `xml.etree`),
`hardware/cards/address-tmp/README.md`, `hardware/FABRICATED.md`, `hardware/PROVENANCE.md`,
`hardware/NEWER-DESIGNS-vs-ACTIVE.txt`, `docs/system/connector/README.md`, `docs/history/general-notes/NOTES-Update from old project.md`,
`docs/history/NOTES Jan 2-17 orig.md`, `tests/bus-tester-scripts/deprecated/address-register-2020-07/address registers.txt`,
`tests/bus-tester-scripts/README.md`, `hardware/cards/memory/` (v1.3 TMP registers, via `hardware/DESIGN-REVIEW-NOTES-datapath.md` M3).

---

## 1. What it was

Nine ICs on a Bus V3 (June 2020) card:

| IC | Part | Function |
|---|---|---|
| IC1, IC2 | 74*373 x 2 | address register 0: `D` = DATA0..15, `Q` = ADDR0..15, latch enable `N$1` = NOT `-ADDR-REG-LD0` (IC5A), output enable `-ADDR-REG-RD0` |
| IC3, IC4 | 74*373 x 2 | address register 1: same with `-ADDR-REG-LD1` (IC5B) / `-ADDR-REG-RD1` |
| IC6, IC7 | 74*373 x 2 | TMP0: `D` and `Q` both on DATA0..15, latch enable `N$3` = NOT `-TMP-REG-LD0` (IC5C), output enable `-TMP-REG-RD0` |
| IC8, IC9 | 74*373 x 2 | TMP1: `-TMP-REG-LD1` (IC5D) / `-TMP-REG-RD1` |
| IC5 | 74*04 | the four strobe inverters (E, F grounded) |
| RN1..RN4 | 8-resistor networks, common pin to **GND**, value blank | on ADDR0..15 and DATA0..15 — pull-downs as drawn (the card README says "resistor-network pull-ups"; the schematic's common pin is GND; **To verify:** which was fitted, and the value) |
| PWR, R2 | LED, 330 | power LED |

Bus pins (X1): `-ADDR-REG-RD0` = C3, `-ADDR-REG-LD0` = C4, `-ADDR-REG-RD1` = C5, `-ADDR-REG-LD1` = C6 — the Bus V3.0/V3.1
names of those pins; C12 = `UNUSED0` (this is the pre-`-VMA` bus); the TMP strobes on B27..B30 as today.

A 74x373 is a **transparent** latch: with the enable high (strobe low) the outputs follow the inputs, and the value present
when the strobe rises is kept. So a load took effect at the trailing edge of `-ADDR-REG-LDn` / `-TMP-REG-LDn`, and an address
register read put the latched value onto ADDR0..15 for as long as `-ADDR-REG-RDn` was low. There was no counter: the
program counter had to be reloaded through the data bus for every step, which is the reason the card lost.

## 2. Why it was retired, and what replaced it

The 2020 design notes record the decision (`docs/history/general-notes/NOTES-Update from old project.md`):

- under "SP/PC ... YACC2020 updates and carry forward: **This board is no longer used**";
- under "Design Changes": "1) Remove address latch register from register file, recover bus pins & mem control pins,
  update 1.2 bus definition"; "2) add temp 8 bit latch to sequencer card to facilitate mem to mem transfer";
  "3) convert reg card to 8 registers, modify bus definition to 3 bits register select, 1 bit board select";
- under "TBD RESEARCH": "Should tmp register be on sequencer card or not exist at all — this would free up two bus lines
  although the bottleneck is still the number of control signals in sequencer connector".

What happened:

1. **The addresses went to the Index Registers card** (`docs/cards/register.md`, fabricated 2020-08-31): eight 16-bit
   *counters* selected by a 4-bit register number `ADDR-REG-ID0..3` on the same pins C3–C6. The four dedicated strobes of
   this card became the four bits of that number — Bus V3.2 (2020-09-10, `docs/system/connector/README.md`). A counter as PC
   or SP removes the reload-per-step cost; `-VMA` (added on C12 in Bus V3.1) qualifies the address drive.
2. **The TMP registers went to the memory card** (v1.2, 2020-11; v1.3 in the machine): TMP0 = IC26/IC27, TMP1 = IC28/IC29,
   74LS374 edge-triggered registers on the same `-TMP-REG-RD0/1` / `-TMP-REG-LD0/1` strobes — but latching on the **leading**
   edge of the load strobe instead of the trailing edge of this card's transparent latches (`DESIGN-REVIEW-NOTES-datapath.md` M3:
   "TMP registers latch on the leading edge of -TMP-REG-LDn; correct only under a microcode ordering rule"). The microcode
   generator's "source one line before the strobe" convention dates from this change.
3. The card was moved to "Old & obsolete – do not use" in the Production folder in January 2021 (`hardware/FABRICATED.md`).

The generator still carries dead code from the transition under `#ifdef NOTYET` (`firmware/microcode/ucode-generator2/main.c`
lines 287–355): `ADDR-REG-FUNC-RD` ("sp/pc sel on old card"), `ADDR-REG-ADDR-RD`, `ADDR-REG-UP`, `ADDR-REG-LD-LO/HI` ("FIX on
new card"). Those names describe a *counting* SP/PC board (the gen-1 "SP/PC" card of `docs/history/NOTES Jan 2-17 orig.md`),
not the latch card documented here; none of them is in `yaccsignaldata2.h`, so the block cannot be compiled in.

## 3. Why it still matters

- **The Blank V3.1 template** (`hardware/bus/blank-card/eagle/v3.1`) and the cards drawn on it (IO 1.1, Mem Switch, Mem
  Register) still label C3–C6 `-ADDR-REG-RD0/LD0/RD1/LD1`. Harmless — those cards do not use the pins — and documented in
  `docs/system/MACHINE.md` (known fault 4) and `BACKLOG.md` (Blank V3.2 has the V3.2 names). Anyone reading an old schematic
  of the machine will meet these names; they mean this card.
- **The test script** `tests/bus-tester-scripts/deprecated/address-register-2020-07/address registers.txt` documents its
  use: write $1234 with `-TMP-REG-LD0`, $5678 with `-TMP-REG-LD1`, $1010 with `-ADDR-REG-LD0`, $0101 with `-ADDR-REG-LD1`;
  read the TMPs back on the data bus and the address registers on the address bus (`RD-ADDRBUS:0#1010!`). The TMP half of
  that script is still a valid test of the memory card's TMP registers (same strobes, same bus), the address half is not.
- **The mechanical design review** does not list this card (only active revisions are converted to KiCad); the Eagle
  schematic PDF is in `eagle/deprecated/v1.0/pdf/` (`hardware/SCHEMATICS.md`).

## 4. Revision record

| Revision | Date (PROVENANCE) | Status | Notes |
|---|---|---|---|
| V1.0 | 2020-06-20 (sch and brd) | fabricated (CAM output in `eagle/deprecated/v1.0/fab/`), retired 2021-01 | a "Working" copy differing only by a stray "test text" element was dropped 2026-09-20 (`NEWER-DESIGNS-vs-ACTIVE.txt`: 0 differences) |

Not in the machine (`docs/system/MACHINE.md`). Nothing to revise: the functions live on the Index Registers and memory cards.

Related documents: `docs/cards/register.md`, `docs/cards/memory.md` (TMP registers), `docs/system/BUS.md` (the V3.0 -> V3.2
signal history, when written).
