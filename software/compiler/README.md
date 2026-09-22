# software/compiler — y1cc, a C cross-compiler for the YACC1

`y1cc.py` (Python 3, no dependencies) compiles a small C subset to YACC1 assembly for `software/assembler`
(RC/asm with `yacc1.def`). Written 2026-09-22; the first C compiler the machine has had. The front end (lexer,
parser, the C subset) is the one of the P8X compiler `p8x/compiler/p8cc.py`, so P8X C programs port with their
source unchanged as far as the subset goes; the back end is new, written for what the YACC1 actually has.

```
python3 software/compiler/y1cc.py prog.c -o prog.asm            # for the machine (monitor: G3000 calls main)
python3 software/compiler/y1cc.py prog.c -o prog.asm --vector   # for the monitor as burned in 2021 (G = BRVR)
python3 software/compiler/y1cc.py prog.c -o prog.asm --boot     # for the emulator, stand-alone
cd <dir with rcasm.rc + yacc1.def> && ../software/assembler/asm prog -d=yacc1 > prog.lst   # -> prog.img (Intel hex)
software/emulator/emulator -x -f prog.img                       # runs it, exits at HALT (--boot images)
python3 tests/compiler/run.py                                    # the test suite (make cc-test)
```

## The C subset

| | |
|---|---|
| types | `int` (16-bit **unsigned**, as in p8cc), `char` (8-bit unsigned), pointers, arrays `T a[N]`, `struct`/`union` (by pointer or member: no by-value struct params, returns or assignment); `unsigned`, `const`, `static`, `void` accepted |
| top level | struct/union definitions, function definitions and prototypes, globals with constant initializers (numbers, strings, `{lists}`, `&var` / array addresses, `[]` length inferred) |
| statements | `{}` decl (with initializer, several per line) `if/else` `while` `for(e;e;e)` `switch/case/default` `break` `continue` `return` expr `;` |
| expressions | `=` `+= -= *= /= %= &= \|= ^= <<= >>=` `++ --` (pre/post) `?:` `\|\| &&` `\| ^ &` `== != < > <= >=` `<< >>` `+ - * / %` unary `- ! ~ & *` `a[i]` `s.m` `p->m` `f(args)` `sizeof` |
| preprocessor | `#define NAME value` (integer or char), `#include "file"` (textual, each file once, searched beside the source then in `lib/`) |
| builtins | `putchar(c)` `getchar()` `puts(s)` (console), `peek(a)` `poke(a,v)` `peekw(a)` `pokew(a,v)` (memory), `inp(port)` `outp(port,v)` (I/O ports, constant 0..15), `halt()`, `bios(addr, r7, acc)` (JSR a monitor routine with R7 and ACC set; returns ACC) |
| library | `lib/y1lib.c`: `putstr putnum puthex puthex2 strlen strcmp strcpy memset` — `#include "y1lib.c"`; unused functions cost nothing (dead-function elimination) |
| not there | **recursion** (rejected at compile time), signed arithmetic, `long`/float, function pointers, `goto`, bit fields |

Console I/O: on the emulator `putchar` is `OUTA P2` and `getchar` is `INP P2` (returns 0 at end of input); on the
machine they call the monitor's BIOS vectors `charout` ($FFC4) and `uartin` ($FFE8). The runtime chooses at run
time with `BRDEV`, which never branches on the emulator and always branches on the hardware, so one image serves
both. `puts` appends `\n` (10) only.

## How the generated code works (the YACC1-specific part)

The YACC1 has an 8-bit accumulator ACC and an 8-bit TMP, eight 16-bit registers R0-R7 (R0 = PC, R1 = SP), byte
loads/stores through any register (`LDAVR`/`STAVR`), absolute 16-bit register loads/stores (`LDR`/`STR`, 3 bytes),
and big-endian words in memory. There is no 16-bit ALU and no indexed addressing, which drove every choice below.

- **R3 is the expression accumulator**: every expression leaves its 16-bit value in R3 (chars zero-extended).
  R4 is the second operand, R5-R7 are runtime scratch (R7 also carries the string for the monitor's `stringout`).
  **R2 is never touched**: on the hardware `LDA/STA/LDT/STT/LDR/STR` use R2 as the hidden operand-address register
  (`docs/isa/MICROCODE-REVIEW-NOTES.md` L-9); the emulator uses a ninth register for that, so a program that
  relied on R2 would only fail on the real machine.
- **Static frames, no recursion.** A global is a labelled word or byte; a function's parameters and locals are
  labelled slots of their own (`main_i: DS 2`). Loading or storing a scalar is one 3-byte `LDR R3,label` /
  `STR R3,label`; a frame-relative access would have cost a 16-bit add per variable (about 12 bytes) because the
  ISA has no `(Rn+d)` addressing. The price: a function that can call itself, even through another function, is
  a compile error (the call graph is checked). A char scalar occupies a 2-byte slot whose high byte is kept zero,
  so it loads with one `LDR` too; char arrays and struct members are true bytes.
- **Calls**: the caller evaluates each argument into R3 and stores it straight into the callee's parameter slot,
  then `JSR`. When a later argument's evaluation could itself run the callee (`f(x, g())` where `g` calls `f`)
  the earlier ones are parked on the stack meanwhile. The result comes back in R3; `return` is `RET`.
- **Arithmetic** is byte-wise through ACC/TMP. `+ & | ^` are inline (`MVRLA R4 / MVAT / MVRLA R3 / ADDT /
  MVARL R3 / ... ADDTC ...`, the `do_add16` idiom the monitor proved on the hardware; 8-10 bytes), constants fold
  into `ADDI`/`ADDIC` immediates, `+1`/`-1` are `INCR`/`DECR`. `-` is a runtime call (two's-complement add: the
  emulator and the hardware disagree about SUB's borrow, so it is never used). `* / % << >>` are runtime loops
  (`rt_mul`, `rt_divmod`, `rt_shl`, `rt_shr`); shifts by small constants, `*2 *4 *8 *256`, `/2^k`, `%2^k` are inline.
- **Comparisons** in conditions branch straight on the comparator instructions (`BRLT/BRGT/BREQ/BRNEQ` compare
  ACC with TMP): high bytes first, low bytes only if they are equal. Two char operands need one compare; `x == 0`
  ORs the two bytes. Unsigned, like p8cc's int. A relation used as a value becomes 0/1 through the same path.
- **The carry flag** is used only inside an `ADDT/ADDTC` (or `ADDI/ADDIC`) pair with nothing but register moves
  between them, and inside a `CSHL/CSHR` pair after an explicit clear (`LDAI 0 / CSHL`). Plain shifts and
  subtracts never feed a following carry op, because the hardware loads the carry flip-flop on every shift and on
  SUB and the emulator does not (review item L-7).
- **Image layout**: `ORG` → main → the other live functions →
  the runtime helpers actually used → initialised data and strings (`DB` as numbers: the assembler upper-cases
  every source line, so `DB "text"` would be shouted) → uninitialised variables (`DS`, kept last) → with
  `--boot` a stub at $F000 (`BR $F003 / MVIW R1,$0EFF / JSR f_main / HALT`; the first branch presents an A15-high
  address, which releases the memory card's FORCE-ROM boot remap exactly as the monitor's first instruction does —
  without it every fetch stays inside $F000-$FFFF, seen on the microcode emulator). The monitor's `G AAAA` (rebuilt 2026-09-22) is
  `JSRUR R7`, a call: `G3000` enters main and main's RET returns to the command loop. `--vector` is the layout for
  the monitor as burned in 2021, whose G was `BRVR R7`: on the hardware that is an indirect jump through the word at
  AAAA (the microcode reads `[R7]`,`[R7+1]` into the branch register, `docs/isa/steps.txt`) that pushes no return
  address, so that image starts with a 2-byte vector to a stub `JSR f_main / BR $F000` (monitor restart). Both were
  run on the emulator against the respective monitor image (the 2021 one from the chip capture).
  The default `--org` is $3000 because $1000-$1FFF is BASIC's token buffer, which the monitor's boot (and the
  restart after main) clears, and the monitor's T tests use $2000 as scratch; a program at $1000 lost its first
  byte before it ran (found on the emulator 2026-09-22).
- **Zero-initialised data** (2026-09-22, found by the microcode emulator's $FF-filled RAM): main starts by clearing
  every `DS` slot between `bss_start` and `bss_end` (20 bytes of code), and a partially initialised array's tail is
  real zero bytes in the image, not `DS`. The interpreter's zeroed memory had hidden both.
- **`switch`** (2026-09-22): the case labels must be direct statements of the switch block. Dispatch is whichever is
  smaller: a compare chain (`LDTI k / BREQ` per case when every case fits a byte, 5 bytes each; a two-level compare,
  13 bytes, otherwise) or a jump table through `BRUR` ($AD, PC ← Rn): subtract the lowest case, range-check, index
  a table of `DW` addresses, load the word into R3, `BRUR R3` (about 49 bytes plus 2 per slot; holes go to default).
  `--no-brur` forbids the table, for the machine until its sequencer EEPROM holds the microcode with BRUR; the
  same test program passes both ways (`switch.c` / `switchnb.c`).
- Never emitted: `LDTVR STTVR OUTVR BR16Z BR16NZ BRNC` (no microcode), `BRVR JSRUR` (not needed yet),
  negative numbers (the assembler silently drops the sign), labels over 29 characters (crash the assembler), or
  two labels differing only in case (the assembler folds case; the compiler mangles and uniquifies).

## Tests

`tests/compiler/*.c` with the expected output beside each (`.out`, `.in` for stdin, `.err` for an expected
compile error, `// y1cc: flags` on a line for per-test compiler flags); `tests/compiler/run.py` compiles, assembles, runs each on `emulator -x` and diffs. `--oracle`
regenerates the `.out` files with the HOST C compiler through `host_shim.h` (`int` = `unsigned short`, unsigned
char), so the expectations are independent of this compiler; tests marked `no-oracle` (peek/poke, struct layout,
byte order) carry hand-written expectations. 15 programs, 15/15 on 2026-09-22 (~1 s). `make check` runs them.
The same images also run under the monitor on the emulator (`emulator -m -f prog.img`, then `G3000`): the program's
output appears after `GO ADDRESS:` and the monitor's banner follows when main returns (hello and fib tried 2026-09-22).

Sizes on 2026-09-22 (code + data + runtime, bytes): hello 111, io 722, sieve 862, chars 893, calls 948,
globals 966, fib 1045, structs 1398, arrays 1446, control 2356, arith 2339.

## Not done yet (BACKLOG "C compiler")

Running a compiled program on the real machine needs a way to load RAM (the monitor's E-command loader on the
backlog, or the bus tester with the CPU off); a stack-frame mode for recursion; `switch`; signed types; peephole
work (the code is straightforward, roughly 2-3x what hand assembly would be); the P8X-side libraries.

## Size against the P8X compiler

`bench/sizecmp.sh` compiles the same four programs (written in the subset both compilers accept) with p8cc + p8xasm
and with y1cc + asm and compares the binaries, uninitialised data included on both sides (2026-09-22):

| program | P8X bytes | YACC1 bytes | ratio |
|---|---|---|---|
| fib | 1075 | 813 | 0.76 |
| sieve | 760 | 667 | 0.88 |
| sort | 1114 | 896 | 0.80 |
| strings | 1030 | 782 | 0.76 |

The YACC1 binaries are 14-26% smaller for the same source (2026-09-22 evening, after main gained its 20-byte BSS clear).
The same four programs rewritten with everything y1cc accepts (`bench/full/`: the library's putnum, `++`, `+=`,
`?:`, `continue`, pointer loops, `char` loop counters) come out only a little smaller — sieve 633, fib 769, strings
713, sort 865 bytes (1-6%) — because `i++` and `i = i + 1` are the same code; what saved bytes was `char` counters
(one-byte compares) and pointer walks. The size is in the code model, not the syntax.
 The reasons are in the instruction sets rather than in
the compilers: y1cc keeps every scalar at a fixed address, so a load or store is one 3-byte `LDR`/`STR` and a
16-bit constant is one 3-byte `MVIW`, while p8cc's frame-relative `LDW/STW (P3+d)` and `LDW __ax,#n` (4-5 bytes)
plus its memory-word arithmetic helpers cost more per operation; the YACC1's register `INCR`/`DECR` and the
comparator branches are 1-3 bytes where the P8X needs a memory word op. Speed is another matter: a YACC1 step is
two clocks and an instruction 8-30 steps, so the emulator's instruction counts above translate to roughly 10x the
clock cycles of the same work on the P8X. Integer literals over 65535 are a compile error (int is 16-bit).
