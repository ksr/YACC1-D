# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

# y1ucemu - the microcode-level YACC1 emulator (steps the control store the sequencer card holds).
#   make          build ./y1ucemu (videogate.h first, when the card's netlist or software/gatemodel changed)
#   make test     run tests/ucemu/run.py (the compiler suite + brur on this emulator, against the interpreter's expectations)
#   make clean
CC     ?= cc
CFLAGS ?= -O2 -Wall -fno-common
include ../../mk/sdk.mk
CFLAGS += $(SDKFLAGS)
all: y1ucemu
CARD   = ../../hardware/cards/video/kicad/v1.0-fusion-export-2026-09-18/reports
y1ucemu: y1ucemu.c videogate.h ../videomodel.h ../cfmodel.h ../../firmware/microcode/yaccsignaldata2.h
	$(CC) $(CFLAGS) -o $@ y1ucemu.c
# the video card at gate level (-G): generated from its netlist by software/gatemodel (committed; tests/video/gate.py
# checks it is current)
videogate.h: $(wildcard ../gatemodel/*.py) $(CARD)/netlist.net $(CARD)/netlist-compare.txt
	python3 ../gatemodel -o $@
test: y1ucemu
	python3 ../../tests/ucemu/run.py
clean:
	rm -f y1ucemu
.PHONY: all test clean
