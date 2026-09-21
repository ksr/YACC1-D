# software/disassembler — microcode disassembler

`disasm2/` decodes the 64-step microcode image produced by `firmware/microcode/ucode-generator2/` and prints, per opcode,
which control signals are active on each step, using the signal names in `firmware/microcode/yaccsignaldefine.h`.
`make` builds it; `./disasm2` decodes every opcode, `./disasm2 04 05` selected ones (hex). It finds `test.123` relative to its
own location, so it runs from anywhere (Finder double-click included).

Fixed in the tree 2026-09-20 (listed in `tools/patched_files.txt`, the only edited migrated source so far): the
`#include "../yaccsignaldata2.h"` line, commented out in the 2024 commit, is re-enabled (it resolves through the layout link
made by `tools/layout_links.py`) and `printWave()` is declared `void`. Builds with plain `cc -o disasm2 main.c` and runs.

`disasm/` (the 32-step, Generator-v1 version; only `main.c` differed) → `archive/superseded-revisions/disasm-v1/`.
