# YACC1-D top level — builds every C tool and runs every proof.
#   make            build emulator, assembler, the C twin of the C compiler (software/compiler/c), microcode generator,
#                   disassembler, uBASIC, vector generator
#   make check      audit the tree + rebuild firmware/microcode/sketches and diff against the committed images,
#                   then run the C compiler's test programs on the emulator (tests/compiler/run.py), compare
#                   y1cc.py with its C twin and with the multi-pass compiler over the whole corpus (tests/compiler/
#                   twin.py, also --16, --chain, --chain16), and size the passes against Y1/OS (tests/compiler/passes.py);
#                   the Y1/OS sessions, the native assembler against the host one and under Y1/OS (tests/asm/run.py --target),
#                   C compiled, assembled and run under Y1/OS by the native compiler and assembler (tests/native/run.py),
#                   the toolchain rebuilding itself natively, twice, byte-identical (tests/native/selfhost.py)
#                   the ROM's video unit and Y1/OS's video command on both emulators' card model (tests/video/emu.py),
#                   Kermit transfers between /BIN/KERMIT and tools/y1kermit.py over a pty on both emulators (tests/kermit/run.py)
#   make cc-test    just the compiler tests (on both emulators) and the twin comparisons (y1cc.c, the passes)
#   make os-test    Y1/OS sessions on both emulators (tests/os/run.py)
#   make native-test  the native compiler under Y1/OS on both emulators (tests/native/run.py; --all-uc: ~20 min)
#   make selfhost   the full native self-host (also in check): under Y1/OS on the instruction-level emulator the nine
#                   passes, /BIN/ASM and /BIN/CC compiled and assembled natively, byte-identical to the host builds,
#                   then again with the natively built tools - the fixed point (tests/native/selfhost.py, ~30 s)
#   make asm-test   the native assembler /BIN/ASM against the host assembler over the tree's sources, then under Y1/OS on
#                   both emulators (tests/asm/run.py --target)
#   make bom        regenerate docs/bom/ (bills of material per card + consolidated) from the active Eagle schematics (tools/gen_bom.py)
#   make clean
TOOLS = software/emulator software/ucemu software/assembler software/compiler/c firmware/microcode/ucode-generator2 software/disassembler/disasm2 \
        software/ubasic-c/ubasic-master "tests/bus-tester-scripts/Gen Test Vectors/gen test vectors"
all:
	@python3 tools/layout_links.py
	@for d in $(TOOLS); do echo "== $$d"; $(MAKE) -s -C "$$d" all || exit 1; done
check:
	python3 tools/audit_tree.py
	python3 tools/verify_firmware.py
	python3 tools/verify_embedded.py
	python3 tools/verify_processing.py
	$(MAKE) -s -C software/assembler check
	$(MAKE) -s -C firmware/microcode/ucode-generator2 check
	python3 tests/compiler/run.py
	python3 tests/compiler/twin.py
	python3 tests/compiler/twin.py --16
	python3 tests/compiler/twin.py --chain
	python3 tests/compiler/twin.py --chain16
	python3 tests/compiler/passes.py
	python3 tests/ucemu/run.py
	python3 tests/os/run.py
	python3 tests/asm/run.py --target
	python3 tests/native/run.py
	python3 tests/native/selfhost.py
	python3 tests/monload/run.py
	python3 tests/kermit/run.py
	python3 tests/bench/run.py
	python3 tests/cfcard/run.py
	python3 tests/video/emu.py
	python3 tests/sequencer/run.py
	python3 tests/assembler/romcount/run.py
	python3 tests/assembler/romdiag/run.py
cc-test:
	python3 tests/compiler/run.py
	python3 tests/compiler/twin.py
	python3 tests/compiler/twin.py --chain
	python3 tests/ucemu/run.py
os-test:
	python3 tests/os/run.py
asm-test:
	python3 tests/asm/run.py --target
native-test:
	python3 tests/native/run.py
selfhost:
	python3 tests/native/selfhost.py
clean:
	@for d in $(TOOLS); do $(MAKE) -s -C "$$d" clean; done
kicad:
	python3 tools/eagle_to_kicad_all.py
isa:
	python3 tools/ucode_wavedrom.py --all
bom:
	python3 tools/gen_bom.py
.PHONY: all check clean kicad isa bom cc-test os-test asm-test native-test selfhost
