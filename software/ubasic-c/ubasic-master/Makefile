# uBASIC (YACC1 interactive version) — plain make (NetBeans one: Makefile.netbeans).
#   make          build ./ubasic
#   make run      interactive session (type lines, `run`, `list`; end of input quits)
#   ./ubasic FILE run a program file (e.g. ../../../tests/basic/test)
CC     ?= cc
CFLAGS ?= -O2 -Wall
all: ubasic
ubasic: ubasic.c tokenizer.c use-ubasic.c ubasic.h tokenizer.h vartype.h
	$(CC) $(CFLAGS) -o $@ ubasic.c tokenizer.c use-ubasic.c
run: ubasic
	./ubasic
clean:
	rm -f ubasic
.PHONY: all run clean
