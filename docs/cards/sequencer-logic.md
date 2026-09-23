# Sequencer logic card (v2.1) — theory of operation

The control half of the YACC1's microcode sequencer: it latches the opcode, counts the 64 microcode steps, pipelines
the 64-bit control word from the sequencer-memory card onto the backplane, and holds the front panel (run/reset,
single-step, halt/continue), the branch-taken latch and the interrupt logic.

Written 2026-09-23 from the YACC1-D tree.

Sources: `hardware/cards/sequencer-logic/eagle/v2.1/Sequencer-Logic-Prod-V2.1l.sch` and `.brd` (parsed with Python's
`xml.etree`; every net and pin below comes from the `<part>`/`<net>/<pinref>` elements), `hardware/cards/sequencer-logic/README.md`,
`eagle/v2.1/Notes.md`, `eagle/v2.1/bom/Sequencer-Logic-Prod-V2.1l.csv`, `hardware/FABRICATED.md`, `hardware/PROVENANCE.md`,
`hardware/DESIGN-REVIEW-NOTES-control-io.md` (section 1), `docs/isa/MICROCODE-REVIEW-NOTES.md` (section 1.1, findings
H-1..H-5, M-7, M-8, L-1, L-6, L-8), `firmware/microcode/yaccsignaldata2.h`, `firmware/microcode/ucode-generator2/main.c`,
`software/ucemu/y1ucemu.c`, `docs/system/MACHINE.md`, `BACKLOG.md`, `docs/history/general-notes/NOTES-Update from old project.md`,
`media/sequencer logic v2.1 top.jpeg`, `media/sequencer top.jpeg`, `tests/sequencer/`, `tests/assembler/{ledcount,romcount,romdiag}`.

Eagle gate letters are used for the glue logic (IC38B = gate B of IC38); physical pin numbers are quoted only where a
review document gives them. Net names `N$nn` are the schematic's own.

---

## 1. Purpose and place in the machine

The YACC1 is a microcode-sequenced machine: every opcode is a record of up to 64 steps, each step an 8-byte control
word whose 64 bits are (almost all) backplane control lines. The sequencer is built as two cards that plug into each
other through two 40-pin headers (SV1, SV2) and a 2x2 header (JP1): the **sequencer-memory** card holds the control
store (8 x 62256 SRAM loaded from I2C EEPROM by an ATmega328, `docs/cards/sequencer-memory.md`) and this **logic**
card turns that store into a running control unit. The logic card is the only card that plugs into the backplane; the
memory card rides piggyback on it (`media/sequencer top.jpeg`).

What the logic card does, in the order a fetch happens:

1. A step counter (IC33/IC34) driven by the on-card oscillator QG1 (or the single-step clock) produces the 6-bit step
   address `CADDR0..5`; the instruction register (IC8/IC9, loaded from `DATA0..7`) produces the 8-bit opcode address
   `CADDR6..13`. Together they address one of 256 x 64 control words in the memory card's RAM.
2. The 64 data bits come back over SV1/SV2 with a `U` prefix (`U-MEM-RD`, `UALU0` ...) and are clocked into eight
   74HC374 pipeline registers (IC7, IC12, IC14, IC16, IC17, IC19, IC20, IC28) on `BUS-LATCH-CLK`. Their outputs are the
   bus control lines. Their output enables are `-BUS-EN`, which the card derives from the memory card's `READY`.
3. A few control-word bits never reach the bus directly: `LD-INS-REG` clocks the IR, `OPERAND-CLK` clocks the operand
   register IC6, `BRANCH-LD-HI/LO` and `INT-LD-HI/LO` clock the on-card branch/interrupt-vector registers (whose outputs
   go onto `DATA0..15` under `-BRANCH-RD`/`-INT-JMP`), `UCODE-COUNT-RESET` ends the record, `BR-TEST` samples `BR-COND`,
   `SOFT-HALT` stops the clock, `OUT-ON/OFF` set and clear the `OUT` LED line, `INT-EN/INT-START` run the interrupt
   enable latch, `-2-BYTE-OPERAND-SEL` switches the register-select buses from the pipeline fields to the operand byte.
4. The register-load strobes `-REG-LD-LO/HI` are not simple pipeline bits: they are gated so that a load whose target is
   register 0 (the PC) only happens if the branch-taken latch is set — that is how conditional branches work.

```
                    +------------------------------------------------------------------+
   DATA0..7 ------->| IC2 (or IC1 = $FF on interrupt) -> IR IC8/IC9 --IC15--> CADDR6..13 |----> SV1 -> memory card
                    |                                                                  |
   QG1 osc ----+--->| IC38/IC26 gated clock -> IC33/IC34 step counter --IC35--> CADDR0..5 |----> SV1 -> memory card
   single-step-+    |                             |QA = CNT-CLK -> BUS-LATCH-CLK        |
                    |                                                                  |
   SV1/SV2 U* <-----|--- 64 control bits from RAM --> 8 x 74HC374 pipeline (OC=-BUS-EN) |====> bus control lines B7..C27
   JP1 (3 bits)     |                 |                                                 |
                    |   LD-INS-REG, OPERAND-CLK, BRANCH-LD-*, INT-LD-*, BR-TEST,        |
                    |   UCODE-COUNT-RESET, SOFT-HALT, OUT-ON/OFF, INT-EN/START,         |
                    |   -2-BYTE-OPERAND-SEL, -BRANCH-RD, -INT-JMP  (used on the card)   |
                    |                                                                  |
   DATA0..7 ------->| IC6 operand reg -> IC5/IC18A/IC11A (REG-RD/LD-ID, ADDR-REG-ID)    |
   DATA0..7 ------->| IC13/IC21 branch reg, IC3/IC10 INT vector  ==> DATA0..15          |
   BR-COND -------->| branch latch N$71 -> gates -REG-LD-LO/HI for register 0           |
   -INT ----------->| IC23A pending FF, IC22A/B enable latch -> DO-INT -> IC1/IC2 select |
   READY (SV1) ---->| IC36D -> -BUS-EN (bus C28)                                        |
   front panel ---->| RESET/EXECUTE, SS-WAIT/FREERUN, STEP-CLK, HALT, CONT -> -RESET (C30)|
                    +------------------------------------------------------------------+
```

The card is 218 x 114 mm ("V2.1l", lengthened from the 178 mm V2.0 outline so that the front-panel switches clear the
memory card) and was fabricated 2020-12-01 (`hardware/FABRICATED.md`). The photo `media/sequencer logic v2.1 top.jpeg`
shows it populated almost entirely with **74HC** parts (SN74HC374N, SN74HC244N, SN74HC193N, SN74HC175N, SN74HC02N,
SN74HC04N, SN74HC08N/MC74HC08AN, SN74HC32N, SN74HC74N) although the schematic, board and BOM say 74LS/74ALS — see 4.7.

## 2. Bus signals

Direction is seen from this card. Names are the Bus V3.2 names of `docs/system/connector/` and
`firmware/microcode/yaccsignaldata2.h`; the pin is the DIN 41612 pin of X1 (`<net>` to `X1.-Bxx`). "Pipelined" means
the line is a 74HC374 output whose D input is the like-named `U` bit from the memory card and whose OC is `-BUS-EN`.

| Pin | Signal | Dir | On this card |
|---|---|---|---|
| A3–A18 | ADDR0..15 | – | not connected on this card (the register card drives the address bus) |
| A19–A26 | DATA0..7 | in/out | in: opcode (IC2 -> IR), operand (IC6), branch/INT vector bytes (IC13, IC21, IC3, IC10). out: IC21 (branch lo), IC10 (INT lo) under `-BRANCH-RD` / `-INT-JMP` |
| A27–A30, B3–B6 | DATA8..15 | out | IC13 (branch hi) and IC3 (INT hi) Q outputs; the D inputs of those two chips are DATA0..7, so the high byte is written through the low byte |
| B7, B8 | -REG-FUNC-RD, -REG-FUNC-LD | out | pipelined (IC20 1Q, 2Q) |
| B9–B12 | REG-RD-ID0..3 | out | IC4A from the pipeline field `LREG-RD-ID0..3` (IC20) when `-ONE-OPERAND-SEL` is low, or IC5A from operand bits 0..3 when `-2-BYTE-OPERAND-SEL` is low. Not gated by `-BUS-EN` (4.6) |
| B13–B16 | REG-LD-ID0..3 | out | IC4B (`LREG-LD-ID0..1` from IC20, `LREG-LD-ID2..3` from IC12) or IC5B (operand bits 4..7). Also read back on the card by IC25A/IC30D for the PC-load gate |
| B17, B19 | -REG-RD-LO, -REG-RD-HI | out | pipelined (IC12 3Q, 5Q) |
| B18, B20 | -REG-LD-LO, -REG-LD-HI | out | **gated**: IC31E/F = NOT(`LREG-LD-LO/HI` AND `N$53`), see 3.5. Totem-pole, never tri-stated |
| B21, B22 | -REG-DN, -REG-UP | out | pipelined (IC12 7Q, 8Q) |
| B23–B26 | -MEM-RD, -MEM-WR, -IO-RD, -IO-WR | out | pipelined (IC14 1Q..4Q) |
| B27–B30 | -TMP-REG-RD0, -TMP-REG-LD0, -TMP-REG-RD1, -TMP-REG-LD1 | out | pipelined (IC14 5Q..8Q) |
| C3–C6 | ADDR-REG-ID0..3 | out | IC18B from the pipeline field `LADDR-REG-ID0..3` (IC19) when `-ONE-OPERAND-SEL` low; IC18A from operand bits 0..3 when `SRC-ADDR` low; IC11A from operand bits 4..7 when `DEST-ADDR` low. Not gated by `-BUS-EN` |
| C7–C10 | IO-ADDR0..3 | out | pipelined (IC19 5Q..8Q) |
| C11 | -IO-ADDR-LD | out | pipelined (IC7 1Q); no card consumes it (`MICROCODE-REVIEW-NOTES.md` 1.5) |
| C12 | -VMA | out | pipelined (IC7 2Q); asserted in every microcode line (`main.c:103,115` "Hack prevent ROM mapping from triggering") |
| C13 | -INT | in | JP3 pin 3; optional 10k pull-up R5 through the `-INT-PULLUP` header |
| C14 | -INTA | out | pipelined (IC17 1Q); never asserted by any record (`MICROCODE-REVIEW-NOTES.md` L-8) |
| C15–C19 | -ALU-FUNC, ALU0..3 | out | pipelined (IC7 3Q..7Q) |
| C20–C23 | -AC-LD-INV, -AC-RD, -AC-LD, -SR-LD | out | pipelined (IC7 8Q, IC28 1Q..3Q) |
| C24 | BR-COND | in | IC27A, ANDed with `BR-TEST` into the branch-taken latch |
| C25 | -HL-SWAP | out | pipelined (IC28 5Q) |
| C26 | IN | – | not connected on this card (the ALU tests it through its condition mux) |
| C27 | OUT | out | IC22D, the OUT-ON/OUT-OFF SR latch; drives the on-card OUT LED through R2 (330). Totem-pole, never tri-stated |
| C28 | -BUS-EN | out | IC36D = NOT(`READY`), `READY` = SV1 pin 12 from the memory card's ATmega. Totem-pole (4.4) |
| C29 | -RUN | – | not connected on this card (nor on any other) |
| C30 | -RESET | out | IC36C = NOT(`RESET`), the front-panel latch. Totem-pole |
| A2, B2, C2, A31, B31, C31 / A1, B1, C1, A32, B32, C32 | VCC / GND | in | 38 x 100 nF decoupling C1–C38, PWR LED through R1 (10k as drawn) |

Control-word bits that stay on the card: `LD-INS-REG`, `OPERAND-CLK`, `UCODE-COUNT-RESET`, `BRANCH-LD-HI/LO`,
`-BRANCH-RD`, `INT-LD-HI/LO`, `-INT-JMP`, `INT-EN`, `INT-START`, `BR-TEST`, `SOFT-HALT`, `OUT-ON`, `OUT-OFF`,
`-2-BYTE-OPERAND-SEL`, `SRC-ADDR`, `DEST-ADDR`, `SPARE3`. The three last ones arrive through JP1, not SV1/SV2 (3.6).

The microcode-level emulator `software/ucemu/y1ucemu.c` (`do_step()`, `compute()`) implements exactly this card's
behaviour for the IR, operand register, branch/INT registers, the branch-taken latch (`cond_latch`) and the R0 load
gate (`allowed = (cur.ld_id != 0) || cond_latch`), so it is the executable form of sections 3 and 4.

## 3. Schematic walkthrough

Sheet numbers are those of the Eagle schematic (10 sheets; sheet 7 is empty). Part values below are the schematic's
(`74*xxN` devices, BOM `74LS`/`74ALS`); the photo shows 74HC parts fitted (4.7).

### 3.1 Sheet 1 — clock, step counter, instruction register, microcode address

**Clock gating.** QG1 (XO-14 crystal oscillator can; value not in the design files — the photo shows a CTS MXO45-series can
marked `x.000000`, most likely 1.000000 MHz, **To verify:** read the can) drives `N$40`.

- IC38C: `N$39` = `N$40` AND `FREE-RUN`; IC38D: `N$38` = `SINGLE-STEP/WAIT` AND `SINGLE-STEP-CLK`; IC26B: `UCODE-CLK` =
  `N$39` OR `N$38`. So the clock source is the oscillator in free-run mode or the single-step line in single-step mode
  (both latches from sheet 5).
- IC26D: `N$26` = `COUNT-FAULT` OR `DO-HALT`; IC31C: `N$16` = NOT `N$26`; IC38A: `N$31` = `N$16` AND `RUN`; IC38B:
  `N$4` = `N$31` AND `UCODE-CLK`. `N$4` is the counter clock: it runs only while RUN is set (front panel in EXECUTE),
  the halt flip-flop is clear and the counter has not overflowed.

**Step counter.** IC33 and IC34 are 4-bit up/down counters (drawn 74*192, fitted SN74HC193N — 4.7) with `DN` = VCC,
`LD` = VCC, data inputs GND, `CLR` = `COUNT-RESET`. IC33 `UP` = `N$4`, `CO` = `N$1` -> IC34 `UP`. The outputs go through
IC35 (74*244, both gates enabled by `-BUS-EN`):

| Counter bit | Net | IC35 output | Meaning |
|---|---|---|---|
| IC33 QA | N$7 | CNT-CLK | phase bit: the pipeline clocks when it rises (3.2) |
| IC33 QB, QC, QD | N$8, N$9, N$11 | CADDR0, 1, 2 | step address bits 0..2 |
| IC34 QA, QB, QC | N$12, N$13, N$14 | CADDR3, 4, 5 | step address bits 3..5 |
| IC34 QD | N$15 | COUNT-FAULT | bit 7 of the count = step 64 reached: stops the clock through IC26D |

Because QA is the phase bit, **one microcode step is two counter clocks**. IC26A: `COUNT-RESET` = `RESET` OR `N$55`;
IC27B: `N$55` = `UCODE-COUNT-RESET` AND `N$4`. The reset of the counter is asynchronous and gated with the clock: the step
that carries `UCODE-COUNT-RESET` lasts one clock period, not two (`MICROCODE-REVIEW-NOTES.md` 1.1, M-7, M-8).

**Instruction register.** IC8 and IC9 (74*175 quad D flip-flops) are clocked by `LD-INS-REG1` = IC24A =
`LD-INS-REG` AND `RUN`, cleared by `-RESET`. Their D inputs `N$5, N$6, N$17, N$18` (IC9 = bits 0..3) and
`N$19..N$22` (IC8 = bits 4..7) are driven by one of two 74*244s: IC2 passes `DATA0..7` while `DO-INT` is low (gate
enable = `DO-INT`), IC1 passes VCC on all eight inputs while `-DO-INT` is low (IC36A: `-DO-INT` = NOT `DO-INT`).
That is how an interrupt substitutes opcode $FF (INT) for whatever the memory delivered. The Q outputs `N$2, N$3, N$10,
N$23` (IC9) and `N$34..N$37` (IC8) feed IC15 (74*244, enabled by `-BUS-EN`) whose outputs are `CADDR6..9` and `CADDR10..13`.
The IR therefore latches on the **rising edge of LD-INS-REG**, i.e. at the start of the step that asserts it, and the
memory card sees the new opcode address ~50 ns later; the pipeline latch at the end of that step already reads the new
record. The generator makes steps 0..5 identical in every record (`startInstruction()` + `loadNextInstruction()`,
`main.c`), which is why steps 0..2 can run "from the previous opcode's record" without harm.

**Reset and bus enable.** IC36C: `-RESET` = NOT `RESET` (bus C30). IC36D: `-BUS-EN` = NOT `READY` (bus C28, and the
OC of every pipeline 374 and of IC15/IC35). IC37A/D and IC36E form the three-inverter delay `RESET -> N$44 -> N$42 ->
N$46`, and IC32C makes `N$32` = NOR(`RESET`, `N$46`): a ~30–45 ns pulse on the falling edge of RESET only. IC25D ORs it
with `CNT-CLK` into `BUS-LATCH-CLK`, so releasing RESET clocks the pipeline once (address IR = 0, step 0: the START record)
even though the counter is held at 0 (`DESIGN-REVIEW-NOTES-control-io.md` 1.3).

**Halt.** IC23B (74*74) `D` = VCC, `PRE` = VCC, `CLK` = `N$33` = IC25B = `N$54` OR `SOFT-HALT`, `N$54` = IC24D = `FP-HALT`
AND `UCODE-COUNT-RESET`; `CLR` = `HALT-CLR` = IC32D = NOR(`RESET`, `FP-HALT-CONT`); `Q` = `DO-HALT`. So the HALT button
takes effect at the end of the current instruction (when `UCODE-COUNT-RESET` is high), `SOFT-HALT` (the HALT opcode, $03)
at once; CONT or RESET clears it and the clock resumes at the step the record was in.

### 3.2 Sheet 2 — the pipeline

Eight 74*374 with `CLK` = `BUS-LATCH-CLK` and `OC` = `-BUS-EN`. D inputs are the `U`-prefixed SV1/SV2 lines, Q outputs
the bus lines (2) or on-card signals:

| Register | D inputs (from memory card) -> Q outputs |
|---|---|
| IC7 | U-IO-ADDR-LD, U-VMA, U-ALU-FUNC, UALU0..3, U-AC-LD-INV -> -IO-ADDR-LD, -VMA, -ALU-FUNC, ALU0..3, -AC-LD-INV |
| IC12 | UREG-LD-ID2..3, U-REG-RD-LO, UREG-LD-LO, U-REG-RD-HI, UREG-LD-HI, U-REG-DN, U-REG-UP -> LREG-LD-ID2..3, -REG-RD-LO, LREG-LD-LO, -REG-RD-HI, LREG-LD-HI, -REG-DN, -REG-UP |
| IC14 | U-MEM-RD, U-MEM-WR, U-IO-RD, U-IO-WR, U-TMP-REG-RD0/LD0/RD1/LD1 -> the same without U |
| IC16 | U-BRANCH-RD, UBRANCH-LD-LO, USPARE3, UBRANCH-LD-HI, U-INT-JMP, UINT-LD-LO, U-2-BYTE-OPERAND-SEL, UDEST-ADDR -> -BRANCH-RD, BRANCH-LD-LO, SPARE3, BRANCH-LD-HI, -INT-JMP, INT-LD-LO, -2-BYTE-OPERAND-SEL, DEST-ADDR |
| IC17 | U-INTA, USRC-ADDR, UINT-LD-HI, UINT-START, UINT-EN, ULD-INS-REG, UUCODE-COUNT-RESET, UOPERAND-CLK -> -INTA, SRC-ADDR, INT-LD-HI, INT-START, INT-EN, LD-INS-REG, UCODE-COUNT-RESET, OPERAND-CLK |
| IC19 | UADDR-REG-ID0..3, UIO-ADDR0..3 -> LADDR-REG-ID0..3, IO-ADDR0..3 |
| IC20 | U-REG-FUNC-RD, U-REG-FUNC-LD, UREG-RD-ID0..3, UREG-LD-ID0..1 -> -REG-FUNC-RD, -REG-FUNC-LD, LREG-RD-ID0..3, LREG-LD-ID0..1 |
| IC28 | U-AC-RD, U-AC-LD, U-SR-LD, UBR-TEST, U-HL-SWAP, USOFT-HALT, UOUT-OFF, UOUT-ON -> -AC-RD, -AC-LD, -SR-LD, BR-TEST, -HL-SWAP, SOFT-HALT, OUT-OFF, OUT-ON |

The `L` prefix marks fields that go through a further buffer (IC4, IC18B) before the bus. JP2 (2 pins) links `SPARE3`
(IC16 3Q) to `-MEM-CPU-RESET` (JP1 pin 2 — the memory card's ATmega reset): a microcode bit that could reset the loader.
The generator never sets SPARE3 (it is cleared to 0 by `initCurrentLine()`, `main.c:94-105`), so with JP2 fitted the
memory card would be held in reset permanently; JP2 must stay open (`DESIGN-REVIEW-NOTES-control-io.md` 1.4). The mated-pair
photo shows bare pins at the `SPARE3`/`CPU-RESET` silk. **To verify:** JP2 open on the card.

The 74*374 map to bits: `yaccsignaldata2.h` gives every signal as (chip, port, bit); byte index = (chip-1)*2+port
(`controlLine.c`); the memory card wires byte n to its RAM ICn and MCP23017 port, and SV1/SV2 carry the same name to
the D input here. The 2026-09-21 review checked all 64 mappings (`DESIGN-REVIEW-NOTES-control-io.md`, "checked, no issue").

### 3.3 Sheet 3 — interrupt request and enable, the OUT latch

- **Enable latch**: IC22A `N$24` = NOR(`N$27`, `N$25`), IC22B `N$25` = NOR(`N$24`, `INT-EN`), IC30C `N$27` = `INT-START`
  OR `RESET`. A pulse on `INT-EN` (the INTE opcode) sets `N$24` = 1 (enabled); `INT-START` (INTD, and the INT record itself)
  or RESET clears it.
- **Pending flip-flop**: IC23A `D` = VCC, `CLK` = `INT-EDGE` (JP3 pin 2), `PRE` = `N$41` = IC36F = NOT `INT-LEVEL`
  (JP3 pin 4), `CLR` = `N$29` = IC36B = NOT `N$27`, `Q` = `N$28`. JP3 is a 5-pin header: 1 = GND, 2 = INT-EDGE, 3 = -INT
  (bus C13), 4 = INT-LEVEL, 5 = GND. A jumper 2–3 makes the flip-flop clock on the *rising* edge of -INT (the release of
  the request); a jumper 3–4 presets it while -INT is low (level mode). The other input must be jumpered to its GND
  neighbour, otherwise it floats (`DESIGN-REVIEW-NOTES-control-io.md` 1.6). The `-INT-PULLUP` header puts R5 (10k) on -INT.
  **To verify:** JP3 population (the mated-pair photo shows two caps on the LEVEL/EDGE header but not which pairs).
- IC24C: `DO-INT` = `N$28` AND `N$24` (pending AND enabled) — the IC1/IC2 select of 3.1. The generator's INT record ($FF)
  asserts `INT-START` first, which both acknowledges (clears IC23A) and disables further interrupts until IRET's `INT-EN`.
- **OUT latch**: IC22C `N$48` = NOR(`OUT`, `OUT-ON`), IC22D `OUT` = NOR(`OUT-OFF`, `N$48`). `OUT-ON` (the ON opcode, $01)
  sets `OUT` = 1, `OUT-OFF` ($02, and the START record) clears it. `OUT` is bus C27 and lights the on-card LED (part `.`,
  through R2 = 330). The record for opcode $00 (START) asserts `OUT-OFF` (`main.c:118`), so the LED goes out at reset release.

### 3.4 Sheet 4 — branch and interrupt-vector registers, branch-taken latch, PC-load gate

**Branch register.** IC13: `D` = `DATA0..7`, `Q` = `DATA8..15`, `CLK` = `BRANCH-LD-HI`, `OC` = `-BRANCH-RD`. IC21: `D` =
`DATA0..7`, `Q` = `DATA0..7`, `CLK` = `BRANCH-LD-LO`, `OC` = `-BRANCH-RD`. A 3-byte branch instruction fetches its two
address bytes one at a time on `DATA0..7` (high byte first, `branch.c`), latches each on the **leading edge** of its
`BRANCH-LD-*` strobe, and later drives the assembled 16-bit target onto `DATA0..15` with `-BRANCH-RD` while the register
card loads it into R0 (`-REG-FUNC-LD` with REG-LD-ID = 0, then `REG-LD-LO` + `REG-LD-HI` in one step — a 16-bit load
over both byte lanes, gated by the branch-taken latch as described below).

**Interrupt vector.** IC3 (hi: `D` = DATA0..7, `Q` = DATA8..15, `CLK` = `INT-LD-HI`) and IC10 (lo, `CLK` = `INT-LD-LO`),
both `OC` = `-INT-JMP`: loaded by the IADDR opcode ($FE) byte by byte, driven onto the bus by the INT record ($FF) to load
the PC. Same structure and same latch edge as the branch register.

**Branch-taken latch** (the V2.1 addition, `Notes.md`: "Add SR Flip Flop out of extra gates for Branch Cond, SET with
and of BRTest and BRCond, Clear with code-count-reset"):

```
IC27A  N$72 = BR-COND AND BR-TEST
IC26C  N$60 = N$72 OR N$71
IC37B  N$70 = NOT N$60
IC30A  N$67 = N$70 OR UCODE-COUNT-RESET
IC37C  N$71 = NOT N$67          =>  N$71 = (N$72 OR N$71) AND NOT UCODE-COUNT-RESET
```

`N$71` is a gate-built SR latch: set by any moment where `BR-COND` is high while `BR-TEST` is high (level-sensitive), held
until the record's last step clears it. The ALU card computes `BR-COND` from the ALU function code (0 = always true, used
by unconditional branches, JSR, RET, IRET, INT).

**PC-load gate.** The bus lines `-REG-LD-LO/HI` are not pipeline outputs:

```
IC25A  N$45 = REG-LD-ID0 OR REG-LD-ID1          (taken from the BUS lines B13..B16, so the 2-byte-operand
IC30D  N$47 = REG-LD-ID2 OR REG-LD-ID3           forms MOVRR/POPR see their own operand field)
IC25C  N$56 = N$45 OR N$47                       = "target is not register 0"
IC37F  N$51 = NOT N$56
IC27C  N$52 = N$51 AND N$71                      = "target is R0 and the branch was taken"
IC30B  N$53 = N$56 OR N$52
IC27D  N$57 = N$53 AND LREG-LD-LO ; IC31E  -REG-LD-LO = NOT N$57     (bus B18)
IC24B  N$58 = N$53 AND LREG-LD-HI ; IC31F  -REG-LD-HI = NOT N$58     (bus B20)
```

A load aimed at R0 reaches the register card only after a `BR-TEST` that found `BR-COND` true in the same instruction.
This is the whole mechanism of a not-taken conditional branch: the record runs exactly the same steps, the strobes are
simply swallowed. Consequences documented in `MICROCODE-REVIEW-NOTES.md` L-6: MVIB R0, MVIW R0, MVARL/MVARH R0, MOVRR x,R0,
POPR R0 and LDR R0 silently do not load (the emulators reproduce this: `y1ucemu.c` `allowed`).

### 3.5 Sheet 5 — front panel

Three toggle switches (9070-1W, a common `P` = VCC, two positions `O`/`S`) with 10k pull-downs R6–R11 feed NOR-pair latches
(debounce), two push buttons with 10k pull-ups R3/R4 feed inverters:

| Control | Nets | Logic |
|---|---|---|
| RESET / EXECUTE toggle | O = FP-RESET (R7), S = FP-EXECUTE (R6) | IC32A `RUN` = NOR(FP-RESET, RESET); IC32B `RESET` = NOR(RUN, FP-EXECUTE). RESET side: RESET = 1, RUN = 0: counters cleared (COUNT-RESET), IR cleared (-RESET), bus -RESET low, register cards and ALU carry cleared, memory FORCE-ROM set. EXECUTE side: RUN = 1: the counter clock and LD-INS-REG are enabled |
| SS/WAIT / FREERUN toggle | O = FP-FREERUN (R9), S = FP-SS (R8) | IC29A `SINGLE-STEP/WAIT` = NOR(FP-FREERUN, FREE-RUN); IC29B `FREE-RUN` = NOR(SS/WAIT, FP-SS): picks the oscillator or the single-step line as UCODE-CLK (3.1) |
| STEP-CLK toggle | O = FP-CLKL (R11), S = FP-CLKH (R10) | IC29C `FP-SINGLE-STEP-CLK` = NOR(FP-CLKL, HARD-RESET1); IC29D `HARD-RESET1` = NOR(FP-SINGLE-STEP-CLK, FP-CLKH): a debounced clock, one counter clock (half a step) per flip |
| SS-SEL header (3 pins) | 1 = FP-SINGLE-STEP-CLK, 2 = SINGLE-STEP-CLK, 3 = EXTERNAL-SINGLESTEP-CLK | jumper 1–2: the STEP-CLK toggle is the single-step clock; 2–3: JP4 pin 2 (an external clock, e.g. `embedded/clocker`) is |
| JP4 (4 pins) | 1 = GND, 2 = EXTERNAL-SINGLESTEP-CLK, 3 = UCODE-COUNT-RESET, 4 = GND | the external-clock input and the end-of-instruction signal for an external stepper (Notes.md: "Expose Ucode-Count-Reset ... for external debugger") |
| HALT button | -FP-HALT (R4) | IC31A `FP-HALT`: halt at the end of the instruction (3.1) |
| CONT button | -HALT-CONT (R3) | IC31D `FP-HALT-CONT`: clears the halt flip-flop through IC32D |

The card also has a place for the oscillator socket to take a function generator: MACHINE.md records the 2026-09-21
bring-up "on a function-generator TTL clock in the logic card's oscillator socket (pin 8 clock, pin 7 GND)".

### 3.6 Sheet 6 and 8 — operand register and the register-select buffers

IC6 (74*374, `CLK` = `OPERAND-CLK`, `OC` = GND, so always driving) captures `DATA0..7` on the leading edge of
`OPERAND-CLK`: bits 0..3 = `N$62, N$63, N$64, N$65`, bits 4..7 = `N$66, N$68, N$69, N$61`. Four 74*244 gates put these or
the pipeline fields on the three 4-bit select buses:

| Buffer | Enable (active low) | Inputs -> outputs |
|---|---|---|
| IC4A | -ONE-OPERAND-SEL | LREG-RD-ID0..3 (pipeline) -> REG-RD-ID0..3 |
| IC4B | -ONE-OPERAND-SEL | LREG-LD-ID0..3 (pipeline) -> REG-LD-ID0..3 |
| IC5A | -2-BYTE-OPERAND-SEL | operand bits 0..3 -> REG-RD-ID0..3 |
| IC5B | -2-BYTE-OPERAND-SEL | operand bits 4..7 -> REG-LD-ID0..3 |
| IC18B | -ONE-OPERAND-SEL | LADDR-REG-ID0..3 (pipeline) -> ADDR-REG-ID0..3 |
| IC18A | SRC-ADDR | operand bits 0..3 -> ADDR-REG-ID0..3 |
| IC11A | DEST-ADDR | operand bits 4..7 -> ADDR-REG-ID0..3 |
| IC11B | GND (enabled) | inputs GND; **outputs not connected** (no net on the schematic pins, no copper on pads 3/5/7/9 in the `.brd`) |

IC31B: `-ONE-OPERAND-SEL` = NOT `-2-BYTE-OPERAND-SEL`, so exactly one of IC4/IC5 drives at any time. This matches the
assembler's encoding (`software/assembler/yacc1.def`): MOVRR's byte is (dst<<4)|src, PUSHR/JSRUR/BRUR use the low nibble,
POPR uses reg<<4.

`SRC-ADDR` and `DEST-ADDR` (and `SPARE3`) are pipeline outputs whose D inputs come from **JP1** (2x2: 1 = USPARE3,
2 = -MEM-CPU-RESET, 3 = USRC-ADDR, 4 = UDEST-ADDR), not from SV1/SV2. On the memory card JP1 carries the same four
nets 1:1 (`SPARE3` = RAM IC5 I/O5 and MCP IC12 GPB2, `SRC-ADDR` = IC6 I/O6 / IC12 GPA1, `DEST-ADDR` = IC5 I/O0 / IC12 GPB7;
`Sequencer-Memory-V2.1.brd` signals). The mated-pair photo shows JP1 in line with SV1/SV2, so with the cards plugged
together these are ordinary microcode bits (`-SRC-ADDR` = byte 6 bit 1, `-DEST-ADDR` = byte 7 bit 7 in `yaccsignaldata2.h`,
named with `-` so their idle value is 1 = buffer disabled). The generator never asserts them, so the operand-to-address
path (a register named in the operand byte as the address source, the way BRVR/LDAVR would like it) is unused today.
`MICROCODE-REVIEW-NOTES.md` 1.1 calls them "jumper inputs, not microcode bits"; the board files say they are microcode bits
routed through the jumper header. **To verify:** that JP1 on the two cards is mated (a 2x2 female on one side).

**About review finding H-5** (`MICROCODE-REVIEW-NOTES.md`: "IC11 gate B permanently drives ADDR-REG-ID0..3 low"): the
Eagle schematic gives IC11 gate B `A1..A4` = GND and `G` = GND but no net on its `Y1..Y4`; the board file has no signal
on IC11 pads 3, 5, 7, 9 (the 2Y outputs) — pads 12/14/16/18 on `ADDR-REG-ID3..0` are gate A's outputs, enabled by
`DEST-ADDR`. The control-path review read it the same way ("IC11B inputs grounded and enabled (harmless)"). As drawn and as
fabricated there is no contention; the H-5 scope check (bus C3 during a single-stepped PUSH) is still cheap insurance.

Sheet 8 holds only the IC11B spare and IC37E (input grounded).

### 3.7 Sheets 9 and 10 — SV1, SV2, JP1, X1

SV1 and SV2 are 2x20 headers (MA20-2). Their pin-outs are identical on both cards apart from the `U` prefix on this side
(80/80 checked in `DESIGN-REVIEW-NOTES-control-io.md`). Notable pins: SV1 12 = `READY` (memory card ATmega PD7), SV1 14..38
even = `CADDR0..12`, SV1 2 = `CADDR13`, SV1 39/40 = GND, SV2 1/2 = VCC. `CADDR14` is not on the headers: the memory card
sets it with its own jumper. X1 is the 96-pin DIN 41612 (FABC96R) to the backplane, pinned as in section 2.

## 4. Timing and the review findings that concern this card

The model is `MICROCODE-REVIEW-NOTES.md` section 1.1, confirmed against the schematic above:

- **One step = two clock periods.** The pipeline latches the word for step k when IC33 QA rises (count 2k -> 2k+1); the
  memory card has one clock period after `CADDR` changes to deliver the next word (62256-55 access time is 55 ns, far
  inside any clock the card is likely to see).
- **The IR latches on the leading edge of LD-INS-REG** (3.1); the operand register on the leading edge of `OPERAND-CLK`;
  the branch and INT registers on the leading edges of their `*-LD-*` strobes. All of these need their data valid at the
  end of the *previous* step — the generator's "source one line early" convention (`memory.c`, `branch.c`).
- **The reset step is one clock long** (3.1): every signal asserted together with `UCODE-COUNT-RESET` is half length
  (M-7). Step 0 of the next record is latched from the short QA pulse the counter makes before its second asynchronous
  clear (M-8) — margin is fine with HC/LS parts (a 374 needs ~15–20 ns) but it is a race to remember before changing clock
  or logic family.
- **Steps 0..2 belong to the previous record**: the IR changes ~50 ns into the LD-INS-REG step, so the next pipeline latch
  already fetches from the new record. The six-step common prologue (L-1) exists so that this hand-over is invisible; the
  review's 3-step prologue would save ~22 % of all executed steps.
- **BR-TEST is level-sampled** (3.4): `BR-COND` must be stable through the whole BR-TEST step. The generator sets the ALU
  function one step before BR-TEST in every conditional branch (`branch.c`); JSR/RET/IRET/INT assert both in the same step
  with ALU = 0 (D0 = VCC on the ALU's mux), which is safe only because the result is a constant 1 (M-5).

Findings, with their status on 2026-09-23:

| Finding | What it is on this card | Status |
|---|---|---|
| H-1 PUSHR bus fight | not a card fault: the record left `-REG-RD-HI/LO` and `-REG-FUNC-RD` on while TMP1 drove the stack byte | **fixed in the generator 2026-09-22** (`branch.c`, "H-1"), reproduced and verified on `software/ucemu`, EEPROM reloaded the same evening (`tools/ucode_send.py --all`) |
| H-2 BRZ/BRNZ/BR16Z/BR16NZ release order | the ALU kept `-AC-RD` on while IC13/IC21 drove the target under `-BRANCH-RD` and the PC loaded (3.4) — a taken BRZ landed on offset $00 under the wired-AND rule | **fixed 2026-09-22** (`branch.c` clears `-AC-RD` where it clears `-TMP-REG-RD0`), loaded; bench check pending (`tests/assembler/brur`, `tests/ucemu/isa.asm`, then the monitor from ROM) |
| H-3 BR16Z/NZ | needs the 16-bit operand on the bus with the ALU receiving; as microcoded it tests $FF on BDATA8..15 | **open** (no user of these opcodes) |
| H-4 38 all-zero records | an all-zero word asserts every active-low line for 61 steps until `COUNT-FAULT` (IC34 QD) stops the clock — the halted pipeline then holds that word on the bus until RESET | **open**; fix is in the generator (fill unwritten records with the idle word + `UCODE-COUNT-RESET`); on the card, `COUNT-FAULT` is the only protection |
| H-5 IC11 gate B | see 3.6: schematic and board show its outputs unconnected | resolved from the design files; a scope on C3 during PUSH would close it on the hardware |
| Review 1.1 (control-io): 17 lines driven regardless of -BUS-EN | IC4/IC5/IC18 (B9–B16, C3–C6), IC31E/F (-REG-LD-LO/HI), IC36C (-RESET), IC22D (OUT), IC36D (-BUS-EN) are not tri-stated. With -BUS-EN high IC16 7Q floats, IC31B reads it as high, IC4 + IC18B drive the floating `L*` nets onto the bus. This is why the bus tester cannot load RAM with this card fitted (its MCP23017s drive the same lines push-pull) | **open**; BACKLOG "Sequencer logic v2.2: a CPU off switch" must cover all of them |
| Review 1.2: 74LS192 in schematic/BOM | decade counters would skip step 5 of the fetch and fault at 40 steps | **resolved by the photo**: IC33 and IC34 are SN74HC193N (binary). The design files and BOM still say 74LS192 — correct them before any rebuild. **To verify:** the same on the card in hand |
| Review 1.3: reset does not reload the pipeline | during RESET the counter is held, `N$32` fires only on release: the 374s keep the last word (with `-MEM-WR`/`-VMA` possibly asserted while FORCE-ROM maps the EEPROM everywhere) | **open** (MED); goes with memory-card finding M2 (28C64 `-WE` = raw `-MEM-WR`), also open |
| Review 1.4: JP2 and SPARE3 | JP2 fitted = memory card held in reset | keep JP2 open (**To verify**) |
| Review 1.5: -REG-LD-LO/HI glitch | two gates on the strobe path vs seven on the ID path (3.4); a future record that changes REG-LD-ID and raises the strobe in the same step can produce a 40–60 ns runt load of R0 | latent; the generator writes the ID one line before the strobe |
| Review 1.6: JP3 needs two jumpers; edge mode triggers on release | 3.3 | configuration (**To verify**) |
| Review 1.7: asynchronous gating of N$4 | CONT/EXECUTE/SS-WAIT changes can produce a runt on IC33 UP | front-panel only |
| Review 1.8: all pipeline outputs float with -BUS-EN high, no pull-ups | LS inputs read floating as high (= inactive for every strobe); the 54 s microcode load and every tester session depend on it | **open**, and worse than the review assumed if the receiving cards are 74HC (4.7) |
| S1 (datapath review): no power-on reset | RESET is the IC32A/B latch of 3.5; FORCE-ROM, the register counters and the ALU carry are undefined until the RESET switch is thrown | **open** (MED) |
| BACKLOG "CPU off switch" | v2.2 idea: OE of the 374/244s through a switch (RUN = follow -BUS-EN, OFF = high), plus the 17 lines above, plus an open-collector or jumperable -BUS-EN driver so the bus tester can own the bus | not started |
| BACKLOG / Notes.md: HALT LED, expose ucode-count-reset and instruction number for an external debugger | JP4 already exposes UCODE-COUNT-RESET; the IR is only on CADDR6..13 (SV1) | not started |

### 4.7 74HC, not 74LS — what the photo changes

`media/sequencer logic v2.1 top.jpeg` (2020/21) shows SN74HC-series parts in every socket that can be read: the 374s,
244s, 175s, 193s, 02/04/08/32 gates, the 74 flip-flop (IC23 SN74HC74N) and MC74HC08AN at IC27. The schematic values are
`74*xxN`, the BOM says 74LS/74ALS, and both 2026-09-21 reviews reason with LS numbers (input floating = high, VIH 2.0 V,
40 mA short-circuit currents). With HC parts:

- a floating input is **not** reliably high: it sits at an undefined level and can oscillate, and the "floating = inactive"
  convention that the machine relies on during the microcode load (review 1.8, backplane 5.1) is weaker than the reviews
  state. The machine has run this way (ledcount, romcount), so in practice the lines settle high enough, but a pull-up bank
  on a backplane revision is the real answer;
- the register card's CD4077 (`docs/cards/register.md`, R1) is driven from this card by HC outputs for `-RESET` (IC36C) and
  `-HL-SWAP` (IC28), which swing to the rail — that part of R1 is moot; the LS139 on the register card (its IC32) remains;
- the reset-release pulse `N$32` (three inverter delays) is shorter with HC than with LS; it still has to exceed the 374's
  minimum clock width. **To verify:** scope IC25 pin 11 on a RESET release (expect > 20 ns).

**To verify:** every chip marking on the card in hand against the BOM (only the top-side photo was read), and a corrected
BOM (74HC193, 74HC374 ...) in `eagle/v2.1/bom/` before any rebuild.

## 5. Jumpers, switches, LEDs, connectors — settings in the machine

`docs/system/MACHINE.md` lists the card as fitted (v2.1, 2020-12) but records no jumper settings for it; the settings
below are read from the photos and flagged accordingly.

| Item | Function (from the schematic) | In the machine |
|---|---|---|
| RESET toggle | RESET / EXECUTE (3.5) | EXECUTE to run |
| SS/WAIT toggle | single-step (SS-WAIT) or FREERUN clock | FREERUN for the ROM programs; SS-WAIT with STEP-CLK for bring-up |
| STEP-CLK toggle | one counter clock (half a step) per flip in single-step mode | – |
| HALT / CONT buttons | halt at end of instruction / continue | – |
| SS-SEL (3 pins, silk EXT/INT) | 1–2 = on-card STEP-CLK toggle, 2–3 = JP4 pin 2 external clock | photo: cap on the EXT-side pair; **To verify** which pins the cap bridges |
| JP4 (4 pins, silk GND / CLK / CLK-RESET / GND) | 2 = external single-step clock in, 3 = UCODE-COUNT-RESET out | no cap (signal header) |
| JP3 (5 pins, silk LEVEL / EDGE) | 2–3 edge, 3–4 level; the unused input jumpered to GND (1–2 or 4–5) | photo: two caps; **To verify** positions |
| -INT-PULLUP (2 pins) | R5 10k on -INT | photo: no cap visible; the IO card's -INT driver is open-collector with its own RN2 (`DESIGN-REVIEW-NOTES-control-io.md` 3), **To verify** |
| JP2 (2 pins, silk SPARE3 / CPU-RESET) | SPARE3 microcode bit -> memory-card ATmega reset | **must be open**; photo: bare pins |
| JP1 (2x2) | SPARE3, -MEM-CPU-RESET, SRC-ADDR, DEST-ADDR to the memory card | mated with the memory card's JP1 (photo) |
| SV1, SV2 (2x20) | the 64 microcode bits, CADDR0..13, READY, VCC/GND | mated with the memory card |
| QG1 (DIL14 socket) | oscillator can; or a function generator on pin 8 (GND pin 7) | MXO45-class can fitted (photo); function generator used 2026-09-21 |
| LEDs | PWR (R1), OUT (`.`, R2) | – |
| X1 | DIN 41612 to the backplane | any slot |

## 6. Bring-up and test

**How the card was proven.**

- 2020: `tests/assembler/yacc1test.asm` and its 15 dated snapshots (`tests/assembler/history-2020/`: serial out, ROM,
  RAM, push/pop, ring shift, "major test") were run through the bus tester and the machine as the cards came up; the
  monitor and BASIC were burned 2021 and ran (`docs/system/MACHINE.md`).
- 2026-09-21: with the tree's microcode in the sequencer RAM and a function-generator clock in the QG1 socket, the CPU
  executed the 16-byte switch-ROM program `tests/assembler/ledcount` (LDAI/OUTI/OUTA/ADDI/BR — PC-relative only) on the IO
  card's LEDs (`MACHINE.md`).
- 2026-09-22/23: `tests/assembler/romcount` (BRNZ, DECR, MVRHA, MVAT/MVTA, ADDI, OUTA/INP, BRINL) ran overnight from the
  28C64 on the reloaded microcode without a fault. Its first build failed because the bring-up machine had only register
  card 0: `tests/assembler/romdiag` (a staged instruction check paced by the input switch) read $FF at its stage 2 and $FF
  at stage 9 (R7) — a read of an absent register leaves the bus to its pull-ups. That is a register-card lesson, but it is
  also the way to test this card: romdiag's stages 5/6 (BRNZ taken/not taken) exercise the branch-taken latch and the R0
  load gate of 3.4 directly, and stage 1 (LDAI after a JSR/RET) the branch register and the stack.
- `tests/sequencer/*.log` are the memory card's run-mode boots; the 2026-09-21 log with the bus tester still asserting
  `-BUS-EN` shows every RAM dump as zero — the tester's -BUS-EN put this card's IC15/IC35 onto the CADDR lines against the
  memory card's MCP23017, so every write went to address 0 (`embedded/sequencer-card/README.md`). Keep the bus quiet
  (tester unplugged or running `bus-monitor`) while the loader copies.

**If it misbehaves — what to measure** (bench items from the reviews, in the order that settles the most):

1. `-BUS-EN` (C28) low once the memory card's READY LED is on; if not, IC36D or SV1 pin 12.
2. `CNT-CLK` (IC35 1Y1) toggling at half the clock rate while RUN; `CADDR0..5` counting; `COUNT-FAULT` (IC35 2Y4) low.
   If `COUNT-FAULT` is high the record ran to step 63: an all-zero record (H-4) was fetched, or the pipeline never saw
   `UCODE-COUNT-RESET` — check SV1 pin 31 (UUCODE-COUNT-RESET) against the RAM dump.
3. Single-step (SS-WAIT + STEP-CLK) and watch `CADDR` on SV1 with the memory card's monitor loop (`Sequencer4.ino`
   prints `Addr/Ins/Line/Data` and the bits that changed once a second): the cheapest logic analyser the machine has.
4. `LD-INS-REG1` (IC24A output) pulsing once per instruction; IR contents on `CADDR6..13` equal to the opcode on DATA0..7
   at that edge (if not: IC2 enable = `DO-INT` stuck high -> IC1 forces $FF -> the INT record runs).
5. Branches: `BR-COND` (C24) at `BR-TEST` (IC28 4Q) with a scope; `N$71` (IC37C output) set for a taken branch; B18/B20
   pulsing only when taken. This is the H-2 bench check: taken `BRZ` to a target with a non-zero low byte.
6. Reset release: the `N$32` pulse at IC25D's input (IC32C output) and the pipeline word after it (instruction 0, step 0 = `03 d4 ff 00 85 57 03
   d1` in the boot dumps of `tests/sequencer/`).
7. Bus-fight symptoms (a mid-rail level on any control line with a meter) while the bus tester is plugged in: expected
   with this card fitted (review 1.1); remove the card or the tester.

## 7. Revision history and what the next revision should change

| Revision | Date | What | Source |
|---|---|---|---|
| gen-1 SEQUENCER-LOGIC-V1.0 / SEQUENCER-PROD-V1.0 | 2016 | the 2016 machine's sequencer (32-step microcode, `archive/superseded-revisions/ucode-generator-v1/`, signal names TEST-IN, U-TEST-IN ...) | `archive/gen1-2015-2018/`, README |
| V2.0 | 2020-07-25 (real date, PROVENANCE) | the 2020 redesign: IN tested in the ALU and returned on BR-COND (no TEST-IN line), soft reset removed, HALT/CONT moved to the top edge, `-1-BYTE-OPERAND-SEL` dropped in favour of `-2-BYTE-OPERAND-SEL` and its inverse, external single-step jumper added, `-halt-cont` renamed | `docs/history/general-notes/NOTES-Update from old project.md` ("YACC2020 updates"), `eagle/deprecated/v2.0/`; fabricated, retired 2021-01 |
| V2.1 ("V2.1l") | 2020-12-01 | branch-condition SR flip-flop (3.4), 2-byte opcodes split into 2-byte-reg and 2-byte-IO, FP-HALT/CONT naming cleaned up (IC36/8 FP-CONT, IC36.2 FP-HALT ...), SOFT-HALT and USOFT-HALT made one net, board lengthened to 218 mm; `orig size/` holds the same circuit on the 178 mm outline (silk still V2.0) and an unrouted copy — never ordered | `eagle/v2.1/Notes.md`, `hardware/FABRICATED.md`; **in the machine** (Ken 2026-09-20) |

Open ideas from `Notes.md` not done in V2.1: "if design goes down to 8 registers bit 3 of reg rd and ld can be repurposed"
(the machine has 8 registers and REG-*-ID3/ADDR-REG-ID3 are indeed spare), expose UCODE-COUNT-RESET and the instruction
number for an external debugger (UCODE-COUNT-RESET is on JP4; the IR is not brought out), "maybe expose reset signal",
HALT LED.

**A v2.2 should** (from `BACKLOG.md` and the reviews, in order of value):

1. The "CPU off" switch: route the OE of the eight pipeline 374s and of IC15/IC35 through a switch (RUN = follow -BUS-EN,
   OFF = high) **and** gate the 17 lines that bypass -BUS-EN today (IC4/IC5/IC18 enables, IC31E/F, IC36C, IC22D), and make
   the READY-to-BUS-EN driver open-collector or jumperable so the bus tester can own -BUS-EN. Until then the tester cannot
   load RAM with this card plugged in.
2. Clear the pipeline on RESET (or force the idle word) so that the bus does not carry a stale `-MEM-WR`/`-VMA` while
   FORCE-ROM maps the EEPROM everywhere (review 1.3; memory M2).
3. A power-on reset (RC or supervisor into the IC32 latch) — S1.
4. Correct the design files to the fitted parts (74HC193 counters at least) and record the oscillator frequency in the BOM.
5. Keep JP2 or replace it with a solder link labelled "do not fit"; document JP3's two-jumper rule on the silk.
6. Optional: the 3-step fetch prologue is a microcode change, not a card change, but if the IR is ever brought out for a
   debugger, bring out `CADDR6..13` and `LD-INS-REG1` together.

Related documents: `docs/cards/sequencer-memory.md` (the other half, the ATmega firmware and loader),
`docs/cards/register.md` (what the ID buses and strobes do at the far end), `docs/cards/alu.md` (BR-COND),
`docs/isa/MICROCODE-REVIEW-NOTES.md` (per-opcode timing), `docs/system/MICROCODE.md` (the control-store format, when written).
