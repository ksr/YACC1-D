# BACKLOG — unbuilt work, open questions, verification still to do (2026-09-20)

Gathered from the card/folder READMEs and the old notes so that pending work is visible in one place. Built state:
`docs/system/MACHINE.md`. Which revisions exist and were fabricated: `hardware/FABRICATED.md`.

## Hardware — designed, not built
- **Blank V3.2** (`hardware/bus/blank-card/eagle/v3.2`): derived 2026-09-20 from V3.1 with the Bus V3.2 names on C3–C6.
  Open it in Eagle/Fusion, re-save, use as the template for every new card.
- **Bus Tester V3.1** (`hardware/cards/bus-tester/eagle/v3.1`, 2020-07): latches drive the bus, soft bus-enable/reset,
  bypass caps; routed, CAM run, never ordered. Decide: build it, or keep the 2016 v1.1 for good.
- **Video card**: RN2 is currently 1k (design says 10k, changed during the 2026-09-18 tests) — decide which value stays.
- **Video card fixes** (`hardware/cards/video`): 6845 CS/RS both on A0; 7416 outputs need pull-ups; block-0/9
  write-through fault to be diagnosed (ADP2230 capture on IC18 pin 6). Fusion 360 is the master — decide whether the
  tree's Eagle export (or a KiCad conversion) becomes the master.
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
- The three C tools carry the old tree's relative include paths; `tools/layout_links.py` symlinks cover it. When the
  NetBeans → Makefile move happens (README decision 7), fix the includes and drop the links.
- Port of the P8X work (OS, monitor, BASIC, compilers) onto YACC1 — the reason this repo exists; not started.

## Verification still to do
- Rebuild `embedded/bus-tester/bus-driver` and `embedded/sequencer-card/sequencer3` with arduino-cli from the tree and
  upload them, so the boards run exactly what the tree records (today: assumed).
- Add an arduino-cli compile check for every sketch (the C tools and firmware already have `tools/verify_firmware.py`).
- Memory v1.3: the 2025 gerbers came from Fusion's CAM; overlay them against the tree's Eagle board (netlist proven, gerbers not).
- (answered 2026-09-20: jumper boards not fitted/obsolete, EEPROM adaptor fitted, two register cards, RN2 = 1k) — the only
  remaining **(confirm)** is the ATmega firmware above.

## Tree / docs
- Per-revision `Notes.rtf` → Markdown twins (git can't diff rtf).
- Theory-of-operation write-ups per card (`docs/cards/`), architecture / memory map / microcode format (`docs/system/`).
- KiCad conversion of the remaining cards with the memory-card toolchain (`tools/kicad/`); Eagle then frozen.
- `git init` (no LFS), first commit, GitHub repo; decide whether `archive/` (190 MB) is committed or kept as a separate repo.
- Move off NetBeans (README decision 7).
