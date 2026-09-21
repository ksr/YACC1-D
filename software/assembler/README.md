# software/assembler — RC/asm v2.2, YACC1 port

Michael H. Riley's table-driven cross assembler (`upstream/rcasm-2.2/` is his unmodified 2.2 with the .def tables
for other CPUs). The YACC1 port (2020-08 → 2021-07-09) changed `asm.c asmcmds.c support.c mstrings.* header.h
Makefile rcasm.rc` and added `yacc1.def`, the YACC1 instruction table. `asm.txt` / `asm.doc` = the manual.

`yacc1.def` here is the 2025-03-14 version: the 2020-11-25 table plus a lowercase `equ` directive (the only
difference); it is what `firmware/monitor/monnew-2025/` was assembled with. Build: `make` (plain Makefile, 2026-09-20; the NetBeans one is `Makefile.netbeans`). `make check` assembles the monitor and BASIC
sources from `firmware/` in `build/` and diffs the images and the ROM against the committed ones; `make install` copies a
fresh build into `firmware/` when a source was changed on purpose. Run the assembler from a folder containing `rcasm.rc`.

Moved out of here 2026-09-20 (this folder used to be the working directory for everything):
- monitor/BASIC sources, listings, images and `rom` → `firmware/` (the copies here were the git-HEAD "not working"
  3bcacf3 build, now `firmware/*/candidates/2021-09-02-3bcacf3-not-working/`); `basic.asmtmp copy` (Nov-2020 port draft)
  → `firmware/basic/candidates/2020-11-10-port-draft/`.
- `yacc1test.asm` (the CPU test program) and its 15 dated 2020 snapshots → `tests/assembler/`.
- `old/rcasm`, `old/rcasm-old` (intermediate stages of the port, with compiled binaries) → `archive/superseded-revisions/assembler-port-2020/`.
- `old/a18*` (Riley's A18 1802 assembler, CUG149 – RC/asm's ancestor, not YACC1 work) → `archive/third-party/`.
- dropped: `abc` (a symbol listing), `list` (a run log), `c_standard_headers_indexer.c` (Xcode artefact).
