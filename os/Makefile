# Y1/OS - the YACC1 disk operating system (docs/system/OS-PLAN.md), built with the tree's own tools.
#   make            y1os.bin (the OS image), the /BIN programs, and disk.img (a P8XFS v2 volume with all of it)
#   make OS=c       the same with the C OS (y1os.c, the specification) instead of the assembly one (y1os.asm, the
#                   default since 2026-09-23); the choice is remembered in build/os-sel, so switching rebuilds disk.img.
#                   `OS=c python3 ../tests/os/run.py` runs the test sessions against the C OS (make inherits OS).
#   make XISA=1     every program (the /BIN commands, and the OS with OS=c) compiled with y1cc --xisa (2026-09-24:
#                   LDZ/STZ + the page, ADDIW, SHL16 - needs the 2026-09-24 microcode on the machine); remembered in
#                   build/xisa-sel like OS, so switching rebuilds. `XISA=1 python3 ../tests/os/run.py` tests that build.
#   make run        boot it on the microcode emulator, interactive (type O at the monitor prompt)
#   make run-int    same on the instruction-level emulator
#   make test       tests/os/run.py: scripted sessions on both emulators against expected transcripts
#   make clean
#   make sizes      each /BIN program's size (image + uninitialised data) against the 32K program area
# The OS: y1os.asm (hand-written, 2026-09-23) is assembled with strings.txt made into numeric DB lines by
# mkstrings.py (the assembler upper-cases its source); its image must end below its RAM at $4A00. y1os.c (y1cc
# --os) is the same OS in C, image + data below $5000. Both are installed with `p8xfs.py boot` as build/y1os.bin.
# y1cc --os (2026-09-23) for every program: putchar/puts/getchar are the OS syscalls CONOUT/CONIN,
# which the shell redirects (> >> < |); a program built without it would write past a redirect to the screen.
# Programs: os/commands/*.c -> /BIN/NAME (upper case), compiled at TPA $5000; they #include the os/lib_*.c
# libraries. Files in os/disk/ go to the root, os/man/NAME to /MAN/NAME (upper case: `man` upper-cases the name),
# and the Markdown documents in DOCS to /DOCS for `md` (host file = disk name).
OS    ?= asm
XISA  ?=
CCX    = $(if $(XISA),--xisa)
ifneq ($(OS),asm)
ifneq ($(OS),c)
$(error OS must be asm (the default) or c, not "$(OS)")
endif
endif
ROOT   = ..
CC     = python3 $(ROOT)/software/compiler/y1cc.py
ASM    = $(ROOT)/software/assembler/asm
DEF    = $(ROOT)/software/assembler/yacc1.def
I2B    = python3 $(ROOT)/tools/img2bin.py
FS     = python3 $(ROOT)/tools/p8xfs.py
B      = build
CMDS   = $(patsubst commands/%.c,$(B)/bin/%.bin,$(wildcard commands/*.c))
FILES  = $(wildcard disk/*)
LIBS   = $(wildcard lib_*.c)
MANS   = $(wildcard man/*)
DOCS   = docs/mddemo.md:MDDEMO.MD README.md:OS.MD ../software/compiler/README.md:Y1CC.MD ../docs/system/OS-PLAN.md:OSPLAN.MD PORT-PLAN.md:PORT.MD

all: disk.img

$(B)/y1os.bin: $(B)/y1os-$(OS).bin $(B)/os-sel
	cp $< $@

$(B)/os-sel: FORCE
	@mkdir -p $(B); if [ "$$(cat $@ 2>/dev/null)" != "$(OS)" ]; then echo $(OS) > $@; fi

$(B)/xisa-sel: FORCE
	@mkdir -p $(B); if [ "$$(cat $@ 2>/dev/null)" != "$(CCX)" ]; then echo "$(CCX)" > $@; rm -f $(B)/bin/*.bin $(B)/y1os-c.bin; fi

$(B)/y1os-asm.bin: y1os.asm strings.txt mkstrings.py $(DEF)
	@mkdir -p $(B)/asm && cp $(DEF) $(B)/asm/ && echo -h > $(B)/asm/rcasm.rc && cp y1os.asm $(B)/asm/
	python3 mkstrings.py strings.txt > $(B)/asm/y1os_str.inc
	@cd $(B)/asm && ../../$(ASM) y1os -d=yacc1 > y1os.lst && grep -q "^0 Errors" y1os.lst || { grep "ERR" y1os.lst | head -20; exit 1; }
	@grep "Object Code" $(B)/asm/y1os.lst
	$(I2B) $(B)/asm/y1os.img $@ --base 0x1000
	@i=$$(wc -c < $@); \
	  printf "y1os (asm): %d bytes image (%d of 32 sectors), \$$1000-\$$%04X; RAM \$$4A00-\$$4FFF; %d bytes free between\n" $$i $$(( (i + 511) / 512 )) $$(( 4096 + i - 1 )) $$(( 0x4A00 - 4096 - i )); \
	  if [ $$(( 4096 + i )) -gt $$(( 0x4A00 )) ]; then echo "y1os: the image runs into its RAM at \$$4A00"; rm -f $@; exit 1; fi

$(B)/y1os-c.bin: y1os.c lib_abi.c lib_fs.c $(ROOT)/software/compiler/y1cc.py $(ROOT)/software/compiler/lib/y1lib.c $(B)/xisa-sel
	@mkdir -p $(B)/c && cp $(DEF) $(B)/c/ && echo -h > $(B)/c/rcasm.rc
	$(CC) y1os.c -o $(B)/c/y1os.asm --org 0x1000 --os $(CCX) -l
	@cd $(B)/c && ../../$(ASM) y1os -d=yacc1 > y1os.lst && grep -q "^0 Errors" y1os.lst || { grep -i "err" $(B)/c/y1os.lst | head; exit 1; }
	@grep "Object Code" $(B)/c/y1os.lst
	$(I2B) $(B)/c/y1os.img $@ --base 0x1000
	@i=$$(wc -c < $@); d=$$(awk '/^(zpad|bss_start):/{b=1} b && $$2=="DS"{s+=($$3 ~ /^[0-9]+$$/) ? $$3 : 255} END{print s+0}' $(B)/c/y1os.asm); \
	  printf "y1os (C): %d bytes image (%d of 32 sectors) + %d data = %d of 16384 (\$$1000-\$$4FFF)\n" $$i $$(( (i + 511) / 512 )) $$d $$((i + d)); \
	  if [ $$((i + d)) -gt 16384 ] || [ $$i -gt 16384 ]; then echo "y1os: over its 16K (the programs start at \$$5000)"; rm -f $@; exit 1; fi

$(B)/bin/%.bin: commands/%.c $(LIBS) $(ROOT)/software/compiler/y1cc.py $(B)/xisa-sel
	@mkdir -p $(B)/bin && cp $(DEF) $(B)/bin/ && echo -h > $(B)/bin/rcasm.rc
	@$(CC) $< -o $(B)/bin/$*.asm --org 0x5000 --os $(CCX)
	@cd $(B)/bin && ../../$(ASM) $* -d=yacc1 > $*.lst && grep -q "^0 Errors" $*.lst || { grep -i "err" $(B)/bin/$*.lst | head; exit 1; }
	@$(I2B) $(B)/bin/$*.img $@ --base 0x5000
	@t=$$(( $$(wc -c < $@) + $$(awk '/^(zpad|bss_start):/{b=1} b && $$2=="DS"{s+=($$3 ~ /^[0-9]+$$/) ? $$3 : 255} END{print s+0}' $(B)/bin/$*.asm) )); \
	  if [ $$t -gt 32768 ]; then echo "$*: $$t bytes, over the 32K program area"; rm -f $@; exit 1; fi

disk.img: $(B)/y1os.bin $(CMDS) $(FILES) $(MANS) $(foreach d,$(DOCS),$(firstword $(subst :, ,$(d)))) Makefile
	@rm -f $@
	$(FS) create $@ --sectors 2048
	$(FS) boot $@ $(B)/y1os.bin
	$(FS) mkdir $@ /BIN
	@for c in $(CMDS); do n=$$(basename $$c .bin | tr a-z A-Z); $(FS) put $@ $$c --name /BIN/$$n --load 0x5000 --exec 0x5000; done
	@for f in $(FILES); do $(FS) put $@ $$f --name /$$(basename $$f); done
	$(FS) mkdir $@ /MAN
	@for f in $(MANS); do $(FS) put $@ $$f --name /MAN/$$(basename $$f | tr a-z A-Z); done
	$(FS) mkdir $@ /DOCS
	@for d in $(DOCS); do $(FS) put $@ $${d%%:*} --name /DOCS/$${d##*:}; done
	$(FS) tree $@

sizes: $(CMDS)
	@for c in $(CMDS); do n=$$(basename $$c .bin); b=$$(wc -c < $$c); \
	  d=$$(awk '/^(zpad|bss_start):/{f=1} f && $$2=="DS"{s+=($$3 ~ /^[0-9]+$$/) ? $$3 : 255} END{print s+0}' $(B)/bin/$$n.asm); \
	  printf "%-8s %6d image + %6d data = %6d of 32768\n" $$n $$b $$d $$((b + d)); done

run: disk.img
	$(ROOT)/software/ucemu/y1ucemu -m -c disk.img
run-int: disk.img
	$(ROOT)/software/emulator/emulator -m -c disk.img
test: disk.img
	python3 $(ROOT)/tests/os/run.py
clean:
	rm -rf $(B) disk.img
.PHONY: all sizes run run-int test clean FORCE
FORCE:
