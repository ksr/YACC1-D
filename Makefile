# YACC1-D top level — builds every C tool and runs every proof.
#   make            build emulator, assembler, microcode generator, disassembler, uBASIC, vector generator
#   make check      audit the tree + rebuild firmware/microcode/sketches and diff against the committed images
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
clean:
	@for d in $(TOOLS); do $(MAKE) -s -C "$$d" clean; done
.PHONY: all check clean
