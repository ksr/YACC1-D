# YACC1 emulator — plain make, no NetBeans needed.
#   make            build ./emulator
#   make run        run it with the shipped ROM (BASIC at $E000 + monitor at $F000), the image that is in the machine
#   make run ROM=path/to/other.img   (any Intel-hex file; .img from the assembler, or rom from makerom)
#   make clean
CC      ?= cc
CFLAGS  ?= -O2 -Wall
ROM     ?= ../../firmware/rom/shipped/rom

all: emulator

emulator: main.c ../opcodes.h
	$(CC) $(CFLAGS) -o $@ main.c

run: emulator
	./emulator -f $(ROM)

clean:
	rm -f emulator

.PHONY: all run clean
