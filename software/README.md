# software — host-side toolchain (runs on the Mac)

| Folder | What | Status |
|---|---|---|
| `assembler/` | RC/asm v2.2 (Michael H. Riley), YACC1 port: `asm.c asmcmds.c support.c mstrings.*`, `yacc1.def` (the ISA table), `rcasm.rc`, manual `asm.txt/asm.doc`; `upstream/rcasm-2.2/` = the unmodified upstream | builds with `cc asm.c asmcmds.c support.c mstrings.c` |
| `opcodes.h` | the opcode table shared by the emulator, the disassembler and the microcode generator | 2024-06-19 |
| `emulator/` | the C emulator, reference model of the ISA (`-m/-f` options added 2026-06) | builds |
| `disassembler/disasm2/` | microcode disassembler for the 64-step Generator2 format | builds (2-line fix 2026-09-20, see `tools/patched_files.txt`) |
| `ubasic-c/` | the C uBASIC (Adam Dunkels) the assembly BASIC was ported from; `ubasic-master-orig/` = upstream | builds |

The C tools are NetBeans 8.2 projects (their `nbproject/` folders are kept); Ken intends to move off NetBeans.
They still use the relative include paths of the old `Software/` tree; `tools/layout_links.py` creates three symlinks
(`firmware/opcodes.h`, `software/disassembler/yaccsignaldefine.h`, `software/disassembler/ucode-Generator2`) so they
build UNCHANGED here. Verified 2026-09-20: assembler, emulator, ubasic and ucode-generator2 compile with clang, and
ucode-generator2 regenerates `firmware/microcode/ucode-generator2/test.hex` byte-identical to the committed image.

Firmware sources (monitor, BASIC, ROM images, microcode) live under `firmware/`, not here. The 2021 16-bit
experiment (Assembler-16, emulator-16) was deleted on Ken's instruction 2026-09-20.
