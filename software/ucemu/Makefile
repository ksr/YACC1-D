# y1ucemu - the microcode-level YACC1 emulator (steps the control store the sequencer card holds).
#   make          build ./y1ucemu
#   make test     run tests/ucemu/run.py (the compiler suite + brur on this emulator, against the interpreter's expectations)
#   make clean
CC     ?= cc
CFLAGS ?= -O2 -Wall -fno-common
include ../../mk/sdk.mk
CFLAGS += $(SDKFLAGS)
all: y1ucemu
y1ucemu: y1ucemu.c ../../firmware/microcode/yaccsignaldata2.h
	$(CC) $(CFLAGS) -o $@ y1ucemu.c
test: y1ucemu
	python3 ../../tests/ucemu/run.py
clean:
	rm -f y1ucemu
.PHONY: all test clean
