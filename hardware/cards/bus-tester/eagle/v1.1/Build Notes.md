*Converted from `Build Notes.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

Build Notes: Bus Test Card

Always start with a quick board check (See BUS description)
GND
3 FAR right and 3 FAR LEFT BUS connector pins are connected
VCC
3 next to GND right and 3 next to GND LEFT BUS connector pins are connected
Test VCC not shorted to GND
Test VCC is connected to board, use C1  (any bypass cap has a GND side and a VCC side)
Test GND is connected to board, use C1 (any bypass cap has a GND side and a VCC side)

A couple of notes

R12 & R10 are 2.2k resistors (forget to send in package)
C6 and C7 are 22pf and are packaged with the XTAL
Also with XTAL is an insulator to place between the XTAL and the board
This board has no polarized capacitors
No need to install 10K - R2 through R7

I like building boards in reverse height order:

1) Lay flat resistors
2) IC Sockets, SIP Sockets, and XTAL
3) Smaller switches (BUS-RESET, CPU-RESET, S-A, S-B)
4) LEDS & Standup resistors (non on this board)
    LEDS are polarized and have a flat side as indicated on the board silkscreen
5) Jumpers
6) Large Switches (Use template to assist with alignment)
7) Bus connector
    Bolt connector in before soldering and verify all pins are properly through holes
    Recommend soldering the middle of pins followed by the outside rows
8) The exception to the height rule, I do bypass caps last

Bringing up the board 
1) Test VCC and GND are not shorted
2) NO BUS - Apply power to board by connecting FTDI cable and jumper FTDI-VCC jumper
2) With Bus - Plug board into bus and apply power to bus
    - in either case PWR LED should come on
3) Install ATMEGA (ARDUINO) Chip and connect FTDI connector
    Jumper DTR-RESET (resets ATMEGA chip on port open)
    If powering from bus remove FTDI-VCC jumper
    If powering from FTDI install jumper
    Start Arduino IDE and select proper serial port
    Install Arduino example “Blink” program
    Install Memory Chip IC7
    Test memory with program “mem” in Software->BUS-TEST-CARD->Test EEPROM->mem.ino
    Install IC8 & IC9
    Test Switches and LEDs with led-switch-test.ino
         This program continuously reads switches, adds 1, and displays on LEDS
    Install remaining ICs
    Test for shorts with bus-test
