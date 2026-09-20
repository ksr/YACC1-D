*Converted from `Build Notes.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

Build Notes: Memory Card

Always start with a quick board check (See BUS description)
GND
3 FAR right and 3 FAR LEFT BUS connector pins are connected
VCC
3 next to GND right and 3 next to GND LEFT BUS connector pins are connected
Test VCC not shorted to GND
Test VCC is connected to board, use C1  (any bypass cap has a GND side and a VCC side)
Test GND is connected to board, use C1 (any bypass cap has a GND side and a VCC side)

I like building boards in reverse height order:

1) Lay flat resistors
2) IC Sockets, no need to install SIP connectors
3) LEDS & Standup resistors (non on this board)
    LEDS are polarized and have a flat side as indicated on the board silkscreen
4) Jumpers
5) Bus connector
    Bolt connector in before soldering and verify all pins are properly through holes
    Recommend soldering the middle of pins followed by the outside rows
6) The exception to the height rule, I do bypass caps last

EEPROM & Sockets
Solder 1 machined 28 pin socket into IC13
Place EEPROMS into separate machined sockets
Add/Remove EEPROMS from board keeping EEPROMS in their own milled sockets

Bringing up the board 
1) Test VCC and GND are not shorted
2) Plug board into bus and apply power to bus
    - PWR LED should come on
3) Install Bus Test Card
    Install Bus-Test program and check for shorts
4) Install all ICs in Memory card
    Install Bus Driver Arduino program
    Use Processing Command Sender (to be documented) and use memory test script
