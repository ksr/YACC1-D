# software/disassembler — microcode disassembler

`disasm2/` decodes the 64-step microcode image produced by `firmware/microcode/ucode-generator2/` (it reads
`../ucode-Generator2/test.123` – a symlink here points at the generator folder) and prints, per opcode, which control
signals are active on each step, using the signal names in `firmware/microcode/yaccsignaldefine.h`.

As committed (2024-06-25) `main.c` does not build on its own: line 21, `#include "../yaccsignaldata2.h"` (the signal table), is
commented out, and two functions are declared without a return type. It builds once that include is restored and clang is told
`-std=gnu99 -Wno-implicit-int` (verified 2026-09-20 on a scratch copy; the source here is left exactly as migrated).

`disasm/` (the 32-step, Generator-v1 version; only `main.c` differed) → `archive/superseded-revisions/disasm-v1/`.
