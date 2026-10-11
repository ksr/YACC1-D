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
python3 software/y1dbg                               # the debugger: y1ucemu -D under a terminal UI with the video screen
```

Options: `-u test.hex` another control store; `-F and|src` how a bus fight resolves (below); `-s NN` the switch
byte; `-c disk.img` a CompactFlash image; `-l N` stop after N steps; `-V` the video card's screen and CRTC registers
at the end, `-W` a CRTC write log, `-N` no video card (2026-09-25, `software/videomodel.h`); `-G REV` the video card at gate level from its netlist (2026-10-11, below); `-H` an undriven data lane keeps its last value; `-O` the old address model (2026-10-10: by default nothing drives ADDR-REG-ID while `-2-BYTE-OPERAND-SEL` is asserted - the sequencer's IC18B is off - and the address reads $FFFF, as the machine did; this caught POPR, fixed in the microcode the same day). The status line on stderr gives instructions, steps, clocks (a step is two clock
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
- **CompactFlash** (`-c disk.img`, 2026-09-22): `software/cfmodel.h`, shared with the other emulator, on P8 (register
  select) and P9 (data) (`docs/cards/cf.md`). With no image every read gives $FF; `tests/os` boots Y1/OS through it.
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

Interrupts beyond the enable/pending latches (no source raises one); IRET/IADDR/INT records run as written; the
video card's picture (the model is its bus side: display RAM, the CRTC's registers, the latch; 2026-09-25; at gate
level with `-G`, 2026-10-11); a clock-cycle cost model per instruction
is one step-count away (the status line has steps and clocks); comparing the interpreter's and this emulator's
instruction traces automatically.

- **2026-09-22 (evening):** `-i 0|1` sets the level of the input-switch line that `BRINH`/`BRINL` test (fixed for the run), and `-L` reports writes to the LED board, the TIL311 displays and the ON/OFF LED on stderr as they change (`tests/assembler/romcount/` uses both); `-I N` flips the input line every N steps, a bench hand on the switch (`tests/assembler/romdiag/`). `-R 1|2` = the index-register cards fitted: with one, R4..R7 are absent (reads leave the bus to its pull-ups, $FF; loads and counts are lost), which reproduced the 2026-09-22 bench symptom of the first romcount build.

- **2026-09-23 (afternoon):** the UART's data-ready bit is a non-blocking poll. Before, every status-register read, including the transmit-empty check before each output character, blocked in `read()` until the next input byte, so a live sender (a pty, `tools/monload.py`) got no answer until it sent more; scripted runs never noticed because their input was already complete. Data reads still block; after 20,000 empty polls with no output each poll waits 1 ms, so an idle monitor does not spin the host CPU. `tests/monload/run.py` drives the emulator through a pseudo-terminal.
- **2026-09-23: the carry is modelled as the ALU is built**: add/subtract latch CO/BO OR SHIFT-OUT (IC7A), so a stale
  shift-out corrupts the next add unless the microcode clears it, which it now does. This is the default; `-K` keeps
  the old, kinder model (carry = CO/BO only). The old model hid the fault that made `arith` hang on the machine.
- **2026-10-11: the debug server, `-D PORT`.** In this mode the emulator leaves the terminal alone and serves one
  connection on 127.0.0.1:PORT (0 = any free port, printed on stdout): one-line commands, one JSON line back each -
  step (instructions or microcode steps), run / until / pause, breakpoints at instruction fetch, memory watches,
  registers, memory, poke, register writes, keys into the UART's receive path, the UART's output, the video card's
  RAM and CRTC registers, an instruction trace, reset, load. The front end is `software/y1dbg` (Python; its README has
  the protocol, the comment above `dbg_serve` in `y1ucemu.c` is the reference). It exits when the connection closes.
  Without `-D` nothing changes: the stepping code is the same (the debugger steps through one wrapper, so `do_step`
  keeps two call sites and is inlined into `main`'s loop as before), and a 300-million-step BASIC loop took 13.13-13.31 s
  before and 13.34-13.37 s after (median user time of six runs, measured twice; within about 1.5%), with an identical
  status line. `tests/y1dbg/run.py` tests the server and the debugger.
- **2026-10-11 (evening): the video card at gate level, `-G REV` (also `--video-rev REV`).** `videogate.h` is
  generated by `software/gatemodel` (`python3 software/gatemodel -o videogate.h`; this Makefile runs it when the
  card's netlist or the generator changes; `tests/video/gate.py` checks the committed copy is current) from the V1.0
  card's netlist with the bench reworks as netlist edits: the block compare, the ADDR11/ADDR0 decode, the E one-shot,
  evaluated in three-valued logic for all 1024 combinations of the ten bus inputs the bus path reaches. Each step
  looks its decode up: whether the display RAM's bus port, the 6845 or the JP1 latch drives DATA0..7 or takes the
  write. The display RAM stays in the memory array and the 6845's registers in `videomodel.h`, so `-V`, `-W`,
  `Y1VIDSTATE` and the debugger work as before. `-G list` names the revisions: `v1.0` as fitted (the +5V wire, the
  6845 with RS on A1), `v1.0-no6845` (the machine today), `v1.0-no-rs`, `v1.0-no-5v` (the card of 2026-09-18),
  `v1.0-drawn`, `v1.0-a0fix` (`docs/cards/video.md` section 9). Bus events on the card's side are listed on stderr
  once per (event, opcode, step), as `-w` lists fights, and counted on a line after the status line: contention (the
  card drives DATA0..7 together with another driver, whatever the values), a CPU read that finds DATA0..7 undriven
  while the card is selected, a read of the latch's floating inputs, an undefined select. `-G` and `-N` exclude each
  other.
  - **How (measured, then decided):** the decode never depends on the data lines, so it is a pure function of the
    bus inputs; three ways were measured on the 300-million-step BASIC loop of 2026-10-11 (13.7 s without a card
    model change): (a) the decode generated into C at build time, a table lookup per step: 15.2 s with `-G v1.0`
    (+11%); (b) a small C evaluator over a compiled netlist, both phases of the bus cycle settled every step: 125 ns
    a step, about 51 s for the same run; (c) the Python model behind the debug connection: 123 µs a bus cycle plus a
    28 µs round trip, 12 hours for the run if every step went over (the latch drives on -VMA alone, so every step
    counts), and a mirroring session (V I, V M1, two help listings; 4.0 million steps, 0.4 million with the card
    selected) a minute instead of 0.2 s even if only the selected steps did. (a) it is: no Python at run time, the
    netlist reader and part library in Python where they are easy to read, `make check` fast.
  - **Speed without `-G`**: the card's hook is one predictable branch per step and the write's under `-MEM-WR`. The
    300-million-step BASIC loop (`I`, `10 GOTO 10`, `RUN`, `-l 300000000`), six runs each, interleaved: 13.68 s
    before, 13.63 s after (median user time), the status line identical; with `-G v1.0` 15.2 s.
