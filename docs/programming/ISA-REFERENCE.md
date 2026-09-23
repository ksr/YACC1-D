# YACC1 instruction set reference

Every opcode of the YACC1: encoding, size, microcode step count, what it does, and the traps. Written 2026-09-23
from the YACC1-D tree.

Sources: `software/opcodes.h` (the opcode numbers; `firmware/opcodes.h` is the same file), `software/assembler/yacc1.def`
(mnemonic syntax and byte encoding), `firmware/microcode/ucode-generator2/{main,branch,register,accumulator,io,memory}.c`
and `CodeGen.h` (what each instruction does at the microcode level — **the source of truth for semantics**),
`docs/isa/steps.txt` (every control step of every record, regenerated 2026-09-22 18:30 after the H-1/H-2 fixes) and
`docs/isa/README.md` (the timing-diagram index), `docs/isa/MICROCODE-REVIEW-NOTES.md` and `MICROCODE-REVIEW.md` (the
hardware model and the findings H-1..H-5, M-1..M-8, L-1..L-9), `software/emulator/main.c` (the instruction-level
emulator) and `software/ucemu/y1ucemu.c` (the microcode-level emulator), `firmware/monitor/monitor.asm` (usage
idioms). A scratch assembly of the encodings below was checked with `software/assembler/asm` on 2026-09-23.

## 1. How to read this document

- **Opcode**: the byte in `opcodes.h`. A *family* opcode carries a register or port number in its low bits:
  `MVIB Rn` is `$10 | n` (n = 0..7), `OUTA Pn` is `$60 | n` (n = 0..15). The tables list the base value; the
  index in section 10 lists every byte.
- **Operands** follow the mnemonic as `yacc1.def` spells them: `Rn` = `R0`..`R7`, `Pn` = `P0`..`P9`, `PA`..`PF`,
  `byte` = an 8-bit value, `addr` = a 16-bit value (assembled high byte first). Where an operand goes into its own
  byte the table says which nibble.
- **Bytes**: instruction length including operands.
- **Steps**: microcode steps of the record as generated (counted from `docs/isa/steps.txt`, one line per step). Every
  record begins with the same 6-step fetch prologue (`main.c` `startInstruction` + `loadNextInstruction`: read the
  opcode into the instruction register, increment R0) and ends with a `UCODE-COUNT-RESET` step. A step is two clock
  periods and the reset step one, so an N-step instruction costs 2N−1 clocks (`y1ucemu.c` header, review note 1.1).
  Family members differ by at most one step (duplicate-line elision, review L-5); the table gives the common value
  and the notes the exception.
- **Carry** means the ALU card's carry flip-flop. It is clocked only when the ALU function is ADD, SUB or SHIFT
  (review 1.4, IC9A), so logic operations, moves, loads and stores leave it alone.
- "Interpreter" below means `software/emulator` (it interprets opcodes); "ucemu" means `software/ucemu` (it runs the
  microcode). Where they differ from each other or from the hardware, the note says so.

Register numbers in the operand byte of `MOVRR`/`PUSHR`/`POPR`/`JSRUR`/`BRUR` are taken from the byte by the
sequencer's operand register with `-2-BYTE-OPERAND-SEL` (review 1.1): the low nibble becomes `REG-RD-ID`, the high
nibble `REG-LD-ID`. That is why `POPR` encodes its register as `n<<4` and `MOVRR` as `(dst<<4)|src`.

## 2. The instruction cycle in brief

Each record's steps 0..5 fetch the next opcode: the address bus follows R0, `-MEM-RD` puts the byte on the bus,
`LD-INS-REG` latches it into the instruction register, `-REG-UP` increments R0 (`main.c` `loadNextInstruction`).
Because the instruction register changes early in the `LD-INS-REG` step, steps 0..2 of every record are actually
executed from the *previous* opcode's record; the generator makes those steps identical everywhere so it does not
matter (review 1.1). Operand bytes are then read the same way (address = R0, `-MEM-RD`, R0++), and the work happens
in the steps that follow. Nothing is pipelined across instructions.

## 3. Loads and stores (ACC, TMP and memory)

| Opcode | Mnemonic | Bytes | Steps | Description |
|---|---|---|---|---|
| $0E | `LDAI byte` | 2 | 12 | ACC ← byte |
| $0D | `LDTI byte` | 2 | 11 | TMP ← byte |
| $40+n | `LDAVR Rn` | 1 | 11 (R0: 10) | ACC ← [Rn] (the byte at the address in Rn; Rn unchanged) |
| $48+n | `STAVR Rn` | 1 | 12 | [Rn] ← ACC |
| $E4 | `LDA addr` | 3 | 22 | R2 ← addr; ACC ← [R2] |
| $E5 | `STA addr` | 3 | 23 | R2 ← addr; [R2] ← ACC |
| $E6 | `LDT addr` | 3 | 21 | R2 ← addr; TMP ← [R2] |
| $E7 | `STT addr` | 3 | 22 | R2 ← addr; [R2] ← TMP |
| $D0+n | `LDIVR Rn,byte` | 2 | 15 | [Rn] ← byte (through TMP1) |
| $C0+n | `LDTVR Rn` | 1 | — | **no microcode** (TMP ← [Rn] on the interpreter only) |
| $C8+n | `STTVR Rn` | 1 | — | **no microcode** ([Rn] ← TMP on the interpreter only) |

Notes:

- **`LDA`/`STA`/`LDT`/`STT` clobber R2.** The generator loads the operand address into register `IR` = R2
  (`register.c`: `setLdId(IR)`, `putMemAtRegOnBus(IR)`) and leaves it there. The interpreter uses a hidden ninth
  register for the same purpose (`main.c`: `#define IR 8 //HACK`), so a program that keeps a value in R2 works on
  the interpreter and fails on the machine and on ucemu. Rule: never use R2 (`software/compiler/README.md`,
  `tests/assembler/romcount/romcount.asm`).
- `LDAVR`/`STAVR` are the only byte accesses through a general register; there is no auto-increment — pair them with
  `INCR Rn`. The monitor's `stringout` is the idiom: `LDAVR R7 / BRZ done / JSR uartout / INCR R7 / BR loop`.
- `LDIVR Rn,byte` goes through TMP1, the memory card's second temporary register (`memory.c`), so TMP (= TMP0) is
  preserved. `LDIVR R0,byte` would write the byte over the next instruction — do not.
- `LDTVR`/`STTVR` ($C0..$CF) have all-zero microcode records (review H-4): on the machine an all-zero control word
  asserts every active-low strobe at once for 61 steps until `COUNT-FAULT` stops the clock. The assembler accepts the
  mnemonics and the interpreter executes them; ucemu and the hardware do not. Neither the monitor nor BASIC uses them.
- Hazard on the machine: a store into $E000–$FFFF reaches the 28C64's `-WE` (`BACKLOG.md`, design review MED: "28C64
  -WE is raw -MEM-WR"), i.e. it can program the EEPROM. The interpreter exits with `Rom Write` on any write above
  $DFFF (`main.c` `memory_write`); ucemu ignores writes above $E000 (`software/ucemu/README.md`).
- `LDT` loads all 16 bits of TMP0 from the bus, but memory drives only DATA0..7; the high byte is whatever the bus
  pull-ups give and nothing reads it (review 1.3, 1.4).

## 4. Register moves and counts

| Opcode | Mnemonic | Bytes | Steps | Description |
|---|---|---|---|---|
| $0F | `MOVRR Rs,Rd` | 2 | 17 | Rd ← Rs (16 bits). Operand byte = `(d<<4) \| s` |
| $10+n | `MVIB Rn,byte` | 2 | 12 | Rn.lo ← byte (high byte unchanged) |
| $18+n | `MVIW Rn,addr` | 3 | 17 | Rn ← addr (high byte first, then low) |
| $20+n | `MVRLA Rn` | 1 | 10 | ACC ← Rn.lo |
| $28+n | `MVRHA Rn` | 1 | 10 | ACC ← Rn.hi |
| $30+n | `MVARL Rn` | 1 | 12 | Rn.lo ← ACC |
| $38+n | `MVARH Rn` | 1 | 12 | Rn.hi ← ACC |
| $0B | `MVAT` | 1 | 10 | TMP ← ACC |
| $0C | `MVTA` | 1 | 11 | ACC ← TMP |
| $F0+n | `LDR Rn,addr` | 3 | 30 | R2 ← addr; Rn.hi ← [R2]; Rn.lo ← [R2+1]; R2 ← addr+2 |
| $E8+n | `STR Rn,addr` | 3 | 32 (R2: 31) | R2 ← addr; [R2] ← Rn.hi; [R2+1] ← Rn.lo; R2 ← addr+2 |
| $50+n | `INCR Rn` | 1 | 9 | Rn ← Rn+1 |
| $58+n | `DECR Rn` | 1 | 10 | Rn ← Rn−1 |

Notes:

- **`MOVRR` operand order is source first, destination second** (`yacc1.def`: `MOVRR \{regs},\{regs}` → `0F |2<4|1`,
  i.e. the second operand shifted into the high nibble, the first in the low; the sequencer feeds the low nibble to
  `REG-RD-ID` and the high nibble to `REG-LD-ID`, review 1.1). The monitor's `MOVRR r0,r7 / jsr showaddr` prints R0.
  The interpreter agrees (`main.c`: `src = reg & 0x0f; dest = (reg >> 4) & 0x0f`).
- `INCR`/`DECR` are 16-bit counts on the 74LS192 chain (review 1.2); they are the only 16-bit arithmetic the machine
  has. `INCR R0`/`DECR R0` move the PC (the fetch prologue relies on `INCR`-like steps), so they are usable only as a
  deliberate skip. The monitor's delay loops are `DECR R7 / MVRHA R7 / BRNZ loop`.
- `LDR`/`STR` are the 16-bit variable access of the C compiler (one 3-byte instruction per scalar,
  `software/compiler/README.md`). Both leave R2 = addr+2. `LDR R2,addr` and `STR R2,addr` are degenerate (review
  L-9): `STR R2,addr` stores `addr` itself at `addr`; `LDR R2,addr` reads its second byte from the value it just
  loaded plus one.
- **Loads whose target is R0 are silently suppressed on the hardware** unless a taken branch test preceded them in
  the same instruction (review 1.1 and L-6, the `N$53` gate on `-REG-LD-LO/HI`): `MVIB R0`, `MVIW R0`, `MVARL R0`,
  `MVARH R0`, `MOVRR Rs,R0`, `POPR R0` (the SP still advances by 2), `LDR R0,addr` (R2 still advances). ucemu models
  the gate; the interpreter performs the load. Jump through a register with `BRUR`/`JSRUR` instead.
- `MVRHA`/`MVARH` reach the high byte through the register card's swap transceiver (`-HL-SWAP`, `accumulator.c`);
  `tests/assembler/romdiag` stages 2–3 check exactly this path (expected `20` then `11` from `MVIW R3,2011H`).
- `MVAT` puts ACC on DATA0..7 with $FF on DATA8..15 (`-AC-RD` drives all 16 lines, review 1.4), so TMP0's high byte
  becomes $FF; harmless, nothing reads it.
- `yacc1.def` lists `R8` and `R9` in the register class. They are not registers: `INCR R8` assembles to `$58` =
  `DECR R0`, `MVIB R8,b` to `$18` = `MVIW R0`'s first byte, and so on. Never write R8/R9.

## 5. The stack, calls and returns

| Opcode | Mnemonic | Bytes | Steps | Description |
|---|---|---|---|---|
| $04 | `JSR addr` | 3 | 31 | push PC (hi at [R1], R1−−, lo at [R1], R1−−); PC ← addr |
| $05 | `RET` | 1 | 20 | R1++; PC.lo ← [R1]; R1++; PC.hi ← [R1] |
| $06 | `JSRUR Rn` | 2 | 32 | push PC (as `JSR`); PC ← Rn. Operand byte = n (low nibble) |
| $07 | `PUSHR Rn` | 2 | 33 | [R1] ← Rn.hi; R1−−; [R1] ← Rn.lo; R1−−. Operand byte = n (low nibble) |
| $08 | `POPR Rn` | 2 | 28 | R1++; Rn.lo ← [R1]; R1++; Rn.hi ← [R1]. Operand byte = n<<4 (high nibble) |
| $09 | `PUSH` | 1 | 15 | [R1] ← ACC; R1−− |
| $0A | `POP` | 1 | 13 | R1++; ACC ← [R1] |

Notes:

- The pushed PC is the address of the instruction after the `JSR`/`JSRUR` (R0 was incremented past the operands
  before the push, `branch.c`). `RET` and `IRET` restore in the reverse order. R1 always points at the next free byte.
- **`JSRUR Rn` = call the address IN Rn** (`branch.c`: the register's high byte goes into the branch register through
  the swap transceiver, then the low byte, then the stack push, then `PC ← branch register`). The interpreter had the
  two bytes swapped until 2026-09-22 (`tools/patched_files.txt`); it now agrees. The monitor's `G` command and the
  `O` boot both end in `JSRUR R7` (`monitor.asm`), which is why a program run by `G` returns to the prompt with `RET`.
- **`PUSHR` (review H-1)**: as microcoded until 2026-09-22 both stack writes happened during a bus fight (the register
  card kept driving the bus while TMP1 drove the byte being written); ucemu reproduced `PUSHR R3` with R3 = $ABCD
  pushing $21CC. Fixed in `branch.c` (the read strobes are released before each write) and loaded into the sequencer
  EEPROM the same evening (`firmware/microcode/README.md`). **To verify:** a bench `PUSHR`/`POPR` round trip on the
  reloaded image (`docs/isa/MICROCODE-REVIEW-NOTES.md` section 7, item 3).
- `PUSHR` goes through TMP1, so TMP is preserved; `POPR` loads the register straight from memory.
- `POPR R0` and `LDR R0` do not load R0 on the hardware (section 4 note); use `RET` to pop into the PC.
- The `-2-BYTE-OPERAND-SEL` mechanism means `PUSHR`, `POPR`, `JSRUR`, `BRUR` and `MOVRR` are the only instructions whose
  register is in a separate byte; every other register instruction has it in the opcode's low three bits.
- Review H-5 (open hardware question): the sequencer-logic netlist shows IC11 gate B tied so that it would drive
  `ADDR-REG-ID0..3` low permanently, which would fight every SP- or R2-relative access (all of this section, `LDA`
  family, `LDAVR`/`STAVR`, `LDIVR`, `BRVR`). **To verify:** a scope on bus pin C3 during a single-stepped `PUSH`
  (review section 7, item 1). `tests/assembler/romdiag` stage 1 (`JSR show` / `RET`) passing on the bench would
  also show the stack path works.

## 6. ALU operations

All operate on ACC; the second operand is an immediate byte (`…I`) or TMP (`…T`). Function codes are the ALU
card's `ALU0..2` (`CodeGen.h`: 0 DATA, 1 SUB, 2 AND, 3 OR, 4 XOR, 5 SHIFT, 6 ZERO, 7 ADD; `ALU3` = carry-in for ADD).

| Opcode | Mnemonic | Bytes | Steps | Description | Carry FF |
|---|---|---|---|---|---|
| $B0 | `ADDI byte` | 2 | 12 | ACC ← ACC + byte | ← carry out |
| $E2 | `ADDIC byte` | 2 | 12 | ACC ← ACC + byte + carry | ← carry out |
| $B8 | `ADDT` | 1 | 11 | ACC ← ACC + TMP | ← carry out |
| $E3 | `ADDTC` | 1 | 11 | ACC ← ACC + TMP + carry | ← carry out |
| $B1 | `SUBI byte` | 2 | 12 | ACC ← ACC − byte | ← borrow (hardware only, see note) |
| $B9 | `SUBT` | 1 | 11 | ACC ← ACC − TMP | ← borrow (hardware only) |
| $B3 | `ANDI byte` | 2 | 12 | ACC ← ACC & byte | unchanged |
| $BB | `ANDT` | 1 | 11 | ACC ← ACC & TMP | unchanged |
| $B2 | `ORI byte` | 2 | 12 | ACC ← ACC \| byte | unchanged |
| $BA | `ORT` | 1 | 11 | ACC ← ACC \| TMP | unchanged |
| $B4 | `XORI byte` | 2 | 12 | ACC ← ACC ^ byte | unchanged |
| $BC | `XORT` | 1 | 11 | ACC ← ACC ^ TMP | unchanged |
| $B5 | `INVA` | 1 | 10 | ACC ← ~ACC (DATA function with `-AC-LD-INV`) | unchanged |
| $B6 | `SHL` | 1 | 16 | ACC ← ACC << 1, bit 0 ← 0 | ← old bit 7 (hardware only) |
| $B7 | `SHR` | 1 | 16 | ACC ← ACC >> 1, bit 7 ← 0 | ← old bit 0 (hardware only) |
| $BD | `RSHL` | 1 | 15 | rotate left within 8 bits (bit 0 ← old bit 7) | ← old bit 7 (hardware only) |
| $BE | `RSHR` | 1 | 16 | rotate right within 8 bits (bit 7 ← old bit 0) | ← old bit 0 (hardware only) |
| $BF | `PSHR` | 1 | 16 | arithmetic shift right (bit 7 propagates) | ← old bit 0 (hardware only) |
| $E0 | `CSHL` | 1 | 16 | rotate left through carry: bit 0 ← carry | ← old bit 7 |
| $E1 | `CSHR` | 1 | 16 | rotate right through carry: bit 7 ← carry | ← old bit 0 |

Notes:

- **Which carry values a program may rely on.** The flip-flop is clocked at every `-AC-LD` whose function is ADD, SUB
  or SHIFT, and loads `CO/BO OR SHIFT-OUT` (review 1.4). So on the hardware every shift and every subtract writes it,
  while the interpreter writes it only for `ADDI/ADDT/ADDIC/ADDTC/CSHL/CSHR` (`main.c`: `SUBI`, `SUBT`, `SHL`, `SHR`,
  `RSHL`, `RSHR`, `PSHR` never touch `carry`). The only carry uses that behave identically everywhere are:
  an `ADDI`/`ADDT` immediately followed by an `ADDIC`/`ADDTC` with nothing but register moves between them (the monitor
  never does 16-bit adds, but `software/compiler/y1cc.py`'s `do_add16` idiom does), and a `CSHL`/`CSHR` after an
  explicit clear (`LDAI 0 / CSHL` clears it: 0 + nothing shifted out; `rt_mul` in `y1cc.py`). `BRC` after anything
  else means different things on the two emulators and the machine. The sense of the borrow the hardware loads
  after `SUB` (adder carry XOR SUB, review 1.4) is stated by the review as "borrow"; **To verify:** its polarity
  (`SUBI 1` with ACC = 0 then `BRC`) on the bench before any code depends on it.
- Subtraction on the ALU is two's-complement addition with the SUB line (`-ADD/SUB`, review 1.4); the result byte
  is exact (`tests/ucemu/isa.asm`: `LDAI 3 / SUBI 5` → $FE on both emulators).
- Comparisons do not need a subtract: `BRLT`/`BRGT`/`BREQ`/`BRNEQ` compare ACC with TMP directly (section 7).
- The shift instructions load the 74LS194 shifter from ACC, shift once, and load ACC back (`accumulator.c`
  `shiftOp`): three strobes, hence 15–16 steps. `RSHL` is one step shorter because its mode code equals the SHIFT
  output code and the generator elided a duplicate line (review L-5) — same effect.
- `ADDIC`/`ADDTC` add the flip-flop into the adder's C0 through `ALU3` (`CodeGen.h` `CARRY_SHIFT`, review 1.4).
- The monitor's nibble printing is `SHR` ×4 (`showaddr`, `showbyte`); `getaddress` builds a byte with `SHL` ×4 /
  `ANDI 0F0H` / `ORT`.

## 7. Branches

All 3-byte branches carry an absolute 16-bit target, high byte first, and all take 21 steps whether or not they
branch (the target is loaded into the branch register, the condition is latched at `BR-TEST`, and the PC load is
gated by that latch; `branch.c` `branch()`, review 1.1). There are no relative branches.

| Opcode | Mnemonic | Bytes | Steps | Branches when | Condition source (ALU mux `CodeGen.h`) |
|---|---|---|---|---|---|
| $A0 | `BR addr` | 3 | 21 | always | `ALUBR` (D0 = VCC) |
| $A1 | `BRZ addr` | 3 | 21 | ACC == 0 | `ALUZ` (D4: BDATA0..7 == 0 with `-AC-RD`) |
| $A2 | `BRNZ addr` | 3 | 21 | ACC != 0 | `ALUZ` inverted |
| $A3 | `BRINH addr` | 3 | 21 | the input-switch line is high | `ALUIN` (D5) |
| $A4 | `BRINL addr` | 3 | 21 | the input-switch line is low | `ALUIN` inverted |
| $A5 | — (`BRNC` planned) | — | — | **no microcode** | |
| $A6 | `BRC addr` | 3 | 21 | carry flip-flop set | `ALUCS` (D7) |
| $A7 | `BRLT addr` | 3 | 21 | ACC < TMP (unsigned) | `ALULT` (D3: TMP > ACC) |
| $A8 | `BREQ addr` | 3 | 21 | ACC == TMP | `ALUEQ` (D2) |
| $A9 | `BRGT addr` | 3 | 21 | ACC > TMP (unsigned) | `ALUGT` (D1: TMP < ACC) |
| $AA | `BRNEQ addr` | 3 | 21 | ACC != TMP | `ALUEQ` inverted |
| $AB | `BR16Z addr` | 3 | 21 | **broken** (never branches on hardware, review H-3) | `ALU16Z` (D6) |
| $AC | `BR16NZ addr` | 3 | 21 | **broken** (always branches on hardware, H-3) | `ALU16Z` inverted |
| $AD | `BRUR Rn` | 2 | 20 | always: PC ← Rn. Operand byte = n (low nibble) | `ALUBR` |
| $AE | — | — | — | **no microcode** | |
| $AF | `BRDEV addr` | 3 | 21 | always on the hardware and on ucemu; **never on the interpreter** | `ALUBR` |
| $D8+n | `BRVR Rn` | 1 | 22 (R0: 21) | always: PC ← the word at [Rn] (high byte first); Rn ← Rn+2 | `ALUBR` |

Notes:

- **`BRVR Rn` is an indirect jump**: the generator's `branch(reg, ...)` reads the two target bytes *through the
  register* exactly as `BR` reads its operand through R0, incrementing the register after each byte (`branch.c`,
  `docs/isa/steps.txt`). So `BRVR R7` with R7 = $3000 jumps to the address stored at $3000/$3001 and leaves R7 =
  $3002; it pushes nothing. `BRVR R0` is therefore the same as `BR addr` (the "vector" is the following word).
  This was the monitor's `G` command until 2026-09-22 (`G AAAA` never ran the code at AAAA); the compiler's
  `--vector` layout exists for the 2021 chip (`software/compiler/README.md`). The interpreter did something else
  until 2026-09-22 (loaded Rn from [Rn] and never branched) and now follows the microcode (`tools/patched_files.txt`).
- **`BRUR Rn`** is the direct register jump, added 2026-09-22 ($AD was an empty record before): JSRUR's
  operand/register-to-branch-register steps without the push (`branch.c`). Emulator-proven (`tests/assembler/brur`,
  `ABC0123`; the C compiler's `switch` jump tables use it). **To verify:** on the bench with the reloaded EEPROM
  (`tests/assembler/brur/README.md`); `y1cc --no-brur` avoids it until then.
- **`BRDEV`** ("branch if device") is the hardware/emulator switch the monitor and the C runtime use: the microcode
  is a plain `BR` (`branch.c`: `branch(PC, ALUBR, ...)`), the interpreter deliberately falls through (`main.c`:
  `case BRDEV: // emulator does not branch, hardware does branch`). `uartout` is `BRDEV emulator2 / outa p2 / ret`
  followed by the UART code at `emulator2:` (`monitor.asm`). ucemu runs the microcode, so it takes the hardware path
  and the console goes through its UART model.
- **`BRZ`/`BRNZ` (review H-2)**: as microcoded until 2026-09-22 the ALU kept driving DATA0..7 = ACC while the branch
  register was copied into the PC; under the usual TTL rule a taken `BRZ` landed on page offset $00 and the monitor
  could not print a string on ucemu. Fixed in `branch.c` (`clearSignal("-AC-RD")` before `-BRANCH-RD`) and loaded.
  `tests/assembler/romdiag` stages 5–6 and `tests/assembler/romcount` (`BRNZ delay`, ran overnight 2026-09-22/23 on
  the machine, `docs/system/MACHINE.md`) exercise it.
- **`BR16Z`/`BR16NZ`** cannot work as microcoded (review H-3): the 16-bit-zero detector needs the operand's high byte
  on BDATA8..15, which `-AC-RD` pins at $FF. The interpreter reports them as bad opcodes; the assembler accepts them;
  `y1cc` never emits them. Open.
- `BRLT`/`BRGT` are unsigned 8-bit comparisons of ACC against TMP (74LS85 comparators, A = TMP on the bus, B = ACC;
  D3 = A>B is used for `BRLT`, review section 4). `BRGT`/`BREQ` are how the monitor parses hex (`getnibble`:
  `LDTI '9' / BRGT INAF`).
- `BRINH`/`BRINL` test the I/O card's input-switch line, the machine's one "button": `romcount` mirrors the switches
  until the line goes high; the monitor boots into its command loop only `BRINH cmdloop`, else it runs the
  start-up test message (`monitor.asm`). ucemu: `-i 0|1` sets the line, `-I N` flips it every N steps.
- `BRC` tests the carry flip-flop as loaded by the previous ADD/SUB/shift (section 6). The monitor's `showcarry`
  prints `C` or `X` with it.
- Empty records ($A5, $AE): fetching them on the machine causes the H-4 storm (section 3 note). The interpreter
  reports `bad opcode`.
- Review M-2: the branch register is a leading-edge latch that captures each operand byte one step after the address
  became valid; this is the path that limits the clock frequency, not the ALU.

## 8. Input / output

| Opcode | Mnemonic | Bytes | Steps | Description |
|---|---|---|---|---|
| $60+p | `OUTA Pp` | 1 | 12 | port p ← ACC |
| $70+p | `OUTI Pp,byte` | 2 | 14 (P0: 13) | port p ← byte (memory → port directly, ACC unchanged) |
| $80+p | `OUTVR Pp,Rn` | 2 | — | **no microcode** (bad opcode on the interpreter too) |
| $90+p | `INP Pp` | 1 | 12 | ACC ← port p |
| $01 | `ON` | 1 | 8 | the OUT latch (ON/OFF LED) on |
| $02 | `OFF` | 1 | 8 | OUT latch off |

Notes:

- p = 0..15, spelled `P0`..`P9`, `PA`..`PF` (`yacc1.def` CLASS ports; `P8=8` since the 2026-09-22 typo fix).
  The port number is the `IOADDR0..3` field of the control word; the `-IO-ADDR-LD` strobe the generator also emits
  reaches nothing on the I/O card (review 1.5, L-2).
- The I/O card decodes P0..P7 (its `IO-ADDR3` strap); P0 is a select latch and P1 the data port of the selected
  device (UART, switches/LEDs, LCD, TIL311), so a UART byte is two instructions: `OUTI P0,UARTCS / OUTA P1`
  (`monitor.asm` `uartout`). Full map in [IO-PORTS.md](IO-PORTS.md).
- P8/P9 are the CompactFlash card (register select / data), modelled by both emulators with `-c disk.img`
  (`software/cfmodel.h`); the card is not built yet.
- Port 2 is the interpreter's console (`OUTA P2` prints, `INP P2` reads a key; `main.c`); ucemu keeps that shortcut
  too. On the machine P2 is `-IO-SEL2` on the I/O card's header with nothing wired (`docs/system/OS-PLAN.md`).
- On the interpreter only `OUTA`/`OUTI` to P2, and `OUTI P1` while P0 = $40 (the UART THR), produce output; `INP P1`
  returns $FF on the first read while P0 = 1 (the switches), and an `INP` of any port other than P2/P9 otherwise
  leaves ACC unchanged (`main.c`: only ports 2, 8 and 9 assign `acc`).
- `INP` has the slowest signal path in the machine in one microcode step (open-collector `IO-RD` rise, review M-3):
  the first instruction to misread at a faster clock.
- I/O writes latch at the trailing edge of `-IO-WR` (review 1.5), which is why `OUTI` can send the byte straight
  from memory.

## 9. Control, interrupts and the reset record

| Opcode | Mnemonic | Bytes | Steps | Description |
|---|---|---|---|---|
| $00 | (`START`) | — | 8 | the reset record: fetch + PC++ with `OUT-OFF`. Not an assembler mnemonic. Executed as an opcode it is a 1-byte NOP that clears the OUT LED (the interpreter reports it as a bad opcode) |
| $03 | `HALT` | 1 | 8 | `SOFT-HALT` stops the clock; the front-panel CONT resumes in the reset step. The emulators exit here with `-x` |
| $FB | `INTE` | 1 | 9 | enable interrupts (`INT-EN`) |
| $FC | `INTD` | 1 | 9 | disable interrupts (`INT-START`) — also clears a pending interrupt (review M-6) |
| $FE | `IADDR addr` | 3 | 16 | interrupt vector ← addr |
| $FF | (`INT`) | — | 30 | forced by hardware when an interrupt is pending and enabled: `INT-START`, PC−1, push PC, PC ← vector. Not an assembler mnemonic |
| $FD | `IRET` | 1 | 22 | pop PC as `RET`, then `INT-EN` |

Notes:

- Reset clears the instruction register and the index registers and sets FORCE-ROM, so record $00 fetches from
  $0000 and gets ROM[$F000] (`MICROCODE-REVIEW-NOTES.md` section 4, `software/ucemu/README.md`). A stand-alone ROM
  program's first instruction must present an A15-high address (`BR begin`) to end the remap.
- The interrupt entry substitutes opcode $FF at the instruction-register latch (sequencer IC1/IC2, review 1.1);
  `INT` decrements the PC to undo the prologue's increment, pushes it like `JSR`, and loads the vector through
  `-INT-JMP`. `IRET` pops and re-enables. The monitor installs `isrcode` ($FF90) with `iaddr isrcode / INTE` at boot;
  the ISR blinks the LED `interupt_cnt` times (`monitor.asm`). **To verify:** no interrupt source is wired in the
  tree's model (`software/ucemu/README.md` "Not modelled yet"), and `-INTA` is never asserted by any record (review
  L-8); the ISR has not been exercised from this tree.
- The interpreter: `INTE`/`INTD` do nothing, `IADDR` skips its two operand bytes, `IRET` and `INT` are bad opcodes
  (`main.c`).
- **Assembler trap: `IADDR addr` with an odd low byte assembles to opcode $FF.** `yacc1.def` encodes it as
  `FE|1 hi(1) lo(1)`, and `|1` ORs the operand word's low bits into the opcode byte without shifting (RC/asm manual,
  `asm.txt`); checked 2026-09-23: `IADDR 1234H` → `FE 12 34` but `IADDR 1235H` → `FF 12 35`. The monitor's
  `iaddr isrcode` ($FF90) happens to be even. The line should read `FE hi(1) lo(1)` like `BR`. (Reported here; the
  `.def` is not this document's to change.)
- `HALT` on the machine halts in step 6 of the record; on both emulators `-x` mode exits with a status line
  (`HALT at aaaa after N instructions, R3=xxxx`; ucemu adds steps, clocks and the bus-fight count).

## 10. Opcode index $00..$FF

`—` = no assembler mnemonic. **empty** = the microcode record is all zeros (review H-4: on the machine it asserts
every active-low strobe for 61 steps until `COUNT-FAULT`; the interpreter says `bad opcode`).

| Opcode | Mnemonic | Opcode | Mnemonic | Opcode | Mnemonic | Opcode | Mnemonic |
|---|---|---|---|---|---|---|---|
| $00 | START (reset record) | $40 | LDAVR R0 | $80 | **empty** (OUTVR P0) | $C0 | **empty** (LDTVR R0) |
| $01 | ON | $41 | LDAVR R1 | $81 | **empty** | $C1 | **empty** |
| $02 | OFF | $42 | LDAVR R2 | $82 | **empty** | $C2 | **empty** |
| $03 | HALT | $43 | LDAVR R3 | $83 | **empty** | $C3 | **empty** |
| $04 | JSR addr | $44 | LDAVR R4 | $84 | **empty** | $C4 | **empty** |
| $05 | RET | $45 | LDAVR R5 | $85 | **empty** | $C5 | **empty** |
| $06 | JSRUR Rn | $46 | LDAVR R6 | $86 | **empty** | $C6 | **empty** |
| $07 | PUSHR Rn | $47 | LDAVR R7 | $87 | **empty** | $C7 | **empty** (LDTVR R7) |
| $08 | POPR Rn | $48 | STAVR R0 | $88 | **empty** | $C8 | **empty** (STTVR R0) |
| $09 | PUSH | $49 | STAVR R1 | $89 | **empty** | $C9 | **empty** |
| $0A | POP | $4A | STAVR R2 | $8A | **empty** | $CA | **empty** |
| $0B | MVAT | $4B | STAVR R3 | $8B | **empty** | $CB | **empty** |
| $0C | MVTA | $4C | STAVR R4 | $8C | **empty** | $CC | **empty** |
| $0D | LDTI byte | $4D | STAVR R5 | $8D | **empty** | $CD | **empty** |
| $0E | LDAI byte | $4E | STAVR R6 | $8E | **empty** | $CE | **empty** |
| $0F | MOVRR Rs,Rd | $4F | STAVR R7 | $8F | **empty** (OUTVR PF) | $CF | **empty** (STTVR R7) |
| $10 | MVIB R0,b | $50 | INCR R0 | $90 | INP P0 | $D0 | LDIVR R0,b |
| $11 | MVIB R1,b | $51 | INCR R1 | $91 | INP P1 | $D1 | LDIVR R1,b |
| $12 | MVIB R2,b | $52 | INCR R2 | $92 | INP P2 | $D2 | LDIVR R2,b |
| $13 | MVIB R3,b | $53 | INCR R3 | $93 | INP P3 | $D3 | LDIVR R3,b |
| $14 | MVIB R4,b | $54 | INCR R4 | $94 | INP P4 | $D4 | LDIVR R4,b |
| $15 | MVIB R5,b | $55 | INCR R5 | $95 | INP P5 | $D5 | LDIVR R5,b |
| $16 | MVIB R6,b | $56 | INCR R6 | $96 | INP P6 | $D6 | LDIVR R6,b |
| $17 | MVIB R7,b | $57 | INCR R7 | $97 | INP P7 | $D7 | LDIVR R7,b |
| $18 | MVIW R0,w | $58 | DECR R0 | $98 | INP P8 | $D8 | BRVR R0 |
| $19 | MVIW R1,w | $59 | DECR R1 | $99 | INP P9 | $D9 | BRVR R1 |
| $1A | MVIW R2,w | $5A | DECR R2 | $9A | INP PA | $DA | BRVR R2 |
| $1B | MVIW R3,w | $5B | DECR R3 | $9B | INP PB | $DB | BRVR R3 |
| $1C | MVIW R4,w | $5C | DECR R4 | $9C | INP PC | $DC | BRVR R4 |
| $1D | MVIW R5,w | $5D | DECR R5 | $9D | INP PD | $DD | BRVR R5 |
| $1E | MVIW R6,w | $5E | DECR R6 | $9E | INP PE | $DE | BRVR R6 |
| $1F | MVIW R7,w | $5F | DECR R7 | $9F | INP PF | $DF | BRVR R7 |
| $20 | MVRLA R0 | $60 | OUTA P0 | $A0 | BR addr | $E0 | CSHL |
| $21 | MVRLA R1 | $61 | OUTA P1 | $A1 | BRZ addr | $E1 | CSHR |
| $22 | MVRLA R2 | $62 | OUTA P2 | $A2 | BRNZ addr | $E2 | ADDIC byte |
| $23 | MVRLA R3 | $63 | OUTA P3 | $A3 | BRINH addr | $E3 | ADDTC |
| $24 | MVRLA R4 | $64 | OUTA P4 | $A4 | BRINL addr | $E4 | LDA addr |
| $25 | MVRLA R5 | $65 | OUTA P5 | $A5 | **empty** (BRNC planned) | $E5 | STA addr |
| $26 | MVRLA R6 | $66 | OUTA P6 | $A6 | BRC addr | $E6 | LDT addr |
| $27 | MVRLA R7 | $67 | OUTA P7 | $A7 | BRLT addr | $E7 | STT addr |
| $28 | MVRHA R0 | $68 | OUTA P8 | $A8 | BREQ addr | $E8 | STR R0,addr |
| $29 | MVRHA R1 | $69 | OUTA P9 | $A9 | BRGT addr | $E9 | STR R1,addr |
| $2A | MVRHA R2 | $6A | OUTA PA | $AA | BRNEQ addr | $EA | STR R2,addr |
| $2B | MVRHA R3 | $6B | OUTA PB | $AB | BR16Z addr (broken, H-3) | $EB | STR R3,addr |
| $2C | MVRHA R4 | $6C | OUTA PC | $AC | BR16NZ addr (broken, H-3) | $EC | STR R4,addr |
| $2D | MVRHA R5 | $6D | OUTA PD | $AD | BRUR Rn (2026-09-22) | $ED | STR R5,addr |
| $2E | MVRHA R6 | $6E | OUTA PE | $AE | **empty** | $EE | STR R6,addr |
| $2F | MVRHA R7 | $6F | OUTA PF | $AF | BRDEV addr | $EF | STR R7,addr |
| $30 | MVARL R0 | $70 | OUTI P0,b | $B0 | ADDI byte | $F0 | LDR R0,addr |
| $31 | MVARL R1 | $71 | OUTI P1,b | $B1 | SUBI byte | $F1 | LDR R1,addr |
| $32 | MVARL R2 | $72 | OUTI P2,b | $B2 | ORI byte | $F2 | LDR R2,addr |
| $33 | MVARL R3 | $73 | OUTI P3,b | $B3 | ANDI byte | $F3 | LDR R3,addr |
| $34 | MVARL R4 | $74 | OUTI P4,b | $B4 | XORI byte | $F4 | LDR R4,addr |
| $35 | MVARL R5 | $75 | OUTI P5,b | $B5 | INVA | $F5 | LDR R5,addr |
| $36 | MVARL R6 | $76 | OUTI P6,b | $B6 | SHL | $F6 | LDR R6,addr |
| $37 | MVARL R7 | $77 | OUTI P7,b | $B7 | SHR | $F7 | LDR R7,addr |
| $38 | MVARH R0 | $78 | OUTI P8,b | $B8 | ADDT | $F8 | **empty** |
| $39 | MVARH R1 | $79 | OUTI P9,b | $B9 | SUBT | $F9 | **empty** |
| $3A | MVARH R2 | $7A | OUTI PA,b | $BA | ORT | $FA | **empty** |
| $3B | MVARH R3 | $7B | OUTI PB,b | $BB | ANDT | $FB | INTE |
| $3C | MVARH R4 | $7C | OUTI PC,b | $BC | XORT | $FC | INTD |
| $3D | MVARH R5 | $7D | OUTI PD,b | $BD | RSHL | $FD | IRET |
| $3E | MVARH R6 | $7E | OUTI PE,b | $BE | RSHR | $FE | IADDR addr |
| $3F | MVARH R7 | $7F | OUTI PF,b | $BF | PSHR | $FF | INT (hardware only) |

218 of the 256 records hold microcode (`MICROCODE-REVIEW.md`); the 38 empty ones are $80–$8F, $A5, $AE, $C0–$CF,
$F8–$FA. `BACKLOG.md` lists filling them with a one-step trap as an open HIGH item.

## 11. Emulator versus hardware, in one table

The microcode is the truth of the machine; ucemu runs it; the interpreter is the quick model. Where they differ:

| Instruction(s) | Hardware / ucemu (microcode) | Interpreter (`software/emulator/main.c`) |
|---|---|---|
| `LDA STA LDT STT LDR STR` | operand address left in **R2** (+2 for LDR/STR) | a hidden 9th register; R2 untouched |
| loads to R0 (`MVIB/MVIW/MVARL/MVARH/MOVRR/POPR/LDR`) | suppressed (branch-taken gate) | performed |
| `BRDEV` | branches | falls through |
| `SUBI SUBT` | carry FF ← borrow | carry untouched |
| `SHL SHR RSHL RSHR PSHR` | carry FF ← bit shifted out | carry untouched |
| `BR16Z BR16NZ` | never / always branch (H-3) | bad opcode |
| `LDTVR STTVR` | empty record (H-4 storm) | executed |
| `OUTVR`, $A5, $AE, $F8–$FA | empty record (H-4 storm) | bad opcode |
| $00 | 1-byte NOP + OUT off | bad opcode |
| `INTE INTD IADDR IRET INT` | as microcoded (never exercised; ucemu has no interrupt source) | no-op / skip / bad opcode |
| `INTD` | also clears a pending interrupt (M-6) | — |
| `BRVR`, `JSRUR`, `BRUR`, `PUSHR`, `BRZ/BRNZ` | (all as described above) | agree since 2026-09-22 |
| writes to $E000–$FFFF | reach the EEPROM's -WE (hazard) / ignored by ucemu | exit with `Rom Write` |
| console | UART on P0/P1 (ucemu models it); P2 also works on ucemu | port 2 only (plus `OUTI P1` when P0 = $40) |
| RAM at power-up | undefined (ucemu fills $FF) | zero |

`tests/ucemu/isa.asm` runs every arithmetic, logic, shift, compare, register, memory and stack instruction on both
emulators and the port-2 byte streams are identical apart from `BRDEV` (`software/ucemu/README.md`, item 4).

## 12. Status of the microcode findings on 2026-09-23

- H-1 (`PUSHR` bus fight) and H-2 (`BRZ`/`BRNZ`/`BR16Z`/`BR16NZ` bus fight): fixed in `branch.c` 2026-09-22, image
  regenerated, EEPROM reloaded with `tools/ucode_send.py --all`; `romcount` ran on the machine afterwards (`BRNZ`).
- H-3 (`BR16Z`/`BR16NZ` cannot work): open.
- H-4 (38 empty records): open (`BACKLOG.md`).
- H-5 (sequencer IC11 gate B on `ADDR-REG-ID`): open hardware question; see section 5.
- M-2 (one-step memory windows before leading-edge latches): a clock-frequency rule, open.
- The review's speed table (section 5 there) estimates ~30 % of all executed steps removable; nothing changed.
