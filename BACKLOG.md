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
  `register` x16); the machine runs 32-step binary microcode, so 74LS193 must be fitted. (2026-09-23: the board photos in
  `media/` read **SN74HC193N** at IC33/IC34 and on the register counters, and 74HC parts through much of the sequencer, ALU
  and register cards, so the machine is right and the DESIGN FILES are wrong; `docs/cards/sequencer-logic.md` / `register.md`.
  Still to do: confirm the markings on the second register card, then fix schematic/BOM.)
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
- (done 2026-09-23: **the monitor's `:` Intel-hex loader and `tools/monload.py`** — records answered `.`/`?`/`!`, $1000-$DFFF only,
  read-back verify, ESC abandons; host tool paces 3 ms/char and waits per record, `--go`, `--listen`, `--term`; tested on both
  emulators and over a pty (`tests/monload/`); burned 2026-09-23 and the monitor boots on the machine. The E-command scheme planned here was dropped.)
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

## Disk operating system (plan `docs/system/OS-PLAN.md`, decisions 2026-09-22)
- (done 2026-09-22 evening: phase 1 — CF model in both emulators, ROM driver + `O` boot + vectors, p8xfs/img2bin; phase 2
  read-only — `os/y1os.c` shell with dir/cd/pwd/cat/load/run and /BIN programs, `tests/os/` sessions on both emulators.)
- (designed 2026-09-23: **the CF card v1.0** — `hardware/cards/cf/kicad/v1.0/` generated from `cf_netlist.py`: 5 ICs
  (74LS138/32/175/08/245), 40-pin IDE header for a CF-to-IDE adapter, schematic and board both proven equal to the
  netlist, DRC 0 errors / 0 unconnected, gerbers ready; theory in `docs/cards/cf.md`.) **Before ordering**: check Ken's
  CF-to-IDE adapter against J1 (fit, overhang, ribbon or direct) and its power connector against J2 / JP1; check X1's
  position on a real card (the blank V3.2 it came from was never fabricated); confirm the I/O card's IO-ADDR-HL strap
  is P0-P7. **After building**: the bring-up steps in `docs/cards/cf.md` section 7 (empty adapter = `CF ERROR`, the P8
  latch on J1's DA pins, then `O` with a card prepared by `dd` from `os/disk.img`); write the card-preparation procedure.
- (done 2026-09-23: **write support** — save/del/ren/mkdir/rmdir in the shell, files written at the free pointer and
  registered as `p8xfs.py` does, verified from the host in `tests/os/run.py` (fsck, ls, get); **the file API** —
  a 22-entry syscall table at $0F14 (SYSARG/SYSRES at $0F06..), y1cc's `sys()`/`funcaddr()` builtins, `os/lib_fs.c`
  wrappers (fopen/fread/fgetc/fclose/fcreate/fwrite/fputc/fdelete/fmkdir/frmdir/opendir/readdir/fresolve/fentry/
  getcwd/chdir/frename/conin/constat), four handles with their own buffers; CONIN through a new ROM vector UARTINNE
  $FFFC (no echo; ROM rebuilt, still unburned); ARGBUF 128 bytes; first commands on the API: CAT2 (retired the same day for the ported cat), WC, LS, CP;
  OS image 12,183 bytes = 24 sectors; `os/README.md`.)
- (done 2026-09-23: **PACK** — `/BIN/PACK` (`os/commands/pack.c`, 5,397 bytes + 9.3K tables; a program, the OS image
  did not grow): iterative tree walk into a record table, sort by start LBA, layout check, each extent moved down
  sector by sector, entries rewritten where their directory is now, '.'/'..' fixed; refused under `<`/`>`/`>>`/`|`;
  keeps the current directory (GETCWD/CHDIR); `pack -v` shows each move and its steps. **Reset-safe** (second version
  the same day): an extent whose hole is smaller than itself moves in two steps through a scratch area above the free
  pointer (raised over it before the first move), so every entry always points at a complete copy; `tests/os/run.py
  --cuts 60` cuts pack off at 120 points in two fragmented volumes, every phase hit, and after each cut fsck passes,
  every file is byte-identical and a rerun completes (120/120; a one-step-only build fails 16 of 40). The OS re-reads
  the free pointer after every program (`read_free()`), zeroes its state through main's BSS clear only, `save` closes
  its handle after a failed write (a leaked write handle was the one open file STDIO could not show), and
  `take_entry()` counts sectors without the 16-bit wrap of `(e_len + 511) / 512` (65,025..65,535-byte files were 1
  sector), and `load` checks the size against the program area without the wrap of `e_load + e_secs * 512` (a 64K file
  passed the check and overwrote all of memory). `p8xfs.py fsck` checks '.'. `tests/os/pack.session` with host checks
  (no dead sector, every pristine file byte-identical, the next file at the new free pointer); `os/man/pack`. OS image
  14,619 bytes, image + data 16,043.)
- **PACK reset window (found 2026-09-23 by `run.py --cuts 60`, 1 of 120):** in a two-step move of a DIRECTORY, a cut
  after the copy down but before the entry's final rewrite (`631>630 via 687: ceC`) leaves a child's `..`
  (`/PK/SUB/..`) pointing at the scratch copy (687) while its parent's entry already says 630: fsck fails until the
  next pack's repair pass fixes it (no file is lost; the rerun passes). The same cut fails identically with the C OS
  and the assembly OS (pack does its own raw sector I/O); earlier runs passed only because no cut point landed in
  that ~20,000-instruction window, and the man-page/README edits of the same day moved the layout. Either rewrite the
  '..' of the subdirectories before the parent's entry moves off the scratch copy, or let fsck accept a '..' that
  points at an identical copy; `os/README.md`'s "a '..' that lags one step" says the second is the design.
- PACK, what is left: the "no room on the card" refusal for the scratch area rests on a real card rejecting an LBA
  past its end (the emulators' CF model reads zeros there and grows the image), so try it on the CF card once it
  exists; a nearly full card cannot pack a big file that sits behind a small hole (the scratch area needs its size
  above the free pointer). Tombstones are not squeezed out of directories (the OS reuses them, so nothing is lost).
  800 files and directories at most; every sector past the first hole is copied, one at a time, two-step moves twice.
- Y1/OS still to write: FORMAT and FSCK on the target, seek, more than one write handle (needs allocation away from
  the single free pointer; it would let `cp`/`touch`/`save`/`mkdir`/`vi :w` work inside a `>` or a pipe).
- (done 2026-09-23: **the P8X commands, waves 0-2 of `os/PORT-PLAN.md`** — shared libs `os/lib_*.c` (stdin, rdline,
  glob/globx with an iterative gmatch, regex with a backtrack stack, walk = a recursion-free tree walker on one
  directory handle, apath, more = the pager, num, err); /BIN pwd help dep dump examine man cat wc head tail more sort
  uniq sed awk cmp diff md touch del mv tree find dir grep cp (cat2 retired); man pages in `os/man/` -> /MAN, Markdown
  docs -> /DOCS, sample data /FRUIT.TXT /FRUIT2.TXT; the shell runs /BIN/NAME before a built-in of the same name;
  `tests/os/wave1.session`, `wave2.session` with host-side p8xfs checks. Status per command in PORT-PLAN section 2.)
- Wave 3 of the port: `asm` (on-target assembler for the RC/asm dialect, table generated from `yacc1.def`), a YACC1
  `disasm`; `vi` is being ported separately. Then BASIC as /BIN/BASIC. The assembly OS has 18 sectors of headroom in the
  16K reserve (LBA 1..32) and 7,711 bytes free below its RAM (2026-09-23, v0.2).
- (done 2026-09-23: **redirection and pipes** — `cmd [< in] [> out | >> out] [| cmd ...]`, up to 4 commands, clauses
  after the arguments, quotes protect `| < >`; `y1cc --os` makes putchar/puts the new syscall CONOUT (19) and getchar
  CONIN, KEYIN (20) is always the keyboard (pager, vi, dump, examine), STDIO (21) says what is redirected (the pager
  stops paging into a file); pipes run stage by stage through /PIPE0.TMP and /PIPE1.TMP, deleted after the line;
  `>>` appends in place when the file is the last one written, else copy-then-extend; CREATE now replaces a same-named
  file at CLOSE (the new entry over the old slot); eputs() and the shell's errors go to the raw console; the four
  handle buffers moved to $0400-$0BFF to fit (OS image 14,673 bytes = 29 sectors, image + data 16,097 of 16K);
  `tests/os/redirect.session`, `pipe.session` with host checks; `os/man/shell`.)
- Redirection and pipes, what is left: SYSTAB is full (see the SYSTAB item below); no `2>` (errors always go to the screen); stages run one after the other, not concurrently; a
  redirect clause must follow the arguments (`echo > F hi` is a syntax error); a write that fails part-way (disk full,
  64K) drops bytes silently. (The space problem is gone with the assembly OS: 7,711 bytes free, below.)
- (done 2026-09-23: **the OS in assembly, v0.2** — `os/y1os.asm` (hand-written, 3,415 lines) replaces the C OS as
  the default: 7,137 bytes = 14 sectors instead of 14,619 = 29; its RAM at fixed aligned addresses $4A00-$4F0F, so
  $2BE1-$49FF (7,711 bytes) is free; messages in `os/strings.txt` -> numeric DB lines by `os/mkstrings.py`. Same
  behaviour and ABI: every `tests/os` session passes on both emulators with either OS (run.py compares the banner
  without its version; transcripts changed only in the banner), `--cuts 60` 120/120 (119/120 after the day's doc edits moved the disk layout: the PACK reset window below, identical with the C OS), and a C-vs-asm differential
  run (same disk and keystrokes, transcript and every data sector compared) agreed on the sessions plus the
  built-ins /BIN hides, load limits, redirect/pipe edge cases and a syscall torture program. Instructions to `exit`,
  C -> asm (interpreter; ucemu steps the same ratio): basic 1.53M -> 0.99M, api 1.80M -> 1.11M, write 2.84M -> 1.95M,
  wave1 5.04M -> 3.20M, wave2 5.68M -> 3.63M, redirect 1.88M -> 1.25M, pipe 9.57M -> 4.91M, vi 1.11M -> 0.84M,
  pack 29.97M -> 15.78M (1.3-1.9x). `make -C os OS=c` builds the C OS, still the specification.)
- **SYSTAB 22 -> 32 entries, not done (2026-09-23).** The assembly OS has the room, but the table's address is
  compiled into every program (`LDR R7,SYSTAB+2n`) and hard-coded in `tests/compiler/syscall.c` and the committed
  bench image `tests/bench/images/syscall.img`; it cannot grow in place without moving ARGBUF. When the 23rd syscall
  comes: the smallest change is the whole table at $4FC0-$4FFF (kept free in the assembly OS's RAM, and above the C
  OS's data), `SYSTAB`/`SYSMAX` in `y1cc.py` (rt_putc/rt_getc follow the constant) and `os/lib_abi.c`, the two tests
  above re-made, `firmware/abi/README.md`; every program is rebuilt by the Makefile anyway.
- **Y1/OS behaviours kept by the assembly rewrite (y1os.c's, the transcripts are the contract; fix both together):**
  CLOSE of a
  directory handle returns 3 (its mode), of a read handle 1, not "1" as documented. A trailing slash after a file name
  resolves (`fopen("README.TXT/")`). CHDIR with a component over 12 characters matches the entry named by its first
  12 and puts the whole typed name in the path (`cd /D1/AAAAAAAAAAAAXYZ`). DELETE returns 1 when the tombstone write
  fails. `ren A B C` names the file "B C".
- (done 2026-09-23, both OSes: PUTC/WRITE through anything but the open write handle refused — handle 0 with no write
  open used to write $0200 and then LBA 0, the boot block; `load`/`run` of an empty file refused with "bad load address
  or size"; `tests/os/badhandle.session` + `badh.c`, host checks fsck, boot block, pristine files. The asm image is
  7,151 bytes.)
- `software/emulator` (instruction level) treats a lower-case `q` on the console as end of input (`mygetchar()`,
  an old quit key): a command line containing `q` (`uniq`, `sed s/q/x/`) is cut there. Sessions use `UNIQ` and `Q`
  until it is fixed; the microcode emulator has no such quirk.
- Y1/OS details found while writing the man pages (2026-09-23, not fixed): `path_push` stops extending the textual
  current path past 62 characters while `cd` still descends, so the prompt/GETCWD (and every command's `abspath`)
  point at the wrong directory that deep; the built-in `rmdir` says "not an empty directory" for every failure.
  (The `load_file` whole-sector overrun past $CFFF was fixed the same day: the check now uses the sector count.)
- `vi` redraws the whole current line on every keystroke in insert mode (`<ESC>[r;1H` + line + `<ESC>[K`): fine on the emulators, ~80 bytes per key at 9600 baud on the machine; redraw only from the cursor, or just echo the character when appending at the end of a line.
- Phase 4: video card v2 (6845 on ports PA/PB, 2K RAM) + PS/2 keyboard behind the console vectors.
- (done 2026-09-22: `yacc1.def` P8=9 typo -> P8=8.)

## C compiler (y1cc, 2026-09-22)
`software/compiler/y1cc.py` compiles p8cc's C subset to YACC1 assembly (static frames, R3 accumulator, see its README);
12 test programs pass on the emulator (`make cc-test`), 9 of them checked against the host C compiler as an oracle.
- **Burn the rebuilt ROM** (`firmware/rom/shipped/rom`, 2026-09-22: monitor G = `JSRUR R7`, was the indirect `BRVR R7`; BASIC
  unchanged), then re-capture and `tests/memory/rom_verify.py` (until then it reports the monitor half as different).
  Until burned, compile for the machine with `--vector`.
- (done 2026-09-22: the sequencer EEPROM holds the regenerated image — BRUR at $AD, the H-2 fix in BRZ/BRNZ/BR16Z/BR16NZ, the
  H-1 fix in PUSHR; six records differed, all 256 sent with `tools/ucode_send.py --all`; the scope look at the old image's
  bus fight was skipped.) **Bench-check the reloaded microcode** (first evidence 2026-09-22/23: `tests/assembler/romcount` ran overnight from ROM — BRNZ, DECR, MVRHA, MVAT/MVTA, ADDI, OUTA/INP, BRINL — after `romdiag` had shown the bring-up machine lacked register card 1; card fitted, R7 reads correctly). The rest is ONE command since 2026-09-23: burn the ROM, then
  `python3 tests/bench/run.py --port /dev/cu.usbserial-X` loads and runs hello, BRUR (`ABC0123`), the ISA sweep (every
  instruction, one hex byte each) and 12 compiled C programs through the `:` loader and diffs each against the microcode
  emulator's transcript; the log lands in `tests/bench/logs/` (`docs/procedures/BRING-UP.md` section 6b).
- **Run a compiled program on the machine.** Burn the 2026-09-23 ROM, then `tools/monload.py prog.img --go 3000` (the `:` loader); the compiler suite is in `tests/bench/`.
  First hardware checks: `rt_sub` (INVA/moves between ADDTC), `rt_divmod` (SUBT/SUBI after a comparator branch), the
  shifts (`LDAI 0 / CSHL` carry clear), `BRDEV` selecting the BIOS path, and that `BR $F000` after main is acceptable
  (it restarts the monitor: BASIC cold start, banners). A `cmdloop` BIOS vector would be cleaner than the restart.
- Stack-frame mode (`--frames`) for recursion/reentrancy, at ~4x the cost per local access; or overlaying the static
  frames of functions that are never live together (cheap, no semantic change).
- (done 2026-09-22: `switch`, compare chain or BRUR jump table by size, `--no-brur` until the microcode is reloaded.)
- Function pointers (`BRUR`/`JSRUR`), signed `int` (BRLT/BRGT are unsigned comparators: signed compare = flip bit 15
  first), `long`, `goto`.
- Code size: peephole over R3/R4 traffic (store-then-reload across labels, `MVIW R3,k / MVRLA R3` → `LDAI`), 8-bit paths
  for char arithmetic (`c + 1` still goes through 16-bit add), constant compares with a zero high byte, `for` loops
  counting down to 0. Measure with `run.py` (bytes + instruction counts per test).
- (done 2026-09-22: `software/ucemu` counts steps and clocks; a per-opcode cost table from it is a one-liner away.)
- Microcode emulator follow-ups: interrupts (a source, INT/IRET/IADDR checked against the generator), the CF ports P8/P9
  and a disk image (OS-PLAN phase 1), automatic trace comparison against the interpreter, the video card.
- Port the P8X libraries/programs that fit the subset (the P8X OS itself needs the stack-frame mode and its syscalls).
- Emulator (done 2026-09-22, `tools/patched_files.txt`): `-x` scripted mode; BRVR and JSRUR now follow the microcode, so the
  monitor's `G` and `T` commands work on the emulator (they never had). Still stubs vs the hardware: IRET/INT/IADDR, SUB
  borrow into carry, shifts loading carry, opcode $00, LDTVR/STTVR (emulator runs them, hardware has no microcode).
- Assembler (done 2026-09-22): `DS` flushes the hex record. Still open: negative numbers silently mis-assemble, labels
  over 29 chars crash it, source lines are upper-cased (strings in `DB "..."` come out upper-case).
