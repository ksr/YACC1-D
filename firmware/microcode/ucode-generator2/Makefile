# YACC1 microcode generator — plain make (NetBeans one: Makefile.netbeans).
#   make          build ./ucodegen (includes resolve via ../../opcodes.h -> tools/layout_links.py)
#   make check    generate into build/ and diff against the committed test.hex (fails on difference)
#   make regen    run ./ucodegen here: rewrites test.123 / test.hex / test.hexz beside it (what the loader sends)
#   make clean
CC     ?= cc
CFLAGS ?= -O2 -Wall -fno-common
SRC     = $(wildcard *.c)
all: ucodegen
ucodegen: $(SRC) $(wildcard *.h) ../yaccsignaldefine.h ../yaccsignaldata2.h ../../../software/opcodes.h
	$(CC) $(CFLAGS) -o $@ $(SRC)
check: ucodegen
	@mkdir -p build && cp ucodegen build/ && cd build && ./ucodegen > gen.log && \
	 if cmp -s test.hex ../test.hex; then echo "test.hex: IDENTICAL to the committed microcode image"; else echo "test.hex: DIFFERS"; exit 1; fi
regen: ucodegen
	./ucodegen > /dev/null && ls -la test.hex test.123
clean:
	rm -rf ucodegen build
.PHONY: all check regen clean
