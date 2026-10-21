#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""crtc_picture.py - a picture from the video card with the CPU out (2026-10-10): the Bus Test Card writes the test card
into the display RAM and programs the 6845, then lets go. The 6845 runs from the card's own clock, so the picture stays
on the monitor while the tester holds nothing - the video side (crystal, character clock, EPROM, shift register, sync)
can be brought up before the CPU and the E one-shot matter at speed.

  crtc_picture.py [port] [--regs R0,R1,...] [--dotclock HZ] [--blank] [--png OUT.png] [--verify]

  --regs      R0..R15 (decimal or 0x..; missing ones from testcard.asm's table = the ROM's, cursor at row 12 col 40)
  --dots      dots a character (default 6: IC28 a 74163, fitted 2026-10-18; 5 = the drawn 74HC160)
  --dotclock  the crystal (or crystal/2 with SV4 on 2-3) for the timing report (default 10e6, the ROM's assumption)
  --blank     fill the RAM with spaces instead of the test card (a raster with nothing on it: sync only)
  --png       also draw what the monitor should show (tools/vidsim.py, same RAM and registers)
  --verify    read the 2K back and compare (the RAM half through the tester, as video_ram_test.py does for 1K)

The registers are written once each, slowly: with finding 6.1 (C1, the E one-shot) a register write may be lost -
crtc_regs.py --gap 0.5 shows whether that happens; this script waits --wait seconds (default 0.3) between register
writes for the same reason. The test card is tests/video/asm/testcard.asm's, byte for byte (tools/vidsim.py testcard_ram).
"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
from busdrv import BusDriver, PORT
import vidsim

args = sys.argv[1:]
def opt(name, default):
    if name in args:
        v = args.pop(args.index(name) + 1); args.remove(name); return v
    return default
regs = [int(x, 0) for x in opt("--regs", "").split(",") if x] or []
regs = regs + vidsim.TESTCARD_TABLE[len(regs):]
dotclock = float(opt("--dotclock", 10e6)); png = opt("--png", None); wait = float(opt("--wait", 0.3))
vidsim.DOTS = int(opt("--dots", 6))   # IC28 a 74163 since 2026-10-18: dot clock / 6
blank = "--blank" in args; verify = "--verify" in args
port = next((a for a in args if not a.startswith("--")), PORT)

vidsim.timing(regs, dotclock)
ram = bytes(b" " * 2048) if blank else vidsim.testcard_ram()

bd = BusDriver(port); bd.wait_prompt(timeout=20)
c = bd.cmd
c("-BUS-EN", 1); bd.no_registers(); c("-VMA", 1); c("ADDRBUS-WR-MODE", 1); c("DATABUS-RD-MODE", 1)
bd.pulse("-RESET"); bd.readmem(0xF000)
t0 = time.time()
bd.write_block(0xD000, ram)
print("display RAM written: 2048 bytes in %.1f s" % (time.time() - t0))
c("DATABUS-WR-MODE", 1)
for r, v in enumerate(regs[:16]):
    bd.writemem(0xD800, r); time.sleep(wait / 2)
    bd.writemem(0xD802, v); time.sleep(wait / 2)
c("DATABUS-RD-MODE", 1)
print("6845 R0-R15 written: " + " ".join("%02X" % v for v in regs[:16]))
cur = []
for r in (14, 15):
    c("DATABUS-WR-MODE", 1); bd.writemem(0xD800, r); c("DATABUS-RD-MODE", 1); time.sleep(wait / 2)
    cur.append(bd.read_block(0xD802, 1)[0]); time.sleep(wait / 2)   # fast: E ends ~12 ms after the strobe (crtc_regs.py)
print("cursor read back R14:R15 = %02X%02X (written %02X%02X)%s" % (cur[0], cur[1], regs[14] & 0x3F, regs[15],
      "" if cur == [regs[14] & 0x3F, regs[15]] else "  - the register path is not working: crtc_regs.py"))
if verify:
    back = bytes(bd.read_block(0xD000, 2048))
    bad = [i for i in range(2048) if back[i] != ram[i]]
    print("RAM read back: %s" % ("identical" if not bad else "%d bytes differ, first $%04X: %02X (wrote %02X)" % (
        len(bad), 0xD000 + bad[0], back[bad[0]], ram[bad[0]])))
c("-VMA", 0); c("-BUS-EN", 0); bd.ser.close()
print("the tester has let go of the bus: the picture is the 6845's now")
if png:
    st = vidsim.State(regs, ram)
    W, H, img = vidsim.picture(st)
    vidsim.write_png(png, W, H, img, 2, 4)
    print("expected picture: %s" % png)
