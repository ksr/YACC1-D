# The YACC1 cross assembler (RC/asm, YACC1 port)

How to assemble YACC1 programs on the Mac with `software/assembler`, what it accepts, what it produces, and its
traps. Written 2026-09-23 from the YACC1-D tree. Since 2026-09-25 the same dialect assembles on the machine too:
`/BIN/ASM` under Y1/OS, section 10.

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
6. (Fixed 2026-09-23 in `yacc1.def`, commit 69db58d.) `IADDR` with an odd operand assembled to opcode $FF because its
   pattern was `FE|1 hi(1) lo(1)` (`|1` ORs the operand into the opcode byte): `IADDR 1235H` gave `FF 12 35`. The line
   is `FE  hi(1) lo(1)` now: `IADDR 1235H` → `FE 12 35` (checked 2026-09-25).
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
12. **A line of 100 characters or more aborts the assembler** (found 2026-09-25): `trim()` and `parse()` copy the text
    after the leading blanks / after the label, up to the comment, into `char tmp[100]`, and macOS's fortified
    `strcpy` stops the program (exit status 133, no output). y1cc's instructions are far shorter (its longest lines,
    109 characters, are comments, cut before the copy); the native assembler (section 10) takes 254.
    BACKLOG has the fix.

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
| `IADDR \W` / `FE  hi(1) lo(1)` | $FE, then the word (it was `FE\|1`, quirk 6) |

To add an instruction: give it a number in `software/opcodes.h` (the generator, both emulators and the disassembler
include it), microcode in the generator (`firmware/microcode/README.md`: `make regen`, then load the EEPROM), a case
in `software/emulator/main.c`, and two lines here. `make -C os` then regenerates the native assemblers' tables and
the disassembler's (`/BIN/DISASM`, `os/dis_optab.c` by `tools/gen_y1_distab.py`, 2026-09-29), which also checks the
new opcode against `software/opcodes.h`; `disasm` prints it in this dialect, so `disasm -s` output assembles back. `BRUR` on 2026-09-22 is the worked example of exactly that
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

## 10. The native assembler, /BIN/ASM (2026-09-25; in YACC1 assembly since 2026-09-26)

The same dialect on the machine, in two versions that behave identically (`man asm`, `man asmc`, `os/README.md`
"asm"), written after RC/asm's own code (not the P8X assembler, whose syntax is another) so that they make the same
bytes of the same source, quirks and all:

| | `/BIN/ASM` | `/BIN/ASMC` |
|---|---|---|
| source | `os/commands-asm/asm.asm`, hand-written YACC1 assembly (2026-09-26) | `os/commands/asm.c`, compiled by y1cc (2026-09-25) |
| role | the assembler everything uses (`cc`'s users, `tests/native`, the self-host) | **the specification**: asm.asm was written from it routine by routine; any change of behaviour goes into both |
| instruction table | `os/commands-asm/asmtab.inc` (INCLUDEd) | `os/asm_optab.c` (#included) |
| size | 9,239 bytes of program file | 13,186 bytes + 19,569 of data |
| symbol table | **20,292 bytes** (about 1,660 of y1cc's labels) | 17,088 bytes (about 1,400) |
| speed (instructions, cat's 1,504 lines) | 2.75M: 1 min 29 s at 1 MHz | 12.8M: 6 min 55 s |
| needs | the 2026-09-24 microcode (ADDIW, SHL16; so does the native compiler) | any microcode (compiled without `--xisa`, as every /BIN command) |

```
asm HELLO.ASM              HELLO: a program file (first to last address, gaps zero; load, exec = END or load)
asm -h HELLO.ASM           HELLO.IMG: Intel hex, the text of `asm HELLO -d=yacc1` with -h on the Mac
asm -h MONITOR.ASM M.IMG   an output name; a source name without '.' gets .ASM
```

- **The table** is `os/asm_optab.c` (asm.c) and `os/commands-asm/asmtab.inc` (asm.asm), both generated from
  `yacc1.def` by one run of `tools/gen_y1_optab.py` (the `os/Makefile` rules regenerate them; `tests/asm/run.py`
  fails if either is stale). The assembly table is laid out for its reader: 64 mnemonic chains under the hash
  `h = rotl8(h) + c` from a seed the generator picks (at most 3 records a chain), each name followed by a 127, and
  a register or port class as a direct table by the name's second character. The generator reads the file as `Read_Def_File` does
  and compiles each construction line with a copy of `Translate()` into a few operations (a run of hex digits is one
  constant), checked against a model of `Translate()` on random arguments; the patterns keep their order, grouped by
  mnemonic in 64 hash chains. A construction it cannot express (`\N`, `\D`, `%`, `|n>s`, `OPTION 16BIT`) stops the
  generator rather than producing a different assembler. To add an instruction, section 8 is all there is to do,
  then `make -C os`.
- **What is copied**: the line read 254 bytes at a time (`fgets(buffer, 255)`); `makeupper` (upper case outside
  single quotes); `parse` (the comment at the first `;` outside quotes, the label before the first `:` outside
  quotes, with RC/asm's rule that a second kind of quote inside a quote takes over); `WildMatch`/`Class_Match`
  (first word literal, whitespace, `\B`/`\W` up to a `,` or space outside quotes with the `abs((int)v)` range test,
  a class name as a prefix, `\L`/`\M` the rest); `get_num` with `buildTokens`/`process_tokens` in 32 bits, token
  records shifted exactly as RC/asm shifts them - including the tokens that slide in from beyond a parenthesis'
  range and the stale ones past the count, the dropped leading minus, `.1` as C's `/ 256`, `12H3` as hex 123;
  pass 1 reading a forward reference as 1 and EQU setting its value in pass 1; the Intel-hex records (16 bytes, a
  new record at ORG and DS); INCLUDE's file name taken from the raw line (two levels here).
- **Not supported** (an error in /BIN/ASM, accepted by RC/asm; nothing in the tree uses them): MACRO/ENDM, PUBLIC,
  EXTERN, LIB PROC/ENDP; `/` on values beyond 16 bits; an EQU value outside -65535..65535 (labels are 16 bits + a
  sign); code or a label past $FFFF (RC/asm counts on into 17 bits); INCLUDE more than two deep (four OS handles:
  the source, two includes, the output). RC/asm's `.prg` output and its listing, cross-reference and symbol options
  are not there: the summary line gives the size, the label count and the addresses.
- **Other differences**: errors are counted once per line (RC/asm can print the same undefined label for every
  pattern it tries) and name the line in its own file; after an error the output file is deleted (RC/asm writes
  it anyway); a missing INCLUDE file is an error (RC/asm prints a message and goes on); lines of 100-254 characters
  work (quirk 12).
- **Limits**: the symbol table is 20,292 bytes in `/BIN/ASM` (17,088 in `/BIN/ASMC`: 16,640 until 2026-09-25,
  when cc8's buffered I/O outgrew it), 5 + the name's length a label (y1cc's labels average 7 characters: about
  1,660 labels, 1,400 in ASMC; the biggest compiler pass, cc8, has 1,383 in 16,925 bytes, 83% of ASM's table);
  29 characters a label, 254 a line, 45 tokens an expression, 32 characters a token; source files up to 16M
  (Y1/OS's positions are 24 bits since 2026-09-25); the program file needs the code to go up in address (else
  `-h`). A source that fills ASMC's table can fill ASM's too a little later, with its own error on its own line:
  y1cc.c itself compiled (4,186 labels) is refused by both (`tests/asm`). The output takes Y1/OS's one write
  handle, so neither works inside a `>` or a pipe ("cannot create").
- **asm.asm** (`os/commands-asm/asm.asm`, 2026-09-26; its header has the conventions): every routine names the asm.c
  function it implements. What makes it fast: the source is read a sector at a time with READ straight into its
  buffer and each line scanned where it lies, 8 instructions a byte, with a translation table that upper-cases and
  maps the characters `parse()` must see to 0, and two 0 sentinels (the end of the data read, the line's 254th
  byte), so the loop tests nothing else; a line that runs past the data is moved into the page before the buffer,
  so the raw line (for the error messages and INCLUDE's name) is always the bytes in the buffer; a comment is
  scanned only for its line feed; leading blanks are skipped (put into `ln` only when the line has a label).
  Tokens are cut in place in `ln` (a token with a blank inside - RC/asm skips blanks inside a token - sends the
  expression to asm.c's copying tokenizer, which writes the same records from the start); the records are
  asm.c's, 8 bytes apart, shifted exactly as there, stale ones included; `(label).0` and `(label).1`, y1cc's
  `--xisa` page offsets, are computed at once when the five records are the usual ones, with the same records left
  behind (the general algorithm runs when the stale record after them is an operator: `tests/asm/src/err_stale.asm`).
  Labels: 256 chains of `len|flags next value name` records, the name stored backwards so the compare starts where
  y1cc's labels differ. An INCLUDE keeps the outer file's position and SEEKs back to it. It uses ADDIW and SHL16
  (the 2026-09-24 microcode), never R2, and the shell's stack (~20 bytes deep); the page-aligned tables and
  buffers are at $C400-$CFFF, its variables after the code, the symbol table between.
- **Speed** (instructions on the instruction-level emulator, program file; the monitor to hex; each figure includes
  the OS's and the ROM's work for the file I/O, 15-25%; at 1 MHz with 32.4 clocks an instruction):

  | source | lines | bytes | `/BIN/ASMC` | `/BIN/ASM` | faster | an instruction a byte | at 1 MHz |
  |---|---|---|---|---|---|---|---|
  | hello (y1cc) | 82 | 1,652 | 0.88M | 0.20M | 4.3x | 124 | 28 s -> 6 s |
  | cat (y1cc) | 1,504 | 27,706 | 12.8M | 2.75M | 4.7x | 99 | 6 min 55 s -> 1 min 29 s |
  | the ROM monitor (-h) | 1,972 | 46,179 | 17.3M | 3.96M | 4.4x | 86 | 9 min 20 s -> 2 min 08 s |
  | cc4 (y1cc `--xisa`) | 3,404 | 65,973 | 37.8M | 7.18M | 5.3x | 109 | 20 min 25 s -> 3 min 52 s |
  | cc8 (y1cc `--xisa`, the biggest pass) | 11,897 | 235,482 | 129.7M | 26.4M | 4.9x | 112 | 1 h 10 min -> 14 min 15 s |

  The microcode emulator (cat, each in a session of its own less an empty one): ASM 2.85M instructions and 83.9M
  clocks (29.4 an instruction: hand-written code has fewer of the long instructions), ASMC 12.9M and 435.5M
  (33.7): 5.2x in real time, no bus fights. A native compile (`tests/native/run.py`'s 27 programs): assembling
  217M -> 46.5M instructions, compile and assemble 687M -> 517M (6 h 11 min -> 4 h 39 min at 1 MHz). The self-host
  (`tests/native/selfhost.py`, one stage): assembling 764M -> 153M, the eleven C programs 21 h 17 min -> 15 h 47 min,
  15 h 52 min with asm.asm's own assembly (software/compiler/README.md). Where ASM's time goes now
  (`tests/native/profile.py`): reading lines 20%, the ROM's sector reads 12%, the mnemonic 12%, tokens 15%,
  matching 10%, labels 9%, the operations 8%, output 5%.
- **Tests**: `tests/asm/run.py` (in `make check`, `make asm-test`) builds `asm.c` for the Mac with the YACC1's
  integer types against an emulation of the Y1/OS syscalls (`tests/asm/host_asm.c`, `host_sys.c`) and compares it
  with RC/asm on every source in the tree; then it runs `/BIN/ASM` (asm.asm) under Y1/OS on the instruction-level
  emulator on the same 336 sources, with -h and to a program file (disks of 72 sources, the sessions in parallel,
  20 seconds), and its messages, summary and files must be what asm.c gives for the same command line: 334
  identical, 2 refused by both where ASMC's table is full (`--uc`: 27 of them on the microcode emulator too, 2
  minutes) - each y1cc compile of `tests/compiler/corpus.py` plain and `--xisa` (262,
  the nine compiler passes and `asm.c` itself among them), the monitor and BASIC with their candidates, monnew,
  `tests/assembler`, `isa.asm`, `y1os.asm` with its INCLUDE, and `tests/asm/src` (`quirks.asm`: the corners above;
  six sources both must refuse): 283 identical in hex and as program files, 1 identical in hex (`yacc1test.asm`
  goes back in address: its program file is refused, as it must be), 13 refused by both. `--target`
  (`tests/asm/target.py`) runs `asm` under Y1/OS on both emulators: y1cc programs assembled and run, the monitor
  assembled to `firmware/monitor/monitor.img`, `isa.asm`, the quirks with INCLUDE, compiler pass cc4, an error;
  every file written compared with RC/asm's output.
