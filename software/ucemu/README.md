# software/ucemu — y1ucemu, the microcode-level YACC1 emulator

`y1ucemu.c` (2026-09-22) is the YACC1 counterpart of the P8X's `p8xemu`: it does not know what any instruction does.
It loads the control store the sequencer card holds (`firmware/microcode/ucode-generator2/test.hex`: 256 opcodes × 64
steps × 64 control bits) and steps the same control words the hardware steps, driving a model of the cards on the
bus. ADDI adds because record $B0 says so. The other emulator (`software/emulator`) interprets instructions and stays
the quick, forgiving one; this one is the faithful one, and it is what turns the microcode reviews' findings into
things that can be run.

```
make -C software/ucemu
software/ucemu/y1ucemu -x -m -f prog.img            # monitor ROM + a program image, scripted (HALT exits)
software/ucemu/y1ucemu -m                            # interactive monitor on the terminal (UART = stdin/stdout)
software/ucemu/y1ucemu -x -f prog.img -t             # -t: one line per instruction fetch; -T: every step + signals
software/ucemu/y1ucemu -x -m -f prog.img -w          # -w: list every bus fight as it first occurs
python3 tests/ucemu/run.py                           # the compiler suite + tests/assembler/brur on this emulator
```

Options: `-u test.hex` another control store; `-F and|src` how a bus fight resolves (below); `-s NN` the switch
byte; `-l N` stop after N steps. The status line on stderr gives instructions, steps, clocks (a step is two clock
periods, the UCODE-COUNT-RESET step one), R3, and the bus-fight count.

## The model

Straight from `docs/isa/MICROCODE-REVIEW-NOTES.md` section 1 (each card's netlist), with `yaccsignaldata2.h` giving
the bit positions:

- **Sequencer**: step counter, instruction register (latched at the leading edge of LD-INS-REG from the previous
  step's bus, $FF when an interrupt is pending and enabled), operand register (OPERAND-CLK), branch register
  (BRANCH-LD-HI/LO both take DATA0..7; -BRANCH-RD drives all 16 lines), interrupt vector, the level-sensitive
  branch-taken latch (BR-TEST AND BR-COND, cleared by UCODE-COUNT-RESET), and the N$53 gate: a load whose target is
  R0 happens only when that latch is set. -2-BYTE-OPERAND-SEL substitutes the operand byte's nibbles for REG-RD-ID
  and REG-LD-ID.
- **Register cards**: R0-R7 as 74LS192 counters. Reads put byte lanes on the card's internal bus (-REG-RD-LO/HI),
  the straight transceivers or the swap transceiver (-HL-SWAP: high byte onto DATA0..7) carry it to the bus unless
  the read and load selects name the same card (an internal copy). -REG-FUNC-RD with no read strobe drives the
  pull-up value $FFFF; that is counted as a *weak* drive, not a fight. Loads are level-sensitive (value at the end
  of the strobe step); counts happen when -REG-UP/-REG-DN ends or the selection changes.
- **ALU card**: function blocks 0 DATA, 1 SUB, 2 AND, 3 OR, 4 XOR, 5 SHIFT, 6 ZERO, 7 ADD (ALU3 feeds the carry
  flip-flop into the adder), accumulator and carry flip-flop latched at the leading edge of -AC-LD (carry from CO/BO
  on add/sub, from the shift-out flip-flop on shift), the 74LS194 shifter (-SR-LD; mode from ALU1..0, serial input
  from ALU3..2), the 74LS251 branch-condition mux (D0 always, D1..3 the comparator of BDATA against AC, D4 low byte
  zero, D5 IN, D6 16-bit zero, D7 carry, XOR -AC-LD-INV). With -ALU-FUNC and -AC-RD the card drives DATA0..7 = AC
  and DATA8..15 = $FF.
- **Memory card**: RAM/EEPROM (writes above $E000 ignored), FORCE-ROM boot remap (address bits 12..15 forced high
  until an A15-high address is presented with -VMA), TMP0/TMP1 (16-bit, leading-edge loads, reads drive all 16 lines).
- **I/O card**: P0 = the control latch, P1 = the data port behind it: a 16550 UART (RBR/THR = stdin/stdout, LSR data
  ready and THRE, DLAB divisor writes accepted), the switches (`-s`) and LEDs. Port 2 is also a console, the old
  emulator's shortcut, so `OUTA P2` programs still print. A port read is sampled once at the leading edge of -IO-RD;
  a port write happens once, at the trailing edge of -IO-WR. Reading with nothing left gives 0 with "ready" set.
- **Reset** is the real one: registers and IR cleared, FORCE-ROM set, so record $00 fetches $0000 and gets ROM[$F000];
  the monitor's first `BR eprom` releases the remap. A stand-alone image therefore needs the same first branch
  (the compiler's `--boot` stub and `tests/assembler/brur` got one on 2026-09-22).

Timing: leading-edge latches take the bus and the function-block outputs as they were at the end of the previous
step (the generator's set-up-step convention); trailing-edge actions use the values at the end of the strobe step.

**Bus fights.** Every step, each data lane collects its drivers (memory, I/O, TMP0/1, the branch and interrupt
registers, the ALU, the register cards). Two drivers that disagree are a fight: counted per (opcode, step), listed
with `-w`, summarised on the status line. `-F and` (default) resolves a lane as the AND of its drivers, the usual
outcome of a TTL fight (a low output wins); `-F src` lets the ALU's -AC-RD drive lose to any other driver, which is
what the hardware must have been doing if the monitor ever ran on the image as burned (see below).

## What it found on 2026-09-22

Run against the control store as it was that morning (the image the sequencer EEPROM holds):

1. **H-2 is real and fatal under the AND rule.** BRZ/BRNZ (and BR16Z/NZ) left -AC-RD asserted with -ALU-FUNC while
   -BRANCH-RD drove the target into the PC: a taken BRZ loaded PC.lo = target.lo AND $00. `puts` never left its loop;
   the monitor could not print a string. Fixed in the generator (`branch.c`: `clearSignal("-AC-RD")` where TMP is
   released; records $A1, $A2, $AB, $AC change).
2. **H-1 is real.** PUSHR's two stack writes happened while the register card still drove PC.hi (swap path) and then
   SP: `PUSHR R3` with R3 = $ABCD pushed $21CC. Fixed in the generator (release -REG-RD-HI/LO, -REG-FUNC-RD,
   -HL-SWAP before each write; record $07..$0F change).
3. **Two compiler bugs the interpreter's zeroed memory hid**: y1cc did not zero its uninitialised globals (RAM
   powers up random; the emulator fills it with $FF) and padded partially initialised arrays with `DS`. main now
   clears the BSS at entry and the padding is real zeros.
4. **The rest of the ISA matches the interpreter byte for byte**: `tests/ucemu/isa.asm` runs every arithmetic, logic,
   shift, compare, register, memory and stack instruction on both emulators and the output streams are identical,
   apart from BRDEV (a branch here, not in the interpreter: by design) — 0 bus fights with the fixed image.
5. With the fixed image: the whole compiler suite passes on this emulator through the monitor's real console path
   (BRDEV branches, so `putchar` is the ROM's charout and the UART model), and the monitor boots from reset, takes
   `G3000`, runs a compiled program and returns to its prompt, with 0 fights over 6 million steps. `chars.ucout`
   holds the expectation with the input echo the monitor's uartin produces on the hardware.

The mechanical review's "two drivers" count (`tools/ucode_review.py`, rule R2) went from 37 to 3 with the two fixes.

## Not modelled yet

Interrupts beyond the enable/pending latches (no source raises one); IRET/IADDR/INT records run as written; the CF
card (ports P8/P9, `docs/system/OS-PLAN.md` phase 1) and the video card; a clock-cycle cost model per instruction
is one step-count away (the status line has steps and clocks); comparing the interpreter's and this emulator's
instruction traces automatically.

- **2026-09-22 (evening):** `-i 0|1` sets the level of the input-switch line that `BRINH`/`BRINL` test (fixed for the run), and `-L` reports writes to the LED board, the TIL311 displays and the ON/OFF LED on stderr as they change (`tests/assembler/romcount/` uses both); `-I N` flips the input line every N steps, a bench hand on the switch (`tests/assembler/romdiag/`).
