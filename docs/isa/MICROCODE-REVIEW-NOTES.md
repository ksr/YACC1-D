# Microcode review notes — every opcode against the hardware (2026-09-21)

Reviewer: Claude (Fable 5.1), working from the tree only; nothing was run on the machine and the microcode was not modified.

Inputs: `docs/isa/steps.txt` (all 218 records, every step), `docs/isa/MICROCODE-REVIEW.md` (the mechanical pass),
`firmware/microcode/ucode-generator2/*.c` (intent), `firmware/microcode/yaccsignaldata2.h`, `software/emulator/main.c`
(reference semantics), `software/assembler/yacc1.def`, `firmware/monitor/monitor.asm`, `firmware/basic/basic.asm`, and the
KiCad netlists of the cards in the machine: `hardware/cards/{register/v1.1, alu/v3.2, memory/v1.3, sequencer-logic/v2.1,
io/v1.1}/kicad/*/reports/netlist.net` (plus the Eagle `.sch` of the sequencer for one cross-check). Pin numbers below are
from those netlists; "IC7" means the chip on the card being discussed.

The document is long on purpose: section 1 explains the hardware model the findings depend on, so each finding can be
re-derived (and challenged) from the netlists rather than taken on trust.

Contents: 1 hardware model · 2 findings (HIGH / MED / LOW) · 3 per-opcode check against the emulator · 4 checked, no issue ·
5 cycle-savings table · 6 corrections to the mechanical pass and the timing-diagram model · 7 bench confirmations · 8 summary.

---

**Status 2026-09-22 (evening):** H-1 and H-2 were reproduced on the microcode-level emulator `software/ucemu` (PUSHR $ABCD
pushed $21CC; a taken BRZ landed on offset $00 and the monitor could not print a string) and FIXED in the generator
(`branch.c`); the regenerated `test.hex` runs the monitor, the compiler suite and `tests/ucemu/isa.asm` with 0 bus fights.
The sequencer EEPROM was reloaded with it the same evening (`tools/ucode_send.py --all`). H-3 (BR16Z/NZ) stands; the emulator reproduces it too.

## 1. What the hardware actually does (the model behind every finding)

### 1.1 Sequencer: one microcode step = two clock periods, and step 0 is shared with the previous opcode

Sequencer-logic v2.1 (`hardware/cards/sequencer-logic/kicad/v2.1/reports/netlist.net`):

- The gated clock `N$4` (IC38 pin 6 = oscillator/single-step clock AND `RUN` AND not-halted) drives the UP input of an 8-bit
  74LS192 counter (IC33 → IC34). Its bit 0 (IC33 QA) becomes `CNT-CLK`; bits 1..6 become `CADDR0..5` (the 64-step address
  into the sequencer-memory card); bit 7 is `COUNT-FAULT`, which stops the clock (IC26 pin 11 → IC31 → IC38 pin 1).
- The pipeline registers (74LS374 IC7, IC12, IC14, IC16, IC17, IC19, IC20, IC28) are clocked by `BUS-LATCH-CLK` =
  `CNT-CLK` (IC25 pin 11; the other OR input `N$32` is a constant 0: IC32 pin 10 = NOR(RESET, NOT RESET)). So the control
  word for step k is latched when the counter goes from 2k to 2k+1, i.e. **each step lasts two clock periods, and the
  memory card has one clock period to deliver the next word after `CADDR` changes**.
- `UCODE-COUNT-RESET` (IC17 pin 16) is ANDed with the clock (IC27 pins 4,5 → 6) and ORed with `RESET` into the counters'
  asynchronous CLR (IC26 pin 3 → IC33/IC34 pin 14). Consequence: the step that carries `UCODE-COUNT-RESET` lasts only ONE
  clock period (the counter is cleared during the first clock-high of that step), and step 0 of the next instruction then
  lasts three (the counter is cleared once more at the next clock edge while the pipeline still holds the reset word; step 0
  is latched from a ~50 ns pulse on QA — it works, but it is a race, see finding M-8). Every signal asserted in the reset
  step is therefore active for half a step.
- The instruction register is two 74LS175 (IC8, IC9) clocked by `LD-INS-REG1` = `LD-INS-REG` AND `RUN` (IC24 pin 3):
  **the IR latches on the leading (rising) edge of `LD-INS-REG`**, i.e. at the start of the step that asserts it. Its D
  inputs come from IC2 (DATA0..7, enabled while `DO-INT` is low) or IC1 (all VCC = $FF, enabled while `DO-INT` is high):
  that is how an interrupt substitutes opcode $FF (INT).
- The IR feeds `CADDR6..13` through IC15. Because the IR changes ~50 ns into the `LD-INS-REG` step and the next pipeline
  latch reads ROM[new opcode, next step], **steps 0, 1 and 2 of every record are executed with the PREVIOUS opcode in the
  IR** (they come from the previous instruction's record), and the fetched opcode's own record takes over at step 3. The
  generator makes steps 0..5 identical in all records (`startInstruction` + `loadNextInstruction`), which is why this works
  and why record $00 (START) is the reset vector: RESET clears the IR (IC8/IC9 CLR) and the index registers.
- Operand register: 74LS374 IC6, clocked by `OPERAND-CLK` (leading edge). With `-2-BYTE-OPERAND-SEL` asserted, IC5 drives
  `REG-RD-ID0..3` = operand bits 0..3 and `REG-LD-ID0..3` = operand bits 4..7 onto the bus instead of the pipeline's fields
  (IC4, enabled by the inverse `-ONE-OPERAND-SEL`). This matches `yacc1.def`: MOVRR byte = (dst<<4)|src, PUSHR/JSRUR use the
  low nibble, POPR uses `reg<<4`.
- Branch register: two 74LS374, IC13 (D = DATA0..7, Q = DATA8..15, clocked by `BRANCH-LD-HI`) and IC21 (DATA0..7, clocked
  by `BRANCH-LD-LO`), both output-enabled by `-BRANCH-RD`. **Both latch on the leading edge of their strobe, and `-BRANCH-RD`
  drives all 16 data lines.** The interrupt vector is the same structure: IC3 (hi, `INT-LD-HI`) and IC10 (lo, `INT-LD-LO`),
  output-enabled by `-INT-JMP`, loaded by IADDR from DATA0..7 one byte at a time.
- Branch-condition latch (the V2.1 "SR flip-flop"): `N$71` = ((`BR-TEST` AND `BR-COND`) OR `N$71`) AND NOT `UCODE-COUNT-RESET`
  (IC27 pin 3, IC26 pin 8, IC37 pins 4/6, IC30 pin 3). Level-sensitive: any high on `BR-COND` while `BR-TEST` is high sets it;
  it is cleared only at the end of the instruction.
- **Loads of the PC are gated by that latch.** The bus signals `-REG-LD-LO` / `-REG-LD-HI` are IC31 pins 10/12 =
  NOT(`N$53` AND `LREG-LD-LO/HI`), with `N$53` = (`REG-LD-ID` != 0) OR branch-taken (IC25 pins 3/8, IC30 pins 11/6). So a
  load whose target is register 0 reaches the register card only after a `BR-TEST` that found `BR-COND` true in the same
  instruction. This is how a not-taken conditional branch leaves the PC alone — and it also means MVIB R0, MVIW R0,
  MVARL/MVARH R0, MOVRR ..,R0, POPR R0 and LDR R0 silently do not load (section 3).
- Interrupts: `INT-EN` sets and `INT-START`/`RESET` clear a NOR latch (IC22 pins 1/4 = interrupts enabled); `INT-START` also
  clears the pending-interrupt flip-flop IC23A (CLR = NOT(INT-START OR RESET), IC36 pin 4). `DO-INT` = pending AND enabled
  (IC24 pin 8). `-INTA` is pipelined to the bus (IC17 pin 2) but no record ever asserts it. The `-SRC-ADDR`/`-DEST-ADDR`/`SPARE3`
  bits in the signal table are NOT wired to the microcode memory: their pipeline D inputs come from jumper JP1 (pins 3, 4, 1).
- `-BUS-EN` on the sequencer = NOT(`READY`) from the memory half (IC36 pin 8): all pipeline outputs are tri-stated until the
  ATmega reports the image loaded.
- `SOFT-HALT` clocks IC23B (`DO-HALT`) at its leading edge, stopping the clock in the step that asserts it; the front-panel
  CONT clears it and the record continues from the same step.

### 1.2 Register card: what -REG-FUNC-RD, -REG-RD-LO/HI, -HL-SWAP, -REG-UP/DN and -REG-LD-* really do

Register card 1.1 (`hardware/cards/register/kicad/v1.1/reports/netlist.net`), four 16-bit registers per card, each = four
74LS192 (e.g. R0 = IC3..IC6, low byte IC3/IC4, high byte IC5/IC6), two 74LS244 read buffers onto the card's internal 16-bit
bus `ADATA0..15` (R0: IC7 low byte, IC8 high byte), two 74LS244 address buffers onto `ADDR0..15` (R0: IC41, IC42), and three
shared 74LS245 transceivers between the internal bus and the backplane: IC35 (DATA0..7 ↔ ADATA0..7), IC36 (DATA8..15 ↔
ADATA8..15) and IC37 (DATA0..7 ↔ ADATA8..15, the byte-swap path). `ADATA` has 10k pull-ups (RN1/RN2 pin 1 = VCC).

- Card select for reads: `-RDSEL` (jumper J1) = `-REG-FUNC-RD` AND `-BUS-EN` AND (`REG-RD-ID3..2` == this card) (IC31 pin 3,
  IC32 half A). `-LDSEL` likewise from `-REG-FUNC-LD` and `REG-LD-ID3..2`. Register select inside the card: IC33 decodes
  `REG-RD-ID1..0` → `-Rn-RDSEL`, `REG-LD-ID1..0` → `-Rn-LDSEL`.
- **Read strobes select byte LANES, not a shared byte:** IC2 pin 3 = `-R0-RDSEL` OR `-REG-RD-LO` enables IC7 (R0 low byte →
  ADATA0..7); IC2 pin 6 = `-R0-RDSEL` OR `-REG-RD-HI` enables IC8 (R0 high byte → ADATA8..15). Without `-HL-SWAP` the low byte
  reaches DATA0..7 through IC35 and the high byte reaches DATA8..15 through IC36. With `-HL-SWAP` only IC37 is enabled, so
  the high byte reaches DATA0..7 (and the low byte stays inside the card). **`-REG-RD-LO` together with `-REG-RD-HI` is a
  16-bit transfer, not a bus fight** (the mechanical pass's R2 rule assumed an 8-bit bus).
- **Transceiver enable does not depend on the read strobes.** IC34 (4077 XNOR): `N$42` = XNOR(`-RDSEL`, `-LDSEL`),
  `N$41` = NOT(`-HL-SWAP`), `BUS-DIR` = NOT(`-LDSEL`). IC31 pin 8 = `N$41` OR `N$42` enables IC35+IC36; IC31 pin 11 = `N$42` OR
  `-HL-SWAP` enables IC37. So the straight transceivers are open whenever exactly one of RDSEL/LDSEL is active for the card and
  `-HL-SWAP` is off; the swap transceiver whenever exactly one is active and `-HL-SWAP` is on. Direction: `BUS-DIR` high (LDSEL
  active) = bus → card; low = card → bus. **Therefore `-REG-FUNC-RD` alone (as in every increment/decrement step) puts the
  card's internal bus onto DATA0..15 — with no read buffer enabled that is the pull-up value $FFFF, driven actively by two
  LS245s.** When both RDSEL and LDSEL select the same card (MOVRR between two registers of one card) the transceivers close
  and the copy happens on ADATA internally; that is the intended use of the XNOR.
- Count: IC1 pin 3 = `-R0-RDSEL` OR `-REG-UP` → IC3 UP; IC1 pin 6 = `-R0-RDSEL` OR `-REG-DN` → IC3 DN (carry/borrow chained
  through IC4..IC6). A 74LS192 counts on the LOW→HIGH edge of UP (or DN) while the other input is high. **The count happens at
  the trailing edge of `-REG-UP`/`-REG-DN` — or at any moment the card/register is deselected while the strobe is still low
  (a rising edge of the OR output).** The generator's `decrementReg()` writes a select-only step before asserting `-REG-DN`;
  `incrementReg()` does not, so an increment whose previous step selected a different register with `-REG-FUNC-RD` would clock
  the old register (checked: no record does this today, see 4).
- Load: IC1 pin 8 = `-R0-LDSEL` OR `-REG-LD-LO` → IC3/IC4 LOAD (low byte); IC1 pin 11 = `-R0-LDSEL` OR `-REG-LD-HI` → IC5/IC6 LOAD.
  74LS192 LOAD is asynchronous and level-sensitive: the outputs follow ADATA while LOAD is low and keep the value present at
  its rising edge. **Register loads take effect at the trailing edge of the strobe and need ADATA stable through the whole
  strobe step.** (The 2020 diagrams in `docs/system/waveforms/` show exactly this.)
- Address: IC38 (74LS139) decodes `ADDR-REG-ID`; its enable is `-BUS-EN` OR `-VMA` (IC40 pin 3), so the address buffers drive
  `ADDR0..15` only while `-VMA` is asserted — the generator asserts `-VMA` in every step ("Hack prevent ROM mapping from
  triggering"), so the address bus is always driven by the selected register.

### 1.3 Memory card: TMP registers live here; write timing

Memory v1.3 (`hardware/cards/memory/kicad/v1.3/reports/netlist.net`):

- TMP0 = IC26 (DATA0..7) + IC27 (DATA8..15), TMP1 = IC28 + IC29, all 74LS374 with D and Q on the same bus lines, output-enabled
  by `-TMP-REG-RD0/1` (pin 1) and clocked by `-TMP-REG-LD0/1` through inverter IC14 (pins 2, 12): **TMP registers latch on the
  leading edge of `-TMP-REG-LDx` and are 16 bits wide; reads drive all 16 data lines.**
- `-MEM-RD` sets the direction of the data transceiver IC5 (DIR pin 1; G = `-VMA`) and, doubly inverted (IC6 pins 6, 2), the
  RAM/ROM `-OE`. `-MEM-WR` doubly inverted (IC6 pins 8, 4) is the `-WE` of both 62256 and the 28C64; chip selects are
  address-decoded and gated by `-VMA` (IC10 pin 3, IC7 pin 4). A 62256 write is WE-controlled: data is taken at the rising edge
  of `-WE`, the address must not change while `-CS` and `-WE` are both low. **The data source must be valid before the end of
  the `-MEM-WR` step and the address stable through it** (the generator's `putBustoRegMem` satisfies both: one set-up step,
  one strobe step, one hold step).
- Boot remap: `FORCE-ROM` (IC12) is cleared by the first bus cycle with ADDR15 high while `-VMA`/`-BUS-EN` are asserted (IC10 pin 8).

### 1.4 ALU card: the accumulator latches on the leading edge, and -AC-RD drives all 16 data lines

ALU v3.2 (`hardware/cards/alu/kicad/v3.2/reports/netlist.net`):

- Bus transceivers IC10 (DATA0..7 ↔ BDATA0..7) and IC11 (DATA8..15 ↔ BDATA8..15) are enabled by `-ALU-FUNC` OR `-BUS-EN`
  (IC7 pin 11) and pointed by `-AC-RD` (DIR pin 1): `-AC-RD` asserted = card → bus. The accumulator output reaches BDATA through
  IC12 (enabled by `-AC-RD`). BDATA8..15 has only pull-ups (RN2) and the 16-bit-zero NOR (V1). **So whenever `-ALU-FUNC` and
  `-AC-RD` are both asserted the ALU drives DATA0..7 = AC and DATA8..15 = $FF.** Without `-AC-RD` the transceivers receive
  (bus → BDATA), which is how operands from memory/TMP/registers reach the function blocks.
- Function select: 74LS138 IC8 decodes `ALU0..2` into one enabled 74LS244 onto `INV-IN0..7`: 0 DATA (IC13), 1 SUB, 2 AND (IC20),
  3 OR (IC23), 4 XOR (IC17), 5 SHIFT (IC31 = shift-register outputs), 6 ZERO (IC16, inputs grounded), 7 ADD (IC37 = adder sum;
  IC37 is enabled for both ADD and SUB via `-ADD/SUB`). `ALU3` with the ADD/SUB code adds the carry flip-flop into the adder's
  C0 (IC6 pin 11 → IC27 pin 3 XOR SUB → IC35 pin 7).
- Accumulator: 74LS374 IC5 clocked by `AC-LD` = NOT(`-AC-LD`) (IC1 pin 12) through JP2: **the accumulator latches on the leading
  edge of `-AC-LD`.** Its D inputs are INV-IN through IC3 (non-inverting, enabled when `-AC-LD-INV` is inactive) or IC2
  (inverting, enabled when `-AC-LD-INV` is asserted).
- Carry flip-flop IC9A is clocked by (ADD/SUB or SHIFT function active) AND `AC-LD` (IC4 pin 3 → IC6 pin 8): it loads
  `CO/BO` OR `SHIFT-OUT` at the same leading edge as the accumulator. `CO/BO` = adder carry XOR SUB, gated to add/sub only
  (IC1 pin 10). `SHIFT-OUT` (IC9B) is captured at each `-SR-LD` leading edge from the bit about to leave the 74LS194 pair
  (IC32 mux: SRD7 for left shifts, SRD0 for right shifts, 0 for the parallel load).
- Shift register: 74LS194 IC29/IC30, mode S1S0 = ALU1,ALU0 (11 = parallel load from AC, 01 = towards bit 7, 10 = towards
  bit 0), clocked by `SR-LD` = NOT(`-SR-LD`) (leading edge). Serial inputs from IC28 by ALU3,ALU2: 00 zero, 01 the opposite end
  (rotate), 10 bit 7 (arithmetic right), 11 the carry flip-flop.
- Branch condition: 74LS251 IC26, select = ALU2..0: D0 = VCC (unconditional), D1 = BDATA<AC (BRGT), D2 = BDATA==AC (BREQ),
  D3 = BDATA>AC (BRLT), D4 = BDATA0..7 == 0 (BRZ, needs `-AC-RD` so BDATA = AC), D5 = `IN`, D6 = (BDATA0..7 == 0) AND
  (BDATA8..15 == 0), D7 = carry. Output XOR `AC-LD-INV` (IC27 pin 8) = `BR-COND`. The mux's output enable is jumper JP1
  (either `-ALU-FUNC` or always on).

### 1.5 I/O card

I/O v1.1: `-IO-ADDR-LD` reaches nothing but the connector (net has one node); the port is decoded combinationally from
`IO-ADDR0..3` (74LS138 IC5, IO-ADDR3 through the IO-ADDR-HL jumper). `-IO-WR`/`-IO-RD` are inverted by open-collector 7406
IC8 into `IO-WR`/`IO-RD` with pull-ups (RN2, value unknown): the switch/LED latch (74LS273 IC4) and the control latch (IC10)
clock on the trailing edge of `-IO-WR` (NAND of `IO-WR` falling), the switch buffer IC3 and the 16550 drive the bus while
`-IO-RD` is low. The open-collector rise after `-IO-RD` asserts is RC-limited (pull-up × bus capacitance), the slowest
edge in the machine.

### 1.6 Latch-edge summary (this is what the timing model in `tools/ucode_wavedrom.py` gets wrong)

| Destination | Strobe | Takes the value at | Data must be valid |
|---|---|---|---|
| Instruction register (seq. IC8/IC9) | LD-INS-REG | leading edge | before the strobe step starts |
| Operand register (seq. IC6) | OPERAND-CLK | leading edge | before |
| Branch register hi/lo (seq. IC13/IC21) | BRANCH-LD-HI/LO | leading edge | before |
| INT vector hi/lo (seq. IC3/IC10) | INT-LD-HI/LO | leading edge | before |
| TMP0 / TMP1 (mem. IC26..29) | -TMP-REG-LD0/1 | leading edge | before |
| Accumulator, carry FF (ALU IC5, IC9A) | -AC-LD | leading edge | before |
| Shift register, shift-out FF (ALU IC29/30, IC9B) | -SR-LD | leading edge | before |
| Index register byte (74LS192 LOAD) | -REG-LD-LO/HI (+FUNC-LD) | trailing edge, level-sensitive | through the whole strobe step |
| Index register count (74LS192 UP/DN) | -REG-UP/-REG-DN (+FUNC-RD) | trailing edge (rising edge of the OR with the select) | select must not change while the strobe is low |
| RAM/EEPROM write | -MEM-WR | trailing edge (`-WE` rising) | through the strobe step; address stable |
| I/O latches (io IC4/IC10) | -IO-WR | trailing edge | through the strobe step |
| Branch-taken latch (seq. N$71) | BR-TEST | level (any high sets) | BR-COND stable through the BR-TEST step |
| Step counter clear | UCODE-COUNT-RESET | first clock-high of the step | the step lasts one clock period |

---

## 2. Findings

Severity: HIGH = wrong result or bus fight; MED = timing-marginal or electrically abusive without a wrong result today;
LOW = speed / cleanliness / documentation. "Confirm" = how to see it with the bus tester (single-stepping the sequencer with
`-BUS-EN` and logging the bus; scripts in `tests/bus-tester-scripts/`, driver `tools/busdrv.py`) or a scope.

### HIGH

**H-1 PUSHR ($07): both stack writes happen during a data-bus fight — the pushed word is corrupted.**
Steps (PUSHR record, `steps.txt`):
- 13..17: `-REG-FUNC-RD, -REG-RD-HI, -HL-SWAP` stay asserted after `-2-BYTE-OPERAND-SEL` is released (step 13), so
  `REG-RD-ID` falls back to the pipeline field = 0 and the register card drives **PC.hi onto DATA0..7** through the swap
  transceiver (1.2). In the same steps 14..16 `-TMP-REG-RD1` drives TMP1 (the register's high byte, captured at step 11) onto
  DATA0..15, and `-MEM-WR` is asserted at step 15. Two LS drivers (register IC37 vs memory IC28) on DATA0..7 during the write.
- 24..28: `-REG-FUNC-RD, -REG-RD-LO, -REG-RD-HI` stay asserted after the second `-2-BYTE-OPERAND-SEL` release, now with
  `REG-RD-ID` = 1 (left by `decrementReg(SP)`): the register card drives **SP.lo on DATA0..7 and SP.hi on DATA8..15** while
  `-TMP-REG-RD1` drives the register's low byte (TMP1 lo) and its stale high byte (TMP1 hi) on the same lines; `-MEM-WR` at
  step 26. Sixteen-line fight during the write.
Generator cause (`branch.c`, PUSHR): the strobes set before `putBustoRegMem(SP, "-TMP-REG-RD1")` are never cleared, and
`-REG-RD-HI` is never cleared at all. Failure: the byte written is roughly (register byte AND PC.hi) for the high byte and
(register byte AND SP byte) for the low byte — a wired-AND of LS outputs, exact value depends on drive strengths. Every
POPR of that word then returns garbage. PUSHR is used 4× in the monitor and 34× in BASIC.
Fix (microcode only): clear `-REG-RD-HI`/`-REG-RD-LO`/`-REG-FUNC-RD` before each `putBustoRegMem`; or drop the TMP1 detour and
write the register straight from the card (as JSR does with PC), which also shortens the record (section 5).
Confirm: SP = $001F (Mem Register RAM), R3 = $A55A, single-step `PUSHR R3`; at steps 15 and 26 log DATA0..7 while both
`-REG-RD-*` and `-TMP-REG-RD1` are low (expect neither $A5 nor $5A, and a mid-level on a scope); read back $001F/$001E.

**H-2 BRZ ($A1), BRNZ ($A2), BR16Z ($AB), BR16NZ ($AC): the ALU keeps driving the data bus while the branch register is
copied into the PC.** Steps 16..20: `-AC-RD` (set at step 13 for the condition test) is still asserted with `-ALU-FUNC`, so
the ALU drives DATA0..7 = AC and DATA8..15 = $FF (1.4) while `-BRANCH-RD` drives the 16-bit target and `REG-LD-LO/HI` load the
PC at step 18 (trailing edge). Sixteen-line fight between the ALU's LS245s and the sequencer's LS374s during the load.
Failure: taken BRZ (AC = 0 by definition) loads PC.lo = target.lo AND $00 = $00 — every taken BRZ lands on the wrong page
offset; taken BRNZ loads PC.lo = target.lo AND AC. The generator (`branch.c`, `branch()`) clears `-TMP-REG-RD0` before
`-BRANCH-RD` for the TMP-sourced branches ("problem will conflict with data transfer of branch reg to PC") but never clears
`-AC-RD` for the AC-sourced ones. BRNZ is used 29× in the monitor and 17× in BASIC, BRZ 4×/11×.
Fix: `clearSignal("-AC-RD")` where `-TMP-REG-RD0` is cleared (the condition latch is already set at step 14).
Confirm: AC = 0, `BRZ $000C` from the switch ROM; single-step; at steps 16..18 DATA0..7 should read $0C but will read ~$00;
the next fetch address on ADDR0..15 shows where the PC went. Repeat BRNZ with AC = $0F vs $F0 and target $0F.

**H-3 BR16Z/BR16NZ can never work as microcoded, independent of H-2.** The 16-bit-zero condition (IC26 D6) needs BDATA8..15
to be the operand's high byte, but with `-AC-RD` asserted BDATA8..15 is the pull-up value $FF (1.4): BR16Z never branches,
BR16NZ always branches. The emulator marks both `badOpcode`; the assembler accepts them; neither the monitor nor BASIC uses
them. To be meaningful they would need the 16-bit operand on the bus (a register via `-REG-RD-LO`+`-REG-RD-HI`, or TMP0) with
the ALU receiving (no `-AC-RD`). Severity HIGH by the rules (wrong result), impact nil today.

**H-4 38 opcodes have all-zero records, and an all-zero control word asserts every active-low signal at once.** Records
$80..$8F (OUTVR), $A5, $AD, $AE, $C0..$CF (LDTVR/STTVR), $F8..$FA hold zeros in `test.hex` (the generator never writes them;
`test.hexz`, what the loader sends, zero-fills too). The signal table stores active-low signals as 1 = inactive, so a zero
word asserts `-REG-FUNC-RD, -REG-FUNC-LD, -REG-RD-LO/HI, -REG-UP, -REG-DN, -MEM-RD, -MEM-WR, -IO-RD, -IO-WR, -TMP-REG-RD0/1,
-TMP-REG-LD0/1, -ALU-FUNC, -AC-LD-INV, -AC-RD, -AC-LD, -SR-LD, -HL-SWAP, -BRANCH-RD, -INT-JMP, -2-BYTE-OPERAND-SEL, -INTA`
simultaneously (and `-VMA`). When such an opcode is fetched, steps 3..63 of that record run: memory write-with-read-enabled
at [PC] with five sources fighting for the bus, TMP0/TMP1/AC/shift register clobbered, both counter clocks held low, for 61
steps until `COUNT-FAULT` stops the clock — and the halted pipeline then holds that word until reset. The mechanical pass
skipped these records ("all 256 records that hold microcode"), so its E1 rule never saw them. The assembler will emit
OUTVR/LDTVR/STTVR if asked (`yacc1.def` has the syntax) and the emulator implements LDTVR/STTVR, so a program that runs on the
emulator can do this on the hardware. Neither the monitor nor BASIC uses them (mnemonic counts, section 3). Fix in the
generator: fill every unwritten record with the idle word (initCurrentLine) plus `UCODE-COUNT-RESET` at step 3 (illegal
opcode = 1-byte NOP), or with `SOFT-HALT`.
Confirm: put $80 in the switch ROM; expect the COUNT-FAULT halt with all strobes low on the bus tester's monitor.

**H-5 (hardware, raised by the review — verify on the board) Sequencer IC11 gate B permanently drives ADDR-REG-ID0..3 low.**
Netlist and Eagle schematic agree: IC11 (74LS244) gate B has G, A1..A4 all on GND and Y1..Y4 on `ADDR-REG-ID0..3`; IC18 gate B
(enabled whenever `-2-BYTE-OPERAND-SEL` is inactive) drives the pipeline's `LADDR-REG-ID0..3` onto the same nets. IC11 is in
the BOM. If the board is built as drawn, every step with `ADDR-REG-ID` != 0 (all SP-, IR- and Rn-relative accesses: JSR, RET,
PUSH*, POP*, LDA/STA/LDT/STT, LDR/STR, LDAVR/STAVR, LDIVR, BRVR) is a two-driver fight on those select lines, resolved at
~1 V by drive strength. The 2026-09-21 bring-up program (`tests/assembler/ledcount`) uses only PC-relative addressing, so it
would not have shown this. Out of scope for the microcode but it decides whether any of the above instructions can work.
Confirm: scope bus pin C3 (`ADDR-REG-ID0`) during a single-stepped `PUSH` (steps 7..9): a clean TTL high means the board
differs from the drawing (IC11 not fitted or gate B unpowered); ~0.5..1.5 V means the contention is real.

### MED

**M-1 `-REG-FUNC-RD` without read strobes puts $FFFF on the data bus, and 327 steps do that while memory also drives.**
Per 1.2 the register card's transceivers open on RDSEL alone. Every record's fetch step 4 (`-REG-FUNC-RD, -REG-UP, -MEM-RD`)
and every operand increment that keeps `-MEM-RD` asserted (LDAI/ADDI/SUBI/ORI/ANDI/XORI/ADDIC step 9, MVIB 9, MVIW 9 and 14,
LDTI 8, JSR 7, BR-family 7 and 10, BRVR 8 and 11, LDA/STA/LDT/STT 9, STR 10, LDR 9 and 23, IADDR 8 and 12, RET 11, IRET 11,
POPR 20) has the memory card's LS245 driving data against the register card's LS245s driving high — 8 outputs shorted for one
step per fetch. Functionally harmless today because nothing latches the bus in those steps (IR latched at step 2, AC at 7,
register loads ended before), but it is a sustained short-circuit condition on LS outputs and a supply-noise source on every
instruction. Fix in microcode: release `-MEM-RD` before `-REG-UP` (the IR and all leading-edge latches have their data
already; the level loads have ended) — in `loadNextInstruction` move `clearSignal("-MEM-RD")` before `incrementReg(PC)`, and do
the same in `branch()`, `LDTI`, the immediate ALU ops, etc. JSR step 10 and OUTI step 10 already do it right.
Confirm: scope DATA0 during fetch step 4 of any instruction whose opcode has bit 0 = 0 while the register card is fitted:
a level around 0.5..1.5 V instead of a clean low.

**M-2 One microcode step of memory access before a leading-edge latch (address changed in the previous step).**
With the edges in 1.6 these loads capture data one step after the address became valid:
LDTI step 6 (`-TMP-REG-LD0`, PC incremented at the end of step 4, `-MEM-RD` from 5); LDIVR step 6 (`-TMP-REG-LD1`); LDT step 18
(`-TMP-REG-LD0`, IR first on the address bus at 17); BRANCH-LD-HI/LO in BR, BRZ..BRDEV (steps 6/9), JSR (6/9), RET (9/13),
IRET (9/13), BRVR (7/10; 6/9 for R0); INT-LD-HI/LO in IADDR (6/10). Budget per step (two clock periods): register select
+ address buffer (~40 ns) + 28C64 address access (150..250 ns for the monitor/BASIC in ROM) + memory LS245 (~12 ns) + 374 set-up
(~20 ns) ≈ 230..320 ns, i.e. a clock faster than ~6 MHz makes these the first instructions to fail. The `-AC-LD` cases (LDAI,
ADDI.., LDAVR, POP, LDA) have two steps and are fine. The oscillator value is not in the tree (BOM: "XO-14, unknown"), so
this is a rule for whoever picks the clock rather than a present fault. Fix costs nothing: because the count is a trailing-edge
event and the latch a leading-edge one, the strobe can move one step later and share the step with the following increment.
Confirm: raise the clock until BR stops landing on its target; the first byte to go wrong is the operand latched with one
step of access.

**M-3 INP ($90..$9F) has the slowest path in the machine in one step.** Step 8 asserts `-IO-RD`, step 9 latches the AC
(leading edge). `-IO-RD` becomes `IO-RD` through an open-collector 7406 whose rising edge is an RC (pull-up RN2 × bus
capacitance), then the NAND enable, the 74LS244/16550 output, the ALU transceiver and two function buffers. With a 10k pull-up
this alone is several hundred ns. Same edge feeds the 16550's IOR for the UART reads the monitor depends on. Give INP two set-up
steps or a stronger pull-up; the same OC edge on `IO-WR` is harmless because the write latches on the (fast) falling edge.

**M-4 PUSHR steps 17→18 and STR steps 21→22 change the register driving the bus while its read strobe stays asserted.**
PUSHR step 18 changes `REG-RD-ID` 0→1 with `-REG-RD-HI` and `-HL-SWAP` still on (PC.hi → SP.hi on DATA0..7); STR step 22 keeps
`-REG-FUNC-RD` with the ID switched to IR after the high-byte write. Same-card source switch (one 74LS139 output falling, one
rising), so at most a few ns of overlap — not a fight, but neither is intended, and both are symptoms of the never-cleared
strobes in H-1/M-1.

**M-5 The condition latch is level-sensitive and `BR-COND` is not guaranteed stable when the 251 is disabled.** JP1 on the ALU
lets the condition mux output enable follow `-ALU-FUNC`; JSR/JSRUR/RET/IRET/INT assert `BR-TEST` in the very step `-ALU-FUNC`
first appears (JSR 26, JSRUR 28, RET 16, IRET 16, INT 25), so `BR-COND` is a floating-then-driven line during the BR-TEST step.
With ALU = 0 the driven value is 1 (D0 = VCC) so the latch sets correctly either way, and the conditional branches set up the
function one step before `BR-TEST` — no wrong result, but do not copy the JSR pattern for a conditional instruction.

**M-6 Interrupt entry has no synchroniser.** `DO-INT` (pending AND enabled) is asynchronous to the clock and selects the IR's
D inputs (IC1/IC2) that the 74LS175s sample at the `LD-INS-REG` edge; an interrupt arriving within the set-up window of that
edge can load a mixed opcode. Also `INTD` is implemented with `INT-START`, which clears a pending interrupt as well as the enable
(the interrupt is lost, not deferred). Hardware/semantics note; the software uses INTE/IADDR/IRET once each.

**M-7 Every signal in the `UCODE-COUNT-RESET` step is active for one clock period, not two** (1.1). Today the last step only
carries hold states (`-MEM-RD`, `-ALU-FUNC`, `-REG-FUNC-LD`, `-BRANCH-RD`...), so nothing is lost; any future edit that puts a
strobe in the reset step gets a half-length pulse. The wavedrom diagrams draw it full length.

**M-8 The end-of-instruction mechanism is a race** (1.1): step 0 is latched from the ~50 ns pulse the counter produces before
its second asynchronous clear. It has margin with LS parts (LS374 needs ~15 ns) but it is worth knowing before changing the
clock or the logic family; the front-panel single step exercises the same path.

### LOW

**L-1 The common fetch prologue is 6 steps where 3 would do — in every instruction.** Steps 0 (idle), 1 (`-MEM-RD`), 2
(`-MEM-RD, LD-INS-REG`), 3 (`-MEM-RD` hold), 4 (increment with `-MEM-RD`), 5 (`-MEM-RD` hold). The IR latches at the leading
edge of step 2, so steps 3 and 5 hold nothing, and step 0 is needed only as "some common word" (it is executed from the previous
record). A prologue of 0: `-MEM-RD`; 1: `-MEM-RD, LD-INS-REG`; 2: `-REG-FUNC-RD, -REG-UP` (no `-MEM-RD`, which also removes M-1
at the fetch) saves 3 steps per instruction (JSR 31→28, LDAI 12→9, INCR 9→6: roughly 25 % of the machine's instruction time),
and the records switch at step 2 instead of 3 because the IR changes ~50 ns into step 1. Only the first two steps need to be
identical across all 256 records. Address time for the opcode after a taken branch is still ≥ 2.5 steps (PC loaded at the end of
the branch's load step, then the release step, the half-length reset step and the 3-clock step 0).

**L-2 `-IO-ADDR-LD` has no consumer** (1.5): OUTA/OUTn steps 7..8, OUTI/OUTn steps 6..7 (plus its idle step 11/12) and INP steps
6..7 can go: 2..3 steps each, and the I/O port comes from the static `IOADDR` field anyway.

**L-3 Release/hold steps after leading-edge latches can be merged with the next action.** Because `-AC-LD`, `-SR-LD`,
`-TMP-REG-LDx`, `BRANCH-LD-*`, `INT-LD-*`, `OPERAND-CLK` act at their leading edge, the following "strobe off" step can carry the
next set-up. Examples: LDTI 7, LDAI/ADDI-family 8, ADDT-family 9, MVAT 8, MVTA 9, MVRLA/MVRHA 8, INVA 8, INP 10, LDA 20, LDT 19,
BR-family 15 (after BR-TEST) and 19, JSR 27 and 29, shifts 8/11/14, IADDR 7/11, INT 26/28. The generator's `aluOp()`/`shiftOp()`
pattern "set-up, strobe, release" costs one step per strobe.

**L-4 Idle steps (S1 in the mechanical pass, 351 in total) that carry nothing:** step 0 everywhere (see L-1); INCR 7 / DECR 8
(the release step before the reset: `UCODE-COUNT-RESET` can be asserted in the same step as the strobe release, the count still
happens when step 0's word is latched); OUTI 11; LDIVR 11, 13; LDA/STA/LDT/STT 14, 16; STR 15, 17; LDR 14, 16; BR-family 12;
RET 7, 15; POP 7; POPR 8, 10, 12; INTE/INTD 7; IRET 7, 15; IADDR 14; INT 7, 10, 24; JSR 11, 25; JSRUR 15, 27; PUSHR 9; MOVRR
8, 10; LDAVR-family: none beyond step 0. Note the steps that look idle but are the select-only set-up before `-REG-DN` (JSR 16,
23; PUSH 11; INT 8, 15, 22; PUSHR 18, 28; RET/POP/IRET 6..7 pattern) are needed (1.2, count hazard) and are not in this list.

**L-5 RSHL is 15 steps because its shift mode code (5) equals the SHIFT output code, so the generator's duplicate-line filter
dropped one step; equivalent and harmless.** Same mechanism explains the only family differences: LDAVR R0 (10 vs 11), BRVR R0
(21 vs 22), STR R2 (31 vs 32), OUTI P0 (13 vs 14) — a repeated `putMemAtRegOnBus(PC)`/`setRdId(IR)`/`setIo(0)` line equal to its
predecessor was skipped. All eight members of every family are otherwise identical except the register/port select fields.

**L-6 Loads whose target is R0 are silently suppressed unless a taken BR-TEST preceded them in the same instruction** (1.1):
MVIB R0, MVIW R0, MVARL R0, MVARH R0, MOVRR src,R0, POPR R0 (SP still advances by 2), LDR R0 (IR still advances). The emulator
performs them. Probably intended ("R0 is the PC") but undocumented; a program tested on the emulator behaves differently.

**L-7 Emulator/microcode semantic mismatches found while checking every opcode** (the microcode is taken as the truth of the
machine; the emulator is the one to fix): see section 3 — BRVR, JSRUR (emulator swaps the bytes), SUB borrow into the carry FF,
shifts clobbering the carry FF, BR16Z/BR16NZ, opcode $00, IRET/INT/IADDR stubs, LDTVR/STTVR (emulator runs them, hardware has
no record: H-4), INTD losing a pending interrupt.

**L-8 `-INTA` is never asserted; `-SRC-ADDR`/`-DEST-ADDR`/`SPARE3` in the signal table are jumper inputs, not microcode bits**
(1.1). `IOADDR` is written into every step by `setIo()` only in the I/O records (the field is 0 elsewhere — fine, unused).

**L-9 R2 is a hidden scratch register.** LDA/STA/LDT/STT/LDR/STR load the operand address into R2 (`IR`) and leave it there
(+2 for LDR/STR); LDR R2/STR R2 are degenerate (STR R2,addr stores addr at addr; LDR R2,addr reads its second byte from
(hi:lo)+1 of the value just loaded). The emulator does the same; worth a line in the ISA documentation.

---

## 3. Per-opcode check against the emulator (`software/emulator/main.c`)

Columns: what the emulator does → what the microcode does → verdict (✓ same; ≠ differs; ! finding). Families are one row.

| Opcode(s) | Emulator | Microcode (steps after the common fetch 0..5) | Verdict |
|---|---|---|---|
| $00 START | badOpcode | reset vector: fetch + PC++ with OUT-OFF; as an opcode = 1-byte NOP that clears OUT | ≠ (harmless) |
| $01 ON / $02 OFF | LED on/off | OUT-ON / OUT-OFF at 6..7 (SR latch IC22 on the sequencer) | ✓ |
| $03 HALT | debug halt | SOFT-HALT at 6 stops the clock; CONT resumes into step 7 (reset) | ✓ |
| $04 JSR addr | push PC+3 hi then lo (SP--, SP--), PC = addr | branch reg ← hi (6), lo (9); PC++ twice; [SP] ← PC.hi via swap (12..14), SP-- (16..17), [SP] ← PC.lo (19..21), SP-- (23..24); PC ← branch reg with BR-TEST/ALU=0 (26..28) | ✓ (M-1 at 7; M-2 at 6/9) |
| $05 RET | SP++, lo; SP++, hi | 6..14 same order; PC load 16..17 (BR-TEST held through the load, harmless) | ✓ |
| $06 JSRUR Rn | PC.hi ← Rn.LO, PC.lo ← Rn.HI (swapped) | branch reg hi ← Rn.hi via swap (10), lo ← Rn.lo (13); push PC; PC ← Rn | ≠ emulator has hi/lo swapped |
| $07 PUSHR Rn | [SP]=hi, SP--, [SP]=lo, SP-- | same order via TMP1 | ! H-1 bus fight on both writes |
| $08 POPR Rn | SP++, lo; SP++, hi | 11..24 same, target from operand[7:4] | ✓ (L-6 for R0) |
| $09 PUSH / $0A POP | [SP]=AC, SP-- / SP++, AC=[SP] | 7..12 / 6..10 | ✓ |
| $0B MVAT / $0C MVTA | TMP=AC / AC=TMP | TMP0 ← DATA (AC on 0..7, $FF on 8..15) / AC ← TMP0 | ✓ |
| $0D LDTI / $0E LDAI | TMP/AC ← imm | 6 / 7, PC++ | ✓ (M-2 for LDTI) |
| $0F MOVRR Rs,Rd | Rd ← Rs (16 bit) | 11..14: 16-bit copy on ADATA (same card) or via the bus | ✓ (mechanical R2 was a false alarm; L-6 for Rd = R0) |
| $10 MVIB Rn,b | Rn.lo ← b | 6..8, PC++ at 9 | ✓ |
| $18 MVIW Rn,w | Rn.hi ← b1, Rn.lo ← b2 | 6..8 (swap, LD-HI), PC++, 11..13 (LD-LO), PC++ | ✓ |
| $20 MVRLA / $28 MVRHA | AC ← Rn.lo / Rn.hi | 6..8, hi via -HL-SWAP | ✓ |
| $30 MVARL / $38 MVARH | Rn.lo/hi ← AC | 6..10, hi via -HL-SWAP into the swap transceiver (receive) | ✓ (L-6 for R0) |
| $40 LDAVR / $48 STAVR | AC ← [Rn] / [Rn] ← AC | 6..8 / 7..9 | ✓ |
| $50 INCR / $58 DECR | Rn ± 1 | 6 / 6..7 (select-only step before -REG-DN, needed) | ✓ |
| $60 OUTA Pn | port ← AC | -AC-RD + -ALU-FUNC 6..11, -IO-WR 9 (latched at its trailing edge) | ✓ (L-2) |
| $70 OUTI Pn,b | port ← imm | -MEM-RD + -IO-WR at 8 (memory → port directly), PC++ at 10 | ✓ (L-2, L-4) |
| $80 OUTVR | badOpcode | no record | ! H-4 |
| $90 INP Pn | AC ← port | -IO-RD 8..11, -AC-LD 9 | ✓ (M-3) |
| $A0 BR / $AF BRDEV | PC ← addr (BRDEV: emulator does not branch) | ALU=0 → BR-COND=1, BR-TEST 14, load 18 | ✓ (BRDEV = BR on hardware) |
| $A1 BRZ / $A2 BRNZ | if AC==0 / !=0 | ALU=4 with -AC-RD (BDATA = AC), invert via -AC-LD-INV | ! H-2 |
| $A3 BRINH / $A4 BRINL | if IN==1 / 0 | ALU=5 (D5 = IN), invert | ✓ |
| $A5 | badOpcode (BRNC was planned) | no record | ! H-4 |
| $A6 BRC | if carry | ALU=7 (D7 = carry FF) | ✓ (carry semantics: L-7) |
| $A7 BRLT / $A8 BREQ / $A9 BRGT / $AA BRNEQ | AC <,==,>,!= TMP | ALU=3/2/1/2+invert with -TMP-REG-RD0 (BDATA = TMP0), comparators A=TMP,B=AC; -TMP-REG-RD0 released before -BRANCH-RD | ✓ |
| $AB BR16Z / $AC BR16NZ | badOpcode | ALU=6 with -AC-RD | ! H-2, H-3 |
| $B0 ADDI / $B1 SUBI / $B2 ORI / $B3 ANDI / $B4 XORI | AC op imm | ALU=7/1/3/2/4 at 6, -AC-LD 7, PC++ 9 | ✓ (SUBI also loads borrow into carry: L-7) |
| $B5 INVA | AC = ~AC | DATA function + -AC-RD + -AC-LD-INV | ✓ |
| $B6 SHL / $B7 SHR / $BD RSHL / $BE RSHR / $BF PSHR / $E0 CSHL / $E1 CSHR | shifts (carry only for CSHx) | load SR (ALU=3, -SR-LD), mode (1/2/5/6/A/D/E, -SR-LD), SHIFT out (ALU=5, -AC-LD) | ✓ data; ≠ all seven load the carry FF with the bit shifted out |
| $B8 ADDT / $B9 SUBT / $BA ORT / $BB ANDT / $BC XORT / $E3 ADDTC | AC op TMP | -TMP-REG-RD0 6..10, ALU code at 7, -AC-LD 8 | ✓ |
| $C0 LDTVR / $C8 STTVR | TMP ← [Rn] / [Rn] ← TMP | no record | ! H-4 (emulator runs them) |
| $D0 LDIVR Rn,b | [Rn] ← imm | TMP1 ← imm (6), [Rn] ← TMP1 (8..10), PC++ (12) | ✓ (M-2) |
| $D8 BRVR Rn | Rn.hi ← [Rn], Rn++, Rn.lo ← [Rn], Rn++ (loads Rn itself) | branch reg ← [Rn], [Rn+1]; Rn += 2; PC ← branch reg (indirect jump through a table) | ≠ emulator is wrong |
| $E2 ADDIC | AC += imm + carry | ALU=F (ADD + carry into C0) | ✓ |
| $E4 LDA / $E5 STA / $E6 LDT / $E7 STT | via IR=R2 | R2 ← addr (6..13), then [R2] access (17..21) | ✓ (L-9) |
| $E8 STR Rn,addr / $F0 LDR Rn,addr | hi at addr, lo at addr+1, R2 = addr+2 | same | ✓ (L-9; L-6 for LDR R0) |
| $FB INTE / $FC INTD | nothing | INT-EN / INT-START at 6 | ✓ (INTD also clears pending: M-6) |
| $FD IRET | badOpcode | RET + INT-EN at 19 | emulator stub |
| $FE IADDR addr | skips 2 bytes | INT vector ← hi (6), lo (10), PC += 2 | emulator stub |
| $FF INT | badOpcode | forced by DO-INT: INT-START, PC-- (undo the fetch increment), push PC, PC ← vector via -INT-JMP + BR-TEST | consistent with IRET |

Interrupt consistency (item 7 of the brief): INT decrements the PC before pushing (the common prologue incremented it), pushes
hi then lo exactly like JSR, loads the vector with the same BR-TEST/ALU=0 pattern, and `INT-START` both disables and
acknowledges; IRET restores in RET order and re-enables after the load; a second interrupt pending at IRET is taken before the
interrupted instruction re-executes (its opcode is re-fetched, so nothing is lost). `INT-EN`/`INT-START` are pulses into
level latches, so their one-step width is fine.

---

## 4. Checked, no issue

- Write strobes (`-MEM-WR`, `-IO-WR`): every one has its data source and address asserted one step before and held one step
  after; `-VMA` always on; no read/write overlap (agrees with the mechanical W1/W2/W3/R1/I1 = 0).
- Address-register count hazard (1.2: select changed in the step a count strobe asserts): scanned all 218 records, zero cases
  (`decrementReg` has its set-up step; every `incrementReg` follows a step without `-REG-FUNC-RD` or with the same ID).
- `-REG-UP` and `-REG-DN` never asserted together; never across a `-2-BYTE-OPERAND-SEL` toggle.
- The mechanical L1 hits: SHL/SHR/RSHL/RSHR/PSHR/CSHL/CSHR step 12/13 (`-AC-LD` with "nothing driving") — the source is the
  ALU-internal shift register (ALU=5 enables IC31 onto INV-IN), no bus needed; INT step 27 — `-INT-JMP` drives, the tool
  just does not list it. Both fine.
- The mechanical R2 hits for `-REG-RD-LO`+`-REG-RD-HI` (MOVRR 12..14, PUSHR 21..24, 28..31): byte lanes, not a fight (1.2).
  (PUSHR's real problem is H-1, which the tool could not see.)
- Register loads (level-sensitive): in every record the data source is asserted at least one full step before the load
  strobe's trailing edge and the address register driving `-MEM-RD` data was not changed in the load step (MVIB 7, MVIW 7/12,
  LDA/STA/LDT/STT/LDR 6 and 12, LDR 19/26, POPR 16/24, MVARL/MVARH 8, MOVRR 13, all PC loads).
- Branch condition set-up: every conditional branch establishes function code, source and inversion one step before
  `BR-TEST` (step 13 → 14); unconditional users rely on ALU=0 (M-5).
- Shift modes: the 74LS194 S1S0 and the 74LS153 serial-input selections match the emulator for all seven shifts (1.4).
- ADDIC/ADDTC carry-in path (ALU3 AND carry XOR SUB → C0) matches "add with carry".
- BRLT/BRGT polarity: comparators take A = bus (TMP), B = AC; D3 = A>B is used for BRLT (AC < TMP), D1 = A<B for BRGT — correct.
- STA/STAVR/PUSH/OUTA/MVAT/MVARL/MVARH: `-AC-RD` drives DATA8..15 = $FF as well; nothing else drives those lines in those steps.
- JSR/RET/IRET/INT PC loads: `-REG-FUNC-RD` released before `-BRANCH-RD`/`-INT-JMP`, the register card is in receive mode.
- `UCODE-COUNT-RESET` present in all 218 written records, always after the last strobe's release step; no dead steps after it.
- Family members: identical up to the select fields and the duplicate-line artefacts in L-5.
- Opcodes without microcode are not used by the assembler output of the monitor or BASIC (mnemonic counts over
  `monitor.asm`/`basic.asm`: no OUTVR, LDTVR, STTVR, BRNC, BR16Z, BR16NZ).
- The boot path: RESET clears the IR and the index registers, record $00 fetches from PC = 0 with FORCE-ROM mapping the ROM
  there, so the first opcode comes from $F000 (`BR eprom` in `monitor.asm`); the first access with ADDR15 high ends the remap.

---

## 5. Cycle savings (potential, per opcode)

Rules used for the "achievable" column: keep one set-up step before every strobe, one hold step after every write strobe, the
select-only step before `-REG-DN`/`-REG-UP` when the previous step selected another register, two steps of memory access before
a leading-edge latch of memory data (M-2), no `-MEM-RD` in increment steps (M-1), no `-IO-ADDR-LD` (L-2), the 3-step prologue
(L-1), and the reset step used as the last hold. Numbers are estimates to be verified on the bus tester one record at a time.

| Opcode | Now | Achievable | Saved | Main sources |
|---|---|---|---|---|
| START/ON/OFF/HALT | 8 | 5 | 3 | L-1 |
| JSR | 31 | 24 | 7 | L-1, L-3, L-4 |
| RET | 20 | 15 | 5 | L-1, L-4 |
| JSRUR | 32 | 24 | 8 | L-1, L-3, L-4 |
| PUSHR | 32 | 18 | 14 | L-1 + write the register directly (also fixes H-1) |
| POPR | 28 | 18 | 10 | L-1, L-4 |
| PUSH / POP | 15 / 13 | 9 / 9 | 6 / 4 | L-1, L-3 |
| MVAT / MVTA | 10 / 11 | 6 / 6 | 4 / 5 | L-1, L-3 |
| LDTI / LDAI | 11 / 12 | 8 / 8 | 3 / 4 | L-1, L-3 (LDTI keeps 2 access steps: M-2) |
| MOVRR | 17 | 10 | 7 | L-1, L-4 |
| MVIB / MVIW | 12 / 17 | 7 / 10 | 5 / 7 | L-1, L-3 |
| MVRLA / MVRHA | 10 | 6 | 4 | L-1 |
| MVARL / MVARH | 12 | 6 | 6 | L-1, L-3 |
| LDAVR / STAVR | 11 / 12 | 7 / 7 | 4 / 5 | L-1 |
| INCR / DECR | 9 / 10 | 5 / 6 | 4 / 4 | L-1, L-4 |
| OUTA / OUTI / INP | 12 / 14 / 12 | 7 / 8 / 8 | 5 / 6 / 4 | L-1, L-2 (INP keeps 2 set-up steps: M-3) |
| BR .. BRDEV (13 opcodes) | 21 | 16 | 5 | L-1, L-3, L-4 |
| BRVR | 22 | 17 | 5 | as BR |
| ADDI/SUBI/ORI/ANDI/XORI/ADDIC | 12 | 8 | 4 | L-1, L-3 |
| ADDT/SUBT/ORT/ANDT/XORT/ADDTC | 11 | 6 | 5 | L-1, L-3 |
| INVA | 10 | 6 | 4 | L-1 |
| SHL/SHR/RSHR/PSHR/CSHL/CSHR (RSHL) | 16 (15) | 10 (9) | 6 | L-1, L-3 |
| LDIVR | 15 | 11 | 4 | L-1, L-4 |
| LDA / STA / LDT / STT | 22 / 23 / 21 / 22 | 13 | 9..10 | L-1, L-3, L-4 |
| STR / LDR | 32 / 30 | 18 / 18 | 14 / 12 | L-1, L-4 |
| INTE / INTD | 9 | 5 | 4 | L-1, L-4 |
| IRET / IADDR / INT | 22 / 16 / 30 | 17 / 12 / 19 | 5 / 4 / 11 | L-1, L-3, L-4 |

Weighted by the monitor's static instruction mix (JSR 250, MVIW 110, RET 68, LDAI 44, LDTI 38, MVRLA 34, OUTI 33, BR 30,
BRNZ 29, POP 28, BREQ 26 ...) the saving is about 30 % of executed microcode steps; the 3-step prologue alone is ~22 %.

---

## 6. Corrections to the mechanical pass and to the timing-diagram model

- `tools/ucode_review.py` R2: `-REG-RD-LO` with `-REG-RD-HI` is not a fight (byte lanes); `-INT-JMP` is missing from
  `DATA_DRIVERS` (false L1 on INT 27); the tool should also list the register card as a driver whenever `-REG-FUNC-RD` selects a
  card without `-REG-FUNC-LD` selecting the same card (that is what would have caught H-1, H-2 and M-1), and the ALU as a driver
  whenever `-AC-RD` and `-ALU-FUNC` are both on (H-2).
- E1 must run over all 256 records, not only the non-empty ones (H-4).
- L2 assumes loads take the value at the trailing edge; for the IR, operand, branch, INT, TMP, AC and SR registers it is the
  leading edge (1.6), so "source appears in the same step" is a real fault for those and "source appeared one step earlier" is
  the marginal case (M-2). Only the index-register loads, memory and I/O writes are trailing-edge.
- `tools/ucode_wavedrom.py` `TIMING["latch"] = 0.00` ("loads take effect at the trailing edge") is wrong for the same
  registers; the diagrams also draw the reset step and step 0 as equal-length (1.1, M-7), draw `-REG-RD-LO`/`-REG-RD-HI` on one
  8-bit bus (the data bus is 16 bits wide at the register card, TMP registers and branch/INT registers), and show the data bus
  idle during increments although the register card drives $FFFF there (M-1).
- `docs/isa/README.md` says "Bytes" = 1 for BRVR and "no microcode" for four opcodes; add that `$AD`, `$AE`, `$F8..$FA` and the
  whole `$80..$8F`, `$C0..$CF` ranges are empty records (H-4).

---

## 7. Bench confirmations, in the order that settles the most

1. H-5: scope `ADDR-REG-ID0` (bus C3) while single-stepping `PUSH` — a 10-second check that decides whether any SP/IR-relative
   instruction can work on the board as drawn.
2. H-2: `BRZ` with AC = 0 to a target with a non-zero low byte, from the switch ROM; watch DATA0..7 at steps 16..18 and the
   fetch address afterwards.
3. H-1: `PUSHR` into the Mem Register RAM, read back; then the same after clearing the read strobes in the generator
   (`make check` will show the changed records).
4. M-1: DATA0 level during fetch step 4 (any instruction with an even opcode); VCC ripple at the same time.
5. H-4: fetch $80; expect COUNT-FAULT and all strobes low.
6. M-2/M-3: raise the function-generator clock until `BR` mis-targets or `INP` reads $FF; note the frequency — that is the
   machine's real limit and it is set by the one-step latches, not by the ALU.
7. L-1: regenerate with the 3-step prologue for one opcode family only (e.g. INCR), load, run `ledcount`; then the rest.

---

## 8. Summary

The microcode implements what the emulator describes for 70 of the 78 opcode families (section 3). The hardware model that
the mechanical pass and the timing diagrams used is wrong in four places that matter — the register card drives the bus on
`-REG-FUNC-RD` alone and its two read strobes are byte lanes of a 16-bit path; seven of the machine's registers latch on the
leading edge of their strobe; the reset step is half length and steps 0..2 belong to the previous opcode; the I/O address
latch does not exist. With the corrected model: two real bus fights that corrupt results (PUSHR on both stack writes, and
BRZ/BRNZ/BR16Z/BR16NZ while the PC is loaded), both one-line fixes in `branch.c`; 38 empty opcode records that turn an illegal
opcode into a 61-step "assert everything" storm; a permanent electrical contention in every fetch (harmless functionally);
one-step memory access windows that will be the first thing to fail at a faster clock; and about 30 % of all microcode steps
removable, 22 % of them from the common fetch alone. One hardware question came out of the netlist (sequencer IC11 gate B
driving ADDR-REG-ID low) that should be settled with a scope before any SP-relative instruction is trusted. Nothing was
changed in the microcode.
