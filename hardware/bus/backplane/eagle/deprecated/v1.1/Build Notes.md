*Converted from `Build Notes.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

Build Notes: Bus Cards

Always start with a quick board check (See BUS description)
GND
3 FAR right and 3 FAR LEFT BUS (any bus connector) pins are connected
VCC
3 next to GND right and 3 next to GND LEFT BUS (any bus connector) pins are connected
Test VCC not shorted to GND
Test VCC is connected to board, use C1
Test GND is connected to board, use C1

I like building boards in reverse height order:

1) Lay flat resistors
2) Bus connectors
    Bolt connectors in before soldering and verify all pins are properly through holes
    Recommend soldering the middle of pins followed by the outside rows
3) LED (note flat side), Resistor, and Power (Included in package are M/F barrel connectors
4) Capacitors, only 2 required - C2 & CV5  - NOTE polarity

Bringing up the board 
1) Test VCC and GND are not shorted
2) Apply power, LED is light up
3) Plug into Bus Test Card
4) Use bus-test Arduino program to verify bus has no shorts
