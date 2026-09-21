# YACC1 microcode disassembler — plain make (NetBeans one: Makefile.netbeans).
#   make            build ./disasm2
#   make run        disassemble every opcode of firmware/microcode/ucode-generator2/test.123 (found relative to the binary)
#   ./disasm2 04 05 selected opcodes (hex)
CC     ?= cc
CFLAGS ?= -O2 -Wall
all: disasm2
disasm2: main.c code.h ../yaccsignaldefine.h ../yaccsignaldata2.h
	$(CC) $(CFLAGS) -o $@ main.c
run: disasm2
	./disasm2
clean:
	rm -f disasm2
.PHONY: all run clean
