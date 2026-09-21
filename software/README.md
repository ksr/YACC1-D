# software — host-side toolchain (runs on the Mac)

| Folder | What | Status |
|---|---|---|
| `assembler/` | RC/asm v2.2 (Michael H. Riley), YACC1 port: `asm.c asmcmds.c support.c mstrings.*`, `yacc1.def` (the ISA table), `rcasm.rc`, manual `asm.txt/asm.doc`; `upstream/rcasm-2.2/` = the unmodified upstream | `make`; `make check` reproduces the burned firmware |
| `opcodes.h` | the opcode table shared by the emulator, the disassembler and the microcode generator | 2024-06-19 |
| `emulator/` | the C emulator, reference model of the ISA (`-m/-f` options added 2026-06) | `make`; double-click runs the burned ROM |
| `disassembler/disasm2/` | microcode disassembler for the 64-step Generator2 format | `make`; `./disasm2 [opcode…]`, finds the image relative to itself |
| `ubasic-c/` | the C uBASIC (Adam Dunkels) the assembly BASIC was ported from; `ubasic-master-orig/` = upstream | `make`; `./ubasic [FILE]`, interactive without a file |

Every tool has a plain `Makefile` (2026-09-20; the NetBeans-generated one is kept as `Makefile.netbeans`, `nbproject/` too) and
the top-level `Makefile` builds them all (`make`) and runs every proof (`make check`). All six binaries can be started by a
Finder double-click: they locate their inputs/outputs relative to the executable, not the working directory.
They still use the relative include paths of the old `Software/` tree; `tools/layout_links.py` creates three symlinks
(`firmware/opcodes.h`, `software/disassembler/yaccsignaldefine.h`, `software/disassembler/ucode-Generator2`) so they
build UNCHANGED here. Verified 2026-09-20 (`make check`): all six compile; the assembler reproduces the burned ROM and ucode-generator2 regenerates
`test.hex` byte-identical. Deliberate source edits are listed in `tools/patched_files.txt`.

Firmware sources (monitor, BASIC, ROM images, microcode) live under `firmware/`, not here. The 2021 16-bit
experiment (Assembler-16, emulator-16) was deleted on Ken's instruction 2026-09-20.
