# tests/basic

`test` — a small uBASIC program (LET/FOR loops) used to exercise the interpreter (`software/ubasic-c`, `firmware/basic`).
See also `software/ubasic-c/ubasic-master/x.tb`.

Note (2026-09-20): this file is NOT in the uBASIC dialect (`software/ubasic-c` expects numbered lines; `./ubasic test` crashes on it)
and neither `basic.asm` nor the C uBASIC know DUMPVARS/DUMPLABELS or `:label`. Its interpreter has not been identified; it may
belong to the gen-1 Tiny BASIC experiments in `archive/`. Kept as found.
