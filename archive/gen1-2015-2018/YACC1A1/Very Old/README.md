# YACC1-A

YACC1 - Yet Another Custom CPU.


The project consists of several components:

	Microcode generator
	Assembler
	Logisim circuit design
	Schematic - TBD
	PCB - TBD


Microcode Generator

Generates the microcode for the CPU instruction decoder/sequencer. The code is “documented”, the microcode generator has two phases. Phase 1 generates codefile, this is a human readable file containing the microcode for every CPU instruction. The file format is

:ins XX      (XX is 8bit hex instruction)
One or lines of sequencer codes
:end

In phase 2 the codefile is compiled into ROM images rom1 and rom2



Assembler

Assembler is your basic run of the mill assembler, it takes a source file,  optionally creates a listing file, and creates a rom image that can be loaded into the simulator and loaded into RAM. Supported Opcode and Directives are listed near the top of the file. Currently only enough opcodes are supported to test out various addressing modes and instruction types.


Logisim

A work in progress simulator for the YACC1 CPU.

Approx steps:

Download logisim from http://www.cburch.com/logisim/
Load the latest circ file from this GIT project
I won’t go into detailed Logisim instructions but make sure you have selected the “poke” tool. The hand icon at the top left of the app. Under Simulate window option select Simulation Enabled, then Reset Simulation, finally select Ticks enabled. Now load rom1 and rom2 from the microcode Generator into ROM1 and ROM2 and load “loadrom” from assembler into RAM LOADER (The RAM loader is used to initialize the YACC1 RAM with program code). Now using the control buttons click 
reset on
reset off
load on
wait for all 256 bytes of RAM to load (approx 10 secs at full clock speed)
load off
reset on
reset off
run on
at this point the YACC1 should started could counting by 2 starting at 54
hitting INT will cause number in upper display to be copied into lower display, don’t forget to turn INT off 
