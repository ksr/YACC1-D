# software/compiler/c - y1cc.c, the C twin of y1cc.py (2026-09-24)
#   make          build ./y1cc for the Mac (C89, no warnings: -std=c89 -Wall -Wextra -pedantic) and ./y1cc16
#   make twin     tests/compiler/twin.py: the whole corpus through y1cc.py and ./y1cc, assembly compared; then the
#                 same with ./y1cc16 (host16.c: int = unsigned short, unsigned char, the YACC1's integer types)
#   make target   the self-compile proof: y1cc.py compiles target.c (y1cc.c + target_io.c, the Y1/OS I/O); its size
#                 against the 32K program area ($5000-$CFFF), counted with yacc1.def's instruction lengths (the
#                 assembler cannot take it: over 1,000 labels and over 64K), the count checked on the corpus first
#   make clean
CC      = cc
CFLAGS  = -std=c89 -Wall -Wextra -pedantic -O1 -fno-common
ROOT    = ../../..
B       = build

all: y1cc y1cc16

y1cc: host.c host_io.c y1cc.c io.h limits_host.h
	$(CC) $(CFLAGS) -o $@ host.c host_io.c

y1cc16: host16.c host_io.c y1cc.c io.h limits_host.h
	$(CC) $(CFLAGS) -funsigned-char -Wno-keyword-macro -o $@ host16.c host_io.c

twin: y1cc y1cc16
	python3 $(ROOT)/tests/compiler/twin.py
	python3 $(ROOT)/tests/compiler/twin.py --16

target: target.c target_io.c y1cc.c io.h limits_y1.h
	@mkdir -p $(B) && cp $(ROOT)/software/assembler/yacc1.def $(B)/ && echo -h > $(B)/rcasm.rc
	python3 $(ROOT)/software/compiler/y1cc.py target.c -o $(B)/y1cct.asm --org 0x5000 --os -l | cut -c1-100
	@python3 $(ROOT)/tests/compiler/twin.py --size $(B)/y1cct.asm

clean:
	rm -rf y1cc y1cc16 $(B)

.PHONY: all twin target clean
