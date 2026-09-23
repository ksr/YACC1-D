#!/usr/bin/env python3
"""monload.py - send a program to the YACC1's RAM through the ROM monitor's ':' Intel-hex loader (2026-09-23),
then optionally run it and show its console output.

  monload.py PROG.img [--port /dev/cu.usbserial-X] [--baud 38400] [--delay MS] [--go ADDR] [--listen S] [--term]

PROG.img is the assembler's Intel-hex output (y1cc: compile without --boot/--vector; the program starts at $3000 and
its main returns to the monitor). Each record is sent as is; the monitor answers one character per record:
  .  stored and checksum right      ?  bad hex digit or checksum      !  address refused or read back wrong
and prints LOADED (or LOADED WITH ERRORS) after the end record. On the first ? or ! this tool sends ESC (the monitor
abandons the load) and exits 1.

Pacing: the monitor spends about 39 instructions (~1,600 clocks, measured on the microcode emulator) on each
received character and the UART's FIFO is off, so characters must not arrive faster than that: at a 1 MHz CPU clock
that is 1.6 ms, and --delay (default 3 ms between characters) leaves a factor of two. Scale it with the clock:
delay_ms >= 3.2 / clock_MHz. A 16-byte record is 43 characters, so about 0.15 s per record at the default.

--go ADDR   after LOADED, send G and the address (4 hex digits; the monitor calls it with JSRUR, RET returns)
--listen S  print what the machine sends for S seconds after the load/go (default 3; 0 = not at all)
--term      after that, a plain terminal: keys go to the machine (Ctrl-] quits)

The machine's console is the I/O card's UART (DB9 behind the MAX232, 38400 8N1 as the monitor sets it). The
sequencer card's FTDI (usbserial-AB6WZCQX) is NOT the console; with several ports present, pass --port.
tests/monload/run.py exercises this tool against the microcode emulator through a pseudo-terminal.
"""
import os, sys, time, glob, argparse, select

SEQUENCER_FTDI = "AB6WZCQX"


def find_port():
    ports = [p for p in sorted(glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*")) if SEQUENCER_FTDI not in p]
    if not ports: sys.exit("monload: no USB serial port for the console (the sequencer's FTDI is excluded): use --port")
    if len(ports) > 1: sys.exit("monload: several ports, pick the console with --port: " + " ".join(ports))
    return ports[0]


def records(path):
    recs = [l.strip() for l in open(path) if l.strip().startswith(":")]
    if not recs: sys.exit("monload: %s holds no Intel-hex records" % path)
    for r in recs:
        b = bytes.fromhex(r[1:])
        if len(b) != b[0] + 5 or sum(b) & 0xFF: sys.exit("monload: bad record in %s: %s" % (path, r))
    if recs[-1][7:9] != "01": recs.append(":00000001FF")      # always end with an end record
    return recs


class Link:
    def __init__(self, port, baud, drain=True):
        import serial
        self.s = serial.Serial(port, baud, timeout=0.05)
        self.seen = b""
        self.drain = drain          # tcdrain after each character; off only for a pty read by this same process
                                    # (tests/bench/run.py's self-test), where tcdrain blocks

    def write(self, data, delay):
        for ch in data:
            self.s.write(bytes([ch]))
            if self.drain: self.s.flush()
            if delay: time.sleep(delay / 1000.0)

    def wait_for(self, wanted, timeout):
        """Read until one of the byte strings in wanted appears in new input; returns it, or None on timeout."""
        deadline = time.time() + timeout; buf = b""
        while time.time() < deadline:
            c = self.s.read(64)
            if not c: continue
            buf += c; self.seen += c
            for w in wanted:
                if w in buf: return w
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=38400)
    ap.add_argument("--delay", type=float, default=3.0, help="ms between characters (default 3)")
    ap.add_argument("--timeout", type=float, default=5.0, help="seconds to wait for each acknowledgement")
    ap.add_argument("--go", help="run from this address after the load (hex, e.g. 3000)")
    ap.add_argument("--listen", type=float, default=3.0)
    ap.add_argument("--term", action="store_true")
    a = ap.parse_args()
    recs = records(a.image)
    data = sum(1 for r in recs if r[7:9] == "00")
    print("%s: %d records (%d data), about %.0f s at %g ms per character" % (a.image, len(recs), data,
          sum(len(r) for r in recs) * (a.delay / 1000.0 + 10.0 / a.baud), a.delay))
    link = Link(a.port or find_port(), a.baud)
    t0 = time.time()
    for n, r in enumerate(recs, 1):
        link.write(r.encode("ascii"), a.delay)
        if r[7:9] == "01":
            got = link.wait_for([b"LOADED WITH ERRORS", b"LOADED\r", b"LOADED\n"], a.timeout)
            if got is None: sys.exit("monload: no LOADED after the end record")
            if got == b"LOADED WITH ERRORS": sys.exit("monload: the monitor reports errors")
            break
        got = link.wait_for([b".", b"?", b"!"], a.timeout)
        if got is None:
            sys.exit("monload: no answer to record %d (is the monitor at its '>' prompt? right port and baud?)" % n)
        if got != b".":
            link.write(b"\x1b", 0)
            sys.exit("monload: record %d refused with '%s' (%s): %s" % (n, got.decode(), "bad record" if got == b"?"
                     else "address outside $1000-$DFFF or read back wrong", r))
        sys.stdout.write("\r  %d/%d" % (n, len(recs))); sys.stdout.flush()
    print("\r%d records loaded in %.1f s" % (len(recs), time.time() - t0))
    if a.go:
        link.wait_for([b">"], a.timeout)
        link.write(("G%04X" % int(a.go, 16)).encode(), a.delay)
    if a.listen:
        end = time.time() + a.listen
        while time.time() < end:
            c = link.s.read(256)
            if c: sys.stdout.write(c.decode("latin1")); sys.stdout.flush()
    if a.term: terminal(link.s)


def terminal(s):
    import tty, termios
    print("\n[terminal: Ctrl-] quits]")
    fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            r, _, _ = select.select([fd, s.fileno()], [], [], 0.1)
            if fd in r:
                k = os.read(fd, 1)
                if k == b"\x1d": break
                s.write(k)
            if s.fileno() in r:
                c = s.read(256)
                if c: os.write(sys.stdout.fileno(), c)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old); print()


if __name__ == "__main__":
    main()
