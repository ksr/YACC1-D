# Memory card v1.3 — theory of operation

64K of address space on one card: two 62256 SRAMs, one 28C64 EEPROM, the 4K-block map jumpers, the FORCE-ROM boot
remap, and the two 16-bit TMP registers that the microcode uses as scratch words.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/memory/eagle/v1.3/Memory V1.3.sch` and `.brd` (the built card; parts and nets parsed from
the Eagle XML), `hardware/cards/memory/eagle/v1.3/Notes.md`, `hardware/cards/memory/README.md`,
`hardware/cards/memory/eagle/deprecated/v1.1/Notes.md`, `.../v1.2/Notes.md`, `.../v1.2/Build Notes.md`,
`hardware/DESIGN-REVIEW-NOTES-datapath.md` (findings M1–M8, S1, S3), `hardware/DESIGN-REVIEW-NOTES-control-io.md`
(1.3, 5.1), `docs/isa/MICROCODE-REVIEW-NOTES.md` (1.3, 1.6, H-1/H-2 status), `firmware/microcode/yaccsignaldata2.h`,
`firmware/microcode/ucode-generator2/main.c` (the -VMA "hack"), `software/ucemu/y1ucemu.c` (the memory model),
`firmware/monitor/monitor.asm` (the reset entry), `docs/system/MACHINE.md`, `hardware/FABRICATED.md`,
`tests/memory/*.py` and their logs, `BACKLOG.md`.

## 1. Purpose and place in the machine

The memory card is the only card that answers a memory cycle. The sequencer puts an address on ADDR0-15 through the
index-register cards (the register selected by ADDR-REG-ID0..3 drives the address bus while -VMA is low), and this
card turns the address into one of three chip selects: low RAM (IC1, $0000-$7FFF, always), high RAM (IC2, any 4K
block of $8000-$FFFF jumpered "up") or the EEPROM (IC13, any 4K block jumpered "down"). Data moves between the 8-bit
memory chips and the low byte of the 16-bit data bus through a single 74LS245 (IC5).

Two things make the card more than "RAM plus ROM":

- **The FORCE-ROM boot remap.** The CPU starts fetching at $0000 after reset, but the monitor lives at $F000. A 74LS74
  flip-flop (IC12) is preset by -RESET and, while set, forces the top four address bits seen by the chips to 1111, so
  every address reads the $F000 block of the EEPROM. The first bus cycle whose ADDR15 is high clears the flip-flop and
  the real map appears. The monitor's first instruction is a `BR` to $F003, which is exactly that cycle
  (`firmware/monitor/monitor.asm` lines 58-61).
- **TMP0 and TMP1.** Two 16-bit registers built from four 74LS374 (IC26-IC29) sit on DATA0-15. They are the
  microcode's scratch words (the second operand of the ALU instructions, the return address during JSR, the swap
  space of PUSHR). They have nothing to do with memory decoding; they are on this card because it had the board space
  (`Notes.md`: "Should tmp registers be moved to ALU - I do not see why").

```
                 ADDR0..15 (A3..A18)                      DATA0..15 (A19..A30, B3..B6)
                       |                                            |
          +------------v------------+                  +------------v-------------+
          | IC8, IC9  74LS244 x2    |                  |  IC26/IC27  TMP0 (374x2) |<- -TMP-REG-LD0 / -RD0
          | ADDR -> BADDR0..15      |                  |  IC28/IC29  TMP1 (374x2) |<- -TMP-REG-LD1 / -RD1
          +--+---------+------------+                  +--------------------------+
             |         | BADDR12..15 (raw)                          | DATA0..7
             |   +-----v------+   FORCE-ROM   +--------+            |
             |   | IC11 74157 |<--------------| IC12   |<- -RESET   |
             |   | mux, B=1111|               | 74LS74 |<- ADDR15.VMA.BUS-EN (IC10, IC3)
             |   +-----+------+               +--------+            |
             |         | BADDR12..15 (mapped)                       |
             |   +-----v------+  Y0..Y7  +-------------+     +------v------+
             |   | IC7 74LS138|--------->| U$1 3x8 hdr |     | IC5 74LS245 | DIR = -MEM-RD
             |   | G1=BADDR15 |          | jumpers     |     | G   = -VMA  |
             |   | G2A=-VMA   |          +--+-------+--+     +------+------+
             |   | G2B=JP1    |    ROM row  |       | RAM row        | BDATA0..7
             |   +------------+   +--------v-+   +--v-------+        |
             |                    | IC18 7430|   | IC4 7430 |        |
             |                    +----+-----+   +----+-----+        |
             |          -ROM-CS (IC6/F) |    -HI-RAM (IC6/E)|        |
      BADDR0..14 -----+-----------------+---------+---------+        |
                      |                 |         |                  |
              +-------v------+  +-------v------+  +--------v-----+   |
              | IC1 62256    |  | IC13 28C64   |  | IC2 62256    |<--+
              | low RAM      |  | EEPROM 8K    |  | high RAM     |
              | -CS=-LO-RAM  |  | -CE=-ROM-CS  |  | -CS=-HI-RAM  |
              +--------------+  +--------------+  +--------------+
                    -OE (all three) = -MEM-RD via IC6/C+IC6/A;  -WE (all three) = -MEM-WR via IC6/D+IC6/B
```

## 2. Bus signals used

Names as in `firmware/microcode/yaccsignaldata2.h` (the sequencer's control-word table) and
`hardware/bus/bus-template/eagle/v3.2/Bus Template V3.2.sch`; pins from the card's own schematic. Direction is from
the card's point of view.

| Signal | Bus pin | Dir | What it does on this card |
|---|---|---|---|
| ADDR0..15 | A3..A18 | in | buffered by IC8/IC9 (74LS244) to BADDR0..15; ADDR15 is also taken raw into IC10 for the FORCE-ROM clock |
| DATA0..7 | A19..A26 | bidir | memory data through IC5 (74LS245); also the low byte of TMP0/TMP1 |
| DATA8..15 | A27..A30, B3..B6 | bidir | high byte of TMP0/TMP1 only; the memory chips never see it |
| -MEM-RD | B23 | in | direction of IC5 (low = memory drives the bus) and, through IC6/C then IC6/A, the -OE of IC1, IC2 and IC13 |
| -MEM-WR | B24 | in | through IC6/D then IC6/B, the -WE of IC1, IC2 and IC13 (see M2 in section 4) |
| -VMA | C12 | in | "valid memory address": IC5 output enable, IC7 G2A (high-32K decode), one input of the -LO-RAM NAND, one term of the FORCE-ROM clock, and the clock for TMP loads is not gated by it |
| -BUS-EN | C28 | in | one term of the FORCE-ROM clock (IC3/A ORed with -VMA); optionally IC7 G2B through JP1 |
| -RESET | C30 | in | presets IC12/A: FORCE-ROM = 1 |
| -TMP-REG-LD0 / -LD1 | B28 / B30 | in | inverted by IC14/A and IC14/F into the CLK of the TMP0 / TMP1 374s: the register latches at the **leading** edge of the strobe |
| -TMP-REG-RD0 / -RD1 | B27 / B29 | in | output enable of the TMP0 / TMP1 374s: the register drives all 16 data lines |
| VCC / GND | A2,B2,C2,A31,B31,C31 / A1,B1,C1,A32,B32,C32 | power | 24 x 100 nF-class decoupling C1-C24; PWR LED through R2 330 Ω |

Every other bus signal reaches the connector symbol only (the template's full set is on X1) and has no other node on
the card. In particular -IO-RD/-IO-WR, the register strobes and the ALU lines are not used here.

How the sequencer drives these: `software/ucemu/y1ucemu.c` is the executable statement of the bus model. It reads
memory while -MEM-RD and -VMA are both asserted (`compute()`, "MEM" driver), writes at the trailing edge of a step
that has -MEM-WR and -VMA (`mem[cur.addr] = ...`), ignores writes at or above $E000 ("the EEPROM: ignore writes"),
applies FORCE-ROM as `addr | 0xF000` and clears it when `vma && (a & 0x8000)`, and latches TMP0/TMP1 from the
**previous** step's bus value when -TMP-REG-LDn appears (leading-edge latch, section 1.6 of
`docs/isa/MICROCODE-REVIEW-NOTES.md`).

## 3. Schematic walkthrough, IC by IC

Part values are from `Memory V1.3.brd` (the schematic's value fields are mostly empty); the two 62256 and the 28C64
carry no value in either file, only the deviceset (`62256P`, `28C64C`).

### 3.1 Address path: IC8, IC9 (74LS244), IC11 (74LS157), IC12 (74LS74)

IC8 and IC9 are plain buffers with both enables grounded (`IC8.G`, `IC8/B.G`, `IC9.G`, `IC9/B.G` on GND): BADDR0..11
follow ADDR0..11 with one gate delay, always. The card therefore always loads the address bus with one LS input per
line and nothing more.

BADDR12..15 are different. ADDR12..15 go through IC9's second half (`IC9/B`) to nets N$15..N$18, which are the **A**
inputs of the quad mux IC11; the **B** inputs are tied to VCC. IC11's select pin (`!A/B`) is the net FORCE-ROM
(IC12/A Q) and its enable `G` is grounded. So:

- FORCE-ROM = 0: BADDR12..15 = ADDR12..15 (normal).
- FORCE-ROM = 1: BADDR12..15 = 1111, whatever the address bus says. Every address falls into the $F000 block.

IC12/A is the boot flip-flop: PRE = -RESET, CLR = VCC, D = GND, Q = FORCE-ROM. Reset sets it; the first rising edge on
its CLK (N$19) clocks a 0 in, and it stays 0 until the next reset. IC12/B is unused (CLK, CLR, D, PRE all on GND).

N$19 is built by IC10 and IC3: IC3/A (74LS32) ORs -VMA with -BUS-EN (N$25, low only when both are asserted); IC10/D is
wired as an inverter (N$22 = VMA AND BUS-EN); IC10/B NANDs that with the **raw** ADDR15 (not BADDR15: `Notes.md` "ROM
address map triggered by HIGH on ADDR15 not BADDR15" — with the mapped BADDR15 the mux would feed the flip-flop its
own forced 1 and the remap could never release); IC10/C inverts again, so N$19 = ADDR15 AND VMA AND BUS-EN. In words:
FORCE-ROM is released by the first bus cycle that is valid, enabled, and addresses the upper 32K.

### 3.2 Block decode: IC7 (74LS138), U$1 (3x8 jumper block), IC4 and IC18 (74ALS30), IC6 (74LS04)

IC7 decodes BADDR12..14 (A, B, C) into eight active-low block selects Y0..Y7 = $8000, $9000, ... $F000. Its three
enables make the decode conditional: G1 = BADDR15 (upper half only), G2A = -VMA (valid cycles only — added in v1.2,
`Notes.md`), G2B = N$24 = pin 2 of JP1 (see section 5).

The eight outputs go to the middle row of the 3x8 header U$1 (pins 9..16 = Y0..Y7). The other two rows are the two
functions a block can have:

- pins 1..8 ("ROM row"): pulled up by RN7 (SIL9, common pin 1 to VCC) and fed into the eight inputs of IC18 (74ALS30
  8-input NAND). Pin 8 is I0, pin 1 is I7. A jumper from a block's centre pin to its ROM-row pin pulls that NAND input
  low when the block is selected; the NAND output N$1 goes high; IC6/F inverts it to -ROM-CS = IC13 -CE.
- pins 17..24 ("RAM row"): pulled up by RN8, into IC4 (74ALS30); N$14 through IC6/E gives -HI-RAM = IC2 -CS.

An unjumpered block leaves both NAND inputs high: nothing is selected, and a read returns whatever the bus was left
at ("looks like RAM that echoes the last write", `docs/system/MACHINE.md`). This is the mechanism behind
`tests/memory/memory_status.py`'s block classification (RAM / ROM / VIDEO / undecoded) and the reason the video card
can sit at $D000 without a change on this card.

Only BADDR0..12 reach the EEPROM (A0..A12, 8K), so with $E and $F both jumpered "down" both halves of the 28C64 are
reachable: $E000-$EFFF = EEPROM offset $0000 (BASIC), $F000-$FFFF = offset $1000 (monitor). `tools/img2bin.py`'s
`--base 0xE000` in the ROM test READMEs is this offset.

### 3.3 Low RAM select: IC10/A, IC14/B, IC14/E

Low RAM has no jumper. IC14/B inverts BADDR15 (N$13), IC14/E inverts -VMA (N$12) and IC10/A NANDs them: -LO-RAM = IC1
-CS is low whenever BADDR15 = 0 and -VMA is asserted (`Notes.md` v1.2: "Combine -VMA and LOW BADDR15 to generate -CS
for LOW RAM so LOW RAM cannot be selected with -VMA not asserted"; "7400 added back in to generate LOW RAM -CS").
Because it is BADDR15 and not ADDR15, low RAM is *not* selected during FORCE-ROM (BADDR15 is forced high), which is
what lets the ROM answer at $0000 after reset.

### 3.4 Read/write strobes: IC6 (74LS04)

IC6/C inverts -MEM-RD to MEM-RD, IC6/A inverts it back onto N$3, the -OE of IC1, IC2 and IC13. IC6/D and IC6/B do the
same for -MEM-WR onto N$4, the -WE of all three. The double inversion is a buffer, not logic: each chip's -OE and -WE
are the bus strobes re-driven by one LS gate. There is no address, -VMA or FORCE-ROM term in the write enable; the
chip *select* carries all the qualification. For the two RAMs that is fine (a 62256 write needs -CS and -WE both
low). For the EEPROM it is the M2 finding (section 4).

### 3.5 Data path: IC5 (74LS245), RN5/RN6

IC5's A side is DATA0..7, its B side BDATA0..7 (the three memory chips' I/O pins). G = -VMA, DIR = -MEM-RD. With the
74LS245 convention DIR high = A to B, the card receives the bus (bus to memory) whenever -VMA is low and -MEM-RD is
high, and drives the bus (memory to bus) while -MEM-RD is low. The 245 is therefore *always* turned on during a valid
cycle, in the write direction unless a read is in progress — `Notes.md` v1.2: "-VMA to enable 74245 bus data buffer
pin 19". The datapath review notes the ~20-30 ns BDATA overlap at the end of a read (the 245 turns around before the
RAM's -OE releases) as normal for LS parts.

RN5 and RN6 (RN-9, common pin 1 on **GND**) hang on DATA0..7 and DATA8..15: they are pull-downs on the whole data
bus. Their value is empty in both `.sch` and `.brd` (M8). **To verify:** measure the resistance from bus pin A19
(DATA0) to GND with the card out of the bus; if it is below ~4.7 kΩ every LS driver on the bus is over its IOH budget,
and MACHINE.md's "undecoded block echoes the last value" observation suggests they are high-value or not fitted.

### 3.6 TMP registers: IC26-IC29 (74LS374), IC14/A and IC14/F

TMP0 = IC26 (DATA0..7) + IC27 (DATA8..15); TMP1 = IC28 + IC29. Each 374's D and Q pins are on the same bus line
(`DATA0: IC26.1D IC26.1Q ...`), the classic bus-register wiring. Output enable (`OC`) = -TMP-REG-RD0 / -TMP-REG-RD1
straight from the bus, so a TMP read drives all sixteen lines. The clock is -TMP-REG-LDn through an inverter
(IC14/A gives N$33 for TMP0, IC14/F gives N$47 for TMP1): a 374 clocks on the rising edge of CLK, which is the
**falling** edge of the bus strobe. The register captures what is on the bus about 10 ns after -TMP-REG-LDn goes
low (M3) — the source must already be on the bus when the strobe starts, which the microcode arranges by asserting
the source one step before the load (`memory.c:24-28`, `accumulator.c:343-349`, `branch.c:624-631` per the review).

IC14/B and IC14/E are the inverters of section 3.3; IC14/C and IC14/D are unused and their inputs (pins 5 and 9)
have no net in the PCB (M6).

### 3.7 Gate-count check (what the review calls "checked, no issue")

- 62256 -OE = -MEM-RD (two inverters), -WE = -MEM-WR (two inverters): never both low from a sane control word.
- Write ordering: the generator asserts the address, -VMA and the source one step before -MEM-WR and holds the source
  one step after (`main.c:236-249`), so the decode (IC8/9, IC11, IC7, IC4/IC18, IC6) has a full step to settle
  before -WE falls.
- FORCE-ROM uses raw ADDR15, so the IC11 feedback cannot hold it set.
- Reset polarity: IC12/A PRE is active low and the bus -RESET is active low.

The Logisim file `hardware/cards/memory/eagle/v1.3/ROM ZSelect.circ` is a simulation of this select logic (a 7400-
series library model); it is the designer's check of the jumper/NAND arrangement, not a source of any other fact.

## 4. Timing and the design-review findings

Timing facts come from `docs/isa/MICROCODE-REVIEW-NOTES.md` section 1: one microcode step is two clock periods; a
memory read must deliver its byte within the step that asserts -MEM-RD when the consumer is a leading-edge latch (the
instruction register at step 2, the operand register, TMP, the accumulator); a write is trailing-edge (the 62256
takes data at the rising edge of -WE) with the address stable through the strobe step. The review lists the
"one-step memory windows before leading-edge latches" (LDTI, LDIVR, LDT, BRANCH-LD, INT-LD) as the first thing to
fail at a faster clock; the memory card's part of that path is IC8/IC9 (244), IC7/IC4/IC18/IC6 (decode, ~4 gates),
the RAM access time, and IC5 (245). No measured figure for the maximum clock is in the tree.
**To verify:** the frequency at which `BR` mis-targets or `INP` reads $FF with a function-generator clock (the
review's bench item 6).

Findings that concern this card, with their status on 2026-09-23:

| ID | Severity | Finding | Status 2026-09-23 |
|---|---|---|---|
| M1 (`DESIGN-REVIEW-NOTES-datapath.md`) | HIGH, masked | FORCE-ROM's clock is ADDR15·VMA·BUS-EN (three gates, ~35 ns after -VMA falls) while the register card needs ~75 ns to drive the address after -VMA; between cycles the address bus floats high, so the first -VMA after reset would clear FORCE-ROM regardless of the address. Masked since 2020 by the generator asserting -VMA in **every** step (`main.c:102,115` "Hack prevent ROM mapping from triggering"), which keeps the address bus driven at all times — and thereby removes the -VMA qualification from every chip select on this card (IC7 G2A, -LO-RAM, IC5 G are permanently active). | Open. Hazard returns if any microcode line drops -VMA or the tester drives -VMA with the address bus tri-stated. The tester tests pass because the tester drives the address before it lowers -VMA. |
| M2 | MED | The 28C64's -WE is raw -MEM-WR (N$4), with no write-protect jumper; during FORCE-ROM every address selects block $F, so a store before the first jump above $8000 writes the EEPROM; any later stray write into $E000-$FFFF does too, and a 28C64 then spends ~10 ms in an internal write cycle during which reads return the poll bits (code executing from ROM crashes). | Open. The shipped monitor is safe by construction (`BR eprom` first). The ROM was byte-identical to the sources on 2026-09-18 and again in the 2026-09-21 full test (`tests/memory/full-run-2026-09-21.log`, phase A and F), so it has not happened yet or the fitted chip has data protection. **To verify:** whether the fitted 28C64 has software data protection enabled (read the chip's part marking/datasheet). |
| 1.3 (`DESIGN-REVIEW-NOTES-control-io.md`) | MED | The sequencer's pipeline is not reloaded while reset is asserted, only on its release; during reset the bus carries the last or power-up control word. With FORCE-ROM active and a stale word that has -MEM-WR and -VMA asserted, that is an EEPROM write during reset (same path as M2). | Open (a sequencer v2.2 item). Bench: scope B24 and C12 during power-up and with RESET held; run `tools/verify_firmware.py` after a batch of power cycles. |
| M3 | MED | TMP registers latch on the leading edge of -TMP-REG-LDn; correct only under the microcode's source-one-step-early rule. `moveRegtoTmp` in `branch.c:14-22` breaks the rule but has no callers. | Open, latent. |
| M4 / B1 | MED, configuration | Low RAM cannot be jumpered out; with a bring-up card (Mem Switch at $0000-$000F, Mem Register at $0010-$001F) on the bus at the same time, a read of $0000-$001F has two drivers on DATA0..7, three after reset with FORCE-ROM. | Open. MACHINE.md: the bring-up cards were re-fitted 2026-09-21 for CPU bring-up; whether the memory card was in at the same time is not recorded. **To verify:** which cards share the bus in the current bring-up configuration. |
| M5 / S3 | LOW | All control inputs (-MEM-RD, -MEM-WR, -VMA, the TMP strobes) are 74LS374 outputs on the sequencer whose OC is -BUS-EN; nothing pulls them up on any card or the backplane (5.1 in the control/IO notes). They float for the ~54 s microcode load and on every handover; LS inputs read that as high (inactive), but the 62256/28C64 -WE depends on it. | Open, by convention. Bench: B24 reads ~1.5-1.9 V with the sequencer not READY. |
| M6 | LOW | IC14 pins 5 and 9 open (no net). | Housekeeping. |
| M7 | LOW | IC7 G2B is JP1 pin 2 only; with no jumper the whole high-32K decode is dead. MACHINE.md's "jumper wire from IC7 pin 4, unconnected" — pin 4 is G2A = -VMA; if that wire ever replaces the track, the same symptom. | Open: the wire's purpose is not remembered (`BACKLOG.md`). |
| M8 | LOW | RN5/RN6 value unknown (section 3.5). | Open. |
| S1 | MED, system | No power-on reset anywhere: -RESET is a manual RS latch on the sequencer, so FORCE-ROM is undefined at power-up until the button is pressed. | Open. |
| H-1 / H-2 (`docs/isa/MICROCODE-REVIEW-NOTES.md`) | HIGH, microcode | PUSHR wrote both stack bytes while TMP1 (this card's IC28/IC29) and the register card both drove the data bus; BRZ/BRNZ loaded the PC while the ALU still drove the bus. Not faults of this card, but TMP1 is one of the fighting drivers in H-1. | **Fixed** in the generator 2026-09-22 and loaded into the sequencer EEPROM the same evening (MACHINE.md, BACKLOG). H-3 (BR16Z/NZ) stands. |

## 5. Jumpers, headers, LEDs, connectors — and how the machine is set

| Item | What it is | Setting in the machine (`docs/system/MACHINE.md`, verified with the bus tester 2026-09-18) |
|---|---|---|
| U$1, 3x8 header (`PIN_3X8`, `pinhead_3row`) | one column per 4K block $8000..$F000 (centre pins 9..16 = IC7 Y0..Y7); centre-to-RAM-row (pins 17..24) = high RAM, centre-to-ROM-row (pins 1..8) = EEPROM, no jumper = undecoded | $8000-$CFFF five jumpers to RAM ("up"), $D000 no jumper (reserved for the video card), $E000 and $F000 two jumpers to ROM ("down") |
| JP1, 1x3 (`PINHD-1X3`) | pin 1 = -BUS-EN, pin 2 = IC7 G2B, pin 3 = GND: 1-2 gates the high-32K decode with -BUS-EN, 2-3 enables it unconditionally; open = decode dead (M7) | **To verify:** which position is fitted (not recorded in MACHINE.md) |
| PWR LED + R2 330 Ω | power indicator on VCC | — |
| X1, DIN 41612 96-pin (`FABC96R`, "DIN41612-R") | the bus | the slot is not recorded. **To verify:** slot position |
| IC13 socket | the 28C64; the v1.2 build notes say to keep each EEPROM in its own machined socket and move the pair, never the bare chip | holds the 2021 build (`firmware/rom/eprom-captured-2026-09-18.bin`); `firmware/rom/shipped/rom` (2026-09-22) is waiting to be burned |
| Unconnected wire from IC7 pin 4 | present on the board, purpose not remembered | see BACKLOG; trace it or remove it |

Which row of U$1 is physically "up" and which is "down" on the silkscreen is MACHINE.md's wording; the schematic only
gives pin numbers (ROM row = pins 1-8, RAM row = 17-24). **To verify:** the silkscreen orientation before moving a
jumper.

Memory map that results (also `docs/system/OS-PLAN.md` decision 4, variant A):

| Range | Chip | Notes |
|---|---|---|
| $0000-$7FFF | IC1 62256 | always; after reset it is shadowed by the ROM until the first A15-high cycle |
| $8000-$CFFF | IC2 62256 (blocks 8..C) | five jumpers "up" |
| $D000-$DFFF | none on this card | the video card decodes $D000-$D7FF; $D800-$DFFF answers nothing (`memory_full_test.py` phase F2) |
| $E000-$EFFF | IC13 offset $0000 | BASIC (`firmware/basic`) |
| $F000-$FFFF | IC13 offset $1000 | monitor, BIOS vectors $FFC0-$FFF8 (`firmware/abi/README.md`) |

## 6. Bring-up and test

How the card was proven (all through the Bus Test Card, `docs/cards/bus-tester.md`, host `tools/busdrv.py`):

1. `tests/memory/memory_status.py` (~1 min): pulses -RESET, asserts -BUS-EN and -VMA, puts the tester's address bus
   in write mode and data bus in read mode, then reads $0000-$000F and expects the ROM's $F000 page (the FORCE-ROM
   check); reads $F000 to release the remap; write/read spots in low RAM; classifies every 4K block above $8000.
2. `tests/memory/rom_verify.py` (~30 s): every byte of $E000-$FFFF against the image `tools/romimage.py` builds from
   `firmware/basic/basic.img` + `firmware/monitor/monitor.img`. Until the 2026-09-22 ROM is burned it reports the
   monitor half as different (MACHINE.md).
3. `tests/memory/memory_full_test.py` (~16 min with the blocks-1 tester firmware): ROM, address-line independence
   (a unique byte at $0000 and at every 1<<n), two full RAM sweeps written and verified in separate passes (retention),
   the video RAM, ROM again, $D800-$DFFF silent. Result 2026-09-21: 14/14 PASS
   (`tests/memory/full-run-2026-09-21.log`; the three other logs in the folder are the aborted attempts of the same
   day — a USB link drop and a stop for the tester reflash).
4. The 2020 scripts in `tests/bus-tester-scripts/Memory Card Tests/` (`basic mem test low and eprom.txt`,
   `... low hi and eprom.txt`, `dump-eprom.txt`) do the same by hand: reset, `-VMA:1#`, `ADDRBUS-WR-MODE:1#`,
   `DATABUS-RD-MODE:1#`, `DUMP:0000-000F#`, `DUMP:F000-F00F#`, then a FOR loop of `WR-ADDRBUS`/`WR-DATABUS`/
   `-MEM-WR:1#`/`-MEM-WR:0#`.
5. With the CPU: `tests/assembler/romcount` (burned in place of the monitor) proves the fetch path from $F000 under
   FORCE-ROM and the release on the first `BR`; it ran overnight into 2026-09-23 without a fault (MACHINE.md).

The bring-up order in `eagle/deprecated/v1.2/Build Notes.md`: power check (the six GND and six VCC pins of the
connector), PWR LED, bus tester in, `bus-test` sketch for shorts, then all ICs and the memory test script.

What to measure if it misbehaves:

| Symptom | Where to look |
|---|---|
| $0000-$000F after reset is not the ROM's $F000 page | IC12/A pin 5 (FORCE-ROM) should be high after -RESET; if it drops on the first cycle, M1 (address bus floating when -VMA falls) — scope IC12 pin 3 against pin 5. IC11 select pin. |
| a jumpered block reads as undecoded | JP1 (M7): IC7 pin 5 must be low; IC7 pin 4 (-VMA) must follow C12; the jumper's NAND input (IC4/IC18) must go low when the block is addressed |
| writes to $E000-$FFFF change the ROM | expected as built (M2): -WE on IC13 pin 27 follows B24 one for one. Re-verify with `rom_verify.py`, re-burn from `firmware/rom/shipped/rom` |
| a byte reads back differently minutes later | RAM retention; `memory_full_test.py` phases C/D separate the write sweep from the read sweep for this reason |
| reads return the last value on the bus | the block is undecoded (no jumper) or the 245 is not turning around: IC5 pin 1 (DIR) = B23, pin 19 (G) = C12 |
| TMP values wrong (JSR returns to the wrong place, ALU operands stale) | M3: the source must be on the bus before -TMP-REG-LDn falls; with the tester, put a value on DATA, assert -TMP-REG-LD0, change DATA while still low, release, read back with -TMP-REG-RD0: the first value must return |
| control lines at ~1.5-1.9 V | the sequencer is not READY or -BUS-EN is high (M5): nothing pulls them; not a fault of this card |

## 7. Revision history and what a next revision should change

| Rev | Date | Status | What changed (`hardware/FABRICATED.md`, the Notes files) |
|---|---|---|---|
| v1.0 | 2020-06 | fabricated, retired | first card; IN/OUT bus signals were still active-low in the template ("converted from active low to Active HI ... not used in memory board") |
| v1.1 | 2020-06-19 (files still named V1.0) | fabricated, retired | adds the boot ROM remap: IC11 74LS157 + IC12 74LS74 FORCE-ROM ("Add memory map ROM to 0x0000 until 0xf000 is accessed") |
| v1.2 | 2020-11-29 | fabricated (built), retired 2021 | -VMA arrives on the bus (Blank V3.1 note): -VMA enables IC5, gates IC7 (pin 4) and the low-RAM -CS; the remap trigger moves from BADDR15 to raw ADDR15; "RN3&4 BADDR pull-ups not needed, leave in design"; the 7400 removed then added back for -LO-RAM. `media/memory v1.2 top.jpeg` and `... solder.jpeg` are photographs of this build |
| v1.3 | design 2021-03-17, boards ordered 2025-06-27 | **in the machine** | "ARGH": the 3x8 jumper block on IC7's outputs with pull-ups so any 4K block can be removed from the map (for memory-mapped I/O — the video card uses it); KiCad conversion in `kicad/v1.3` (netlist proof 115/115) |

**Planned (Ken, 2026-09-24; not designed yet):** the CompactFlash interface goes onto this card, which has room for
it. It stays I/O-mapped on ports P8/P9, as the ROM and the emulators use them, with the CF card v1.0 circuit
([`cf.md`](cf.md)); it would be the first use of the IO-ADDR0..3, -IO-RD and -IO-WR pins this card leaves unwired today.

Open ideas from `eagle/v1.3/Notes.md`, `BACKLOG.md` and the reviews, for a v1.4:

1. **Gate the EEPROM write (M2).** Either -WE = -MEM-WR OR FORCE-ROM (no writes while the remap is on) or, better, a
   write-protect jumper on IC13 pin 27 that is only closed for burning in place. This also closes the reset-time
   window of finding 1.3.
2. **The 4K-block EEPROM select** ("Jump select by 4k block EEPROM", Notes): today the EEPROM's A12 is BADDR12, so the
   chip's two halves are pinned to $E and $F. A jumper that picks which 4K of the 8K answers a given block would let a
   single block ($F000) carry either half, freeing $E000 for RAM (OS-PLAN's variant B moves video, not ROM, so this
   is independent).
3. **Hard-jumper a boot-loader enable** (Notes): a way to force or defeat FORCE-ROM from a header for bench work.
4. **Fix M1 properly**: clock IC12 from the *trailing* edge of the cycle, or qualify the clock with a delayed -VMA,
   so the microcode can stop asserting -VMA in every step and the chip selects regain their -VMA gating.
5. **Pull-ups on the strobe inputs** (M5) or on the backplane (control/IO 5.1), so the EEPROM -WE has a defined level
   when the sequencer is off the bus.
6. **Jumper out low RAM** (M4) or at least the first 32 bytes, so the bring-up cards can coexist with the card.
7. Record RN5/RN6's value (M8); tie IC14 pins 5 and 9 (M6); decide the IC7-pin-4 wire.
8. The datapath review's question whether TMP should move to the ALU is answered "no" in the Notes; the H-1 fix
   removed the microcode fight that involved TMP1, so nothing in the hardware needs to move.

The 2025 gerbers came from Fusion's CAM; `BACKLOG.md` asks for an overlay against the tree's Eagle board
(netlist proven, gerbers not).
