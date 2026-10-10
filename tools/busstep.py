#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""busstep.py - drive the bus tester's bus-stepper sketch (2026-10-10): the tester clocks the sequencer one edge at a
time through JP4 pin 2 (SS-SEL 2-3, SS/WAIT on SS) and reads the whole bus after each edge.

  busstep.py [--port P] CMD [CMD ...]      run the commands, print each bus line decoded
     p | t | nN | qN | l0 | l1 | fAAAA,BB[,M]    as the sketch takes them (embedded/bus-tester/bus-stepper)
  busstep.py --raw ...                      print the sketch's raw lines too

A decoded line: edge count, clock level, address, data (hi lo), the select fields (ADDR/RD/LD register IDs, IOADDR,
ALU) and every asserted strobe (active-low names at 0, active-high ones at 1), from the same pin table the tester
firmware uses (embedded/libraries/YACC/YACC_Common_header.h).
"""
import os, re, sys, time, argparse
import serial

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER = os.path.join(ROOT, "embedded/libraries/YACC/YACC_Common_header.h")
PORT = "/dev/cu.usbserial-AB6WZCQX"
LOCAL = {"OUT-LED", "IN-SWITCH", "LEDS-LD", "SWITCHES-RD"}          # tester-card signals, not bus lines
FIELDS = ("ADDR-REG-ID", "REG-RD-ID", "REG-LD-ID", "IOADDR", "ALU")


def pin_table():
    t = []
    for m in re.finditer(r'^\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),', open(HEADER).read(), re.M):
        name, chip, port, pin = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if 2 <= chip <= 5 and name not in LOCAL and not re.match(r"BIT\d$", name):
            t.append((name, chip, port * 8 + pin))
    return t


TABLE = pin_table()


def decode(line):
    m = re.match(r"(notfound )?E=(\d+) K=(\d) A=([0-9A-F]{4}) D=([0-9A-F]{4}) 2=([0-9A-F]{4}) 3=([0-9A-F]{4}) "
                 r"4=([0-9A-F]{4}) 5=([0-9A-F]{4})", line)
    if not m: return line
    regs = {c: int(m.group(4 + c), 16) for c in range(6)}
    bit = lambda chip, b: (regs[chip] >> b) & 1
    fields = {f: 0 for f in FIELDS}; on = []
    for name, chip, b in TABLE:
        v = bit(chip, b)
        f = next((f for f in FIELDS if re.fullmatch(re.escape(f) + r"\d", name)), None)
        if f: fields[f] |= v << int(name[-1])
        elif (name.startswith("-") and v == 0 and name != "-INT") or (not name.startswith("-") and v == 1):
            on.append(name)
    d = regs[1]
    return "%sE=%-6s K=%s A=%04X D=%02X %02X  ADR=%-2d RD=%-2d LD=%-2d IO=%-2d ALU=%-2d  %s" % (
        "NOTFOUND " if m.group(1) else "", m.group(2), m.group(3), regs[0], d >> 8, d & 0xFF, fields["ADDR-REG-ID"],
        fields["REG-RD-ID"], fields["REG-LD-ID"], fields["IOADDR"], fields["ALU"], " ".join(on))


class Stepper:
    def __init__(self, port):
        self.s = serial.Serial(port, 115200, timeout=0.2)
        self.read_until_prompt(10)

    def read_until_prompt(self, timeout):
        end = time.time() + timeout; buf = b""; lines = []
        while time.time() < end:
            b = self.s.read(4096)
            if b:
                buf += b
                while b"\n" in buf:
                    l, buf = buf.split(b"\n", 1); l = l.decode("latin1").strip()
                    if l == ">>": return lines
                    if l: lines.append(l)
        raise TimeoutError("busstep: no '>>' from the bus-stepper sketch (is it flashed? right port?)")

    def cmd(self, c, timeout=120):
        self.s.write(c.encode() + b"\n"); self.s.flush()
        return self.read_until_prompt(timeout)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", default=PORT)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("cmds", nargs="*")
    a = ap.parse_args()
    st = Stepper(a.port)
    for c in a.cmds or ["p"]:
        for l in st.cmd(c, timeout=600):
            if a.raw: print("  " + l)
            print(decode(l))


if __name__ == "__main__":
    main()
