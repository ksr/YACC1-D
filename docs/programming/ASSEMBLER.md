# The YACC1 cross assembler (RC/asm, YACC1 port)

How to assemble YACC1 programs on the Mac with `software/assembler`, what it accepts, what it produces, and its
traps. Written 2026-09-23 from the YACC1-D tree.

Sources: `software/assembler/README.md`, `asm.txt` (Michael H. Riley's RC/asm 2.2 manual, the `.def` format and the
output formats), `asm.c` / `asmcmds.c` (option handling, the `.prg`/`.img` switch, the 2026-09-22 `DS` fix),
`yacc1.def` (the YACC1 instruction table), `Makefile`, `rcasm.rc`, `software/compiler/README.md` and
`software/compiler/y1cc.py` (the quirks the compiler had to work around), `tests/assembler/{ledcount,brur,romcount,
romdiag}/`, `tests/compiler/run.py`, `firmware/monitor/monitor.asm` (the largest source). Encodings quoted below
were checked with a scratch assembly on 2026-09-23.

## 1. What it is

RC/asm is a table-driven assembler: the program `asm` knows nothing about the YACC1; `yacc1.def` tells it, one
pattern per instruction, how a source line maps to bytes. The YACC1 port (2020-08 → 2021-07) changed the C sources
and added the table; `upstream/rcasm-2.2/` is the untouched original. Build it with `make` in `software/assembler`
(also built by the top-level `make`). `make check` there re-assembles the monitor and BASIC and diffs the images
against the committed ones (the burned ROM); this is the tree's proof that the assembler and the table still
reproduce what is in the machine.

## 2. Invocation

```
cd <a folder holding NAME.asm, yacc1.def and rcasm.rc>
../software/assembler/asm NAME -d=yacc1 > NAME.lst
```

- **The source name comes first, without `.asm`, and `-d=yacc1` after it.** The `-d` handler in `readOptions()`
  (`asm.c`) skips the argument that follows it, so `asm -d=yacc1 NAME` loses the file name (`firmware/README.md`,
  `Makefile`). `-d=yacc1` means "read `yacc1.def`"; it is looked for in the current directory and then in the
  compiled-in `DEF_DIR` (`asm.c` `Read_Def_File`).
- **`rcasm.rc`** in the current directory is read before the command line, one option per line (`asm.txt`). The
  tree's copy in `software/assembler/` holds `-l -x -h` (listing, cross-reference, Intel hex). Every test runner
  creates one with just `-h` (`tests/compiler/run.py`, `tests/assembler/romcount/run.py`, `os/Makefile`:
  `echo -h > rcasm.rc`).
- The listing (and the summary `N Lines assembled / N Errors / N Labels / Object Code:N bytes`) goes to **stdout**,
  so redirect it to `NAME.lst`. `tests/compiler/run.py` greps `Object Code:(\d+) bytes` and `^0 Errors` from it.
- Options (`asm.txt`, `asm.c`): `-h` Intel hex output; `-l` listing; `-s` symbols; `-x` cross-reference; `-t` no
  trailer; `-Sl`/`-Sa` sort the label reference by line/alphabetically; `-r` show the matching rule (debugging a
  `.def`); `-v` version; `-Dsym=val` define a preprocessor symbol; `-d name` the definition file.
- The assembler wants all three files in the working directory; the runners copy `yacc1.def` and the source into a
  scratch folder first (`tests/compiler/run.py` `run_one`, `tests/assembler/brur/README.md`).

## 3. Output files

With `-h` the object file is **`NAME.img`, Intel hex** (`asm.c`: `emucode='H'` → `.img`), the format both emulators
load (`emulator -f NAME.img`, `y1ucemu -f NAME.img`), that `tools/img2bin.py` flattens for the ROM programmer and
for `tools/p8xfs.py`, and that the compiler tests use. Example (`tests/assembler/romcount/romcount.img`):

```
:10f00000a0f003190eff0270019161708061a4f0fd
:10f0100007010b0c7001617080611b20005b2ba24b
:09f02000f01d0cb0010ba0f0136f
:00000001ff
```

Each record is `:` + byte count + address + type (`00` data, `01` end) + bytes + checksum; records hold up to 16
bytes and start a new line at every `ORG` and (since 2026-09-22) every `DS`.

Without `-h` the object file is **`NAME.prg`** in RC/asm's own text format (`asm.c`: `emucode='I'` → `.prg`):
`:AAAA b b b ...` lines and a `*AAAA` start-address line (`asm.txt` "Output file"; example
`tests/assembler/ledcount/ledcount.prg`: `:0000 0e 00 70 01 61 b0 01 a0 00 02` / `*0000`). `BACKLOG.md`'s planned
monitor loader reads that format. Nothing in the tree consumes `.obj`.

The **listing** (`-l`) is one line per source line: line number, address, the bytes, the source; then the label
table with `-x`. `firmware/monitor/monitor.lst` is the reference example (`f05b: cmdloop:` etc.).

## 4. Source syntax

- A line is `[label:] mnemonic [operands] [; comment]`. Labels end with `:`; the whole line is upper-cased before
  matching (see quirks), so `cmdloop`, `CMDLOOP` and `CmdLoop` are one label.
- Numbers: decimal (`512`), hex with a trailing `H` (`0EFFH`, `0F000H` — a leading digit is required, so `$F000`-style
  is not accepted and `0F000H` is the form), characters in single quotes (`'A'`). `0x` hex is not in the manual.
- Operands are matched literally against the `.def` patterns: `MVIW R1,0EFFH`, `OUTI P0,SWITCHLED`,
  `MOVRR R0,R7`, `LDIVR R3,5`. Register names are `R0`..`R7` (the class also lists `R8`/`R9`, which silently produce
  wrong opcodes — see the ISA reference), ports `P0`..`P9`,`PA`..`PF`.
- Expressions (`asm.txt`, precedence high to low): `.0`/`.1` (low/high byte), `* /`, `+ -`, `<< >>`, `&`, `| ^`.
  Parentheses group: `(label+4).0`. `HIGH expr` is a `DB` form (`DB HIGH \W` → the high byte). Checked 2026-09-23:
  `LDAI lab+4` → `0E 14` with `lab = 10H`; `LDAI lab*2` → `0E 20`; `DB (1234H).0` → `34`; `DB (1234H).1` → `12`;
  `DB HIGH 1234H` → `12`. `label+4.0` does not work (`software/assembler/README.md`); write `(label+4).0`.
  The monitor writes OR as `!`: `OUTI P0,(UARTA3!UARTCS)` assembles to `70 58` = $18 | $40 (`monitor.lst` line 77).
  `!` is a YACC1-port addition to the tokenizer (`support.c` line 188, comment `ken add | &`), not in `asm.txt`.
- Preprocessor: `#DEFINE symbol value`, `#UNDEF`, `#IFDEF`, `#IFNDEF`, `#ELSE`, `#ENDIF` (`asm.txt`); none of the
  tree's sources use them.

## 5. Directives (all defined in `yacc1.def`, not in the assembler)

| Directive | Effect | `.def` line |
|---|---|---|
| `ORG addr` | set the assembly address; flushes the hex record | `ORG \W` → `\O1` |
| `END addr` | set the start address (the `*AAAA` line of a `.prg`; ignored by the hex loaders) | `END \W` → `\S1` |
| `EQU value` / `.EQU` / `equ` | define the label on this line as a constant (a register name or a word) | `EQU \{regs}`, `EQU \W` → `\E1` |
| `DB byte[,byte...]` / `DB "text"` | emit bytes | `DB \L` → `\1` |
| `DB HIGH word` | emit the high byte of a word | `DB HIGH \W` → `hi(1)` |
| `DW word[,word...]` | emit words, **high byte first** | `DW \W` → `hi(1) lo(1)`; `DW \M` |
| `DS n` | reserve n bytes (nothing emitted; the next record starts after them); n may use backward labels (quirk 11) | `DS \W` → `\B1` |
| `PUBLIC`, `EXTERN`, `LIB PROC`, `LIB ENDP` | RC/asm library markers; unused in the tree | `\P \X \R \Q` |

`ORG` takes the address in the assembler's expression syntax; the compiler emits it as decimal (`ORG 12288`).
`END` is optional in practice (`ledcount.asm` has none).

## 6. Quirks (verified, with the evidence)

1. **Every source line is upper-cased before matching**, so labels are case-insensitive and
   `DB "text"` emits upper-case text (`DB "Ab"` → `41 42`, checked). Emit strings as numeric bytes when case matters:
   the compiler writes `DB 115,117,109,...` (`y1cc.py`). The monitor's banner is written `"YACC 2020: hello world  "`
   in `monitor.asm` but the listing shows the bytes `4f 52 4c 44` (`ORLD`, `monitor.lst` around line 1160): the
   machine prints `YACC 2020: HELLO WORLD`.
2. **Labels are at most 29 characters** (`header.h`: `char labels[MAX_LABELS][30]`, "KEN CHANGED FROM 16 TO 30";
   `y1cc.py` `LABEL_MAX = 29`; the compiler mangles long C names). A longer label used to overwrite memory; since
   2026-09-24 it stops the assembly with `ERR - Label longer than 29 characters`. The label table holds **8,191**
   labels (`MAX_LABELS` 8192, was 1,000 with no check: 3,817 crashed it); a full table is the error `Too many labels`.
   Also fixed 2026-09-24: a space or tab inside an operand (`DW A, B`) made the assembler loop forever.
3. **A leading `-` on a number is silently dropped**: `LDAI -1` assembles to `0E 01` (checked). There are no negative
   numbers; write two's complement by hand (`0FFH`).
4. **A `\B` operand over 255 is an error** ("out of range"); `\W` operands over 65535 likewise. The compiler rejects
   integer literals over 65535 at its own level.
5. **`DS` used to corrupt the following bytes' addresses**: bytes after a `DS` were appended to the Intel-hex record
   that began before it and so loaded at the wrong address. Fixed 2026-09-22 in `asmcmds.c` (`write_line()` after
   `\B`, "flush the pending hex record so bytes after a DS start a new record"); `tools/patched_files.txt` records it.
   The firmware never uses `DS`, so the burned images are unchanged (`make check` proves it).
6. **`IADDR` with an odd operand assembles to opcode $FF** because its pattern is `FE|1 hi(1) lo(1)` (`|1` ORs the
   operand into the opcode byte): `IADDR 1235H` → `FF 12 35` (checked 2026-09-23). See the ISA reference section 9.
7. Two labels differing only in case collide (quirk 1); the compiler uniquifies its labels for that reason.
8. The `-d` option consumes the following argument (section 2).
9. Missing `yacc1.def` or a missing source name used to crash; since 2026-09-20 they print a message (`asm.c`).
10. There is no `.0`/`.1` on a bare `label+4` (write `(label+4).0`); the compiler always parenthesises.
11. **Pass 1 used to read every label as 1** (`support.c` `find_label`), so an `ORG`, `DS` or `EQU` whose operand
    named a label placed what followed at the wrong address (`DS 256-(y).0` reserved 255 bytes). Since 2026-09-24 a
    label already defined earlier in the source (a backward reference) has its value in pass 1 too, and `EQU` sets
    its value in pass 1 (`asmcmds.c`); a forward reference is still 1 in pass 1, so keep label expressions in
    `ORG`/`DS`/`EQU` backward. y1cc `--xisa` aligns its variable page with `zpad: DS (256-(zpad).0)&255` (the label
    on the same line counts as defined). Every firmware image, bench image and test program assembles to the same
    bytes as before (`tools/verify_firmware.py`, `tests/bench`, `tests/os`, `tests/compiler/passes.py`).

## 7. The four worked examples in `tests/assembler/`

Each folder has a README with the byte listing and what a failure means; here is what each program teaches.

**`ledcount/`** — the 16-byte switch-ROM program (10 bytes at $0000) for the Mem Switch bring-up card:

```
SWITCHLED:  EQU 001H
        ORG 0000H
        LDAI 0                  ; count = 0
loop:   OUTI P0,SWITCHLED       ; select the LED board
        OUTA P1                 ; LEDs = count
        ADDI 1                  ; count += 1
        BR loop                 ; forever
```

Bytes `0E 00 70 01 61 B0 01 A0 00 02`. It shows the I/O card's two-step port idiom (`OUTI P0,select / OUTA P1`),
an immediate ALU op and an absolute branch, and it uses only PC-relative fetches (no stack, no R2), which is why it
ran on 2026-09-21 before any of the register/stack findings mattered (`docs/system/MACHINE.md`). Its output is the
`.prg` text format (no `-h`).

**`brur/`** — the test of `BRUR Rn` ($AD, added 2026-09-22): a direct `BRUR R5`, a jump through an address fetched
from a `DW` table (`LDAVR R6 / MVARH R5 / INCR R6 / LDAVR R6 / MVARL R5 / BRUR R5`: the two bytes of a big-endian word
into a register by hand), and a four-way dispatch indexed by a counter (`MVRLA R7 / MVAT / MVRLA R6 / ADDT / MVARL R6`,
the table kept inside one page so only the low byte is added). Expected console output `ABC0123`, then `HALT`. The
program starts at $3000 and carries the same boot stub the compiler's `--boot` emits at $F000 (`BR 0F003H / MVIW
R1,0EFFH / JSR main / HALT`): the first branch presents an A15-high address to end FORCE-ROM. Run:
`emulator -x -f brur.img`; `tests/ucemu/run.py` runs it on the microcode emulator too.

**`romcount/`** — a 41-byte program burned in place of the monitor to prove the EPROM tool chain: mirror the
switches to the LED board and the TIL311 displays while the input line is low, then count up from the switch value
with a `DECR R3 / MVRHA R3 / BRNZ` delay loop and `MVAT`/`MVTA` keeping the count in TMP. It uses only R1, R3 and TMP
after the first build (R6/R7) exposed the missing second register card on the bench. Build chain: `asm romcount
-d=yacc1` → `romcount.img` → `python3 tools/img2bin.py romcount.img romcount.bin --base 0xE000 --end 0x10000 --fill
0xFF --size 8192` (offset $1000 in the 8K image = $F000). `run.py` re-assembles, compares both files with the
committed ones and runs the image on `y1ucemu -s 0x25 -i 0/1 -L`. It ran overnight on the machine 2026-09-22/23.

**`romdiag/`** — the instruction check paced by the input switch: twelve stages, each waiting for the line to
change (`BRINH wlo1` / `BRINL whi2`), each showing a byte on the LEDs through a `show` subroutine (`JSR`/`RET`, so
stage 1 also proves the stack): `LDAI`, `MVRHA`, `MVRLA`, `DECR`, `BRNZ` both ways, `ADDI`, `MVAT`/`MVTA`, a probe of
R7 (stage 9: `FF` means register card 1 is absent), the delay loop, then a free-running count. Expected LED sequence
`25 ON AA 20 11 03 01 02 FF 33 20 55 00 01 02`. `run.py` runs it on ucemu with `-I 100000` flipping the line and
`-R 2`/`-R 1` for both card configurations.

## 8. The `.def` file, so a new instruction can be added

`yacc1.def` (format from `asm.txt`, "Definition files"):

1. Line 1 is a comment (`yacc1 -> Native`).
2. `CLASS regs` / `CLASS ports` define operand classes: `text=value` pairs. `\{regs}` in a pattern matches one of them
   and yields its value.
3. `*` starts the translations. Each instruction is **two lines**: the pattern (`MNEMONIC<tab>operand pattern`) and the
   construction line.
4. Pattern wildcards: `\B` a byte (0–255), `\W` a word, `\N` a nibble, `\{class}` a class member, `\L` the rest of the
   line as a byte list (for `DB`), `\M` as a word list (`DW`), `\D` a displacement (unused here). The k-th wildcard
   becomes replacement variable k.
5. Construction: hex digits build a byte in an accumulator; a blank outputs it and starts the next byte. `\n` inserts
   variable n; `hi(n)`/`lo(n)` its high/low byte; `|n` ORs variable n into the current byte without shifting, `|n<v`
   after shifting it left v bits, `|n>v` right; `&nn` ANDs the byte with hex nn; `%` swaps nibbles. Directive
   builders: `\On` ORG, `\En` EQU, `\Sn` END, `\Bn` DS, `\P \Q \R \X` library marks.

Reading the tree's entries with that key:

| Entry | Meaning |
|---|---|
| `LDAI \B` / `0E \1` | opcode $0E, then the byte |
| `BR \W` / `A0 hi(1) lo(1)` | $A0, high byte, low byte — every address operand is big-endian |
| `MVIB \{regs},\B` / `10\|1 \2` | $10 OR the register number in the opcode, then the byte |
| `MVIW \{regs},\W` / `18\|1  hi(2) lo(2)` | $18 OR reg, then the word |
| `MOVRR \{regs},\{regs}` / `0F \|2<4\|1` | $0F, then (second reg << 4) OR first reg: **source first, destination second** |
| `POPR \{regs}` / `08 \1<4&f0` | $08, then reg << 4 |
| `PUSHR`/`JSRUR`/`BRUR \{regs}` / `07 \1`, `06 \1`, `AD \1` | opcode, then the register number in the low nibble |
| `BRVR \{regs}` / `D8\|1` | one byte, register in the opcode |
| `OUTI \{ports},\B` / `70\|1 \2` | $70 OR port, then the byte |
| `IADDR \W` / `FE\|1  hi(1) lo(1)` | the buggy one (quirk 6); should be `FE hi(1) lo(1)` |

To add an instruction: give it a number in `software/opcodes.h` (the generator, both emulators and the disassembler
include it), microcode in the generator (`firmware/microcode/README.md`: `make regen`, then load the EEPROM), a case
in `software/emulator/main.c`, and two lines here. `BRUR` on 2026-09-22 is the worked example of exactly that
(`tools/patched_files.txt`: `opcodes.h`, `branch.c`, `yacc1.def`, `main.c`, `test.hex`); `tests/assembler/brur`
is its test. Keep the mnemonic order in the file irrelevant (patterns are matched, not searched in order) but avoid
a pattern that is a prefix of another with the same operand shape.

## 9. Putting the output to use

- Run on the interpreter: `software/emulator/emulator -x -f NAME.img` (with a `--boot`-style stub at $F000 and a
  `HALT`), or `emulator -m -f NAME.img` and `G3000` at the monitor prompt for a program assembled at $3000 that ends
  with `RET`.
- Run on the microcode emulator: `software/ucemu/y1ucemu -x -m -f NAME.img` (the ROM is needed for the console path).
- Burn: `tools/img2bin.py` with `--base 0xE000 --end 0x10000 --fill 0xFF --size 8192` for a whole 28C64 image
  (`tests/assembler/romcount/README.md`); see [TOOLCHAIN.md](TOOLCHAIN.md).
- Put on a CF image for Y1/OS: `img2bin.py NAME.img NAME.bin --base 0x5000`, then `p8xfs.py put disk.img NAME.bin
  --name /BIN/NAME --load 0x5000 --exec 0x5000` (`os/Makefile`).
- Loading RAM on the real machine has no path yet: the monitor has no hex loader (`BACKLOG.md`: `tools/monload.py`
  through the `E` command is planned), so today a program reaches the machine only in the ROM socket or, once the
  card exists, from the CF card.
