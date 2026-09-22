# BACKLOG — unbuilt work, open questions, verification still to do (2026-09-20)

Gathered from the card/folder READMEs and the old notes so that pending work is visible in one place. Built state:
`docs/system/MACHINE.md`. Which revisions exist and were fabricated: `hardware/FABRICATED.md`.

## Hardware — designed, not built
- **Blank V3.2** (`hardware/bus/blank-card/eagle/v3.2`): derived 2026-09-20 from V3.1 with the Bus V3.2 names on C3–C6.
  Open it in Eagle/Fusion, re-save, use as the template for every new card.
- **Bus Tester V3.1** (`hardware/cards/bus-tester/eagle/v3.1`, 2020-07): latches drive the bus, soft bus-enable/reset,
  bypass caps; routed, CAM run, never ordered. Decide: build it, or keep the 2016 v1.1 for good.
- **Video card v1.1** (`hardware/cards/video/kicad/v1.1`, the KiCad master since 2026-09-21; Fusion abandoned): DONE in the
  design — one 5 V rail (`+5V` folded into `VCC`, joining track added; proof 116/116). TO DO — move the 6845 RS from A0 to A1
  (`hardware/cards/video/docs/fix-6845-register-select.md`; bench job first), pull-ups on the 7416 outputs; then order.
- **Sequencer logic v2.2: a "CPU off" switch** (`hardware/cards/sequencer-logic`). Today the card's outputs can never be
  silenced while the memory card is enabled: -BUS-EN is generated on the card itself (IC36 74LS04 from the sequencer's
  READY line) and is also the output enable of all nine pipeline 74LS374s and the two microcode-address 74LS244s; -RESET
  only clears the instruction register and step counter, so in reset the pipeline still drives every control line (word
  instruction 0 step 0: -VMA asserted, R0 selected as address source, the rest driven inactive). The bus tester therefore
  cannot load RAM with the logic card fitted (found 2026-09-21; every switch on the card is in use and the -BUS-EN copper
  cannot be split with one cut). Change: (1) route the 374/244 output enables through a new switch or jumper, RUN = follow
  -BUS-EN, OFF = pulled high - AND the 17 lines the 2026-09-21 review found driven regardless of -BUS-EN (IC4/IC5/IC18 select
  buffers, -REG-LD-LO/HI, -RESET, OUT); (2) make the READY-to-BUS-EN driver open-collector (or jumperable) so the bus tester can own
  -BUS-EN without shorting the LS04. With that, the tester loads RAM with everything plugged in. Until then: ROM monitor
  over the UART, or unplug the logic card.
- **IO V1.2 ideas** (IO notes): directional data-bus buffer driven by -IO-RD; 74138 IC5 pin 5 tied to -BUS-EN.
- **Index Registers**: notes ask whether bus direction should follow -RD-SEL (the same question as the IO buffer).
- **Memory v1.3 notes**: "should TMP registers move to the ALU", hard-jumper a boot-loader enable, 4K-block EEPROM select.
- **Sequencer logic notes**: expose ucode-count-reset / instruction number for an external debugger; HALT LED.
- **Memory card**: the unconnected jumper wire on IC7 pin 4 — purpose not remembered (Ken 2026-09-20); trace it on the board or remove it.

## Firmware — written, not burned / loaded
- **Monitor + BASIC 8afde21** (2021-09, `firmware/*/candidates/2021-09-8afde21`): `charavail` BIOS vector ($FFEC),
  BASIC ON/OFF statements, break into a running program. Needs a hardware test, then burn and update `rom/shipped`.
- **monnew-2025** (`firmware/monitor/monnew-2025`): small D/M/B monitor; assembled, never run on the machine.
- `firmware/abi/` — the BIOS/port/variable map still has to be written from the two .asm headers.

## Design review 2026-09-21 (reports: `hardware/DESIGN-REVIEW.md`, `hardware/DESIGN-REVIEW-NOTES-datapath.md`,
`hardware/DESIGN-REVIEW-NOTES-control-io.md`, `docs/isa/MICROCODE-REVIEW.md`, `docs/isa/MICROCODE-REVIEW-NOTES.md`)
Items below were traced to nets/pins or to test.hex and spot-checked; the reports give the evidence and a bench check each.
- **HIGH, microcode: 38 undefined opcodes are all-zero words** ($80-$8F, $A5, $AD, $AE, $C0-$CF, $F8-$FA). An all-zero word asserts
  every active-low line (-MEM-RD and -MEM-WR together, every register strobe) for 61 steps: a bus fight on any stray opcode.
  Fix in `firmware/microcode/ucode-generator2`: fill undefined opcodes with an inactive word + UCODE-COUNT-RESET (a 1-step trap).
- **HIGH, microcode: PUSHR** writes both stack bytes while the register card and TMP1 both drive the data bus (read strobes never
  cleared); **BRZ/BRNZ/BR16Z/BR16NZ** keep -AC-RD on while -BRANCH-RD loads the PC; BR16Z/NZ cannot work (BDATA8-15 are pull-ups
  under -AC-RD). None exercised by `ledcount`; bench order in the notes: IC11 scope check, then BRZ, then PUSHR.
- **HIGH, logic card: 17 bus lines driven regardless of -BUS-EN** (REG-RD-ID/REG-LD-ID/ADDR-REG-ID via IC4/IC5/IC18 enabled by the
  operand-select pipeline bits; -REG-LD-LO/HI, -RESET, OUT from plain gate outputs). The v2.2 "CPU off" switch must cover these
  too, and bus-driver on the tester fights them whenever the logic card is fitted.
- **HIGH, BOM: step counters and all 16 register counters are 74LS192 (BCD)** in schematic/board/BOM (`sequencer-logic` IC33/34,
  `register` x16); the machine runs 32-step binary microcode, so 74LS193 must be fitted. Read a chip label; fix the design files.
- **HIGH (masked), memory v1.3: FORCE-ROM race** - IC12 (74LS74) is clocked by ADDR15·-VMA·-BUS-EN while the register card puts the
  address up ~40 ns after -VMA and the address bus floats high between cycles; masked since 2020 by asserting -VMA in EVERY
  microcode step (`main.c:103,115` "Hack prevent ROM mapping from triggering"), which removes -VMA from all memory chip selects.
- **HIGH (untested), video v1.1: 6845 E clock** derived from C1/R1 discharged by a 7416 open-collector output with no pull-up;
  unreliable at run speed. Goes with the RS-to-A1 change and the 7416 pull-ups before a CRTC is fitted.
- **MED**: 28C64 -WE is raw -MEM-WR (any store during FORCE-ROM writes the EEPROM; the monitor is safe only because its first
  instruction jumps above $8000); reset does not reload the pipeline (stale word on the bus during reset, with FORCE-ROM active);
  no power-on reset anywhere (FORCE-ROM, counters, carry undefined until the button); register card IC34 is a CD4077 driven by LS
  levels; count strobe = OR(-Rx-RDSEL, -REG-UP) counts a deselected register on a REG-RD-ID change; the register card drives $FFFF
  onto DATA0-15 on every increment step, overlapping -MEM-RD (327 steps); one-step memory windows before leading-edge latches
  (LDTI, LDIVR, LDT, BRANCH-LD, INT-LD) are the first to fail at a faster clock; JP2 on the logic card would hold the sequencer
  card in reset; video character clock is a ~50 ns runt; TMP registers latch on the leading edge (microcode must present the
  source a step early - it does).
- **LOW / speed**: 351 idle steps; the 6-step fetch prologue could be 3 (~22% of executed steps); ~30% total savings tabulated per
  opcode in the microcode notes; emulator mismatches listed there (BRVR, JSRUR byte order, carry on SUB/shifts, R0-load suppression).
- Timing-diagram model (`tools/ucode_wavedrom.py`) corrections from the review: IR/operand/branch/TMP/ACC latch on the LEADING
  edge of their strobe; one step = two clocks; steps 0-2 run with the previous opcode in the IR; -REG-RD-LO/HI are byte lanes.
  To fold into the generator when the diagrams are next regenerated.

## Software
- Every C tool now has a plain Makefile (2026-09-20); the NetBeans projects are kept but no longer needed to build. The three
  tools still carry the old tree's relative include paths, satisfied by `tools/layout_links.py` symlinks; fixing the includes
  would let the links go.
- **Test-vector generator uses the 2016 signal names** (`tests/bus-tester-scripts/Gen Test Vectors/`): it emits the
  2016 register-card codes (REG-FUNC-LD, REG-BRD-LD-ID, WDATA/RDATAL) which are not in the 2020 bus table, where the card
  select became REG-LD-ID2..3 / ADDR-REG-ID0..3; the `fix` converter only maps BUS-WR. Rewrite it against the current
  signal table before generating vectors for the 2020 Index Register cards.
- **Replace the Processing command sender with a Python host** (Ken, 2026-09-20). `embedded/command-sender/command_sender_8`
  builds again under Processing 4.5.6 (2026-09-20 fixes) but is a dead end. `tools/busdrv.py` already speaks the bus tester's
  `CMD:OPERAND#` / `>>` protocol; still needed is the script interpreter from the sketch: `//` comments, `:label` + `GOTO`,
  `LET`, `FOR`/`NEXT`, `DUMP start end`, `WAIT`, `DUMPVARS`/`DUMPLABELS`, and `CMD:OP#EXPECTED!VAR` return-value matching
  and capture (hex in the scripts, decimal on the wire). Retire the sketch to `deprecated/` once the Python version runs the
  scripts in `tests/bus-tester-scripts/` on the bench.
- (done 2026-09-21: `embedded/sequencer-card/sequencer4` reads the copy back before READY and refuses on a mismatch; copy 16 s
  + verify 29 s instead of 156 s; sequencer3 deprecated)
- **Monitor loader `tools/monload.py`** — push an assembled program into RAM through the ROM monitor's `E` command over the
  serial console (the monitor has no hex loader; `L` lists BASIC). Protocol from `firmware/monitor/monitor.asm` (`examine:`):
  send `E` + 4 hex address; the monitor prints `AAAA XX ` and waits; two hex characters replace the byte and advance to the
  next address (no CR); CR advances without change; `-` or Esc ends. Loader: open the IO-card UART (38400, the FTDI on the
  card's TTL header), send `E<addr>`, feed the bytes pacing on the echoed address, send `-`, optionally `G<addr>` to run.
  Input = the assembler's `.prg` (`:AAAA b b b ...` lines, `*START`). TEST FIRST ON THE EMULATOR: `software/emulator` runs
  the same monitor on stdin/stdout (raw tty, blocking uartin), so the loader needs a pty/subprocess mode. Load above $1000
  (monitor variables at $0F00, stack down from $0EFF). Sample program: `tests/assembler/ledcount`.
- Port of the P8X work (OS, monitor, BASIC, compilers) onto YACC1 — the reason this repo exists; not started.

## Verification still to do
- (done 2026-09-21: both ATmegas now run tree builds, verified by reading the flash back; the previous binaries are in
  `embedded/*/readback/`)
- (done 2026-09-20: `tools/verify_embedded.py`, 12 sketches compile against the vendored libraries)
- Memory v1.3: the 2025 gerbers came from Fusion's CAM; overlay them against the tree's Eagle board (netlist proven, gerbers not).
- (answered 2026-09-20: jumper boards not fitted/obsolete, EEPROM adaptor fitted, two register cards, RN2 = 1k; bus tester
  firmware settled 2026-09-21 by reading the flash out; sequencer likewise = Sequencer3) — no **(confirm)** marks left.

## Tree / docs
- (done 2026-09-20: every `.rtf` outside archive has a Markdown twin; `tools/rtf_to_md.py`)
- Theory-of-operation write-ups per card (`docs/cards/`), architecture / memory map / microcode format (`docs/system/`).
- KiCad conversion of the remaining cards with the memory-card toolchain (`tools/kicad/`); Eagle then frozen.
- `git init` (no LFS), first commit, GitHub repo; decide whether `archive/` (190 MB) is committed or kept as a separate repo.
- Move off NetBeans (README decision 7).

## C compiler (y1cc, 2026-09-22)
`software/compiler/y1cc.py` compiles p8cc's C subset to YACC1 assembly (static frames, R3 accumulator, see its README);
12 test programs pass on the emulator (`make cc-test`), 9 of them checked against the host C compiler as an oracle.
- **Run a compiled program on the machine.** Needs RAM loading: the monitor E-command loader (`tools/monload.py`, above) or
  the bus tester with the CPU held off (v2.2 CPU-off switch). Then `G3000` (the image starts with the vector BRVR needs; $1000 is BASIC's buffer).
  First hardware checks: `rt_sub` (INVA/moves between ADDTC), `rt_divmod` (SUBT/SUBI after a comparator branch), the
  shifts (`LDAI 0 / CSHL` carry clear), `BRDEV` selecting the BIOS path, and that `BR $F000` after main is acceptable
  (it restarts the monitor: BASIC cold start, banners). A `cmdloop` BIOS vector would be cleaner than the restart.
- Stack-frame mode (`--frames`) for recursion/reentrancy, at ~4x the cost per local access; or overlaying the static
  frames of functions that are never live together (cheap, no semantic change).
- `switch`, signed `int` (BRLT/BRGT are unsigned comparators: signed compare = flip bit 15 first), `long`, `goto`.
- Code size: peephole over R3/R4 traffic (store-then-reload across labels, `MVIW R3,k / MVRLA R3` → `LDAI`), 8-bit paths
  for char arithmetic (`c + 1` still goes through 16-bit add), constant compares with a zero high byte, `for` loops
  counting down to 0. Measure with `run.py` (bytes + instruction counts per test).
- Cycle-accurate cost model: the emulator counts instructions; weighting by the microcode step counts (`docs/isa/README.md`)
  would give clock cycles.
- Port the P8X libraries/programs that fit the subset (the P8X OS itself needs the stack-frame mode and its syscalls).
- Emulator (done 2026-09-22, `tools/patched_files.txt`): `-x` scripted mode; BRVR and JSRUR now follow the microcode, so the
  monitor's `G` and `T` commands work on the emulator (they never had). Still stubs vs the hardware: IRET/INT/IADDR, SUB
  borrow into carry, shifts loading carry, opcode $00, LDTVR/STTVR (emulator runs them, hardware has no microcode).
- Assembler (done 2026-09-22): `DS` flushes the hex record. Still open: negative numbers silently mis-assemble, labels
  over 29 chars crash it, source lines are upper-cased (strings in `DB "..."` come out upper-case).
