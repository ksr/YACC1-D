#!/usr/bin/env python3
"""Minimal reproduction of the video-card write-through fault.

A write to $0010 (block 0, A0=0) also writes the video RAM cell at $D010.
Expected on a good card: D010 keeps 11.  Fault: D010 reads 22.
"""
import sys
from busdrv import BusDriver

bd = BusDriver(sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-AB6WZCQX")
bd.wait_prompt(timeout=8)

# --- setup: reset, enable bus, valid-memory-address, address bus out, data bus in
bd.pulse("-RESET")
bd.cmd("-BUS-EN", 1)
bd.cmd("-VMA", 1)
bd.cmd("ADDRBUS-WR-MODE", 1)
bd.cmd("DATABUS-RD-MODE", 1)
bd.readmem(0xF000)            # one A15-high access releases the memory card's boot remap

# --- seed the video cell with 11
bd.cmd("DATABUS-WR-MODE", 1)
bd.writemem(0xD010, 0x11)     # WR-ADDRBUS:53264  WR-DATABUS:17  -MEM-WR:1  -MEM-WR:0

# --- the trigger: write 22 to block 0, same low bits, A0 = 0
bd.writemem(0x0010, 0x22)     # WR-ADDRBUS:16     WR-DATABUS:34  -MEM-WR:1  -MEM-WR:0

# --- read the video cell back
bd.cmd("DATABUS-RD-MODE", 1)
v = bd.readmem(0xD010)        # WR-ADDRBUS:53264  -MEM-RD:1  RD-DATABUS-L:0  -MEM-RD:0
print("D010 = %02X  ->  %s" % (v, "FAULT REPRODUCED (write to 0010 landed in video RAM)" if v == 0x22 else "no fault"))

# --- control: the same thing from block 1 must NOT alias
bd.cmd("DATABUS-WR-MODE", 1)
bd.writemem(0xD010, 0x11)
bd.writemem(0x1010, 0x33)
bd.cmd("DATABUS-RD-MODE", 1)
v = bd.readmem(0xD010)
print("control from 1010: D010 = %02X  ->  %s" % (v, "ok (no alias, as expected)" if v == 0x11 else "unexpected"))
