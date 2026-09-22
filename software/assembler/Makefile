# RC/asm v2.2, YACC1 port — plain make (the NetBeans-generated one is Makefile.netbeans).
#   make            build ./asm
#   make check      assemble firmware/monitor/monitor.asm and firmware/basic/basic.asm in build/ and diff the
#                   images against the committed ones (the burned ROM); fails on any difference
#   make install    copy the freshly assembled .img/.lst into firmware/ (only after changing a source on purpose)
#   make clean
# Invocation gotcha: `asm NAME -d=yacc1` — the source name (no extension) must come BEFORE -d=…, because the -d
# handler skips the following argument. The assembler wants rcasm.rc, yacc1.def and NAME.asm in the current dir.
CC      ?= cc
CFLAGS  ?= -O2 -Wall -fno-common
SRC      = asm.c asmcmds.c support.c mstrings.c
FW       = ../../firmware
TARGETS  = monitor basic

all: asm

asm: $(SRC) header.h mstrings.h
	$(CC) $(CFLAGS) -o $@ $(SRC)

# assemble one firmware source in build/NAME/ (keeps the tree clean); listing = the assembler's stdout
define ASM_RULE
build/$(1)/$(1).img: asm yacc1.def rcasm.rc $(FW)/$(1)/$(1).asm
	@mkdir -p build/$(1)
	@cp yacc1.def rcasm.rc "$(FW)/$(1)/$(1).asm" build/$(1)/
	@cd build/$(1) && ../../asm $(1) -d=yacc1 > $(1).lst
endef
$(foreach t,$(TARGETS),$(eval $(call ASM_RULE,$(t))))

check: $(foreach t,$(TARGETS),build/$(t)/$(t).img)
	@ok=1; for t in $(TARGETS); do \
	  if cmp -s build/$$t/$$t.img $(FW)/$$t/$$t.img; then echo "$$t.img: IDENTICAL to firmware/$$t/$$t.img"; \
	  else echo "$$t.img: DIFFERS from firmware/$$t/$$t.img"; ok=0; fi; \
	  if cmp -s build/$$t/$$t.lst $(FW)/$$t/$$t.lst; then echo "$$t.lst: identical"; else echo "$$t.lst: differs (listing only)"; fi; \
	done; \
	awk 'n>=1 { print a[n%1] } { a[n%1]=$$0; n=n+1 }' build/basic/basic.img > build/tmprom && cat build/tmprom build/monitor/monitor.img > build/rom; \
	if cmp -s build/rom $(FW)/rom/shipped/rom; then echo "rom: IDENTICAL to firmware/rom/shipped/rom (the image to burn)"; else echo "rom: DIFFERS from firmware/rom/shipped/rom"; ok=0; fi; \
	[ $$ok = 1 ]

install: check
	@for t in $(TARGETS); do cp build/$$t/$$t.img build/$$t/$$t.lst $(FW)/$$t/; done; cp build/rom $(FW)/rom/shipped/rom; echo "installed into firmware/"

clean:
	rm -rf asm build

.PHONY: all check install clean
