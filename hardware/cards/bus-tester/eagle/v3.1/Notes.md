*Converted from `Notes.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

***** NORTE  *****

May 4/2020

This is based on V1.1 PCB Production design

Updates to prior designs,  should have no electrical differences. 
All lines of bus should be controllable

Removing pull-ups of which currently are on Data and Address lines

FIX on PCB
Join R21 to R9 to gnd 8 leds
This fix is reflected in schematic but not on PCB, PCB uses a jumper

Add bypass. Cap for atmega

Should IN INT support read mode  and be readable/reportable through CLI
