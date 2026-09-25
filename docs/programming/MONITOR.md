# The ROM monitor and BIOS

The program in the YACC1's 28C64: what it does at reset, every command, the BIOS vectors and their conventions, the
variables page, the CompactFlash driver and the `O` boot, the video card driver and the `V` command, BASIC's place in
the ROM, the interrupt service routine, and how the ROM image is built and verified. Written 2026-09-23 from the
YACC1-D tree; the video unit (section 11) added 2026-09-25.

Sources: `firmware/monitor/monitor.asm` (the source; addresses from `monitor.lst` as rebuilt 2026-09-23 09:36),
`firmware/abi/README.md` (the ROM's interface), `firmware/rom/README.md` and `firmware/rom/makerom` (the image),
`firmware/README.md`, `firmware/basic/README.md` and `firmware/basic/basic.asm` (the BASIC half), `tools/verify_firmware.py`,
`tools/img2bin.py`, `tools/romimage.py`, `tests/memory/rom_verify.py` and `memory_status.py` (docstrings),
`docs/system/MACHINE.md` (what the chip holds), `software/emulator/main.c` and `software/ucemu/README.md` (how the
emulators run it), `BACKLOG.md`.

## 1. Two monitors: the chip and the tree

- **On the chip** (memory card, 28C64): the 2026-09-23 afternoon build (banner `ROM 2026-09-23`, MD5
  d2d7b027e7c6951d7dd93412a8fd9cd8, CF driver on P8/P9), burned by Ken 2026-09-23 (`docs/system/MACHINE.md`). Before
  that the 2021 build (git ff7d85a), captured 2026-09-18 as `firmware/rom/eprom-captured-2026-09-18.bin/.hex`,
  byte-identical to the 2021 sources.
- **In the tree** (`firmware/rom/shipped/rom`, since 2026-09-25): `ROM 2026-09-25`, **not burned yet** — the chip's
  build plus the video unit (section 11: the driver, the `V` command, mirroring in CHAROUT, the video entry at $FFBC,
  the variables at $0FF0), a shorter help text and the never-called routines removed to make room (MD5 in
  `firmware/rom/README.md`). The old chip stays compatible with everything else in the tree (Y1/OS's `video` says the
  ROM has no driver). Before it:
- **The chip's build** (`git show 65851b0:firmware/rom/shipped/rom`): the 2026-09-22 rebuild of `monitor.asm` — the `G` command
  fixed (`JSRUR R7` instead of `BRVR R7`), the T-menu bench tests removed (1,062 bytes), the CompactFlash driver, the
  `O` boot command, four new BIOS vectors and two new variable areas — plus, on 2026-09-23, `uartinne` (console
  input without echo) and its vector at `$FFFC`, the sixteenth and last slot, the `:` Intel-hex loader and the build
  date in the banner. BASIC is unchanged. Object code 3,398 bytes, 0 errors, 218 labels, 1,535 source lines
  (`monitor.lst`). A `ROM 2026-09-23B` rebuild (CF driver and `O` on P4/P5, for an I/O card v2.0) was made on
  2026-09-23 evening and withdrawn on 2026-09-24 without being burned (`firmware/rom/README.md`).

`tests/memory/rom_verify.py` and `memory_status.py` therefore compare the chip with the image it was burned from; a
chip still holding the 2021 build differs in the monitor half.

## 2. Reset and boot sequence (`monitor.asm` `eprom:`, $F003)

1. `$F000: BR eprom` — the first fetch happens under the memory card's FORCE-ROM remap (the ROM answers at every
   address after reset); the branch target $F003 has A15 high, which ends the remap.
2. `MVIW R1,STACK` — the stack pointer to `$0EFF`.
3. UART set-up through P0/P1: LCR ← $80 (DLAB), DLL ← 3 (**38400 baud**; the commented alternative `12` was 9600),
   DLM ← 0, LCR ← 3 (8 bits, no parity, 1 stop). Register offsets `UARTA0..A7` = 0, 8, … $38 OR `UARTCS` $40
   ([IO-PORTS.md](IO-PORTS.md)).
4. `monmode` ← `NOMODE` (0), `interupt_cnt` ← 5.
4a. (2026-09-25) `JSR vidreset`: mirroring and the CRTC cursor off, the video cursor home, the $D000 probe
   (`VIDPRES`); with `VIDAUTO` = 1 also the CRTC table, a clear and mirroring on (section 11). `VIDAUTO` is 0: the
   card is only probed.
5. `JSR lblink` (a long LED blink), the banner `hello` → `YACC 2020: HELLO WORLD  ROM 2026-09-25` (upper-cased by
   the assembler, see [ASSEMBLER.md](ASSEMBLER.md) quirk 1), then `VIDEO CARD FOUND` when the probe found the card,
   `JSR basic_cold` (initialise the BASIC interpreter: it clears the token buffer at $1000).
6. Proof of life: `showaddr`/`show16` of the first 16 ROM bytes at $F000, `showregs`, then the address of `tttt`
   (the start-up test entry) printed as `F051:`.
7. `iaddr isrcode` / `INTE` — the interrupt vector is set to $FF90 and interrupts enabled.
8. `BRINH cmdloop` — **if the input-switch line is high the monitor goes straight to its prompt**; otherwise it
   falls into `tttt:`, prints `Run test code` (the tests themselves are gone) and branches to `cmdloop` anyway.

The emulators reproduce this: the interpreter starts at PC = $F000 with the images loaded (`main.c`); ucemu starts
from a real reset with FORCE-ROM set (`software/ucemu/README.md`).

## 3. The command loop and the commands (`cmdloop:` $F06A)

The prompt is `>`. The loop reads one byte with `uartin` (which echoes it), upper-cases it and dispatches by
comparing against a list of `LDTI 'x' / BREQ` pairs (`testexamine:`). Anything else prints `UNRECOGINIZED COMMAND`
and the help. A bare CR/LF is `continue` (below). The `H` text is the command reference; each command explained
from its code:

| Key | Command | What it does (`monitor.asm` label) |
|---|---|---|
| `H` | help | prints `helpmenu` ($FB12; reworded shorter 2026-09-25) |
| `0` | exit | `cmd_exit`: `BRDEV stop` — on the machine it loops forever at `stop:` (`BRDEV` branches); on the interpreter it falls into a `DB 0` = opcode $00 = `START`, which the interpreter reports as a bad opcode and exits. "Exit (emulator only)" |
| `B AAAA` | dump block | `dumpblock`: mode ← BLOCKMODE, reads 4 hex digits into R7 (`getaddress`), prints 256 bytes from the 16-byte-aligned address (`show256`), saves the next address in `continue_addr`; CR shows the next 256 |
| `C` | copy | `cmd_basic_copy`: `JSR basic_copy` ($E060) — copies BASIC's built-in test program into the interpreter buffer |
| `D AAAA` | dump | `dump`: 16 bytes at the address (`showaddr` + `show16`); CR shows the next 16 |
| `E AAAA` | examine / modify | `examine`: prints `AAAA: XX` and waits. Two hex digits replace the byte and advance (the value is read with `getbytec`, the two-digit reader shared with `getaddress` and `V` since 2026-09-25, stored with `STAVR R7`); CR or LF advances without change; Esc ($1B) or `-` ends. This is the only way to put bytes into RAM from the console (`BACKLOG.md`'s planned `tools/monload.py` drives it) |
| `F AAAA` | fill | `fillblock`: writes 0 into 256 bytes from the address (`morefill`: `LDAI 0 / STAVR R7 / INCR R7` until the low byte wraps); CR fills the next 256 |
| `G AAAA` | go | `go` ($F261): prints `GO ADDRESS:`, reads the address into R7, **`JSRUR R7`** (a call), then `BR cmdloop`: the program ends with `RET` and lands back at the prompt. History: until 2026-09-22 it was `BRVR R7`, an indirect jump through the word at AAAA that pushed no return, so `G AAAA` never ran the code at AAAA (the microcode's `branch()` fetches the target through the register). Compiled images for the old chip start with a 2-byte vector (`y1cc --vector`) |
| `I` | BASIC | `interpreter`: `JSR BASIC_INTERPRTER` ($E040) |
| `L` | list | `cmd_basiclist`: `JSR basic_list` ($E000) |
| `P` | parse | `cmd_basicparse`: prints `Enter Line:`, reads a line into `line_buffer` ($0F80) until LF, shows it, `JSR BASIC_PARSE` ($E050) — enters one program line into BASIC's token buffer |
| `R` | registers | `dumpreg`: `showregs` — R0..R7 as four hex digits each, then `C`/`X` for the carry flip-flop |
| `:` | Intel-hex load | `hexload` (2026-09-23): the rest of the record is read without echo and stored; `.` good, `?` bad digit or checksum, `!` address outside $1000-$DFFF or read back wrong; records up to the end record (`LOADED` / `LOADED WITH ERRORS`); ESC or NUL abandons anywhere; CR/LF at the prompt afterwards do nothing (`LOADMODE`); error flag `lderr` at $0F01. Host side `tools/monload.py`; about 39 instructions per received character |
| `O` | boot | `boot` ($F473): boot Y1/OS from the CompactFlash card (section 6) |
| `V` | video | `cmd_video` ($F6E9, 2026-09-25): the video unit, a second letter picks the subcommand (section 11); `V?` lists them |
| `Y` | BASIC test | `cmd_basic_test`: `JSR basic_test` ($E030) |
| `Z` | run | `cmd_basic`: `JSR basic_run` ($E010) — run the BASIC program in the buffer |
| CR / LF | continue | `continue`: according to `monmode` (BLOCKMODE 3, DUMPMODE 2, EXAMINEMODE 1, FILLMODE 4) repeats the last B/D/E/F from `continue_addr`; NOMODE just re-prompts. The loop accepts both $0D and $0A because the hardware sends CR and the emulator's terminal sends LF |

Addresses are typed as exactly four hex digits with no space (`getaddress` reads four nibbles through `uartin`,
each echoed); lower-case hex is accepted (`getnibble` → `toupper`). There is no line editing.

## 4. The BIOS vectors ($FFC0, `org 0ffc0h`)

Sixteen entries of 4 bytes, each `JSR routine / RET`, so a caller uses `JSR $FFxx` and the entry address never
moves when the monitor is re-assembled. Conventions (`firmware/abi/README.md`): a pointer travels in **R7**, a byte
in **ACC**; a routine may clobber R5, R6, TMP and, unless stated, R7. The first eleven date from 2020/21 (BASIC calls
them by these addresses: `basic.asm` lines 4–14), four were added 2026-09-22 and the last one 2026-09-23 (`firmware/abi/README.md`
lists all sixteen).

| Vector | Name | In | Out / effect | Body |
|---|---|---|---|---|
| $FFC0 | STRINGOUT | R7 → NUL-terminated string | prints it; R7 left at the NUL | `stringout` $F668: `LDAVR R7 / BRZ / JSR uartout / INCR R7` |
| $FFC4 | CHAROUT | ACC = byte | to the console; with `VIDMIR` set (and `VIDPRES`) also to the screen (2026-09-25) | `charout` = `uartout` $F9E0 |
| $FFC8 | UARTOUT | ACC | same routine (BASIC prints through it, so it mirrors too) | |
| $FFCC | SHOWADDR | R7 = word | prints `HHHH: ` | `showaddr` |
| $FFD0 | TOUPPER | ACC | ACC upper-cased (`LDTI 'Z' / BRGT lower / SUBI 20h`) | `toupper` |
| $FFD4 | SHOWR7 | R7 | prints four hex digits, no suffix | `showr7` (= `shownum`) |
| $FFD8 | SHOWBYTE | R7 → byte | prints two hex digits of [R7] | `showbyte` |
| $FFDC | SHOWREGS | | prints R0..R7 and the carry | `showregs` $F59C |
| $FFE0 | SHOWBYTEA | ACC | prints ACC as two hex digits (ACC preserved) | `showbytea` |
| $FFE4 | SHOWCARRY | | prints `C` or `X` | `showcarry` $F634 |
| $FFE8 | UARTIN | | ACC = next console byte; **waits, echoes it, CR becomes LF**, also shows it on the LEDs (`JSR LEDOUT`) | `uartin` $F68B |
| $FFEC | CFINIT | | ACC = 0 ok, 1 error (an absent card reads $FF and the bounded wait times out) | `cfinit` $F2AA |
| $FFF0 | CFREAD | CFLBA0..2 = sector, R7 → 512-byte buffer | the sector in the buffer, R7 += 512, ACC = 0 ok / 1 error | `cfread` $F2DA |
| $FFF4 | CFWRITE | CFLBA0..2, R7 → buffer | the buffer written, R7 += 512, ACC = 0 ok / 1 (the ERR bit) | `cfwrite` $F303 |
| $FFF8 | CONST | | ACC = 1 when a console byte is waiting (on the interpreter always 1) | `const` $F32C |
| $FFFC | UARTINNE | | ACC = next console byte **without echo** (waits; CR becomes LF; no LED); port 2 on the interpreter | `uartinne` (2026-09-23) |

Below the table, not a vector but at a fixed address like one (2026-09-25; the table is full): **$FFBC VIDCTL**,
`JSR vidctl / RET` — ACC = 0 probe, 1 init, 2 clear; ACC comes back = `VIDPRES` (section 11). An older ROM has $FF
there, so a caller checks for the $04 (`JSR`) first.

The CF routines clobber R6 and TMP. `uartout` and `uartin` are the two `BRDEV` switches: `BRDEV emulator2 / outa
p2 / ret` — on the interpreter (where `BRDEV` never branches) the console is port 2; on the machine and on ucemu the
code after the label polls the 16550: `OUTI P0,(UARTCS!UARTA5) / INP P1 / ANDI 40h` (LSR bit 6, transmitter empty)
before `OUTI P0,UARTCS / OUTA P1`; `uartin` polls LSR bit 0 (data ready) then reads `INP P1`. `const` polls the same
bit without waiting; `uartinne` is `uartin` without the `LEDOUT`/`uartout` echo. With sixteen vectors the table
ends at `$FFFF`; the `ZZZZ: DB 0` end byte that sat at `$FFFC` in the 2026-09-22 build is gone (`firmware/rom/README.md`).

The monitor's own helpers, not vectored but at known addresses in this build (`monitor.lst`): `getaddress` $F889
(four hex digits into R7), `getbyte` $F894 (two, into ACC), `getnibble` $F8AA, `show16`, `show256` $F96D,
`shownibble`, `ledout` $F9CE (LEDs ← ACC), `uartin` $FA08, `blink` $FA3E, `lblink` $FA53, the strings from `hello`
$FA68, `helpmenu` $FB12; the video driver from `vidreset` $F50F to `vcrtab` $F879 (section 11). `switchin`,
`TIL311out`, `LONGDELAY`, `SHORTDELAY`, `switchtoggle` and `nblink` (never called) and the T-menu's help strings were
removed 2026-09-25 for room (git history has them). Addresses in this document are from the current `monitor.lst`
(the `ROM 2026-09-25` build); they move whenever the monitor is rebuilt, so programs use the vectors.

## 5. The variables page ($0F00) and the stack

`monitor.asm` equates (all in the low 62256):

| Address | Name | Use |
|---|---|---|
| $0F00 | `monmode` | which command CR continues (0 none, 1 examine, 2 dump, 3 block, 4 fill) |
| $0F02 | `continue_addr` | the next address for B/D/E/F |
| $0F04 | `interupt_cnt` | how many blinks the ISR does (5) |
| $0F06–$0F0B | (`SYSARG0..2`) | not the monitor's: Y1/OS's three syscall argument words (`os/lib_abi.c`, `y1cc.py`), in the page's free space |
| $0F0C | (`SYSRES`) | the syscall result word (idem) |
| $0F10–$0F12 | `CFLBA0..2` | the 24-bit sector number for CFREAD/CFWRITE, **low byte first** |
| $0F14–$0F3F | (`SYSTAB`) | the OS's 22-entry syscall jump table, big-endian words, filled by Y1/OS at boot (idem) |
| $0F40–$0F7F | `ARGBUF` | 64 bytes to the monitor: the command tail Y1/OS leaves for a program, NUL-terminated (`y1cc` `argstr()`). The OS uses 128 (`ARGMAX` 127 + NUL, `$0F40–$0FBF`), overlaying `line_buffer`, which is idle while the OS runs |
| $0F80–$0FEF | `line_buffer` | the monitor's line buffer (`P` command): 112 bytes since 2026-09-25 (was 128; nothing checks the length) |
| $0FF0 | `VIDPRES` | 1 = the video card answered at $D000 at reset (or the last `V P` / VIDCTL 0) (2026-09-25) |
| $0FF1 | `VIDMIR` | nonzero = CHAROUT/UARTOUT also write to the screen (acts only while `VIDPRES` is 1); 0 at reset |
| $0FF2 | `VIDCUR` | nonzero = the driver keeps the CRTC's cursor registers R14/R15 at the text cursor (set by `V I`) |
| $0FF3 / $0FF4 | `VROW` / `VCOL` | the text cursor, row 0..23, column 0..79 |
| $0FF5 | `VCHAR` | the driver's scratch byte |
| $0FF6–$0FF7 | `VLINE` | the address of the cursor row's first byte (big-endian, `LDR`/`STR`) |
| $0EFF downward | `STACK` | R1 at reset; `$0C00` is the informal floor, nothing checks |

Below the page: BASIC's variables at $0100–$02FF, its line and token-line buffers at $0300/$0400, and the token
buffer at $1000–$1FFF, which the `O` command reuses as the OS load address ([MEMORY-MAP.md](MEMORY-MAP.md)).

## 6. The CompactFlash driver and the `O` command (2026-09-22)

The card sits on two ports (`docs/system/OS-PLAN.md` decision 1): **P8** = a write-only register-select latch (ATA
task-file register 0–7 in bits 0–2), **P9** = the data port; reading or writing P9 strobes the selected register. The
hardware is not built: the CF card v1.0 circuit, planned onto the memory card ([`docs/cards/cf.md`](../cards/cf.md)).
8-bit True IDE mode. Register numbers (`CFSEL_*` equates): 0 data, 1 error/feature, 2 sector count, 3–5 LBA0–2,
6 drive/head, 7 status/command.

- `cfwait` — polls status until BSY (bit 7) clears, bounded to 65,536 polls (`MVIW R6,0 / DECR R6` until both bytes
  are zero); returns the status in ACC. `cfdrq` — the same until DRQ (bit 3) is set.
- `cfinit` — `cfwait`; drive/head ← $E0 (LBA mode, drive 0); feature ← 1 and command ← $EF (SET FEATURES: 8-bit
  transfers); `cfwait`; ACC ← status AND 1 (the ERR bit). An absent card reads $FF everywhere, so the wait times out
  and the result is 1.
- `cfsetl` — task file ← `CFLBA0..2`, drive/head $E0, sector count 1.
- `cfread` — `cfwait`, `cfsetl`, command $20 (READ SECTORS), `cfdrq`; if DRQ is not set → `cferr` (ACC = 1); else
  select the data register once and loop 512 times `INP P9 / STAVR R7 / INCR R7` (R6 counts down). ACC = 0.
- `cfwrite` — the same with command $30 and `LDAVR R7 / OUTA P9`, then `cfwait` and ACC ← ERR.
- `const` — `BRDEV consthw / LDAI 1 / RET`; on hardware LSR bit 0.

The **`O` command** (`boot:` $F473) prints `BOOT FROM CF`, `cfinit` (error → `CF ERROR`), reads LBA 0 to
`OSBASE` = $1000, checks bytes 0–1 = `P8` and byte 3 = OSCNT ≠ 0 (else `NO OS ON THE CARD`), then reads LBA 1..OSCNT
to $1000 onward (R7 advancing 512 per sector, `CFLBA0` incremented — so OSCNT ≤ 255 and the OS ≤ 32 sectors by the
P8XFS rule), `MVIW R7,OSBASE`, **`JSRUR R7`**, `BR cmdloop`. The OS returns with `RET`. Both emulators model the card
with `-c disk.img` (`software/cfmodel.h`); the hardware is not built.

## 7. BASIC in ROM ($E000–$EFFF)

`firmware/basic/basic.asm` is the hand-assembled port of Adam Dunkels' uBASIC (`software/ubasic-c/` is the C
original) as burned in 2021 (git ff7d85a). It occupies $E000–$EFFF with a jump table of entry points at 16-byte
spacing, which the monitor calls (`monitor.asm` equates):

| Entry | Name | Used by |
|---|---|---|
| $E000 | `basic_list` | `L` |
| $E010 | `basic_run` | `Z` |
| $E020 | `basic_cold` | the monitor's boot (initialises the interpreter) |
| $E030 | `basic_test` | `Y` |
| $E040 | `basic_interprter` | `I` |
| $E050 | `basic_parse` | `P` (one line from `line_buffer`) |
| $E060 | `basic_copy` | `C` (the built-in test program into the buffer) |

BASIC's RAM: 26 one-byte variables at `BASIC_VARS` $0100 (256-byte aligned), internal state at $0200–$02FF
(text/token pointers, the FOR-NEXT stack at $0280, the GOSUB stack at $02C0), `parse_input_line` $0300,
`parse_token_buffer` $0400, the token buffer $1000–$1FFF (`bas_tok_buf_start`/`_end`). Tokens include LET PRINT IF
THEN ELSE FOR TO NEXT GOTO GOSUB RETURN CALL REM PEEK POKE END LIST RUN NEW EXIT INPUT INP OUTP (`basic.asm` lines
19–62). It calls the monitor only through the BIOS vectors. `tests/basic/test` is a small program for it. The OS plan
moves BASIC out of the ROM into `/bin/basic` later (`docs/system/OS-PLAN.md`); `firmware/basic/candidates/` holds
never-burned later versions (ON/OFF statements, break-in). **To verify:** the exact `P`-line syntax and the meaning
of `Y`'s test program are not documented outside `basic.asm`; running `C` then `L` on the emulator would show the
built-in program.

## 8. The interrupt service routine ($FF90)

`org 0ff90h / isrcode:` — `PUSH`, `PUSHR R7`, `LDA interupt_cnt`, blink the LED that many times (`JSR BLINK / SUBI 1
/ BRNZ`), `POPR R7`, `POP`, `IRET`. Installed at boot by `iaddr isrcode` and `INTE`. **To verify:** nothing in the tree
raises an interrupt (no source on the bus in the emulators' models, `software/ucemu/README.md`; `-INTA` never
asserted, `docs/isa/MICROCODE-REVIEW-NOTES.md` L-8), so the ISR path has not been exercised from this tree.

## 9. The ROM build and its proofs

- **Assemble**: in `software/assembler` `make check` assembles `firmware/monitor/monitor.asm` and
  `firmware/basic/basic.asm` in `build/` (each with `yacc1.def` and the `-l -x -h` `rcasm.rc`) and diffs the `.img`
  files against the committed ones; `make install` copies a deliberate rebuild into `firmware/`.
- **`makerom`** (`firmware/rom/makerom`): `awk` drops the last line of `basic.img` (its end-of-file record), then
  `cat basic.img-without-EOF monitor.img > rom`. `rom` is therefore one Intel-hex file: BASIC at $E000 followed by the
  monitor at $F000. (The script's assembler path is the old NetBeans one; the Makefile and `verify_firmware.py`
  reproduce its two shell lines.)
- **`shipped/rom.bin`** = the same as a flat 8,192-byte file for the programmer: `python3 tools/img2bin.py
  firmware/rom/shipped/rom firmware/rom/shipped/rom.bin --base 0xE000 --end 0x10000 --fill 0xFF --size 8192`. Offset
  0 = $E000; bytes the sources never write are $FF like a blank part; MD5 in `firmware/rom/README.md`. Device: 28C64, Visual Minipro / `minipro`.
- **Telling builds apart**: the banner ends `ROM 2026-09-25` on the tree's build (not burned; MD5 in
  `firmware/rom/README.md`; $FFBC holds $04, the video entry) and `ROM 2026-09-23` on the chip (MD5
  d2d7b027e7c6951d7dd93412a8fd9cd8, CF on P8/P9; $FF at $FFBC); the 2021 chip
  prints the banner alone and has `00` at $FFEC; the 2026-09-22 build has `04` at $FFEC and `00` at $FFFC. Vector targets
  move with every monitor edit, so compare whole images by MD5.
- **`tools/verify_firmware.py`** rebuilds everything from source in a scratch directory — the assembler from its C
  sources, both images, `rom` via the `makerom` lines, and the microcode `test.hex` via the generator — and diffs
  against the committed files: `FIRMWARE VERIFIED` or exit 1. Part of `make check` at the root.
- **Chip captures**: `tests/memory/rom_verify.py` (~30 s) reads every ROM byte through the bus tester and compares
  with `tools/romimage.py`'s image (basic.img + monitor.img, gaps $FF); `memory_status.py` also checks the boot
  remap and the block map. After burning `shipped/rom`, re-capture and compare.
- `firmware/rom/builds/2021-09-02-3bcacf3-not-working/rom` is a never-burned git-HEAD build; `firmware/monitor/
  candidates/` and `monnew-2025/` hold other never-burned monitors (`BACKLOG.md`: 8afde21 adds a `charavail`
  vector at $FFEC — note the same address the new CFINIT now uses; the two are not compatible).

## 10. Running the monitor on the emulators

`software/emulator/emulator` with no arguments (or `-m`) loads `basic.img` + `monitor.img` found relative to the
executable and starts at $F000 in raw-tty mode; `software/ucemu/y1ucemu -m` does the same from a real reset. Type `H`
at the `>` prompt. The interpreter's input needs LF after a command (the CR/LF handling in `cmdloop`); ucemu shows the
echo the machine produces. Under the interpreter the `0` command exits; under ucemu it loops.

## 11. The video unit (2026-09-25)

The video card ([`docs/cards/video.md`](../cards/video.md): an MC6845 CRTC and an IDT7134 dual-port RAM in the $D000
block) is in the machine for bring-up without its 6845. The ROM carries the whole driver; **it does not start the
card by itself** until the card is debugged (`VIDAUTO EQU 0`). All of it is plain 2021-set code: no `LDZ`/`STZ`/
`ADDIW`/`SHL16`, no `BRUR`, no R2, so it runs on the sequencer EEPROM's current image and on the 2026-09-24 one.

**Equates** (one edit each, top of `monitor.asm`): `VIDAUTO` 0, `VIDRAM` $D000, `VIDSIZE` 2048, `VCOLS` 80, `VROWS` 24,
`VCRTCA` $D800 (6845 address register) and `VCRTCD` $D802 (data register). The CRTC addresses follow the netlist
reading of the card (ADDR11 selects the CRTC half, A1 the register after the RS-to-A1 bench fix); the card's README
and the fix document say $D400/$D402 — `docs/cards/video.md` section 4 has the check that settles it (`hold_address.py`
on $D400 and $D800). Geometry: the 2K the CPU reaches holds 80 x 24 = 1,920 characters, one byte each; the card
latches bits 0-5 (a 64-glyph character EPROM) and bit 7 (inverse); the driver stores ASCII with lower case moved up
($60-$7F → $40-$5F), which a 2513-style character set (code = ASCII bits 0-5) shows as sent. **Assumed**, not read from
the card: the character EPROM's contents (nothing in the tree) and the dot clock (the crystal has no value in the
design); if the EPROM is ordered differently, the text shows scrambled but the driver is unchanged. `VCOLS*(VROWS-1)`
must be a multiple of 8 (the scroll moves 8 bytes a pass): 64 x 16 is the other layout that works as is.

**Detection** (`vprobe`, at reset and by `V P`): the byte at $D000 is saved, $55 written and read back, then $AA,
and the old byte put back; `VIDPRES` = 1 only when both came back. An undecoded block reads whatever was last on the
bus, and between each `STA $D000` and its `LDA $D000` the `LDA`'s own opcode and operand bytes ($E4 $D0 $00) cross
the bus, so a floating bus reads $00, never the pattern. The banner then says `VIDEO CARD FOUND`.

**The driver** (`vputc`, entered from CHAROUT): CR → column 0; LF → column 0 of the next row (Y1/OS ends lines with LF
alone, the monitor sends LF CR: both come out right); BS → one column left, nothing erased; TAB → spaces to the next
multiple of 8; FF → clear + home; other control bytes and DEL are ignored; a character in column 79 wraps; LF on row 23
scrolls (rows 1-23 move up, 8 bytes a pass, row 23 blanked). With `VIDCUR` set every character also writes the
cursor's offset from $D000 into the CRTC's R14/R15. It keeps R3-R7 and TMP (Y1/OS relies on CHAROUT keeping every
register, ACC and TMP); R2 changes as in every `LDA`; the carry is not kept (the monitor's own `SHR`s change it on
the machine anyway).

**Cost**: with mirroring off CHAROUT does `PUSH / LDA VIDMIR / BRZ / POP` more than before (71 microcode steps a
byte); the UART path is unchanged. With mirroring on a character costs about 650 steps more (measured on ucemu: the
help text 884K steps plain, 1,625K mirrored), a scroll about 90K steps; at the machine's clock that is several
times slower console output, which is why mirroring is off unless asked for.

**Mirroring** is `VIDMIR`: `V M1`/`V M0` in the monitor, `video on`/`off` in Y1/OS (`os/man/video`), or a program
writing $0FF1. CHAROUT and UARTOUT are the same routine, so the monitor, BASIC (which prints through UARTOUT), Y1/OS
and every program show on the screen; what goes to a `>` file or a pipe is not console output.

**The V command** — `V` then a letter (blanks skipped), numbers in hex with optional blanks between them. An error
prints ` ?` after dropping the rest of the line (a stray `0` would otherwise stop the machine at `stop:`).

| Command | Effect |
|---|---|
| `V?` (or any other letter) | the two-line list of these commands |
| `VS` | status: `VIDEO 01  MIRROR 00  CRTC 00  ROW 00  COL 00` — `VIDPRES`, `VIDMIR`, `VIDCUR`, `VROW`, `VCOL` |
| `VP` | probe $D000 again, then the status |
| `VI` | init: the 16 CRTC registers from `vcrtab`, `VIDCUR` on, clear, home; then the status |
| `VC` | clear (every byte of the 2K a space), cursor home |
| `VM1` / `VM0` | mirroring on / off; then the status |
| `VW rr cc text` | the text (upper-cased) at row rr, column cc — hex, rows 00-17, columns 00-4F; one blank after cc separates; runs to CR, on into the next rows, never past the 2K; the text cursor does not move |
| `VB aaaa bb bb ..` | bytes stored from aaaa (must be in $D000-$DFFF; stops with ` ?` at the block's end); the raw way to write glyph codes, attributes or the CRTC ($D800 even = address register, $D802 = data). **An odd address in $D800-$DFFF is the JP1 latch, which drives the bus even on a write: don't** |
| `VF bb` | fill all 2K with bb (a RAM test by eye: `VF55` then `VD`) |
| `VD` | the screen as text over the console: 24 lines, each its hex row number and 80 characters, each byte shown as its glyph would be under the 2513 assumption (bits 0-5: 00-1F = `@`..`_`, 20-3F = blank..`?`); mirroring is paused meanwhile. `B D000` shows the bytes in hex |
| `VR rr [vv]` | CRTC register rr ← vv; with no vv, select rr and read the data register (a 6845 reads back R12-R17 only) |

**The CRTC table** (`vcrtab`, R0-R15): 126, 80, 98, 10, 31, 6, 24, 28, 0, 7, $67, 7, 0, 0, 0, 0 — assumes a 10 MHz
dot clock, 5 dots a character (the card's 74HC160 divides by 5) and 8 scan lines a row: 127 characters = 63.5 µs a
line (15.7 kHz), 32 rows + 6 lines = 262 lines (60 Hz), non-interlaced, a blinking underline cursor. R1/R6 come from
`VCOLS`/`VROWS`; re-derive R0/R2/R3/R4/R5/R7 when the crystal is known (`VR` tries values by hand first).

**Turning auto-start on** once the card works: `VIDAUTO EQU 1` in `monitor.asm`, rebuild the ROM (`software/assembler`
`make check`, copy the images, `makerom`, `img2bin.py`, `tools/verify_firmware.py`), burn. Reset then also runs `V I`
and sets `VIDMIR` when the card is found, so the banner is on the screen too.

**Y1/OS**: `/BIN/VIDEO` (`os/commands/video.c`): `video` (status), `video on|off|clear|init|probe`. It reads and writes
the flags and calls `VIDCTL` ($FFBC); on an older ROM it says so and changes nothing. The kernels need nothing: their
console output is CHAROUT.

**Emulators** (`software/videomodel.h`, both): the display RAM is RAM at $D000-$D7FF as before, the 6845 is modelled at
$D800/$D802 (R12-R17 read back), odd addresses read the latch as $FF; `-V` prints the screen and the CRTC registers on
stderr at the end, `-W` logs CRTC writes, `-N` removes the card ($D000-$DFFF reads $FF, writes are lost).
`tests/video/emu.py` runs the monitor and Y1/OS on both ([EMULATORS.md](EMULATORS.md)).

**Bring-up on the real card** (no 6845 yet): `VS` (the banner already said whether $D000 answered); `VF55` then `VD`
(every character `U`), `VFAA` / `VD` (`*`); `VC`, `VW0000 HELLO`, `VD`; `B D000` for the bytes; `VM1`, type, `VD`
shows the console. After fitting the 6845 with the RS-to-A1 fix: `VR0C 12` then `VR0C` must read back `12` (R12, a
readable register); `VI`, then a picture; adjust timing with `VR`. Details in [`docs/cards/video.md`](../cards/video.md)
section 8.
