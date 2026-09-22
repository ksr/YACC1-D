# Y1/OS - the YACC1 disk operating system (docs/system/OS-PLAN.md), built with the tree's own tools.
#   make            y1os.bin (the OS image), the /BIN programs, and disk.img (a P8XFS v2 volume with all of it)
#   make run        boot it on the microcode emulator, interactive (type O at the monitor prompt)
#   make run-int    same on the instruction-level emulator
#   make test       tests/os/run.py: scripted sessions on both emulators against expected transcripts
#   make clean
# Programs: os/commands/*.c -> /BIN/NAME (upper case), compiled at TPA $5000. Files in os/disk/ go to the root.
ROOT   = ..
CC     = python3 $(ROOT)/software/compiler/y1cc.py
ASM    = $(ROOT)/software/assembler/asm
DEF    = $(ROOT)/software/assembler/yacc1.def
I2B    = python3 $(ROOT)/tools/img2bin.py
FS     = python3 $(ROOT)/tools/p8xfs.py
B      = build
CMDS   = $(patsubst commands/%.c,$(B)/bin/%.bin,$(wildcard commands/*.c))
FILES  = $(wildcard disk/*)

all: disk.img

$(B)/y1os.bin: y1os.c lib_abi.c $(ROOT)/software/compiler/y1cc.py $(ROOT)/software/compiler/lib/y1lib.c
	@mkdir -p $(B) && cp $(DEF) $(B)/ && echo -h > $(B)/rcasm.rc
	$(CC) y1os.c -o $(B)/y1os.asm --org 0x1000 -l
	@cd $(B) && ../$(ASM) y1os -d=yacc1 > y1os.lst && grep -q "^0 Errors" y1os.lst || { grep -i "err" $(B)/y1os.lst | head; exit 1; }
	@grep "Object Code" $(B)/y1os.lst
	$(I2B) $(B)/y1os.img $@ --base 0x1000

$(B)/bin/%.bin: commands/%.c lib_abi.c
	@mkdir -p $(B)/bin && cp $(DEF) $(B)/bin/ && echo -h > $(B)/bin/rcasm.rc
	@$(CC) $< -o $(B)/bin/$*.asm --org 0x5000
	@cd $(B)/bin && ../../$(ASM) $* -d=yacc1 > $*.lst && grep -q "^0 Errors" $*.lst || { grep -i "err" $(B)/bin/$*.lst | head; exit 1; }
	@$(I2B) $(B)/bin/$*.img $@ --base 0x5000

disk.img: $(B)/y1os.bin $(CMDS) $(FILES) Makefile
	@rm -f $@
	$(FS) create $@ --sectors 2048
	$(FS) boot $@ $(B)/y1os.bin
	$(FS) mkdir $@ /BIN
	@for c in $(CMDS); do n=$$(basename $$c .bin | tr a-z A-Z); $(FS) put $@ $$c --name /BIN/$$n --load 0x5000 --exec 0x5000; done
	@for f in $(FILES); do $(FS) put $@ $$f --name /$$(basename $$f); done
	$(FS) tree $@

run: disk.img
	$(ROOT)/software/ucemu/y1ucemu -m -c disk.img
run-int: disk.img
	$(ROOT)/software/emulator/emulator -m -c disk.img
test: disk.img
	python3 $(ROOT)/tests/os/run.py
clean:
	rm -rf $(B) disk.img
.PHONY: all run run-int test clean
