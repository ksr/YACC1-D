*Converted from `NOTES-Update from old project.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

BUILD NOTES:

BUS

Original
Add method to chain card together at edge using right angle male/female 96 pin DIN connectors
Once old boards on old bus have been updates mount newer bus card on plywood
    Add Power supply to plywood
    Add on/off switch to above
    Maybe add amp meter
    Use distribution bus for power (screw terminals)

YACC2020 updates and carry forward
Built “Horizontal and Vertical” bus card connectors
Original Horizontal (Side by Side) Connector had long parallel runs close together causing crosstalk
    New board designed with extra separation between traces as well as ground and vcc planes

Side by Side Now mounted on MDF
    Use larger and add Power Supply to board
        Add switch?
        Amp measurement?
    Easy access to vcc and gnd for test probes maybe trough screw terminal bus bar
    Capacitors to bus boards?

ALU

Original
IC8A  CARRY SHIFT Register, should it have a reset capability ?
    DONE
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

YACC2020 updates and carry forward
IC8A now IC9A  CARRY SHIFT Register, should it have a reset capability ?
    DONE connected CLR pin 1 to -RESET?
    What about a software reset ability? 
        Should This be done on add/sub without carry
        Not done, how else could this be achieved

Any Other Status bits required? 
    Look at other CPU designs

C34 Now IC26 Compare register
    Remove test for 0 from HI data byte (8-15) and replace with INPUT line from bus
    This will allow INPUT signal status line to be same as every other test
        DONE

SWAP  A and B lines into IC43 and IC44 now ic35 and IC36
    First retest this logic with test card and test vectors
        Done
    BUT the actual change needed might be have accumulator goes to ic35 & 36 A gates and 
    BDATA goes to XOR gates ic33 and ic34 
    Might need to model all this in a simulator

Incorporate existing PCB Mods
    No idea, will move forward and debug new model
    

SEQUENCER LOGIC

Original
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

YACC2020 updates and carry forward
IC14 Reuse U-TEST-IN 
sheet 4, cleanup logic now that testin input is gone, use br-cond only
    Redesigned, IN is now tested in ALU and comes in on BR-COND bus line
    No longer need control signal TEST-IN, setting ALU to 0x0 (all 4 bits 0) forces BR-COND to HIGH (1)

is soft reset needed or reuse?
    Done - Removed

Maybe move HALT and CONTINUE switches to TOP edge
    Done - Moved

Rename branch register to data immediate and add another 2 x 74374 for add(r?) immediate
    No physical change required - have not changed signal names yet (seems to make sense)
    Due to register redesign no need for addr immediate registers on sequencer board

New removed 1-byte-operand-select, not needed. Use 2-byte-operand-select and its inverse to select buffer to select
    Remove from control signals

Does existing branch (data) 74374s need separate hi and lo read lines ???
    Can one be use for existing 74374s (DATA) and other for new 74374s (ADDR)
    Keeping both for safety but really may not need, lets address with a jumper so we can test and maybe remove in a future design

Possible methods for I/O ADDR line
1) Reuse testin line and drive either UNUSED1 or UNUSED2 on bus
2) Is there a way to generate a pulse on UNUSED1 or 2 delayed after 74274 ADDR outputs enabled?
    Not sure waht this is about about IO-ADDR completely redesign for YACC-2020

review front panel, new circuit, jumpers? make it easier to add single step clock
    Front panel connections removed
    added jumper to support external off board single step clock
    
fix naming , rename -halt-cont to -fp-halt-cont
    Done

SEQUENCER MEMORY

Original
Fixes re PCB Mods
Move CPU reset to top edge of board

YACC2020 updates and carry forward
Fixes re PCB Mods
    Redesign so changes not done or carried forward. Most changes looked like addition or reuse control lines 

Move CPU reset to top edge of board
    Done

SP/PC

Original
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

YACC2020 updates and carry forward
    This board is no longer used

REGISTER BOARD

Original
Now called DATA REGISTER CARD
incorporate mods to board and verify changes to production design in ‘mods’ DIRECTORY

TBD RESEARCH
Interrupt Line: Should this be open collector with pull down and or up
Input Line: Should this be open collector with pull down and/or up

Should tmp register be on sequencer card or not exist at all
    This would free up two bus lines although the bottleneck is still the number of control signals in sequencer connector

YACC2020 updates and carry forward
    Big redesign - Card no longer has address bus section

ADDRESS & TMP REGISTER BOARD

Original
New Card

YACC2020 updates and carry forward
New Card
    

MEMORY CARD - 

Original
BASIC
How to get info into card ?? Using Front Panel ??

FULL
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

YACC2020 updates and carry forward
New Card

2 - 32k x 8 bit ram chips

eprom mapping circuit
    On reset EPROM is mapped into 0x0000
    all memory access goes to EPROM
    first access to location with addr 15 set (HIGH) 
        remaps EPROM to 0xFxxx 
        RAM is mapped to 0x0000
    Accomplished by first EPROM code BRANCH to 0XF003 (BRANCH instruction is 3 bytes)

I/O CARD

Original
New Card

YACC2020 updates and carry forward
New Card
8 toggle swtiches and LEDS
OUT LED
IN Switch
TIL 311 output - tied to LEDS (should this be separate cantle)
2x20 LCD panel
16550 UART based serial IO

Design Changes (from old file) Incorporate into above info
This section was ignored for YACC-2020

1) Remove address latch register from register file
    recover bus pins & men control pins
    update 1.2 bus definition
        on definition
        cards in progress or prod

2) add temp 8 bit latch to sequencer card to facilitate mem to mem transfer

3) convert reg card to 8 registers
    modify bus definition to 3 bits register select, 1 bit board select
    modify bus definition + all cords in process

4) Reduce to 8 registers only, jumper to hold the now 1 bit board select to 0
maybe add jumpers so reg selection is 3 bit, tie upper bit to 0

5) TESTER Board
probably (almost for sure) do not need individual pull-ups for CNTL chips
