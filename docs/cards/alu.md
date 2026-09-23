# ALU card (V3.2) — theory of operation

The 8-bit arithmetic/logic unit of the YACC1 with the accumulator (AC), the carry flip-flop, the shift register and
the branch-condition multiplexer that every conditional branch in the machine goes through.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/alu/eagle/v3.2/ALU V3.2.sch` (parsed with Python's `xml.etree`; every net and gate below comes
from its `<part>`/`<net>/<pinref>` elements), `hardware/cards/alu/README.md`, `eagle/v3.2/Notes.md`, the deprecated
revisions' `Notes.md`, `hardware/FABRICATED.md`, `hardware/PROVENANCE.md`, `hardware/NEWER-DESIGNS-vs-ACTIVE.txt`,
`hardware/DESIGN-REVIEW-NOTES-datapath.md` (ALU section, A1–A3), `docs/isa/MICROCODE-REVIEW-NOTES.md` (1.4, H-2, H-3, M-5,
section 3), `firmware/microcode/yaccsignaldata2.h`, `firmware/microcode/ucode-generator2/{CodeGen.h,accumulator.c,branch.c}`,
`software/ucemu/y1ucemu.c` (`compute()`, `do_step()`), `docs/system/MACHINE.md`, `BACKLOG.md`,
`tests/bus-tester-scripts/ALU/`, `tests/assembler/{ledcount,romcount,romdiag}`, `media/alu v3.2 top.jpeg`.

Eagle gate letters are used for the glue logic (IC6C = gate C of IC6). Net names `N$nn` are the schematic's own.

---

## 1. Purpose and place in the machine

The YACC1 has one 8-bit accumulator and does all its byte arithmetic on this card. The other operand comes over the
16-bit data bus from memory, a TMP register on the memory card, or an index register; the sequencer tells the card what
to do with four function bits `ALU0..3` and a handful of strobes; the result goes back into the accumulator, and the
accumulator can be put onto the bus. The card also answers one question for the sequencer: is the branch condition
selected by `ALU0..2` true right now (`BR-COND`)? The 16-bit index registers live on the register cards and never pass
through the ALU (they count up and down themselves); the TMP registers moved to the memory card in 2020.

```
   DATA0..15 <==IC10/IC11 74*245==> BDATA0..15 (RN1/RN2 10k pull-ups)   G = -ALU-FUNC OR -BUS-EN, DIR = -AC-RD
                                       |
        +------------------------------+----------------------------------------------+
        |  function blocks, one enabled by IC8 74*138 (ALU0..2) onto INV-IN0..7:      |
        |   0 DATA  IC13 (BDATA)        4 XOR  IC17 (IC14/IC15 ACO^BDATA)               |
        |   1 SUB   IC37 (adder)        5 SHIFT IC31 (IC29/IC30 74*194 outputs)         |
        |   2 AND   IC20 (IC18/IC19)    6 ZERO IC16 (inputs GND)                        |
        |   3 OR    IC23 (IC21/IC22)    7 ADD  IC37 (IC35/IC36 74*283, B = BDATA^SUB)   |
        +------------------------------+----------------------------------------------+
                                       |  INV-IN0..7
                        IC2 74*240 (invert, -AC-LD-INV) / IC3 74*244 (straight)
                                       |  ACI-DATA0..7
                        IC5 74*374 ACCUMULATOR, CLK = AC-LD = NOT -AC-LD ---> ACO-DATA0..7
                                       |                                  |
                    IC12 74*244 (G = -AC-RD) ---> BDATA0..7  <-------------+ (adders, gates, comparators, shifter, SV1)
   carry FF IC9A (CO/BO or SHIFT-OUT, clocked with AC-LD on add/sub/shift) ---> C/SHIFT
   IC24/IC25 74*85 (BDATA vs ACO), V1/V2 4078 zero detect, IN, C/SHIFT ---> IC26 74*251 --XOR AC-LD-INV--> BR-COND (C24)
```

Fabricated 2020-11-29, in the machine (`hardware/FABRICATED.md`, Ken 2026-09-20). `media/alu v3.2 top.jpeg` shows it
built with 74HC parts (SN74HC244N/245N/374N/153N/138N/74N/86N/32N, CD74HC194E, CD74HC283E, CD74HC85E, MC74HC08AN,
CD4078BE for V1/V2) where the schematic says `74*xxN` — see 4.5.

## 2. Bus signals

Direction is seen from this card. Pins are the DIN 41612 pins of X1.

| Pin | Signal | Dir | On this card |
|---|---|---|---|
| A3–A18 | ADDR0..15 | – | connector only (not used) |
| A19–A26 | DATA0..7 | in/out | IC10 (74*245) <-> BDATA0..7: receives the operand while `-ALU-FUNC` is low, drives the accumulator while `-AC-RD` is also low |
| A27–A30, B3–B6 | DATA8..15 | in/out | IC11 <-> BDATA8..15: received for the 16-bit zero test (D6); **driven with the pull-up value $FF whenever the card drives** (BDATA8..15 has no source but RN2) |
| B7–B30 | register / memory / TMP strobes | – | connector only |
| C3–C11 | ADDR-REG-ID, IO-ADDR, -IO-ADDR-LD | – | connector only |
| C12 | -VMA | – | connector only (`Notes.md` 3.1: "BUS changed UNUSED -VMA (not used by ALU)") |
| C13, C14 | -INT, -INTA | – | connector only |
| C15 | -ALU-FUNC | in | enables the bus transceivers (IC7D) and, through JP1, optionally the condition mux (IC26 G) |
| C16–C19 | ALU0..3 | in | IC8 (function block select, ALU0..2), IC26 (condition select, ALU0..2), IC29/IC30 mode (ALU0..1), IC28 serial-input select (ALU2..3), IC32 shift-out select (ALU0..1), IC6D (ALU3 = "add the carry") |
| C20 | -AC-LD-INV | in | IC1A -> `AC-LD-INV`: selects IC2 (inverting) instead of IC3 into the accumulator, and inverts BR-COND (IC27C) |
| C21 | -AC-RD | in | direction of IC10/IC11 (low = card -> bus) and enable of IC12 (accumulator onto BDATA) |
| C22 | -AC-LD | in | IC1F -> `AC-LD`: the accumulator clock (rising edge = leading edge of the strobe) and, through JP2, the carry flip-flop clock qualifier |
| C23 | -SR-LD | in | IC1C -> `SR-LD`: the shift-register and shift-out clock |
| C24 | BR-COND | out | IC27C = IC26 Y XOR AC-LD-INV — the only line this card drives besides DATA |
| C25 | -HL-SWAP | – | connector only |
| C26 | IN | in | IC26 D5: the input-switch line tested by BRINH/BRINL |
| C27 | OUT | – | connector only |
| C28 | -BUS-EN | in | IC7D: the transceivers are enabled only while `-BUS-EN` and `-ALU-FUNC` are both low |
| C29 | -RUN | – | connector only |
| C30 | -RESET | in | CLR of IC9A (carry) and IC9B (shift-out) |
| A2/B2/C2, A31/B31/C31; A1/B1/C1, A32/B32/C32 | VCC; GND | in | 39 x 100 nF C1–C39 (C21's value is typed ",1uf"), PWR LED through R1 (330) |

Function and condition codes, as the generator names them (`CodeGen.h`) and the emulator models them (`y1ucemu.c compute()`):

| ALU2..0 | IC8 output | Function block -> INV-IN | Condition (IC26 D input) |
|---|---|---|---|
| 0 | -DATA | BDATA (pass the operand) | D0 = VCC: always true (`ALUBR`) |
| 1 | -SUB | AC − BDATA (adder with B inverted, +1 or +carry) | D1 = BDATA < AC (`ALUGT`: "AC greater") |
| 2 | -AND | AC AND BDATA | D2 = BDATA == AC (`ALUEQ`) |
| 3 | -OR | AC OR BDATA | D3 = BDATA > AC (`ALULT`) |
| 4 | -XOR | AC XOR BDATA | D4 = BDATA0..7 == 0 (`ALUZ`) |
| 5 | -SHIFT | the shift register | D5 = IN (`ALUIN`) |
| 6 | -ZERO | 0 | D6 = BDATA0..15 == 0 (`ALU16Z`) |
| 7 | -ADD | AC + BDATA (+carry if ALU3) | D7 = C/SHIFT, the carry (`ALUCS`) |

`ALU3` = `CARRY_SHIFT`: with ADD/SUB it feeds the carry flip-flop into the adder's carry-in (ADDIC/ADDTC); with SHIFT it is
one of the two serial-input select bits (4.3).

## 3. Schematic walkthrough

Nine sheets: 1 accumulator and carry, 2 pull-ups, 3 bus interface, 4 logic functions, 5 compare and branch, 6 shifter,
7 adder, 8 spares, 9 connectors.

### 3.1 Sheet 3 — bus interface

- IC7D: `-ALU-IO-EN` = `-ALU-FUNC` OR `-BUS-EN`. It is the `G` of the two 74*245 transceivers IC10 (DATA0..7 <-> BDATA0..7)
  and IC11 (DATA8..15 <-> BDATA8..15), whose `DIR` is `-AC-RD`. `-AC-RD` high: bus -> BDATA (the operand comes in);
  `-AC-RD` low: BDATA -> bus.
- IC12 (74*244, `G` = `-AC-RD`): `ACO-DATA0..7` -> `BDATA0..7`. So with `-AC-RD` low the accumulator is on BDATA0..7 and,
  through IC10, on DATA0..7; BDATA8..15 has nothing but RN2 (3.2) and IC11 puts that $FF on DATA8..15. Every STA, STAVR,
  PUSH, OUTA, MVAT, MVARL/MVARH therefore writes $FF on the high byte — harmless where the high byte is not latched, and a
  documented definition where it is (MVAT loads TMP0 = $FFxx, `MICROCODE-REVIEW-NOTES.md` section 4).
- IC13 (74*244, `G` = `-DATA` = IC8 Y0): `BDATA0..7` -> `INV-IN0..7`, the "pass the operand" function (LDAI, LDA, POP,
  INP, MVTA, MVRLA ... all load the accumulator through it).

The microcode always pairs `-AC-RD` with `-ALU-FUNC` (`accumulator.c:343, 377, 513`), so IC10/IC11 are enabled whenever the
card is asked to drive. The 2026-09-21 review's A3 notes the ~10–20 ns overlaps at the release edge (245 turning round
before IC12 has turned off) — normal for this logic family.

### 3.2 Sheet 2 — pull-ups

RN1 (8 x 10k, common to VCC) on `BDATA0..7`, RN2 on `BDATA8..15`. They define the bus when nothing drives it (the
comparators, the XOR array and the zero detectors always see a level) and are the source of the $FF on DATA8..15 above.

### 3.3 Sheet 1 — accumulator, load path, carry flip-flop

- IC1 is the hex inverter: A `AC-LD-INV` = NOT `-AC-LD-INV`; B `SUB` = NOT `-SUB`; C `SR-LD` = NOT `-SR-LD`; D `N$15` =
  NOT `-ADD/SUB`; E `CO/BO` = NOT `N$16`; F `AC-LD` = NOT `-AC-LD`.
- Load path: IC3 (74*244, `G` = `AC-LD-INV`) passes `INV-IN0..7` straight to `ACI-DATA0..7`; IC2 (74*240, `G` = `-AC-LD-INV`)
  passes them inverted. Exactly one is enabled (complementary enables through IC1A, with the ~10 ns overlap of A3). This is
  how INVA ($B5) is one step: DATA function with `-AC-RD` (AC on BDATA) and `-AC-LD-INV`.
- IC5 (74*374): `D` = `ACI-DATA0..7`, `CLK` = `AC-LD`, `OC` = GND (always driving `ACO-DATA0..7`). **The accumulator latches
  on the leading (falling) edge of `-AC-LD`**, i.e. what the function block produced at the end of the previous step.
  `ACO-DATA` goes to IC12, both adders' A inputs, all the gate arrays, the comparators' B inputs, the shifter's parallel
  inputs, IC28 2C2 (bit 7 for sign-propagating shifts) and the debug header SV1.
- IC8 (74*138): `A,B,C` = `ALU0..2`, `G1` = VCC, `G2A` = `G2B` = GND — permanently enabled. Its eight active-low outputs
  enable one function buffer each (2). Because it is not qualified by `-ALU-FUNC`, a function block is always driving
  `INV-IN`; the accumulator simply does not clock unless `-AC-LD` comes.
- IC6A: `-ADD/SUB` = `-ADD` AND `-SUB` (low for either): enables IC37 (the adder's output buffer) and feeds the carry logic.
- Carry flip-flop IC9A (74*74): `D` = `N$7` = IC7A = `CO/BO` OR `SHIFT-OUT`; `CLK` = `N$5` = IC6C = `N$3` AND `N$9`;
  `N$3` = IC4A = NAND(`-ADD/SUB`, `-SHIFT`) = "the function is add, sub or shift"; `N$9` = JP2 pin 2 (1 = `-AC-LD`,
  3 = `AC-LD`); `PRE` = VCC, `CLR` = `-RESET`; `Q` = `C/SHIFT`. With JP2 on `AC-LD` the flip-flop clocks on the same leading
  edge as the accumulator, but only for add/sub/shift functions: logic operations preserve the carry. `Notes.md` (3.2):
  "Ic6 pin 10 - -ac-ld or ac-ld - added jumper - should be ac-ld". **To verify:** JP2 position — the photo shows the cap on
  the pair nearest the `-AC-LD` silk, which would clock the carry at the *trailing* edge of the strobe (still while the
  operand and function are held, so it works, but one step later than the accumulator).
- **Found on the machine 2026-09-23: SHIFT-OUT is not gated off for add/subtract.** IC7A ORs `SHIFT-OUT` (IC9B, which
  keeps the last bit shifted out until the next `SR-LD`) into the carry flip-flop's `D` for every add/sub/shift clock, so
  a 1 left by an earlier shift became the carry of the next ADD/SUB. `tests/bench/diag/div.c` showed it (300-1000 =
  $FE44, divisions after a hex print = $FFFF, 300*7 = $0A34); `software/ucemu` with the ALU modelled as drawn (now its
  default; `-K` = the old model) reproduced every wrong value. Fixed in the microcode, not the card: `aluOp()`
  (`firmware/microcode/ucode-generator2/accumulator.c`) parallel-loads the shift register before every add/subtract,
  which clocks IC9B with 0 (IC32 selects 0 in load mode); six records change (ADDI, SUBI, ADDT, SUBT, ADDIC, ADDTC).
  A card revision could AND `SHIFT-OUT` with the shift function instead.
- `CO/BO` (IC1E) = `N$15` AND `N$10`, `N$15` = ADD/SUB active, `N$10` = IC27B = `N$1` XOR `SUB`, `N$1` = IC36 C4 (the
  adder's carry out): the carry for an add, the borrow (carry inverted) for a subtract, and 0 for any other function —
  the V3.2 change "Added gating so CO/BO is anded with -ADD/SUB so CO/BO only can go high during add/sub".

### 3.4 Sheet 7 — adder and subtractor

- IC33/IC34 (74*86): `N$28, N$12, N$26, N$27, N$29, N$13, N$31, N$32` = `BDATA0..7` XOR `SUB`: the operand is inverted for
  a subtraction (two's complement with the +1 from the carry-in). V3.2 swapped this: "Flipped AC and BDATA for add/sub
  circuit, BDATA now goes into xor array, AC directly into adders".
- IC35 (bits 0..3) and IC36 (bits 4..7), 74*283: `A` = `ACO-DATA`, `B` = the XOR outputs, IC35 `C0` = `N$2`, IC35 `C4` =
  `N$41` = IC36 `C0`, IC36 `C4` = `N$1` (carry out). Sums `N$33..N$36`, `N$37..N$40` -> IC37 (74*244, `G` = `-ADD/SUB`) ->
  `INV-IN0..7`.
- Carry-in `N$2` = IC27A = `N$8` XOR `SUB`, `N$8` = IC6D = `ALU3` AND `C/SHIFT`. ADD (ALU3 = 0): C0 = 0; SUB: C0 = 1 (the +1
  of two's complement); ADDIC/ADDTC (ALU3 = 1, code $F): C0 = carry; a subtract-with-borrow would get C0 = NOT carry — no
  opcode uses it (`opcodes.h` has no SBC), which is why `MICROCODE-REVIEW-NOTES.md` lists SUB's borrow-into-carry as an
  emulator/microcode difference rather than a hardware one.

### 3.5 Sheet 4 — AND, OR, XOR, ZERO

Three 8-gate arrays between `ACO-DATA0..7` and `BDATA0..7`, each followed by a 74*244 onto `INV-IN`: IC18/IC19 (74*08) ->
IC20 (`G` = `-AND`); IC21/IC22 (74*32) -> IC23 (`G` = `-OR`); IC14/IC15 (74*86) -> IC17 (`G` = `-XOR`). IC16 (74*244, inputs
GND, `G` = `-ZERO`) provides the constant 0 (code 6 as a *function* — the branch code 6 is the 16-bit zero *test*; the two
uses share the ALU field but never the same step).

### 3.6 Sheet 6 — shift register

- IC29 (bits 0..3, `QA` = `SRD0`) and IC30 (bits 4..7, `QD` = `SRD7`), 74*194 universal shift registers: `S0` = `ALU0`,
  `S1` = `ALU1`, `CLK` = `SR-LD` (leading edge of `-SR-LD`), `CLR` = VCC, parallel inputs `A..D` = `ACO-DATA`. Modes
  (`CodeGen.h`): `SHIFT_LOAD` 3 = parallel load from the accumulator; `SHIFT_LEFT` 1 (S1S0 = 01: the 194 shifts QA->QD, which
  with QA = bit 0 is a shift *towards bit 7*, i.e. x2); `SHIFT_RIGHT` 2 (towards bit 0).
- Serial inputs come from IC28 (74*153, select `A` = `ALU2`, `B` = `ALU3`): `1Y` = `N$75` -> IC29 `SR` (the bit entering
  bit 0 on a shift towards bit 7): 1C0 = GND, 1C1 = `SRD7` (rotate), 1C2 = GND, 1C3 = `C/SHIFT`; `2Y` = `N$76` -> IC30 `SL`
  (the bit entering bit 7 on a shift towards bit 0): 2C0 = GND, 2C1 = `SRD0` (rotate), 2C2 = `ACO-DATA7` (arithmetic:
  propagate the sign), 2C3 = `C/SHIFT`. So `SHIFT_ZERO` 0 shifts in 0, `SHIFT_RING` 4 rotates, `SHIFT_PROP` 8 keeps bit 7,
  `SHIFT_CARRY` $C shifts the carry in.
- The cross-connection between the two halves is **not** QD -> SR / QA -> SL of the neighbouring chip but the accumulator's
  bits: IC30 `SR` = `ACO-DATA3`, IC29 `SL` = `ACO-DATA4`. This is right for the way the microcode uses the register — load
  from AC, shift exactly once, read back (`shiftOp()`, `accumulator.c`) — because at that moment the register equals AC. A
  second shift without a reload would take the wrong bit into bit 3/bit 4. `Notes.md` records the board mod behind this
  ("Should IC28 data inputs d0/d7 be connected to accumulator or shift register; 28/5 - 30-12, 28-11 - 29-15; prod has this mod").
- IC31 (74*244, `G` = `-SHIFT`): `SRD0, N$66, N$69, N$70, N$71, N$72, N$73, SRD7` -> `INV-IN0..7`: reading the register back
  is the SHIFT *function* (code 5) with `-AC-LD`.
- Shift-out flip-flop IC9B: `D` = `N$11` = IC32 `1Y` (select `ALU0`, `ALU1`: 1C1 = `SRD7` for a shift towards bit 7,
  1C2 = `SRD0` for a shift towards bit 0, 0 for load), `CLK` = `SR-LD`, `CLR` = `-RESET`. It samples the bit about to leave
  on the same edge that shifts; `SHIFT-OUT` then reaches the carry flip-flop through IC7A when the accumulator is loaded
  from the SHIFT function (`N$3` includes `-SHIFT`). Hence every one of the seven shift opcodes (SHL $B6, SHR $B7, RSHL $BD,
  RSHR $BE, PSHR $BF, CSHL $E0, CSHR $E1) loads the carry with the bit shifted out — the instruction-level emulator only did
  so for CSHx (`MICROCODE-REVIEW-NOTES.md` section 3; `y1ucemu.c` follows the hardware).

### 3.7 Sheet 5 — compare, zero detect and the branch condition

- IC24 (bits 0..3) and IC25 (bits 4..7), 74*85 magnitude comparators, `A` = `BDATA`, `B` = `ACO-DATA`; the LSB stage is
  seeded `A<B_I` = GND, `A=B_I` = VCC, `A>B_I` = GND and cascades `N$46/N$45/N$43` into IC25, whose outputs are `N$47`
  (BDATA < AC), `N$48` (equal), `N$49` (BDATA > AC). The compare is unsigned. BRLT/BREQ/BRGT/BRNEQ put TMP0 on the bus
  (`-TMP-REG-RD0`) with `-ALU-FUNC` and the card receiving, so A = TMP, B = AC: D3 (`ALULT`) = TMP > AC = "AC < TMP".
- V2 (74*4078, 8-input NOR, output `W` = `N$6`) on `BDATA0..7`: high when the low byte is 0 -> D4 and IC6B. V1 on
  `BDATA8..15` -> `N$52`; IC6B `N$55` = `N$6` AND `N$52` -> D6 (all 16 bits zero). The datasheet `docs/datasheets/744078.pdf`
  confirms pin 13 is the NOR output.
- IC26 (74*251): `A,B,C` = `ALU0..2`, `D0..D7` as in section 2, `G` = `N$4` = JP1 pin 2 (1 = `-ALU-FUNC`, 3 = GND),
  `Y` = `N$56`. IC27C: `BR-COND` = `N$56` XOR `AC-LD-INV` -> bus C24. `-AC-LD-INV` doubles as the "invert the condition" bit
  (BRNZ = BRZ inverted, BRNEQ = BREQ inverted, BRINL = BRINH inverted).
- JP1 decides whether the mux output is enabled only during `-ALU-FUNC` (pin 1) or always (pin 3). `Notes.md` 3.1: "Should
  Pin 7 of IC 26 be connected to -ALU-FUNC? Added Jumper to address either scenario". With pin 1 selected `N$56` floats
  whenever `-ALU-FUNC` is high and `BR-COND` is whatever IC27C's input reads (datapath review A1); with GND it always drives.
  The photo shows the cap at the `GND` end. **To verify** on the card.

### 3.8 Sheets 8 and 9 — spares and connectors

Spare gates with grounded inputs: IC4C/D, IC7B/C, IC27D. SV1 is a 2x5 header: pins 1..8 = `ACO-DATA0..7`, 9 = `C/SHIFT`,
10 = GND — the accumulator and carry brought out for a front panel or logic analyser. X1 is the DIN 41612 (section 2).

## 4. Timing and the review findings that concern this card

Latch edges (`MICROCODE-REVIEW-NOTES.md` 1.4 and 1.6, confirmed by the nets above):

| What | Strobe | Takes its value at | Data must be valid |
|---|---|---|---|
| Accumulator IC5 | -AC-LD | leading edge (IC1F inversion -> 374 rising CLK) | end of the previous step: function code + operand one step before `-AC-LD` (`aluOp()` in `accumulator.c` does set-up, strobe, release) |
| Carry IC9A | -AC-LD (JP2 = AC-LD) gated by add/sub/shift | same edge | same |
| Shift register IC29/IC30, shift-out IC9B | -SR-LD | leading edge | mode bits and AC before `-SR-LD` (`shiftOp()`: load step, mode step, shift step) |
| BR-COND | none (combinational) | – | the sequencer's `BR-TEST` is level-sensitive: function code and operand one step before `BR-TEST` (`branch.c` does this for every conditional branch) |

Findings and their status on 2026-09-23:

| Finding | On this card | Status |
|---|---|---|
| H-2 (microcode): BRZ/BRNZ/BR16Z/BR16NZ | the card was asked to keep driving the bus (`-AC-RD` + `-ALU-FUNC`) while the sequencer's branch register drove the target and the PC loaded: sixteen-line fight, a taken BRZ landed on offset $00 under the wired-AND rule | **fixed in the generator 2026-09-22** (`branch.c` clears `-AC-RD` before `-BRANCH-RD`), verified on `software/ucemu`, EEPROM reloaded; bench check pending |
| H-3: BR16Z/BR16NZ cannot work | D6 needs `BDATA8..15` = the operand's high byte, but with `-AC-RD` on it is RN2's $FF; the test would need a 16-bit source on the bus (a register through both byte lanes, or TMP0) with the card receiving | **open** (no user of these opcodes; the assembler accepts them) |
| A1: BR-COND floats with JP1 on -ALU-FUNC | 3.7 | configuration: JP1 on GND (photo) — **To verify** |
| A2: -AC-LD-INV also inverts BR-COND | any step with `-AC-LD-INV` and `BR-TEST` would test the inverse; the generator uses the two together only in the inverted branches, by design | note for microcode authors |
| A3: ns-scale overlaps on ACI-DATA and BDATA at strobe edges | IC2/IC3 complementary enables through one inverter; IC10 DIR flip vs IC12 turn-off | tolerated |
| M-5 (microcode): BR-TEST in the same step as the first -ALU-FUNC | JSR/JSRUR/RET/IRET/INT do it with ALU = 0 (D0 = VCC): the answer is a constant 1 whether the mux was floating or not | do not copy the pattern for a conditional |
| M-3 (microcode): INP has the slowest path in one step | the IO card's open-collector `IO-RD` rise, then IC10, IC13 into the accumulator with one set-up step | open (microcode); relevant if the clock is raised |
| Section 4 of the datapath review: accumulator/carry/borrow/carry-in, comparator seeding, shifter modes, 4078 polarity, transceiver enables | all checked against the microcode | no issue |
| Emulator mismatches: SUB loads the borrow into the carry FF; all seven shifts load the carry | hardware behaviour (3.3, 3.6) | `software/emulator` differs, `software/ucemu` follows the hardware; `BACKLOG.md` lists the emulator fix |

### 4.5 74HC, not 74LS

The photo shows 74HC parts throughout. The reviews reason in LS terms; for this card the differences are minor (rail-to-rail
levels into the CD4078BE zero detectors, which the 4000-series parts prefer; HC 245/244 drive is symmetric, so a bus fight
resolves differently from the "low wins" wired-AND of LS — `y1ucemu -F src` models the alternative). The design files and
any BOM generated from them should be corrected. **To verify:** the chip markings on the card in hand.

## 5. Jumpers, headers, LEDs, connectors — settings in the machine

`docs/system/MACHINE.md` records the card as fitted (V3.2) without jumper settings; the settings below are read from
`media/alu v3.2 top.jpeg`.

| Item | Function | Setting |
|---|---|---|
| JP1 (3 pins, silk `-ALU-FUNC` / `GND`) | IC26 output enable: 1–2 = only during `-ALU-FUNC`, 2–3 = always | photo: cap at the GND end (always enabled — the safe choice, A1); **To verify** |
| JP2 (3 pins, silk `-AC-LD` ... `AC-LD`) | carry flip-flop clock qualifier: 1–2 = `-AC-LD`, 2–3 = `AC-LD` (Notes: "should be ac-ld") | photo: cap on the pair at the `-AC-LD` silk; **To verify** which pins, and whether the carry latches at the leading or trailing edge (scope IC9 pin 3 against C22) |
| SV1 (2x5) | ACO-DATA0..7, C/SHIFT, GND — debug/front-panel header | unpopulated in the photo |
| PWR LED | R1 330 | – |
| X1 | DIN 41612 | any slot |

## 6. Bring-up and test

**How the card was proven.**

- 2020-07/08: bus-tester scripts `tests/bus-tester-scripts/ALU/{add,and,or,sub,branch,zero test}.new` — each script asserts
  `-BUS-EN`, `-ALU-FUNC`, sets `ALU0..3`, writes an operand on the data bus with `-AC-LD` pulsed, reads the accumulator back
  with `-AC-RD` and checks it (`RD-DATABUS-L:0#FE!` = expect $FE). `add.new` loads $FE, adds 1 -> $FF, adds 1 -> $00. The
  scripts are in the 2020 signal names and run through `tools/busdrv.py` or the Processing command sender. Note they drive
  the card with the CPU absent; with the logic card fitted the tester fights it (`docs/cards/sequencer-logic.md` 4).
- 2020-10: `tests/assembler/yacc1test.asm` snapshots ("ring shift test", "major test").
- 2026-09-21: `tests/assembler/ledcount` — `ADDI 1` in a loop, LEDs counting: the DATA function, the adder and the
  accumulator load, on a function-generator clock.
- 2026-09-22/23: `tests/assembler/romdiag` stages 1 (LDAI), 5/6 (BRNZ via ALUZ + `-AC-LD-INV`), 7 (ADDI $FE+1 = $FF),
  8 (MVAT/MVTA through the memory card's TMP0) and `tests/assembler/romcount` (ADDI, BRNZ, BRINL = D5 with inversion)
  running overnight from ROM.
- Not yet on the hardware (BACKLOG, "Run a compiled program on the machine"): `rt_sub` (INVA and moves between ADDTC),
  `rt_divmod` (SUBT/SUBI after a comparator branch), the shifts (`LDAI 0 / CSHL` to clear the carry), BRDEV.

**If it misbehaves — what to measure.**

1. `-ALU-IO-EN` (IC7D output) low during any `-ALU-FUNC` step with `-BUS-EN` low; DATA0..7 equal to the accumulator during
   `-AC-RD` (and DATA8..15 = $FF — that is normal).
2. The accumulator: `AC-LD` (IC1F) rising once per load; `ACO-DATA` on SV1 pins 1..8 against the expected value; if the
   value is the operand instead of the function result, IC8's select (`ALU0..2` on C16..C18) or the function buffer enable.
3. Carry: `C/SHIFT` on SV1 pin 9 after `LDAI $FF / ADDI 1` (expect 1) and after `ANDI` (unchanged); if it toggles on logic
   ops, `N$3` (IC4A) is not gating; if it never sets, JP2 / `N$5`.
4. Branches: `BR-COND` (C24) at the sequencer's `BR-TEST` for `LDAI 0` + BRZ (expect 1) and BRNZ (expect 0); a floating
   level here with JP1 on pin 1 is A1. For BREQ/BRLT/BRGT put TMP0 = AC and check D2 (IC25 `A=B_O`).
5. Comparator seeding: IC24 pins `A<B_I` = 0, `A=B_I` = 1, `A>B_I` = 0 — a lifted pin gives "never equal".
6. Shifts: after `LDAI $80 / SHL` expect AC = $00 and carry = 1; `RSHL` expect $01; `PSHR` of $80 expect $C0.
7. The 16-bit zero test: with `-AC-RD` off and TMP0 = $0000 on the bus, `N$55` (IC6B) high; with `-AC-RD` on it can never
   be (H-3).

## 7. Revision history and what the next revision should change

| Revision | Date (PROVENANCE) | What | Source |
|---|---|---|---|
| gen-1 ALU-PROD-V1.0 | 2016 | the 2016 machine's ALU | `archive/gen1-2015-2018/` |
| V3.0 (2-layer, "alu4") | 2020-06-13/14 | first 2020 ALU; sent to fab without the outline file, "should have been a 4 layer board", mask reads V1.0, VCC/GND problem ("SCRAP. ARGh no vcc and gnd"); IN/OUT changed to active high on the bus | `eagle/deprecated/v3.0-2layer/Notes.md` |
| V3.1, V3.1-resubmit, V3.1-buried-vias | 2020-07-07/08 | IN/OUT active high in the schematic; `-VMA` marked unused; JP1 added for the IC26 enable question; three fab variants (buried vias, a resubmit without) | `eagle/deprecated/v3.1*/Notes.md` |
| V3.2 | 2020-11-29 | IC32 pins 4/5 flipped; AC and BDATA swapped in the add/sub circuit (BDATA into the XOR array, AC into the adders); CO/BO gated with `-ADD/SUB`; JP2 for the carry clock (`-AC-LD` or `AC-LD`); IC10 DIR driven from `-AC-RD` (a board mod on 3.1, done in 3.2); the shift-register D0/D7 mod (28/5–30/12, 28/11–29/15) carried into production; net names re-saved to Bus V3.2 | `eagle/v3.2/Notes.md`, `hardware/FABRICATED.md`; **in the machine** |
| "ALU-V3.3" folder | – | the V3.2 design with the bus ribbon label reverted, nothing else (`NEWER-DESIGNS-vs-ACTIVE.txt`: 0 differences); folded away 2026-09-20 | README |
| ALU-V3.3-16 | 2021-09 | a 16-bit ALU experiment with its own assembler/emulator; deleted from this tree 2026-09-20 on Ken's instruction ("useless"), still in YACCS | README |

`Notes.md` items still open: "Retest Shift register functionality", "Retest Carry/Shift register", "How to clear carry
shift? - ADD INSTRUCTION" (the compiler uses `LDAI 0 / CSHL`, `BACKLOG.md`), "Test SUBT".

**A V3.3 (never started) should:**

1. Fix JP1's answer in copper: enable IC26 permanently (or qualify `BR-COND` with `-ALU-FUNC` on the sequencer side) so the
   condition line never floats (A1).
2. Separate the condition inversion from `-AC-LD-INV` (A2) — a spare pipeline bit exists (`SPARE3`).
3. Give the 16-bit zero test a way to see a 16-bit operand while the card receives (H-3), or drop BR16Z/BR16NZ from the
   opcode table.
4. Cascade the shifter halves from the register (IC29 QD -> IC30 SR, IC30 QA -> IC29 SL) so that multi-step shifts are
   possible, or document the load-shift-read rule on the schematic.
5. Add a subtract-with-borrow path (C0 = NOT carry for SUB with ALU3) if the compiler ever needs it (`rt_sub` uses INVA
   and ADDTC instead).
6. Correct the design files to the fitted 74HC parts; give C21 a proper value.

Related documents: `docs/cards/sequencer-logic.md` (the strobes' origin and the BR-TEST latch), `docs/cards/register.md`
(operands from the index registers), `docs/isa/MICROCODE-REVIEW-NOTES.md` (per-opcode step lists), `docs/isa/*.svg`
(timing diagrams).
