#!/usr/bin/env python3
"""Verify the memory card's ROM against the sources: read $E000-$FFFF through the Bus Test Card and compare every byte
with the image tools/romimage.py assembles from firmware/basic/basic.img + firmware/monitor/monitor.img (what the emulator
loads). ~30 s with the blocks-1 firmware. Prints the mismatches (if any) and writes the readback to
tests/memory/rom-readback-<date>.bin when --save is given.
usage: rom_verify.py [port] [--save]"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from busdrv import BusDriver, PORT
from romimage import rom_image
port = next((a for a in sys.argv[1:] if not a.startswith("--")), PORT)
ref = rom_image()
bd = BusDriver(port); bd.wait_prompt(timeout=8)
bd.pulse("-RESET"); bd.cmd("-BUS-EN", 1); bd.cmd("-VMA", 1); bd.cmd("ADDRBUS-WR-MODE", 1); bd.cmd("DATABUS-RD-MODE", 1)
bd.readmem(0xF000)   # release the boot remap
t = time.time(); got = bytes(bd.read_block(0xE000, 8192)); dt = time.time() - t
bad = [a for a in range(8192) if got[a] != ref[a]]
defined = sum(1 for a in range(8192) if ref[a] != 0xFF)
print("reference: basic.img ($E000) + monitor.img ($F000), %d bytes defined, rest $FF" % defined)
print("chip:      8192 bytes read in %.0f s" % dt)
if bad:
    print("MISMATCH: %d bytes differ" % len(bad))
    for a in bad[:32]: print("  $%04X  chip %02X  sources %02X" % (0xE000 + a, got[a], ref[a]))
else:
    print("IDENTICAL: the ROM holds exactly what the emulator loads")
if "--save" in sys.argv:
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rom-readback-%s.bin" % time.strftime("%Y-%m-%d")); open(p, "wb").write(got); print("readback saved:", p)
sys.exit(1 if bad else 0)
