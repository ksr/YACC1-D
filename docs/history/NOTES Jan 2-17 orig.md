*Converted from `NOTES Jan 2-17 orig.rtf` (saved 2020-08-23) by `tools/rtf_to_md.py`; the .rtf is the original.*

BUILD NOTES:

BUS
Add method to chain card together at edge using right angle male/female 96 pin DIN connectors
Once old boards on old bus have been updates mount newer bus card on plywood
    Add Power supply to plywood
    Add on/off switch to above
    Maybe add amp meter???
    Use distribution bus for power (screw terminals)

ALU
IC8A  CARRY SHIFT Register, should it have a reset capability ?
    connect CLR pin 1 to -RESET?
    What about a software reset ability? 
        Should This be done on add/sub without carry

Any Other Status bits required? 
    Look at other CPU designs

IC34 Compare register
    Remove test for 0 from HI data byte (8-15) and replace with INPUT line from bus
    This will allow INPUT signal status line to be same as every other test

SWAP  A and B lines into IC43 and IC44
    First retest this logic with test card and test vectors

Incorporate existing PCB Mods

SEQUENCER LOGIC
IC14 Reuse U-TEST-IN
is soft reset needed or reuse?
sheet 4, cleanup logic now that testin input is gone, use br-cond only
Maybe move HALT and CONTINUE switches to TOP edge

Rename branch register to data immediate and add another 2 x 74374 for add(r?) immediate
clk into new  74374s same as ic26 and 27
output new 74374s to addr lines
Does existing 74374s need separate hi and lo read lines ???
    Can one be use for existing 74374s (DATA) and other for new 74374s (ADDR)
Possible methods for I/O ADDR line
1) Reuse testin line and drive either UNUSED1 or UNUSED2 on bus
2) Is there a way to generate a pulse on UNUSED1 or 2 delayed after 74274 ADDR outputs enabled?

review front panel, new circuit, jumpers? make it easier to add single step clock

fix naming , rename -halt-cont to -fp-halt-cont

SEQUENCER MEMORY
Fixes re PCB Mods
Move CPU reset to top edge of board

SP/PC
Now called ??? ADDR/INDEX/GP
DONE:
USES 7400 NAND (NOT AND) for gating UP/DN signals for counters
UP/DOWN count on rising edge but other line must be high
Example to count up, DOWN line held high, pulse UP by setting/clearing SP/PC-UP - this will appear as low then high at counter pin
DONE:
Front Panel wiring CAREFUL CHECK numbering scheme for RxDx lines from counter chips

DONE:
update sheet 5 to match logic test
DONE:
Arrange so board select can either be driven from unused 1 to become 3rd addr-reg signal or gnd
MAYBE use unused line to add another address line for a 2nd card???

REGISTER BOARD
Now callee DATA REGISTER CARD
incorporate mods to board and verify changes to production design in ‘mods’ DIRECTORY

TBD RESEARCH
Interrupt Line: Should this be open collector with pull down and or up
Input Line: Should this be open collector with pull down and/or up

Should tmp register be on sequencer card or not exist at all
    This would free up two bus lines although the bottleneck is still the number of control signals in sequencer connector

MEMORY CARD - BASIC
How to get info into card ?? Using Front Panel ??

MEMORY CARD - FULL
How many ram chips
    Best case 1 x 64k x 8
    Worst case 8 x 8k x 8

1 4k eprom
eprom mapping circuit
    On reset EPROM is mapped into 0x0000
    all memory access goes to EPROM
    first access to location with addr 15 set (HIGH) 
        remaps EPROM to 0xFxxx 
        RAM is mapped to 0x0000
    Accomplished by first EPROM code BRANCH to 0XF003 (BRANCH instruction is 3 bytes)

I/O CARD

Design Changes (from old file) Incorporate into above info
1) Remove address latch register from register file
    recover bus pins & men cantle pins
    update 1.2 bus definition
        on definition
        cards in progress or prod

2) add temp 8 bit latch to sequencer card to facilitate men to men transfer

3) convert reg card to 8 registers
    modify bus definition to 3 bits register select, 1 bit board select
    modify bus definition + all cords in process

4) Reduce to 8 registers only, jumper to hold the now 1 bit board select to 0
maybe add jumpers so reg selection is 3 bit, tie upper bit to 0

5) TESTER Board
probably (almost for sure) do not need individual pull-ups for CNTL chips
