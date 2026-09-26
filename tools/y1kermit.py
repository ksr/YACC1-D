#!/usr/bin/env python3
"""y1kermit.py - a small standard Kermit for the Mac side of the YACC1's console line (2026-09-26): send files to
/BIN/KERMIT, receive them from it, talk to its server mode. The fallback when C-Kermit is not at hand, and what
tests/kermit/run.py drives the emulators with.

  y1kermit.py send FILE... [--as NAME]      to `kermit -r` (or a `kermit -x` server)
  y1kermit.py receive [DIR]                 from `kermit -s FILE...` (files land in DIR, default .)
  y1kermit.py get NAME... [DIR]             from a `kermit -x` server (GET; a Y1/OS glob works)
  y1kermit.py finish | bye                  end a `kermit -x` server (FINISH / BYE: both end it)
  y1kermit.py term                          a plain terminal on the port (Ctrl-] quits), as monload.py --term
options: --port /dev/cu.usbserial-X (default: the one USB serial port that is not the sequencer's FTDI)
         --baud 38400   --check 1|2|3 (block check to propose, default 3)   --maxl N (packets I take, default 94)
         --time S (the timeout I ask the other side to use, default 10)   --timeout S (mine, default 20)
         --text (send: text mode, LF goes as CR LF and the A packet says so)   --ebq (ask for 8th-bit prefixing)
         --norpt (no repeat counts)   --noattr (no A packets)   -q (quiet)
test options (fault injection, tests/kermit/run.py): --corrupt N (the Nth packet I send goes out once with a byte
         changed), --drop N (the Nth is not sent at first: the other side must time out), --nak N (the Nth I receive
         is answered with a NAK as if damaged), --mute N (the Nth I receive gets no answer: the other side must time
         out and send it again). N counts every packet of the run from 1.

The protocol (Frank da Cruz, "Kermit, A File Transfer Protocol", 1987; the Kermit Protocol Manual): short packets
(MARK LEN SEQ TYPE DATA CHECK EOL, LEN up to 94), window 1, block checks 1-3, control prefixing (#), repeat counts
(~), 8th-bit prefixing (&) only when asked, attribute packets (size, text/binary); no long packets, no sliding
windows: what /BIN/KERMIT does. Packets are read by their LEN, whatever terminator follows. The port is opened with
tools/monload.py's Link (pyserial), 8N1, no flow control. Exit status 0 when every file went, 1 otherwise.
"""
import os, sys, time, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SOH, CR = 1, 13


def tochar(n): return (n + 32) & 255
def unchar(c): return (c - 32) & 255
def ctl(c): return c ^ 64


def chk1(b):
    s = sum(b)
    return (s + ((s & 0xC0) >> 6)) & 63


def crc16(b):                                        # CRC-CCITT as Kermit computes it (reflected, 0 start)
    crc = 0
    for c in b:
        q = (crc ^ c) & 15; crc = (crc >> 4) ^ (q * 0o10201)
        q = (crc ^ (c >> 4)) & 15; crc = (crc >> 4) ^ (q * 0o10201)
    return crc


def blockcheck(b, t):
    if t == 1: return bytes([tochar(chk1(b))])
    if t == 2: s = sum(b) & 0xFFF; return bytes([tochar(s >> 6), tochar(s & 63)])
    c = crc16(b); return bytes([tochar(c >> 12), tochar((c >> 6) & 63), tochar(c & 63)])


class KermitError(Exception): pass


class Kermit:
    def __init__(self, port, a):
        self.a = a
        if port is None:
            from monload import find_port
            port = find_port()
        from monload import Link
        self.link = Link(port, a.baud, drain=False)
        self.s = self.link.s
        self.inbuf = b""
        self.npkt_out = 0; self.npkt_in = 0
        self.stats = {"retries": 0, "naks": 0, "timeouts": 0, "repeats": 0}
        self.lastin = None
        self.reset()

    def reset(self):
        self.bct = 1
        self.maxl = 80; self.eol = CR; self.qctl = ord("#"); self.rqctl = ord("#")
        self.ebq = None; self.rpt = None; self.attr = False; self.their_time = 5
        self.seq = 0

    def log(self, s):
        if not self.a.quiet: print(s, flush=True)

    # ---- the line ----
    def send_raw(self, b):
        self.s.write(b); self.s.flush()

    def spack(self, typ, seq, data=b"", bct=None):
        bct = bct or self.bct
        body = bytes([tochar(len(data) + 2 + bct), tochar(seq), ord(typ)]) + data
        pkt = bytes([SOH]) + body + blockcheck(body, bct) + bytes([self.eol])
        self.last = pkt
        self.npkt_out += 1
        n = self.npkt_out
        if n in self.a.drop:
            self.a.drop.remove(n); self.log("  [test] packet %d (%s) not sent" % (n, typ)); return
        if n in self.a.corrupt:
            self.a.corrupt.remove(n)
            i = 4 if len(pkt) > 7 else 2
            bad = bytearray(pkt); bad[i] = bad[i] ^ 1 if bad[i] ^ 1 >= 32 else bad[i] + 1
            self.log("  [test] packet %d (%s) sent damaged" % (n, typ)); self.send_raw(bytes(bad)); return
        self.send_raw(pkt)

    def resend(self):
        self.stats["retries"] += 1
        self.send_raw(self.last)

    def rpack(self, timeout=None):
        """-> (type, seq, data) or None on a timeout; a damaged packet comes back as ('Q', seq, b'')."""
        deadline = time.time() + (timeout or self.a.timeout)
        while True:
            i = self.inbuf.find(bytes([SOH]))
            if i >= 0:
                self.inbuf = self.inbuf[i:]
                if len(self.inbuf) >= 2:
                    n = unchar(self.inbuf[1])
                    if n < 3 or n > 94: self.inbuf = self.inbuf[1:]; continue
                    if SOH in self.inbuf[1:2 + n]:           # an SOH inside: the packet broke off, resync
                        self.inbuf = self.inbuf[1 + self.inbuf[1:].find(bytes([SOH])):]; continue
                    if len(self.inbuf) >= 2 + n:
                        body = self.inbuf[1:2 + n]; self.inbuf = self.inbuf[2 + n:]
                        return self.check(body)
            else: self.inbuf = b""
            left = deadline - time.time()
            if left <= 0: return None
            self.s.timeout = min(left, 0.2)
            c = self.s.read(max(1, self.s.in_waiting))       # what is there, or wait for one byte
            if c: self.inbuf += c

    def check(self, body):
        typ, seq = chr(body[2]), unchar(body[1])
        self.npkt_in += 1
        if self.npkt_in in self.a.mute:
            self.a.mute.remove(self.npkt_in); self.log("  [test] packet %d (%s) gets no answer" % (self.npkt_in, typ))
            self.lastin = (typ, seq)
            return "MUTE", seq, b""
        if self.npkt_in in self.a.nak:
            self.a.nak.remove(self.npkt_in); self.log("  [test] packet %d (%s) taken as damaged" % (self.npkt_in, typ))
            return "Q", seq, b""
        for bct in ([1] if typ in "SI" or self.bct == 1 else [self.bct, 1] if typ == "E" else [self.bct]):
            n = len(body) - bct
            if n >= 3 and blockcheck(body[:n], bct) == body[n:]:
                if (typ, seq) == self.lastin: self.stats["repeats"] += 1      # the other side sent it again
                self.lastin = (typ, seq)
                return typ, seq, body[3:n]
        return "Q", seq, b""

    # ---- data ----
    def encode(self, data, text=False):
        """-> list of data fields (bytes), each at most maxl - bct - 3 long"""
        room = self.maxl - self.bct - 3
        out, cur, i = [], bytearray(), 0
        if text: data = data.replace(b"\n", b"\r\n")
        while i < len(data):
            c = data[i]; n = 1
            if self.rpt:
                while i + n < len(data) and data[i + n] == c and n < 94: n += 1
            enc = bytearray()
            b8, c7 = c & 128, c & 127
            if self.ebq and b8: enc.append(self.ebq); c = c7
            if c7 < 32 or c7 == 127: enc += bytes([self.qctl, ctl(c)])
            elif c7 == self.qctl or c7 == self.ebq or c7 == self.rpt: enc += bytes([self.qctl, c])
            else: enc.append(c)
            if n > 2: enc = bytes([self.rpt, tochar(n)]) + enc
            elif n == 2: enc = enc + enc
            if len(cur) + len(enc) > room: out.append(bytes(cur)); cur = bytearray()
            cur += enc; i += n
        if cur: out.append(bytes(cur))
        return out

    def decode(self, d):
        try: return self.decode1(d)
        except IndexError: raise KermitError("a prefix at the end of a data field: %r" % d)

    def decode1(self, d):
        out, i = bytearray(), 0
        while i < len(d):
            c, n = d[i], 1; i += 1
            if self.rpt and c == self.rpt: n = unchar(d[i]); c = d[i + 1]; i += 2
            b8 = 0
            if self.ebq and c == self.ebq: b8 = 128; c = d[i] & 127; i += 1
            if c == self.rqctl:
                c = d[i]; i += 1
                if 63 <= (c & 127) <= 95: c = ctl(c)          # ? -> DEL, @.._ -> NUL..US; anything else is itself
            out += bytes([c | b8]) * n
        return bytes(out)

    # ---- parameters ----
    def myinit(self):
        qbin = ord("&") if self.a.ebq else ord("Y")
        capas = 0 if self.a.noattr else 8
        return bytes([tochar(self.a.maxl), tochar(self.a.time), tochar(0), ctl(0), tochar(CR), ord("#"), qbin,
                      ord(str(self.a.check)), ord("~") if not self.a.norpt else ord(" "), tochar(capas), tochar(1)])

    def takeinit(self, d, sender):
        """d = the other side's init; sender = I sent the S (d is the ACK). Sets the negotiated values."""
        f = lambda k: d[k] if len(d) > k else None
        self.maxl = min(unchar(f(0)) if f(0) else 80, 94) or 80
        if f(1): self.their_time = unchar(f(1)) or 5
        self.eol = unchar(f(4)) if f(4) else CR
        self.rqctl = f(5) if f(5) else ord("#")
        theirs, mine = f(6), (ord("&") if self.a.ebq else ord("Y"))
        ok = lambda c: c is not None and (33 <= c <= 62 or 96 <= c <= 126)
        self.ebq = theirs if ok(theirs) and mine in (ord("Y"), theirs) else mine if ok(mine) and theirs == ord("Y") else None
        t = f(7) - 48 if f(7) else 1
        if sender: self.bct = t if t == self.a.check and t in (1, 2, 3) else 1
        else: self.bct = t if t in (1, 2, 3) else 1
        r = f(8); myr = None if self.a.norpt else ord("~")
        self.rpt = r if ok(r) and r == myr else None
        capas = unchar(f(9)) if f(9) else 0
        self.attr = bool(capas & 8) and not self.a.noattr

    def ackinit(self):
        """my init as the answer to their S: echo their choices where we agree"""
        d = bytearray(self.myinit())
        d[6] = self.ebq if self.ebq else ord("N")
        d[7] = ord(str(self.bct))
        d[8] = self.rpt if self.rpt else ord(" ")
        return bytes(d)

    # ---- a sent packet and its ACK ----
    def exchange(self, typ, data=b"", seq=None, bct=None):
        """send a packet until it is ACKed; returns the ACK's data"""
        seq = self.seq if seq is None else seq
        self.spack(typ, seq, data, bct)
        tries = 0
        while True:
            r = self.rpack()
            if r is None:
                self.stats["timeouts"] += 1; tries += 1
                if tries > 10: raise KermitError("no answer to %s %d" % (typ, seq))
                self.resend(); continue
            t, s, d = r
            if t == "Y" and s == seq: return d
            if t == "E": raise KermitError("the other Kermit says: " + d.decode("latin1"))
            if t == "N" and s == (seq + 1) & 63: return b""        # NAK of the next one = ACK of this one
            if t == "MUTE": continue
            if t == "N": self.stats["naks"] += 1
            tries += 1
            if tries > 10: raise KermitError("too many retries on %s %d" % (typ, seq))
            self.resend()

    # ---- send ----
    def send_files(self, files, names):
        self.seq = 0
        ack = self.exchange("S", self.myinit(), bct=1)
        self.takeinit(ack, sender=True)
        self.log("  negotiated: packets <= %d, block check %d, repeat %s, 8th-bit %s, attributes %s" % (
            self.maxl, self.bct, chr(self.rpt) if self.rpt else "no", chr(self.ebq) if self.ebq else "no", self.attr))
        ok = True
        for path, name in zip(files, names):
            data = open(path, "rb").read()
            self.seq = (self.seq + 1) & 63
            ack = self.exchange("F", b"".join(self.encode(name.encode("latin1"))))
            stored = self.decode(ack).decode("latin1") if ack else name
            skip = False
            if self.attr:
                self.seq = (self.seq + 1) & 63
                a = (b'"' + (bytes([tochar(3)]) + b"AMJ" if self.a.text else bytes([tochar(2)]) + b"B8") +
                     b"1" + bytes([tochar(len(str(len(data))))]) + str(len(data)).encode())
                r = self.exchange("A", a)
                skip = r[:1] == b"N"
            t0 = time.time()
            if not skip:
                for field in self.encode(data, self.a.text):
                    self.seq = (self.seq + 1) & 63
                    r = self.exchange("D", field)
                    if r[:1] in (b"X", b"Z"): skip = True; break
            self.seq = (self.seq + 1) & 63
            self.exchange("Z", b"D" if skip else b"")
            if skip: ok = False
            self.log("sent %s as %s, %d bytes in %.1f s%s" % (path, stored, len(data), time.time() - t0, " (refused)" if skip else ""))
        self.seq = (self.seq + 1) & 63
        self.exchange("B")
        return ok

    # ---- receive ----
    def receive(self, outdir, first=None):
        """answer an S and take files until B; first = an S already read"""
        got = []
        r = first or self.rpack()
        tries = 0
        while r is None or r[0] != "S":
            if r is None:
                tries += 1
                if tries > 12: raise KermitError("no S packet")
                self.stats["timeouts"] += 1
                self.spack("N", 0, bct=1)
            elif r[0] == "E": raise KermitError("the other Kermit says: " + r[2].decode("latin1"))
            r = self.rpack()
        self.takeinit(r[2], sender=False)
        self.seq = 0
        self.spack("Y", 0, self.ackinit(), bct=1)
        expect, out, name, size, text = 1, None, None, None, False
        tries = 0
        while True:
            r = self.rpack()
            if r is None or r[0] in ("Q", "MUTE"):
                if r is None: self.stats["timeouts"] += 1
                if r is not None and r[0] == "MUTE": continue
                tries += 1
                if tries > 10: raise KermitError("too many retries")
                self.spack("N", expect); continue
            t, s, d = r
            if t == "E": raise KermitError("the other Kermit says: " + d.decode("latin1"))
            if s == (expect - 1) & 63:                  # my ACK was lost: send it again
                self.stats["retries"] += 1; self.send_raw(self.last); continue
            if s != expect: self.spack("N", expect); continue
            tries = 0
            if t == "S": self.takeinit(d, sender=False); self.spack("Y", s, self.ackinit(), bct=1)
            elif t == "F":
                name = self.decode(d).decode("latin1"); out = bytearray(); size = None; text = False
                self.spack("Y", s, b"".join(self.encode(os.path.basename(name).encode())) if len(name) < 60 else b"")
            elif t == "A":
                self.parse_attr(d); size = self.asize; text = self.atext
                self.spack("Y", s, b"Y")
            elif t == "D": out += self.decode(d); self.spack("Y", s)
            elif t == "Z":
                if d[:1] != b"D":
                    data = bytes(out).replace(b"\r\n", b"\n") if text else bytes(out)
                    path = os.path.join(outdir, os.path.basename(name))
                    open(path, "wb").write(data); got.append(path)
                    self.log("received %s -> %s, %d bytes%s" % (name, path, len(data),
                             "" if size is None or size == len(data) else " (the A packet said %d)" % size))
                self.spack("Y", s)
            elif t == "B": self.spack("Y", s); return got
            else: self.spack("E", s, b"unexpected packet"); raise KermitError("unexpected packet " + t)
            expect = (expect + 1) & 63

    def parse_attr(self, d):
        self.asize, self.atext, i = None, False, 0
        while i + 1 < len(d):
            tag, n = chr(d[i]), unchar(d[i + 1]); v = d[i + 2:i + 2 + n]; i += 2 + n
            if tag == "1" and v.isdigit(): self.asize = int(v)
            if tag == '"' and v[:1] == b"A": self.atext = True

    # ---- server client ----
    def get(self, names, outdir):
        got = []
        for nm in names:
            self.reset(); self.seq = 0
            self.spack("R", 0, b"".join(self.encode(nm.encode())), bct=1)
            tries = 0
            while True:
                r = self.rpack()
                if r is None or r[0] in ("Q", "N"):
                    tries += 1
                    if tries > 10: raise KermitError("no answer to GET")
                    self.resend(); continue
                if r[0] == "E": raise KermitError("the server says: " + r[2].decode("latin1"))
                if r[0] == "S": break
            got += self.receive(outdir, first=r)
        return got

    def generic(self, cmd):
        self.reset()
        self.exchange("G", cmd.encode(), seq=0, bct=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["send", "receive", "get", "finish", "bye", "term"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--port"); ap.add_argument("--baud", type=int, default=38400)
    ap.add_argument("--as", dest="asname", action="append", default=[])
    ap.add_argument("--check", type=int, default=3, choices=[1, 2, 3])
    ap.add_argument("--maxl", type=int, default=94); ap.add_argument("--time", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--text", action="store_true"); ap.add_argument("--ebq", action="store_true")
    ap.add_argument("--norpt", action="store_true"); ap.add_argument("--noattr", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true")
    for o in ("corrupt", "drop", "nak", "mute"): ap.add_argument("--" + o, type=int, action="append", default=[])
    a = ap.parse_args()
    if a.cmd == "term":
        from monload import Link, terminal
        terminal(Link(a.port or __import__("monload").find_port(), a.baud).s); return
    k = Kermit(a.port, a)
    k.s.reset_input_buffer()
    t0 = time.time(); ok = True
    try:
        if a.cmd == "send":
            if not a.args: sys.exit("y1kermit: send what?")
            names = [a.asname[i] if i < len(a.asname) else os.path.basename(f).upper() for i, f in enumerate(a.args)]
            ok = k.send_files(a.args, names)
        elif a.cmd == "receive":
            d = a.args[0] if a.args else "."
            os.makedirs(d, exist_ok=True); k.receive(d)
        elif a.cmd == "get":
            d = "."
            if len(a.args) > 1 and os.path.isdir(a.args[-1]): d = a.args.pop()
            k.get(a.args, d)
        else: k.generic("F" if a.cmd == "finish" else "L")
    except KermitError as e:
        print("y1kermit: %s" % e, file=sys.stderr); ok = False
    k.log("y1kermit: %s in %.1f s; %d packets out, %d in; retries %d, NAKs %d, timeouts %d, repeats %d" % (
        "done" if ok else "FAILED", time.time() - t0, k.npkt_out, k.npkt_in, k.stats["retries"], k.stats["naks"],
        k.stats["timeouts"], k.stats["repeats"]))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
