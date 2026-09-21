# software/ubasic-c — uBASIC in C

Adam Dunkels' uBASIC, made interactive for YACC1. `ubasic-master-orig/` = upstream as received; `ubasic-master/` =
the YACC1 version. The assembly BASIC (`firmware/basic/basic.asm`, Nov 2020 → Jul 2021) was ported from this C line.

Three lines existed in the old tree (resolved 2026-09-20, "newest wins"):
- **2020-11 (git)** – the interactive version the asm port was made from.
- **2024-06-28 (kept here)** – the 2020 line plus 6 lines of compile fixes (`char *` argument, `static` removed).
- **2023-02 (archived)** – a separate experiment that turns the program pointer into an integer index and `#ifdef OLD`s
  the pointer code (121/147 changed lines in ubasic.c/tokenizer.c): `archive/conflict-losers/YACC1-2020/Software/ubasic-master/`.
Dropped: `tokenizer copy.c` (2020-11-06 intermediate) and the compiled `use-ubasic` binaries. `x.tb` = a test program.
Build: `make` in `ubasic-master/`; `./ubasic FILE` runs a program, `./ubasic` alone is interactive (type numbered lines, then
`run`, `list`; end of input quits — fixed 2026-09-20, it looped forever before).
