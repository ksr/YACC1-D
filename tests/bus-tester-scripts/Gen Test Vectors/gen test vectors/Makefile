# bus-tester test-vector generator — plain make (NetBeans one: Makefile.netbeans).
#   make        build ./gen ;  make run   print the generated script to stdout (redirect into a script file)
CC     ?= cc
CFLAGS ?= -O2 -w
all: gen
gen: main.c
	$(CC) $(CFLAGS) -o $@ main.c
run: gen
	./gen
clean:
	rm -f gen
.PHONY: all run clean
