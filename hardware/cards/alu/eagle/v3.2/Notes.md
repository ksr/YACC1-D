*Converted from `Notes.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

Changes since production of ALU-V3.0

Next version V3.2 - OFF TO PRODUCTION

Signal IN and OUT converted from active low to Active HI (Done on Schematic)

BUS changed UNUSED -VMA (not used by ALU) (Done on Schematic)

Should Pin 7 of IC 26 be connected to -ALU-FUNC ?
    Added Jumper to address either scenario  (Done on Schematic)

Looks like change ic10 DIR driven form -AC-RD instead if inverse if -AC-LD (NOT DONE in Schematic) Mod done on current board - done

Board mod D0 D7 shift register (may not be needed)

See Page 3 - BUS Direction change

Page 6 - Should IC28 data inputs d0/d7  be connected to accumulator or shift register
Current board has this partially implemented for pin 5 and 11 - prod has this mod

28/5 - 30-12
28-11 - 29-15

Retest Shift register functionality 

Retest Carry/Shift register

How to clear carry shift? - ADD INSTRUCTION

Test SUBT

Ic6 pin 10 - -ac-ld or ac-ld - added jumper - should be ac-ld

IC32 flipped pins 4 and 5

Flipped AC and BDATA for add/sub circuit
BDATA now goes into xor array
AC directly into adders

Added gating so CO/BO is anded with -ADD/SUB so CO/BO only can go high during add/sub

NEXT VERSION 3.3
