# Y1/OS - the YACC1 disk operating system (docs/system/OS-PLAN.md), built with the tree's own tools.
#   make            y1os.bin (the OS image), the /BIN programs, and disk.img (a P8XFS v2 volume with all of it)
#   make run        boot it on the microcode emulator, interactive (type O at the monitor prompt)
#   make run-int    same on the instruction-level emulator
#   make test       tests/os/run.py: scripted sessions on both emulators against expected transcripts
#   make clean
#   make sizes      each /BIN program's size (image + uninitialised data) against the 32K program area
# Programs: os/commands/*.c -> /BIN/NAME (upper case), compiled at TPA $5000; they #include the os/lib_*.c
# libraries. Files in os/disk/ go to the root, os/man/NAME to /MAN/NAME (upper case: `man` upper-cases the name),
# and the Markdown documents in DOCS to /DOCS for `md` (host file = disk name).
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

$(B)/y1os.bin: y1os.c lib_abi.c lib_fs.c $(ROOT)/software/compiler/y1cc.py $(ROOT)/software/compiler/lib/y1lib.c
	@mkdir -p $(B) && cp $(DEF) $(B)/ && echo -h > $(B)/rcasm.rc
	$(CC) y1os.c -o $(B)/y1os.asm --org 0x1000 -l
	@cd $(B) && ../$(ASM) y1os -d=yacc1 > y1os.lst && grep -q "^0 Errors" y1os.lst || { grep -i "err" $(B)/y1os.lst | head; exit 1; }
	@grep "Object Code" $(B)/y1os.lst
	$(I2B) $(B)/y1os.img $@ --base 0x1000

$(B)/bin/%.bin: commands/%.c $(LIBS)
	@mkdir -p $(B)/bin && cp $(DEF) $(B)/bin/ && echo -h > $(B)/bin/rcasm.rc
	@$(CC) $< -o $(B)/bin/$*.asm --org 0x5000
	@cd $(B)/bin && ../../$(ASM) $* -d=yacc1 > $*.lst && grep -q "^0 Errors" $*.lst || { grep -i "err" $(B)/bin/$*.lst | head; exit 1; }
	@$(I2B) $(B)/bin/$*.img $@ --base 0x5000
	@t=$$(( $$(wc -c < $@) + $$(awk '/^bss_start:/{b=1} b && $$2=="DS"{s+=$$3} END{print s+0}' $(B)/bin/$*.asm) )); \
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
	  d=$$(awk '/^bss_start:/{f=1} f && $$2=="DS"{s+=$$3} END{print s+0}' $(B)/bin/$$n.asm); \
	  printf "%-8s %6d image + %6d data = %6d of 32768\n" $$n $$b $$d $$((b + d)); done

run: disk.img
	$(ROOT)/software/ucemu/y1ucemu -m -c disk.img
run-int: disk.img
	$(ROOT)/software/emulator/emulator -m -c disk.img
test: disk.img
	python3 $(ROOT)/tests/os/run.py
clean:
	rm -rf $(B) disk.img
.PHONY: all sizes run run-int test clean
