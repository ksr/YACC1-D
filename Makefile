# YACC1-D top level — builds every C tool and runs every proof.
#   make            build emulator, assembler, microcode generator, disassembler, uBASIC, vector generator
#   make check      audit the tree + rebuild firmware/microcode/sketches and diff against the committed images,
#                   then run the C compiler's test programs on the emulator (tests/compiler/run.py)
#   make cc-test    just the compiler tests
#   make clean
TOOLS = software/emulator software/assembler firmware/microcode/ucode-generator2 software/disassembler/disasm2 \
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
cc-test:
	python3 tests/compiler/run.py
clean:
	@for d in $(TOOLS); do $(MAKE) -s -C "$$d" clean; done
kicad:
	python3 tools/eagle_to_kicad_all.py
isa:
	python3 tools/ucode_wavedrom.py --all
.PHONY: all check clean kicad isa cc-test
