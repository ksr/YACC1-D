# software/compiler/c - y1cc in C: y1cc.c (the single-program twin of y1cc.py, 2026-09-24) and the multi-pass
# compiler cc1..cc9 (the same compiler split into nine programs that each fit the Y1/OS program area, 2026-09-24)
#   make          build ./y1cc and ./y1cc16, the passes ./cc1..cc9 and ./cc1_16..cc9_16, the drivers ./y1ccp, ./y1ccp16
#                 (C89, no warnings: -std=c89 -Wall -Wextra -pedantic)
#   make twin     tests/compiler/twin.py: the whole corpus through y1cc.py and ./y1cc, assembly compared; then the
#                 same with ./y1cc16 (host16.c: int = unsigned short, unsigned char, the YACC1's integer types), then
#                 the pass chain ./y1ccp and ./y1ccp16 (twin.py --chain, --chain16)
#   make target   the self-compile proof: y1cc.py compiles target.c (y1cc.c + target_io.c, the Y1/OS I/O); its size
#                 against the 32K program area ($5000-$CFFF), counted with yacc1.def's instruction lengths (the
#                 assembler cannot take it: over 64K)
#   make passes-target   each pass compiled by y1cc.py as a Y1/OS program (target/NAME.c: its Y1/OS table sizes
#                 ylim/NAME.h) and assembled by the host assembler: image + tables + measured stack against the 32K
#                 area; the corpus through the passes built on the Mac with those table sizes and a stack probe
#                 (stackprobe.c, the builds cc1_s..cc9_s and y1ccps): tests/compiler/passes.py
#   make clean
CC      = cc
CFLAGS  = -std=c89 -Wall -Wextra -pedantic -O1 -fno-common
ROOT    = ../../..
B       = build
PASSES  = cc1 cc2 cc3 cc4 cc5 cc6 cc7 cc8 cc9
PSRC    = pdefs.h pcommon.c pnames.c past.c io.h host_io.c plim_host.h hostp.c host16p.c
C16     = $(CC) $(CFLAGS) -funsigned-char -Wno-keyword-macro

all: y1cc y1cc16 passes

y1cc: host.c host_io.c y1cc.c io.h limits_host.h
	$(CC) $(CFLAGS) -o $@ host.c host_io.c

y1cc16: host16.c host_io.c y1cc.c io.h limits_host.h
	$(CC) $(CFLAGS) -funsigned-char -Wno-keyword-macro -o $@ host16.c host_io.c

passes: $(PASSES) $(PASSES:%=%_16) y1ccp y1ccp16

# each pass: cc1 from cc1_lex.c, ..., cc9 from cc9_final.c
cc1 cc1_16: cc1_lex.c
cc2 cc2_16: cc2_parse.c
cc3 cc3_16: cc3_decl.c
cc4 cc4_16: cc4_calls.c
cc5 cc5_16: cc5_layout.c
cc6 cc6_16: cc6_stmt.c
cc7 cc7_16: cc7_sema.c
cc8 cc8_16: cc8_emit.c
cc9 cc9_16: cc9_final.c
$(PASSES): $(PSRC)
	$(CC) $(CFLAGS) '-DPASS="$(filter-out $(PSRC),$^)"' -o $@ hostp.c host_io.c
$(PASSES:%=%_16): $(PSRC)
	$(C16) '-DPASS="$(filter-out $(PSRC),$^)"' -o $@ host16p.c host_io.c

y1ccp: y1ccp.c
	$(CC) -Wall -Wextra -O1 -o $@ y1ccp.c
y1ccp16: y1ccp
	cp y1ccp y1ccp16

twin: y1cc y1cc16 passes
	python3 $(ROOT)/tests/compiler/twin.py
	python3 $(ROOT)/tests/compiler/twin.py --16
	python3 $(ROOT)/tests/compiler/twin.py --chain
	python3 $(ROOT)/tests/compiler/twin.py --chain16

target: target.c target_io.c target_sec.c y1cc.c io.h limits_y1.h
	@mkdir -p $(B) && cp $(ROOT)/software/assembler/yacc1.def $(B)/ && echo -h > $(B)/rcasm.rc
	python3 $(ROOT)/software/compiler/y1cc.py target.c -o $(B)/y1cct.asm --org 0x5000 --os -l | cut -c1-100
	@python3 $(ROOT)/tests/compiler/twin.py --size $(B)/y1cct.asm

passes-target:
	python3 $(ROOT)/tests/compiler/passes.py

clean:
	rm -rf y1cc y1cc16 $(PASSES) $(PASSES:%=%_16) $(PASSES:%=%_s) y1ccp y1ccp16 y1ccps $(B)

.PHONY: all passes twin target passes-target clean
