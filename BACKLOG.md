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
