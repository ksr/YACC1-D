#!/usr/bin/env python3
"""Minimal host driver for the YACC1 Bus Test Card (bus-driver.ino).

Wire protocol (from bus-driver.ino):
  host  -> card : CMD:OPERAND#        operand is DECIMAL, no line ending
  card  -> host : optional "Data: <n>" and "Complete" lines, then ">>" prompt
Active-low signals are named with a leading '-' and the firmware inverts them,
so  -RESET:1  asserts reset.
"""
import sys, time, argparse
import serial

PORT = "/dev/cu.usbserial-AB6WZCQX"
BAUD = 19200


class BusDriver:
    def __init__(self, port=PORT, baud=BAUD, log=None, timeout=3.0):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.timeout = timeout
        self.log = log

    def _readline(self, deadline):
        buf = b""
        while time.time() < deadline:
            c = self.ser.read(1)
            if not c:
                continue
            if c in b"\r\n":
                if buf:
                    return buf.decode("ascii", "replace")
                continue
            buf += c
            if buf.endswith(b">>"):
                return buf.decode("ascii", "replace")
        raise TimeoutError("no line from card (partial=%r)" % buf)

    def wait_prompt(self, timeout=None):
        """Read lines until the '>>' prompt; return the lines before it."""
        deadline = time.time() + (timeout or self.timeout)
        lines = []
        while True:
            line = self._readline(deadline)
            if self.log:
                self.log.write("  < %s\n" % line)
            if line.strip().endswith(">>"):
                return lines
            lines.append(line)

    def cmd(self, name, operand=0):
        """Send one command and return the integer from a 'Data: n' reply, or None."""
        msg = "%s:%d#" % (name, int(operand))
        if self.log:
            self.log.write("> %s\n" % msg)
        self.ser.write(msg.encode("ascii"))
        lines = self.wait_prompt()
        val = None
        for l in lines:
            if l.startswith("Data:"):
                val = int(l.split(":", 1)[1].strip())
            elif l.startswith("Error"):
                raise RuntimeError("card error after %s: %s" % (msg, l))
        return val

    def pulse(self, name):
        self.cmd(name, 1)
        self.cmd(name, 0)

    # --- memory idioms, copied from command_sender_8.pde ---
    def mem_setup_read(self):
        self.cmd("-VMA", 1)
        self.cmd("ADDRBUS-WR-MODE", 1)
        self.cmd("DATABUS-RD-MODE", 1)

    def readmem(self, addr):
        self.cmd("WR-ADDRBUS", addr)
        self.cmd("-MEM-RD", 1)
        v = self.cmd("RD-DATABUS-L", 0)
        self.cmd("-MEM-RD", 0)
        return v

    def dump(self, start, end):
        self.mem_setup_read()
        out = []
        row = []
        for a in range(start, end + 1):
            row.append(self.readmem(a))
            if (a & 0x0F) == 0x0F or a == end:
                base = a & ~0x0F
                out.append("%04X: %s" % (base, " ".join("%02X" % v for v in row)))
                row = []
        return out

    def writemem(self, addr, val):
        self.cmd("WR-ADDRBUS", addr)
        self.cmd("WR-DATABUS", val)
        self.pulse("-MEM-WR")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=PORT)
    ap.add_argument("--probe", action="store_true", help="open port, wait for prompt, read switches")
    ap.add_argument("--dump", nargs=2, metavar=("START", "END"), help="hex range to dump")
    ap.add_argument("--reset", action="store_true", help="pulse -RESET first")
    ap.add_argument("--raw", nargs="*", help="raw commands like -RESET:1")
    ap.add_argument("-v", action="store_true", help="log wire traffic")
    a = ap.parse_args()

    bd = BusDriver(a.port, log=sys.stderr if a.v else None)
    print("port open; waiting for prompt (DTR reset -> LED flash ~1s)...")
    banner = bd.wait_prompt(timeout=8)
    print("prompt received; banner lines:", banner)

    if a.reset:
        bd.pulse("-RESET")
        print("reset pulsed")
    if a.probe:
        print("READ-SWITCHES ->", bd.cmd("READ-SWITCHES"))
        print("RD-IN         ->", bd.cmd("RD-IN"))
        print("RBR-COND      ->", bd.cmd("RBR-COND"))
    if a.raw:
        for r in a.raw:
            n, _, op = r.partition(":")
            print(r, "->", bd.cmd(n, int(op or 0, 0)))
    if a.dump:
        s, e = (int(x, 16) for x in a.dump)
        for line in bd.dump(s, e):
            print(line)
