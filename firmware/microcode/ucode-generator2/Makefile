# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

# YACC1 microcode generator — plain make (NetBeans one: Makefile.netbeans).
#   make          build ./ucodegen (includes resolve via ../../opcodes.h -> tools/layout_links.py)
#   make check    generate into build/ and diff against the committed test.hex (fails on difference)
#   make regen    run ./ucodegen here: rewrites test.123 / test.hex / test.hexz beside it (what the loader sends)
#   make prologue6  the microcode as it was before 2026-09-29's fetch-prologue and M-1 changes (six-step prologue; with
#                 LDZ/STZ/ADDIW/SHL16 and the H-4 fix; = the image committed at b98aec2), in build/p6/test.hex
#                 (for loading in two stages or going back: tools/ucode_send.py --all --hex <that file>)
#   make clean
CC     ?= cc
CFLAGS ?= -O2 -Wall -fno-common
include ../../../mk/sdk.mk
CFLAGS += $(SDKFLAGS)
SRC     = $(wildcard *.c)
all: ucodegen
ucodegen: $(SRC) $(wildcard *.h) ../yaccsignaldefine.h ../yaccsignaldata2.h ../../../software/opcodes.h
	$(CC) $(CFLAGS) -o $@ $(SRC)
check: ucodegen
	@mkdir -p build && cp ucodegen build/ && cd build && ./ucodegen > gen.log && \
	 if cmp -s test.hex ../test.hex; then echo "test.hex: IDENTICAL to the committed microcode image"; else echo "test.hex: DIFFERS"; exit 1; fi
regen: ucodegen
	./ucodegen > /dev/null && ls -la test.hex test.123
prologue6: $(SRC) $(wildcard *.h) ../yaccsignaldefine.h ../yaccsignaldata2.h ../../../software/opcodes.h
	@mkdir -p build/p6 && $(CC) $(CFLAGS) -DPROLOGUE6 -o build/p6/ucodegen $(SRC) && cd build/p6 && ./ucodegen > gen.log && \
	 echo "six-step prologue image: $(CURDIR)/build/p6/test.hex"
clean:
	rm -rf ucodegen build
.PHONY: all check regen clean
