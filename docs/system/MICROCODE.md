# YACC1 microcode — the control store

What the sequencer plays: the format of the control-store image, the meaning of every one of its 64 bits, how the
sequencer steps through a record, how the generator writes the records, how to add an instruction, how the two
2026-09-22 bus-fight fixes were found and made, and how the image gets into the card.

Written 2026-09-23 from the YACC1-D tree.

Sources: `firmware/microcode/README.md`, `firmware/microcode/yaccsignaldefine.h` and `yaccsignaldata2.h`,
`firmware/microcode/ucode-generator2/` (`main.c`, `controlLine.c`, `CodeGen.h`, `code.h`, `accumulator.c`, `branch.c`,
`io.c`, `memory.c`, `register.c`, `Makefile`), the image files `test.hex` / `test.hexz` / `test.123` / `cache`,
`docs/isa/MICROCODE-REVIEW-NOTES.md` (hardware model and findings), `docs/isa/MICROCODE-REVIEW.md` and `docs/isa/steps.txt`
(the mechanical pass), `docs/isa/README.md` and `docs/isa/*.json` (timing diagrams), `tools/ucode_wavedrom.py`,
`tools/ucode_review.py`, `tools/ucode_send.py`, `software/ucemu/y1ucemu.c` and its README, `software/opcodes.h`,
`software/assembler/yacc1.def`, `tests/assembler/brur/`, `tests/ucemu/`, `embedded/sequencer-card/README.md` and
`sequencer4/Sequencer4.ino`, `tests/sequencer/` (`run.py`, `mock_card.py`, the boot logs), the sequencer schematics
(`hardware/cards/sequencer-logic/eagle/v2.1/*.sch`, `hardware/cards/sequencer-memory/eagle/v2.1/*.sch`, parsed with
Python), `hardware/DESIGN-REVIEW-NOTES-control-io.md`, `docs/system/MACHINE.md`, `BACKLOG.md`.

Conventions: as in `ARCHITECTURE.md` (`-` prefix = active low; **To verify:** marks what the tree does not settle).

---

## 1. The control store in one paragraph

Every opcode is a **record** of 64 **steps**; every step is a 64-bit **control word** stored as 8 bytes. The
sequencer-memory card holds all 256 records in eight 62256 RAMs (IC1..IC8, one per byte), addressed by the opcode
(CADDR6..13) and the step counter (CADDR0..5). The sequencer-logic card latches the word for the current step into
eight 74LS374 pipeline registers and drives their outputs onto the bus (the ones that are bus signals) or into its
own logic (the ones that are not). A step lasts two clock periods; a record ends at the step that carries
`UCODE-COUNT-RESET`. The image is produced by a C program, `ucodegen`, from named signals — nobody writes hex by
hand — and reaches the card's I2C EEPROM over a serial download; at every run-mode boot the card's ATmega copies the
EEPROM into the RAMs, verifies the copy and only then raises READY, which releases `-BUS-EN`
(`firmware/microcode/README.md`, `embedded/sequencer-card/README.md`, `docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1).

Size: 256 × 64 × 8 = 131,072 bytes (`CodeGen.h`: `MEMORY_SIZE = BYTES_PER_LINE*LINES_PER_INSTRUCTION*INSTRUCTIONS`),
exactly the size of `test.123`.

---

## 2. Files and formats

All four images live in `firmware/microcode/ucode-generator2/` and are written by `ucodegen` beside its own executable
(`controlLine.c` `dumpCntlMemory()`, `exe_relative()`; "so a Finder double-click regenerates them here").

| File | Format | Consumers |
|---|---|---|
| `test.123` | raw binary, 131,072 bytes, record-major: byte `b` of step `s` of opcode `o` is at `o*512 + s*8 + b` | `software/disassembler/disasm2` (README) |
| `test.hex` | text, 257 lines: 256 records then a line holding `!` | `y1ucemu` (`load_ucode()`), `tools/ucode_wavedrom.py` (`microcode()`), `tools/ucode_review.py`, `tools/ucode_send.py` (`load_records()`) |
| `test.hexz` | byte-identical to `test.hex` today; the name the Processing loader reads | `embedded/sequencer-card/microcode-loader/simple_microcode_sender_64` |
| `cache` | what was last sent to the card = `test.hex` without the `!` line, plus one blank 257th line (the Processing sender's habit, `ucode_send.py` `load_cache()`); **the card holds this image** | both loaders, for differential sends |

### 2.1 The `test.hex` record

`main.c` documents the record as `"%AIXXXX....XXXX-"`, `controlLine.c` writes it:

```
%  cc  ii  <1024 hex digits = 512 bytes = 64 steps x 8 bytes, step 0 first, byte 0 first>  -
```

- `%` starts a record (`START_CHAR`); `-` ends it (`END_INS_CHAR`); the final line is `!` (`END_ALL`).
- `cc` = the checksum: the 8-bit sum of the 512 data bytes (`checksum += cntlMemory[...]`, an `unsigned char`), written as
  two upper-case hex digits. Every reader ignores it ("Ignore for now"; the card too, `tests/sequencer/mock_card.py`).
- `ii` = the opcode number, two hex digits; `ucode_send.py` refuses an image whose record `i` does not carry number `i`.
- Each line is therefore 1 + 2 + 2 + 1024 + 1 = 1030 characters (`ucode_send.py` `RECORD_LEN + 1`).

`test.hexz` was once the "compressed" variant: the generator writes only the lines a record really used and then pads
with explicit zero bytes to 64 lines (the `Z` end-marker code is commented out in `dumpCntlMemory()`), which is why the
two files are identical today and why every reader still accepts a `Z` as "the rest is zero"
(`y1ucemu.c` `load_ucode()`, `mock_card.py`).

### 2.2 Reading a word by hand

The first record's first line, as the card dumps it at boot (`tests/sequencer/boot-run-mode-2026-09-22-reload.log`,
`Ins=0 LINE:00`) and as `test.hex` holds it:

```
byte:   0  1  2  3  4  5  6  7
        03 D4 FF 00 85 57 03 D1      record $00 step 0
        03 D4 FF 00 85 17 03 D1      record $0E (LDAI) step 0 -- the idle word of every other record
```

With the map of section 3: byte 0 = `03` means bits 0 and 1 set, i.e. `-REG-FUNC-RD` and `-REG-FUNC-LD` **inactive**
(active-low signals are stored as 1 = inactive) and all four `REG-RD-ID` bits and `REG-LD-ID0..1` zero. Byte 2 = `FF`:
none of the eight strobes in that byte (memory, I/O, TMP) is active. Byte 4 = `85` = `1000 0101`: bit 1 is **0**, so
`-VMA` is asserted (the generator's "hack", section 5), `-IO-ADDR-LD`, `-ALU-FUNC`, `-AC-LD-INV` inactive, ALU code 0.
Byte 5 differs between the two records: `57` has bit 6 set = `OUT-OFF` asserted, which only record $00 carries
(`main.c` `startInstruction()`: `if (instruction == 0) setSignal("OUT-OFF")`), while `17` is the plain idle value. Byte 7 =
`D1` = `1101 0001`: `-BRANCH-RD`, `-INT-JMP`, `-2-BYTE-OPERAND-SEL`, `-DEST-ADDR` inactive, the active-high loads zero.
Step 4 of any record reads `02 54 FE ...`: byte 0 bit 0 clear = `-REG-FUNC-RD` asserted, byte 1 bit 7 clear =
`-REG-UP` asserted, byte 2 bit 0 clear = `-MEM-RD` asserted — the PC increment of the fetch.

An all-zero word (H-4, section 5.5) is therefore not "nothing": it asserts every active-low line at once.

---

## 3. The signal map: every control bit

`yaccsignaldefine.h` defines `struct signal { char *name; int chip; int port; int bit; }`; `yaccsignaldata2.h` is the
table. `chip` and `port` are the MCP23017 expander (1..4) and port (0 = A, 1 = B) of the sequencer-memory card's loader,
and the byte index in the image is `(chip - 1) * 2 + port` (`controlLine.c` `bitOn()`; `y1ucemu.c` `resolve_signals()`;
the control-io review checked that this order equals the loader's `writeGPIOAB` byte order and that all 64 bits land on
the RAM pin that reaches the same-named 74LS374 input on the logic card). "Active" follows the name: a `-` name is
asserted by a **0** bit, any other name by a **1** bit (`main.c` `setSignal()/clearSignal()`). Bus pins are from the
V3.2 pinout (`BUS.md`); "internal" means the pipeline output stays on the sequencer-logic card.

### Byte 0 (chip 1, port A) — register selects

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0 | `-REG-FUNC-RD` | 0 | bus B7 | select a register for read / count (the card drives the bus on this alone, ARCHITECTURE 4.2) |
| 1 | `-REG-FUNC-LD` | 0 | bus B8 | select a register for load (card receives) |
| 2 | `REG-RD-ID0` | 1 | bus B9 (via IC4, or IC5 from the operand register) | read/count register number bit 0 |
| 3 | `REG-RD-ID1` | 1 | bus B10 | bit 1 |
| 4 | `REG-RD-ID2` | 1 | bus B11 | bit 2 (card select) |
| 5 | `REG-RD-ID3` | 1 | bus B12 | bit 3 (always 0: eight registers) |
| 6 | `REG-LD-ID0` | 1 | bus B13 | load register number bit 0 |
| 7 | `REG-LD-ID1` | 1 | bus B14 | bit 1 |

### Byte 1 (chip 1, port B) — register strobes

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0 | `REG-LD-ID2` | 1 | bus B15 | load register number bit 2 (card select) |
| 1 | `REG-LD-ID3` | 1 | bus B16 | bit 3 (always 0) |
| 2 | `-REG-RD-LO` | 0 | bus B17 | put the selected register's low byte on ADATA0..7 → DATA0..7 (the swap path carries only the high byte; with `-HL-SWAP` the low byte stays inside the card) |
| 3 | `REG-LD-LO` | 1 | bus B18 as `-REG-LD-LO` (inverted and gated by N$53 on the logic card) | load the low byte at the trailing edge |
| 4 | `-REG-RD-HI` | 0 | bus B19 | put the high byte on ADATA8..15 → DATA8..15, or → DATA0..7 with `-HL-SWAP` |
| 5 | `REG-LD-HI` | 1 | bus B20 as `-REG-LD-HI` (inverted, gated) | load the high byte at the trailing edge |
| 6 | `-REG-DN` | 0 | bus B21 | count the read-selected register down at the trailing edge |
| 7 | `-REG-UP` | 0 | bus B22 | count it up at the trailing edge |

The table's comment "this active low on the bus" on `REG-LD-LO/HI` records the polarity change: the image stores them
active high, the logic card makes the bus lines active low (`-REG-LD-LO = NOT(N$53 AND LREG-LD-LO)`, IC27/IC31;
`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1). The bus-tester's own table (`embedded/libraries/YACC/YACC_Common_header.h`)
lists them as `-REG-LD-LO/HI` because it sees the bus side.

### Byte 2 (chip 2, port A) — memory, I/O and TMP strobes

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0 | `-MEM-RD` | 0 | bus B23 | memory drives DATA0..7 from [ADDR] (with `-VMA`) |
| 1 | `-MEM-WR` | 0 | bus B24 | RAM/EEPROM write; data taken at the trailing edge (`-WE` rising) |
| 2 | `-IO-RD` | 0 | bus B25 | port IOADDR drives DATA0..7 |
| 3 | `-IO-WR` | 0 | bus B26 | port latches clock at the trailing edge |
| 4 | `-TMP-REG-RD0` | 0 | bus B27 | TMP0 drives DATA0..15 |
| 5 | `-TMP-REG-LD0` | 0 | bus B28 | TMP0 ← DATA0..15 at the leading edge |
| 6 | `-TMP-REG-RD1` | 0 | bus B29 | TMP1 drives DATA0..15 |
| 7 | `-TMP-REG-LD1` | 0 | bus B30 | TMP1 ← DATA0..15 at the leading edge |

### Byte 3 (chip 2, port B) — address register and port number

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0..3 | `ADDR-REG-ID0..3` | 1 | bus C3..C6 (via IC18B) | which register drives ADDR0..15; the generator defaults it to PC in every line (`initCurrentLine()`) |
| 4..7 | `IOADDR0..3` | 1 | bus C7..C10 | the port number; written only in I/O records (`io.c` `setIo()`), zero elsewhere |

### Byte 4 (chip 3, port A) — bus cycle qualifier and ALU function

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0 | `-IO-ADDR-LD` | 0 | bus C11 | no consumer on the I/O card v1.1 (review L-2) |
| 1 | `-VMA` | 0 | bus C12 | valid memory address: qualifies the memory card's selects and the register card's address drive; asserted in **every** step |
| 2 | `-ALU-FUNC` | 0 | bus C15 | opens the ALU's bus transceivers (and, with JP1, the condition mux) |
| 3 | `ALU0` | 1 | bus C16 | function / condition / shift-mode code bit 0 |
| 4 | `ALU1` | 1 | bus C17 | bit 1 |
| 5 | `ALU2` | 1 | bus C18 | bit 2 |
| 6 | `ALU3` | 1 | bus C19 | carry-in select (add/sub), shift serial-input select bit 1 |
| 7 | `-AC-LD-INV` | 0 | bus C20 | load the accumulator inverted; also inverts BR-COND |

### Byte 5 (chip 3, port B) — accumulator, shift, branch test, halt, OUT

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0 | `-AC-RD` | 0 | bus C21 | ALU drives DATA0..7 = ACC, DATA8..15 = $FF (needs `-ALU-FUNC`) |
| 1 | `-AC-LD` | 0 | bus C22 | ACC (and, for add/sub/shift, the carry FF) latch at the leading edge |
| 2 | `-SR-LD` | 0 | bus C23 | shift register clocks at the leading edge (mode = ALU1..0) |
| 3 | `BR-TEST` | 1 | internal | while high, a high `BR-COND` (bus C24, from the ALU) sets the branch-taken latch |
| 4 | `-HL-SWAP` | 0 | bus C25 | register card: high byte ↔ DATA0..7 through the swap transceiver |
| 5 | `SOFT-HALT` | 1 | internal | stops the clock in this step (HALT opcode); CONT resumes |
| 6 | `OUT-OFF` | 1 | internal → OUT (bus C27) | clears the OUT latch (OFF opcode; record $00 at reset) |
| 7 | `OUT-ON` | 1 | internal → OUT | sets the OUT latch (ON opcode) |

### Byte 6 (chip 4, port A) — interrupt and sequencer control

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0 | `-INTA` | 0 | bus C14 | interrupt acknowledge: pipelined but **no record asserts it** (review L-8) |
| 1 | `-SRC-ADDR` | 0 | see note | the logic card's IC18A enable takes this from jumper JP1 pin 3, not from the RAM |
| 2 | `INT-LD-HI` | 1 | internal | INT vector high byte ← DATA0..7 (leading edge) |
| 3 | `INT-START` | 1 | internal | clears the interrupt-enable latch and the pending flip-flop (INT, INTD) |
| 4 | `INT-EN` | 1 | internal | sets the interrupt-enable latch (INTE, IRET) |
| 5 | `LD-INS-REG` | 1 | internal | IR ← DATA0..7 at the leading edge (or $FF if an interrupt is pending and enabled) |
| 6 | `UCODE-COUNT-RESET` | 1 | internal (also on JP4 pin 3) | end of record: clears the step counter (this step lasts one clock) and the branch-taken latch |
| 7 | `OPERAND-CLK` | 1 | internal | operand register ← DATA0..7 at the leading edge |

### Byte 7 (chip 4, port B) — branch register, operand select, spare

| Bit | Signal | Active | Where it goes | Meaning |
|---|---|---|---|---|
| 0 | `-BRANCH-RD` | 0 | internal → DATA0..15 | the branch register drives all 16 data lines |
| 1 | `BRANCH-LD-LO` | 1 | internal | branch register low byte ← DATA0..7 (leading edge) |
| 2 | `SPARE3` | 1 | RAM IC5 I/O5 → memory JP1 pin 1 → logic JP1 → IC16 3D; 3Q → JP2 → `-MEM-CPU-RESET` | spare; **every record holds it at 0**, so fitting JP2 would hold the sequencer-memory ATmega in reset (control-io review 1.4) |
| 3 | `BRANCH-LD-HI` | 1 | internal | branch register high byte ← DATA0..7 (leading edge) |
| 4 | `-INT-JMP` | 0 | internal → DATA0..15 | the INT vector register drives all 16 data lines |
| 5 | `INT-LD-LO` | 1 | internal | INT vector low byte ← DATA0..7 |
| 6 | `-2-BYTE-OPERAND-SEL` | 0 | internal (IC5/IC4 enables) | REG-RD-ID = operand bits 0..3 and REG-LD-ID = operand bits 4..7 instead of the pipeline fields |
| 7 | `-DEST-ADDR` | 0 | see note | the logic card's IC11A enable takes this from JP1 pin 4, not from the RAM |

Note on `-SRC-ADDR` / `-DEST-ADDR`: the generator writes the two bits into every word (both inactive, they are in
the table), but on the logic card the pipeline D inputs that carry those names come from the 2 × 2 header JP1
(`USRC-ADDR` pin 3, `UDEST-ADDR` pin 4), whose partner header on the memory card connects only `SPARE3` and
`-MEM-CPU-RESET` (pins 1, 2) in the schematic (`docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1; control-io review 1.1 and 1.4;
`Sequencer-Memory-V2.1.sch` JP1 nets). They would let the operand register's nibbles drive `ADDR-REG-ID` (register-indirect
addressing by operand byte), a path no record and no jumper uses. **To verify:** what, if anything, is fitted on JP1 of
either card.

The commented-out `CADDRn` and `BITxxx` entries at the top and bottom of `yaccsignaldata2.h` are the address lines
(driven by the loader, not stored) and a raw bit-name set from the v1 generator; they are not part of the word.

---

## 4. Sequencing: how a record is played

Details and pin references are in `docs/isa/MICROCODE-REVIEW-NOTES.md` 1.1; `ARCHITECTURE.md` section 5 tells the same
story from the machine's side. The points a microcode author needs:

1. **Address** = opcode (IR, CADDR6..13) : step (counter bits 1..6, CADDR0..5). The counter's bit 0 is the pipeline
   clock, so a step is two clock periods and the RAMs have one period of access time. Bit 7 = `COUNT-FAULT` halts the
   clock: a record without `UCODE-COUNT-RESET` inside 64 steps stops the machine with its last word on the bus
   (`y1ucemu.c` prints `COUNT-FAULT`; `ucode_review.py` rule E1).
2. **`UCODE-COUNT-RESET`** clears the counter asynchronously during the first clock-high of its step: that step is one
   clock long (every strobe in it is half length, M-7) and the next record's step 0 is three clocks long (M-8, a
   ~50 ns race that works with LS parts). The generator always makes the reset step a pure hold step
   (`endInstruction()` writes the current line, then the same line plus the reset bit).
3. **The IR latches at the leading edge of `LD-INS-REG`** (step 1 of the prologue since 2026-09-29, step 2 before),
   so the steps up to and including that one come from the previous opcode's record, and the new record takes over at
   the next step (2; it was 3). Hence the rule the generator enforces by construction: **steps 0..2 are identical in
   every record** (`startInstruction()` + `loadNextInstruction()`; with the six-step prologue it was steps 0..5),
   checked by `tests/ucemu/prologue.py`. Section 5.6 has the prologue step by step.
4. **The two-byte operand path**: `OPERAND-CLK` latches the byte after the opcode; while `-2-BYTE-OPERAND-SEL` is
   asserted IC5 puts `operand[3:0]` on `REG-RD-ID` and `operand[7:4]` on `REG-LD-ID` instead of the pipeline's IC4
   (`y1ucemu.c` `compute()`: `if (on(w, s_two_byte)) { rd_id = operand & 0x0F; ld_id = operand >> 4; }`). MOVRR,
   PUSHR, POPR, JSRUR and BRUR are the users; `yacc1.def` encodes the operand accordingly. The bit is released
   before the record ends, and the moment it is released the pipeline's own (usually zero) fields return — which is
   how PUSHR's high-byte write found itself reading PC (H-1, section 8).
   **While the bit is asserted nothing drives ADDR-REG-ID** (IC18B, the pipeline's field, is enabled by
   `-ONE-OPERAND-SEL`, and the operand paths IC18A/IC11A need `SRC-ADDR`/`DEST-ADDR`, never asserted): no memory access
   may happen in those steps. The lines keep their last value for a short step and drift to 15 (no register, address
   $FFFF) in a long one - POPR read [SP] that way and failed at 1 MHz but not at 6 MHz until 2026-10-10, when it was
   changed to read through TMP1 first. `software/ucemu` models the undriven select (`-O` the old model).
5. **Branch-taken latch and the R0 gate**: `BR-TEST` with `BR-COND` sets a level-sensitive latch that is cleared by
   `UCODE-COUNT-RESET`; loads whose `REG-LD-ID` is 0 reach the register card only while the latch is set. Every
   unconditional PC load therefore carries `BR-TEST` with ALU code 0 (`branch.c` JSR, RET, INT, IRET, BRUR, `branch()`).
6. **Interrupt substitution**: with an interrupt pending and enabled, the IR takes $FF at the next `LD-INS-REG`
   whatever the bus holds; record $FF is the interrupt entry (`ARCHITECTURE.md` section 8).
7. **`-BUS-EN`** = NOT READY: the pipeline's eight 374s and the two CADDR buffers are tri-stated until the memory half
   reports the image loaded. Seventeen other lines are not (control-io review 1.1).

### 4.1 Edge summary (which step's bus a latch sees)

From `docs/isa/MICROCODE-REVIEW-NOTES.md` 1.6, the table that decides where a strobe may sit:

| Destination | Strobe | Takes the value at | So the source must be valid |
|---|---|---|---|
| IR | `LD-INS-REG` | leading edge | in the step **before** the strobe step |
| operand register | `OPERAND-CLK` | leading edge | before |
| branch register hi/lo | `BRANCH-LD-HI/LO` | leading edge | before |
| INT vector hi/lo | `INT-LD-HI/LO` | leading edge | before |
| TMP0/TMP1 | `-TMP-REG-LD0/1` | leading edge | before |
| ACC, carry FF | `-AC-LD` | leading edge | before |
| shift register, shift-out FF | `-SR-LD` | leading edge | before |
| index register byte | `REG-LD-LO/HI` (+`-REG-FUNC-LD`) | trailing edge, level-sensitive | through the whole strobe step |
| index register count | `-REG-UP/-REG-DN` (+`-REG-FUNC-RD`) | trailing edge (rising edge of OR(select, strobe)) | select must not change while the strobe is low |
| RAM/EEPROM write | `-MEM-WR` | trailing edge (`-WE` rising) | through the step, address stable |
| I/O latches | `-IO-WR` | trailing edge | through the step |
| branch-taken latch | `BR-TEST` | level | `BR-COND` stable through the step |
| step counter clear | `UCODE-COUNT-RESET` | first clock-high of the step | (one-clock step) |

The generator's habit of "set-up line, strobe line, release line" (`aluOp()`, `putBustoRegMem()`, `shiftOp()`) is what
satisfies the leading-edge rows without the author having known which edge each part used (the source comments still
ask "rising or falling?", "reg up is rising edge??? are you sure"). Review L-3 lists the release steps that could be
merged with the next set-up because of the leading-edge behaviour.

---

## 5. The generator: `firmware/microcode/ucode-generator2/`

### 5.1 Files

| File | Role |
|---|---|
| `main.c` | the signal primitives (`findSignal`, `setSignal`, `clearSignal`, `initCurrentLine`), the field setters (`setAddrId`, `setRdId`, `setLdId`, `setAlu`, `setIo`), the building blocks (`loadNextInstruction`, `incrementReg`, `decrementReg`, `putMemAtRegOnBus`, `putBustoRegMem`), `startInstruction`/`endInstruction`, and `main()` which walks: record 0, HALT, then `branchInstructions()`, `registerOnlyInstructions()`, `ioInstructions()`, `accumulatorInstructions()`, `doMemory()`, then `dumpCntlMemory()` |
| `controlLine.c` | the memory image `cntlMemory[MEMORY_SIZE]`, the working line `currentLine[8]`, `bitOn/bitOff` (byte = `(chip-1)*2+port`), `writeCurrentLine()` with its duplicate filter and 64-line overflow check, `dumpCntlMemory()` writing the three image files |
| `CodeGen.h` | sizes, the ALU function codes (`ALUDATA 0 .. ALUADD 7`, `CARRY_SHIFT 0x08`), the compare codes (`ALUBR 0 .. ALUCS 7`), the shift modes (`SHIFT_LEFT/RIGHT/LOAD`, `SHIFT_ZERO/RING/PROP/CARRY`), `INVERT`, and the register roles `PC 0`, `SP 1`, `IR 2` |
| `code.h` | prototypes |
| `accumulator.c` | MVRLA/MVRHA/MVARL/MVARH, LDAVR/STAVR, LDAI, INVA, the immediate and TMP forms of ADD/SUB/AND/OR/XOR (+ carry forms), the seven shifts via `shiftOp()`, MVAT/MVTA |
| `branch.c` | `branch()` (the BR family and BRVR), JSR, JSRUR, **BRUR**, RET, PUSH/POP, PUSHR/POPR, IADDR, INT, IRET, INTE, INTD |
| `io.c` | ON/OFF, OUTI Pn, OUTA Pn, INP Pn (16 ports each) |
| `memory.c` | LDIVR Rn |
| `register.c` | DECR/INCR, MVIB, LDTI, MVIW, MOVRR, LDR/STR, LDA/LDT/STA/STT |
| `Makefile` | `make` builds `./ucodegen`; `make check` regenerates into `build/` and diffs against the committed `test.hex`; `make regen` rewrites the three images in place; `Makefile.netbeans` is the old NetBeans build |
| `nbproject/` | the NetBeans project (kept, not needed) |

Includes resolve through the symlink `firmware/opcodes.h → software/opcodes.h` (`tools/layout_links.py`), so the
opcode numbers have one source: `software/opcodes.h` is shared by the generator, the emulators and (via `yacc1.def`)
the assembler.

### 5.2 How a record is written

```c
startInstruction(op);      // startUcodeBlock(op); initCurrentLine(); write line 0 (+ OUT-OFF for op 0)
loadNextInstruction();     // lines 1..5: -MEM-RD at [PC]; LD-INS-REG; hold; PC++ ; hold  (clearSignal("-MEM-RD") is
                           //   applied to the line that follows, so it is the caller's next line that drops -MEM-RD)
initCurrentLine();         // most records: back to the idle word (ADDR-REG-ID = PC, -VMA on, everything else off)
...                        // the body: setSignal/clearSignal/set*Id + writeCurrentLine() per step
endInstruction();          // write the current line, then the same line with UCODE-COUNT-RESET; record the length
```

`initCurrentLine()` is worth reading once: it clears every signal in the table to its inactive value and, inside that
loop, re-applies `setAddrId(PC)` and `setSignal("-VMA")` — the two defaults that are true in every word of the
image. The `-VMA` default carries the comment `// Hack prevent ROM mapping from triggering`: it is the workaround for
the memory card's FORCE-ROM race (`ARCHITECTURE.md` 7.2, datapath review M1).

`writeCurrentLine()` has one surprise: **a line identical to the previous line is not written** ("dup found"), which is
why RSHL is 15 steps where the other shifts are 16 (its mode code 5 equals the SHIFT output code) and why a few family
members differ by one step (review L-5: LDAVR R0, BRVR R0, STR R2, OUTI P0). Harmless, but it means `writeCurrentLine()`
cannot be used to make a deliberate hold step of an unchanged word.

The building blocks and their conventions (all in `main.c`):

- `putMemAtRegOnBus(reg)`: ADDR-REG-ID = reg, `-VMA`, `-MEM-RD`, write one line. The next line is where a leading-edge
  latch may take the data (with one step of access time: review M-2 lists the records where that is tight).
- `putBustoRegMem(reg, source)`: ADDR-REG-ID = reg, `-VMA`, assert the source, write; `-MEM-WR`, write; release
  `-MEM-WR`, write; release the source, write. One set-up, one strobe, one hold — the pattern the memory card needs
  (1.3). The source is a *name* (`"-AC-RD"`, `"-TMP-REG-RD1"`, `"-REG-RD-HI"`), so the caller must have arranged any
  other enable the source needs (`-ALU-FUNC` for the accumulator, `-REG-FUNC-RD` + the id for a register).
- `incrementReg(reg)`: id + `-REG-FUNC-RD` + `-REG-UP` in one line, then both released in the next. The count happens at
  the trailing edge; the author's comment "might be an issue if current setRdId reg is different from one here" is the
  register card's R2 hazard (deselecting while the strobe is low counts the deselected register). `decrementReg()`
  writes a select-only line first.
- `aluOp(func)` (`accumulator.c`): `-ALU-FUNC` + code, write; `-AC-LD`, write; release, write.
- `branch(reg, mode, invert, source)` (`branch.c`): fetch the two target bytes through `BRANCH-LD-HI` then
  `BRANCH-LD-LO` (each with its own PC increment), drop `-MEM-RD`, set up the condition (`-AC-RD` for `SOURCE_AC`,
  `-TMP-REG-RD0` for `SOURCE_TMP`, `-ALU-FUNC`, ALU = mode, `-AC-LD-INV` if inverted), `BR-TEST`, release the test
  **and the source**, `-BRANCH-RD`, `-REG-FUNC-LD` with LD-ID = PC, `REG-LD-LO` + `REG-LD-HI`, release. The 2026-09-22
  fix lives in the "release the source" line (section 8).

### 5.3 Building, checking, regenerating

```
cd firmware/microcode/ucode-generator2
make            # builds ./ucodegen
make check      # generates into build/ and reports "test.hex: IDENTICAL to the committed microcode image" or fails
make regen      # rewrites test.123 / test.hex / test.hexz here (what the loaders send)
```

`make check` is the regression test for any change to the generator: it must say IDENTICAL until you mean it to
differ, and when it differs, `docs/isa/steps.txt` (regenerated by `tools/ucode_review.py`) shows exactly which
records and steps moved. The program prints a "dup found" line for each filtered duplicate and "Done".

### 5.4 Records that are never written

**Fixed 2026-09-29 (H-4):** after generating every instruction, `main()` gives each record still all-zero the HALT
record (`haltRecord()`, the same code as HALT $03: the fetch, then `SOFT-HALT`), so a stray fetch of $A5, $AE or
$F8-$FA stops the machine cleanly with the PC past the byte (CONT resumes at the next one) instead of the storm
described below; both emulators also stop on an undefined opcode. Exactly those 5 records changed; `tests/ucemu/undefined.py`
(in `make check`) requires no all-zero record and runs each on the model: HALT after 7 steps, 0 bus fights (the old
image: 124 fights, then COUNT-FAULT). Not yet in the EEPROM: it goes in with the next `ucode_send.py --all`. The
history:

`main()` never emits $A5 (BRNC was planned), $AE and $F8–$FA: **5 all-zero records** remain in `test.hex` since
2026-09-24 (38 before BRUR filled $AD on 2026-09-22; 37 until `LDZ`/`STZ`/`ADDIW`/`SHL16` filled $80–$8F and $C0–$CF,
where OUTVR and LDTVR/STTVR had never had microcode — section 7a). Because active-low signals are stored as
1 = inactive, an all-zero word asserts `-REG-FUNC-RD, -REG-FUNC-LD, -REG-RD-LO/HI, -REG-UP, -REG-DN, -MEM-RD, -MEM-WR,
-IO-RD, -IO-WR, -TMP-REG-RD0/1, -TMP-REG-LD0/1, -ALU-FUNC, -AC-LD-INV, -AC-RD, -AC-LD, -SR-LD, -HL-SWAP, -BRANCH-RD,
-INT-JMP, -2-BYTE-OPERAND-SEL, -INTA` and `-VMA` together; fetching such an opcode runs steps 3..63 of that storm until
`COUNT-FAULT` stops the clock (review H-4, HIGH; fixed 2026-09-29, above). (Until 2026-09-24 the assembler would emit LDTVR/STTVR/OUTVR
and the instruction-level emulator ran LDTVR/STTVR, so a program that worked there could do this on the hardware; those
mnemonics are gone.) The review
proposed filling every unwritten record with the idle word plus `UCODE-COUNT-RESET` (an illegal opcode becomes a
one-byte NOP) or with `SOFT-HALT`; the halt was chosen so a stray fetch is seen, not silently skipped.

### 5.5 Record lengths

Steps per record with the microcode of 2026-09-29 (the three-step fetch prologue, section 5.6, and the idle-step pass,
section 5.7), with the count before those changes in brackets (families as their R0 member; `docs/isa/README.md`
has the diagrams; the undefined opcodes are HALT's record, section 5.4):

| Steps | Opcodes (steps before 2026-09-29: six-step prologue, idle steps) |
|---|---|
| 4 | START (8) |
| 5 | ON (8), OFF (8), HALT (8) |
| 6 | INCR (9), DECR (10), INTE (9), INTD (9) |
| 7 | MVAT (10), MVRLA (10), MVRHA (10), INVA (10) |
| 8 | MVTA (11), LDAVR (10), ORT (11), ANDT (11), XORT (11) |
| 9 | LDTI (11), MVARL (12), MVARH (12), STAVR (12), OUTA (12), INP (12) |
| 10 | POP (13), LDAI (12), MVIB (12), OUTI (13), ORI (12), ANDI (12), XORI (12), ADDT (13), SUBT (13), ADDTC (13) |
| 11 | LDIVR (15) |
| 12 | PUSH (15), ADDI (14), SUBI (14), RSHL (15), ADDIC (14) |
| 13 | SHL (16), SHR (16), RSHR (16), PSHR (16), CSHL (16), CSHR (16), IADDR (16) |
| 14 | MOVRR (17) |
| 15 | MVIW (17) |
| 17 | RET (20), LDT (21), STT (22) |
| 18 | BR (21), BRZ (21), BRNZ (21), BRINH (21), BRINL (21), BRC (21), BRLT (21), BREQ (21), BRGT (21), BRNEQ (21), BR16Z (21), BR16NZ (21), BRUR (20), BRDEV (21), BRVR (21), LDA (22) |
| 19 | STA (23), IRET (22) |
| 24 | POPR (28) |
| 26 | PUSHR (33), LDZ (30), LDR (30), INT (30) |
| 27 | STZ (31) |
| 28 | JSR (31), STR (32) |
| 30 | JSRUR (32) |
| 32 | SHL16 (35) |
| 42 | ADDIW (46) |

Summed over the 85 opcodes of `software/opcodes.h`: 1,434 steps before, 1,226 after the prologue, 1,173 after the
idle steps (-18 %). A record of N steps takes 2N - 1 clocks (the reset step is one clock, M-7). `tests/ucemu/run.py`'s
`xisa` program: 2,621,365 clocks -> 2,157,017 (prologue) -> 2,089,999 (idle steps); `os/kermit_io.asm`'s wait loop
191 -> 161 -> 153 clocks.

Review section 5 estimates ~30 % of executed steps removable (22 % from the six-step prologue alone) and gives a
per-opcode "achievable" column. Applied: the three-step prologue (L-1, section 5.6) and the idle steps that can go
(S1, section 5.7). Still open: `-IO-ADDR-LD` (L-2) and the hold steps that are not idle (below). M-1 is fixed
everywhere (section 5.6).

### 5.6 The fetch prologue (three steps since 2026-09-29)

Every record starts with the fetch of the next opcode (`loadNextInstruction()`). Until 2026-09-29 it took six steps:
0 idle, 1 `-MEM-RD`, 2 + `LD-INS-REG`, 3 `-MEM-RD` hold, 4 PC++ with `-MEM-RD` still on, 5 release with `-MEM-RD`.
Steps 3 and 5 did nothing a latch needed, and step 4 had the memory card's LS245 driving the opcode against the
register card's LS245s driving $FFFF (`-REG-FUNC-RD` without a read strobe) - review M-1, in every instruction. The
review's L-1 proposed three steps, and that is what the generator writes now:

| Step | Signals | Why |
|---|---|---|
| 0 | `-MEM-RD`, ADDR = PC | the opcode on the bus; step 0 is three clocks long (it follows the one-clock reset step) |
| 1 | `-MEM-RD`, `LD-INS-REG` | the IR takes, at this step's **leading** edge, what step 0 left on the bus; `-MEM-RD` stays on through the step as hold time |
| 2 | `-REG-FUNC-RD`, `-REG-UP`, RD-ID = PC | PC++ when `-REG-UP` rises at the end of the step; no `-MEM-RD`: the register card's $FFFF drives alone (no M-1) |
| (3) | release: step 2 without `-REG-UP`/`-REG-FUNC-RD` | only in 55 records, below |

Why it is safe:
- **Records change hands at step 2.** The IR changes early in step 1, so the words of steps 0 and 1 are read from the
  previous opcode's record and the new record's from step 2 (section 4, rule 3). All three steps are the same in every
  record (START, $00, also has `OUT-OFF` in every step, as always: a flip-flop set, harmless a step late).
- **Memory time** is unchanged where it matters: the address has been on the bus since the previous record (the
  `-VMA` hack keeps ADDR-REG-ID = PC driven; after a taken branch the PC was loaded at least 2.5 steps before the IR's
  edge), and `-MEM-RD` is on for the three clocks of step 0 before the edge.
- **The count edge.** A 74LS192 counts when (select OR `-REG-UP`) rises (section 1.2 of the review notes). The old
  release step dropped `-REG-UP` and `-REG-FUNC-RD` together with the selection unchanged. Now the record's first body
  step follows step 2 directly, which is the same thing as long as that step keeps REG-RD-ID = PC and asserts no
  `-REG-UP`, `-REG-DN` or `-2-BYTE-OPERAND-SEL`; otherwise the register selection could change while `-REG-UP` is
  still low, and a decoder glitch would count another register. `writeCurrentLine()` checks the first body line and,
  for the 55 records where it does not qualify (a first body step that selects another register or counts: MVRLA/MVRHA
  and INCR/DECR of R1-R7, INCR R0, RET/POP/IRET's `SP++`, LDZ/STZ's read of R6, SHL16), writes the old release step in
  front of it (`releaseIfNeeded()` in `main.c`).
- **No latch reads the prologue's bus.** In the six-step prologue, step 5 was a read at the new PC, and a body whose
  first line was also "`-MEM-RD` at PC" merged into it (the generator drops a line equal to the one before). Every
  body sets up its own read now; `tests/ucemu/prologue.py` checks that no first body line holds a leading-edge latch.
  That lost merge is why 153 records save two steps rather than three.

**Checked** on the microcode emulator (`software/ucemu`, which applies the leading/trailing-edge model of section 4):
the compiler suite and `--xisa` (23/23 each), the emulated bench (`isa`'s byte stream), romcount, romdiag, video,
monload, cfcard and kermit (timeouts recalibrated: `os/kermit_io.asm` PPS 5229 -> 6203), with 0 bus fights wherever
the run counts them; the OS sessions (32/32 on both emulators), the native tool chain and the disassembler pass too, and
`make check` is green. The self-host's estimate at 1 MHz went from 31 h 45 min to 26 h 51 min for both stages (27.4
clocks an instruction on the microcode emulator's native session against 32.4). `make prologue6` in the generator folder builds the image as it was before this and the M-1 change below
(byte-identical to the one committed before the change, `-DPROLOGUE6`) for loading in two stages or going back:
`python3 tools/ucode_send.py --all --hex firmware/microcode/ucode-generator2/build/p6/test.hex`.

**M-1 in the operand fetches** (the same day, after the prologue). 116 steps in 78 records (LDAI and the other
immediates, MVIB/MVIW, the branches, JSR, LDA/STA/LDT/STT, STR, LDZ's R2++, RET/POPR/IRET's SP++, BRVR's Rn++)
incremented a register with `-MEM-RD` still on: the same LS245-against-$FFFF overlap. The pattern everywhere is read,
latch (or level load), hold, increment, then read the next byte at the new address; nothing uses the bus of the
increment step. `writeCurrentLine()` now writes any line that counts a register without `-MEM-RD` (`m1Mask()` in
`main.c`) and leaves `-MEM-RD` in the current line, so the next step reads as before. Exactly those 116 steps changed,
by that one bit; no record changed length (it is an electrical fix, not a speed one). `tests/ucemu/prologue.py` rule 5
checks the whole store: no count step with `-MEM-RD` (500 count steps), and no leading-edge latch right after one (it
would take the $FFFF).

---

### 5.7 Idle steps (2026-09-29)

`tools/ucode_review.py` rule S1 counts the steps where nothing is asserted but `-VMA`: 259 after the prologue change.
The generator's set-up / strobe / release pattern leaves one between many pairs of steps. Taking one out makes its
neighbours P and N adjacent, so what P switches off and N switches on happen on the same edge - harmless unless an edge
needs that step. `removeIdleSteps()` in `main.c` runs after every record is written and keeps an idle step when:

| Rule | Why the step is needed |
|---|---|
| P ends REG-LD-LO/HI, `-MEM-WR` or `-IO-WR` | the hold after a trailing-edge strobe (74LS192 LOAD is level-sensitive; a write needs address and data stable past its end) |
| N has a leading-edge latch (IR, operand, branch, INT, TMP, AC, shift register) | the latch takes the previous step's bus: it would take P's instead |
| N loads or writes | selects, address and data settle a step before the strobe |
| P counts and N changes REG-RD-ID or `-2-BYTE-OPERAND-SEL` | the count edge would meet a register-selection change: a decoder glitch counts another register (the rule of section 5.6) |
| N counts and its register selection is not P's, or P counts too | the same glitch at the start; two counts would merge into one |
| `-2-BYTE-OPERAND-SEL` starts in N | it replaces the ID fields: a selection change |
| I/O (`-IO-RD` pops the UART's FIFO, `-IO-ADDR-LD`), `BR-TEST` (level-sampled), INT-EN/INT-START/`-INTA`, SOFT-HALT in P or N; OUT-ON/OUT-OFF in the step but not in P and N (ON, OFF) | actions left as they were |
| N is the reset step with anything but the reset bit | M-7: its strobes would be one clock long |
| the step's selection fields (ADDR-REG-ID, REG-RD-ID, REG-LD-ID, ALU, IOADDR) are neither P's nor N's | it is a set-up step of its own |

One data-bus driver switching off and another on at the same edge (review A3, a few ns of overlap) is allowed; the
machine already does it at many boundaries, the fetch's step 1 -> 2 among them. The prologue (steps 0-2) is never
touched. The pass removes one step at a time and re-checks the new neighbours.

**Result**: 152 of the 259 removed, 107 kept (68 count-edge releases, 28 before a count whose selection is not yet
stable, the rest next to I/O, `BR-TEST`, INT or halt actions, and ON/OFF's OUT step). 82 records save one step, 31 two,
one three and one five (PUSHR, 31 -> 26). Compiled code gains ~3 % on top of the prologue's ~18 %.

**Checked**: `tests/ucemu/idle.py` builds the generator with `-DKEEPIDLE` (the records before the pass, byte-identical
to the image committed before it, `d7af02a`) and checks, with its own copy of the rules, that every record is that
record minus idle steps, that every removal satisfies the rules, that the prologue is untouched, and that no idle step
left would pass them. `make check` on the emulators (the native session: 27.4 -> 26.1 clocks an instruction); `os/kermit_io.asm` recalibrated (PPS 6528: 1,000,176 clocks a
second, 217 clocks a received character). `make prologue6` still builds `b98aec2`'s image.

**Not done**: hold steps that are not idle - e.g. LDTI's step after its TMP latch, which keeps `-MEM-RD` a second
step although the latch took its data at the leading edge of the step before. Those need a per-signal decision
(hold time of each latch) rather than a pattern rule.

## 6. Reading the timing diagrams (`docs/isa/`)

`tools/ucode_wavedrom.py --all` (`make isa`) writes one WaveDrom diagram per opcode in `firmware/opcodes.h`:
`docs/isa/<MNEMONIC>.json` (source) and `.svg` (picture), plus the index `docs/isa/README.md`. Control rows are read
straight from `test.hex` and grouped (bus cycle, registers, ALU/accumulator, branch/interrupt, sequencer/misc); rows for
signals that never change in the record are omitted. The last rows (ADDRESS BUS, DATA BUS, IR, ACC, PC) are **modelled**,
not read: the tool's `TIMING` constants place them as fractions of a step (`pipe` 0.05, `reg` 0.12, `mem` 0.30,
`latch` 0.00), and every diagram's footer says so. Register families are drawn once, for R2 ("R0 is the PC and would
show it being overwritten").

Known inaccuracies of that model, from `docs/isa/MICROCODE-REVIEW-NOTES.md` section 6 (to fold into the tool when the
diagrams are next regenerated, `BACKLOG.md`):

- `latch = 0.00` ("loads take effect at the trailing edge") is wrong for the IR, operand, branch, INT, TMP, ACC and
  shift registers: they take the **leading** edge, i.e. the previous step's bus (section 4.1).
- The reset step and step 0 are drawn equal in length; the hardware makes them one and three clock periods.
- `-REG-RD-LO`/`-REG-RD-HI` are drawn on one 8-bit bus; the data bus is 16 bits wide at the register cards, the TMP
  registers and the branch/INT registers.
- The data bus is drawn idle during increment steps although the register card drives $FFFF there (M-1).

The textual form is easier for review: `docs/isa/steps.txt` lists every asserted signal of every step of every record
(`tools/ucode_review.py` writes it together with `docs/isa/MICROCODE-REVIEW.md`). The step tables in
`ARCHITECTURE.md` section 12 were read from it.

### 6.1 The review tool

`tools/ucode_review.py` runs rules W1–W3 (write strobes vs address/data changes and `-VMA`), R1 (read and write
together), R2 (two or more data-bus drivers in a step), L1/L2 (loads with no driver / driver appearing in the same
step), I1 (counting the register on the address bus during a write), E1/E2 (no reset within 64 steps / dead steps
after it) and S1 (idle steps). Totals on 2026-09-22: `L1 8, R2 3, S1 359` (`docs/isa/MICROCODE-REVIEW.md`); before the
fixes R2 was 37 (`software/ucemu/README.md`). The review notes list the tool's blind spots (section 6): R2 should treat
`-REG-RD-LO` + `-REG-RD-HI` as byte lanes, add `-INT-JMP` to `DATA_DRIVERS`, and — the one that would have caught H-1,
H-2 and M-1 — count the register card as a driver whenever `-REG-FUNC-RD` selects a card that `-REG-FUNC-LD` does not,
and the ALU whenever `-AC-RD` and `-ALU-FUNC` are both on. E1 should run over all 256 records, not only the non-empty
ones (H-4).

---

## 7. Worked example: adding BRUR Rn ($AD) on 2026-09-22

`BRUR Rn` is "branch to the address in Rn" — PC ← Rn, nothing pushed, Rn unchanged — the direct counterpart of the
existing `BRVR Rn`, which is an *indirect* jump (PC ← the word at [Rn], Rn += 2; review section 3 found the
instruction-level emulator wrong about that). It was added because the monitor's `G` command and the C compiler's
jump tables needed a plain register jump (`docs/system/MACHINE.md`, `BACKLOG.md` "C compiler"). The places touched:

1. **`software/opcodes.h`**: `#define BRUR 0xAD` — a hole in the map ($AD had no record; H-4) with a comment
   "BRUR Rn = PC <- Rn (2 bytes, register in the operand byte like JSRUR)".
2. **`software/assembler/yacc1.def`** line 89: `BRUR \{regs}` — the two-byte form, register number in the operand byte.
3. **`branch.c`**: a new block after JSRUR. It is JSRUR without the "save pc to stack" part, and its steps
   (`docs/isa/steps.txt`, `docs/isa/BRUR.svg`) read, as built that day with the six-step prologue (since 2026-09-29
   the body starts at step 3 with its own read step; section 5.6):

   | Step | Signals | Why |
   |---|---|---|
   | 0–5 | prologue | fetch $AD, PC++ |
   | 6 | `-MEM-RD`, `OPERAND-CLK` | operand register ← the byte at [PC] (leading edge: memory was driving since step 5, one step of access) |
   | 7 | `-REG-FUNC-RD`, `-MEM-RD` | select PC for the count |
   | 8 | `-REG-FUNC-RD`, `-REG-UP` | PC++ past the operand (`-MEM-RD` dropped first) |
   | 9 | `-REG-FUNC-RD`, `-REG-RD-HI`, `-HL-SWAP`, `-2-BYTE-OPERAND-SEL` | REG-RD-ID = operand[3:0] = n; Rn.hi through the swap transceiver onto DATA0..7 |
   | 10 | + `BRANCH-LD-HI` | branch register high byte ← DATA0..7 (leading edge: step 9's value) |
   | 11 | as 9 | release step |
   | 12 | `-REG-FUNC-RD`, `-REG-RD-LO`, `-2-BYTE-OPERAND-SEL` | Rn.lo onto DATA0..7 (straight path) |
   | 13 | + `BRANCH-LD-LO` | branch register low byte ← DATA0..7 |
   | 14 | as 12 | release step |
   | 15 | idle | **everything released** — `-REG-RD-LO`, `-2-BYTE-OPERAND-SEL` and `-REG-FUNC-RD` in one line, so the register card is off the bus before the branch register drives it (the H-1 lesson) |
   | 16 | `-BRANCH-RD`, `-ALU-FUNC`, ALU = 0, `BR-TEST`, `-REG-FUNC-LD`, LD-ID = PC | the target on DATA0..15; condition "always"; the branch-taken latch sets; card 0 load-selected (receive) |
   | 17 | + `REG-LD-LO`, `REG-LD-HI` | PC ← branch register at the trailing edge (allowed for R0 because the latch is set) |
   | 18 | as 16 | hold |
   | 19 | + `UCODE-COUNT-RESET` | end: 20 steps |

   The generator code is the JSRUR text with the stack block deleted and the release of `-REG-FUNC-RD` added at
   step 15 (JSRUR releases it later, with its own comment "suspect, glitch?").
4. **Both emulators**: the instruction-level `software/emulator` was patched to execute $AD (`tools/patched_files.txt`);
   `y1ucemu` needed nothing — it runs whatever record $AD holds.
5. **The test** `tests/assembler/brur/brur.asm`: a plain `BRUR R5`, a jump through an address fetched from a table, and a
   four-way dispatch driven by a counter; expected console output `ABC0123` then HALT, 89 instructions. It starts
   with the boot stub (`ORG 0F000H / BR 0F003H / MVIW R1,0EFFH / JSR main`) so it also runs from reset on `y1ucemu`;
   `tests/ucemu/run.py` includes it in the suite.
6. **Regenerate and load**: `make regen`, then `make check` (identical to itself), `tools/ucode_review.py` for the new
   `steps.txt`/diagrams, and `tools/ucode_send.py --all` to the card (section 9). The C compiler had a `--no-brur`
   switch for the interval between the generator change and the reload (`BACKLOG.md`).

What remains: **bench-check on the hardware** — the register-to-branch-register path (`-REG-RD-HI/LO` + `-HL-SWAP` into
`BRANCH-LD-HI/LO` under `-2-BYTE-OPERAND-SEL`) is the same one JSRUR uses and had not been exercised on the machine
before (`tests/assembler/brur/README.md`, `BACKLOG.md`). The reload changed six records ($07 PUSHR, $A1/$A2/$AB/$AC the H-2 branches, $AD BRUR): `tools/ucode_send.py
--dry-run` against the loader's cache listed exactly those on 2026-09-22 before the load (the "14 records" once in
`docs/system/MACHINE.md` was an estimate made before the images were compared; corrected).

## 7a. LDZ/STZ, ADDIW, SHL16 (2026-09-24)

Four register families for the C compiler's `--xisa` code (`docs/programming/ISA-REFERENCE.md` section 4a), in the
32 opcodes that had never had microcode. The same places were touched as for BRUR: `software/opcodes.h` (LDZ $80, STZ
$88, ADDIW $C0, SHL16 $C8; OUTVR/LDTVR/STTVR removed), `yacc1.def`, the interpreter, and the generator:

- `register.c`: LDR's and STR's second halves (from "R2 holds the address" to the end) became `loadRegFromIR()` and
  `storeRegAtIR()`, the same lines in the same order, so $E8–$F7 did not change by a bit. `zpageAddress()` builds the
  address from the page register `ZP` = R6 (`CodeGen.h`):

  (Step numbers as built with the six-step prologue; since 2026-09-29 the body is three steps earlier, section 5.6.)

  | Step (LDZ R3) | Signals | Why |
  |---|---|---|
  | 0–5 | prologue | fetch $83, PC++ |
  | 6 | `-REG-FUNC-RD`, RD-ID = 6, `-REG-RD-HI`, `-REG-FUNC-LD`, LD-ID = 2 | R6.hi on card 1's high lane → DATA8..15 (straight transceivers, card 1 only read-selected); card 0 only load-selected: DATA → ADATA |
  | 7 | + `REG-LD-HI` | R2.hi ← DATA8..15 at the trailing edge (level-sensitive load: the source was set up a step before) |
  | 8 | as 6 | hold one step after the strobe |
  | 9 | idle | everything released before memory drives the bus |
  | 10–14 | `-MEM-RD` (address = PC), `-REG-FUNC-LD`, `REG-LD-LO` | R2.lo ← the offset byte (as LDR's second address byte) |
  | 15–16 | `-REG-UP` on R0 | PC past the operand |
  | 17–29 | LDR's own steps 17–29 | Rn.hi ← [R2] (swap path), R2++, Rn.lo ← [R2], `UCODE-COUNT-RESET` |

  No `-HL-SWAP` in steps 6–8: it is one bus line that both cards see, and both ends of this move use the high lane.
  The unread low lane of card 1 drives the pull-ups' $FF onto DATA0..7 while nothing else drives it (the ucemu counts
  it as a weak drive, not a fight). The 16-bit cross-card path is the one every `MOVRR R3,R4` of compiled C uses,
  which `tests/bench` has run on the machine.
- `accumulator.c`: `ADDIW` fetches w.hi into TMP1, then ACC ← Rn.lo, `aluOp(ALUADD)` with w.lo from memory, Rn.lo ←
  ACC, PC++, ACC ← Rn.hi, TMP1 on the bus and `aluOp(ALUADD | CARRY_SHIFT)`, Rn.hi ← ACC (46 steps). `SHL16` loads each
  byte of Rn into ACC and adds it again from the register, which keeps driving the bus through `aluOp` (35 steps).
  `-MEM-RD` is released before every PC increment and before ACC drives the bus. Each add goes through `aluOp()`, so
  SHIFT-OUT is cleared first (the 2026-09-23 carry fix) and only register moves separate the low add from the high one.
- Result: exactly the 32 records $80–$8F and $C0–$CF differ from the image in the EEPROM (`cache`); `tests/ucemu/isa.asm`
  checks every family on both emulators (0 bus fights, the same bytes); `docs/isa/` and `MICROCODE-REVIEW.md` were
  regenerated. **Still to do at the machine**: `tools/ucode_send.py --all`, then `tests/bench/run.py --port ...` (`isa`
  and `xisa`).

---

## 8. H-1 and H-2: lessons about bus-release ordering

Both findings (`docs/isa/MICROCODE-REVIEW-NOTES.md` section 2, HIGH) are the same mistake seen twice: a driver that
was needed *earlier* in the record is still enabled when a *different* driver is needed, and two LS outputs fight on
the data bus at the moment a latch or a memory write takes the value. The review found them by reading the netlists
(who drives the bus under which signals) and the step listings; `software/ucemu` then reproduced both on 2026-09-22
and the fixes were made in `branch.c` the same day.

### 8.1 What a bus fight is, and how the emulator counts one

Two totem-pole TTL outputs on one line with different values: the low output sinks the high one's current and the
line sits at a low-ish level, roughly 0.5–1.5 V, which every input reads as **0** — so the practical outcome is the
AND of the drivers (`y1ucemu -F and`, the default: "a low output wins, the lane is the AND of its drivers"). The
emulator's `compute()` collects the drivers of each byte lane every step (memory, I/O, TMP0/1, the branch and INT
registers, the register cards, the ALU) and notes a fight when two of them disagree; the register card's pull-up value
under a bare `-REG-FUNC-RD` is counted separately as a *weak drive*, because 327 steps of the image do that and the
machine lives with it (M-1). `-F src` is the alternative hypothesis (the ALU's drive loses to anything) that would
explain how the monitor could ever have printed a string on the old image; it was never confirmed on a scope
(`docs/system/MACHINE.md` item 6: "worth one scope look at DATA0 during a taken BRZ").

### 8.2 H-2: BRZ/BRNZ/BR16Z/BR16NZ loaded the PC while the ALU was still driving

`branch()` sets up the condition for the AC-sourced tests with `-AC-RD` (so that BDATA = ACC for the zero detector).
It cleared `-TMP-REG-RD0` for the TMP-sourced tests before `-BRANCH-RD` — the author's own comment says why: "problem
will conflict with data transfer of branch reg to PC" — but never cleared `-AC-RD`. So from step 16 the ALU drove
DATA0..7 = ACC and DATA8..15 = $FF against the branch register's 16 lines while `REG-LD-LO/HI` loaded the PC at step 18.
A taken BRZ has ACC = 0 by definition: PC.lo ← target.lo AND $00 = $00. On the emulator the monitor's `puts` loop
never terminated (`software/ucemu/README.md`). The fix is one symmetrical line:

```c
    if (source == SOURCE_TMP) clearSignal("-TMP-REG-RD0");   // existed
    if (source == SOURCE_AC)  clearSignal("-AC-RD");         // added 2026-09-22 (H-2)
    writeCurrentLine();
```

The condition latch had already been set at BR-TEST (step 14), so releasing the ALU at step 15 loses nothing; steps
15–20 of BRZ now read `-ALU-FUNC` without `-AC-RD` (`steps.txt`). Records $A1, $A2, $AB, $AC changed. H-3 stays: BR16Z /
BR16NZ test BDATA8..15, which under `-AC-RD` are pull-ups, so they can never work as microcoded (nothing uses them).

### 8.3 H-1: PUSHR wrote the stack while the register card was still driving

PUSHR moves the register's bytes through TMP1 (the ISA's push order is hi then lo at descending addresses). The
original record read Rn.hi through the swap path into TMP1 (steps 10–12), then released `-2-BYTE-OPERAND-SEL` — but
not `-REG-FUNC-RD`, `-REG-RD-HI` or `-HL-SWAP`. With the operand select gone, `REG-RD-ID` fell back to the pipeline's
field (0 = PC), so during the write of TMP1 to [SP] the register card was driving **PC.hi** onto DATA0..7 through the
swap transceiver; the second write had the same shape with SP.lo/SP.hi driven on all 16 lines. `PUSHR R3` with
R3 = $ABCD pushed $21CC on the model; PUSHR is used 4 times in the monitor and 34 in BASIC. The fix, in two places:

```c
    clearSignal("-2-BYTE-OPERAND-SEL");
    clearSignal("-REG-RD-HI");        // H-1: release the card before the write
    clearSignal("-REG-FUNC-RD");
    clearSignal("-HL-SWAP");
    writeCurrentLine();
    putBustoRegMem(SP, "-TMP-REG-RD1");
```

and likewise `-REG-RD-LO` / `-REG-FUNC-RD` before the second write. PUSHR is now 33 steps (steps 13 and 24 are the new
release steps, `steps.txt`); review section 5 notes it could be 18 by writing the register straight from the card as
JSR does, which would also remove the TMP1 detour.

### 8.4 The rules that fall out

1. **Know who drives on what.** Memory drives on `-MEM-RD` + `-VMA`; a port on `-IO-RD`; TMPn on `-TMP-REG-RDn` (16
   lines); the branch and INT registers on `-BRANCH-RD` / `-INT-JMP` (16 lines); the ALU on `-ALU-FUNC` + `-AC-RD` (ACC
   on 0..7, $FF on 8..15); **a register card on `-REG-FUNC-RD` alone** unless `-REG-FUNC-LD` selects the same card.
   Exactly one of these per lane per step.
2. **Release before you switch.** A driver stays enabled until its signal is cleared; `-2-BYTE-OPERAND-SEL` going away
   does not disable anything, it only changes *which* register the card drives.
3. **Think in edges.** The leading-edge latches (section 4.1) have their data one step before the strobe; the release
   step after them is free for the next set-up. Register loads, memory writes and I/O writes need the source through
   the whole strobe step.
4. **The condition latch remembers.** Once `BR-TEST` has sampled `BR-COND`, the ALU can let go of the bus; the PC load
   only needs `-REG-FUNC-LD`, the id and the branch register.
5. **Check with the model before the bench**: `make check` to see what moved, `tools/ucode_review.py` for the mechanical
   rules, `y1ucemu -x -m -f prog.img -w` for the fights, `tests/ucemu/run.py` for the compiler suite, then
   `tests/assembler/*` on the hardware.

Status on 2026-09-23 (`DOC-PLAN.md` rule 7): H-1 and H-2 **fixed in the generator and loaded** into the EEPROM on
2026-09-22 (`tools/ucode_send.py --all`); `tests/ucemu/isa.asm`, the compiler suite and the monitor from reset run with
0 fights over 6 million steps on the model; the bench checks (`tests/assembler/brur`, `isa.asm`'s byte stream, then the
monitor from ROM) are pending. H-3 open; H-4 open (fixed in the generator 2026-09-29, section 5.4); M-1 fixed in the generator 2026-09-29 (the fetch
by the three-step prologue, the 116 operand-fetch steps by `m1Mask()`; section 5.6), loaded 2026-10-04: with the
six-step prologue a $00 read back wrong at 13 addresses in $3E00-$3FFF (`tests/bench/diag/zero_readback.py`), with
M-1 fixed at none, and `tests/bench` passes 15/15.

---

## 9. Loading the card

### 9.1 The sequencer-memory card's firmware: Sequencer4

`embedded/sequencer-card/sequencer4/` (flashed 2026-09-21; `embedded/sequencer-card/README.md`) runs on the card's
ATmega328P (IC15, 16 MHz crystal Q1) and talks to five MCP23017 expanders over I2C at 400 kHz: IC10 (address 0x20,
the CADDR lines) and IC14/IC13/IC11/IC12 (0x21..0x24, the four data pairs = the eight RAM bytes); the RAM control
lines `-CMEMSEL/-CMEMRD/-CMEMWR` come straight from the ATmega's PB2/PB1/PB0 (control-io review 2). The control-store
EEPROM is a 24Cxx in socket IC9 (on-board part at I2C 0x57); in the machine an adaptor in IC9 carries two 24Cxx at
I2C devices 6 and 7 (`docs/system/MACHINE.md`, `hardware/FABRICATED.md`). Two switches and three LEDs set and show the mode
(`Sequencer4.ino`):

| Control | Pin | Meaning |
|---|---|---|
| `UCODESWITCH` (the UCODE slide switch) | A0 | 0 = **DOWNLOAD** (receive an image over serial into the EEPROM), 1 = **WRITEMEM** (run mode: copy EEPROM → RAM, verify, raise READY) |
| `STARTSWITCH` (START button) | A2, default high | in DOWNLOAD mode, pressing it starts listening |
| `LOADING` LED | 13 | blinks while copying / verifying |
| `READY` LED | 12 | on when the RAM holds the verified image |
| `FAULT` LED | 11 | blink codes: 5 = unexpected character in the download, 6 = RAM verify failed (READY never rises) |
| `READYLINE` | D7 → `BUS-READY` → SV1 pin 12 → logic card IC36 → `-BUS-EN` | releases the pipeline onto the bus |

Also on the card: the `CADDR14` header (jumper off = upper 16K of the RAMs, on = lower; load and run use the same half),
JP2 (EEPROM WP to GND/VCC), the FTDI header JP3, the `LOCAL-CPU-RESET` button, and two solder jumpers `DTR-RESET`
(dead-ends: flashing needs the button) and `FTDI-VCC` (would parallel the FTDI's 5 V with the backplane if closed while
on the bus) — control-io review 2.2.

**Run-mode boot** (`loop()`, `mode == WRITEMEM`): "Write Memory" → "EEPROM to RAM", 256 instructions copied in 32-byte
EEPROM reads (16 s measured) → "Verify RAM against EEPROM", every byte compared (29 s) → on success the card dumps
instructions 0, 1, 7, 124 and 255 as 64 lines of 8 bytes each (`dumpInstruction()`), sets the RAM to read/selected,
switches its address and data pins to inputs, raises READY and prints "RAM copy complete and verified, READY!!!" at
about 54 s → then a monitor loop that prints `RAW=.. Addr=.. Seq=.. Ins=.. Line=.. Data=` whenever the CPU moves to a
new (instruction, step) address, once a second, so a stepping machine can be watched from the serial console. On a
mismatch it prints the counts and the hint "is -BUS-EN inactive? (the logic card drives the microcode address lines when
it is asserted)" and stops with FAULT blinking 6: the 2026-09-21 boots taken while the bus tester still asserted
`-BUS-EN` dumped all-zero RAM for exactly that reason (`embedded/sequencer-card/README.md`; the logs in
`tests/sequencer/boot-run-mode-2026-09-21*.log`). Sequencer3, the previous firmware, did the copy in 156 s with no
verification (`deprecated/sequencer3`).

### 9.2 The download protocol and `tools/ucode_send.py`

In DOWNLOAD mode, after START, the card speaks (`download.ino`, mirrored by `tests/sequencer/mock_card.py`):

```
card:  >>            a prompt before every instruction (then it flashes a LED for 100 ms before reading)
host:  %ccii<1024 hex digits>       one record; the trailing '-' of test.hex is NOT sent; 'Z' = the rest is zero
...
host:  !             end of the download
```

The card ignores the checksum, reads exactly 512 byte values, writes them into the EEPROM in page writes and prompts
again; a stray character is "Unexpected Char" (FAULT ×5). `tools/ucode_send.py` (2026-09-22) replaces the Processing
sketch `simple_microcode_sender_64` and speaks the same protocol at 115200 baud:

```
tools/ucode_send.py [--port /dev/cu.usbserial-XXXX] [--all] [--dry-run] [--delay MS] [--hex FILE] [--cache FILE]
tools/ucode_send.py --boot-check [--port ...] [--log FILE]
```

- Only the records that differ from `cache` are sent (`--all` ignores the cache; `--dry-run` lists what would go), and
  the cache is rewritten record by record, so an interrupted load resumes on re-run.
- Two timing facts the Processing sketch met by its 25 ms/char pace: opening the FTDI port resets the ATmega (DTR), so
  **run the sender first and press START after it says it is waiting**; and after every `>>` the sender waits
  `--settle` ms (default 250) because the card's 64-byte serial buffer would lose the head of a record sent during its
  100 ms LED flash (seen 2026-09-22 at 1 ms/char).
- Procedure on the card (`ucode_send.py` docstring): UCODESWITCH to DOWNLOAD, reset the card (LOADING on), press START;
  afterwards UCODESWITCH back to run and reset: the boot copies and verifies (READY after ~54 s).
- `--boot-check` captures that run-mode transcript and compares the five dumped instructions with `test.hex`
  (`check_dumps()`).

`tests/sequencer/run.py` exercises the sender without hardware against `mock_card.py` on a pseudo-terminal: a
differential send of four altered records plus one never sent, a `--all` send of all 256, and the `--boot-check`
comparison against the 2026-09-21 transcript (in which only the pre-fix PUSHR record may differ). The 2026-09-22 reload
transcript (`boot-run-mode-2026-09-22-reload.log`) shows RAM == EEPROM for all 256 instructions and the `Ins=7` dump
with the fixed PUSHR.

### 9.3 What the card holds

`cache` == `test.hex` since the 2026-09-22 evening reload with `--all` (`firmware/microcode/README.md`): BRUR at $AD, the
H-2 fix in $A1/$A2/$AB/$AC, the H-1 fix in $07. The RAM copy was verified at that boot. The EEPROM had been verified
against the previous image on 2026-09-21 by the same five-instruction dump (`docs/system/MACHINE.md` "What is loaded").

---

## 10. Glossary of the vocabulary used above

| Term | Meaning here |
|---|---|
| record | the 64-step microprogram of one opcode (`startUcodeBlock`/`endUcodeBlock`) |
| step, line | one 8-byte control word; "line" is the generator's word (`writeCurrentLine`), "step" the hardware's (CADDR0..5) |
| word | the 64 control bits of a step |
| prologue | steps 0..2 (0..5 until 2026-09-29), identical in every record: fetch the opcode and increment the PC (section 5.6) |
| leading / trailing edge | the falling / rising edge of an active-low strobe, i.e. the start / end of the step that asserts it |
| set-up, strobe, release | the generator's three-line pattern around every strobe |
| bus fight | two drivers with different values on one data lane in one step (`y1ucemu -w`) |
| weak drive | the register card's pull-up $FFFF under a bare `-REG-FUNC-RD` (M-1), counted but not a fight |
| family | the eight (Rn) or sixteen (Pn) records generated by one loop, identical except for the select fields |
