# software/compiler — y1cc, a C cross-compiler for the YACC1

`y1cc.py` (Python 3, no dependencies) compiles a small C subset to YACC1 assembly for `software/assembler`
(RC/asm with `yacc1.def`). Written 2026-09-22; the first C compiler the machine has had. Since 2026-09-24 it has a
twin in C, `c/y1cc.c` (below), written in the subset itself and producing the same assembly byte for byte: the first
step towards a compiler that runs on the machine. `y1cc.py` stays the reference and the bootstrap. The front end (lexer,
parser, the C subset) is the one of the P8X compiler `p8x/compiler/p8cc.py`, so P8X C programs port with their
source unchanged as far as the subset goes; the back end is new, written for what the YACC1 actually has.

```
python3 software/compiler/y1cc.py prog.c -o prog.asm            # for the machine (monitor: G3000 calls main)
python3 software/compiler/y1cc.py prog.c -o prog.asm --vector   # for the monitor as burned in 2021 (G = BRVR)
python3 software/compiler/y1cc.py prog.c -o prog.asm --org 0x5000 --os   # a Y1/OS program (os/Makefile): console via the OS
python3 software/compiler/y1cc.py prog.c -o prog.asm --boot     # for the emulator, stand-alone
cd <dir with rcasm.rc + yacc1.def> && ../software/assembler/asm prog -d=yacc1 > prog.lst   # -> prog.img (Intel hex)
software/emulator/emulator -x -f prog.img                       # runs it, exits at HALT (--boot images)
python3 tests/compiler/run.py                                    # the test suite (make cc-test)
make -C software/compiler/c && software/compiler/c/y1cc prog.c -o prog.asm --boot   # the C twin: same options, same output
python3 tests/compiler/twin.py                                   # y1cc.py vs the C twin over the whole corpus
```

## The C subset

| | |
|---|---|
| types | `int` (16-bit **unsigned**, as in p8cc), `char` (8-bit unsigned), pointers, arrays `T a[N]`, `struct`/`union` (by pointer or member: no by-value struct params, returns or assignment); `unsigned`, `const`, `static`, `void` accepted |
| top level | struct/union definitions, function definitions and prototypes, globals with constant initializers (numbers, strings, `{lists}`, `&var` / array addresses, `[]` length inferred) |
| statements | `{}` decl (with initializer, several per line) `if/else` `while` `for(e;e;e)` `switch/case/default` `break` `continue` `return` expr `;` |
| expressions | `=` `+= -= *= /= %= &= \|= ^= <<= >>=` `++ --` (pre/post) `?:` `\|\| &&` `\| ^ &` `== != < > <= >=` `<< >>` `+ - * / %` unary `- ! ~ & *` `a[i]` `s.m` `p->m` `f(args)` `sizeof` |
| preprocessor | `#define NAME value` (integer or char), `#include "file"` (textual, each file once, searched beside the source then in `lib/`) |
| builtins | `putchar(c)` `getchar()` `puts(s)` (console), `peek(a)` `poke(a,v)` `peekw(a)` `pokew(a,v)` (memory), `inp(port)` `outp(port,v)` (I/O ports, constant 0..15), `halt()`, `bios(addr, r7, acc)` (JSR a monitor routine with R7 and ACC set; returns ACC), `call(addr)` (JSRUR a computed address, returns its R3), `argstr()` (the command tail at $0F40), `sys(n, a, b, c)` and `funcaddr(f)` (the Y1/OS syscall interface, below) |
| library | `lib/y1lib.c`: `putstr putnum puthex puthex2 strlen strcmp strcpy memset` — `#include "y1lib.c"`; unused functions cost nothing (dead-function elimination) |
| recursion | direct and mutual (2026-09-24): a call inside a recursive cycle saves and restores the callee's static frame on the stack (below). Not `main`; not the address of a local passed into the cycle |
| not there | signed arithmetic, `long`/float, function pointers, `goto`, bit fields, `do ... while`, `#if`/`#ifdef` (ignored, like every directive but `#define`/`#include`) |

Console I/O: on the emulator `putchar` is `OUTA P2` and `getchar` is `INP P2` (returns 0 at end of input); on the
machine they call the monitor's BIOS vectors `charout` ($FFC4) and `uartin` ($FFE8). The runtime chooses at run
time with `BRDEV`, which never branches on the emulator and always branches on the hardware, so one image serves
both. `puts` appends `\n` (10) only.

**`--os`** (2026-09-23) compiles a Y1/OS program: `os/Makefile` builds the OS itself and every `/BIN` command with
it. `putchar` (and `puts`, which loops over it) then stores the byte in SYSARG0 ($0F06, a big-endian word, high byte
0) and JSRURs the Y1/OS syscall CONOUT (the word at SYSTAB + 38 = $0F3A); `getchar` JSRURs CONIN (SYSTAB + 34) and
returns the low byte of SYSRES, or **0** when CONIN says 65535 (end of input, Ctrl-D, the end of a `<` file): the
same end-of-input byte as `INP P2` on the emulator. Both keep R3 and R4 (`rt_puts` walks its string in R3); the OS
handler is compiled code and clobbers R5-R7, ACC and TMP, which nothing keeps across a call. This is what lets the
shell redirect a program's output (`>`, `>>`, `|`) and input (`<`) with no change to its source (`os/README.md`).
Without `--os` the console runtime is the one above, byte for byte (checked 2026-09-23: every `tests/compiler`
program and the bench sources compile to identical assembly). An `--os` program must run under Y1/OS: from the
bare monitor its first `putchar` would jump through an empty SYSTAB slot.

## How the generated code works (the YACC1-specific part)

The YACC1 has an 8-bit accumulator ACC and an 8-bit TMP, eight 16-bit registers R0-R7 (R0 = PC, R1 = SP), byte
loads/stores through any register (`LDAVR`/`STAVR`), absolute 16-bit register loads/stores (`LDR`/`STR`, 3 bytes),
and big-endian words in memory. There is no 16-bit ALU and no indexed addressing, which drove every choice below.

- **R3 is the expression accumulator**: every expression leaves its 16-bit value in R3 (chars zero-extended).
  R4 is the second operand, R5-R7 are runtime scratch (R7 also carries the string for the monitor's `stringout`).
  **R2 is never touched**: on the hardware `LDA/STA/LDT/STT/LDR/STR` use R2 as the hidden operand-address register
  (`docs/isa/MICROCODE-REVIEW-NOTES.md` L-9); the emulator uses a ninth register for that, so a program that
  relied on R2 would only fail on the real machine.
- **Static frames.** A global is a labelled word or byte; a function's parameters and locals are
  labelled slots of their own (`main_i: DS 2`). Loading or storing a scalar is one 3-byte `LDR R3,label` /
  `STR R3,label`; a frame-relative access would have cost a 16-bit add per variable (about 12 bytes) because the
  ISA has no `(Rn+d)` addressing. A char scalar occupies a 2-byte slot whose high byte is kept zero,
  so it loads with one `LDR` too; char arrays and struct members are true bytes. A function's slots are
  consecutive `DS` lines: its **frame**, one block of bytes.
- **Recursion** (2026-09-24) keeps the static frames and saves them. The call graph's reachability tells which
  functions can reach themselves (a recursive cycle, a strongly connected component: `fact`, or `is_even`/`is_odd`).
  A call from a function to a callee that can reach back to it is a call *inside* a cycle; only those change:
  the caller pushes the callee's whole frame (parameters and locals) on the R1 stack, stores the arguments into
  the slots as usual, `JSR`s, and pops the frame back afterwards. So every activation finds its own values in the
  slots while it runs, all accesses stay one `LDR`/`STR`, and a function outside every cycle compiles exactly as
  before (`tests/compiler/diffcheck.py` proves it on the whole corpus). Why the callee's frame: whatever the callee
  (or anything it calls) changes in any frame of the cycle is put back by the call that changed it, so after any
  call inside the cycle every frame of the cycle is as it was. A function outside the cycle needs nothing: it
  cannot be active further up the stack (it would then reach the cycle and be part of it).
  - **Cost** per call inside a cycle: frames of up to 8 bytes are copied inline, `LDR R4,f+k / PUSHR R4` before and
    `POPR R4 / STR R4,f+k` after (10 bytes of code and about 123 microcode steps per frame word, an odd byte through
    `LDA/PUSH`, `POP/STA`); a bigger frame goes through the runtime pair `rt_fsave`/`rt_frest` (`MVIW R5,frame /
    MVIW R6,bytes / JSR`, 9 bytes each side, about 107 steps per byte each way). Example (2026-09-24, `--boot`):
    `fib(15)` recursive is 1,973 calls, 48,388 instructions and about 980,000 microcode steps (~500 steps a call);
    the iterative loop is 541 instructions and about 9,000 steps; the recursive function is 14 bytes larger (two
    call sites × 10 bytes of save/restore, less code elsewhere). Stack: 2 bytes of return address + the frame per
    level. The stack is the monitor's $0C00-$0EFF (768 bytes, the handle buffers of Y1/OS end at $0BFF), so keep
    deep recursion to small frames; nothing checks for overflow.
  - **Self-calls and arguments.** In `f(a, b)` called from `f` the arguments are stored into the caller's own
    parameter slots; an argument whose slot a later argument still reads (`hanoi(n - 1, from, via, to)` stores `to`'s
    slot before reading `to`) waits on the stack like a parked argument. The return value comes back in R3, which
    the restore does not touch.
  - **Rules.** `main` cannot be recursive (it clears the BSS on entry; compile error). The address of a local of a
    recursive function (`&x`, a local array, a member of a local struct) cannot be passed as an argument to a call
    inside its cycle: the callee's activation of the same function would reuse the slot (compile error "the address
    of local 'x' is passed to f()"). Passing it to a function outside the cycle is fine (`fill(buf)`, `strlen(buf)`).
    Not detected: such an address stored in a variable and used after a call into the cycle, or returned. Local
    arrays and structs in recursive functions are allowed; they are saved and restored whole on every call inside the
    cycle (the cost above, per byte). A syscall handler must still not `sys()` itself (the call graph cannot see
    through SYSTAB).
- **Calls**: the caller evaluates each argument into R3 and stores it straight into the callee's parameter slot,
  then `JSR` (inside a recursive cycle wrapped in the frame save/restore above). When a later argument's evaluation could itself run the callee (`f(x, g())` where `g` calls `f`)
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
- **Syscalls** (2026-09-23): `sys(n, a, b, c)` is how a program reaches Y1/OS (`os/README.md`). The arguments
  (any of a, b, c may be left out) are evaluated into the parameter words SYSARG0..2 at $0F06/$0F08/$0F0A
  (`STR R3,addr`); an argument evaluated later that calls anything (it could run a `sys()` of its own) makes the
  earlier ones wait on the stack, exactly as a user call's arguments do. Then the entry word `SYSTAB + 2n`
  ($0F14 + 2n, n = 0..21) is loaded into R7 (`LDR R7,addr` for a constant n; a computed n is shifted, added and
  dereferenced) and `JSRUR R7` calls the handler; the result word SYSRES ($0F0C) comes back in R3 as an int.
  `funcaddr(f)` is the address of function `f` as an int (`MVIW R3,f_label`): the OS installs its handlers with
  `pokew(SYSTAB + 2 * n, funcaddr(h_open))`. A function named in `funcaddr()` is an entry point: it and whatever it
  calls are kept in the image even when nothing calls them directly (the dead-function pass starts from `main` and
  every such function). The call-graph check cannot see through the table: an OS handler must not `sys()` itself.
  `tests/compiler/syscall.c` installs its own handlers and calls them, constant and computed numbers, 1..4
  arguments, nested `sys()` in arguments. Constant folding got a fix the same day: the operator table was an eager
  dictionary that evaluated `a // b` for every fold, so any constant expression with a zero right operand
  (`SYSTAB + 2 * SYS_OPEN`) crashed the compiler.
- Never emitted: `LDTVR STTVR OUTVR BR16Z BR16NZ BRNC` (no microcode), `BRVR` (not needed yet),
  negative numbers (the assembler silently drops the sign), labels over 29 characters (crash the assembler), or
  two labels differing only in case (the assembler folds case; the compiler mangles and uniquifies).

## Tests

`tests/compiler/*.c` with the expected output beside each (`.out`, `.in` for stdin, `.err` for an expected
compile error, `// y1cc: flags` on a line for per-test compiler flags); `tests/compiler/run.py` compiles, assembles, runs each on `emulator -x` and diffs. `--oracle`
regenerates the `.out` files with the HOST C compiler through `host_shim.h` (`int` = `unsigned short`, unsigned
char), so the expectations are independent of this compiler; tests marked `no-oracle` (peek/poke, struct layout,
byte order) carry hand-written expectations. 16 programs, 16/16 on 2026-09-23 (~3 s; `syscall.c` joined that day);
21 since 2026-09-24 with the recursion tests: `rfact.c` (fact, fib, Ackermann with a recursive call in an argument,
depth 50 with int and char locals), `rmutual.c` (even/odd, a three-function cycle, Hofstadter F/M), `rlocals.c`
(local arrays and structs in a recursive function through `rt_fsave`, an odd-sized frame, Hanoi, a pointer to a
local handed to a non-recursive helper), `rcalc.c` (a recursive-descent expression evaluator over a string), and
the compile errors `recurse.c` (address of a local into the cycle) and `rmain.c` (recursive main); all pass on both
emulators (`tests/ucemu/run.py`); 22 with `adjstr.c` (an error test, from the twin work below). `make check` runs them.

`tests/compiler/diffcheck.py [--base REV]` is the differential proof for a compiler change: it compiles the whole
corpus (`tests/compiler/corpus.py`: the compiler tests with `--boot`, plain, `--os` and `--no-brur`, three
`--vector` builds, the bench sources, `os/y1os.c`, every `/BIN` command, `tests/os/*.c`, and since the twin
`c/target.c` — 121 compiles on 2026-09-24) with an old `y1cc.py` from git and the working one and diffs the assembly
(the header's timestamp masked). Against c847a97 (the last compiler without recursion): 100 identical, 17 that only
the new one compiles (the recursion tests and y1cc.c), 3 expected errors, 1 that crashed the old one (`adjstr.c`),
0 different. `tests/compiler/twin.py` is the same kind of proof between y1cc.py and its C twin (below).
The same images also run under the monitor on the emulator (`emulator -m -f prog.img`, then `G3000`): the program's
output appears after `GO ADDRESS:` and the monitor's banner follows when main returns (hello and fib tried 2026-09-22).

Sizes on 2026-09-22 (code + data + runtime, bytes): hello 111, io 722, sieve 862, chars 893, calls 948,
globals 966, fib 1045, structs 1398, arrays 1446, control 2356, arith 2339.

## y1cc.c — the C twin (2026-09-24)

`c/y1cc.c` is `y1cc.py` rewritten in C, function by function (the same names where C allows), so that a change to
one carries over to the other. It is written in the **intersection of C89 and the y1cc subset**, so it builds three
ways:

```
make -C software/compiler/c              # ./y1cc on the Mac: cc -std=c89 -Wall -Wextra -pedantic, no warnings
                                         #   (plus ./y1cc16, the 16-bit check build, below)
software/compiler/c/y1cc prog.c -o prog.asm [--org N] [--boot] [--vector] [--no-brur] [--os] [-l]
make -C software/compiler/c target       # y1cc.py compiles y1cc.c as a Y1/OS program; its size (below)
python3 tests/compiler/twin.py [--16]    # the twin test (make check, make cc-test)
```

| file | what |
|---|---|
| `c/y1cc.c` | the compiler, 3,122 lines: lexer, parser, AST, code generator, peephole, runtime text, driver (`y1cc_main`) |
| `c/io.h` | the host interface: everything outside y1cc.c goes through these twelve functions |
| `c/host_io.c` | io.h on the Mac (stdio, `getcwd`, `main(argc, argv)`), plain host C |
| `c/target_io.c` | io.h on Y1/OS over `os/lib_fs.c` (the file syscalls), in the subset; compiled, not yet run |
| `c/host.c`, `c/target.c` | the two translation units: limits + (target I/O) + `#include "y1cc.c"` |
| `c/limits_host.h`, `c/limits_y1.h` | the table sizes (#define numbers only: y1cc's preprocessor has no `#if`) |
| `c/host16.c` | the check build `y1cc16`: `#define int unsigned short` and `-funsigned-char` |

**The I/O interface** (`c/io.h`): `io_argc()`, `io_arg(i, buf, max)` (the command line); `io_open(path)`,
`io_getc(h)` (0..255, **256** at the end), `io_close(h)` (source files); `io_find(name, from, out, max)` (an
`#include`: beside the including file, then the library directory, with a canonical path so each file is included
once); `io_create(path)`, `io_put(section, c)`, `io_finish()` (the output in three sections — code, data, uninitialised
data — concatenated at the end; the host writes the file only when the compile succeeded, as y1cc.py does);
`io_out(c)` (the `-l` summary), `io_fail(msg)` (message, exit status 1), `io_date(buf)` (the header's timestamp). All
plain ints and char buffers, no negative numbers. On the host the library directory is `$Y1CC_LIB`, else `../lib`
beside the executable (= `software/compiler/lib`, where y1cc.py looks). On Y1/OS (`target_io.c`) the command line is
the `argstr()` tail, `#include` falls back to `/LIB`, code goes straight into the output file while data and BSS wait
in RAM (Y1/OS has one write handle), there is no clock (the date is `0000-00-00 00:00`) and `io_fail` HALTs (no exit
syscall yet).

**Rules it keeps** (so it means the same compiled by `cc` and by y1cc): `int` is 16-bit unsigned on the YACC1 and
32-bit signed on the Mac, so every value stays in 0..65535 — no negative numbers or -1 sentinels ("none" is 0, the
end of a file is 256), wrapping arithmetic is masked (`& 65535`, products through `mul16`), no loop runs to 65535;
`char` is unsigned there and signed here, so bytes read back from char arrays are masked with `& 255`; no casts, no
`long`, no function pointers (y1cc.py's lambdas became mode numbers), no `goto`, no `do ... while`, no struct at all
(parallel arrays), no adjacent string literals, no `#if`; every local declared at the top of its function (y1cc does
not see declarations inside a `switch` body); every function defined or prototyped before use (the prototype block
at the top). Recursion is y1cc's (since 2026-09-24): the parser and the code generator are recursive, and no address
of a local ever goes into a recursive call — every buffer that crosses a call is a global, and functions that return
two or more values leave them in globals (`fv`, `tb`/`tp`, `sl_*`, `sm_*`...), as their callers read them at once.
**`y1cc16`** (`host16.c`: `int` = `unsigned short`, unsigned `char`, the same trick `tests/compiler/host_shim.h`
plays for the test oracle) runs the whole corpus through the YACC1's integer types on the Mac: arithmetic is still
promoted to the host's `int`, so it does not model every 16-bit wrap, but it found a real bug on its first run —
`for (i = k; i <= 65535; i++)` (emitting up to three `DECR`s) never ends with a 16-bit `int`.

**How it differs inside** (the output does not): y1cc.py lexes the whole file and keeps every line of code until
the end; y1cc.c streams both. The lexer reads through a 4-byte lookahead per open file (an `#include` pushes a
file) and the parser looks at most 2 tokens ahead and 1 back; the peephole pass keeps only the lines that a later
line can still change — a run of `BR` lines, which a following label can delete (the four rules delete or replace
only the NEW line otherwise, so the rewrite system is confluent and the streaming result equals y1cc.py's
repeat-until-no-change passes). The whole program's AST is kept (as in y1cc.py: the call graph, dead functions and
recursion need every body before any code is generated) and the nodes made while generating a function are freed
after it. Generated labels (`Lend12`) are a number plus a prefix remembered per function; the labels derived from
names (`g_x`, `f_main`, `main_i`) are the only ones checked for case-folded uniqueness (they always contain `_`, the
generated ones never do). Where the two can still disagree, on invalid or odd input only: with several errors in a
program y1cc.c may report a different one first (it lexes as it parses); source must be ASCII (Python decodes
UTF-8, y1cc.c sees bytes); a `#define` value over 65535 is masked at once; `*x` of a non-pointer does not go to
pointer depth -1.

**Limits** (`limits_host.h`, each overflow is a clean "y1cc: too many ... (NAME)" error): 4,000 names (32,000
bytes), 2,000 distinct string literals (32,000 bytes, 1,024 per literal), 40,000 AST nodes, 3,000 variables, 512
functions, 64 structs with 512 members, 4,000 derived labels (40,000 bytes), 2,000 generated labels per function,
8 levels of `#include` and 64 files, 64 nested loops, 512 cases per switch. Enough for the corpus and for y1cc.c
itself. `limits_y1.h` is a small illustrative set for the Y1/OS build (about 41K of tables): a native compiler will
size its tables per pass.

**The twin test** `tests/compiler/twin.py` compiles the whole corpus (`tests/compiler/corpus.py`, 121 compiles on
2026-09-24: the compiler tests in four option sets, three `--vector` builds, the bench sources, `os/y1os.c`, every
`/BIN` command, `tests/os` programs, and `c/target.c` — y1cc.c compiling itself) with both compilers and requires
identical assembly (the header's timestamp masked), identical `-l` summaries and identical error messages for the
expected-error tests. 2026-09-24: **117 programs identical, 4 identical errors, 0 different**, with `y1cc` and with
`y1cc16`. It runs in `make check` and `make cc-test`. **`tests/compiler/twinfuzz.py [N] [--seed S]`** adds random
programs (every operator, type and statement shape of the subset mixed, recursion, switch tables, struct members,
pointer arithmetic, initialisers, `--boot`/`--os`/`--no-brur`/`--vector`) and a fixed list of 60 invalid programs
whose error messages must match: 2026-09-24, seeds 1-3, 1,400 random programs identical (or the same error) and 60 of
60 error messages, 0 different. Writing the twin found two y1cc.py crashes, now fixed in y1cc.py: a string literal
right after an expression (`puts("a" "b")`, a Python `TypeError`; now the ordinary "expected ')'" error,
`tests/compiler/adjstr.err`) and `0x` without digits (a `ValueError`; now "bad hex constant").

**y1cc.c compiled by y1cc.py** (`make target`, the proof that it is in the subset): no errors, 45,173 lines of
assembly, **code 75,445 + data 6,900 = an 82,345-byte image** (plus about 41K of tables with `limits_y1.h`), 2.5
times the 32K program area ($5000-$CFFF) for the image alone and over the 64K address space; so the assembler cannot
take it (its label table holds 1,000 labels, this has 3,817; and every label past $FFFF is an error), and the bytes
are counted from the assembly with `yacc1.def`'s instruction lengths — a count checked against the assembler's
"Object Code" on all 116 corpus programs that assemble (exact on every one). Where the code goes: the code generator
56,040 bytes (`gen_call` 4,484, `gen_bin` 2,821, `gen_program` 2,793, `gen_expr` 2,257, `walk` 2,043, `gen_stmt`
1,988, `const_data` 1,729, `type_of` 1,513, `gen_cond` 1,404), the parser 8,749, the lexer 6,549, the runtime text
(`emit_runtime`) 2,257, the Y1/OS I/O with `lib_fs.c` 1,603; the data is mostly message and instruction strings.
Recursion costs about 4,100 bytes of it (124 call sites through `rt_fsave`/`rt_frest`, 190 inline word saves). That is
about 24 bytes of code per line of C.

**The road to native** (BACKLOG "C compiler"):
1. *Self-compile on the host* — done: y1cc.c compiling `target.c` gives the same assembly as y1cc.py (the twin
   corpus), so the C compiler already compiles itself, on the Mac.
2. *Split into passes* that each fit the 32K area with their tables: e.g. pass 1 lexer + parser writing the AST (or a
   token file) to the disk (~15K of code), pass 2 the call graph / layout, pass 3+ the code generator — which alone
   is 56K today and must itself be split (expressions / statements and data / runtime text), or shrunk: the runtime
   text and messages can be data files, and y1cc's own code is 2-3x hand assembly (peephole work pays twice).
3. *A bigger stack*: the recursive parser and generator with frame saves need far more than the monitor's 768
   bytes ($0C00-$0EFF); a native pass must move R1 to a region of its own.
4. *Y1/OS support*: an exit syscall (for `io_fail`), and temporary files or the pass structure instead of RAM for the
   data sections (one write handle).
5. *The on-target assembler* (BACKLOG wave 3): the compiler emits assembly text; the machine needs an assembler
   (and one that takes more than 1,000 labels) before a program compiled on it can run.

## Not done yet (BACKLOG "C compiler")

Running a compiled program on the real machine needs a way to load RAM (the monitor's E-command loader on the
backlog, or the bus tester with the CPU off); signed types; peephole
work (the code is straightforward, roughly 2-3x what hand assembly would be); the P8X-side libraries. (`switch`
done 2026-09-22, recursion 2026-09-24.)

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
