#!/usr/bin/env python3
"""Hold one address on the bus (with -VMA and, optionally, -MEM-RD asserted) so a meter or scope can be put on the
video card's decode pins. The port must stay open: the bus tester resets when it is closed.
usage: hold_address.py HEXADDR [--rd]      then press Enter to release
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver
addr = int(sys.argv[1], 16)
bd = BusDriver(); bd.wait_prompt(timeout=8)
bd.cmd("-BUS-EN", 1); bd.cmd("-VMA", 1); bd.cmd("ADDRBUS-WR-MODE", 1); bd.cmd("DATABUS-RD-MODE", 1)
bd.readmem(0xF000)
bd.cmd("WR-ADDRBUS", addr)
if "--rd" in sys.argv: bd.cmd("-MEM-RD", 1)
input("holding $%04X on the address bus%s - press Enter to release " % (addr, " with -MEM-RD asserted" if "--rd" in sys.argv else ""))
bd.cmd("-MEM-RD", 0); bd.cmd("-VMA", 0)
