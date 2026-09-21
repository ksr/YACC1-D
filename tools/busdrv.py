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
        self.banner = []      # lines the card prints before its first prompt (filled by the first wait_prompt)
        self.blocks = False   # True once the banner shows a firmware with RDBLK/WRBLK (2026-09-21 or later)

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
                if not self.banner and lines:
                    self.banner = list(lines)
                    self.blocks = any("blocks-" in l for l in lines)
                return lines
            lines.append(line)

    on_reopen = None      # callable run after the port had to be reopened (the card resets on open: redo mode setup)
    retries = 3           # resends after a reply timeout
    reopen_wait = 1800    # seconds to keep waiting for a vanished port

    def _reopen(self):
        """The port dropped (USB glitch): wait for it to come back, reopen, let the card boot, redo the caller's setup."""
        try: self.ser.close()
        except Exception: pass
        deadline = time.time() + self.reopen_wait
        while True:
            try:
                self.ser = serial.Serial(self.ser.port, self.ser.baudrate, timeout=0.1); break
            except Exception:
                if time.time() > deadline: raise
                time.sleep(5)
        self.wait_prompt(timeout=10)
        if self.log: self.log.write("  ! port reopened\n")
        if self.on_reopen: self.on_reopen()

    def cmd(self, name, operand=0):
        """Send one command and return the integer from a 'Data: n' reply, or None.
        Resends after a reply timeout (commands are level-sets and reads, so a repeat is harmless) and survives the
        port vanishing (waits for it, reopens, re-runs on_reopen, then resends)."""
        msg = "%s:%d#" % (name, int(operand))
        for attempt in range(self.retries + 1):
            try:
                if self.log:
                    self.log.write("> %s\n" % msg)
                self.ser.reset_input_buffer()
                self.ser.write(msg.encode("ascii"))
                lines = self.wait_prompt()
                break
            except TimeoutError:
                if attempt == self.retries: raise
                if self.log: self.log.write("  ! no reply, resending\n")
                time.sleep(0.5)
            except (serial.SerialException, OSError):
                if attempt == self.retries: raise
                self._reopen()
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
        vals = self.read_block(start, end - start + 1)
        out = []
        for a in range(start, end + 1):
            if (a & 0x0F) == 0 or a == start:
                out.append("%04X:" % a)
            out[-1] += " %02X" % vals[a - start]
        return out

    def writemem(self, addr, val):
        self.cmd("WR-ADDRBUS", addr)
        self.cmd("WR-DATABUS", val)
        self.pulse("-MEM-WR")

    # --- block transfers (firmware "blocks-1", 2026-09-21): one round trip per up to 64 bytes.
    # Both fall back to the per-byte idioms on an older firmware, so callers can always use them.
    BLOCK = 64        # RDBLK bytes per round trip
    WBLOCK = 32       # WRBLK bytes per round trip (the Uno's RAM)

    def _block_reply(self, msg):
        """send a block command, return the text after 'Data:' (raises on an 'Error:' line)"""
        for attempt in range(self.retries + 1):
            try:
                if self.log: self.log.write("> %s\n" % msg)
                self.ser.reset_input_buffer(); self.ser.write(msg.encode("ascii"))
                lines = self.wait_prompt(); break
            except TimeoutError:
                if attempt == self.retries: raise
                time.sleep(0.5)
            except (serial.SerialException, OSError):
                if attempt == self.retries: raise
                self._reopen()
        for l in lines:
            if l.startswith("Error"): raise RuntimeError("card error after %s: %s" % (msg[:40], l))
            if l.startswith("Data:"): return l[5:].strip()
        raise RuntimeError("no Data line after %s" % msg[:40])

    def read_block(self, addr, count):
        """count bytes from addr upward (data bus put in read mode by the card)"""
        if not self.blocks:
            self.cmd("DATABUS-RD-MODE", 1)
            return [self.readmem(addr + i) for i in range(count)]
        out = []
        while count:
            n = min(count, self.BLOCK)
            vals = [int(h, 16) for h in self._block_reply("RDBLK:%d,%d#" % (addr, n)).split()]
            if len(vals) != n: raise RuntimeError("RDBLK returned %d of %d bytes" % (len(vals), n))
            out += vals; addr += n; count -= n
        return out

    def write_block(self, addr, data):
        """write the bytes of data from addr upward (data bus put in write mode by the card)"""
        data = list(data)
        if not self.blocks:
            self.cmd("DATABUS-WR-MODE", 1)
            for i, v in enumerate(data): self.writemem(addr + i, v)
            return
        while data:
            chunk, data = data[:self.WBLOCK], data[self.WBLOCK:]
            n = int(self._block_reply("WRBLK:%d,%d,%s#" % (addr, len(chunk), "".join("%02X" % (v & 0xFF) for v in chunk))))
            if n != len(chunk): raise RuntimeError("WRBLK wrote %d of %d bytes" % (n, len(chunk)))
            addr += len(chunk)


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
    print("prompt received; banner lines:", banner, "| block commands:", "yes" if bd.blocks else "no (older firmware)")

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
