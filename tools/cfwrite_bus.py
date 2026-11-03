#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""cfwrite_bus.py - write a disk image onto the CF card in the machine (memory card v2.0's CF section, P8/P9) through
the Bus Test Card, CPU out (2026-11-03). For when no USB CF reader is at hand; tools/cfcard.py is the fast way.

  cfwrite_bus.py IMAGE [tester port] [--from LBA] [--count N] [--verify-only] [--no-verify]

The tester's I/O block commands (bus-driver blocks-2: IOWBK / IORBK, up to 32 / 64 bytes a command on one port) move
the data register's bytes and set the registers (one IOWBK to P8 and one to P9 a register); WRITE SECTORS ($30) and
READ SECTORS ($20) take up to 256 sectors a command, DRQ polled before each sector's 512 bytes. Then every sector is
read back and compared. The times are printed as it goes.
"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from busdrv import BusDriver, PORT

args = sys.argv[1:]
def opt(name, default=None):
    if name in args:
        v = args.pop(args.index(name) + 1); args.remove(name); return v
    return default
first, count = int(opt("--from", "0")), opt("--count")
verify_only, no_verify = "--verify-only" in args, "--no-verify" in args
args = [a for a in args if not a.startswith("--")]
if not args: sys.exit(__doc__)
image = open(args[0], "rb").read()
if len(image) % 512: sys.exit("cfwrite_bus: %s is not a whole number of sectors" % args[0])
total = len(image) // 512
last = total if count is None else min(total, first + int(count))
bd = BusDriver(args[1] if len(args) > 1 else PORT); bd.wait_prompt(timeout=20)
if not bd.blocks: sys.exit("cfwrite_bus: the tester's firmware has no block commands")
c = bd.cmd
BSY, DRDY, DRQ, ERR = 0x80, 0x40, 0x08, 0x01


def out(p, v):
    if int(bd._block_reply("IOWBK:%d,1,%02X#" % (p, v & 0xFF))) != 1: raise RuntimeError("IOWBK failed")


def reg_w(r, v): out(8, r); out(9, v)


def reg_r(r):
    out(8, r)
    return int(bd._block_reply("IORBK:9,1#").split()[0], 16)


def wait(mask, want, t=5.0):
    t0 = time.time()
    while time.time() - t0 < t:
        s = reg_r(7)
        if s & ERR: raise RuntimeError("CF error: status $%02X error $%02X" % (s, reg_r(1)))
        if s & mask == want: return s
    raise RuntimeError("CF timeout: status $%02X" % s)


def command(lba, n, cmd):
    reg_w(6, 0xE0 | (lba >> 24) & 0x0F); reg_w(5, lba >> 16 & 0xFF); reg_w(4, lba >> 8 & 0xFF); reg_w(3, lba & 0xFF)
    reg_w(2, n & 0xFF); reg_w(7, cmd)                       # n = 256 is written as 0


def write_run(lba, data):
    """WRITE SECTORS over len(data) // 512 (1..256) sectors from lba"""
    command(lba, len(data) // 512, 0x30)
    for k in range(0, len(data), 512):
        wait(BSY | DRQ, DRQ); out(8, 0)
        for j in range(k, k + 512, 32):
            if int(bd._block_reply("IOWBK:9,32,%s#" % data[j:j + 32].hex().upper())) != 32:
                raise RuntimeError("IOWBK failed")
        yield lba + k // 512
    wait(BSY | DRQ, 0)


def read_run(lba, n):
    """READ SECTORS over n (1..256) sectors from lba: yields (lba, 512 bytes)"""
    command(lba, n, 0x20)
    for i in range(n):
        wait(BSY | DRQ, DRQ); out(8, 0)
        got = b""
        for j in range(0, 512, 64):
            got += bytes(int(h, 16) for h in bd._block_reply("IORBK:9,64#").split())
        yield lba + i, got


for s in ("-IO-RD", "-IO-WR", "-MEM-RD", "-MEM-WR", "-VMA", "-REG-FUNC-RD", "-REG-FUNC-LD", "-TMP-REG-RD0",
          "-TMP-REG-RD1", "-AC-RD", "-ALU-FUNC", "-AC-LD"):
    c(s, 0)
c("-BUS-EN", 1); bd.no_registers()
out(8, 8); time.sleep(0.1); out(8, 0); time.sleep(0.5)
wait(BSY | DRDY, DRDY)
reg_w(1, 0x01); reg_w(7, 0xEF); wait(BSY, 0)               # SET FEATURES: 8-bit transfers
t0 = time.time()
if not verify_only:
    for run in range(first, last, 256):
        n = min(256, last - run)
        for lba in write_run(run, image[run * 512:(run + n) * 512]):
            if lba % 32 == 31 or lba == last - 1:
                el = time.time() - t0; done = lba - first + 1
                print("write %d/%d sectors, %.0f s, about %.0f s to go" % (done, last - first, el,
                      el / done * (last - first - done)), flush=True)
bad = []
if not no_verify:
    t1 = time.time()
    for run in range(first, last, 256):
        for lba, got in read_run(run, min(256, last - run)):
            if got != image[lba * 512:(lba + 1) * 512]: bad.append(lba)
            if lba % 64 == 63 or lba == last - 1:
                print("verify %d/%d sectors, %d bad, %.0f s" % (lba - first + 1, last - first, len(bad),
                      time.time() - t1), flush=True)
out(8, 0)
print("RESULT: %s" % ("sectors %d-%d %s" % (first, last - 1, "written" if no_verify else "written and verified")
                      if not bad else "%d sectors differ: %s" % (len(bad), bad[:20])))
sys.exit(1 if bad else 0)
