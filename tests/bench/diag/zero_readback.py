#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""zero_readback.py - bench diagnostic (2026-10-04): which RAM addresses refuse a $00 written through the monitor's
':' loader.

The loader writes each byte and reads it back; it answers '!' when the read-back differs. With the microcode of
2026-09-23 / microcode stage 1 (the six-step fetch prologue), a register count with -MEM-RD still on (review M-1,
docs/system/MICROCODE.md 5.6) puts the register card's LS245s ($FFFF) on the data bus against the memory card's, so
a read can come back with bits set. $00 is the worst case (every bit against $FFFF), and it fails at some addresses
only - in $3E00-$3FFF on 2026-10-04: 3E7C 3EB9 3EBC 3EBD 3EE9 3EF1 3EF9 3EFA 3EFD 3FE9 3FF1 3FF9 3FFD, while every
other value stored there reads back. Stage 2 (the three-step prologue and M-1 in the operand fetches) should leave
none.

  zero_readback.py [--port /dev/cu.usbserial-AB0MVHSQ] [--from 3E00] [--to 4000] [--value 00] [--all-values ADDR]

--from/--to   the range (hex; --to exclusive), one single-byte record per address (~50 ms each)
--value       the byte written (default 00)
--all-values  instead: write every value $00-$FF at this one address and list the refused ones
Writes RAM only (the loader takes $1000-$DFFF); nothing is run. Reset the YACC1 to its '>' prompt first.
"""
import os, sys, time, argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools"))
import monload                                            # noqa: E402  (find_port: the console, not the sequencer)


def record(addr, data):
    b = bytes([len(data), addr >> 8, addr & 0xFF, 0]) + data
    return ":" + (b + bytes([(-sum(b)) & 0xFF])).hex().upper()


class Monitor:
    def __init__(self, port, delay):
        import serial
        self.s = serial.Serial(port, 38400, timeout=0.05)
        self.delay = delay / 1000.0
        self.s.reset_input_buffer(); self.s.write(b"\r"); time.sleep(0.5)
        if b">" not in self.s.read(200):
            sys.exit("zero_readback: no '>' from the monitor on %s: reset the YACC1" % port)

    def send(self, text):
        for ch in text.encode():
            self.s.write(bytes([ch])); self.s.flush(); time.sleep(self.delay)

    def store(self, addr, value):
        """one byte through the loader -> its answer: '.' stored, '?' bad record, '!' refused / read back wrong"""
        self.send(record(addr, bytes([value])))
        end = time.time() + 5; buf = b""
        while time.time() < end:
            buf += self.s.read(64)
            for w in (b".", b"?", b"!"):
                if w in buf: return w.decode()
        sys.exit("zero_readback: no answer to the record for %04X" % addr)

    def finish(self):
        self.send(":00000001FF")
        end = time.time() + 4; buf = b""
        while time.time() < end and b">" not in buf: buf += self.s.read(64)
        self.s.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port")
    ap.add_argument("--from", dest="lo", default="3E00")
    ap.add_argument("--to", dest="hi", default="4000")
    ap.add_argument("--value", default="00")
    ap.add_argument("--all-values", dest="one")
    ap.add_argument("--delay", type=float, default=3.0, help="ms between characters (monload's default)")
    a = ap.parse_args()
    m = Monitor(a.port or monload.find_port(), a.delay)
    t0 = time.time()
    if a.one:
        addr = int(a.one, 16)
        bad = [v for v in range(256) if m.store(addr, v) != "."]
        m.finish()
        print("values refused at $%04X: %s (%.0f s)" % (addr, " ".join("%02X" % v for v in bad) or "none",
                                                        time.time() - t0))
    else:
        lo, hi, v = int(a.lo, 16), int(a.hi, 16), int(a.value, 16)
        if not 0x1000 <= lo < hi <= 0xE000:
            sys.exit("zero_readback: the loader takes $1000-$DFFF only")
        bad = [x for x in range(lo, hi) if m.store(x, v) != "."]
        m.finish()
        print("$%02X refused at %d of %d addresses in $%04X-$%04X: %s (%.0f s)"
              % (v, len(bad), hi - lo, lo, hi - 1, " ".join("%04X" % x for x in bad) or "none", time.time() - t0))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
