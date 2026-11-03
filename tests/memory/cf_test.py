#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""The memory card v2.0's CF section through the Bus Test Card (bus-driver firmware), CPU out (2026-11-03).

The tester plays the sequencer for OUTI/INP: IOADDR0..3 = the port, the byte on DATA0..7, a -IO-WR pulse or -IO-RD
held while DATA is read. P8 = the IC32 latch (bits 0-2 the ATA register, bit 3 the CF reset), P9 = the selected
register through IC34 (8-bit True IDE; hardware/cards/memory/kicad/v2.0/README.md).

  reset       P8 bit 3 pulsed; the status register must come up $50 (ready, seek complete) within 5 s
  registers   sector count and LBA0-2 written and read back: 12 patterns each (every data bit both ways)
  8-bit mode  SET FEATURES $01 (as the monitor does): no error bit
  IDENTIFY    the 512-byte answer: model, firmware, size (proves every data line, -IOR and the register select)
  sector 0    LBA 0 read, its first bytes and the $55 $AA signature printed; saved with --save FILE
Every read is about 10 tester commands at 19200 baud: IDENTIFY and the sector take about 5 minutes each.

  --hold      no test: select the status register and leave a P9 read held (-IO-RD low) for the meter;
              the tester keeps that state until the next command is sent
  --quick     reset, registers and 8-bit mode only (seconds)

If every register reads $FF the CF is not answering: check the adapter's master/slave jumper first (master), then
docs/procedures/CF-CARD.md, "When the machine cannot see the card".
usage: cf_test.py [tester port] [--hold | --quick] [--save FILE]
"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
from busdrv import BusDriver, PORT

args = sys.argv[1:]
save = args.pop(args.index("--save") + 1) if "--save" in args else None
if "--save" in args: args.remove("--save")
hold, quick = "--hold" in args, "--quick" in args
port = next((a for a in args if not a.startswith("--")), PORT)
bd = BusDriver(port); bd.wait_prompt(timeout=20)
c = bd.cmd
STATUS, CMD = 7, 7
BSY, DRDY, DRQ, ERR = 0x80, 0x40, 0x08, 0x01

def ioaddr(p):
    for i in range(4): c("IOADDR%d" % i, (p >> i) & 1)

def out(p, v):
    ioaddr(p); c("DATABUS-WR-MODE", 1); c("WR-DATABUS", v & 0xFF); c("-IO-WR", 1); c("-IO-WR", 0)

def inp(p):
    ioaddr(p); c("DATABUS-RD-MODE", 1); c("-IO-RD", 1); v = int(c("RD-DATABUS-L")); c("-IO-RD", 0)
    return v

def reg_w(r, v): out(8, r); out(9, v)
def reg_r(r): out(8, r); return inp(9)

for s in ("-IO-RD", "-IO-WR", "-ALU-FUNC", "-AC-RD", "-AC-LD", "-MEM-RD", "-MEM-WR", "-VMA", "-REG-FUNC-RD",
          "-REG-FUNC-LD", "-TMP-REG-RD0", "-TMP-REG-RD1"):
    c(s, 0)
c("-BUS-EN", 1); bd.no_registers(); c("ADDRBUS-WR-MODE", 1); c("WR-ADDRBUS", 0)

if hold:
    out(8, STATUS); ioaddr(9); c("DATABUS-RD-MODE", 1); c("-IO-RD", 1)
    print("holding a status read: P8 = 7 (DA2..0 = 111), IOADDR = 9, -IO-RD low, -IO-WR high; bus reads $%02X\n"
          "expect at J2: 1 high, 23 high, 25 low, 33/35/36 high, 37 low, 38 high; D0-D7 (17, 15 .. 3) = the status"
          % int(c("RD-DATABUS-L")))
    sys.exit(0)

fails = 0
def report(name, ok, detail):
    global fails; fails += not ok
    print("%-11s %s  %s" % (name, "PASS" if ok else "FAIL", detail), flush=True)

def wait_ready(t=5.0):
    t0 = time.time(); s = reg_r(STATUS)
    while time.time() - t0 < t and (s & BSY or not s & DRDY):
        s = reg_r(STATUS)
    return s

def wait_drq(t=5.0):
    t0 = time.time(); s = reg_r(STATUS)
    while time.time() - t0 < t and not s & DRQ:
        s = reg_r(STATUS)
    return s

def read_data():
    out(8, 0)                                            # the data register; P9 reads now step through the buffer
    return bytes(inp(9) for _ in range(512))

out(8, 8); time.sleep(0.1); out(8, 0); time.sleep(0.5)
s = wait_ready()
report("reset", s == 0x50, "status $%02X (expect $50: ready, seek complete)" % s)
if s == 0xFF:
    print("RESULT: no drive answers (status $FF): check the adapter's master/slave jumper (master) first")
    sys.exit(1)

bad = []
for r in (2, 3, 4, 5):
    for v in (0x00, 0xFF, 0x55, 0xAA) + tuple(1 << i for i in range(8)):
        reg_w(r, v); g = reg_r(r)
        if g != v: bad.append("reg%d wrote %02X read %02X" % (r, v, g))
report("registers", not bad, "; ".join(bad[:6]) if bad else "sector count, LBA0-2 x 12 patterns read back")

reg_w(6, 0xE0); reg_w(1, 0x01); reg_w(CMD, 0xEF); s = wait_ready()
report("8-bit mode", not s & ERR, "status $%02X error $%02X" % (s, reg_r(1)))

if not quick:
    reg_w(6, 0xE0); reg_w(CMD, 0xEC); s = wait_drq()
    d = read_data(); after = reg_r(STATUS)
    w = lambda i: d[2 * i] | d[2 * i + 1] << 8
    text = lambda a, b: bytes(x for i in range(a, b, 2) for x in (d[i + 1], d[i])).decode("latin1").strip()
    model, fw, sectors = text(54, 94), text(46, 54), w(60) | w(61) << 16
    ok = s != 0xFF and s & DRQ and 0 < sectors < 0xFFFFFFFF and model.isprintable() and model != ""
    report("IDENTIFY", bool(ok), "model '%s' fw '%s', %d sectors (%.1f MB); status $%02X before, $%02X after"
           % (model, fw, sectors, sectors / 2048, s, after))

    reg_w(6, 0xE0); reg_w(5, 0); reg_w(4, 0); reg_w(3, 0); reg_w(2, 1); reg_w(CMD, 0x20); s = wait_drq()
    sec = read_data(); after = reg_r(STATUS)
    report("sector 0", bool(s & DRQ) and not after & ERR, "status $%02X; first bytes %s; last two %02X %02X%s"
           % (s, sec[:16].hex(" "), sec[510], sec[511], " (boot signature)" if sec[510:] == b"\x55\xAA" else ""))
    if save:
        open(save, "wb").write(sec)

out(8, 0)
print("RESULT: %s" % ("ALL PASS" if not fails else "%d FAIL" % fails))
sys.exit(1 if fails else 0)
