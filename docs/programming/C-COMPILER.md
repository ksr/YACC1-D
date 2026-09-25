# y1cc — the C cross compiler for the YACC1

What C the compiler accepts, how the generated code works, how to build, run and test a program, and what to watch
for. Written 2026-09-23 from the YACC1-D tree.

Sources: `software/compiler/y1cc.py` (the compiler, its docstring is the primary reference; read as of 2026-09-23 09:37, when
`sys()`/`funcaddr()` had just been added — `README.md` is the 2026-09-22 text and does not have them yet), `software/compiler/README.md`,
`software/compiler/lib/y1lib.c`, `software/compiler/bench/sizecmp.sh` and `bench/*.c`, `tests/compiler/run.py`,
`tests/compiler/host_shim.h`, `tests/compiler/*.c`, `tests/ucemu/run.py`, `os/Makefile`, `os/lib_abi.c`,
`os/commands/*.c`, `firmware/abi/README.md`, `BACKLOG.md`. The worked example in section 9 was compiled, assembled
and run on `software/emulator` on 2026-09-23.

## 1. What it is

`y1cc.py` (Python 3, no dependencies, ~1,600 lines) turns a small C subset into YACC1 assembly for the RC/asm
assembler (`software/assembler`, `yacc1.def`). Written 2026-09-22; the front end (lexer, parser, the subset) is that
of the P8X compiler `p8cc.py`, so P8X C programs port unchanged as far as the subset goes; the back end is new,
written for what the YACC1 has: an 8-bit ACC and TMP, a carry flip-flop, eight 16-bit registers with R0 = PC and
R1 = SP, byte loads/stores through any register, absolute 16-bit register loads/stores, big-endian words, and no
indexed addressing.

```
python3 software/compiler/y1cc.py prog.c -o prog.asm            # for the machine: G3000 calls main (monitor of 2026-09-22)
python3 software/compiler/y1cc.py prog.c -o prog.asm --vector   # for the monitor as burned in 2021 (G = BRVR R7)
python3 software/compiler/y1cc.py prog.c -o prog.asm --boot     # stand-alone on an emulator
cd <dir with rcasm.rc (-h) + yacc1.def> && software/assembler/asm prog -d=yacc1 > prog.lst      # -> prog.img
software/emulator/emulator -x -f prog.img                       # runs a --boot image, exits at HALT
software/ucemu/y1ucemu -x -m -f prog.img                        # the same on the microcode emulator, ROM loaded
```

Since 2026-09-24 the compiler has a twin in C, `software/compiler/c/y1cc.c`, written in the subset itself (and in
C89), which produces the same assembly byte for byte (`tests/compiler/twin.py`); its build, I/O interface, limits
and self-compiled size are in `software/compiler/README.md` ("y1cc.c — the C twin"). The same day it was split into
nine programs that each fit the Y1/OS program area, `software/compiler/c/cc1_lex.c` .. `cc9_final.c`, run in turn by
`software/compiler/c/y1ccp` with the same command line and the same output (`software/compiler/README.md`, "The
multi-pass compiler": the passes, their files, their sizes and stack against 32K). Everything below describes all three.

## 2. The language subset (`y1cc.py` docstring, `README.md`)

| | Accepted |
|---|---|
| types | `int` — **16-bit unsigned** (as in p8cc, whose `int` is used as unsigned); `char` — 8-bit unsigned; pointers; arrays `T a[N]`; `struct`/`union` used by pointer or member (no by-value struct parameters, returns or assignment); `unsigned`, `const`, `static`, `void` accepted where they make sense |
| top level | struct/union definitions; function definitions and prototypes; globals with constant initializers (numbers, chars, strings, `{lists}`, `&var` / array addresses; `[]` length inferred) |
| statements | `{ }`, declarations with initializers (several per line), `if/else`, `while`, `for(e;e;e)`, `switch/case/default`, `break`, `continue`, `return [e]`, expression statements, `;` |
| expressions | `=`, `+= -= *= /= %= &= \|= ^= <<= >>=`, `++ --` (pre/post), `?:`, `\|\| &&`, `\| ^ &`, `== != < > <= >=`, `<< >>`, `+ - * / %`, unary `- ! ~ & *`, `a[i]`, `s.m`, `p->m`, `f(args)`, `sizeof(type)` / `sizeof(expr)` (constant); literals decimal, `0x` hex, `'c'`, `"string"` |
| preprocessor | `#define NAME value` (integer or char); `#include "file"` (textual, each file once, searched beside the source then in `software/compiler/lib/`) |
| recursion | direct and mutual, since 2026-09-24 (section 4): not `main`, and not the address of a recursive function's local passed into its own cycle |
| not there | signed arithmetic (comparisons and division are unsigned), `long`, floating point, function pointers, `goto`, bit fields, `do ... while`, `#if`/`#ifdef` (every directive but `#define`/`#include` is ignored) |

`switch`: the `case` labels must be direct statements of the switch block.

Gotchas that come with the subset: compound assignment and `++`/`--` evaluate their lvalue twice (keep it free of
side effects); an unsigned loop `for (i = n; i >= 0; i--)` never ends; integer literals over 65535 are a compile
error (`tests/compiler/bigconst.err`); a recursive `main` is an error (`rmain.err`), and so is passing `&local` (or a
local array) of a recursive function to a call that can re-enter it (`recurse.err`).

## 3. Builtins

| Builtin | Code | Notes |
|---|---|---|
| `putchar(c)` | `JSR rt_putc` | the runtime's `rt_putc` is `BRDEV rt_putc_h / OUTA P2 / RET` then `JSR $FFC4` (CHAROUT): port 2 on the interpreter, the monitor's BIOS on the machine and on ucemu (one image serves both); with `--os` the Y1/OS syscall CONOUT instead |
| `getchar()` | `JSR rt_getc` → int | `INP P2` on the interpreter (0 at end of input), `JSR $FFE8` (UARTIN, which echoes) otherwise; with `--os` the syscall CONIN (its 65535 becomes 0) |
| `puts(s)` | `JSR rt_puts` | the string then `\n` (10) only |
| `peek(a)` / `poke(a,v)` | `LDAVR` / `STAVR` through R3 (R4) | byte at address |
| `peekw(a)` / `pokew(a,v)` | two byte accesses | big-endian word at address |
| `inp(port)` / `outp(port,v)` | `INP Pn` / `OUTA Pn` | port must be a constant 0..15; `outp` always uses `OUTA` so the interpreter's port-2 console sees it |
| `halt()` | `HALT` | both emulators exit in `-x` mode |
| `bios(addr, r7, acc)` → int | `MOVRR R3,R7`, ACC ← acc, `JSR addr`, R3 ← ACC | `addr` must be a constant (a BIOS vector from `os/lib_abi.c`); returns ACC |
| `call(addr)` → int | `MOVRR R3,R7 / JSRUR R7` | call a computed address (how Y1/OS runs a program); returns the callee's R3 |
| `argstr()` → `char *` | `MVIW R3,$0F40` | the command tail Y1/OS leaves at ARGBUF (up to 127 characters + NUL since 2026-09-23) |
| `sys(n, a, b, c)` → int | args to `SYSARG0..2` ($0F06/$0F08/$0F0A), `LDR R7,SYSTAB+2n` / `JSRUR R7`, `LDR R3,SYSRES` | a Y1/OS syscall (2026-09-23): n = 0..21, a constant or computed; `a`, `b`, `c` optional; the result is the full 16-bit word the handler wrote to `SYSRES` ($0F0C). A later argument that calls anything is evaluated with the earlier ones parked on the stack, so `sys(S_ADD, 100, sys(S_ADD, 20, 3))` works (`tests/compiler/syscall.c`) |
| `funcaddr(f)` → int | `MVIW R3,f_label` | the address of a defined function; how the OS fills `SYSTAB` (`pokew(SYSTAB + 2*n, funcaddr(handler))`); `f` is kept in the image even if nothing calls it directly |

The library `lib/y1lib.c` (`#include "y1lib.c"`) adds `putstr`, `putnum` (unsigned decimal), `puthex2`, `puthex`,
`strlen`, `strcmp` (0 / 1 / 65535), `strcpy`, `memset`; functions `main` never reaches are dropped
(`; dropped (never called): ...` in the output), so including it costs nothing unused.

## 4. The code model (the YACC1-specific part)

From the docstring and `README.md`, with the instructions involved:

- **R3 is the expression accumulator.** Every expression leaves its 16-bit value in R3 (chars zero-extended). R4 is
  the second operand / scratch pointer; R5–R7 are the runtime helpers' scratch (R7 also carries the string for the
  monitor's `stringout` in `bios()` calls). **R2 is never touched** (the hardware's operand-address register of
  `LDA/STA/LDT/STT/LDR/STR`; the interpreter uses a ninth register, so R2 misuse would only show on the machine).
- **Static frames, no recursion.** A global is a labelled word or byte (`g_total: DS 2`); a function's parameters
  and locals are labelled slots of their own (`main_i: DS 2`, `square_x: DS 2`). A scalar load or store is one
  3-byte `LDR R3,label` / `STR R3,label`; a frame-relative access would have cost a 16-bit add per variable because
  the ISA has no `(Rn+d)`. A `char` scalar occupies a 2-byte slot with a zero high byte so it loads with one `LDR`;
  char arrays and struct members are true bytes. A function's slots are consecutive: its frame.
- **Recursion** (2026-09-24). The call graph's reachability (`build_reach`) finds the recursive cycles. A call whose
  callee can reach back to the caller (a call inside a cycle) pushes the callee's frame on the stack before the
  arguments are stored and pops it after the `JSR` (`LDR R4,f_n / PUSHR R4` ... `POPR R4 / STR R4,f_n` inline for
  frames up to 8 bytes, the runtime pair `rt_fsave`/`rt_frest` above that); a self-call parks an argument whose slot a
  later argument still reads. Nothing else changes: functions outside a cycle compile byte for byte as before
  (`tests/compiler/diffcheck.py`). Cost, rules and the fib example: `software/compiler/README.md`.
- **Calls.** The caller evaluates each argument into R3 and stores it straight into the callee's parameter slot
  (`STR R3,square_x`), then `JSR f_square`. When a later argument's evaluation could itself run the callee
  (`f(x, g())` where `g` reaches `f`) the earlier ones are parked on the stack (`PUSHR R3` … `POPR R4`). The result
  comes back in R3; `return` is `RET`. No caller-saved registers exist: everything lives in memory.
- **Arithmetic** is byte-wise through ACC/TMP. `+ & | ^` are inline: `MVRLA R4 / MVAT / MVRLA R3 / ADDT / MVARL R3 /
  MVRHA R4 / MVAT / MVRHA R3 / ADDTC / MVARH R3` (the `do_add16` idiom, 10 bytes); constants fold into `ADDI`/`ADDIC`;
  `+1`/`-1` are `INCR`/`DECR`. `-` is a runtime call `rt_sub` (two's-complement add through `INVA`) because the
  interpreter and the hardware disagree about SUB's borrow. `* / % << >>` are runtime loops `rt_mul`, `rt_divmod`,
  `rt_shl`, `rt_shr` (R5–R7); shifts by small constants, `*2 *4 *8 *256`, `/2^k`, `%2^k` are inline.
- **Comparisons** in conditions branch straight on the comparator instructions (`BRLT/BRGT/BREQ/BRNEQ` compare ACC
  with TMP): high bytes first, low bytes only if the high bytes are equal; two char operands need one compare;
  `x == 0` ORs the two bytes and uses `BRZ`/`BRNZ`. Unsigned throughout. A relation used as a value yields 0/1.
- **The carry flag** is used only inside an `ADDT/ADDTC` (or `ADDI/ADDIC`) pair with nothing but register moves
  between, and inside a `CSHL/CSHR` pair after an explicit clear (`LDAI 0 / CSHL` in `rt_mul`). Plain shifts and
  subtracts never feed a following carry op, because the hardware loads the carry flip-flop on every shift and on
  SUB and the interpreter does not (`docs/isa/MICROCODE-REVIEW-NOTES.md` L-7).
- **Image layout**: `ORG` → `main` first → the other live functions → the runtime helpers actually used → initialised
  data and strings (`DB` as numbers: the assembler upper-cases every line) → uninitialised variables (`DS`, kept
  last, between `bss_start:` and `bss_end: DS 1`) → the stub, if any. `main` is first so the monitor's `G3000`
  (`JSRUR R7` since 2026-09-22) calls it and its `RET` returns to the command loop.
- **BSS is cleared at `main`'s entry** (20 bytes of code: a loop storing 0 from `bss_start` to `bss_end`), because
  RAM powers up random and ucemu fills it with $FF; a partially initialised array's tail is real zero bytes in the
  image, not `DS`. Both were found on ucemu on 2026-09-22 (`software/ucemu/README.md` item 3).
- **`switch`** dispatches by whichever is smaller: a compare chain (`LDTI k / BREQ` per case when every case fits a
  byte, 5 bytes each; a two-level compare, 13 bytes, otherwise) or a jump table through `BRUR` (subtract the lowest
  case, range-check, index a `DW` table, `BRUR R3`; about 49 bytes plus 2 per slot; holes go to `default`).
  `--no-brur` forbids the table. `tests/compiler/switch.c` and `switchnb.c` (`// y1cc: --no-brur`) are the same
  program both ways.
- **`--xisa`** (2026-09-24, opt-in): the instructions added to the microcode that day (`ISA-REFERENCE.md` section 4a).
  The hottest 2-byte variables go into one 256-byte **page** at the start of the BSS (`zpad: DS (256-(zpad).0)&255`
  aligns it, `zpage:` starts it) and are loaded and stored with `LDZ Rn,(label).0` / `STZ Rn,(label).0`, 2 bytes
  instead of `LDR`/`STR`'s 3. **R6 is the page register**: `main` (and every `funcaddr()` entry) starts with `MVIW
  R6,zpage`, and it is reloaded after everything that leaves compiled code (`bios()`, `call()`, `sys()`, the console
  helpers' ROM/OS calls, `rt_fsave`/`rt_frest`, which use R6 as a counter); `rt_divmod` keeps its remainder in R5.
  Which variables: every uninitialised 2-byte global and every 2-byte parameter/local is a candidate, a recursive
  function's whole frame (1..256 bytes) is one candidate (its save/restore needs it contiguous); weight = how many
  times the variables are named in the live function bodies, density = weight per word; the densest first while they
  fit. Constant adds become `ADDIW R3,k` / `ADDIW R4,k` (3 bytes instead of 8, or of 4 for a high-byte-only add) and the
  doublings `SHL16 R3` (1 byte for 8), in the compiled code and in `rt_mul`/`rt_shl`. Nothing reads the carry after
  them. Without the option the output is byte-identical to before (`tests/compiler/diffcheck.py`); y1cc.c and the
  passes produce the same `--xisa` output (`twin.py --xisa`, `--chain --xisa`).
- **Never emitted**: `BR16Z BR16NZ BRNC` (no microcode; `LDTVR STTVR OUTVR` no longer exist), `BRVR` (not needed), negative numbers
  (the assembler drops the sign), labels over 29 characters, two labels differing only in case (the assembler folds
  case; labels are mangled and uniquified).
- A **peephole** pass removes a reload after a store of the same slot, turns `STR R3,x / LDR R4,x` into `MOVRR R3,R4`,
  and drops a `BR` to the next line (`y1cc.py` `peephole`).
- **Live functions** are `main` and everything it reaches, plus any function named in `funcaddr()` (an entry point
  the OS reaches through `SYSTAB`); the rest are dropped. Constant folding was fixed 2026-09-23 (`2 * ZERO` crashed:
  the operator table evaluated `a // b` eagerly).

## 5. Command-line flags (`y1cc.py` `main`)

| Flag | Effect |
|---|---|
| `-o file` | output assembly file (default: the source name with `.asm`) |
| `--org 0xNNNN` | load address. Default `$3000`: `$1000–$1FFF` is BASIC's token buffer, which the monitor's boot clears (a program at $1000 lost its first byte before it ran, 2026-09-22), and the removed T-menu tests scribbled at $2000 |
| `--boot` | append a stub at `$F000`: `BR $F003 / MVIW R1,$0EFF / JSR f_main / HALT / END $F000`. The first branch presents an A15-high address, which releases the memory card's FORCE-ROM boot remap exactly as the monitor's first instruction does; without it every fetch stays inside $F000–$FFFF on ucemu. This is how the test suites run |
| `--vector` | layout for the monitor as burned in 2021, whose `G` was `BRVR R7` (an indirect jump through the word at the address, no return pushed): the image starts with `DW start`, then `start: JSR f_main / BR $F000` (restart the monitor) |
| `--os` | a Y1/OS program (2026-09-23; `os/Makefile` uses it for the OS and every `/BIN` command): `putchar`/`puts` go through the OS syscall CONOUT (19) and `getchar` through CONIN (17), so the shell can redirect them; `getchar` still returns 0 at the end of input; R3/R4 are kept across both (`software/compiler/README.md`). Without it the console runtime is unchanged |
| `--no-brur` | never emit `BRUR` ($AD): a `switch` is always a compare chain. For a machine whose sequencer EEPROM lacks the 2026-09-22 microcode (it was reloaded that evening, so this is now a bench-verification option) |
| `--xisa` | (2026-09-24) use `LDZ`/`STZ` (the variable page, R6 = page register), `ADDIW`, `SHL16` (section 4). Needs the 2026-09-24 microcode on the machine (`BACKLOG.md`: reload the sequencer EEPROM, then `tests/bench`); the emulators have it. Opt-in until the bench has passed |
| `--stack ADDR` | (2026-09-25) `main` runs on a stack of its own that starts at ADDR (the first byte pushed; it grows down): `main` begins `MOVRR R1,R5 / MVIW R1,ADDR / PUSHR R5` (after the `--xisa` page load) and every return from `main`, and its end, is `POPR R5 / MOVRR R5,R1 / RET`, so the caller's stack (the shell's or the monitor's, $0C00-$0EFF) is untouched and gets its SP back. Recursion's frame saves and every syscall then use the new stack. For programs that need more than the 768-byte monitor stack: the native compiler's passes are built with `--stack 0xCFFF` (`os/Makefile passes`), their tables below, the stack above. Without it the output is unchanged (`diffcheck.py`); `tests/compiler/stack.c` is its test |
| `-l` | print the line count and per-function instruction counts |

Options are recognised anywhere after the source file; the source file must be the first argument.

## 6. Running on the emulators and the machine

- **Interpreter, stand-alone**: compile with `--boot`, `emulator -x -f prog.img [< input]`; stdout is the program's
  output, stderr ends with `HALT at aaaa after N instructions, R3=xxxx`. `-l N` caps the instruction count.
- **Interpreter, under the monitor**: compile without `--boot`, `emulator -m -f prog.img`, then type `G3000` at the
  `>` prompt: the program's output appears after `GO ADDRESS:` and the prompt returns when `main` returns
  (`README.md`: hello and fib tried 2026-09-22). With the 2021 chip's monitor image use `--vector`.
- **ucemu**: `y1ucemu -x -m -f prog.img` — the ROM must be loaded because `BRDEV` branches under the microcode and the
  runtime then calls the monitor's `charout`/`uartin`; the console is the UART model, and input is echoed as the
  machine would (`tests/compiler/chars.ucout` is the expectation with that echo). `tests/ucemu/run.py` runs the
  whole suite this way, reporting steps, clocks and bus fights (0 with the current image).
- **The machine**: not yet. Loading RAM needs the monitor's E-command loader (`tools/monload.py`, `BACKLOG.md`) or the
  bus tester with the CPU held off; once loaded, `G3000` (rebuilt ROM) runs it. **To verify:** the first hardware
  checks listed in `BACKLOG.md` ("C compiler"): `rt_sub`, `rt_divmod`, the shifts' carry clear, `BRDEV` selecting the
  BIOS path.
- **Under Y1/OS**: compile with `--org 0x5000`, flatten with `tools/img2bin.py --base 0x5000`, `p8xfs.py put ...
  --load 0x5000 --exec 0x5000`; the OS `call()`s the exec address and `main`'s `RET` returns to the shell
  ([OS.md](OS.md)).

## 7. The test suite and its oracle

`tests/compiler/run.py [name ...] [--oracle] [--keep] [--xisa]` (`--xisa`: every test compiled with it):

- For each `tests/compiler/NAME.c`: compile with `--boot` (plus any `// y1cc: flags` line in the source), assemble
  in `tests/compiler/build/NAME/` (copies `yacc1.def`, writes a `-h` `rcasm.rc`), run `emulator -x -f NAME.img`
  with `NAME.in` as stdin if present, and compare stdout with `NAME.out`. A `NAME.err` file instead means the
  compiler must fail with that substring (`recurse.err`, `rmain.err`, `bigconst.err`). Prints PASS/FAIL, the object size and the
  instruction count; the build directory is removed when everything passes.
- **`--oracle`** regenerates every `NAME.out` from the **host C compiler**: `cc -w -funsigned-char -include
  host_shim.h -I software/compiler/lib NAME.c`, where `host_shim.h` makes `int` = `unsigned short`, maps
  `getchar`/`puts`/`putchar`/`halt` to stdio and `exit`. So the expectations are independent of y1cc. Tests marked
  `// no-oracle` (peek/poke, struct layout, byte order) carry hand-written expectations.
- Programs (15 on 2026-09-22, 15/15; `syscall` added 2026-09-23, no-oracle): `arith arrays bigconst(err) calls
  chars(in) control fib globals hello io recurse(err) sieve structs switch switchnb syscall`; since 2026-09-24 the
  recursion tests `rfact rmutual rlocals rcalc rmain(err)`, and `recurse.err` checks the address-of-local rule;
  `xisa` (2026-09-24, `// y1cc: --xisa`) exercises the `--xisa` code (a page that cannot hold every variable, a
  recursive frame in it, ADDIW, SHL16, R6 reloads). `make cc-test` at the
  root runs this and `tests/ucemu/run.py`. `syscall.c` is a stand-alone model of the OS's boot (`funcaddr` into
  `SYSTAB`) and of a command's `sys()` calls, including nested ones.
- The same suite on ucemu (`tests/ucemu/run.py`) uses `NAME.ucout` where the monitor's input echo changes the
  transcript (`chars.ucout`), and adds `tests/assembler/brur`.

## 8. Size against the P8X compiler

`software/compiler/bench/sizecmp.sh [p8x-tree]` compiles `bench/{fib,sieve,sort,strings}.c` (written in the subset
both compilers accept: no `++ += ?: switch #include`, one declarator per line) with `p8cc.py` + `p8xasm.py` and with
`y1cc.py --boot` + `asm`, counts bytes the same way on both sides (code + data + uninitialised variables; the 11-byte
boot stub is subtracted, the `DS` bytes added), runs the YACC1 image on the interpreter for its instruction count,
and checks its output against the host compiler's. Needs the P8X tree (default `~/Developer/p8x`). Results recorded
in `README.md` (2026-09-22 evening):

| program | P8X bytes | YACC1 bytes | ratio |
|---|---|---|---|
| fib | 1075 | 813 | 0.76 |
| sieve | 760 | 667 | 0.88 |
| sort | 1114 | 896 | 0.80 |
| strings | 1030 | 782 | 0.76 |

The YACC1 binaries are 14–26 % smaller for the same source, and the README attributes it to the instruction sets
rather than the compilers: a scalar access is one 3-byte `LDR`/`STR` and a 16-bit constant one 3-byte `MVIW`,
against p8cc's frame-relative `(P3+d)` forms and memory-word helpers; `INCR`/`DECR` and the comparator branches are
1–3 bytes where the P8X needs a memory-word operation. Rewriting the four programs with everything y1cc accepts
(`bench/full/`) saved only 1–6 % more. Speed goes the other way: a YACC1 step is two clocks and an instruction 8–30
steps, so the same work costs roughly 10× the clock cycles of the P8X (`README.md`). Test-program sizes on
2026-09-22: hello 111, io 722, sieve 862, chars 893, calls 948, globals 966, fib 1045, structs 1398, arrays 1446,
control 2356, arith 2339 bytes.

## 9. Worked example

`sum.c` (compiled, assembled and run 2026-09-23; output `sum of squares = 55`, `HALT at f009 after 2990
instructions`, 427 object bytes including the library's `putnum` and the runtime):

```c
#include "y1lib.c"
int total;
int square(int x) { return x * x; }
void main() {
    int i;
    total = 0;
    for (i = 1; i <= 5; i++) total += square(i);
    putstr("sum of squares = "); putnum(total); putchar(10);
}
```

The generated `main` (comments added; `ORG 12288` = $3000):

```
f_main:
        MVIW R3,bss_start        ; clear the BSS: g_total, main_i, the library's slots...
Lz1:    MVRHA R3
        LDTI (bss_end).1
        BRNEQ Lzg2
        MVRLA R3
        LDTI (bss_end).0
        BREQ Lzd3
Lzg2:   LDAI 0
        STAVR R3
        INCR R3
        BR Lz1
Lzd3:   MVIW R3,0                ; total = 0
        STR R3,g_total
        MVIW R3,1                ; i = 1
        STR R3,main_i
Ltop4:  LDR R3,main_i            ; i <= 5 : compare the high bytes, then the low bytes, unsigned
        MVRHA R3
        LDTI 0
        BRGT Lend5
        BRNEQ Ls7
        MVRLA R3
        LDTI 5
        BRGT Lend5
Ls7:    LDR R3,main_i            ; square(i): the argument goes straight into square's slot
        STR R3,square_x
        JSR f_square
        LDR R4,g_total           ; total += R3  (the do_add16 idiom, carry between the halves)
        MVRLA R4
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R4
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        STR R3,g_total
Lnext6: LDR R3,main_i            ; i++
        INCR R3
        STR R3,main_i
        BR Ltop4
Lend5:  MVIW R3,s8               ; putstr("sum of squares = ")
        STR R3,putstr_s
        JSR f_putstr
        LDR R3,g_total           ; putnum(total)
        STR R3,putnum_n
        JSR f_putnum
        LDAI 10                  ; putchar(10)
        JSR rt_putc
        RET
f_square:
        LDR R3,square_x          ; x * x : both operands to the runtime multiply
        MOVRR R3,R4
        JSR rt_mul
        RET
```

Then the runtime it needed (`rt_mul`: shift-and-add with `LDAI 0 / CSHL` clearing the carry before each `CSHR`
pair; `rt_divmod`: 16-step restoring division; `rt_putc`: the `BRDEV` console switch), the string as bytes
(`s8: DB 115,117,109,...`), the BSS (`g_total: DS 2`, `main_i: DS 2`, `putstr_s`, `putnum_n`, `putnum_buf: DS 6`,
`putnum_i`, `square_x`, `bss_end: DS 1`) and the `--boot` stub:

```
        ORG 61440                ; $F000
        BR 61443                 ; releases FORCE-ROM
        MVIW R1,3839             ; SP = $0EFF
        JSR f_main
        HALT
        END 61440
```

Things the example shows: every variable is a memory slot; a comparison against a constant is two byte compares; a
16-bit add is ten instructions; a multiply is a call; strings are numeric `DB`; the library functions `putstr` and
`putnum` are compiled in, the six unused ones dropped.

## 10. Known limitations and gotchas

- Recursion costs a frame copy per call inside a cycle (about 123 steps per frame word inline) and stack: 2 bytes +
  the frame per level, in the monitor's 768-byte stack ($0C00-$0EFF) unless `--stack` gives the program its own,
  unchecked either way (the instruction-level emulator's `-S` reports how deep a `--stack` program went). No reentrancy (an interrupt handler
  in C would share the static frames).
- `int` is unsigned: `<`, `/`, `%` and `>>` are unsigned; `-1` is 65535; signed compares would need bit 15 flipped
  first (`BACKLOG.md`).
- **R2** is off limits in any inline or `bios()` code that the program reaches; the compiler itself never uses it.
- **Carry**: only the compiler's own idioms are safe (section 4); a `bios()` routine may leave the flip-flop in any
  state, and on the machine every subtract and shift rewrites it.
- **Literals**: integers ≤ 65535, chars in single quotes; the assembler sees no negative numbers because the compiler
  folds them (the assembler would silently drop a sign).
- Ports in `inp`/`outp` and the address in `bios()` must be constants; `sys()`'s number may be computed (it then
  indexes `SYSTAB` at run time); `funcaddr()` takes only the name of a defined function.
- Console differences: `getchar()` on the interpreter returns 0 at end of input **and on a `q` byte** (the
  interpreter's `mygetchar()` treats `q` as the end); on the machine `UARTIN` waits and
  echoes, and turns CR into LF; `puts` appends only `\n` (10), while the monitor's own messages send `0Ah,0Dh`.
- Programs for the machine must not write into $E000–$FFFF (the EEPROM's write enable) nor below $0F00 unless they
  mean to (monitor variables, stack).
- Code size is "roughly 2–3× what hand assembly would be" (`README.md`); the BACKLOG's peephole ideas (R3/R4 traffic,
  8-bit paths for char arithmetic, count-down loops) are open.
- Not yet run on the real machine (section 6).
