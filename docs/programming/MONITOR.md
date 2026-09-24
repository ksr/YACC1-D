# The ROM monitor and BIOS

The program in the YACC1's 28C64: what it does at reset, every command, the BIOS vectors and their conventions, the
variables page, the CompactFlash driver and the `O` boot, BASIC's place in the ROM, the interrupt service routine,
and how the ROM image is built and verified. Written 2026-09-23 from the YACC1-D tree.

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
- **In the tree** (`firmware/rom/shipped/rom`, to burn): the 2026-09-22 rebuild of `monitor.asm` — the `G` command
  fixed (`JSRUR R7` instead of `BRVR R7`), the T-menu bench tests removed (1,062 bytes), the CompactFlash driver, the
  `O` boot command, four new BIOS vectors and two new variable areas — plus, on 2026-09-23, `uartinne` (console
  input without echo) and its vector at `$FFFC`, the sixteenth and last slot, the `:` Intel-hex loader and the build
  date in the banner. BASIC is unchanged. Object code 2,979 bytes, 0 errors, 193 labels, 1,366 source lines
  (`monitor.lst` of 2026-09-23 09:36, before the loader). **2026-09-23 evening: `ROM 2026-09-23B`**, the CF driver
  and `O` moved from P8/P9 to P4/P5 (the CF interface is going onto the I/O card v2.0), nothing else changed; not
  yet burned (`firmware/rom/README.md`).

Until 2026-09-23B is burned, `tests/memory/rom_verify.py` and `memory_status.py` report the monitor half as different
(the burned 2026-09-23 build differs from 2026-09-23B in the CF port operands, the banner and the strings it shifts),
and `O` on the machine talks to P8/P9.

## 2. Reset and boot sequence (`monitor.asm` `eprom:`, $F003)

1. `$F000: BR eprom` — the first fetch happens under the memory card's FORCE-ROM remap (the ROM answers at every
   address after reset); the branch target $F003 has A15 high, which ends the remap.
2. `MVIW R1,STACK` — the stack pointer to `$0EFF`.
3. UART set-up through P0/P1: LCR ← $80 (DLAB), DLL ← 3 (**38400 baud**; the commented alternative `12` was 9600),
   DLM ← 0, LCR ← 3 (8 bits, no parity, 1 stop). Register offsets `UARTA0..A7` = 0, 8, … $38 OR `UARTCS` $40
   ([IO-PORTS.md](IO-PORTS.md)).
4. `monmode` ← `NOMODE` (0), `interupt_cnt` ← 5.
5. `JSR lblink` (a long LED blink), the banner `hello` → `YACC 2020: HELLO WORLD` (upper-cased by the assembler, see
   [ASSEMBLER.md](ASSEMBLER.md) quirk 1), `JSR basic_cold` (initialise the BASIC interpreter: it clears the token
   buffer at $1000).
6. Proof of life: `showaddr`/`show16` of the first 16 ROM bytes at $F000, `showregs`, then the address of `tttt`
   (the start-up test entry) printed as `F051:`.
7. `iaddr isrcode` / `INTE` — the interrupt vector is set to $FF90 and interrupts enabled.
8. `BRINH cmdloop` — **if the input-switch line is high the monitor goes straight to its prompt**; otherwise it
   falls into `tttt:`, prints `Run test code` (the tests themselves are gone) and branches to `cmdloop` anyway.

The emulators reproduce this: the interpreter starts at PC = $F000 with the images loaded (`main.c`); ucemu starts
from a real reset with FORCE-ROM set (`software/ucemu/README.md`).

## 3. The command loop and the commands (`cmdloop:` $F05B)

The prompt is `>`. The loop reads one byte with `uartin` (which echoes it), upper-cases it and dispatches by
comparing against a list of `LDTI 'x' / BREQ` pairs (`testexamine:`). Anything else prints `UNRECOGINIZED COMMAND`
and the help. A bare CR/LF is `continue` (below). The `H` text is the command reference; each command explained
from its code:

| Key | Command | What it does (`monitor.asm` label) |
|---|---|---|
| `H` | help | prints `helpmenu` ($F694) |
| `0` | exit | `cmd_exit`: `BRDEV stop` — on the machine it loops forever at `stop:` (`BRDEV` branches); on the interpreter it falls into a `DB 0` = opcode $00 = `START`, which the interpreter reports as a bad opcode and exits. "Exit (emulator only)" |
| `B AAAA` | dump block | `dumpblock`: mode ← BLOCKMODE, reads 4 hex digits into R7 (`getaddress`), prints 256 bytes from the 16-byte-aligned address (`show256`), saves the next address in `continue_addr`; CR shows the next 256 |
| `C` | copy | `cmd_basic_copy`: `JSR basic_copy` ($E060) — copies BASIC's built-in test program into the interpreter buffer |
| `D AAAA` | dump | `dump`: 16 bytes at the address (`showaddr` + `show16`); CR shows the next 16 |
| `E AAAA` | examine / modify | `examine`: prints `AAAA: XX` and waits. Two hex digits replace the byte and advance (the value is read with `getnibblec`/`getnibble`, assembled with `SHL`×4 / `PUSH` / `MVAT` / `POP` / `ORT`, stored with `STAVR R7`); CR or LF advances without change; Esc ($1B) or `-` ends. This is the only way to put bytes into RAM from the console (`BACKLOG.md`'s planned `tools/monload.py` drives it) |
| `F AAAA` | fill | `fillblock`: writes 0 into 256 bytes from the address (`morefill`: `LDAI 0 / STAVR R7 / INCR R7` until the low byte wraps); CR fills the next 256 |
| `G AAAA` | go | `go` ($F25C): prints `GO ADDRESS:`, reads the address into R7, **`JSRUR R7`** (a call), then `BR cmdloop`: the program ends with `RET` and lands back at the prompt. History: until 2026-09-22 it was `BRVR R7`, an indirect jump through the word at AAAA that pushed no return, so `G AAAA` never ran the code at AAAA (the microcode's `branch()` fetches the target through the register). Compiled images for the old chip start with a 2-byte vector (`y1cc --vector`) |
| `I` | BASIC | `interpreter`: `JSR BASIC_INTERPRTER` ($E040) |
| `L` | list | `cmd_basiclist`: `JSR basic_list` ($E000) |
| `P` | parse | `cmd_basicparse`: prints `Enter Line:`, reads a line into `line_buffer` ($0F80) until LF, shows it, `JSR BASIC_PARSE` ($E050) — enters one program line into BASIC's token buffer |
| `R` | registers | `dumpreg`: `showregs` — R0..R7 as four hex digits each, then `C`/`X` for the carry flip-flop |
| `:` | Intel-hex load | `hexload` (2026-09-23): the rest of the record is read without echo and stored; `.` good, `?` bad digit or checksum, `!` address outside $1000-$DFFF or read back wrong; records up to the end record (`LOADED` / `LOADED WITH ERRORS`); ESC or NUL abandons anywhere; CR/LF at the prompt afterwards do nothing (`LOADMODE`); error flag `lderr` at $0F01. Host side `tools/monload.py`; about 39 instructions per received character |
| `O` | boot | `boot` ($F333): boot Y1/OS from the CompactFlash card (section 6) |
| `Y` | BASIC test | `cmd_basic_test`: `JSR basic_test` ($E030) |
| `Z` | run | `cmd_basic`: `JSR basic_run` ($E010) — run the BASIC program in the buffer |
| CR / LF | continue | `continue`: according to `monmode` (BLOCKMODE 3, DUMPMODE 2, EXAMINEMODE 1, FILLMODE 4) repeats the last B/D/E/F from `continue_addr`; NOMODE just re-prompts. The loop accepts both $0D and $0A because the hardware sends CR and the emulator's terminal sends LF |

Addresses are typed as exactly four hex digits with no space (`getaddress` reads four nibbles through `uartin`,
each echoed); lower-case hex is accepted (`getnibble` → `toupper`). There is no line editing.

## 4. The BIOS vectors ($FFC0, `org 0ffc0h`)

Sixteen entries of 4 bytes, each `JSR routine / RET`, so a caller uses `JSR $FFxx` and the entry address never
moves when the monitor is re-assembled. Conventions (`firmware/abi/README.md`): a pointer travels in **R7**, a byte
in **ACC**; a routine may clobber R5, R6, TMP and, unless stated, R7. The first eleven date from 2020/21 (BASIC calls
them by these addresses: `basic.asm` lines 4–14), four were added 2026-09-22 and the last one 2026-09-23 (it is not
yet in `firmware/abi/README.md`, whose file date is 2026-09-22).

| Vector | Name | In | Out / effect | Body |
|---|---|---|---|---|
| $FFC0 | STRINGOUT | R7 → NUL-terminated string | prints it; R7 left at the NUL | `stringout` $F528: `LDAVR R7 / BRZ / JSR uartout / INCR R7` |
| $FFC4 | CHAROUT | ACC = byte | to the console | `charout` = `uartout` $F536 |
| $FFC8 | UARTOUT | ACC | same routine | |
| $FFCC | SHOWADDR | R7 = word | prints `HHHH: ` | `showaddr` |
| $FFD0 | TOUPPER | ACC | ACC upper-cased (`LDTI 'Z' / BRGT lower / SUBI 20h`) | `toupper` |
| $FFD4 | SHOWR7 | R7 | prints four hex digits, no suffix | `showr7` (= `shownum`) |
| $FFD8 | SHOWBYTE | R7 → byte | prints two hex digits of [R7] | `showbyte` |
| $FFDC | SHOWREGS | | prints R0..R7 and the carry | `showregs` $F45C |
| $FFE0 | SHOWBYTEA | ACC | prints ACC as two hex digits (ACC preserved) | `showbytea` |
| $FFE4 | SHOWCARRY | | prints `C` or `X` | `showcarry` $F4F4 |
| $FFE8 | UARTIN | | ACC = next console byte; **waits, echoes it, CR becomes LF**, also shows it on the LEDs (`JSR LEDOUT`) | `uartin` $F54B |
| $FFEC | CFINIT | | ACC = 0 ok, 1 error (an absent card reads $FF and the bounded wait times out) | `cfinit` $F2A5 |
| $FFF0 | CFREAD | CFLBA0..2 = sector, R7 → 512-byte buffer | the sector in the buffer, R7 += 512, ACC = 0 ok / 1 error | `cfread` $F2D5 |
| $FFF4 | CFWRITE | CFLBA0..2, R7 → buffer | the buffer written, R7 += 512, ACC = 0 ok / 1 (the ERR bit) | `cfwrite` $F2FE |
| $FFF8 | CONST | | ACC = 1 when a console byte is waiting (on the interpreter always 1) | `const` $F327 |
| $FFFC | UARTINNE | | ACC = next console byte **without echo** (waits; CR becomes LF; no LED); port 2 on the interpreter | `uartinne` (2026-09-23) |

The CF routines clobber R6 and TMP. `uartout` and `uartin` are the two `BRDEV` switches: `BRDEV emulator2 / outa
p2 / ret` — on the interpreter (where `BRDEV` never branches) the console is port 2; on the machine and on ucemu the
code after the label polls the 16550: `OUTI P0,(UARTCS!UARTA5) / INP P1 / ANDI 40h` (LSR bit 6, transmitter empty)
before `OUTI P0,UARTCS / OUTA P1`; `uartin` polls LSR bit 0 (data ready) then reads `INP P1`. `const` polls the same
bit without waiting; `uartinne` is `uartin` without the `LEDOUT`/`uartout` echo. With sixteen vectors the table
ends at `$FFFF`; the `ZZZZ: DB 0` end byte that sat at `$FFFC` in the 2026-09-22 build is gone (`firmware/rom/README.md`
still mentions it: its file date is 2026-09-22).

The monitor's own helpers, not vectored but at known addresses in this build (`monitor.lst`): `getaddress` $F3CF
(four hex digits into R7), `getnibble` $F3F8, `show16`, `show256` $F4BB, `shownibble`, `switchin` $F51C (ACC ←
switches), `ledout` $F520 (LEDs ← ACC), `TIL311out` $F524, `uartin` $F54B, `LONGDELAY` $F581, `SHORTDELAY` $F58C,
`switchtoggle` $F597, `blink` $F5B2, `lblink` $F5C7, `nblink` $F5DC, the strings from `hello` to `PROMPT` $F60A,
`helpmenu` $F6AC. They move when the monitor is rebuilt (everything after `uartin` moved by $18 on 2026-09-23);
use the vectors.

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
| $0F80–$0FFF | `line_buffer` | the monitor's 128-byte line buffer (`P` command) |
| $0EFF downward | `STACK` | R1 at reset; `$0C00` is the informal floor, nothing checks |

Below the page: BASIC's variables at $0100–$02FF, its line and token-line buffers at $0300/$0400, and the token
buffer at $1000–$1FFF, which the `O` command reuses as the OS load address ([MEMORY-MAP.md](MEMORY-MAP.md)).

## 6. The CompactFlash driver and the `O` command (2026-09-22)

The card sits on two ports (`docs/system/OS-PLAN.md` decision 1 and its 2026-09-23 update): **P4** = a write-only
register-select latch (ATA task-file register 0–7 in bits 0–2), **P5** = the data port; reading or writing P5 strobes
the selected register. The hardware will be the I/O card v2.0 ([`docs/cards/cf.md`](../cards/cf.md)). P4/P5 from the
build `ROM 2026-09-23B` (not yet burned); the builds before it, including the chip in the machine, use P8/P9.
8-bit True IDE mode. Register numbers (`CFSEL_*` equates): 0 data, 1 error/feature, 2 sector count, 3–5 LBA0–2,
6 drive/head, 7 status/command.

- `cfwait` — polls status until BSY (bit 7) clears, bounded to 65,536 polls (`MVIW R6,0 / DECR R6` until both bytes
  are zero); returns the status in ACC. `cfdrq` — the same until DRQ (bit 3) is set.
- `cfinit` — `cfwait`; drive/head ← $E0 (LBA mode, drive 0); feature ← 1 and command ← $EF (SET FEATURES: 8-bit
  transfers); `cfwait`; ACC ← status AND 1 (the ERR bit). An absent card reads $FF everywhere, so the wait times out
  and the result is 1.
- `cfsetl` — task file ← `CFLBA0..2`, drive/head $E0, sector count 1.
- `cfread` — `cfwait`, `cfsetl`, command $20 (READ SECTORS), `cfdrq`; if DRQ is not set → `cferr` (ACC = 1); else
  select the data register once and loop 512 times `INP P5 / STAVR R7 / INCR R7` (R6 counts down). ACC = 0.
- `cfwrite` — the same with command $30 and `LDAVR R7 / OUTA P5`, then `cfwait` and ACC ← ERR.
- `const` — `BRDEV consthw / LDAI 1 / RET`; on hardware LSR bit 0.

The **`O` command** (`boot:` $F333) prints `BOOT FROM CF`, `cfinit` (error → `CF ERROR`), reads LBA 0 to
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
- **Telling builds apart**: the banner ends `ROM 2026-09-23B` on the current tree build (MD5 a9fefd4ae21eb46eb21cff614376617f,
  CF on P4/P5, not yet burned) and `ROM 2026-09-23` on the chip in the machine (MD5 d2d7b027e7c6951d7dd93412a8fd9cd8, CF on P8/P9); the 2021 chip
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
