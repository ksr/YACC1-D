# The two YACC1 emulators

The instruction-level emulator (`software/emulator`) and the microcode-level emulator (`software/ucemu`): what each
models, its options, what it does not model, how to run the monitor, a program and Y1/OS on each, and how to turn a
session into a test. Written 2026-09-23 from the YACC1-D tree.

Sources: `software/emulator/main.c` and `README.md`, `software/ucemu/y1ucemu.c` (its header comment is the option
reference) and `README.md`, `software/cfmodel.h`, `software/README.md`, `tests/compiler/run.py`, `tests/ucemu/run.py`,
`tests/ucemu/isa.asm`, `tests/os/run.py`, `tests/assembler/{romcount,romdiag}/run.py`, `docs/isa/MICROCODE-REVIEW-NOTES.md`,
`tools/patched_files.txt`, `os/Makefile`, `Makefile` (root).

## 1. Which one to use

| | `software/emulator/emulator` (the interpreter) | `software/ucemu/y1ucemu` (the microcode emulator) |
|---|---|---|
| knows | what each opcode does (a `switch` per opcode, `main.c`) | nothing about opcodes: it steps the control store the sequencer holds (`test.hex`) through a model of the cards |
| speed | fast; ~1 s for the compiler suite | slower (a step per control word: the OS session runs 80 million steps within its limit) |
| fidelity | the reference of *intended* semantics; forgiving | reproduces the hardware's quirks and bus fights; the faithful one |
| use it for | developing a program, the compiler tests, the oracle comparison | proving a program will behave on the machine, microcode changes, bench-symptom reproduction |

Both load Intel hex (`.img`), both start the monitor with `-m`, both take a CF image with `-c`, both exit at `HALT`
in `-x` mode with a status line on stderr, and both are built by the top-level `make` (`mk/sdk.mk` picks an SDK that
still links). `tests/ucemu/isa.asm` runs every arithmetic, logic, shift, compare, register, memory and stack
instruction on both and the byte streams are identical apart from `BRDEV` (`software/ucemu/README.md`).

## 2. The instruction-level emulator (`software/emulator`)

`main.c` (~1,360 lines, 2020 with 2026 additions): 8-bit ACC/TMP, 16-bit R0–R7 plus a hidden ninth register for the
operand address, 64K, 16 ports, a carry flag.

Options (`print_usage`, `main`):

| Option | Effect |
|---|---|
| `-m` (default with no arguments) | load `firmware/basic/basic.img` + `firmware/monitor/monitor.img`, found relative to the executable (works from a Finder double-click or any directory) |
| `-f FILE` | load an Intel-hex image (relative to the current directory); after `-m` if both given |
| `-x` | scripted run: no load/dump chatter, no raw tty, stdout flushed, `HALT` exits with `HALT at aaaa after N instructions, R3=xxxx` on stderr |
| `-c IMAGE` | attach a CompactFlash image on ports P4/P5 (created zero-filled if missing; P8/P9 until 2026-09-23) |
| `-l N` | stop after N instructions (`instruction limit reached at ... R3=...` on stderr) |
| `-h` | usage |

Behaviour worth knowing (`main.c`):

- Starts with PC = `$F000`, memory zero, R1 = 0 (the monitor sets the stack).
- **Console = port 2**: `OUTA P2` writes the byte to stdout; `INP P2` reads one key (raw tty unless `-x`; CR becomes
  LF; 0 at end of input). **A `q` byte ends input**: `mygetchar()` returns 0 on it (`main.c`), so a program that
  reads a `q` from a redirected stdin sees end of input, not the letter. `OUTI P1` prints when P0 holds `$40` (the UART THR path). All other
  ports are plain bytes.
- **`BRDEV` never branches**, so the monitor's `uartout`/`uartin` and the compiler runtime's `rt_putc`/`rt_getc`
  take their port-2 branch — this is the whole reason the same image runs here and on the machine.
- Writes above `$DFFF` print `Rom Write`, dump the registers and exit.
- An interactive debugger is wired to `HALT` (without `-x`) and to `PC == $0000`: keys `C` continue, `S` single-step
  (prints opcode, PC, ACC, TMP, R3, R7 per instruction), `R` run, `J` step over the current call depth, `D` dump
  $0200, $0F80, $0400, $1000 and the registers. `HALT` without `-x` prints those dumps too.
- `INP P1` returns `$FF` once when P0 = 1 (the first switch read); `INP P4`/`INP P5` go to the CF model (`$FF` from
  P4, the write-only select, and from P5 with no image); `INP` of other ports leaves ACC unchanged.
- Bad opcodes (`$00`, `$A5`, `$AE`, `$80–$8F`, `$F8–$FA`, `BR16Z/NZ`, `IRET`, `INT`) print `bad opcode [xx] pc[aaaa]`
  and exit.

What it does **not** model (the ISA reference has the full table): `BRDEV` on hardware, the carry flip-flop's loads
on SUB and on the plain shifts, R2 as the operand-address register, the suppressed loads of R0, bus fights,
timing, FORCE-ROM, interrupts, the UART's status bits, the video card. `LDTVR`/`STTVR` run here although the
hardware has no microcode for them. Since 2026-09-22 `BRVR` (indirect jump, Rn += 2), `JSRUR` (PC ← Rn, bytes no
longer swapped) and `BRUR` follow the microcode (`tools/patched_files.txt`).

## 3. The microcode-level emulator (`software/ucemu`)

`y1ucemu.c` loads the control store (`firmware/microcode/ucode-generator2/test.hex`: 256 opcodes × 64 steps × 8 bytes,
the signal-to-bit map from `firmware/microcode/yaccsignaldata2.h`) and executes it step by step against a model of
the cards, built from `docs/isa/MICROCODE-REVIEW-NOTES.md` section 1 (the netlists). It reproduces: R2 as the
operand-address register, `BRVR` as an indirect jump, `BRDEV` branching, SUB and every shift loading the carry
flip-flop, loads of R0 gated by the branch-taken latch, FORCE-ROM, and **bus fights** — every step where two sources
drive a data lane with different values is counted and can be listed.

Options (`y1ucemu.c` header):

| Option | Effect |
|---|---|
| `-u FILE` | another control store (default the tree's `test.hex`, relative to the executable) |
| `-m` | load `basic.img` + `monitor.img` (the ROM) as the interpreter does |
| `-f FILE` | load an Intel-hex image; repeatable, later files overwrite |
| `-c IMAGE` | the CF image on P4/P5 (P8/P9 until 2026-09-23) |
| `-x` | scripted: quiet, stdout flushed, `SOFT-HALT` exits; a status line on stderr with instructions, steps, clocks, R3 and the bus-fight count (`... bus fights: N in M`) |
| `-t` | one line per instruction fetch on stderr; `-T` every step with the signals asserted |
| `-w` | list bus fights (opcode, step, drivers) as they first occur (the summary is always printed with `-x`) |
| `-F and\|src` | how a fight resolves: `and` (default) = a low output wins, the lane is the AND of its drivers (the usual TTL outcome, what made H-2 fatal); `src` = the ALU's `-AC-RD` drive loses to any other driver |
| `-s NN` | the byte the I/O card's switches read as (default 0) |
| `-i 0\|1` | the level of the input-switch line that `BRINH`/`BRINL` test (default 0) |
| `-I N` | flip that line every N steps (a bench hand on the switch; `romdiag`) |
| `-R 1\|2` | index-register cards fitted (default 2): with 1, R4–R7 are absent — reads leave the bus to its pull-ups ($FF), loads and counts are lost, as on the 2026-09-22 bench |
| `-L` | report writes to the LED board, the TIL311 displays and the ON/OFF LED on stderr as they change (`LED=25`, `TIL=25`, `ON`, `OFF`) |
| `-l N` | stop after N **steps** |

The model (`software/ucemu/README.md` "The model"): the sequencer (step counter, instruction register latched at the
leading edge of `LD-INS-REG`, operand register, branch register, interrupt vector, the level-sensitive branch-taken
latch, the `N$53` gate for R0 loads, `-2-BYTE-OPERAND-SEL`); two register cards of 74LS192 counters with byte-lane
reads, the straight and swap transceivers, `$FFFF` weak drive on `-REG-FUNC-RD` alone, level-sensitive loads, counts
at strobe end or selection change; the ALU card (function blocks 0–7, accumulator and carry at the leading edge of
`-AC-LD`, the 74LS194 shifter, the 74LS251 condition mux, `-AC-RD` driving `$FF` on DATA8..15); the memory card
(RAM/EEPROM, writes above $E000 ignored, FORCE-ROM, TMP0/TMP1); the I/O card (P0 latch, P1 with a 16550 model on
stdin/stdout — LSR data ready and THRE, DLAB divisor writes accepted — switches and LEDs; a port read sampled at the
leading edge of `-IO-RD`, a write at the trailing edge of `-IO-WR`; reading with nothing left gives 0 with "ready"
set). Port 2 is also a console. Timing: a step is two clock periods, the `UCODE-COUNT-RESET` step one; leading-edge
latches take the previous step's bus, trailing-edge actions the strobe step's values.

**Reset is the real one**: registers and IR cleared, FORCE-ROM set, so the first fetch at $0000 reads ROM[$F000]; a
stand-alone image therefore needs the same first branch the monitor has (the compiler's `--boot` stub, `brur.asm`).
RAM starts as `$FF` (the interpreter's is zero: this found the compiler's uncleared BSS).

Not modelled yet (`README.md`): interrupts beyond the enable/pending latches (no source raises one); the video card;
a per-instruction cost table (the status line has steps and clocks); automatic trace comparison with the
interpreter.

What it found on 2026-09-22 (`README.md`): H-2 real and fatal under the AND rule (a taken `BRZ` landed on offset
$00; the monitor could not print a string), H-1 real (`PUSHR R3` with $ABCD pushed $21CC), two compiler bugs
(uncleared BSS, `DS` padding of partially initialised arrays); with the fixed image the whole compiler suite passes
through the monitor's real console path, the monitor boots from reset, takes `G3000` and returns, 0 fights over 6
million steps; the mechanical review's two-driver count went from 37 to 3.

## 4. Recipes

Build first: `make` at the root (or `make -C software/emulator`, `make -C software/ucemu`).

**The monitor, interactive**

```
software/emulator/emulator            # or: emulator -m ; raw tty, type H at the > prompt, 0 exits
software/ucemu/y1ucemu -m             # from a real reset; the echo is the machine's; 0 loops (BRDEV branches)
```

The interpreter's `cmdloop` accepts LF as "continue", so a terminal's Enter works; addresses are four hex digits with
no space (`E3000`, `G3000`).

**A compiled or assembled program, stand-alone** (image with a `$F000` stub and a `HALT`):

```
software/emulator/emulator -x -f prog.img < input.txt
software/ucemu/y1ucemu -x -m -f prog.img < input.txt      # -m: the runtime's BRDEV path needs the ROM's console
software/ucemu/y1ucemu -x -f brur.img                      # a port-2 program needs no ROM
```

**A program under the monitor** (assembled at $3000, ending in `RET`, no stub):

```
software/emulator/emulator -m -f prog.img      then  G3000  at the prompt
software/ucemu/y1ucemu -m -f prog.img          then  G3000
```

**Y1/OS**

```
make -C os run        # y1ucemu -m -c os/disk.img ; type O
make -C os run-int    # emulator -m -c os/disk.img ; type O
```

**A ROM-resident program** (`ORG 0F000H`, first instruction a branch above $8000): `y1ucemu -x -f romcount.img -s 0x25
-i 1 -L -l 1500000` — no `-m`, the image *is* the ROM; the interpreter can run it too (`emulator -x -f romcount.img`)
but has no switches or LEDs to show.

**Tracing**: `y1ucemu -x -m -f prog.img -t 2> trace.txt` (one line per fetch), `-T` for every step with the asserted
signals, `-w` for the fights. The interpreter's `S` key single-steps interactively.

**Reproducing a bench symptom**: `-R 1` (one register card), `-s`/`-i`/`-I` for the switches, `-F src` for the
other fight outcome, `-u old.hex` for a previous control store (e.g. the image the EEPROM held before 2026-09-22, if
kept: `cache` in the generator folder is what was last sent).

## 5. Capturing a session for a test

Every suite is a script that runs an emulator with a canned stdin and compares stdout with a committed expectation;
adding a case means adding files, not code:

- **Compiler program** (`tests/compiler/run.py`): add `NAME.c`, optionally `NAME.in` (stdin) and a `// y1cc: flags`
  line; generate `NAME.out` with `run.py NAME --oracle` (host `cc` through `host_shim.h`) or write it by hand and add
  `// no-oracle`; a `NAME.err` file instead expects a compile error. The same program then runs on ucemu via
  `tests/ucemu/run.py`; if the monitor's input echo changes the transcript, add `NAME.ucout`.
- **OS session** (`tests/os/run.py`): add `tests/os/NAME.session` (one shell line per line; `O\n` is prepended);
  run `run.py --update` to write `NAME.int.out` and `NAME.uc.out`, check them by eye, commit. The comparison runs
  from `BOOT FROM CF` to the prompt after `bye`; CR LF pairs are preserved (`newline=""`).
- **ROM program with LEDs** (`tests/assembler/romcount/run.py`, `romdiag/run.py`): the expectation is the list of
  `LED=`/`TIL=`/`ON`/`OFF` lines from `-L` on stderr plus the `bus fights: 0 in 0` status; the scripts also
  re-assemble the source and compare the `.img` and the `img2bin` `.bin` with the committed ones.
- **ISA differential** (`tests/ucemu/isa.asm`): write results raw to port 2; `tests/ucemu/run.py` compares the two
  emulators' byte streams. (`isa.asm` is run by hand today: the runner's list is the compiler programs plus `brur`.)
  **To verify:** whether `isa.asm` is wired into any runner — `grep isa tests/ucemu/run.py` finds nothing, so its
  comparison is a manual step.
- **A monitor session** by hand: `printf 'H\n0\n' | emulator -x -m` captures the help text; on ucemu use `-l` to
  bound the run since `0` loops there.

Exit codes: every runner exits 1 on any failure, so they chain in `make check` ([TOOLCHAIN.md](TOOLCHAIN.md)).

## Live console connections (2026-09-23)

The microcode emulator can now be driven by a live program on a pseudo-terminal, not only by a finished input file: its
UART status read no longer blocks waiting for input (see `software/ucemu/README.md`). `tests/monload/run.py` relays a pty
to `y1ucemu -x -m` and runs `tools/monload.py` against it, the same way it would talk to the machine's UART.
