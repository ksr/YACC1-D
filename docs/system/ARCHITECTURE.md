# YACC1 architecture — the machine as a whole

How the YACC1's cards, buses, registers and control store fit together, and what happens between one opcode fetch
and the next. This is the entry document: the bus itself is in `BUS.md`, the control store in `MICROCODE.md`, each
card will get its own theory of operation under `docs/cards/`.

Written 2026-09-23 from the YACC1-D tree.

Sources: `docs/system/MACHINE.md` (what is fitted), `docs/isa/MICROCODE-REVIEW-NOTES.md` section 1 (the hardware model
re-derived from the KiCad netlists), `hardware/DESIGN-REVIEW-NOTES-datapath.md` and `hardware/DESIGN-REVIEW-NOTES-control-io.md`
(the 2026-09-21 design review), `software/ucemu/y1ucemu.c` (the microcode-level emulator: the executable form of that model),
`firmware/microcode/ucode-generator2/*.c` and `firmware/microcode/yaccsignaldata2.h`, `docs/isa/steps.txt` and
`docs/isa/LDAI.json` / `docs/isa/OUTA.json`, `hardware/cards/*/README.md` and `eagle/<rev>/Notes.md`, the Eagle schematics
(`hardware/cards/<card>/eagle/<rev>/*.sch`, parsed with Python for part types and nets), `hardware/cards/memory/README.md`,
`firmware/abi/README.md`, `firmware/monitor/monitor.asm`, `software/opcodes.h`, `software/assembler/yacc1.def`,
`docs/system/OS-PLAN.md`, `BACKLOG.md`, `hardware/FABRICATED.md`.

Conventions: a signal name with a leading `-` is active low (the same rule the generator uses to decide which way a bit
is written, `main.c` `setSignal()`); "IC7 on the memory card" means the reference designator on that card's schematic;
`$` prefixes hexadecimal. Anything the tree does not settle is marked **To verify:**.

---

## 1. What the YACC1 is

The YACC1 ("Yet Another Custom CPU", `README.md`) is an 8-bit accumulator machine built from TTL on plug-in cards
that share a 96-pin DIN 41612 backplane. Its datapath is 8 bits wide (the accumulator, the ALU, memory bytes) but its
address space, its index registers and the data bus are 16 bits wide, so a 16-bit word can travel across the bus in one
step. There is no instruction decoder in the usual sense: every opcode is a 64-step microprogram held in RAM on the
sequencer-memory card, and the sequencer-logic card simply plays those steps onto the bus. The datapath cards (ALU,
index registers, memory, I/O) contain no state machine of their own; each one reacts to the strobes it sees on the bus.
That is why a wrong microcode step can corrupt a stack push (`docs/isa/MICROCODE-REVIEW-NOTES.md` H-1) and why the
microcode-level emulator can reproduce the machine from the control-store image alone (`software/ucemu/README.md`).

Register model in one line (`firmware/microcode/ucode-generator2/CodeGen.h`, `docs/isa/MICROCODE-REVIEW-NOTES.md` 1.2, L-9):
one 8-bit accumulator **ACC**, two 16-bit temporaries **TMP0/TMP1** on the memory card (the ISA's "TMP" is TMP0), a carry
flip-flop, an 8-bit shift register, and eight 16-bit up/down counters **R0..R7** of which R0 is the program counter, R1 the
stack pointer and R2 the operand-address register that LDA/STA/LDT/STT/LDR/STR use as scratch.

---

## 2. Block diagram

The machine as fitted on 2026-09-23 (`docs/system/MACHINE.md`; `hardware/FABRICATED.md` "In the machine"):

```
                 SV1/SV2 ribbon (2 x 40 pins: 8 control bytes + CADDR0..13 + READY/SPARE)
   +------------------------+  <=====================>  +--------------------------+
   | SEQUENCER MEMORY V2.1  |                           | SEQUENCER LOGIC v2.1     |   front panel:
   | 8 x 62256 = 256 op x   |                           | step counter (2x74LS192) |   RESET/EXECUTE, HALT, CONT,
   | 64 step x 8 byte       |                           | IR (2x74LS175)           |   SS/WAIT, STEP-CLK, SS-SEL
   | ATmega328P loader,     |                           | operand/branch/INT regs  |   clock: QG1 oscillator socket
   | 24Cxx EEPROM (adaptor) |                           | pipeline: 8 x 74LS374    |
   | not on the bus         |                           | -BUS-EN = NOT READY      |
   +------------------------+                           +-----------+--------------+
                                                                    | control lines (rows B, C)
   ===================================================================================================  96-pin
    ADDR0..15 (row A)      DATA0..15 (row A/B)      -MEM-RD -MEM-WR -IO-RD -IO-WR -VMA  ...  -RESET   DIN 41612
   ===================================================================================================  backplane
        |                       |                        |                     |                      |
   +----+--------+   +----------+----------+   +---------+--------+   +--------+---------+   +--------+--------+
   | INDEX REGS  |   | ALU V3.2            |   | MEMORY v1.3      |   | I/O V1.1         |   | BUS TESTER v1.1 |
   | card 0: R0-3|   | ACC (74LS374)       |   | 2 x 62256 RAM    |   | XR16C550 UART    |   | ATmega328 +     |
   | card 1: R4-7|   | 2 x 74LS283 adder   |   | 28C64 EEPROM     |   | switches/LEDs    |   | 6 x MCP23017    |
   | 74LS192 x16 |   | carry FF, 74LS194   |   | FORCE-ROM remap  |   | LCD, TIL311 x2   |   | (bring-up only) |
   | per card    |   | 74LS85 compare,     |   | TMP0/TMP1        |   | P0 = control     |   +-----------------+
   | drive ADDR  |   | 74LS251 BR-COND     |   | (4 x 74LS374)    |   | P1 = data        |
   +-------------+   +---------------------+   +------------------+   +------------------+   +-----------------+
                                                                                             | VIDEO V1.0      |
                                                                                             | IDT7134 + 6845  |
                                                                                             | (no 6845 fitted)|
                                                                                             +-----------------+
```

Cards that exist but are not on the bus: Mem Switch 1.1 and Mem Register 1.0 (the bring-up ROM/RAM pair, refitted for
the 2026-09-21 CPU bring-up and normally out), the two bus-jumper boards (obsolete), the retired Address+TMP card
(replaced by the index registers in 2020), the protocard (`docs/system/MACHINE.md`, `hardware/FABRICATED.md`).

Two things the diagram makes visible that are easy to miss:

- **There is no clock on the bus.** The only clock in the machine is on the sequencer-logic card (section 11). Every
  other card is purely combinational plus latches clocked by the strobes it receives, so the timing rules of the whole
  machine are the rules of those strobes (`BUS.md` section 5).
- **The sequencer-memory card is not a bus card.** It talks only to the logic card over the SV1/SV2 ribbon, and the
  logic card's `-BUS-EN` output is the inverse of the memory card's READY line (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1),
  so the bus is released until the ATmega has copied and verified the control store (about 54 s after reset,
  `embedded/sequencer-card/README.md`).

---

## 3. The datapath: ACC, TMP, the ALU card

The ALU card (ALU V3.2, `hardware/cards/alu/eagle/v3.2/ALU V3.2.sch`, netlist model in
`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.4 and `hardware/DESIGN-REVIEW-NOTES-datapath.md` "ALU v3.2") holds the
accumulator and every arithmetic element. Its internal bus is **BDATA0..15**; the accumulator's output is **ACO**;
the selected function's result is **INV-IN0..7**; the accumulator's input is **ACI-DATA**.

### 3.1 The bus side

Two 74LS245 transceivers (IC10 for DATA0..7, IC11 for DATA8..15) join BDATA to the backplane. They are enabled by
`-ALU-FUNC OR -BUS-EN` (IC7) and their direction is set by `-AC-RD`: with `-AC-RD` asserted the card drives the bus,
otherwise it receives. The accumulator reaches BDATA0..7 through IC12 (74LS244, enabled by `-AC-RD`). BDATA8..15 has
nothing on it but the 10 k pull-ups RN2 and the 16-bit zero detector V1. Consequently (this is the fact that decides
several findings):

> Whenever `-ALU-FUNC` and `-AC-RD` are both asserted, the ALU card drives **DATA0..7 = ACC and DATA8..15 = $FF**.
> Without `-AC-RD` the card receives, and the value on the bus (memory, TMP, a register, a port) is what the
> function blocks see as their B operand. (`y1ucemu.c` `compute()`: "the ALU: AC on DATA0..7, pull-ups on DATA8..15".)

### 3.2 The function blocks

A 74LS138 (IC8) decodes `ALU0..2` into one enabled 74LS244 that puts a result onto INV-IN
(`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.4; the codes are the `ALU*` constants in `CodeGen.h`):

| ALU2..0 | Function | Result on INV-IN | Chip |
|---|---|---|---|
| 0 | DATA | BDATA0..7 (pass the operand through) | IC13 |
| 1 | SUB | ACC + NOT(BDATA) + carry-in | IC37 (adder sum), XOR array IC33/IC34 inverts BDATA |
| 2 | AND | ACC AND BDATA | IC20 |
| 3 | OR | ACC OR BDATA | IC23 |
| 4 | XOR | ACC XOR BDATA | IC17 |
| 5 | SHIFT | the 74LS194 shift register's outputs | IC31 |
| 6 | ZERO | 0 (inputs grounded) | IC16 |
| 7 | ADD | ACC + BDATA + carry-in | IC37 |

The adder is a pair of 74LS283 4-bit adders, IC35 (low nibble, carry-in C0 on pin 7) and IC36 (high nibble)
(`ALU V3.2.sch` parts list; `docs/datasheets/7483.pdf` is the closest datasheet in the tree). `ALU3` is the carry
select: with the ADD or SUB code, `ALU3 = 1` feeds the carry flip-flop into C0 (`(ALU3 AND C/SHIFT) XOR SUB`,
datapath review "Carry-in IC35 C0"). That is how ADDIC/ADDTC (`ALUADD | CARRY_SHIFT` = code $F in `accumulator.c`)
differ from ADDI/ADDT (code 7); a plain SUB gets +1 from the XOR (two's complement), a subtract-with-borrow (ALU3 set
with code 1) takes the flag with the right sense. The ALU V3.2 notes record the design change that made this work:
"Flipped AC and BDATA for add/sub circuit: BDATA now goes into xor array, AC directly into adders"
(`hardware/cards/alu/eagle/v3.2/Notes.md`).

Why an inverting path into the accumulator? ACI-DATA is INV-IN either straight (IC3, 74LS244, enabled when
`-AC-LD-INV` is inactive) or inverted (IC2, 74LS240, enabled when `-AC-LD-INV` is asserted). That single bit gives
INVA for free (DATA function with `-AC-RD` so BDATA = ACC, then load inverted: `accumulator.c` INVA) and, because the
same bit also inverts BR-COND (section 3.5), it gives every "not" branch (BRNZ, BRNEQ, BRINL, BR16NZ) for free too.

### 3.3 The accumulator and the carry flip-flop

The accumulator is a 74LS374 (IC5) clocked by `AC-LD = NOT(-AC-LD)` through JP2, so **it latches on the leading
(falling) edge of `-AC-LD`** and captures whatever the function blocks produced from the bus of the *previous* step
(`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.4, 1.6). The generator honours that by always writing the function code one
step before the strobe (`accumulator.c` `aluOp()`: set `-ALU-FUNC` + code, write a line, set `-AC-LD`, write, clear, write).

The carry flip-flop is half of a 74LS74 (IC9A). Its D input is `CO/BO OR SHIFT-OUT` and its clock is
`(function is ADD, SUB or SHIFT) AND AC-LD` (`DESIGN-REVIEW-NOTES-datapath.md` "Carry flip-flop IC9A"). Three
consequences for programmers, all reproduced by `y1ucemu.c` (`do_step()`, the `-AC-LD` block):

1. Logic operations (AND, OR, XOR, DATA, ZERO) **do not touch** the carry: the clock is gated off.
2. `CO/BO` is the adder's carry-out XOR SUB, gated to add/sub only (IC1 pin 10), so **SUB loads the borrow** into the
   same flip-flop (`y1ucemu.c` case 1: `co_bo = carry_out ^ 1`). The instruction-level emulator did not do this
   (review L-7); the microcode is the truth of the machine.
3. Every shift (SHL, SHR, RSHL, RSHR, PSHR, CSHL, CSHR) loads the carry with the bit shifted out, because the
   SHIFT function's `-AC-LD` clocks the flip-flop with SHIFT-OUT as its D input. The ALU notes ask "How to clear
   carry shift? - ADD INSTRUCTION"; the practical idiom is `LDAI 0 / CSHL` (`BACKLOG.md`, C compiler notes).

The flip-flop is cleared by `-RESET` (IC9 CLR), so the carry is defined only after the reset button (section 8).

### 3.4 The shift register and SHIFT-OUT

Two 74LS194s (IC29, IC30) form an 8-bit shifter clocked by `SR-LD = NOT(-SR-LD)` (leading edge of `-SR-LD`). Mode
S1S0 comes from `ALU1,ALU0` and the serial input from a 74LS153 (IC28) selected by `ALU3,ALU2`
(`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.4; `CodeGen.h` SHIFT_* constants):

| ALU1..0 | Mode | ALU3..2 | Serial input |
|---|---|---|---|
| 11 | parallel load from ACC (`SHIFT_LOAD`) | 00 | 0 (`SHIFT_ZERO`) |
| 01 | shift towards bit 7 (`SHIFT_LEFT`) | 01 | the opposite end = rotate (`SHIFT_RING`) |
| 10 | shift towards bit 0 (`SHIFT_RIGHT`) | 10 | bit 7 = arithmetic right (`SHIFT_PROP`) |
| | | 11 | the carry flip-flop (`SHIFT_CARRY`) |

A shift instruction is therefore three strobes (`accumulator.c` `shiftOp()`): `-SR-LD` with mode 11 (load ACC),
`-SR-LD` with the shift mode, then `-AC-LD` with the SHIFT function (code 5) to read the result back. IC9B
(`SHIFT-OUT`) samples the bit about to leave (SRD7 for left, SRD0 for right, chosen by IC32) at each `-SR-LD` edge, and
that is what the carry flip-flop takes on the final `-AC-LD` (`y1ucemu.c` `-SR-LD` block, `shift_out`).

### 3.5 Compare and the branch condition

Two 74LS85 comparators (IC24, IC25, cascaded with the LSB stage seeded pin 2 = GND, pin 3 = VCC, pin 4 = GND) compare
A = BDATA (the operand: TMP0 for BRLT/BREQ/BRGT/BRNEQ) with B = ACC. Two 74HC4078 NORs (V1 on BDATA8..15, V2 on
BDATA0..7) detect zero. A 74LS251 (IC26) selects one condition by `ALU2..0` and the result is XORed with `AC-LD-INV`
(IC27) to make the bus line **BR-COND** (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.4; `CodeGen.h` compare codes):

| ALU2..0 | Mux input | Condition | Used by |
|---|---|---|---|
| 0 | D0 = VCC | always | BR, BRDEV, JSR/RET/INT loads (`ALUBR`) |
| 1 | D1 | BDATA < ACC | BRGT (`ALUGT`) |
| 2 | D2 | BDATA == ACC | BREQ, BRNEQ (inverted) |
| 3 | D3 | BDATA > ACC | BRLT (`ALULT`) |
| 4 | D4 | BDATA0..7 == 0 | BRZ, BRNZ (with `-AC-RD` so BDATA = ACC) |
| 5 | D5 | the bus line IN | BRINH, BRINL |
| 6 | D6 | BDATA0..15 == 0 | BR16Z, BR16NZ (cannot work: H-3) |
| 7 | D7 | the carry flip-flop | BRC |

The comparators are unsigned; the compiler notes that a signed compare needs bit 15 flipped first (`BACKLOG.md`).
The mux's output enable is jumper JP1 (either `-ALU-FUNC` or GND); with JP1 on `-ALU-FUNC` the line floats while the ALU
is idle (datapath review A1), harmless only because every record sets up the function one step before BR-TEST.

### 3.6 TMP0 and TMP1

The two 16-bit temporaries do not live on the ALU card but on the memory card (IC26/IC27 = TMP0, IC28/IC29 = TMP1,
74LS374s with D and Q on the same bus lines; `docs/isa/MICROCODE-REVIEW-NOTES.md` 1.3). They latch on the **leading**
edge of `-TMP-REG-LDn` (through inverter IC14) and their reads drive **all 16** data lines. TMP0 is the programmer's
TMP (MVAT/MVTA/LDTI/LDT/STT, the T-forms of the ALU ops, the compare branches); TMP1 is microcode scratch (LDIVR, PUSHR).
The memory notes ask "Should tmp registers be moved to ALU - I do not see why" (`hardware/cards/memory/eagle/deprecated/v1.3-do-not-use/Notes.md`).
When `-AC-RD` writes ACC into TMP0 (MVAT), TMP0's high byte becomes $FF from the ALU's pull-ups (review section 4).

---

## 4. The register file: R0..R7 on two Index Register cards

Each Index Register card 1.1 (`hardware/cards/register/eagle/v1.1/Index Registers - 1.1.sch`; model in
`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.2 and `DESIGN-REVIEW-NOTES-datapath.md` "Index Register card 1.1") holds four
16-bit registers. Card 0 is R0..R3, card 1 is R4..R7 (`docs/system/MACHINE.md`). A register is four cascaded
74LS192 counters (e.g. R0 = IC3..IC6: low byte IC3/IC4, high byte IC5/IC6), so it can be **loaded** a byte at a time
and **counted** up or down as a 16-bit whole. The schematic, board and BOM name the counters 74LS192 (BCD decade); the
machine executes binary step and address sequences, so the review concludes 74LS193 (binary) must be what is fitted
(`DESIGN-REVIEW-NOTES-control-io.md` 1.2). **To verify:** read the markings on the register-card counters (and the
sequencer's IC33/IC34) and correct the design files.

### 4.1 What the three register-id fields mean

Three 4-bit fields on the bus name registers (`BUS.md`; `main.c` `setRdId()/setLdId()/setAddrId()`):

- `ADDR-REG-ID0..3` (C3–C6): which register drives the **address bus**. IC38 (74LS139) decodes bits 0–1 into
  `-Rn-ADDRSEL`; bits 2–3 select the card through jumper **J3**. The decode is enabled only while `-VMA` (and `-BUS-EN`)
  are asserted, so the address buffers (74LS244 pairs IC41/42, IC17/18, IC27/28, IC49/50) drive ADDR0..15 only during a
  `-VMA` cycle. The generator asserts `-VMA` in every step (section 8.3), so in practice the selected register is on the
  address bus all the time.
- `REG-RD-ID0..3` (B9–B12): which register is **read** (or counted). IC33 decodes bits 0–1 into `-Rn-RDSEL`;
  bits 2–3 select the card through **J1**, gated by `-REG-FUNC-RD` and `-BUS-EN` (`-RDSEL`).
- `REG-LD-ID0..3` (B13–B16): which register is **loaded**. Same structure through **J2** (`-LDSEL`).

All three jumper headers on a card must be set to the same card number, because the microcode uses one register
number for all three purposes (datapath review "Both card-select headers"). Only three bits are ever non-zero (eight
registers); the sequencer notes foresaw it: "If design goes down to 8 registers bit 3 of reg rd and ld can be
repurposed" (`hardware/cards/sequencer-logic/eagle/v2.1/Notes.md`).

### 4.2 The internal bus ADATA and the three transceivers

Reads go through two 74LS244 read buffers per register (R0: IC7 low byte, IC8 high byte) onto the card's 16-bit
internal bus **ADATA0..15**, which has 10 k pull-ups (RN1/RN2). `-REG-RD-LO` enables the low-byte buffer onto
ADATA0..7 and `-REG-RD-HI` the high-byte buffer onto ADATA8..15: **the two read strobes select byte lanes of a
16-bit path, not halves of an 8-bit one**. Three shared 74LS245s join ADATA to the backplane:

| Transceiver | Path | Enabled when |
|---|---|---|
| IC35 | DATA0..7 ↔ ADATA0..7 | exactly one of RDSEL/LDSEL selects this card, `-HL-SWAP` off |
| IC36 | DATA8..15 ↔ ADATA8..15 | same |
| IC37 | DATA0..7 ↔ ADATA8..15 (the byte swap) | exactly one of RDSEL/LDSEL selects this card, `-HL-SWAP` on |

The XNOR that computes "exactly one" is a CD4077 (IC34; the notes say it was chosen as pin-compatible with the 74266,
`register/eagle/v1.1/Notes.md`), a CMOS part driven by LS levels — review finding R1, MED: its 3.5 V input threshold
is above the guaranteed LS high and it adds ~100 ns to every bus turn-around. Direction is `BUS-DIR = NOT(-LDSEL)`:
bus → card when this card is load-selected, card → bus otherwise.

Two behaviours follow that every microcode author has to know:

- **`-REG-FUNC-RD` alone puts the card on the bus.** The transceiver enable does not look at the read strobes, so a
  select with no `-REG-RD-LO/HI` drives the pull-up value $FFFF onto DATA0..15 through two LS245s. Every fetch's
  increment step does this while memory is also driving (review M-1: 327 steps; `y1ucemu.c` counts them as "weak
  pull-up drives", not fights, because the machine demonstrably lives with it).
- **A same-card move happens on ADATA.** When RDSEL and LDSEL both select one card (MOVRR between two registers of the
  same card) the transceivers close and the copy is internal. The swap path is unavailable then (review R3).

`-HL-SWAP` is how a byte gets to the *other* half: MVRHA reads Rn.hi through IC37 onto DATA0..7 for the ALU; MVIW and
MVARH load Rn.hi from DATA0..7; JSR pushes PC.hi by reading it through the swap path (`register.c`, `accumulator.c`,
`branch.c`).

### 4.3 Loads and counts are trailing-edge; loads of R0 are gated

- **Load**: IC1 pin 8 = `-R0-LDSEL OR -REG-LD-LO` → 74LS192 LOAD (low byte), likewise `-REG-LD-HI` for the high byte.
  The 192's LOAD is asynchronous and level-sensitive: the outputs follow ADATA while LOAD is low and keep the value
  present at its rising edge. So **a register takes the value on ADATA at the end of the strobe step**, and the source
  must stay stable through the whole step (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.2; the 2020 diagrams in
  `docs/system/waveforms/REG-LD.json` show exactly this).
- **Count**: IC1 pin 3 = `-R0-RDSEL OR -REG-UP` → UP; pin 6 with `-REG-DN` → DN. A 192 counts on the rising edge of UP
  (or DN) with the other input high, so the count happens **when the strobe ends — or when the register is deselected
  while the strobe is still low** (review R2, MED). The generator's `decrementReg()` writes a select-only step first;
  `incrementReg()` does not, and the author's own comment flags it ("might be an issue if current setRdId reg is
  different", `main.c`). The review scanned all records and found no case where it bites today.
- **R0 is special**: on the sequencer-logic card the bus lines `-REG-LD-LO/-REG-LD-HI` are
  `NOT(N$53 AND LREG-LD-LO/HI)` with `N$53 = (REG-LD-ID != 0) OR branch-taken` (`docs/isa/MICROCODE-REVIEW-NOTES.md`
  1.1; `y1ucemu.c` `do_step()`: "N$53: loads of R0 need the branch-taken latch"). A load whose target is register 0
  reaches the card only after a `BR-TEST` that found `BR-COND` true in the same instruction. That is how a not-taken
  conditional branch leaves the PC alone, and it also means that **MVIB R0, MVIW R0, MVARL/MVARH R0, MOVRR ..,R0,
  POPR R0 and LDR R0 silently do nothing to R0** (review L-6) although the instruction-level emulator performs them.

### 4.4 The register conventions

| Register | Role | Where it is fixed |
|---|---|---|
| R0 | program counter: fetched through, incremented by every fetch, loaded only through the branch path | `CodeGen.h` `#define PC 0`; the N$53 gate |
| R1 | stack pointer: JSR/RET/PUSH*/POP*/INT/IRET address memory through it and count it | `CodeGen.h` `#define SP 1`; the monitor sets it to $0EFF (`monitor.asm` `STACK`) |
| R2 | the hardware's **operand-address register**: LDA/STA/LDT/STT load the 16-bit operand into it, then access memory through it; LDR/STR leave it at addr+2 | `CodeGen.h` `#define IR 2`; review L-9 |
| R3..R7 | general purpose; the monitor's BIOS passes a pointer in R7 and may clobber R5, R6 (`firmware/abi/README.md`); y1cc uses R3 as its accumulator (`BACKLOG.md`) | |

**Programs must never keep anything in R2**: any absolute-addressed load or store overwrites it, and LDR R2 / STR R2
are degenerate (STR R2,addr stores addr at addr; review L-9). With only card 0 fitted, reads of R4..R7 leave the bus
to its pull-ups ($FF) and their loads and counts are lost — the 2026-09-22 bench symptom that `y1ucemu -R 1`
reproduces (`software/ucemu/README.md`). Card 1 was fitted that evening (`docs/system/MACHINE.md`).

Words are big-endian: STR writes the high byte at the address and the low byte at address+1; MVIW's operand is
high byte first; JSR pushes PC.hi then PC.lo at descending addresses (`register.c`, `branch.c`; the emulator agrees).

---

## 5. The instruction cycle: the two sequencer cards

The sequencer is two cards joined by a 2 × 40-pin ribbon (SV1/SV2, MA20-2 headers on both; the control-io review
checked all 80 pins carry the same signal on both cards). Sequencer-memory holds the control store and its loader;
sequencer-logic holds the counters, the instruction register and the pipeline (`hardware/cards/sequencer-*/README.md`).
The model below is `docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1 as executed by `y1ucemu.c`.

### 5.1 Addressing the control store

The control-store address is 14 bits: **CADDR6..13 = the opcode** in the instruction register (IC8/IC9, two
74LS175, buffered by IC15) and **CADDR0..5 = the step** (bits 1..6 of the 8-bit step counter IC33→IC34). Eight
62256 RAMs on the memory half, one per control byte, deliver the 64-bit word; a header `CADDR14` picks which 16K half
of the RAMs is used (control-io review 2 "CADDR14"). So a record is `256 opcodes × 64 steps × 8 bytes`
(`CodeGen.h` INSTRUCTIONS/LINES_PER_INSTRUCTION/BYTES_PER_LINE) and the word for step k of opcode o sits at
`o*512 + k*8` in `test.123` (`MICROCODE.md`).

### 5.2 One step = two clock periods

The gated clock `N$4` drives the step counter's UP input. Bit 0 (QA) is `CNT-CLK`, which clocks the eight pipeline
74LS374s (`BUS-LATCH-CLK`); bits 1..6 are the step address. The control word for step k is therefore latched when the
counter goes from 2k to 2k+1: **each step lasts two clock periods**, and the RAMs get one period to deliver the next
word after CADDR changes. Bit 7 is `COUNT-FAULT`: if a record runs past step 63 the clock stops (IC26→IC31→IC38) and
the machine halts with the last word on the bus (`y1ucemu.c` reports this as "COUNT-FAULT" and exits 4).

`UCODE-COUNT-RESET` is ANDed with the clock and ORed with RESET into the counters' asynchronous clear. The step that
carries it therefore lasts **one** clock period (every strobe in it is half length, review M-7) and step 0 of the next
record lasts three (M-8 explains the ~50 ns race that latches step 0). The emulator counts 2 clocks per step and 1 for
the reset step (`y1ucemu.c` `nclocks`).

### 5.3 The instruction register latches early, so three steps belong to the previous opcode

The IR clocks on `LD-INS-REG AND RUN` at the **leading** edge of `LD-INS-REG`, i.e. ~50 ns into the step that asserts
it. The next pipeline latch already reads `ROM[new opcode, next step]`. So steps 0, 1 and 2 of every record execute
with the *previous* opcode's record, and the fetched opcode's own record takes over at step 3. It works because the
generator writes the same six-step prologue into every record (`main.c` `startInstruction()` + `loadNextInstruction()`):

| Step | Signals (`docs/isa/steps.txt`, any opcode) | What happens |
|---|---|---|
| 0 | `-VMA`, ADDR-REG-ID = 0 | idle (the record's "common word"; instruction $00 adds OUT-OFF) |
| 1 | `-MEM-RD` | memory at [PC] onto DATA0..7 |
| 2 | `-MEM-RD`, `LD-INS-REG` | IR ← DATA0..7 (leading edge: the value of step 1) |
| 3 | `-MEM-RD` | hold; the new record is now being read |
| 4 | `-REG-FUNC-RD`, `-REG-UP`, `-MEM-RD` | PC++ (count at the trailing edge); M-1 weak drive against memory |
| 5 | `-MEM-RD` | hold |

The IR's D inputs come from IC2 (DATA0..7) while `DO-INT` is low or from IC1 (all VCC = $FF) while it is high: that is
how an interrupt substitutes opcode $FF (section 9). RESET clears the IR, so record $00 (START) is the reset vector:
its body is just this prologue with OUT-OFF, i.e. "fetch from PC = 0 and go" (`main.c` `startInstruction(0)`).

Review L-1 shows the prologue could be three steps (the IR has its data at the leading edge of step 2, so steps 3 and 5
hold nothing), worth ~22 % of all executed steps; that change has not been made.

### 5.4 Operand register, two-byte opcodes, branch and interrupt registers

- **Operand register** IC6 (74LS374, `OPERAND-CLK`, leading edge) captures the byte after the opcode. With
  `-2-BYTE-OPERAND-SEL` asserted, IC5 drives `REG-RD-ID0..3 = operand bits 0..3` and `REG-LD-ID0..3 = operand bits 4..7`
  onto the bus in place of the pipeline's fields (IC4). `y1ucemu.c` `compute()`: "sequencer IC5". That matches
  `yacc1.def`: MOVRR's byte is `(dst<<4)|src`, PUSHR/JSRUR/BRUR use the low nibble, POPR uses `reg<<4`.
- **Branch register** IC13 (high byte: D = DATA0..7, Q = DATA8..15, clocked by `BRANCH-LD-HI`) and IC21 (low byte,
  `BRANCH-LD-LO`), both output-enabled by `-BRANCH-RD` which **drives all 16 data lines**. Both bytes are loaded from
  DATA0..7 one at a time, which is why a branch target is fetched as two bytes and why a register can be copied into it
  through the swap path (BRUR, JSRUR).
- **Interrupt vector** IC3/IC10, loaded by `INT-LD-HI/LO` (IADDR), output-enabled by `-INT-JMP`.
- **Branch-taken latch** `N$71` = `((BR-TEST AND BR-COND) OR N$71) AND NOT UCODE-COUNT-RESET`: level-sensitive, any high
  on BR-COND while BR-TEST is high sets it, cleared only at the end of the instruction (`y1ucemu.c` `cond_latch`).
  It feeds the N$53 gate of section 4.3. Unconditional loads of the PC (BR, JSR, RET, IRET, INT, BRVR, BRUR) simply
  assert BR-TEST with ALU code 0 (D0 = VCC).

### 5.5 Halting and stepping

`SOFT-HALT` (the HALT opcode) clocks IC23B (`DO-HALT`) at its leading edge and stops the clock in that very step; the
front-panel CONT clears it and the record continues from the same step (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1).
The front panel also has RESET/EXECUTE (an RS latch, section 8), a SS/WAIT switch that selects free-run or single-step
clocking, a STEP-CLK switch and an SS-SEL header that takes the step clock either from the panel or from JP4 pin 2
(EXTERNAL-SINGLESTEP-CLK); JP4 pin 3 exposes UCODE-COUNT-RESET for an external debugger
(`Sequencer-Logic-Prod-V2.1l.sch` nets; control-io review "Checked, no issue (sequencer logic)").

---

## 6. Memory map

From `hardware/cards/memory/README.md`, `docs/system/MACHINE.md` "Memory card v1.3 settings", `firmware/abi/README.md`,
`firmware/monitor/monitor.asm` and `docs/system/OS-PLAN.md`:

| Range | What | Decided by |
|---|---|---|
| $0000–$7FFF | low RAM (62256 IC1) — always present, cannot be jumpered out (`-LO-RAM` = NAND(NOT BADDR15, VMA); datapath review M4) | memory card |
| $0000–$0FFF | the system page: BASIC variables $0100–$02FF; Y1/OS's four handle buffers $0400–$0BFF while the OS runs (2026-09-23); monitor variables $0F00.. (monmode $0F00, continue_addr $0F02, interupt_cnt $0F04, CFLBA0..2 $0F10–$0F12, ARGBUF $0F40–$0F7F, line_buffer $0F80–$0FFF); the hardware stack grows down from $0EFF (R1), informal floor $0C00 | `monitor.asm` EQUs, `firmware/abi/README.md` |
| $1000–$1FFF | BASIC's token buffer, also where the `O` command loads Y1/OS (the two are not used together) | `firmware/abi/README.md` |
| $3000.. | where y1cc images load and where `G3000` runs them | `docs/system/MACHINE.md` |
| $8000–$CFFF | high RAM (62256 IC2), five 4K blocks jumpered "up" | memory card jumper header U$1 (3 × 8) |
| $D000–$DFFF | no jumper: undecoded on the memory card, reserved for the video card, which claims a 2K block there (low 1K display RAM, upper half the 6845; $D400 address register / $D402 data register once RS moves to A1) | video card SV3 = $D000 |
| $E000–$FFFF | ROM (28C64 IC13, 8K), two blocks jumpered "down": BASIC at $E000 (entry points $E000/$E010/$E020..$E060), monitor at $F000, ISR at $FF90, BIOS vectors $FFC0–$FFF8 (4 bytes each, `JSR routine / RET`) | `monitor.asm`, `firmware/abi/README.md` |

Reading an undecoded block "returns the last value left on the bus" (`docs/system/MACHINE.md`); the memory card's
DATA pull-down networks RN5/RN6 have no value in the design files (datapath review M8), so **To verify:** whether RN5/RN6
are fitted and their value (measure A19 to GND with the card out). The 4K-block jumper idea came from the 1.3 notes
("add jumpers so any 4k block can be removed (for memory map IO)", `hardware/cards/memory/eagle/deprecated/v1.3-do-not-use/Notes.md`).
`OS-PLAN.md` keeps this map for the disk OS (system page, OS at $1000–$4FFF, TPA above) and lists a variant B that
would move the video block up by a jumper.

---

## 7. Reset and the FORCE-ROM boot remap

### 7.1 Reset

`-RESET` (bus C30) is a plain LS04 output on the sequencer-logic card driven by the front-panel latch:
`RESET = NOR(FP-RESET, RUN)`, `RUN = NOR(RESET, FP-EXECUTE)` (control-io review 1.3, datapath review S1). There is no
RC network and no supervisor anywhere: **the machine has no power-on reset**, and until the button is pressed the
things `-RESET` initialises are undefined (S1, MED). Those things are: the IR (IC8/IC9 CLR) and the step counter on
the logic card; all sixteen 74LS192 counters of each register card (CLR via the 4077, `RESET` active high);
the carry and shift-out flip-flops on the ALU (IC9 CLR); the boot flip-flop on the memory card (IC12A PRE);
the 74LS273 latches and the 16550 on the I/O card (`-B-RESET` and `RESET` through the 7406); the 6845's -RES on the
video card. Reset polarity is consistent across the cards (S2). The pipeline itself is **not** cleared: during reset
the 374s keep whatever word they last held, and only the release of reset produces the pulse (`N$32`) that latches
address 0 (1.3, MED — with FORCE-ROM active and `-MEM-WR` a raw `-WE` on the 28C64 this is a way to write the EEPROM;
the ROM was still byte-identical on 2026-09-18).

### 7.2 What the first fetch sees

After reset R0 = $0000, and the IR = $00 so record $00 (START) runs: `-MEM-RD` at [PC]. The memory card's boot logic
(IC12A 74LS74 `FORCE-ROM`, IC11 74LS157) forces BADDR12..15 = 1111 while FORCE-ROM is set, so the block decoder
selects block $F and the EEPROM answers every address: **the CPU's first opcode comes from ROM[$F000]** although the
address bus says $0000 (`hardware/cards/memory/README.md`; `y1ucemu.c` `compute()`: `addr = force_rom ? (a | 0xF000) : a`).
The monitor's first instruction is `BR eprom` to $F003 (`monitor.asm` "remap eprom from 0x0000 to 0xf000 by initial
access to 0xf003 via BRanch"). That fetch presents an address with ADDR15 high while `-VMA` and `-BUS-EN` are asserted,
which clocks D = 0 into IC12A: FORCE-ROM clears and the normal map is in force from then on
(`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.3 "Boot remap"). A stand-alone image therefore needs the same first branch:
the compiler's `--boot` stub and `tests/assembler/brur/brur.asm` (`ORG 0F000H / BR 0F003H`) do it.

Two review findings live here:

- **M1 (HIGH, masked)**: IC12A's clock is `ADDR15 AND VMA AND BUS-EN`. If the address bus floats when `-VMA` falls,
  ADDR15 reads high for the ~40 ns before the register card drives it, and FORCE-ROM clears on the first cycle
  regardless of the address. The designer met this in 2020 by asserting `-VMA` in **every** microcode step
  (`main.c` `initCurrentLine()`: `setSignal("-VMA"); // Hack prevent ROM mapping from triggering`), so the address bus
  never floats while the machine runs — at the price of removing the `-VMA` qualification from every chip select on
  the card (`DESIGN-REVIEW-NOTES-datapath.md` M1).
- **M2 (MED)**: the 28C64's `-WE` is `-MEM-WR` re-buffered, with no write-protect. During FORCE-ROM every address selects
  the ROM block, so a store before the first jump above $8000 would write the EEPROM. The shipped monitor is safe by
  construction (branch first); nothing in hardware enforces it. Status 2026-09-23: open (`DOC-PLAN.md` rule 7).

---

## 8. Interrupts

What exists (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1 "Interrupts", control-io review 1.6, `branch.c`):

| Piece | Where | Behaviour |
|---|---|---|
| `-INT` (bus C13) | driven by the I/O card only: 7406 open collector IC8 pin 12 with RN2 pull-up, from the 16550's INT pin through the INT0 jumper (control-io review "Checked, no issue (IO)"); the logic card can add a 10 k pull-up via its `-INT-PULLUP` header (R5) | the one interrupt source in the machine |
| JP3 on the logic card | 1 × 5 header: pin 3 = `-INT`, pin 2 = `INT-EDGE` (IC23A CLK), pin 4 = `INT-LEVEL` (→ IC36 → IC23A PRE), pins 1/5 = GND | selects edge or level mode; **needs two jumpers** (the unused input to its GND neighbour) or the LS74 preset/clock floats; in edge mode the 74LS74 clocks on the rising edge, i.e. on the *release* of `-INT` (1.6, LOW) |
| pending flip-flop IC23A, enable latch IC22 | logic card | `INT-EN` sets the enable NOR latch; `INT-START` or RESET clear it and clear the pending flip-flop; `DO-INT = pending AND enabled` |
| opcode substitution | IC1/IC2 into the IR | at the next `LD-INS-REG` edge the IR loads $FF instead of the fetched byte (`y1ucemu.c`: `ir = do_int ? 0xFF : data`) |
| `-INTA` (bus C14) | pipelined from IC17 1Q | **never asserted by any record** (review L-8) |
| record $FF INT (30 steps) | `branch.c` "Interrupt handler" | `INT-START` (disable + acknowledge), PC−− (undo the prologue's increment), push PC.hi then PC.lo exactly like JSR, PC ← vector via `-INT-JMP` + BR-TEST/ALU 0 |
| IADDR addr ($FE, 16 steps) | `branch.c` | INT vector ← hi (INT-LD-HI), lo (INT-LD-LO), PC += 2 |
| IRET ($FD, 22 steps) | `branch.c` | RET, then `INT-EN` |
| INTE ($FB) / INTD ($FC) | `branch.c` | one-step `INT-EN` / `INT-START` pulses. INTD therefore also *clears a pending interrupt* (lost, not deferred: M-6) |

The monitor arms it at boot: `iaddr isrcode / INTE` before entering the command loop; the ISR at $FF90 pushes ACC and R7,
blinks the OUT LED `interupt_cnt` (= 5) times, restores and IRETs (`firmware/monitor/monitor.asm` lines 127–128, 1272–1287).
BASIC uses no interrupt instruction (review section 4). The 16550's interrupt enable is never written by the monitor as
far as the setup at $F003 shows (only LCR/DLL/DLM), so **To verify:** whether an interrupt has ever been taken on the
hardware, how JP3 and the IO card's INT0 jumper are populated, and whether the 16550 IER is ever set. Review M-6 adds
that the entry path has no synchroniser: `DO-INT` is asynchronous to the clock and selects the IR's D inputs, so an
interrupt arriving in the set-up window of `LD-INS-REG` can load a mixed opcode. The microcode emulator models the
enable/pending latches and the records but has no source that raises `-INT` (`software/ucemu/README.md` "Not modelled").

---

## 9. Input/output

### 9.1 The port mechanism

The bus carries a static 4-bit port number `IOADDR0..3` (C7–C10) and two strobes `-IO-RD` (B25) and `-IO-WR` (B26);
a third line `-IO-ADDR-LD` (C11) was meant to latch the port number but reaches nothing on the I/O card v1.1
(`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.5, L-2; the generator still asserts it in OUTA/OUTI/INP). The generator writes
the port number into every step of an I/O record (`io.c` `setIo()`), so decode is combinational.

On the I/O card (`hardware/cards/io/eagle/v1.1/IO V1.1.sch`; control-io review 3):

- IC5 (74LS138) decodes `IO-ADDR0..2` into `-IO-SEL0..7`; the `IO-ADDR-HL` 2 × 3 header decides whether `IO-ADDR3`
  must be low or high, i.e. whether the card answers P0–P7 or P8–PF (it is in the low half, `OS-PLAN.md`).
- Two 2 × 8 jumper blocks, `IO-ADDR` and `DATA-ADDR`, pick which `-IO-SELn` becomes `-IO-ADDRSEL` (the **control
  port**) and which becomes `-IO-DATASEL` (the **data port**). In the machine they are P0 and P1 (`firmware/abi/README.md`).
  **To verify:** the jumper positions on the board (the schematic only shows the alternatives).
- The strobes pass through open-collector 7406 inverters (IC8) with pull-ups RN2 (value blank in the design) to become
  `IO-RD`/`IO-WR`; every latch clocks on the trailing edge of `-IO-WR` and every reader drives the bus while `-IO-RD` is
  low. The slow OC rising edge is the slowest path in the machine (review M-3 for INP; 3.2 for a possible double LCD
  write).

### 9.2 The P0 control latch / P1 data convention

P0 is a 74LS273 (IC10) whose bits select the device that P1 talks to (`monitor.asm` equates; `firmware/abi/README.md`;
control-io review 3.3):

| P0 bit | Name | Selects on P1 |
|---|---|---|
| $01 | SWITCHLED | the 8 toggle switches on read (IC3, 74LS244) / the 8 LEDs on write (IC4, 74LS273) |
| $02 | LCDENABLE | the HD44780 LCD E line (write only: R/W is grounded) |
| $04 | LCDREGISTER | LCD register select |
| $08, $10, $20 | UARTA0..A2 | the 16550 register number (register n is selected by writing n × 8) |
| $40 | UARTCS | the 16550's chip select (CS1; CS0 is `-IO-DATASEL`) |
| $80 | TIL311 | the two TIL311 hex displays (IC9 latch) |

So every UART access is two instructions: `OUTI P0,(UARTAn!UARTCS)` then `OUTI/OUTA/INP P1`. The monitor's boot
sequence (`monitor.asm` "SERIAL OUT SETUP") writes LCR = $80 (DLAB), DLL = 3, DLM = 0, LCR = $03. The select bits have
no hardware exclusivity: SWITCHLED and UARTCS set together would make IC3 and the 16550 both drive DATA0..7 on a P1
read (3.3) — a software rule. The emulator implements exactly this latch (`y1ucemu.c` `io_read()/io_write()`:
`ctl & 0x40` → UART register `(ctl >> 3) & 7`; `ctl & 0x01` → switches/LEDs; `ctl & 0x80` → TIL311 with `-L`).

### 9.3 Port map

| Port | Device (`firmware/abi/README.md`, `docs/system/OS-PLAN.md`) |
|---|---|
| P0 | I/O card control latch |
| P1 | I/O card data port for the device selected in P0 |
| P2 | nothing on the hardware (`-IO-SEL2` reaches only the header); the instruction-level emulator's console, and `y1ucemu` keeps it as a second console so `OUTA P2` programs print |
| P3–P7 | `-IO-SEL3..7` on the I/O card's header, unused; reserved to that card |
| P8 | planned: CompactFlash register-select latch (ATA register 0–7 in bits 0–2, bit 3 = CF reset) |
| P9 | planned: CompactFlash data (the ROM driver, `O` command and both emulators already use P8/P9; the hardware is not built: the CF card v1.0 circuit, planned 2026-09-24 onto the memory card, `docs/cards/cf.md`) |
| PA, PB | planned: 6845 address/data on a video card v2 |
| PC–PF | free (PS/2, RTC ... in the plan) |

### 9.4 OUT and IN

Two more bus lines belong to I/O but bypass the port mechanism. `OUT` (C27) is an SR latch on the sequencer-logic card
(IC22) set by the ON opcode's `OUT-ON` and cleared by OFF's `OUT-OFF` (`io.c`); it lights the OUT LED on the I/O card
and on the logic card, and record $00 clears it at reset. `IN` (C26) is driven only by the IN0 toggle switch on the I/O
card through the INPUT0 jumper and read by the ALU's condition mux (D5), so `BRINH`/`BRINL` branch on a front-panel
switch; the monitor uses it at boot ("if INPUT high start the monitor", else run the test code, `monitor.asm`).
`y1ucemu -i 0|1` sets the line and `-I N` flips it (`software/ucemu/README.md`).

---

## 10. The console

The console is the 16550-class UART (XR16C550, IC1 on the I/O card) behind P0/P1, with a MAX232 (IC2) and a DB9 whose
TX/RX can be crossed by a jumper (I/O notes: "add null modem logic to route tx/rx"). The monitor programs divisor 3,
which is 38400 baud only if the UART clock is 1.8432 MHz; the oscillator Y1's Eagle value "ECS-2100AX-200" is a package
name, not a frequency (control-io review 3.1). **To verify:** read the oscillator can and record the frequency in the BOM.

Console I/O goes through the BIOS vectors CHAROUT ($FFC4), UARTIN ($FFE8, which waits and **echoes** the byte, turning
CR into LF) and CONST ($FFF8) (`firmware/abi/README.md`). Inside them `BRDEV` selects the UART on the machine and port 2
on the instruction-level emulator; on the hardware BRDEV is microcoded as an unconditional branch (`branch.c`:
`branch(PC, ALUBR, ...)`), and the microcode emulator takes the same path, so its console *is* the UART model on
stdin/stdout (`y1ucemu.c` header). Loading a program over the console uses the monitor's `E` command (no hex loader
exists yet; `BACKLOG.md` "Monitor loader").

---

## 11. The clock

The machine's clock is on the sequencer-logic card. `QG1` is a 14-pin oscillator socket (Eagle part "XO- 14", value
blank; `Sequencer-Logic-Prod-V2.1l.sch`). Its output goes to IC38 gate C, ANDed with `FREE-RUN`, ORed (IC26 B) with the
single-step path into `UCODE-CLK`, ANDed with `RUN` (IC38 B) and with NOT(`COUNT-FAULT` OR `DO-HALT`) to make `N$4`, the
step counter's UP input (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1; control-io review 1.7). The front-panel SS/WAIT switch
chooses between free-run and single step; the single-step clock is the STEP-CLK switch or the external clock on JP4.

What frequency the machine runs at is not in the tree. Bring-up in 2026-09 used a **function-generator TTL clock in the
oscillator socket (pin 8 clock, pin 7 GND)** (`docs/system/MACHINE.md`, 2026-09-21), and `tests/assembler/romcount`
counted overnight on it; that README quotes "about 0.6 s per count at 1 MHz" as an example, not a measurement. The
review's timing budget (M-2) says the one-step memory windows before the leading-edge latches (LDTI, LDIVR, LDT, the
BRANCH-LD and INT-LD steps) are the first thing to fail, at roughly 6 MHz with the 28C64 in the path.
**To verify:** the oscillator fitted (if any) and the frequency used on the bench.

---

## 12. How a program runs: LDAI then OUTA at the signal level

Take the two-instruction fragment `LDAI $41` / `OUTA P1` — put $41 in the accumulator, then write it to port 1
(with P0 already holding `UARTCS|UARTA0`, that sends 'A' to the UART). Step lists are from `docs/isa/steps.txt`; the
diagrams `docs/isa/LDAI.svg` and `docs/isa/OUTA.svg` draw the same records (with the timing-model caveats in
`MICROCODE.md` section 7). "Edge" notes use the latch table of `docs/isa/MICROCODE-REVIEW-NOTES.md` 1.6.

### LDAI ($0E, 12 steps, `accumulator.c` "load accumulator immediate")

| Step | Word (besides `-VMA`, ADDR-REG-ID = 0) | On the bus / in the latches |
|---|---|---|
| 0 | — | Executed from the *previous* record. R0 (= PC) is on ADDR0..15 because `-VMA` is asserted and ADDR-REG-ID = 0. |
| 1 | `-MEM-RD` | Memory drives M[PC] = $0E onto DATA0..7 (the memory card's LS245 IC5 turns toward the bus). |
| 2 | `-MEM-RD`, `LD-INS-REG` | Leading edge: IR ← $0E. CADDR6..13 now say "LDAI"; the RAMs start reading its record. |
| 3 | `-MEM-RD` | Hold. From here the words come from record $0E. |
| 4 | `-REG-FUNC-RD`, `-REG-UP`, `-MEM-RD` | Card 0 is read-selected with no read strobe: it drives $FFFF against memory (M-1). At the trailing edge the OR of select and `-REG-UP` rises: R0 counts to PC+1. The address bus follows within ~40 ns. |
| 5 | `-MEM-RD` | Memory now drives M[PC+1] = $41. |
| 6 | `-MEM-RD`, `-ALU-FUNC`, ALU = 0 | The ALU's transceivers open in receive (`-AC-RD` off). Function DATA: INV-IN = $41, ACI-DATA = $41 (not inverted). |
| 7 | `-MEM-RD`, `-ALU-FUNC`, `-AC-LD` | Leading edge: ACC ← $41 (the step-6 value). The carry flip-flop's clock is gated off (function 0), so the carry is unchanged. |
| 8 | `-MEM-RD`, `-ALU-FUNC` | Release step (the "set-up, strobe, release" pattern of `aluOp()`). |
| 9 | `-REG-FUNC-RD`, `-REG-UP`, `-MEM-RD`, `-ALU-FUNC` | PC++ again (to PC+2) at the trailing edge; M-1 weak drive again. |
| 10 | `-MEM-RD`, `-ALU-FUNC` | Hold. |
| 11 | `-MEM-RD`, `-ALU-FUNC`, `UCODE-COUNT-RESET` | One clock long: the counter clears; step 0 of the next record (with `-MEM-RD` off) is latched from the ~50 ns pulse. |

The emulator's count for this record is 12 steps and 23 clocks (11 × 2 + 1); the hardware's step 0 is three clocks
long rather than two (M-8). Note how nothing depends on the ALU "finishing": the function blocks are combinational, and
the whole set-up is one step (two clock periods) before the latch.

### OUTA P1 ($61, 12 steps, `io.c` "OUT ACCUM")

| Step | Word (besides `-VMA`, ADDR-REG-ID = 0) | On the bus / in the latches |
|---|---|---|
| 0–5 | the common prologue | Fetch $61 (the IR takes it at step 2), PC++ at step 4. |
| 6 | `-ALU-FUNC`, `-AC-RD`, IOADDR = 1 | The ALU drives DATA0..7 = $41 and DATA8..15 = $FF. The port decoder sees port 1 = `-IO-DATASEL`. `-MEM-RD` is off, so nothing else drives. |
| 7 | + `-IO-ADDR-LD` | No consumer on the card (L-2); a wasted step. |
| 8 | `-ALU-FUNC`, `-AC-RD` | Hold. |
| 9 | + `-IO-WR` | `-IO-WR` low → 7406 → `IO-WR` high (the slow OC edge does not matter for a write). The 16550's IOW is high with CS0 (`-IO-DATASEL`) and CS1 (UARTCS from P0) active. At the **trailing** edge of `-IO-WR` (end of step 9) the UART takes THR = $41 (a 74LS273 latch on the same bus, e.g. the LEDs, would clock here too). |
| 10 | `-ALU-FUNC`, `-AC-RD` | Hold: the data source stays valid one step after the strobe. |
| 11 | + `UCODE-COUNT-RESET` | End (one clock). |

`y1ucemu.c` performs the port write exactly once, at the step where `-IO-WR` is asserted and the next step's word does
not assert it (`do_step()`: "the I/O card's latches clock on the trailing edge, once per assertion"), and it samples a
port read once at the leading edge of `-IO-RD` and holds it (`io_rd_hold`). The review's speed table (section 5 of the
notes) says OUTA could be 7 steps instead of 12; LDAI 8 instead of 12.

---

## 13. Findings that shape the machine, and their status on 2026-09-23

Per `DOC-PLAN.md` rule 7 (`docs/isa/MICROCODE-REVIEW-NOTES.md`, `hardware/DESIGN-REVIEW-NOTES-*.md`, `BACKLOG.md`,
`docs/system/MACHINE.md`):

| ID | One line | Status |
|---|---|---|
| H-1 | PUSHR wrote both stack bytes during a data-bus fight (register card still driving) | **fixed** in `branch.c` 2026-09-22, loaded into the EEPROM the same evening; bench check pending |
| H-2 | BRZ/BRNZ/BR16Z/BR16NZ kept `-AC-RD` on while the PC loaded from the branch register (taken BRZ landed on offset $00) | **fixed** in `branch.c` 2026-09-22, loaded; bench check pending |
| H-3 | BR16Z/BR16NZ cannot work: BDATA8..15 are pull-ups under `-AC-RD` | **open** (nothing uses them) |
| H-4 | 37 opcodes have all-zero records; an all-zero word asserts every active-low line for 61 steps ($80–$8F, $A5, $AE, $C0–$CF, $F8–$FA; $AD is now BRUR) | **open** |
| H-5 | sequencer IC11 gate B appears to drive ADDR-REG-ID0..3 low permanently in the netlist | **To verify** on the board (scope C3 during a PUSH) — the 2026-09-22/23 `romcount` run used only PC-relative addressing plus DECR/BRNZ, so it does not settle it |
| M1 | FORCE-ROM clock races the address drivers; masked by `-VMA` in every step | **open**, masked |
| M2 | 28C64 `-WE` = raw `-MEM-WR`; a store during FORCE-ROM writes the EEPROM | **open** |
| S1 | no power-on reset | **open** |
| 1.1/4.1 | 17 bus lines driven regardless of `-BUS-EN`; the bus tester drives everything push-pull at boot | **open** (v2.2 "CPU off" switch in BACKLOG) |
| 1.2 | counters drawn as 74LS192 (BCD), machine needs binary | **To verify** chip markings |
| video | 6845 data register unreachable (RS = A0); 7416 outputs without pull-ups; E-clock one-shot | **open**, RS-to-A1 fix documented in `hardware/cards/video/docs/fix-6845-register-select.md` |
| ROM | the 2021 monitor's `G` was `BRVR R7` (indirect); rebuilt as `JSRUR R7` in `firmware/rom/shipped/rom` | **resolved** 2026-09-23 (`ROM 2026-09-23` burned) |

---

## 14. The two emulators, briefly

`software/emulator` interprets instructions (it knows what ADDI does) and is the quick one; it differs from the
hardware where the microcode does something else (BRDEV never branches there, carry semantics of SUB and shifts, R0-load suppression: review L-7). `software/ucemu/y1ucemu` loads
`test.hex` and steps the control words through the model described in this document; it is the one that reproduced
H-1 and H-2, runs the monitor from reset and counts bus fights (`software/ucemu/README.md`). When the two disagree,
the microcode emulator is the closer approximation of the machine, and the bench is the truth.
