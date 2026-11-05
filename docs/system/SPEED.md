# Speed: where the machine's time goes

Measurements of the YACC1 at work, in clocks, and what they point at. First measured 2026-11-05. The time is at the
machine's 1 MHz. Nothing here has been changed yet: this page is the baseline.

## The instruments

- **`software/opclocks.h`** is every opcode's length in clocks, generated from the microcode (`y1ucemu -x -Y`). Every
  opcode has one length, fetch to fetch: a conditional branch costs the same taken or not.
- **`emulator -P FILE`** counts instructions and clocks per address, the opcodes and the CF sectors, a block for every
  program Y1/OS starts. It runs about 70 times faster than the microcode emulator.
- **`y1ucemu -Q FILE`** measures clocks per opcode on the microcode itself.
- **`tools/speed.py`** runs a line under Y1/OS and reports the time by program, by where it runs (program, OS, ROM), by
  function and by opcode.
- **`tests/native/clocks.py`** (in `make check`) keeps these honest: the table against the microcode, one length for
  every opcode, and the total against `y1ucemu` (0.023% apart on `make touch`).

```
python3 tools/speed.py                     everything in /src/os/commands
python3 tools/speed.py touch               one command
python3 tools/speed.py --dir / --cmd 'ls /bin'
```

## `make` in /src/os/commands

39 commands, 430 programs started: **45.0 G clocks, 12 h 30 m**, 1,668 M instructions, 27.0 clocks an instruction, 49,338 sectors read and
10,334 written. A command takes 19 minutes on average (median 18): `echo.c` 3 minutes, `asm.c` 76.

| Program | Time | Share |
|---|---|---|
| cc9, the assembly text | 3 h 37 m | 28.9% |
| cc1, the lexer | 1 h 37 m | 12.9% |
| cc2, the parser | 1 h 35 m | 12.7% |
| cc7 | 1 h 15 m | 10.0% |
| cc6 | 1 h 08 m | 9.1% |
| cc8 | 1 h 03 m | 8.4% |
| asm | 55 m | 7.4% |
| cc5, cc3, cc4 | 1 h 17 m | 10.3% |
| cc, make | 3 m | 0.4% |

| Where it runs | Time | Share |
|---|---|---|
| the program | 10 h 46 m | 86.0% |
| the ROM (`cfrdl` 6.1%, `cfwrl` 1.2%) | 56 m | 7.5% |
| the OS (`rdn_cp` 2.3%, `fwf_cp` 1.2%, `zero512` 0.8%) | 49 m | 6.5% |

The biggest functions are small and shared: the ROM's sector read loop `cfrdl` 6.1%, `f_bcat`, `f_mn_arg`, `f_Ls`,
`f_pnum`, `f_io_wputs` (cc9's text) 12.3% together, and `f_io_getc` across the passes, 10.8%.

| Opcode | Clocks | Share |
|---|---|---|
| `LDZ R3` | 51 | 12.2% |
| `STZ R3` | 55 | 6.6% |
| `BRNEQ` | 35 | 5.4% |
| `LDR R3` | 51 | 5.3% |
| `BRNZ` | 35 | 4.9% |
| `STR R3` | 57 | 4.5% |
| `JSR` | 55 | 3.5% |
| `ADDIW R3` | 85 | 3.2% |

## What has been done

Each line is measured on `make grep` (33 m 06 s at the baseline).

| Date | Change | `make grep` |
|---|---|---|
| 2026-11-05 | Counted I/O: `io_getc`/`io_wput` test a one-byte count instead of comparing a handle and a pointer; `ri`/`wi` move a word whole with `peekw`/`pokew`; `rb`/`wb` are gone (`software/compiler/c/target_io.c`) | 29 m 24 s, -11.2% |

## What it points at

1. **The microcode.** Everything runs through it: 27 clocks an instruction. `LDZ` is 51 clocks and `LDZ`/`STZ`/`LDR`/`STR`
   are 34% of the time, branches 18%. A saving on the common records is a saving on everything, compiler or not.
2. **cc9 and asm are 36%.** The compiler writes assembly text (118 KB for `asm.c`) and the assembler reads it back. An
   object format between them, or a faster text path in cc9, attacks that directly.
3. **The disk is about 12%** (ROM and OS copy loops), on 1,265 sectors read a command. The passes hand each other
   work files; fewer or smaller ones, or a tighter CF loop, reduce it.
4. **Byte-at-a-time helpers** (`io_getc`, `bcat`, `io_wput`) are small and hot in every pass.
5. **A faster clock** is the plain multiplier: 2 MHz halves every figure here. The cards' margins at 6 MHz are in
   `docs/cards/video-v2.md` and `hardware/cards/memory/reviews/v2.0.md`.
