# BACKLOG — unbuilt work, open questions, verification still to do (2026-09-20)

Gathered from the card/folder READMEs and the old notes so that pending work is visible in one place. Built state:
`docs/system/MACHINE.md`. Which revisions exist and were fabricated: `hardware/FABRICATED.md`.

## Hardware — designed, not built
- **Memory card: the FORCE-ROM race fix (review M1, 2026-09-30) - a 470 Ω pull-down on ADDR15.** Undriven, A15
  floats high, so IC12 is clocked ~40 ns before the real address arrives. v1.3 in the machine: fit 470 Ω from IC10 pin 4
  to IC10 pin 7 on the solder side (`docs/cards/memory.md` 4.1 has the why, the value and the check); read the bus
  tester's RN4 value first (pull-ups on the address lines: 10 kΩ is fine, 1 kΩ is not). v2.0: **done** - R15 (470 Ω,
  beside the bus connector, pin 1 on the ADDR15 track; `hardware/cards/memory/kicad/v2.0` README). Then,
  optional and separate: drop the `-VMA`-in-every-step hack from the microcode generator (a reload) so the chip selects
  are qualified by -VMA again.
- **RESOLVED 2026-10-10 (the POPR microcode fix, end of this item): BASIC programs go wrong at RUN on the machine: a $00 read from the program buffer comes back with bits set
  (2026-10-08, open; found with ROM 2026-10-07 MD5 122f1a93... and microcode stage 2; the machine runs stage 1 and ROM 2026-09-23 since that evening).** Both emulators run every program below
  correctly. On the machine (`tools/y1term.py --send FILE --new --run`):
  - `10 l=0 / 20 c=0 / 30 c=c+1 / 40 if c < 32000 then goto 30 / 50 l=l+1 / 60 print l / 70 goto 20` (the program
    that first failed) - at 32000 it would print once per ~12 minutes at 1 MHz anyway (about 850 instructions a pass
    of lines 30-40, measured on the emulator); with `c < 100` it printed `44#` and hung.
  - T1 `10 l=0 / 20 l=l+1 / 30 print l / 40 if l < 5 then goto 20`: at 6 MHz `1`, then `44#` and a hang (the first
    pass after GOTO); at 1 MHz `8193` ($2001) and back to the prompt. A dump after it: L at $0116 = `01 20`, so the
    value was STORED with $20 in its high byte. T2 `10 c=0 / 20 c=c+1 / 30 if c < 100 then goto 20 / 40 print c`
    at 1 MHz: `44#` and a hang, C at $0104 = `02 00`.
  - The same family as the LIST misprint (a $00 at $100F read as $48 by LIST in the first ROM 2026-10-07 build): a
    $00 in the token buffer ($10xx), read by ROM code (`INCR R3` / `LDAVR R3`), comes back with bits set; the same
    reads run from RAM (`tests/bench/diag/listread.asm`) and the monitor's loader (`zero_readback.py` over
    $1000-$10FF) read it right; the result changes with the clock but 1 MHz does not cure it.
  - **The machine had been running at 6 MHz** (found 2026-10-08; set back to 1 MHz that day). Everything in the tree
    assumes 1 MHz (CLAUDE.md, the tools' pacing, the microcode's timing review); bench runs, the 2026-10-04 microcode
    loads and the BASIC tests before 2026-10-08 ran at whatever clock was fitted then.
  - **Microcode ruled out (2026-10-08):** stage 1 loaded (boot check 0 mismatches), T1 at 1 MHz printed `1`, then
    `04#` and hung. **ROM code ruled out:** `ROM 2026-09-23` (the image BASIC worked with on 2026-09-23) burned back:
    on the machine `10 L=0` already hung at entry, while y1ucemu with the same two images runs T1 (1..5) and LIST
    right. So the machine changed since 2026-09-23.
  - **Suspect: the ROM chip, damaged when it was powered fitted reversed on 2026-10-07** (it passed minipro's pin
    test, two burns and read-backs, which test it alone). If its outputs are slow to switch off after the CPU fetches
    from it, a RAM read straight after a ROM fetch gets the ROM's byte at the same offset ORed in: the LIST misprint
    matches exactly (RAM $100F = $00 read as $48; ROM[$F00F] = $48), T1's $20 matches no single ROM byte (partial
    bits), and code run from RAM (`listread.asm`) and the loader's read-back are unaffected - the ROM was deselected
    long before. **Next: a fresh 28C64 (AT28C64B) burned with `firmware/rom/shipped/rom.bin`, then T1.** If T1
    counts 1..5, retire the old chip; if not, the memory card's ROM -CE/-OE path (IC6, IC18) or its data buffer.
    The old chip holds `ROM 2026-09-23` at the moment (burned for this test).
  - **The chip is ruled out too (2026-10-08, late):** a second AT28C64B burned with `rom.bin` (ROM 2026-10-07,
    verified, read back identical) fitted, reset, T1 at 1 MHz with microcode stage 1: now even entry fails -
    `10 l=0` and `20 l=l+1` answer SYNTAX ERROR, RUN prints `25#` and hangs. Worse than on 2026-10-07, when line
    entry and LIST worked. So an electrical fault on the machine, possibly from the reversed chip (VCC/GND across
    the ROM socket): **next, in this order**: measure VCC at the memory card (a chip's VCC-GND pins near the ROM
    socket and at the bus connector; 4.75-5.25 V) and feel for warm chips; run `tests/bench/run.py --port ...
    --only hello,brur,isa,arith` (programs from RAM: all passed 2026-10-08 07:40) to see whether the whole machine
    degraded or only reads by ROM code; then the memory card's ROM -CE/-OE path (IC6, IC18), its data buffer
    (74LS245) and the ROM socket's contacts.
  - **2026-10-09: the memory card's 74LS245 (IC5, the data-bus buffer) replaced** - no change: `10 l=0` and
    `20 l=l+1` SYNTAX ERROR at entry, RUN `25=TOKEN NOT SUPPORTED / EXE STMT` and a halt (its register dump:
    R2 = $0FF1, VIDMIR - the new CHAROUT's `LDA VIDMIR` changes R2 on the machine, as CLAUDE.md says; BASIC keeps
    nothing in R2 across a print, so not the cause).
  - **2026-10-09: the 2026-09-23 pair put back - it fails: a hardware fault, independent of the software.**
    ROM 2026-09-23 (MD5 d2d7b027..., the help has no V) and the microcode the EEPROM held on 2026-09-23 (the cache
    at 9000a22, staged as `/tmp/ucode-2026-09-23.hex` with the `!` sentinel; boot check 0 mismatches), clock 1 MHz:
    `10 L=0` hangs at entry. The same pair ran BASIC and passed the bench 14/14 on this machine on 2026-09-23, and
    y1ucemu runs T1-T3 right with it (and with the tree pair, ROM 2026-10-07 + stage 2). Next: VCC at the memory
    card (4.75-5.25 V, ripple), the ROM socket and the ROM -CE/-OE path (IC6, IC18), anything that ran hot when the
    chip was reversed; the 2026-09-23 bench images (`git show 9000a22:tests/bench/images/...`, no --xisa) run from
    RAM to see how far it reaches. Afterwards back to the tree pair: burn `rom.bin`, `ucode_send.py --all`.
  - **2026-10-09: VCC at the memory card reads good (meter). The 2026-09-23 bench images (`git show
    9000a22:tests/bench/images/...`, with the 2026-09-23 microcode) run from RAM: 10 of 14 pass; isa differs (its
    first 35 bytes right, a rerun printed 2 bytes, wrong in D2+D5 and D0+D1+D2+D6), switch prints garbled text
    (`heL?oworld###` for hello world: bit 5 lost in the `l`), sieve prints `000`, syscall's load got no answer.** So
    the fault is no longer limited to reads by ROM code: random data bits fail across programs, and it is getting
    worse. Not one data line (the bits vary). Next (hands-on, scope / bus tester): reseat every card and look at the
    backplane contacts; the clock from the function generator (level, edges, ringing); ripple and spikes on VCC
    under load; a chip on another card that loads or drives the data bus (the reversed ROM had the supply across
    the memory card's pins).
  - **2026-10-09, CPU out, bus tester in (flashed back to bus-driver blocks-1; its bus-monitor flash saved in
    `embedded/bus-tester/readback/`): `memory_status.py` reads $A0 everywhere** - the first read (boot remap, $F000)
    returns the ROM's first byte $A0, every later read the same $A0, RAM, ROM and empty blocks alike: nothing on the
    memory card drives the data bus after that, the bus keeps its last value. The just-fitted 74LS245 (IC5) is the
    first suspect (orientation, pins, seating), then the card's seating. Rerun `memory_status.py` after; then
    `memory_full_test.py` (its ROM phase compares against the tree's image, while the chip holds ROM 2026-09-23).
    Unchanged after reseating every chip and fitting a new 74HC245 as IC5. With the tester's outputs off the data
    bus reads $FF and the address bus $FFFF (pull-ups only), so no card drives either bus at idle.
  - **2026-10-09, only the bus tester and the memory card on the backplane: the memory card works.**
    `memory_status.py`: boot remap OK, low RAM OK, $8000-$CFFF RAM, $E000/$F000 ROM; the full 8K ROM read back
    through the tester is byte-identical to ROM 2026-09-23 (its "ROM mismatches" and "$F000 WRITABLE!" lines come
    from comparing against the tree's newer image: $F123 is $68 in 2026-09-23, $04 in the tree; `--rom FILE` now
    names the image on the chip).
  - **2026-10-10, the $A0 was the tester, not a card:** with register card 1 back in, $A0 everywhere again - because
    the tester left ADDR-REG-ID at 0, so R0 drove ADDR0..15 in every cycle with -VMA low (register.md 3.4), against
    the tester's address; R0 = $0000 after reset, FORCE-ROM never released, every read was ROM $F000 = $A0. The
    tester tools now select no register (`BusDriver.no_registers()`, ADDR-REG-ID = 8) and `memory_status.py` passes
    with the register card in. So the CPU-out tests have not found a faulty card yet; the RUN failures and the random
    bench errors are still open. Register card R0-R3: `tests/registers/register_test.py` ALL PASS (load/read 38
    patterns, byte lanes, counting across every carry, HL-SWAP, address drive, reset;
    `tests/registers/run-2026-10-10-card-R0-R3.log`). Both register cards in: `memory_status.py`, `tests/memory/tmp_test.py`
    and `register_test.py` on R0-R7 ALL PASS (`tests/registers/run-2026-10-10-two-cards.log`). ALU card in: the
    same three still pass (`run-2026-10-10-with-alu.log`) and `tests/alu/alu_test.py` ALL PASS (accumulator, invert,
    AND/OR/XOR/ZERO, add, add with carry, subtract with borrow, the seven shifts with the bit out in the carry, every
    BR-COND condition plain and inverted, reset; IN untested, the tester cannot drive it; `tests/alu/run-2026-10-10.log`).
    I/O card in: memory/TMP/registers still pass (`run-2026-10-10-with-io.log`); `tests/io/io_test.py` ALL PASS - the
    16550's registers through P0/P1, 38400 8N1, 44 bytes UART -> Mac console port, 21 bytes Mac -> UART, switches read
    $00 (driven), IN reads 0 through the ALU; LEDs/TIL311/OUT LED are visual checks (`tests/io/run-2026-10-10.log`).
    ALU still ALL PASS with the I/O card in (`tests/alu/run-2026-10-10-with-io.log`). Front panel, watched at the
    card with `tests/io/io_panel.py`: LEDs 0-7 each, TIL311 digits 0-F on both, the OUT LED on/off, the LCD (first
    time driven: two lines correct), switches $00/$01/$80/$55/$AA each read right, IN up = 1 / down = 0: all OK.
    Afterwards the bus tester was flashed back to bus-monitor (the saved 2026-10-09 image, verified) to listen
    while the machine runs. Next: sequencer and CPU back, tree ROM + stage 2 microcode, boot check, bench, T1-T3.
    2026-10-10, CPU back with the 2026-09-23 ROM + microcode: boots to the monitor, but the bench's hello hung at
    $3022 = $8B (`STZ`, an `--xisa` instruction the 2026-09-23 microcode does not have: an empty record, every strobe
    asserted, COUNT-FAULT stops the clock - the frozen bus word the bus-monitor showed; `bench-2026-10-10-1216.log`). So
    bench images built with `--xisa` cannot run on that microcode, and the 2026-10-09 bench on it proves nothing.
    Stage 2 (`test.hex`) loaded again the same day (boot check 0 mismatches); next: `rom.bin` burned, bench, T1-T3.
  - **2026-10-10, the tree's pair (ROM 2026-10-07 `rom.bin` on both chips + stage 2): POPR is broken on the
    machine.** Bench (`bench-2026-10-10-1352.log` at 3 ms/char lost the `3` of `G3000` at 1 MHz - use `--delay 6`;
    `bench-2026-10-10-1359.log` at 6 ms): hello, brur PASS; isa: the PUSHR/POPR word wrong ($99B3 for $ABCD); every
    compiled program prints wrong DECIMAL numbers (hex right): rt_divmod pops words. `tests/bench/diag/pushr.asm`
    (loaded with `monload.py --delay 6 --go 3000`) separates it: MVIW+showr7, MOVRR across cards and the two bytes
    PUSHR writes are all right; POPR of a correct stack (built with single-byte PUSHes) loads wrong, data-dependent
    values (`00AB 4A12 2700 C0FF 5A3C ...` for `ABCD 1234 0000 FFFF 5AA5 ...`); single-byte PUSH/POP right. Both
    emulators right; `y1ucemu -H` (new: an undriven bus keeps its last value) still right. POPR loads through
    -2-BYTE-OPERAND-SEL (the register number from the sequencer's operand register) and, for the high byte, -HL-SWAP.
    The same microcode passed the bench 15/15 on 2026-10-04 at 6 MHz; since then the clock went to 1 MHz (10-08) and
    the memory card's IC5 became a 74HC245 (10-09). **At 6 MHz (function generator in QG1, pin 8 clock / pin 7 GND)
    the probe is all right and the bench is 15/15** (`bench-2026-10-10-1602.log`): the fault needs the SLOW clock -
    a node held only by charge, which survives a 6 MHz step and drifts in a 1 MHz one. Suspect: sequencer JP1 (2x2,
    logic card <-> memory card) carrying SRC-ADDR/DEST-ADDR from the microcode RAM into the pipeline (`docs/cards/
    sequencer-logic.md` 3.6, "To verify: JP1 mated"). Unmated, those HC374 D inputs float; when they drift low the
    operand register drives ADDR-REG-ID against the pipeline (IC18A/IC11A), and POPR's stack read goes to another
    register's address. Next: check JP1, then the probe at 1 MHz.
  - **2026-10-10, FOUND by single-stepping (the bus tester as the clock: `bus-stepper`, `tools/busstep.py`,
    `tests/bench/diag/poprloop.asm`): while `-2-BYTE-OPERAND-SEL` is asserted nothing drives ADDR-REG-ID.** The
    sequencer logic card's IC18B (the pipeline's ADDR-REG-ID onto the bus) is enabled by `-ONE-OPERAND-SEL` = NOT
    `-2-BYTE-OPERAND-SEL` (`docs/cards/sequencer-logic.md` 3.6), and IC18A/IC11A (operand -> ADDR-REG-ID) are off
    (SRC-ADDR/DEST-ADDR idle). POPR is the only instruction that reads memory in those steps (10-14, 18-23): the
    stepped bus shows ADDR-REG-ID = 15, address $FFFF, data $05 (the ROM's last byte) where the microcode asks for
    SP and $0EFC/$0EFD. At 6 MHz the floating lines still hold 1 (SP) from the step before; at 1 MHz they drift to
    15 - the slow-clock POPR fault, the wrong decimal numbers and BASIC's RUN failures. JP1 was not it (reseated, no
    change; its SRC-ADDR/DEST-ADDR are still unverified). The emulators take ADDR-REG-ID from the word and miss it.
    **FIXED 2026-10-10 in the microcode** (record $08 reloaded, boot check 0 mismatches; the probe all right at
    1 MHz): POPR through TMP1 - read [SP] with the pipeline's ADDR-REG-ID into TMP1, then
    `-2-BYTE-OPERAND-SEL` with TMP1 as the source - and `y1ucemu` models the floating select (address $FFFF while
    `-2-BYTE-OPERAND-SEL`; `-O` the old model), so `make check` sees this class: with the old POPR it fails the isa
    test as the machine did, with the new one every check passes. **On the machine at 1 MHz: the bench 15/15**
    (`bench-2026-10-10-1912.log`; 13 of 15 failed before the fix). **BASIC at 1 MHz: T1 (prints 1..5), T2 (counts to
    100), T3 (nested loops, 1 2 3) all right through `tools/y1term.py --send ... --new --run` - the RUN fault of
    2026-10-08 is resolved.** Open from this hunt: the cards were never faulty (the "$A0 everywhere" was the tester
    leaving R0 on the address bus); the sequencer card revision note (IC18B enable); `baslook.bas` (the 32000-count
    loop) is in the tree root, untracked. Hardware alternative: IC18B's enable to GND
    (a cut and a jumper; conflicts with IC18A/IC11A if SRC-ADDR/DEST-ADDR ever assert).
    Next: the remaining cards
    back one at a time with `memory_status.py --rom /tmp/rom-2026-09-23.bin` after each.
    `memory_full_test.py` the same evening (`tests/memory/full-run-2026-10-09.log`): B address lines PASS, C and D
    every RAM byte $0000-$CFFF both patterns PASS (0 bad of 53248); A/F fail only against the tree's image, E fails
    because the video card is out. TMP0/TMP1 through the tester: PASS (38 patterns each, with the other register
    holding the complement; both latch on the leading edge of -TMP-REG-LDn, finding M3). With only these two cards
    the undriven data bus keeps the last value driven (seconds; nothing pulls it up), so a tester read of an address
    nothing answers returns the previous value - which is also how "$A0 everywhere" looks.
  - **The machine as left 2026-10-09:** clock 1 MHz; sequencer EEPROM = the 2026-09-23 microcode; both AT28C64B
    chips hold ROM 2026-09-23 (one fitted); IC5 new. To return to the tree's state: `rom.bin` on a chip,
    `python3 tools/ucode_send.py --all`.
  - T1-T3 for `y1term.py --send` (upper case for ROM 2026-09-23): T1 `10 l=0 / 20 l=l+1 / 30 print l / 40 if l < 5
    then goto 20`, T2 `10 c=0 / 20 c=c+1 / 30 if c < 100 then goto 20 / 40 print c`, T3 T1's outer loop around T2's
    inner (`70 if l < 3 then goto 20`).
- **A placement-dependent wrong value on the machine (2026-10-07/08, open).** With the first `ROM 2026-10-07` build
  (MD5 3a4ff079..., BASIC's new code early in the file, most routines 13-20 bytes later than in ROM 2026-09-23),
  `LIST` showed the line after an assignment line with $48 as its number's high byte (`10 L=0 / 20 C=0` -> 18452 =
  $4814); both emulators showed 20, the bytes in memory were right (`$100D: 25 14 00`), `zero_readback.py` found no
  bad $00 there, and `tests/bench/diag/listread.asm` - LIST's reads and BASIC's own `exe_itoa` called from RAM -
  read and printed 0014 / 20 every time. Moving the new code to the end of BASIC (only the line loop's
  `JSR parse_token_chk` and the 17-byte `get_inputline` slot differ before $EF3E) made it list 20. So some routine
  misbehaves on the hardware only at certain addresses (in the bad build `exe_itoa` started at $E5FF, the last byte
  of a page; `basic_list` $E6DC, `baslist37` $E966). To chase with the scope: the old image is
  `git show f04f13e:firmware/rom/shipped/rom.bin`; the 2026-09-29 review's one-step memory windows and the counter
  carry across a page are the first suspects.
- **Ports P2-P7 are probably free for another card** (noted 2026-09-24). The I/O card's 74LS138 (IC5, strapped to
  P0-P7) decodes all eight, but only P0 (control) and P1 (data) are used, each picked by a jumper on the IO-ADDR /
  DATA-ADDR headers; -IO-SEL2..7 go only to those headers and drive nothing. So a card decoding P2-P7 itself should not
  clash, as long as neither header's jumper selects that port. **To verify on the board** before relying on it: nothing
  else on the I/O card loads or drives -IO-SEL2..7, and the fitted jumpers are on P0/P1 (`docs/cards/io.md` 3.1).
- **Blank V3.2** (`hardware/bus/blank-card/eagle/v3.2`): derived 2026-09-20 from V3.1 with the Bus V3.2 names on C3–C6.
  Open it in Eagle/Fusion, re-save, use as the template for every new card.
- **Bus Tester V3.1** (`hardware/cards/bus-tester/eagle/v3.1`, 2020-07): latches drive the bus, soft bus-enable/reset,
  bypass caps; routed, CAM run, never ordered. Decide: build it, or keep the 2016 v1.1 for good.
  Whichever is built next: **bring the OUT-LED signal (IC6 GPA4) to a jumper/header pin, with a GND pin beside it**,
  so the card can clock the sequencer through its JP4 pin 2 (EXTERNAL-SINGLESTEP-CLK) without a wire soldered or clipped
  to the MCP23017 (2026-10-10: the `bus-stepper` sketch single-steps the machine this way and found the POPR fault).
  A second header pin on a spare MCP input for the sequencer's JP4 pin 3 (UCODE-COUNT-RESET) would let the stepper see
  where each instruction ends.
- **Video card v1.1** (`hardware/cards/video/kicad/v1.1`, the KiCad master since 2026-09-21; Fusion abandoned): DONE in the
  design — one 5 V rail (`+5V` folded into `VCC`, joining track added; proof 116/116). **Superseded 2026-10-22 by
  `kicad/v1.2`**: v1.1 plus every bench fix (RS on ADDR1, LPSTB to GND, R13/R14 4.7k on N$16 and N$5, E from the strobe
  with R1/C1 removed, IC28 74163, Q2 11.0592 MHz; proof 114/114, DRC 0 unconnected). **v1.2 NOT ORDERED**: order it, or
  fold it into the next revision (the graphics overlay / 8-dot plans below).
- **NEXT AT THE MACHINE: video card V1.0, Phase B (the CPU)** - `docs/procedures/VIDEO-BRINGUP.md`.
  - **Phase A done 2026-10-21, CPU out**: the latch's floating -OC (N$16) had the card driving every memory read in
    the machine - 4.7k pull-ups on N$16 (IC2 pin 1-20) and N$5 (IC27 pin 8-14), IC2 a 74LS373 (was a 74LS374); the
    MC6845 fitted (RS on A1, LPSTB to GND), `crtc_regs.py` ALL PASS (read through RDBLK: C1 is 1 uF, E ~12 ms);
    the remapped EPROM in IC25, SV4 1-2; `crtc_picture.py` put the test card on a TV-rate monitor. With a 9 MHz
    crystal 80 columns overflowed it (~72 visible) and 64 x 24 fitted; an **11.0592 MHz crystal** (fitted the same
    day) gives **80 x 24 with even margins, the standard**: R0..R9 = 116,80,94,9,31,6,24,27,0,7 (15.75 kHz /
    60.1 Hz) in `ROM 2026-10-21` (rom.bin MD5 68b584fc04885ac6abbfc26a96548696; a first 64 x 24 build, 8b5f778f, was
    never burned), `testcard.asm`, `crtc_picture.py`, `tools/vidsim.py`, the emulators' default geometry.
  - `ROM 2026-10-21` burned 2026-10-21 on the T48 (`minipro -p AT28C64B -u -P -w`, verify OK, read back and `cmp` identical).
    Until then `memory_status.py` and the card tests report the chip's ROM as differing from the tree's: pass the
    burned image with `--rom` (`firmware/rom/README.md`).
  - Phase B 2026-10-21 (reset in SS, then FREERUN: the reset fault under Verification): `vram.img` 0 errors; `crtcreg.img`
    failed (E never rose: C1 = 1 uF, finding 6.1) until IC1 pin 2 (N$4, the one-shot) bent out of the socket and wired to IC1 pin 14 (VCC), 2026-10-21: E = the strobe XOR (IC26/C), high for the whole of every memory read and write; then ALL OK. `testcard.img`: the card on
    the monitor; `vstress.img`: no snow; the ROM's `VI`, `VW`, `VM1`: text on screen and the console mirrored. **The video
    card works with the CPU.** Left: `estrobe.img` (a scope on E, optional now E is the strobe); `VIDAUTO EQU 1` (start the
    screen at reset: rebuild and burn) when wanted.
  - Phase B: `tests/video/asm/{vram,crtcreg,testcard,vstress,estrobe}.img` with `monload.py --delay 6 --go 3000`,
    then the ROM's `V` commands (`VI` gives the 80 x 24 picture) and `VM1`; `VIDAUTO EQU 1` last.
  - Away from the machine: `tools/vidsim.py run/render/timing` draws the card's picture (the emulators save its state
    with `Y1VIDSTATE`); `tests/video/asm/run.py` in `make check`.
- **Video card, the next revision (2026-10-10): a PS/2 keyboard interface, and the DB9 able to drive an old IBM XT
  monitor.** (2026-10-22: the PS/2 half is designed in **Video card V2.0** below; the IBM-monitor half - MDA timing,
  9-dot cells, sync polarity, intensity - stays open.) Which monitor decides the timing (to ask at the machine): **IBM 5151** (MDA, mono): 18.432 kHz / 50 Hz,
  720x350, 9-dot characters from a 16.257 MHz dot clock, DB9 1-2 GND, 6 intensity, 7 video, 8 +HSYNC, 9 -VSYNC; or **IBM
  5153** (CGA, colour): 15.7 kHz / 60 Hz, DB9 3-6 R G B I, 8 +HSYNC, 9 +VSYNC. The v1.0/v1.1 DB9 is MDA-like (7 video,
  8 HS, 9 VS, 1 GND) but its timing is TV rate (the ROM's table: 15.75 kHz from the 11.0592 MHz crystal, 80 x 24) and its
  character is 5 dots and a gap (IC28 a 74163 divides by 6) - it does not sync on a 5151. So: a crystal for the
  standard (16.257 MHz for MDA), a 9-dot character (counter /9, the chargen 8 bits wide plus the gap column), the
  sync polarities and an intensity output, with the review items 6.1-6.5 and the RS/7416 fixes folded in. Keyboard:
  PS/2 clock/data into a shift register or a small MCU, read on an I/O port behind the console vectors (OS-PLAN
  phase 4). `tools/vidsim.py timing` checks a register table against both monitors.
- **Video v1.3: 6 or 8 dots a character, chosen by one jumper (planned 2026-10-22; design `hardware/cards/video/kicad/v1.3`,
  model `tools/vidsim.py --card v1.3`; not ordered; the board: 4 layers, In1 GND / In2 VCC planes, routed from scratch by
  `build.sh` - proof 116/116, DRC 0 unconnected).** One 12 MHz crystal (Q2, SV4 1-2) gives both modes:
  | DOTS jumper | divider | character clock | screen | 6845 R0..R9 | dots across | EPROM time a character |
  |---|---|---|---|---|---|---|
  | open (high) | /6 | 2.0 MHz | **80 x 24** | 126, 80, 98, 10, 31, 6, 24, 27, 0, 7 | 480 | 500 ns |
  | fitted (low) | /8 | 1.5 MHz | **64 x 24** | 94, 64, 75, 8, 31, 6, 24, 27, 0, 7 (proven 2026-10-21) | 512 | 667 ns |
  Both 15.75 kHz / 60 Hz; the 80-column table is centred in the TV-rate monitor's measured visible window (about
  10.3-58.3 us after the sync starts: the text runs 14.5-54.5 us, margins 4.2 / 3.8 us).
  - **IC28 (74163) divides by 16 - P**, loading P on its carry: -CLR (pin 1) to VCC; data A (3) = GND, B (4) = DOTS,
    C (5) = GND, D (6) = VCC, so P = 8 (/8) or 10 (/6); -LOAD (9) = CHARCLOCK = NOT RCO, IC19/C with both inputs
    (pins 9, 10) on RCO (pin 15); ENT/ENP stay on N$73 (R10). CHARCLOCK is one dot low at count 15 in both modes, the
    pulse the 74LS166 load and IC22/IC23 get today. CRTCCLOCK stays QC (pin 12 -> IC17 21): /8 low 4 / high 4 dots,
    /6 low 2 / high 4 - 167 ns low at 12 MHz against the MC6845's minimum clock low width (see the v1.3 README for the
    margin and the faster-part option).
  - **DOTS**: a new 2-pin header (fitted = GND = 8 dots, open = 6 dots) with a 4.7k pull-up. It also drives **EPROM
    A10** (font select: the 8-dot font at $000, the 6-dot font at $400; A9, A11 stay GND) and **latch IC2 input 1D**
    (pin 3, was JP1 pin 1): `$D801` bit 0 = 1 for 6 dots, 0 for 8. The latch's LE (pin 11, was JP1 pin 13, floating)
    goes to VCC: transparent by design.
  - **IC24 (74LS166) A, B, C** (pins 2, 3, 4, were GND) to EPROM O0, O1, O2 (pins 9, 10, 11): all eight bits load;
    in 6-dot mode the next load comes after 6 shifts, so only O7..O2 are seen. Fonts (`firmware/video/chargen-v13.bin`,
    `vidsim.py chargen --card v1.3`): 8-dot cells a 7-dot glyph in D7..D1 (D0 = 0, the gap); 6-dot cells the 5-dot
    glyph in D7..D3, D2..D0 = 0. 8 scan lines a row in both modes (R9 = 7): taller characters need RA3 to the EPROM and
    break the overlay's 8-plane addressing, so not in v1.3.
  - **EPROM speed**: 500 ns a character in 6-dot mode against the MBM2732A's 450 ns: works, little slack; a faster part
    (a 2732A-25, or a 27C32/2764 at 250 ns with a socket adapter) removes the worry.
  - **The ROM: done 2026-10-22 (`ROM 2026-10-22`, built, NOT burned).** A card ID on the latch: v1.3 ties **3D (IC2
    pin 7) to GND** (JP1 pin 4 unconnected), so `$D801` bit 2 = 0 means V1.3; the V1.0-V1.2 card reads bit 2 = 1. At
    reset (and `V P`, `V I`) `vmode` reads the latch: bit 2 = 1 -> 80 x 24 with the 11.0592 MHz table as before;
    bit 2 = 0 -> bit 0 picks 80 x 24 (126/80/98/10) or 64 x 24 (94/64/75/8). `VCOLSV` ($0FF8) and `VSCRLN` ($0FF9)
    replace the `VCOLS` constant. Emulators: `Y1VID_LATCH` (default FF); `tests/video/emu.py` case `dots`.
  - **At the machine (Ken)**: fit a jumper on the video card's **JP1 pins 3-4** (VCC to 3D: bit 2 held at 1 - open, the
    input floats and read $FD/$3C once each on 2026-10-21), burn `ROM 2026-10-22` (MD5 ffee9163...), reset (SS, reset,
    FREERUN), then `VS` (ends `COLS 50`), `VI` and `VM1`: the screen as before.
- **Video: 64 columns of 8-dot characters (planned 2026-10-22, folded into v1.3 above as its 8-dot mode; the IC28 rework
  below is the same load-on-carry scheme with B tied low).** For the graphics overlay's arithmetic: with
  8 dots a cell the overlay is 512 x 192, every bit of a byte used, and a dot's byte and bit are shifts only - cell =
  (y >> 3) << 6 | x >> 3, mask = $80 >> (x & 7), plane = y & 7 (no divide by 6, no lookup table; with 64 columns the
  row multiply is a shift too). Its RA2..0:MA10..0 addressing still takes a 16K space (eight 2K planes, 1,536 bytes of
  each used: 12,288 bytes of picture).
  - **Crystal Q2 = 12 MHz** (SV4 1-2): 12 / 8 = 1.5 MHz, the same character clock as 9 MHz / 6, so the 6845 table is
    the 64 x 24 one proven on the monitor on 2026-10-21: **94, 64, 75, 8, 31, 6, 24, 27, 0, 7** (15.79 kHz, 60.3 Hz,
    even margins). Dot 83 ns (fastest video 6 MHz, easier on the monitor than today's 80 columns); the EPROM gets 667 ns
    a character. (80 columns of 8 dots would need 14.7456 MHz: 640 dots, 68 ns, 7.4 MHz video - harder on a TV-rate
    monitor.)
  - **IC28 (74163) to divide by 8: load 8, count 8..15, reload on the carry.** Decoding count N into the synchronous
    -CLR divides by N + 1 (today NAND(QA, QC) at 5: /6; QD alone at 8 would give /9), and /8 needs count 7 = QA.QB.QC,
    a 3-input NAND the card does not have - so use RCO instead. From the netlist (`kicad/v1.0-fusion-export-2026-09-18`):
    | pin | today | for /8 |
    |---|---|---|
    | IC28 1 -CLR | CHARCLOCK (IC19 8, IC22 9, IC23 9, IC24 15) | lift, to N$73 (+5 V through R10: IC28 7/10) |
    | IC28 6 D | GND | lift, to N$73 (bridge to pin 7) - the load value 1000 |
    | IC28 9 -LOAD | N$73 | lift, to CHARCLOCK (IC19 pin 8) |
    | IC28 15 RCO | unconnected | to IC19 pins 9 and 10 |
    | IC19 9 (NAND in) | IC28 14 QA | lift, to RCO |
    | IC19 10 (NAND in) | CRTCCLOCK (IC28 12, IC17 21) | lift, to RCO (CRTCCLOCK itself stays: IC28 12 -> IC17 21) |
    CHARCLOCK = NOT RCO: low for one dot at count 15, the same one-dot pulse the 74LS166 load and IC22/IC23 get today;
    QC (pin 12) is low 8-11, high 12-15: one 6845 clock a character, unchanged wiring.
  - **Stage 1 (the EPROM as burned)**: crystal + IC28 only - today's 5-dot glyphs in 8-dot cells (5 + 3 blank), and the
    ROM back to `VCOLS 64` with the table above (the 64 x 24 build of 2026-10-21, `0384c73`, never burned).
  - **Stage 2, a 7-dot font**: IC24 (74LS166) B and C to the EPROM's O1, O2 - lift IC24 pin 3 (B) and 4 (C) from GND,
    wire 3 -> IC25 pin 10 (O1), 4 -> IC25 pin 11 (O2); A (pin 2) stays grounded as the gap column, shifted out last
    (H = O7 leftmost, as now). A new 2732 with 7-dot glyphs in D7..D1, D0 = 0 (a font drawn for it, not a copied
    commercial one). Optional: VDATA6 to EPROM A9 for 128 characters (lower case) - one wire; the 2732 has the room.
  - **To do in the tools before the bench**: `tools/vidsim.py --dots 8` (it draws 5-dot glyphs in an 8-dot cell today;
    a 7-dot font and the overlay at 8 dots a byte are not modelled yet), `tests/video/asm` and the emulators' screen
    geometry follow `VCOLS`.
- **Video: a graphics overlay (proposed 2026-10-21, modelled in `tools/vidsim.py overlay`; designed 2026-10-22 as part of
  Video card V2.0 below - 8-dot mode only, 512 x 192, one time-shared 62256; the 6-dot/480-wide variant here is not built).** A 480 x 192
  bitmap over the 80 x 24 text, from the same 6845. Each character time the 6845's MA0..10 (cell) and RA0..2 (scan
  line) already address the text RAM and the EPROM; the overlay RAM is addressed **RA2..0:MA10..0** (14 bits, 16K: eight
  2K planes, plane n = scan line n of every cell) and read in step with the text, so the two cannot drift. A byte is one
  cell's 6 dots on one line (bits 7..2, bit 7 leftmost; bits 1..0 spare - an attribute such as "overlay wins" or
  intensity), latched on CHARCLOCK like IC23 so it meets the glyph's one-character pipeline delay, shifted by a second
  74LS166 on DOTCLOCK and ORed/XORed with the text dots before IC19/D (DE gating). **Each layer can be switched on
  and off**: TEXT-ON and GFX-ON, two more bits of the bank/control register, each ANDed with its dot stream before the
  combine (or the 74LS166's clock inhibit); with both off the screen is blank but sync runs. OR or XOR could be a third
  bit. 16K, not 11,520 bytes: 6-dot cells do
  not pack into 8-bit bytes with addresses the 6845 can make, so three 4K chips are not enough.
  - **Memory**: one 62256 (32K: two overlay pages, a page bit in the bank register) time-shared, or four IDT7134s (dual
    port, no arbitration, 4 x 48 pins). Time-sharing works because the character slot is 542 ns at 11.0592 MHz and a
    55-70 ns SRAM manages two accesses in it: the display read in one half, the CPU in the other; a YACC1 memory strobe
    lasts ~2 us at 1 MHz (about four slots), so the card does the CPU's read in a CPU slot and latches the byte onto
    DATA0..7 for the rest of the strobe, and holds a write in a latch until a CPU slot - no snow, no wait states. Address
    mux: 74LS157s (CPU address + bank against RA/MA).
  - **CPU access, no main memory lost**: a window in the card's own $D000 block plus a bank register. With the 6845
    still memory-mapped, its decode shrinks to $D800-$DBFF and the window is **$DC00-$DFFF (1K, 16 banks)**, the bank
    register one more address there (e.g. $D804, write-only, 74LS173/374). With the 6845 on I/O ports PA/PB (the v2
    plan), the window is the whole **$D800-$DFFF (2K: one bank = one scan-line plane)** and the bank register an I/O port.
  - **Software**: dot (x, y) is plane y & 7, cell (y >> 3) * 80 + x / 6, mask $80 >> (x mod 6); a 480-entry table
    (x -> column, mask; `vidsim.x_table`) replaces the divide by 6; with 1K banks the bank is (plane * 2048 + cell) >> 10.
  - Roughly 8-10 more chips: the SRAM, 2-3 74LS157, the slot logic (a few gates, a flip-flop on CHARCLOCK/DOTCLOCK), a
    CPU read latch (74LS374) and write latch, the bank/control register (bank, TEXT-ON, GFX-ON), a 74LS166, three gates. Goes with the PS/2 and IBM-monitor
    revision. Model: `python3 tools/vidsim.py overlay --tint --png ov.png` (the test card plus a drawing; `--overlay FILE`
    any 16K image, also in run/render; `--gmode or|xor`, `--layers text,gfx|text|gfx|none`); `tests/video/overlay_check.py` checks the addressing.
- **Video card V2.0 (designed 2026-10-22; `hardware/cards/video/kicad/v2.0`; re-reviewed and READY TO ORDER 2026-10-23, not ordered).** V1.3 (DOTS jumper, 12 MHz,
  both fonts in one EPROM, 4 layers) plus a graphics layer, two PS/2 ports and every register on I/O ports. Board 218 mm
  long (the sequencer logic V2.1l's length; X1 where every card has it), 4 layers: In1 GND plane, In2 VCC plane.
  - **Memory map**: text RAM **$D000-$D7FF** as before (IDT7134, the 6845 reads the other port); **graphics window
    $D800-$DFFF** (2K = one scan-line plane, chosen by the control register). The 6845's memory-mapped registers and the
    JP1 latch are gone (IC2, JP1, the upper-half decode, R13/R14). Board select unchanged (74S85 + SV3: the $D000 block).
  - **I/O ports** (74LS138 on IO-ADDR0..2, enabled by IO-ADDR3: PA..PF = Y2..Y7; two 74LS32 OR each select with
    -IO-RD/-IO-WR, so a strobe is low only during the bus strobe for this card's port, as on the CF card; P0-P9 untouched):
    | port | read (IN) | write (OUT) |
    |---|---|---|
    | **PA** | - | 6845 address register |
    | **PB** | 6845 data (R14-R17) | 6845 data |
    | **PC** | card status: bit 0 DOTS (1 = 6 dots), 1 VSYNC, 2 DE (display enable), 3 = 0, bits 7..4 = **0101 (card ID $5x)** | control: bits 0-2 PLANE (the CPU window's plane), 3 CPAGE (the CPU's 16K page), 4 DPAGE (the displayed page), 5 TEXT-OFF, 6 GFX-ON, 7 XOR (graphics XOR text instead of OR); 74LS273, cleared by -RESET: plane 0, page 0, text on, graphics off |
    | **PD** | PS/2 status: bit 0 FULL (a byte waits in PE), 1 SRC (0 keyboard, 1 mouse; valid with FULL), 2 BUSY (a command not yet taken), 7..3 = 0 | PS/2 command (below) |
    | **PE** | PS/2 data: the next byte; reading it clears FULL | - |
    | **PF** | spare | spare |
    6845 on PA/PB: -CS = Y2 AND Y3 (address only, so it is settled before E), RS = IO-ADDR0 (PA even, PB odd),
    R/-W = -IO-WR, **E = -IO-RD XOR -IO-WR** (IC26/C: high for the whole of every I/O strobe; no one-shot - the bench's
    V1.2 fix, now on I/O strobes). An old ROM (2026-10-22) on V2.0: the $D000 probe still finds the card, but its 6845
    writes land in graphics RAM at $D800/$D802 (harmless) and `$D801` reads RAM, so there is no picture until a ROM
    with the V2.0 driver: IN PC, (v AND $F0) = $50 -> V2.0, bit 0 -> 80 x 24 or 64 x 24, the 6845 through OUT PA/PB.
  - **Graphics**: 16K at **RA2..0:MA10..0** per page (eight 2K planes, plane n = scan line n of every cell; at 64
    columns 1,536 bytes of each used: **512 x 192**, 8 dots a byte, bit 7 leftmost). One **62256** (32K = two pages:
    CPAGE / DPAGE give double buffering), **time-shared per character slot** - the slot logic from the existing clocks:
    IC28 counts 8..15 in 8-dot mode (10..15 in 6-dot); its **QC** (CRTCCLOCK) is 0 for counts 8-11 = the **CPU half**
    and 1 for 12-15 = the **display half** (333 ns each at 12 MHz). QC is the select of four 74LS157s (CPU: ADDR0..10,
    PLANE0..2, CPAGE; display: MA0..10, RA0..2, DPAGE).
    | count | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
    |---|---|---|---|---|---|---|---|---|
    | QC / address | CPU | CPU | CPU | CPU | display | display | display | display |
    | -WE (write pending) | | low | low | | | | | |
    | latches | WRQ samples | | | | CPU read latch loads (QC rises) | | | display latch loads (CHARCLOCK rises at the end) |
    - **CPU read** of $D800-$DFFF: every QC rise loads a 74LS374 with the RAM byte at the CPU's address; it drives
      DATA0..7 while -MEM-RD and the window are selected (-OE = NAND(GSEL, MEMRD), IC19/A). The YACC1's read strobe
      is a whole microcode step (2 us at 1 MHz), so at least one complete CPU half falls inside it and the latch holds
      the right byte when the CPU samples - no wait states, no snow. Needs a strobe of at least ~1.4 us: graphics reads
      fail above a ~1.5 MHz CPU clock (the text RAM, dual-port, has no limit).
    - **CPU write**: a 74LS74 (WRQ) samples GWR (window AND -MEM-WR) on CHARCLOCK's rise (the start of the CPU half);
      WSLOT = WRQ AND NOT QC turns the RAM's -OE off and a 74LS244 on (DATA0..7 -> the RAM's data pins);
      -WE = NAND(WRQ, NOT QC, QA XOR QB, GWR) is low for counts 9-10 (167 ns; count 10 only, 83 ns, in 6-dot mode).
      Sampling at the start of the half means a write never starts mid-slot; GWR in the NAND ends it with the strobe.
      A 2 us strobe writes the same byte two or three times - harmless.
    - **Display**: the display half reads the byte for the current cell and scan line; a 74LS374 latches it on
      CHARCLOCK's rise (the same edge as the text code into IC23), a second 74LS166 loads it on the next CHARCLOCK
      (with IC24) and shifts it out bit 7 first: the text and graphics dots stay in step through the same
      one-character pipeline, with DE and the cursor delayed by IC22 as before.
    - **Combine**: TDG = text dot AND NOT TEXT-OFF; GDG = graphics dot AND GFX-ON AND **8-dot mode** (NOT DOTS: in
      6-dot mode the graphics layer never shows; the CPU can still fill it); dot = (TDG OR GDG) AND NOT(TDG AND GDG AND
      XOR) - OR, or XOR when bit 7 is set; video = NAND3(dot, NAND-term, delayed DE) into IC27/A as before.
  - **PS/2: two Mini-DIN-6 jacks** (keyboard J2, mouse J3; pin 1 data, 3 GND, 4 +5 V, 5 clock; 4.7k pull-ups on clock and
    data) on an **ATmega328P** (16 MHz crystal; keyboard clock on INT0/PD2, mouse clock on INT1/PD3, data on PD4/PD5;
    the PS/2 lines driven open-drain for host-to-device commands). Firmware `embedded/video-ps2/`: frames with parity
    and timeouts, set-2 scan codes -> ASCII (shift, caps, ctrl, extended keys, break codes), the mouse reset + enable
    reporting ($F4) and its 3-byte packets queued.
    - **Bus interface** (latches, so the 1 MHz CPU never waits for the MCU): an 8-bit local bus MD0..7 (PC0-PC5,
      PB0, PB1). **Data out**: the MCU puts a byte on MD and pulses LDDATA (PD6): a 74LS374 latches it (read by IN PE)
      and a 74LS74 sets FULL; reading PE clears FULL (CLR = -RD_PE AND -RESET); the MCU waits for FULL = 0 (PB2) before
      the next byte, and sets SRC (PB3) first. **Commands**: OUT PD latches DATA0..7 into a second 74LS374 on the
      strobe's rising edge and sets BUSY (74LS74); the MCU sees BUSY (PB5), reads the latch onto MD with -RDCMD (PD7,
      the latch's -OE), which also clears BUSY. **Status**: a 74LS244 puts FULL, SRC, BUSY on DATA0..2 for IN PD.
    - **Commands (OUT PD)**: $01 interrupts on, $02 off, $03 acknowledge (release -INT until the next byte), $04 mouse
      on (reset + enable reporting), $05 mouse off, $06 flush both queues, $07 keyboard reset, $10-$17 keyboard LEDs
      (bit 0 scroll, 1 num, 2 caps), $FF re-initialise.
    - **INT**: the MCU's INTREQ (PB4) through IC27/D (7416, open collector) to **jumper JP3 (INT-EN)** and the bus -INT
      (C13; the I/O card's RN2 is its pull-up). Jumper off: the card never touches -INT. Jumper on: -INT is low while
      interrupts are on (command $01) and a byte waits; reading PE (or $03) releases it; the handler reads PD first,
      so -INT can be shared with the I/O card.
    - **FTDI header J4** (GND, CTS, VCC not connected, TXD, RXD, DTR -> 100 nF -> RESET) for the bootloader and a debug
      console, as on the sequencer card; bus -RESET also resets the MCU (since the review: through two open-collector
      inverters, IC27/E,F, instead of a 1N4148).
  - **Chips added**: 74LS138, 2x 74LS32, 74LS273, 2x 74LS244 (status, PS/2 status), 4x 74LS157, 62256, 74LS244 (write
    buffer), 3x 74LS374 (CPU read, display, PS/2 data) + 1 (command), 74LS166, 2x 74LS74, 74LS20, 74LS04, 74LS08,
    74LS10, ATmega328P; IC1 (74ALS08) reused, IC2 removed. Model: `tools/vidsim.py --card v2.0`.
  - **Software to follow (not designed here)**: the ROM's driver over IN/OUT for V2.0 (probe IN PC), the keyboard behind
    the console vectors (CONST/CHARIN read PD/PE besides the UART), the emulators' V2.0 card model, Y1/OS `video`.
  - **Design review 2026-10-22: `hardware/DESIGN-REVIEW-video-v2.0.md` - HIGH 3, MED 9, LOW 11, INFO 6. Verdict: order
    after the HIGH fixes** (and fold the MED net changes into the same rebuild; the architecture needs no rework).
    Must fix before ordering: **V2-1** Optiboot drives PB5 = BUSY (IC53/B's output) for ~1.4 s after every reset - swap
    BUSY and SRC on the ATmega (IC49 pins 19 / 17) and the firmware's two pin numbers; **V2-2** redraw the Mini-DIN-6
    footprint from the jack bought. Before the PS/2 ports are used: **V2-3** (firmware) `ps2_send()` counts the host's
    own clock edge, so every command goes out a bit late - the mouse never starts. MED, all for the same rebuild: V2-4
    the 157s' select = QC OR RCO (spare IC32/C: IC42's hold race); V2-5 IC40 enabled by GWE (GD contention); V2-6 MRST
    through IC27/E,F (open collector) instead of D1; V2-7/V2-8 -INT = INTREQ AND FULL (spare IC19/D + IC48/C), pull-ups on
    LDDATA and RDCMD, LDDATA idle high; V2-9/V2-12 IC33, IC40, IC51, IC53 in 74HCT; V2-10 a 28-pin socket for an
    AT28C64B-15 instead of the 2732; V2-11 a faster 6845 grade for 80 x 24. Bench order in the review's last section.
  - **Review fixes applied (2026-10-22; firmware `7d3c054`, board `fc71ec4`)**: every HIGH and MED finding, and the
    trivial LOW ones (V2-16 decoupling and 47 uF bulk, V2-17 a PTC in the PS/2 +5 V, V2-18 in part, V2-20 the J4 legend,
    V2-21 `BOM.md`). The status of each finding is the table at the top of the review. The Mini-DIN is the **Same Sky
    MD-60SM** (date code after 2022-03-03), its footprint drawn from the data sheet. New parts: IC54 74HCT08, IC55
    74HCT244, RN3, R21-R27, F1; D1 gone; IC25 an AT28C64B-15 (`firmware/video/chargen-v20.bin`).
  - **Direct mode (2026-10-22)**: with **GFX-ON = 0** (the reset state) the CPU owns the graphics RAM - the muxes hold
    the CPU address (NMUX = NAND(QC OR RCO, GFX-ON)), -WE = NOT GWR (WRQ preset, the phase term forced), the RAM's -OE is
    the window read, reads pass through IC55 (74HCT244) instead of the slot latch IC41. A plain SRAM: checked against
    the microcode (`tests/video/v20_timing.py`: all 59 `-MEM-WR` held a step each side, one-step read window) - 38 ns of
    read margin at 6 MHz on a selected register (85 °C, since R2-5), ~6.8 MHz for the card alone; the machine's own limit
    (~6 MHz) comes first. GFX-ON = 1 is the
    slot mode as before, ~1.8 MHz. Rule: the instruction that writes PC does not touch the window.
  - **Text-only build (2026-10-22)**: the graphics chips (IC35-IC45, IC55, RN3, their capacitors) left off, R25 / R26
    (1k pull-downs on GDOT and WRQ) fitted only then; **IN PC bit 3 = TEXT-ONLY** (IC44/B's Q low when fitted, R27
    pull-up when not). The recommended first build; `BOM.md` marks it.
  - **Re-review 2026-10-23: `hardware/DESIGN-REVIEW-video-v2.0-r2.md` - HIGH 0, MED 1, LOW 9, INFO 6. Verdict: order
    after R2-1.** The slot logic, direct mode and the text-only build are right (IC42's hold >= 9 ns at the corners; GD
    hand-over a dot apart; direct-mode writes meet the 62256 at 1 and 6 MHz, re-derived from `test.hex`). **R2-1, R2-2,
    R2-3 and R2-14 done 2026-10-23 (`560977b`)**: the MD-60SM side-leg slots 1.2 x 2.6 mm, IC55 0.6 mm up, IC27/E's input
    through IC54/C (RESETB), 16 more nets in `verify`'s KEY; routed anew (order 6, 328 vias), proof MATCH, DRC clean -
    **the order gate is lifted**. **The rest applied 2026-10-23** (the status table at the top of the r2 review): R2-7
    the BOM (IC17 HD68B45SP / MC68B45P, the B grade; C16 47 uF 16 V), R2-8 the README (IN PC AND $F9; the -55 grade's
    reasons), R2-9 the silkscreen (every text placed clear by `gen_v20.py`), a socket-outline check over the whole board
    in `gen_v20.py place` (R2-2), R2-5 the counted-register windows in `tests/video/v20_timing.py` (`f3cd989`), R2-10
    the firmware's reply filter (`a139dc4`); R2-6 / R2-12 / R2-15 / R2-16 are bench steps in the README's order. Board
    rebuilt and verified (`ed7c060`: order 5, 0 unrouted, 285 vias, proof MATCH, DRC clean, silk overlaps 0). **Ready to order** - nothing blocks it; before ordering, if a jack is
    at hand, measure its leg span (14.28 mm). What to upload and buy: the card's README, "Ordering".
  - **Open - the ROM's V2.0 driver** and the emulators' V2.0 card model. The driver's requirements (the card's README,
    "The software rules for the window"): the card ID check **(IN PC AND $F0) = $50**, the build and DOTS from **(IN PC
    AND $F9)** = $58 / $59 text-only, $50 / $51 with graphics (bits 1 and 2 are VSYNC and DE, live); GFX-ON left 0 on a
    text-only card; **refuse GFX-ON = 1 in 6-dot mode** (IN PC bit 0 = 1, R2-4); the 6845 through OUT PA/PB; graphics
    drawn in direct mode (GFX-ON = 0); the **6 MHz read rules** - no code in the window ever, no stack and no BRVR vector
    table in it at 6 MHz (R2-5), the window only in direct mode above ~1.8 MHz; the **mode switch** - the instruction
    that writes PC does not touch the window, GFX-ON switched in vertical blanking (IN PC bit 1, R2-11); the keyboard on
    PD/PE behind the console vectors, **IN PE only after IN PD showed FULL** (R2-10).
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
- **Memory card**: the unconnected jumper wire on IC7 pin 4 — purpose not remembered (2026-09-20); trace it on the board or remove it.

## Firmware — written, not burned / loaded
- **ROM 2026-10-07 (burned 2026-10-07): the video unit + BASIC's input fix** — `firmware/rom/shipped/rom.bin` (MD5 122f1a93..., the 2026-10-08 layout; BASIC: backspace/DEL, lower case, SYNTAX ERROR instead of an endless loop, `firmware/basic/README.md`; the monitor as 2026-09-25 with the new banner date): the $D000 probe at
  reset, the screen driver, CHAROUT mirroring (`VIDMIR` $0FF1, off at reset), the `V` command, the video entry at $FFBC
  (`docs/programming/MONITOR.md` section 11). Burned 2026-10-07 (`firmware/rom/README.md`; BASIC's fix checked on the
  machine, bench hello/brur/isa/arith PASS). Still to check: the banner's `VIDEO CARD FOUND` line at power-up, then the
  bring-up table in `docs/cards/video.md` section 8.
- **Video auto-start: `VIDAUTO EQU 1`** in `firmware/monitor/monitor.asm` once the card is debugged (6845 fitted with
  the RS-to-A1 fix, E one-shot and 7416 pull-ups sorted, a picture from `V I`): reset then programs the CRTC, clears the
  screen and turns mirroring on. Rebuild, `tools/verify_firmware.py`, burn.
- **Sequencer microcode: five changes waiting for one EEPROM** (`firmware/microcode/ucode-generator2/test.hex`; `cache` =
  what the EEPROM holds, the 2026-09-23 image): (a) `LDZ`/`STZ`/`ADDIW`/`SHL16` (2026-09-24, 32 new records $80-$8F,
  $C0-$CF), (b) the undefined opcodes $A5, $AE, $F8-$FA get HALT's record (2026-09-29, H-4), (c) the three-step fetch
  prologue (2026-09-29, `docs/system/MICROCODE.md` 5.6: every record changes, instructions 2-3 steps shorter), (d) M-1:
  every step that counts a register is written without `-MEM-RD` (2026-09-29, the same section; 116 steps, one bit
  each), (e) 152 idle steps removed (2026-09-29, 5.7 there). Load in two stages so a failure points at its change:
  **Baseline 2026-10-04, on the EEPROM's 2026-09-23 image** (`ROM 2026-09-23` in the chip): hello, brur and the 11
  compiled C programs 13/13 PASS (`tests/bench/logs/bench-2026-10-04-1120.log`); `isa` runs the new opcodes, which
  that image holds as all-zero words, and hangs the machine after `GO ADDRESS:3000` (every later load then gets no
  answer: `bench-2026-10-04-1115.log`). **Stage 1 loaded 2026-10-04** (`ucode_send.py --all --hex build/p6/test.hex`;
  `--boot-check` against that image: RAM == EEPROM, 320 dump lines, 0 mismatches): **14/15 on the machine**
  (`bench-2026-10-04-1518.log`) - `isa` PASS (the four instructions byte by byte), every C program PASS; **`xisa`
  differs in one line: `deep 925`, both emulators `deep 945`**. 945 = 315 + 630; 925 is what comes out if `a` stays 1
  down the 20 levels of `deep(n, a, b, c, d, e)` (the recursive function with a 12-byte frame: rt_fsave/rt_frest,
  R6 reloaded), so one frame word is not saved, restored or passed on the machine. **Isolated the same day: not the
  code, an address-dependent $00 read-back - review M-1.** `tests/bench/diag/deep.c`, the same recursion with every
  level printed, gives 945 on the machine (its frame at $360E); `xisa` gives 925 every time (3 runs, logs
  `bench-2026-10-04-1555/1556/1557`), also with `deep` run first in `main` (so no earlier test's state). A variant
  of `xisa` would not even load: the monitor's loader refused (read back wrong) the record at $3EF0. Byte by byte:
  only the value $00 fails there; $3000-$4FFF holds two full complementary patterns; and
  `tests/bench/diag/zero_readback.py` finds $00 refused at 13 of 512 addresses in $3E00-$3FFF (3E7C 3EB9 3EBC 3EBD
  3EE9 3EF1 3EF9 3EFA 3EFD 3FE9 3FF1 3FF9 3FFD - low bytes heavy in 1 bits). That is M-1: a register count with
  `-MEM-RD` still on puts the register card's LS245s ($FFFF) on the data bus against the memory card's, and $00
  loses that fight at some addresses. `xisa`'s page ($3F00) and frame ($409E) sit in that neighbourhood. Stage 1
  keeps the six-step prologue (M-1 in every fetch); **stage 2 removes M-1**, so it is the fix: after stage 2,
  `zero_readback.py` must find no address and `xisa` must pass.
  **Stage 2 loaded 2026-10-04** (`ucode_send.py --all`, the tree's `test.hex`; `--boot-check`: RAM == EEPROM, 320
  dump lines, 0 mismatches): `zero_readback.py` finds $00 refused at **0 of 512** addresses in $3E00-$3FFF (13 with
  stage 1), and **`tests/bench` passes 15/15** with `isa` and `xisa` (`bench-2026-10-04-1719.log`). M-1 is gone on
  the machine. Left from stage 2's list: the monitor and BASIC by hand, Y1/OS from CF (needs the CF hardware: memory
  card v2.0) and a kermit transfer (`/BIN/KERMIT` is a Y1/OS command: it waits for the CF hardware too; its timeouts
  were recalibrated for the three-step prologue). `--xisa` became y1cc's default the same day (below, "C compiler").
  1. `make -C firmware/microcode/ucode-generator2 prologue6`, then
     `python3 tools/ucode_send.py --all --hex firmware/microcode/ucode-generator2/build/p6/test.hex` (at the machine: press START), reset,
     `python3 tests/bench/run.py --port /dev/cu.usbserial-AB0MVHSQ`: (a) + (b) with the old prologue. `isa` checks the
     four instructions byte by byte (the machine must print exactly `expected/isa.uc.out`), `xisa` is compiled C using
     them (y1cc `--xisa`: the page register R6, a recursive frame in the page, ADDIW, SHL16, R6 reloaded after the ROM's
     charout).
  2. `python3 tools/ucode_send.py --all` (the tree's image, + (c), (d) and (e)), START, reset, the bench again: every test must print
     the same; then the monitor, BASIC, Y1/OS from CF and a kermit transfer (its timeouts were recalibrated for (c):
     `os/kermit_io.asm` PPS 6528 - with the old microcode they are 25% long, harmless). If stage 2 fails where stage 1
     passed, stage 1's image is the way back.
  `xisa` passes since 2026-10-04, and `--xisa` is y1cc's default since that day (below, "C compiler").
- **Monitor + BASIC 8afde21** (2021-09, `firmware/*/candidates/2021-09-8afde21`): `charavail` BIOS vector ($FFEC),
  BASIC ON/OFF statements, break into a running program. Needs a hardware test, then burn and update `rom/shipped`.
- **monnew-2025** (`firmware/monitor/monnew-2025`): small D/M/B monitor; assembled, never run on the machine.
- `firmware/abi/` — the BIOS/port/variable map still has to be written from the two .asm headers.

## Design review 2026-09-21 (reports: `hardware/DESIGN-REVIEW.md`, `hardware/DESIGN-REVIEW-NOTES-datapath.md`,
`hardware/DESIGN-REVIEW-NOTES-control-io.md`, `docs/isa/MICROCODE-REVIEW.md`, `docs/isa/MICROCODE-REVIEW-NOTES.md`)
Items below were traced to nets/pins or to test.hex and spot-checked; the reports give the evidence and a bench check each.
- (done 2026-09-29 in the tree, NOT YET LOADED: **HIGH, microcode: undefined opcodes were all-zero words** ($80-$8F, $A5, $AD,
  $AE, $C0-$CF, $F8-$FA; BRUR and the four xisa instructions filled all but five). An all-zero word asserts every active-low
  line (-MEM-RD and -MEM-WR together, every register strobe) for 61 steps. The generator now gives $A5, $AE, $F8-$FA the HALT
  record (`docs/system/MICROCODE.md` 5.4, `tests/ucemu/undefined.py`); it reaches the EEPROM with the next
  `tools/ucode_send.py --all`, the same reload as the xisa instructions.)
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
- (done 2026-10-21/22: video 6845 E clock - the C1/R1 one-shot never let E rise at 1 MHz; the bench card takes E from the
  strobe (IC1 pin 2 to VCC) and `kicad/v1.2` drops the one-shot.)
- **MED**: 28C64 -WE is raw -MEM-WR (any store during FORCE-ROM writes the EEPROM; the monitor is safe only because its first
  instruction jumps above $8000; **memory v2.0 has the write-protect jumper JP3, 2026-09-29**); reset does not reload the pipeline (stale word on the bus during reset, with FORCE-ROM active);
  no power-on reset anywhere (FORCE-ROM, counters, carry undefined until the button); register card IC34 is a CD4077 driven by LS
  levels; count strobe = OR(-Rx-RDSEL, -REG-UP) counts a deselected register on a REG-RD-ID change; the register card drives $FFFF
  onto DATA0-15 on every increment step, overlapping -MEM-RD (327 steps); one-step memory windows before leading-edge latches
  (LDTI, LDIVR, LDT, BRANCH-LD, INT-LD) are the first to fail at a faster clock; JP2 on the logic card would hold the sequencer
  card in reset; video character clock is a ~50 ns runt; TMP registers latch on the leading edge (microcode must present the
  source a step early - it does).
- **LOW / speed**: (done 2026-09-29 in the generator, NOT YET LOADED: the fetch prologue is 3 steps, `docs/system/MICROCODE.md`
  5.6; compiled code ~18% fewer clocks on the emulator.) (Also done, the same day: M-1 in the 116 operand-fetch
  increment steps, section 5.6 there, and 152 of the 259 idle steps, section 5.7, ~3% more.) Still open: hold steps
  that are not idle (5.7 "Not done"), `-IO-ADDR-LD` (L-2); the rest of the ~30% tabulated per opcode in the microcode notes; emulator mismatches listed there (BRVR, JSRUR byte order, carry on SUB/shifts, R0-load suppression).
- Timing-diagram model (`tools/ucode_wavedrom.py`) corrections from the review: IR/operand/branch/TMP/ACC latch on the LEADING
  edge of their strobe; one step = two clocks; steps 0-2 run with the previous opcode in the IR; -REG-RD-LO/HI are byte lanes.
  To fold into the generator when the diagrams are next regenerated.

## Software
- **The debugger with a live video screen (`software/y1dbg`, 2026-10-11), modelled on the ELF repository's System-5
  emulator (`software/s5emu`: `debugger.py`, `shell.py`, `tui.py`, `web.py`).**
  - **Phase 1 - done 2026-10-11:** `y1ucemu -D PORT` (a line/JSON debug server on 127.0.0.1; run speed without `-D`
    unchanged) and the Python front end: the command language (`shell.py`), the curses UI with the screen pane drawn
    from the display RAM with the 6845's geometry, registers, code, the UART console; `tests/y1dbg/run.py` in `make
    check`. `software/y1dbg/README.md`.
  - **Phase 2, the browser debugger - done 2026-10-11:** `python3 software/y1dbg --ui web` (http://127.0.0.1:8803/,
    `--port N`): `web.py` + `web/index.html`, a port of s5emu's, every command through the same `Shell.exec`. The
    screen is drawn dot by dot on a canvas with `tools/vidsim.py`'s font served by the page's server (or a 2732 dump
    with `--chargen`), 5 dots a character, R9+1 lines a row, inverse, the cursor on R10/R11's lines with R10's blink;
    green/amber/white phosphor; typing on the screen goes to the UART. Panels: status, registers, code, breakpoints and
    watches, memory, the UART console, the command line. Shared with the terminal UI: `Shell.snapshot()` (the code
    read in one block: the TUI's refresh during a run went from ~80 ms to ~6 ms) and `debugger.geometry()`. No protocol
    change: a page state is 7 round trips, ~7 ms during a run, so a combined "frame" reply was not needed.
    `tests/y1dbg/run.py` cases `web` and `webstop`. Not done: `vidsim.py --raster` (the whole frame with the sync
    intervals) on the page; `waitfor`/`sleep` typed on the page block its polling until they end.
  - **Phase 3, the gate-level video card - done 2026-10-11:** `y1ucemu -G REV` (`--video-rev REV`; y1dbg
    `--video-rev REV`). `software/gatemodel` reads the V1.0 netlist, the board's own connections
    (`netlist-compare.txt`), the SV3 jumper and the reworks as netlist edits (the +5V wire, RS to A1, each citing its
    document), traces the bus path (IC18, IC20, IC1, IC19, IC27, IC26, R1/C1; devices IC15's bus port, IC17's
    register interface, the IC2 latch; IC21-IC25, IC28 checked off it) and generates `software/ucemu/videogate.h`:
    the decode for all 1024 combinations of the ten bus inputs it reaches, looked up every step. Revisions `v1.0` (as
    fitted), `v1.0-no6845` (the machine today), `v1.0-no-rs`, `v1.0-no-5v` (2026-09-18), `v1.0-drawn`, `v1.0-a0fix`.
    Bus events on the card's side (contention, undriven reads, floating latch inputs, undefined selects), once per
    (event, opcode, step). The open question was decided by measurement: generated C (a table lookup per step; 15.2 s
    with `-G` on the 300-million-step BASIC loop) against a C gate evaluator (about 51 s) and the Python model over
    the debug connection (hours); without `-G` 13.68 s before, 13.63 s after. `tests/video/gate.py` (in `make
    check`): the card as fitted equals the behavioural model byte for byte on the monitor's video unit, Y1/OS's
    `video` and the bring-up programs, 0 bus events (`crtcreg`'s latch reads aside); without the RS fix `crtcreg`
    fails as predicted; without the wire the write-through fault returns. `docs/cards/video.md` section 9. Found: the
    JP1 latch drives DATA0..7 on -VMA alone (no strobe term), so an odd $D8xx-$DFxx address in the selected register
    is a fight in any step where something else drives the data bus (finding 6.4 is wider than writes). Not done:
    timing (the E one-shot's width and C1's recharge, finding 6.1; a strobe over several steps gives E in each), the
    v1.1 netlist (when it is built: one more revision entry), the instruction-level emulator (keeps the behavioural
    card), JP1 settings (none fitted, so none modelled), the rest of "electrical checks on every bus" (below; this is
    the video card's side only).
  - **Later:** the same `-D` mode in the instruction-level emulator (`software/emulator/main.c`, a migrated file: a
    dated `tools/patched_files.txt` note), so the debugger runs on either; `y1dbg --emu` already takes another
    executable.
- **BASIC: a break key (2026-10-10, not started).** The ROM's BASIC has no way to stop a running program short of
  reset (found running `baslook.bas`, a 32000-count loop, at 1 MHz). Plan: at the start of every statement check the
  UART for a waiting character through the ROM's no-wait vectors (`CONST`/`UARTINNE`); on Ctrl-C (and/or Esc - to
  decide) print `BREAK` and return to the `>>` prompt with the program kept, any other key ignored. Cost: one status
  read per statement. Precedent: `firmware/basic/candidates/2021-09-8afde21/` (break-in via `charavail`, never burned).
  Needs a ROM burn: emulators and `make check` first.
- **BASIC and monitor: unchecked areas and hazards (found 2026-10-08, `docs/programming/MEMORY-MAP.md` section 2a; none
  fixed yet).** Each is a change to `basic.asm` or `monitor.asm` (migrated: a `tools/patched_files.txt` note), a ROM
  build, `tools/verify_firmware.py`, a burn. Keep the 2026-10-08 layout rule: new BASIC code goes after `CRLF` at
  the end, so the old routines keep their addresses (the address-dependent fault, below).
  - **R2 in `exe_set_variable` / `exe_get_variable`**: they point R2 at the variable. R2 is the microcode's operand
    address register (CLAUDE.md); it holds only because no LDA/STA/LDR/STR sits in between. Move the pointer to
    another register (R7 is free there) - a likely source of machine-only faults.
  - **Division by zero hangs** (`parse_div16` / `parse_mod16` loop until the remainder is below the divisor): test
    for 0 first and stop with an error message.
  - **FOR and GOSUB stacks unchecked**: past 10 nested FOR (6 bytes a level from $0282, pointer R4) the FOR stack
    runs into the GOSUB stack; past 30 GOSUB (2 bytes from $02C2, R5) into the input line at $0300. Check R4 below
    $02C0 and R5 below $0300 before a push; the words at $0280 / $02C0 are unused.
  - **Program buffer full** ($1000-$1FFF): adding a line moves the whole 4K and drops the end, the end token
    included, without a message; check the room first (and move only the program's length).
  - **Line inputs unbounded**: BASIC's `get_inputline` ($0300, 256 bytes) and the monitor's `P` input
    (`line_buffer` $0F80, 112 bytes: past it the video variables, then the BASIC program at $1000). Stop storing at
    the limit (keep reading until LF).
  - **The `C` command copies code**: `basic_copy` takes $0400 bytes from `BASIC_TEST` ($EF00), whose test program is
    commented out while BASIC's code reaches $EFDD; restore a test program elsewhere or drop the command.
  - **ARGBUF / `line_buffer` overlap** at $0F80-$0FBF (ARGBUF 128 bytes since 2026-09-23): not in use together
    today; correct `monitor.asm`'s "64 bytes" comment, or move `line_buffer`.
- **BASIC `OUTP port,value` / `INP port,var`** (open since 2026-09-23): both keywords tokenise, but `exe_outp_stmt` and
  `exe_inp_stmt` in `firmware/basic/basic.asm` only eat the keyword - no port access, so BASIC cannot drive the LEDs or read
  the switches (POKE cannot: they are I/O ports, P0 select + P1 data). The port is in the opcode (`OUTA Pn` $60+n, `INP Pn`
  $90+n), so a run-time port needs `OUTA/INP Pn` + `RET` built in RAM and called, or a 16-entry jump table. `INP` like
  `PEEK addr,var` (no functions in expressions). ~230 bytes free in the BASIC half of the ROM. Test on both emulators
  (ucemu `-L` shows LED writes, `-i`/`-I` the switches), patched_files entry for basic.asm, then burn - ideally together
  with the next ROM burn. Example: `OUTP 0,1` (select switches/LEDs), `OUTP 1,170` (LEDs = $AA), `INP 1,S`.
- Every C tool now has a plain Makefile (2026-09-20); the NetBeans projects are kept but no longer needed to build. The three
  tools still carry the old tree's relative include paths, satisfied by `tools/layout_links.py` symlinks; fixing the includes
  would let the links go.
- **Test-vector generator uses the 2016 signal names** (`tests/bus-tester-scripts/Gen Test Vectors/`): it emits the
  2016 register-card codes (REG-FUNC-LD, REG-BRD-LD-ID, WDATA/RDATAL) which are not in the 2020 bus table, where the card
  select became REG-LD-ID2..3 / ADDR-REG-ID0..3; the `fix` converter only maps BUS-WR. Rewrite it against the current
  signal table before generating vectors for the 2020 Index Register cards.
- **Replace the Processing command sender with a Python host** (2026-09-20). `embedded/command-sender/command_sender_8`
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
- **OPEN 2026-10-22: `tests/kermit/run.py` on the microcode emulator fails intermittently** at "send them back
  (kermit -s *)" (the detail is only the `/K>` prompt: the Y1 side returned with nothing sent). Seen in `make check` and
  reproduced on a clean checkout of 53f6493 (2 of 3 runs failed; the instruction-level emulator always passes), so it
  is older than ROM 2026-10-22 - probably timing between the host kermit's wall-clock waits and the slow microcode
  emulator. To look into: `--time` / the host side's timeouts in that session, or a race in /BIN/KERMIT's send start.
- **OPEN 2026-10-21: reset with the 1 MHz clock running does not boot.** The CPU never reaches the banner: the first
  fetch reads RAM ($0000 = EB 81 37 instead of the ROM's A0 F0 03), the boot remap (memory card IC12/A, FORCE-ROM) already
  cleared, and the PC then walks $A7xx-$DFxx with no I/O. Reset with the clock stopped boots every time: SS/WAIT on SS
  (SS-SEL on EXT, nothing on JP4 pin 2 moving), reset, then FREERUN - banner, `VIDEO CARD FOUND`, `>` (twice, once
  after 400 stepped edges, once with none). Stepped from reset the CPU follows the ROM exactly (BR $F003, MVIW R1, the
  UART OUTIs). Everything else checked the same day: microcode `--boot-check` 0 mismatches, `ROM 2026-10-21` byte-
  identical on the chip, every card through the bus tester (`tests/cards/run-2026-10-21-1304.log`). Suspects: the
  sequencer logic card's reset release (the ~30-45 ns `N$32` pulse into `BUS-LATCH-CLK`, `docs/cards/sequencer-logic.md`
  3.2) racing the running counter so a stale pipeline word (VMA asserted, no register selected: the address floats to
  $FFFF, seen while -RESET was held) clears FORCE-ROM; or reset-switch bounce. Next: a scope on -RESET, BUS-LATCH-CLK,
  -VMA, ADDR15 and IC12/A Q, triggered on -RESET rising. **Workaround: reset in SS, then FREERUN.** It did boot with
  a running clock on 2026-10-10, so check what differs (the SS-SEL jumper, the JP4 clip lead, the front-panel latch).
  - **Tests to run next (agreed 2026-10-21), in order, each a reset in FREERUN with the console watched:**
    1. **1 MHz, the 2026-10-10 setup**: SS-SEL on INT, the clip lead off JP4, the bus tester pulled (or on bus-monitor).
       Boots -> the stepping setup was the cause (the clip into the clock gating, or the tester's 100k pull-ups).
    2. If not, **the 6 MHz oscillator**, same setup. Boots at 6 but not at 1 -> a timing race: while -RESET is held the
       pipeline keeps its last word (reset does not clear it), possibly with -2-BYTE-OPERAND-SEL set, which disables
       ADDR-REG-ID (the POPR mechanism) so no one drives the address bus (A=$FFFF, ADR=14 seen during reset). If the
       release pulse fails to load START, that word lasts until the first counter clock - ~1 us at 1 MHz, ~170 ns at
       6 MHz - and a floating ADDR15 pulled up (the tester's 100k on every line) reaches threshold only in the longer
       window, with -VMA asserted: FORCE-ROM cleared. Fails at both -> the release pulse itself: the scope.
    The microcode is ruled out: the image (boot check 0 mismatches, `test.hex` unchanged since ad0cef3) reset fine at
    speed on 2026-10-10 after the POPR load, and 1 MHz resets worked for every bench run 2026-09-23..10-09.
- (done 2026-09-21: both ATmegas now run tree builds, verified by reading the flash back; the previous binaries are in
  `embedded/*/readback/`)
- (done 2026-09-20: `tools/verify_embedded.py`, 12 sketches compile against the vendored libraries)
- (done 2026-09-24: the tree's `eagle/v1.3` board turned out NOT to be the ordered one (now `eagle/deprecated/v1.3-do-not-use/`);
  the Fusion 360 export of the built card is `hardware/cards/memory/eagle/v1.3/` (filed first as `v1.3-fusion-export-2026-09-24`),
  proven hole for hole and track for track against the 2025 gerbers (JLCPCB order 2000765A) by `tools/verify_fab_vs_brd.py`; it
  adds IC15, the 74245 enable from the chip selects.)
- (answered 2026-09-20: jumper boards not fitted/obsolete, EEPROM adaptor fitted, two register cards, RN2 = 1k; bus tester
  firmware settled 2026-09-21 by reading the flash out; sequencer likewise = Sequencer3) — no **(confirm)** marks left.
- **Microcode diagnostic suite (designed 2026-10-10, not built; on hold until the standard suite has run with the
  CPU back in).** A control store that is not the ISA but a chain of test records, run at full clock speed:
  - Mechanism: no literal field and no microcode branch, so constants are built with the ALU (ZERO, INVA, shifts, OR
    through a scratch register) and registers (cleared by -RESET, counted); the "branch" is R0 preset to the FAIL record
    number, a compare, BR-TEST letting a register load into R0 only when the condition holds (R0 = next test), then
    LD-INS-REG from R0.lo with UCODE-COUNT-RESET (step 0 of that record). A record that resets the step counter without
    LD-INS-REG repeats itself (loops). FAIL record: failing test number on the TIL311s, OUT LED on, held. End record:
    pass counter on the LEDs, back to test 1 (soak).
  - Tests: 0 constants; 1 registers (patterns, moves within/between cards, counting carries); 2 ALU pairs with the
    equality condition; 3 TMP0/TMP1; 4 RAM $0000-$CFFF address pattern and inverse; 5 ROM checksum; 6 fetch stress (R0
    on the address bus, read, count, back to back); 7 I/O. Each in an ISA-timed form (source one step before the latch)
    and a tight form (same step): a pair that splits shows the margin. Clocked from the function generator, the
    frequency at which each test first fails ranks the slow paths.
  - Build: `tools/udiag.py` (Python, signal table read from `yaccsignaldata2.h`, 256-record test.hex, unused records
    HALT), checked on `y1ucemu -u ... -T -L -w` (and with a broken card model it must stop at the right test) in `make
    check`; loaded with `ucode_send.py` (only the differing records, ~40), the ISA back with `--all`. A second FTDI on
    the sequencer's loader is planned, so the tester can stay on as bus-monitor: `ucode_send.py` must find it.
  - First version: tests 0, 1, 4, 5, 6 plus FAIL/pass reporting.
- **`y1ucemu`: electrical checks on every bus - undriven when sampled, and conflicts (2026-10-11, not started).**
  - Why: the POPR fault (fixed `ad0cef3`) passed both emulators for weeks. `y1ucemu` took ADDR-REG-ID straight from
    the control word, but on the machine that field reaches the backplane only through the sequencer's IC18B, which
    is off while `-2-BYTE-OPERAND-SEL` is asserted; the two-byte mode was modelled for REG-RD-ID/REG-LD-ID (sequencer
    IC5, `y1ucemu.c` "sequencer IC5") but not for ADDR-REG-ID. And the machine agreed with the model: at 6 MHz the
    floating select still held SP. The 2026-10-10 change makes that read return $FFFF, so it is caught only when a test's
    output changes. Checked 2026-10-11: the pre-fix `test.hex` (`ad0cef3^`) under today's model prints `25#` and
    hangs on T1 (the machine's symptom); under `-O` it counts 1..5.
  - 1. **Every bus as drivers with enables**: the data lanes (done today), the address bus (today one computed value:
    the selected register, OR $F000 under FORCE-ROM) and the select lines ADDR-REG-ID / REG-RD-ID / REG-LD-ID (today
    taken from the word), each through the card buffers that really drive it (sequencer IC5, IC18A/IC18B, IC11A; the
    register cards' ID decode; the FORCE-ROM gating).
  - 2. **Undriven when sampled**: at each consumer's sampling edge every lane it takes must have a driver - trailing
    edge for REG-LD-LO/HI, the TMP loads, the accumulator, `-MEM-WR`, `-IO-WR`; leading edge for the
    `LEADING_EDGE` list in `tests/ucemu/prologue.py` (LD-INS-REG, OPERAND-CLK, BRANCH-LD-*, ...); a memory or I/O read
    needs the address bus driven for the whole strobe. Report opcode, step, consumer and bus, as `-w` reports fights.
    With item 1 this flags POPR on its first execution ("-MEM-RD, ADDR-REG-ID undriven, record $08, step 10") at any
    clock, whether or not the wrong value changes a program's output.
  - 3. **Conflicts**: two or more enabled drivers on any bus, whatever their values. Today's fight check counts only
    drivers that disagree, so two outputs enabled together stay silent until the data differs; and the address bus
    has no fight check at all (the 2026-10-10 bench case: the bus tester left ADDR-REG-ID at 0 and R0 drove the address
    bus against the tester - every read $A0).
  - Allow-list the deliberate cases: the register cards' pull-up reads (review M-1, 327 steps), the ALU's $FF on
    DATA8..15.
  - First step, measurement only: the checks in a scratch copy, the existing suites (`tests/ucemu`, `make check`)
    run, every flag listed; then the allow-list; then `make check` fails on any new case.
  - Limit: a logic check. Set-up/hold and races (the FORCE-ROM/A15 race, review M1) need timing; the microcode
    diagnostic suite's clock sweep (above) is the tool for those.
  - Related static check (probe 2026-10-11, not committed): no step may read or write memory while asserting
    `-2-BYTE-OPERAND-SEL` (`docs/system/MICROCODE.md` 4.4). Pre-fix `test.hex`: 11 steps, all in record $08 (POPR);
    today's: 0. A candidate `tests/ucemu/twobyte.py` beside `prologue.py` and `idle.py`.

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
  netlist, DRC 0 errors / 0 unconnected, gerbers ready; theory in `docs/cards/cf.md`; never ordered.
  Card-preparation procedure written: `docs/procedures/CF-CARD.md`. A move of the interface onto an I/O card v2.0 on
  ports P4/P5 was designed 2026-09-23 and dropped 2026-09-24 (6eeb259, 65851b0).)
  **2026-10-09: memory card v2.0 ORDERED from JLCPCB, order 2000765A-Y52.** **2026-09-25: memory card v2.0 FINISHED FOR FABRICATION** (`hardware/cards/memory/kicad/v2.0`, README
  "The v2.0 board"): **standoff option E** (chosen 2026-09-25) - the CF-to-IDE adapter (HX-2118P: 60 x 44 mm, 2 M3 holes 52 mm
  apart at the header end, no pin 20) on two 15 mm M3 standoffs over the CF chips at the free top edge, J2 parallel to
  X1 with a short straight ribbon, the ROM uncovered in the top row of the memory column. **2026-09-29: + JP3, the ROM
  write-protect jumper** (design review M2; 1-2 WRITE, 2-3 PROTECT), added locally beside the ROM, the rest of the
  route unchanged. **2026-09-30: + R15, the 470 Ω ADDR15 pull-down** (design review M1, the FORCE-ROM race),
  added locally beside the bus connector (pad 1 on the ADDR15 track, which was split there; no via). **The 1:1 print
  changed again (JP3, then R15): reprint it before ordering.** `memory-v2.0.kicad_pcb`:
  0 unrouted, 72 through vias, DRC 0 copper violations / 0 unconnected, planes one piece each, netlist proof MATCH,
  silkscreen tidied (adapter outline, standoff holes H1/H2, "CF CARD INSERTS HERE", J3 / JP2 / LED labels); gerbers +
  NPTH/PTH drill zip, renders, placement PDF, BOM (+ standoffs, screws, washers, ribbon), JLCPCB order note (as order
  2000765A), 1:1 print. **Open before ordering:** the ribbon plug's pin 20 (open, or pull J2's pin
  20). Resolved 2026-09-26: the adapter's power pads are a floppy pinout in J3's order, so the J3 cable is straight
  through (a harness built by hand). Resolved 2026-09-25: the card-cage slot in front of the memory card stays empty, so
  the ~35-44 mm stack does not matter. Before that (2026-09-24 evening): five standoff placements A-E trial-routed
  with 1:1 check prints (records in the folder).
  Earlier the same day: **memory card v2.0 ROUTED, fab files ready, NOT ORDERED**: `hardware/cards/memory/kicad/v2.0`
  (built memory card + CF on P8/P9, schematic proven) did not fit with the built card's copper kept, so the whole card
  was laid out again (same circuit, outline, X1, 4-layer GND/VCC planes; 0.25 mm tracks / 0.2 mm clearance / 0.8-0.4 mm
  vias). Option B was chosen (TMP registers at the bus connector, CF column at the top edge, J2 centred);
  `memory-v2.0.kicad_pcb` is routed (0 unrouted, 43 through vias, DRC 0 copper violations), silkscreen tidied, gerbers
  + drill zip, renders, placement PDF, BOM and the JLCPCB order note (4 layers, 1.6 mm, as order 2000765A) are in the
  folder. **Before ordering**, the open items in its README: J2 pin-1/key vs the chosen adapter, J3 pinout vs the
  adapter's power cable, socket heights under a TAODAN overhang, which backplane slot (TAODAN needs ~75 mm free).
  C20-C23 (four spare 100 nF with no IC): removed (2026-09-24), board and fab files re-made. Earlier plan:
  design the CF interface onto the **memory card** (more room, chips spaced far apart),
  kept I/O-mapped on **P8/P9** with the CF card v1.0 circuit (own 74LS138 enabled by IO-ADDR3, 74LS32, 74LS175, 74LS08,
  74LS245, 40-pin IDE header); the memory card's IO-ADDR0-3, -IO-RD and -IO-WR pins are on its connector but unwired
  today (`docs/cards/memory.md`). The CF-to-IDE adapter is undecided: a SinLoon CF-IDE on a ribbon/standoffs, or the
  TAODAN CF-IDE40 V2.0 plugged straight onto a male header (`docs/cards/cf.md` section 0). The ROM in the machine
  (`ROM 2026-09-23`) already drives P8/P9, so no burn is needed. **After building**: the bring-up steps in
  `docs/cards/cf.md` section 7 (empty adapter = `CF ERROR`, the P8 latch on the IDE header's DA pins, then `O` with a
  card prepared by `tools/cfcard.py` from `os/disk.img`).
  - **2026-10-23: design review of the fabricated v2.0 before the build: `hardware/DESIGN-REVIEW-memory-v2.0.md`**
    (HIGH 0, MED 4, LOW 8, INFO 8; verdict: build as is, no bodge wire needed at 1 MHz; the board, schematic and gerbers
    unchanged, the gerbers' copper traced net for net against the board). Open actions:
    - **Before the adapter goes on (M2-1):** the record of the HX-2118P's pin 1 ("left end of the outer row", pin 20
      "the 10th of the inner row") is the mirror of standard numbering; the straight ribbon is right only if the
      adapter's missing pin is in its *outer* row, the 10th from its H1 end. Look at the adapter, then the meter check
      of the review's bring-up stage 4 (J2 pins 1, 3, 23, 25, 39 must not beep to GND) before power.
    - **Adapter jumpers (M2-2):** 5 V and master, before its first power-up.
    - **Microcode, for 6 MHz disk work (M2-3, M2-4, M2-6):** `INP` one more step between `-IO-RD` and `-AC-LD` (also
      the microcode review's M-3) and a release step without `-IO-RD` at its end (also video V2-14); `OUTA`/`OUTI`
      hold `-IO-WR` two steps. Until loaded, disk work at ≤ 4 MHz.
    - **ROM driver, next burn (M2-9):** `cfdrq` waits for BSY = 0 / DRQ = 1 / ERR = 0; `cfread`/`cfwrite` return the
      `cfwait` time-out. Correct `docs/cards/cf.md` 7: `O` with no card takes ~20 s at 1 MHz (M2-18).
    - **Optional bodges:** 10k JP3 pin 2 to pin 3 (no cap = PROTECT, M2-10); 4.7k pull-ups on `-IO-WR`/`-IO-RD` at
      IC31 (M2-5); RN9 47k only if the write hold measures short (M2-8).
    - **On the v1.3 card (M2-13):** measure the IC7 pin-4 wire (IC7 pin 4 to X1 C12 < 1 Ω on the chip's leg, the
      wire's far end open, no cut); v2.0 needs no wire either way. Also read off it JP1's position and RN5/RN6's value
      for the v2.0 build (M2-11, M2-12).
    - `y1ucemu`'s floating-address model: $7FFF with R15 fitted (M2-14).
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
- Wave 3 of the port: (done 2026-09-25: **`asm`**, the on-target assembler for the RC/asm dialect, table generated from
  `yacc1.def` - `os/README.md` "asm", `tests/asm`), (done 2026-09-29: **`disasm`**, `os/commands/disasm.c`, 6,107
  bytes: `disasm [-s] FILE [START [COUNT]]` / `-m ADDR [COUNT]`, lines in RC/asm's dialect that reassemble byte for
  byte, unknown bytes as DB; its table `os/dis_optab.c` generated from `yacc1.def` by `tools/gen_y1_distab.py`, which
  runs the assembler generator's Translate() backwards and checks every opcode against `software/opcodes.h`;
  `tests/disasm/run.py` round-trips 382 programs/sources/ROM/synthetic files through RC/asm, `tests/os/disasm.session`
  reassembles its output with /BIN/ASM under Y1/OS - `os/README.md` "disasm"); `vi` done 2026-09-23. Then BASIC as
  /BIN/BASIC.
  - disasm follow-ups (2026-09-29, none needed for it to work): (1) labels - a second pass that names every branch/JSR
    target inside the range (`L5003:`) and prints `BR L5003`, so `-s` output reads like source and can be edited and
    moved (today it reassembles only at the same address); (2) not yet run on the machine (no CF card yet): nothing in
    it is machine-specific beyond peek and the syscalls every command uses; (3) seen in passing: `tests/compiler/passes.py`
    lists `os/commands/help.c` (STRPOOL: its strings), `os/commands/kermit.c` and `tests/os/rdn.c` (NODES_MAX) as not
    fitting the native passes' tables, besides y1cc.c - help.c already before disasm's line was added; the docs name
    only y1cc.c, and none of these is built natively today.
- `/BIN/ASM` follow-ups (2026-09-25): (1) speed - (done 2026-09-26: **`/BIN/ASM` in YACC1 assembly**,
  `os/commands-asm/asm.asm`, identical to asm.c - now `/BIN/ASMC`, the specification - on the whole `tests/asm` corpus
  and in the self-host's fixed point; 4.3-5.3x fewer instructions, 5.2x in clocks: `cat` 12.8M -> 2.75M, cc8's 235K
  129.7M -> 26.4M; a native build's assembling 217M -> 46.5M, 9% of it; the self-host's stage 21 h 17 min -> 15 h 47
  min at 1 MHz; the label table 17,088 -> 20,292 bytes; `docs/programming/ASSEMBLER.md` section 10). Left in asm.asm,
  a few percent each (`tests/native/profile.py`): the label hash over the whole name (the last four characters and
  the length chain as well), 512 chains (-1.7 records a lookup, 512 bytes of table), hashing the mnemonic in the
  getln loop, unrolling `gl_lp`; the ROM's sector reads are 12% and fixed. Keep asm.c and asm.asm in step: a
  change of behaviour goes into both, `tests/asm/run.py` compares them; (2) sources over 64K - (done 2026-09-25:
  24-bit positions); (3) what RC/asm accepts and asm refuses (MACRO, PUBLIC/EXTERN/LIB, '/' beyond 16 bits,
  EQU values beyond 16 bits) - nothing in the tree uses them; (4) `asm` inside a `>` or a pipe needs the OS's second
  write handle ("Y1/OS still to write", above).
- RC/asm (host) aborts on a line whose text after the label or the leading blanks, up to the comment, is 100
  characters or more (`trim()`/`parse()` copy it into `char tmp[100]`, and macOS's fortified strcpy traps; found
  2026-09-25 writing `tests/asm/src/quirks.asm`); y1cc's lines are shorter, and /BIN/ASM takes 254. A
  `tools/patched_files.txt` fix to the host, with `make -C software/assembler check` and `tests/asm` after it. The assembly OS has 18 sectors of headroom in the
  16K reserve (LBA 1..32) and 7,711 bytes free below its RAM (2026-09-23, v0.2).
- (done 2026-09-23: **redirection and pipes** — `cmd [< in] [> out | >> out] [| cmd ...]`, up to 4 commands, clauses
  after the arguments, quotes protect `| < >`; `y1cc --os` makes putchar/puts the new syscall CONOUT (19) and getchar
  CONIN, KEYIN (20) is always the keyboard (pager, vi, dump, examine), STDIO (21) says what is redirected (the pager
  stops paging into a file); pipes run stage by stage through /PIPE0.TMP and /PIPE1.TMP, deleted after the line;
  `>>` appends in place when the file is the last one written, else copy-then-extend; CREATE now replaces a same-named
  file at CLOSE (the new entry over the old slot); eputs() and the shell's errors go to the raw console; the four
  handle buffers moved to $0400-$0BFF to fit (OS image 14,673 bytes = 29 sectors, image + data 16,097 of 16K);
  `tests/os/redirect.session`, `pipe.session` with host checks; `os/man/shell`.)
- Redirection and pipes, what is left: no `2>` (errors always go to the screen); stages run one after the other, not concurrently; a
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
- (done 2026-09-25: **SYSTAB 22 -> 32 entries** — the OS fills SYSTAB2 at $4FC0-$4FFF (32 entries) and copies its
  first 22 to SYSTAB at $0F14, so every program compiled before (and `tests/compiler/syscall.c`, the bench image
  `syscall.img`) keeps working unchanged; y1cc's `sys()` reads SYSTAB for a constant 0..21 (output unchanged) and
  SYSTAB2 for 22..31; a computed number still indexes SYSTAB (0..21). `os/README.md` "Two tables",
  `tests/compiler/syscall2.c`, `sysbig.c`, `tests/os/systab.session`. Left: a computed number over 21.)
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
- (done 2026-09-27: **the "READN gives stale data" report** (from the `/BIN/ASM` work, 2026-09-26) - not READN:
  the READN trial of `asm.asm` (`READN(fh, SDATA, 512)` in `gs_rd`) kept the skip it needs after a SEEK with READ
  (`GL_SKIP`: READ starts at the sector's start, READN at the position), so after every INCLUDE it lost the outer
  file's next bytes (tests/asm QUIRKS.ASM, first run or not); READ is what `asm.asm` uses. The hunt found a real bug
  next to it, in `y1os.asm` only: since 6a42b9f (2026-09-25, 24-bit positions) `fs_getc`'s sector-boundary compare
  read the handle's start LBA instead of its buffered sector (a missing `ANDI 0F0H`), so GETC and READN re-read a
  sector at nearly every boundary and returned the buffer's stale bytes for the sector whose number equals the
  file's start LBA - only possible for a file longer than its start LBA in sectors, which no disk made from
  `os/disk.img` can hold (the free pointer is past 1,100 on 2,048 sectors), so no test or native compile ever met it.
  Fixed; READN's exact contract documented (os/README.md, docs/programming/OS.md, man fs); `tests/os/rdn.session`
  (`rdn.c`: every READN count and byte against the contract in the mixed patterns) and `rdnlow.session` (a fresh
  volume, a 40K file at LBA 37: failed at byte 18,944 before the fix), both kernels, both emulators.)
- `software/emulator` (instruction level) treats a lower-case `q` on the console as end of input (`mygetchar()`,
  an old quit key): a command line containing `q` (`uniq`, `sed s/q/x/`) is cut there. Sessions use `UNIQ` and `Q`
  until it is fixed; the microcode emulator has no such quirk.
- Y1/OS details found while writing the man pages (2026-09-23, not fixed): `path_push` stops extending the textual
  current path past 62 characters while `cd` still descends, so the prompt/GETCWD (and every command's `abspath`)
  point at the wrong directory that deep; the built-in `rmdir` says "not an empty directory" for every failure.
  (The `load_file` whole-sector overrun past $CFFF was fixed the same day: the check now uses the sector count.)
- `vi` redraws the whole current line on every keystroke in insert mode (`<ESC>[r;1H` + line + `<ESC>[K`): fine on the emulators, ~80 bytes per key at 9600 baud on the machine; redraw only from the cursor, or just echo the character when appending at the end of a line.
- Phase 4: video card v2 (6845 on ports PA/PB, 2K RAM) + PS/2 keyboard behind the console vectors.
- **`kermit` (`/BIN/KERMIT`, 2026-09-26; `os/README.md` "kermit", `docs/procedures/KERMIT.md`)** - done on both emulators
  against `tools/y1kermit.py` (`tests/kermit`), open:
  - **On the machine with C-Kermit**: not run yet. To verify there: that the XR16C550's FIFO works as kermit uses it
    (FCR = 7 at the start, 0 at the end; if it does not, packets over ~13 characters overrun at 38400: try `kermit -r
    -l 20`, then a lower line speed), the timeouts at the real clock (poll counts calibrated for 1 MHz), C-Kermit 9.0.302
    with `tools/y1.ksc` in all three modes, and autodownload.
  - Not implemented (optional in the protocol; each would cost code in a program already at 27K of the 32K area):
    **long packets** (E-Kermit's F_LP: up to 4096 characters a packet, fewer ACK round trips; with the six-step fetch
    prologue a receive burst that long would overrun the 16-byte FIFO at 279 clocks a character against the line's 260;
    with the three-step one of 2026-09-29 the loop takes 217 and keeps up, so receiving becomes possible once the
    microcode is reloaded - the packet buffer is the remaining limit), **sliding windows** (F_SSW; the same), streaming, locking shifts, RESEND/recovery of an
    interrupted transfer, file dates in the attribute packet (Y1/OS has no dates), and the server's REMOTE commands
    (DIR, CD, DELETE, TYPE, SPACE: each a G subcommand; now "Unimplemented server command").
  - A timer would make the timeouts real seconds at any clock (today a count of UART polls).
  - The instruction-level emulator's port 2 still turns `q` into end of input (item above); the UART model added for
    kermit does not, so the two console paths of that emulator now differ in that one byte.
- (done 2026-09-22: `yacc1.def` P8=9 typo -> P8=8.)

## C compiler (y1cc, 2026-09-22)
`software/compiler/y1cc.py` compiles p8cc's C subset to YACC1 assembly (static frames, R3 accumulator, see its README);
12 test programs pass on the emulator (`make cc-test`), 9 of them checked against the host C compiler as an oracle.
- (done 2026-09-24: **`software/compiler/c/y1cc.c`, the C twin** — 3,122 lines in the C89 + y1cc subset, the same
  assembly as y1cc.py on the whole corpus including itself, `tests/compiler/twin.py` in `make check`; compiled by
  y1cc.py it is an 82,345-byte image, 2.5x the 32K program area.) **The road to a native compiler**, in order:
  1. (done 2026-09-24: **the multi-pass compiler** — y1cc.c split into nine programs `software/compiler/c/cc1_lex.c`
     .. `cc9_final.c` (lexer; parser; declarations; call graph; labels and frames; statements; expression analysis;
     expression code; the text), chained by `y1ccp` on the Mac: the same assembly as y1cc.py on the whole corpus
     (`twin.py --chain`, `--chain16`: 126 programs + 4 errors, the passes compiling themselves among them) and on
     random programs (`twinfuzz.py --chain`, seeds 1-6 x 500, the 60 error programs and 20 with two errors found
     in different passes, where the first in y1cc.py's order must win). Every pass compiled by
     y1cc.py and assembled fits $5000-$CFFF with its Y1/OS tables and its measured stack, the tightest cc9 with 244
     bytes to spare; with those tables the chain compiles the whole corpus but y1cc.c (`tests/compiler/passes.py`,
     in `make check`). software/compiler/README.md, "The multi-pass compiler".)
  2. (done 2026-09-25: **a stack for the native compiler** - y1cc `--stack ADDR` (the chosen design) in y1cc.py, y1cc.c
     and the passes: main saves the caller's SP on its own stack at ADDR and puts it back at every return; the
     passes are built with `--stack 0xCFFF` (`make -C os passes`), and `tests/native/run.py` runs them under Y1/OS
     with the emulator's program watch (`emulator -S`): every pass stays above its data (measured 2026-09-24 in
     passes.py: 84-1,202 bytes on the corpus, cc2 about 144 more per level of parentheses, cc8 62 per level of
     operators).)
  3. (done 2026-09-25: **Y1/OS for the compiler** - files over 64K (24-bit positions and lengths in both kernels,
     `tests/os/big.session`), SYSTAB2 (32 entries), the syscalls EXIT, EXEC and SEEK (`tests/os/exec.session`),
     `/BIN/CC` chaining the passes with EXEC, the lexer's `#include` stack over three real handles
     (`c/target_inc.c`), `/LIB/Y1CCRT.TXT` and `/LIB/Y1LIB.C` on the disk. The passes are built with `--xisa` since:
     with the chaining and the include stack cc1, cc6 and cc9 no longer fit 32K without it.)
  4. (done 2026-09-25: **the passes run under Y1/OS** - one by one and chained by `cc`, on the emulators;
     `tests/native/run.py`: 27 programs compiled by `cc`, assembled by `/BIN/ASM` and run under Y1/OS, the tests,
     four `/BIN` commands and the compiler's own pass 4 among them, byte-identical to the host toolchain; about 32 us
     an instruction at 1 MHz, so hello 3.7 minutes, fib 18, cat.c an hour, pass 4 2.3 hours - software/compiler/
     README.md "Native".) Follow-ups:
     - (done 2026-09-25: **speed** - the passes' I/O buffered through the new syscall READN and a WRITE that copies
       a sector's rest at once (both kernels, `tests/os/big.session`), and the hot spots `tests/native/profile.py`
       (the emulator's `-P` PC histogram) showed: cc9 made the code text in all three section readings, parsed each
       line three times, divided twice a digit; cc1's lookahead array, operator search and per-character hash; cc2's
       token calls; cc4's matrix multiplies. Compiles 2.7x faster (all 27 of tests/native: 1,269M -> 468M
       instructions), compile + assemble 2.2x (13.3 h -> 6.2 h at 1 MHz); cat.c 57 -> 24 minutes, pass 4 2.2 h -> 57
       min. software/compiler/README.md "Native".) Left, largest first: `/BIN/ASM` is now 30% of compile + assemble
       (`getln`, a third of it, ~50 instructions a source byte; `hash`, `asmcmd`, `same`); cc9's text building
       (`mn_arg`, `Ls`, `bcat`: ~20% of a compile) - (the assembler: done 2026-09-26, asm.asm, 9% of compile + assemble
       now); the ROM loading each pass and `main`'s BSS clear (~2M a compile,
       half of hello's time); cc2's parser; cc7's and cc8's records a byte at a time. The passes' room shrank for
       it: cc1 314 bytes free, cc9 463 (`passes.py`), and `/BIN/ASM`'s symbol pool grew to 17,088 bytes (cc8's
       labels need 16,925; the assembler fills 32,755 of 32,768; asm.asm's table is 20,292 since 2026-09-26).
     - The passes need the 2026-09-24 microcode (`--xisa`) since the chaining and the lexer's include stack: without
       it cc1, cc6 and cc9 are 26-985 bytes over 32K. So the machine needs the EEPROM reload and `tests/bench` (the
       --xisa item below) before it can compile, besides the CF interface Y1/OS itself needs.
     - The work files `CCW.*` stay in the current directory (replaced by the next compile; pack reclaims the space);
       cc9 could delete them, at the cost of bytes in the tightest pass.
     - (done 2026-09-25: **the full native self-host** - `tests/native/selfhost.py`, `make selfhost`, in `make check`:
       under Y1/OS on the instruction-level emulator the host-built CC/CC1..CC9/ASM compile and assemble the nine
       passes, asm.c and cc.c from their sources on the disk, all eleven byte-identical to os/build; then the natively
       built tools, installed in their place, do it again, identical again: the fixed point. Nothing had to change
       (every table, stack and file held). 2,365M instructions a stage, about 21 hours at 1 MHz; the image grows to
       5.7M (P8XFS: 32M at most). software/compiler/README.md "Self-host".) y1cc.c, the single-program twin, still
       does not fit the passes' tables (833 names, 130K of source) - it is not needed natively.
     - (done 2026-09-25: y1cc: a block comment that starts on a `#define` line and continues on the next was not
       skipped (the next line was lexed: `$` in it was "bad character", found in `os/lib_abi.c`). Now a directive's
       `/* */` comment is one space and may go on over newlines, a `//` ends the directive, neither inside quotes
       - y1cc.py, y1cc.c and cc1 alike; `tests/compiler/dircomment.c`, `dircomline.c` (the line numbers after it);
       os/lib_abi.c's EXIT/EXEC/SEEK comments are back beside their `#define`s.)
  5. (done 2026-09-25: **the on-target assembler** `/BIN/ASM`, wave 3 of os/PORT-PLAN.md - byte-identical to the host
     assembler on the corpus, the nine passes' assembly among it; its 16,640-byte symbol pool holds cc8's 1,326
     labels, the most of any pass. The host assembler's label table: done 2026-09-24, 8,191 labels with a clear error
     when full, was 1,000 with no check.) Left before a pass is assembled on the machine: its assembly is 110-257K
     and Y1/OS files stop at 64K (step 3), and the speed (about 9,000 instructions a line: BACKLOG "Disk operating
     system", the /BIN/ASM follow-ups).
  6. Code size of what y1cc emits (the bullet below): every byte saved there shrinks the native compiler too — cc6,
     cc7 and cc9 are within 600 bytes of the 32K (cc6 since the --xisa page planning); the nine passes are 124K of code
     against y1cc.c's 75K, 102K when compiled with `--xisa` (2026-09-24: every pass then has 2-15K free).
  7. y1cc.c, the single-program twin, stays until the passes run on the machine (a y1cc.py change now has two C
     counterparts to follow), then can go.
- y1cc.py: a function defined twice is not an error — both definitions are laid out and the last is compiled twice
  under the second label (`f_f_1:` twice, which the assembler rejects); y1cc.c and the passes compile it once. Make it
  an error like "global declared twice" (a y1cc.py change, still to be decided; the C versions follow). Found 2026-09-24.
- (done 2026-09-23: the rebuilt ROM is burned — `ROM 2026-09-23`, MD5 d2d7b027…, = `firmware/rom/shipped/rom.bin`; monitor
  G = `JSRUR R7`, so `--vector` is only for a 2021 chip.) (The read-back: done 2026-10-07 for `ROM 2026-10-07`
  with the TL866II+, identical to `firmware/rom/shipped/rom.bin`.)
- (done 2026-09-22: the sequencer EEPROM holds the regenerated image — BRUR at $AD, the H-2 fix in BRZ/BRNZ/BR16Z/BR16NZ, the
  H-1 fix in PUSHR; six records differed, all 256 sent with `tools/ucode_send.py --all`; the scope look at the old image's
  bus fight was skipped.) (done 2026-09-23 evening: `tests/bench/run.py --port` 14/14 on the machine after the SHIFT-OUT carry fix; first run found the fault.) **Bench-check the reloaded microcode** (first evidence 2026-09-22/23: `tests/assembler/romcount` ran overnight from ROM — BRNZ, DECR, MVRHA, MVAT/MVTA, ADDI, OUTA/INP, BRINL — after `romdiag` had shown the bring-up machine lacked register card 1; card fitted, R7 reads correctly). The rest is ONE command since 2026-09-23: burn the ROM, then
  `python3 tests/bench/run.py --port /dev/cu.usbserial-X` loads and runs hello, BRUR (`ABC0123`), the ISA sweep (every
  instruction, one hex byte each) and 12 compiled C programs through the `:` loader and diffs each against the microcode
  emulator's transcript; the log lands in `tests/bench/logs/` (`docs/procedures/BRING-UP.md` section 6b).
- (done 2026-09-23: **compiled C runs on the machine** — eleven y1cc programs in `tests/bench/` pass through the `:` loader.)
  First hardware checks: `rt_sub` (INVA/moves between ADDTC), `rt_divmod` (SUBT/SUBI after a comparator branch), the
  shifts (`LDAI 0 / CSHL` carry clear), `BRDEV` selecting the BIOS path, and that `BR $F000` after main is acceptable
  (it restarts the monitor: BASIC cold start, banners). A `cmdloop` BIOS vector would be cleaner than the restart.
- (done 2026-09-24: **recursion** — static frames kept, a call inside a recursive cycle saves/restores the callee's frame
  on the stack; functions outside a cycle compile byte-identically, `tests/compiler/diffcheck.py`.) Still open:
  reentrancy (an interrupt handler in C), overlaying the static frames of functions that are never live together
  (cheap, no semantic change), a stack-overflow check (the stack is 768 bytes, $0C00-$0EFF).
- (done 2026-09-22: `switch`, compare chain or BRUR jump table by size, `--no-brur` until the microcode is reloaded.)
- Function pointers (`BRUR`/`JSRUR`), signed `int` (BRLT/BRGT are unsigned comparators: signed compare = flip bit 15
  first), `long`, `goto`.
- **`--xisa`** (2026-09-24: `LDZ`/`STZ` through a 256-byte variable page, `ADDIW`, `SHL16`; README "--xisa").
  (done 2026-10-04: (1) the EEPROM holds that microcode, `tests/bench --port` 15/15; (2) **it is the default**: y1cc.py,
  y1cc.c and cc1 take `--no-xisa` for the old code (`--xisa` still accepted), `os/Makefile` builds every `/BIN`
  command with it (`NOXISA=1` the old build), the harnesses take `--no-xisa` (tests/asm compiles the corpus both
  ways), 10 tests/os transcripts and 12 bench images refreshed - sizes only, outputs unchanged; (3) the passes were
  already built with it since 2026-09-25. On the machine the same evening, every bench program as `--xisa` code:
  15/15 across `bench-2026-10-04-2130` (hello, brur, isa, arith), `-2144` (calls) and `-2145` (calls again, then
  control .. xisa).) **Watch: one crash in the monitor's `:` loader** (`bench-2026-10-04-2130.log`, ~2 minutes into
  the run, during `calls` record 19: no answer, then a stream of garbage characters on the console - the CPU off
  its program); after a reset `calls` loaded and passed twice and the next ten loads were clean. Not reproduced:
  note the time into the session and the program if it happens again (temperature, clock, a marginal step). Later: rely on SHL16's carry out of
  bit 15 in `rt_divmod`'s double-width shift (tested on both emulators, not on the machine yet); a second page
  (a family through R6.lo would need 16 more opcodes; only 5 are left) or word offsets; drop LDZ/STZ's three idle
  microcode steps (they take 30 steps like LDR: they save a byte, not time); `ADDIW R1` for stack frames.
- Code size: peephole over R3/R4 traffic (store-then-reload across labels, `MVIW R3,k / MVRLA R3` → `LDAI`), 8-bit paths
  for char arithmetic (`c + 1` still goes through 16-bit add), constant compares with a zero high byte, `for` loops
  counting down to 0. Measure with `run.py` (bytes + instruction counts per test).
- (done 2026-09-22: `software/ucemu` counts steps and clocks; a per-opcode cost table from it is a one-liner away.)
- Microcode emulator follow-ups: interrupts (a source, INT/IRET/IADDR checked against the generator), automatic trace
  comparison against the interpreter, the video card. (The CF model with a disk image, `-c`, is done: 2026-09-22 on
  P8/P9.)
- Port the P8X libraries/programs that fit the subset (the P8X OS itself needs its syscalls; recursion exists since 2026-09-24).
- Emulator (done 2026-09-22, `tools/patched_files.txt`): `-x` scripted mode; BRVR and JSRUR now follow the microcode, so the
  monitor's `G` and `T` commands work on the emulator (they never had). Still stubs vs the hardware: IRET/INT/IADDR, SUB
  borrow into carry, shifts loading carry, opcode $00. (LDTVR/STTVR, which it ran without microcode, became ADDIW/SHL16
  on 2026-09-24.)
- Assembler (done 2026-09-22): `DS` flushes the hex record. Still open: negative numbers silently mis-assemble, labels
  over 29 chars crash it, source lines are upper-cased (strings in `DB "..."` come out upper-case).
