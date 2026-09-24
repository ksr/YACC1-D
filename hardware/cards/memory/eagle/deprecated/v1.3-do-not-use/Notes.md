*Converted from `Notes.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

Changes since production of Memory 1.0

Added ROM select logic at boot
Add memory map ROM to 0x0000 until 0xf000 is accessed and then remapped to 0Xf000

Since 1.1

Added -VMA to bus

-VMA to enable 74245 bus data buffer pin 19

ROM address map triggered by HIGH on ADDR15 not BADDR15

RN3&4 BADDR pull-ups not needed, leave in design

Add -VMA to IC7 74138 pin 4 so ROM & HI Ram can only  be selected with -VMA asserted 

Combine -VMA and LOW BADDR15 to generate -CS for LOW RAM so LOW RAM cannot be selected with -VMA not asserted

7400 was not needed once enable circuit changed for IC5 74245

7400 added back in to generate LOW RAM -CS

ALL Above reflected V1.1 mods and V1.2 working schematics 

Next version 1.3

ARGH, 74ls138 IC 7 add jumpers so any 4k block can be removed (for memory map IO)
Add jumpers with pull-ups to VCC
For example add a jumper so pin 15 IC7 can be disconnected  from IC4 pin 2, on IC4 side add a pull-up
This will only allow mapping into hi 32k which should be fine

Should tmp registers be moved to ALU - I do not see why
Hard jumper a boot loader enable ?
Jump select by 4k block EEPROM
Sho tmp-registers use -BUS-EN

OLD NOTES

Signal IN and OUT converted from active low to Active HI

This change is reflected in schematic

IN OUT not used in memory board
