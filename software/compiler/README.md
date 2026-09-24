# software/compiler — y1cc, a C cross-compiler for the YACC1

`y1cc.py` (Python 3, no dependencies) compiles a small C subset to YACC1 assembly for `software/assembler`
(RC/asm with `yacc1.def`). Written 2026-09-22; the first C compiler the machine has had. Since 2026-09-24 it has a
twin in C, `c/y1cc.c` (below), written in the subset itself and producing the same assembly byte for byte: the first
step towards a compiler that runs on the machine. The same day that twin was split into nine programs, `c/cc1_lex.c`
.. `c/cc9_final.c` ("The multi-pass compiler", below), each of which fits the Y1/OS program area with its tables and
its stack, and which together still produce the same assembly. `y1cc.py` stays the reference and the bootstrap. The front end (lexer,
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
software/compiler/c/y1ccp prog.c -o prog.asm --boot             # the multi-pass compiler (cc1..cc9): the same again
python3 tests/compiler/twin.py [--chain]                         # y1cc.py vs the C twin (vs the passes) over the corpus
python3 tests/compiler/passes.py                                 # each pass against the Y1/OS program area
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
`c/target.c` — 121 compiles on 2026-09-24; 130 with the nine passes of the multi-pass compiler as Y1/OS programs,
`c/target/*.c`, the same day) with an old `y1cc.py` from git and the working one and diffs the assembly
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
| `c/io.h` | the host interface: everything outside y1cc.c goes through these twelve functions (five more for the passes, below) |
| `c/host_io.c` | io.h on the Mac (stdio, `getcwd`, `main(argc, argv)`), plain host C |
| `c/target_io.c` | io.h on Y1/OS over `os/lib_fs.c` (the file syscalls), in the subset; compiled, not yet run; the three output sections, which only y1cc.c uses, are in `c/target_sec.c` (so the passes do not carry its buffers) |
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
program y1cc.c may report a different one first (it lexes as it parses; and with bad `funcaddr()`s in several
functions it reports them in function order, where y1cc.py takes the order of the first definitions, and in one
function the first in the text where y1cc.py puts a malformed one first - the multi-pass compiler, below, follows
y1cc.py in all of these); source must be ASCII (Python decodes UTF-8, y1cc.c sees bytes); a `#define` value over
65535 is masked at once; `*x` of a non-pointer does not go to pointer depth -1; a function defined twice (below).

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
`y1cc16`; 126 and 4 once the nine passes joined the corpus. It runs in `make check` and `make cc-test`; `--chain` and
`--chain16` run the same comparison against the multi-pass compiler (below). **`tests/compiler/twinfuzz.py [N] [--seed S]`** adds random
programs (every operator, type and statement shape of the subset mixed, recursion, switch tables, struct members,
pointer arithmetic, initialisers, `--boot`/`--os`/`--no-brur`/`--vector`) and a fixed list of 60 invalid programs
whose error messages must match: 2026-09-24, seeds 1-3, 1,400 random programs identical (or the same error) and 60 of
60 error messages, 0 different. Writing the twin found two y1cc.py crashes, now fixed in y1cc.py: a string literal
right after an expression (`puts("a" "b")`, a Python `TypeError`; now the ordinary "expected ')'" error,
`tests/compiler/adjstr.err`) and `0x` without digits (a `ValueError`; now "bad hex constant").

**y1cc.c compiled by y1cc.py** (`make target`, the proof that it is in the subset): no errors, 45,173 lines of
assembly, **code 75,445 + data 6,900 = an 82,345-byte image** (plus about 41K of tables with `limits_y1.h`), 2.5
times the 32K program area ($5000-$CFFF) for the image alone and over the 64K address space; so the assembler cannot
take it (every label past $FFFF is an error; its label table held 1,000 labels until 2026-09-24 and crashed on this
one's 3,817 - it holds 8,191 now and says so when full), and the bytes
are counted from the assembly with `yacc1.def`'s instruction lengths — a count checked against the assembler's
"Object Code" on all 116 corpus programs that assemble (exact on every one). Where the code goes: the code generator
56,040 bytes (`gen_call` 4,484, `gen_bin` 2,821, `gen_program` 2,793, `gen_expr` 2,257, `walk` 2,043, `gen_stmt`
1,988, `const_data` 1,729, `type_of` 1,513, `gen_cond` 1,404), the parser 8,749, the lexer 6,549, the runtime text
(`emit_runtime`) 2,257, the Y1/OS I/O with `lib_fs.c` 1,603; the data is mostly message and instruction strings.
Recursion costs about 4,100 bytes of it (124 call sites through `rt_fsave`/`rt_frest`, 190 inline word saves). That is
about 24 bytes of code per line of C.

**The road to native** (BACKLOG "C compiler"; where it stands in "The multi-pass compiler", below):
1. *Self-compile on the host* — done: y1cc.c compiling `target.c` gives the same assembly as y1cc.py (the twin
   corpus), so the C compiler already compiles itself, on the Mac.
2. *Split into passes* that each fit the 32K area with their tables — done 2026-09-24: nine passes, below.
3. *A bigger stack* — measured, placed, not built: below, "The stack".
4. *Y1/OS support*: an exit syscall (`io_fail` and `io_done` HALT today), files over 64K, a way to run nine
   programs in a row, `/LIB/y1ccrt.txt` on the disk: below, "What is left for native".
5. *The on-target assembler* (BACKLOG wave 3): the compiler emits assembly text; the machine needs an assembler
   (the host assembler's label table now holds 8,191, enough for any single pass) before a program compiled on it can run.

## The multi-pass compiler (2026-09-24)

y1cc.c compiled by y1cc.py is an 82K image; the Y1/OS program area is 32K ($5000-$CFFF) for a program's image, its
uninitialised data (the tables, and every function's static frame) and its stack. So the compiler is split into
nine programs run one after the other, each passing the next its work in files. Each is written in the y1cc subset
(the rules of y1cc.c, above: C89 on the Mac with `-Wall -Wextra -pedantic` clean, a 16-bit check build, compiled by
y1cc.py), each is y1cc.c's code for its part of the work - the same functions under the same names wherever the part
is the same - and **the nine chained produce y1cc.py's assembly byte for byte**.

```
make -C software/compiler/c                                     # cc1..cc9, cc1_16..cc9_16, the drivers y1ccp, y1ccp16
software/compiler/c/y1ccp prog.c -o prog.asm [--org N] [--boot] [--vector] [--no-brur] [--os] [-l]   # as y1cc.py
Y1CCP_KEEP=dir software/compiler/c/y1ccp prog.c ...             # the intermediate files kept in dir (dir/w.*)
python3 tests/compiler/twin.py --chain [--16 | --chain16]        # the corpus: y1cc.py against the chain
python3 tests/compiler/twinfuzz.py 500 --seed 1 --chain          # random programs and the error list, likewise
python3 tests/compiler/passes.py [-v]                            # the sizes, the stack, the capacity (below)
```

`y1ccp` (`c/y1ccp.c`, host C) takes y1cc.py's command line, makes a temporary directory `W`, runs `cc1 W <the
command line>`, then `cc2 W` ... `cc9 W`, stops at the first pass that fails (that pass printed the message) and
removes the files. On Y1/OS the nine would be run in turn by the shell (not yet possible: "What is left", below).

### The passes

| pass | y1cc.c's part | reads | writes |
|---|---|---|---|
| `cc1_lex.c` | `y1cc_main`'s options, the preprocessor (`#define`, `#include`), the lexer | the source, its includes | `W.opt` options, `W.tok` tokens, `W.nam` names, `W.lit` string literals |
| `cc2_parse.c` | the parser, constant folding | `W.tok` | `W.ast` one record per top-level declaration, `W.typ` types |
| `cc3_decl.c` | `gen_program` to the check for `main()`: structs, the function table, the globals, their data | `W.ast` (3 readings), `W.typ`, `W.nam`, `W.lit` | `W.dat` the global data (a stream), `W.s1` symbols |
| `cc4_calls.c` | `build_reach` (main must not be recursive), the `funcaddr()` roots, the live functions | `W.ast` (2), `W.s1`, `W.nam` | `W.cg` live functions + the reach matrix |
| `cc5_layout.c` | the labels (`ulabel`) of the globals, functions, parameters and locals, `layout_func`, the frames | `W.ast` (2), `W.s1`, `W.cg`, `W.typ`, `W.nam` | `W.sym` symbol tables, `W.lab` the labels' owners |
| `cc6_stmt.c` | `compile_func`, `gen_stmt`, `gen_switch`'s case labels: every expression becomes a *hole* | `W.ast` (2: main first), `W.sym` | `W.st` a stream: labels, branches, holes |
| `cc7_sema.c` | the analysis `gen_*` asks of every node: `fold`, `type_of`, `type_lval`, `vinfo`, `struct_member`, `sizeof`, the call graph walks, `escapes` | `W.st`, `W.sym`, `W.cg`, `W.lit` | `W.se` the stream, every hole's tree annotated |
| `cc8_emit.c` | `gen_expr`, `gen_assign`, `gen_bin`, `gen_cond`, `gen_call`...: each hole's code | `W.se`, `W.sym` | `W.em` the stream, instruction records |
| `cc9_final.c` | the text: labels numbered, the macros (`add_const`, `branch_rel`, `frame_save`, `switch_table`...) expanded, the peephole, strings at first use, the runtime (from `lib/y1ccrt.txt`), the three sections | `W.opt`, `W.dat`, `W.em`, `W.lab`, `W.nam`, `W.lit`, `W.sym` | the `.asm` file, the `-l` line |

Shared source: `pdefs.h` (every number: token and node kinds, record codes, mnemonics, macros...), `pcommon.c`
(strings, errors, the file primitives: bytes, words, strings, whole table columns), `pnames.c` (the names' text),
`past.c` (reading `W.ast`), `plabel.c` (a label's text from its owner); the I/O is `io.h` as for y1cc.c, grown by
`io_wopen`/`io_wput`/`io_wclose` (one file written at a time, as Y1/OS allows), `io_done` and `io_lib`. The builds:
`hostp.c` / `host16p.c` (a pass on the Mac and its 16-bit check build, `-DPASS="cc1_lex.c"`), `plim_host.h` (the
Mac's table sizes), `ylim/NAME.h` and `target/NAME.c` (each pass's Y1/OS table sizes and its Y1/OS translation unit,
as `target.c` is y1cc.c's), `stackprobe.c` (passes.py's stack probe), `lib/y1ccrt.txt` (the runtime helpers' text).
Each file's header comment gives its formats in full; the ideas that make the split exact:

- **The whole-program work never loads a function body.** cc2 writes into each function's record the calls it makes
  (in the order y1cc.c's `walk()` meets them) and its declarations (in `collect_decls()` order), so the call graph
  (cc4) and the layout (cc5) read short lists; only cc6 loads a body, one function at a time.
- **Holes.** The statement pass allocates its labels and writes the branches around each expression, and in the
  expression's place a hole holding the expression's tree (renumbered 1..n: the biggest in the corpus has 31
  nodes). cc7 adds to every node what the code generator will ask about it, cc8 replaces the hole by the code. A
  generated label is a symbol (cc6's from 1, cc8's from 32768) announced by an `R_ALLOC` record at the moment
  y1cc.c's `lbl()` would have run; cc9 numbers them in stream order, so `Lend12` gets the same 12.
- **Errors come out in y1cc.py's order.** y1cc.py lexes the whole source first (so cc1 stops at a lexer error, as
  it does), then parses, then generates each function's statements and expressions in one walk: a statement error
  (a `break` outside a loop) comes after any error in an expression before it. So cc6 writes a statement error into
  its stream and stops (cc8 raises it once the expressions before it are done), and cc7 never stops at an error: it
  records it with the attribute ("poisoned": code and names) and cc8 raises it when its code generator asks for that
  attribute, which is when y1cc.py would have failed. The fuzzer's error list (60 programs), every random program
  that fails, and a list of programs with two errors in different passes give the same message as y1cc.py - better
  than y1cc.c, which lexes as it parses and can report a parse error before a lexer error further on.
- **No label text is kept.** A label is y1cc.c's `ulabel(want)`: the want sanitised, cut to 29 characters, or to 24
  and `_n` after n labels equal to it ignoring case. cc5 remembers each label's owner and n and makes the text again
  when it compares (`plabel.c`); cc9 does the same when it prints. The globals' labels moved from the declarations to
  cc5, in the same order.
- **Fixed sequences are macros.** cc8 writes `M_ADDK k`, `M_BREL rel label ...`, `M_FSAVE var bytes`,
  `M_SWITCH ...` and cc9 expands them with y1cc.c's code (and allocates their labels then, in the same order).
- **Addresses keep y1cc.c's text**: a label and its `+k` terms as written (`g_s+2+4`, not `g_s+6`), a constant
  index times the element size as a 32-bit number (`g_a+131070` for `a[-1]` of an int array, as y1cc.py prints it).
- **Column files.** The symbol tables go to and from the files a column at a time (`warr`/`rarr`), and each pass
  reads only the columns it needs: a statement per field costs y1cc's code model far more.

Found on the way: y1cc.c's `switch_table` counts `v` from lo to hi, which never ends in 16 bits when hi is 65535;
cc9 counts the table's entries instead. Known differences from y1cc.py, both on programs y1cc.py cannot compile
into working assembly, none in the corpus or produced by the fuzzer: an object over 65,535 bytes (`int a[40000]`;
the address space is 64K) - y1cc.py prints its size whole (`DS 80000`, `sizeof` 80000), the passes, written for
16-bit ints, mod 65536 (14464), as y1cc16 does (y1cc.c on the Mac prints it whole); and a function defined twice -
y1cc.py lays out both definitions and compiles the last one twice under the second label (`f_f_1:` twice: the
assembler rejects it), y1cc.c and the passes compile it once as `f_f`. (Better: y1cc.py reports the redefinition as
an error, like a global declared twice - BACKLOG.)

### Sizes against the program area

`tests/compiler/passes.py` compiles each pass with y1cc.py as a Y1/OS program (`c/target/NAME.c`: its Y1/OS table
sizes `c/ylim/NAME.h`, the Y1/OS I/O layer `c/target_io.c`, the pass), assembles it with the host assembler (0
errors; the label count), counts code and data (checked against the assembler's Object Code) and the uninitialised
data (tables, static frames), and measures the stack (below). 2026-09-24, in bytes:

| pass | code | data | image | tables | stack | total | free of 32,768 | labels |
|---|---|---|---|---|---|---|---|---|
| cc1 lex | 12,408 | 1,427 | 13,835 | 17,771 | 90 | 31,696 | 1,072 | 878 |
| cc2 parse | 16,893 | 696 | 17,589 | 11,733 | 1,202 | 30,524 | 2,244 | 967 |
| cc3 decl | 8,961 | 977 | 9,938 | 12,143 | 86 | 22,167 | 10,601 | 528 |
| cc4 calls | 5,792 | 430 | 6,222 | 12,131 | 84 | 18,437 | 14,331 | 382 |
| cc5 layout | 8,908 | 540 | 9,448 | 17,003 | 84 | 26,535 | 6,233 | 578 |
| cc6 stmt | 9,017 | 648 | 9,665 | 15,949 | 592 | 26,206 | 6,562 | 523 |
| cc7 sema | 16,974 | 440 | 17,414 | 14,613 | 195 | 32,222 | 546 | 910 |
| cc8 emit | 24,514 | 1,422 | 25,936 | 3,597 | 424 | 29,957 | 2,811 | 1,283 |
| cc9 final | 16,918 | 1,809 | 18,727 | 13,697 | 100 | 32,524 | 244 | 1,160 |

Every pass fits. The nine together are 120,385 bytes of code against y1cc.c's 75,445: each carries the shared
utilities and file code, and the work split across passes costs its intermediate records. What made them fit: the
runtime helpers' text moved into `lib/y1ccrt.txt` (about 3K out of cc9); the call graph and the layout read the call
and declaration lists instead of bodies (they had to hold whole functions); the labels made again from their owners
(cc5 and cc9 each held all the label text, 5-8K for the bigger programs); the symbol and tree files a column at a
time (1.5K of code each in cc7 and cc8); cc1 passing on only the names that become tokens (the pass sources intern
about 700 names, about 360 of them `#define`s that later passes never see); cc7's name lookups hashed instead of an
array per name.

**The table sizes** (`c/ylim/`; `c/plim_host.h` has the Mac's, far larger) are set so that the whole corpus except
y1cc.c, and the nine passes' own sources, compile: 760 names in cc1 (5,400 bytes of text, `#define`s included), 400
identifiers after it (2,600 bytes), 170 functions, 380 variables (128 globals), 160 string literals (1,800 bytes),
920 AST nodes in one function (the biggest function of the passes, in cc8, has 856), 40 nodes in one expression
(the corpus has 31), 200 generated labels in one function, 64 cases in a switch. passes.py builds the passes on the
Mac with exactly these sizes (only the path pool is larger: Mac paths are absolute) and compiles the corpus through
them: **125 identical to y1cc.py, 4 identical errors, and y1cc.c the one program that does not fit** (833 names,
130K of source). So the chain can compile itself: each of the nine passes, compiled by the nine, is identical to
what y1cc.py makes of it.

### The stack

y1cc gives every local a fixed address; the stack holds only return addresses, pushed operands and parked
arguments, and the frames saved around a call inside a recursive cycle. passes.py measures how deep that goes:
it reads, in each pass's y1cc assembly, the bytes each function has on the stack at each of its calls (return
address included; a runtime helper, the Y1/OS I/O layer and a syscall are counted there, a syscall with an allowance
of 64 bytes for the OS, a ROM routine 16), builds the pass on the Mac with `-finstrument-functions`
(`c/stackprobe.c`), and replays the YACC1 stack on every call while the corpus and the passes' sources compile.
The deepest points are the "stack" column. They grow with nesting: about 144 bytes per level of parentheses in cc2
(its recursive descent: `((((1))))` 12 levels deep takes cc2 to 2,004 bytes), 62 per level of operators in cc8
(`x + (x + (...))`), 28 in cc7, 16 in cc6; the other passes do not recurse on the input.

*Where it goes* (BACKLOG step 2, not built): at the top of each pass's own program area, growing down from $CFFF
towards its tables, which end at $5000 + image + tables; the "free" column is the room beyond the deepest point
measured (cc2: about 15 more levels of parentheses than the corpus uses, cc8 about 45 levels of operators). Not the
monitor's $0C00-$0EFF: that 768 bytes is shared with the shell that runs the program and with every syscall, and
cc2 alone needs 1,202 on the corpus. Two ways to get there, neither done: (a) y1cc takes `--stack ADDR`: main saves
the caller's R1, loads ADDR and puts the old R1 back before it returns (a few bytes, only when the option is given;
a change to y1cc.py, so Ken's decision); (b) Y1/OS's `run` gives every program the top of the program area as its
stack (simpler, but a /BIN command whose data reaches $CFFF would then collide with it).

### What is left for native

- **Files over 64K.** Y1/OS keeps a 16-bit position per handle. 111 of the corpus's 125 compiles keep every
  intermediate file and the output under 64K; 14 do not: y1os.c (`W.se` 174K, its assembly 152K), md.c, awk.c,
  grep.c and vi.c (their `W.se`, 75-88K: the annotated trees take 43 bytes a node, a tighter format would bring these
  four under) and the passes compiling themselves (their assembly 68-251K). Either Y1/OS grows 32-bit positions (the
  P8XFS v2 entry already has a 32-bit length), or the passes write a file per function.
- **Open files.** Y1/OS has four handles, one of them the file being written: cc1 can keep only three sources open,
  so an `#include` nested deeper (the /BIN commands nest five: cat.c, lib_stdin.c, lib_globx.c, lib_fs.c, lib_abi.c) needs
  `target_io.c` to close the outer file and read up to its position again when the inner one ends.
- **An exit syscall** (`io_fail` and `io_done` HALT today), **a way to run nine programs in a row** (a shell script
  or a small driver; there is no exec), `lib/y1ccrt.txt` on the disk as `/LIB/Y1CCRT.TXT`, room on the disk for the
  intermediate files (cc8's source compiling itself: 740K, of which `W.se` 231K and the assembly 251K), and the
  stack (above).
- **Then** run each pass on the emulator under Y1/OS (`target_io.c` is compiled, never run), then the chain; then the
  on-target assembler (BACKLOG wave 3: cc8, the biggest pass, has 1,283 labels) and the code size work (every byte
  y1cc saves shrinks the passes too, and cc7 and cc9 are within 600 bytes of the limit, cc1 within 1.1K).

**y1cc.c stays** as the single-program C twin: it is what the passes were cut from, `twin.py` keeps it identical to
y1cc.py, and it is the quicker program to read. A change to y1cc.py now has two C counterparts to follow it; once
the passes run on the machine, y1cc.c can go.

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
