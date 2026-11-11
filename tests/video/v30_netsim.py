#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/v30_netsim.py - the video card V3's netlist run as a circuit (2026-11-11).

  v30_netsim.py [-v]      -v prints every run's measurements

hardware/cards/video/kicad/v3.0/v30_netlist.py is simulated gate for gate, with delays in nanoseconds: every 74xx
part, the RAMs and the EPROMs are models written here from the parts' pinouts and function tables (not from the
netlist), wired by the netlist's nets. The HD63484 is a model of its memory side from the manual's figures T-6, T-8,
T-9 and 2.1: it answers the 2CLK the card gives it with MCYC, AS, the address and data on MAD, MRD, DRAW, CHR, the
raster line, HSYNC and DISP1, each after its delay from the timing table, and runs a script of memory cycles.

What is checked, with the chip's delays at their maximum and near their minimum, and from both phases the dot counter
can start in:
  interleaved access (text method A's sockets empty): the counter falls into step with MCYC; a drawing write puts
    the word into both RAMs and nowhere else; a drawing read gives the chip the word 40 ns before its cycle ends; the
    font EPROM's byte reads on both halves; every display cycle's word leaves the shift registers bit 0 first for
    16 dots, 8 dots later after the delay line, and on the three guns; a dummy cycle and a drawing cycle load
    nothing; the control register takes the attribute byte of the last cycle before HSYNC rises and never moves
    while HSYNC is low; the guns follow its off bits, the syncs its polarity bits
  superimposed access (the sockets fitted): the character word of a Window cycle comes out as its two glyphs, the
    left code first, bit 0 first, exactly under the graphics word of the same display cycle, and only while the text
    layer is on (ATR bit 5); a word written to the character screen lands in the RAM's top 64K words whatever the
    raster line says; the layers OR and XOR
  the ports: OUT PA / PB and IN PC / PD select the chip with the bus buffer the right way round; nothing else does
  everywhere: no two outputs fighting on a net, every flip-flop's and register's set-up and hold met, the RAM's
    write pulse wide enough with its data set up

The delays are the parts' data-sheet maximums as far as they are known here (the table DELAY): the netlist's logic
is proved, and the margins printed are a first figure for the timing check against the parts actually bought.
"""
import os, sys, heapq, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("v30_netlist", os.path.join(ROOT, "hardware/cards/video/kicad/v3.0/v30_netlist.py"))
N = importlib.util.module_from_spec(spec); spec.loader.exec_module(N)
VERBOSE = "-v" in sys.argv
DOT = 1000.0 / 25.175                                  # ns

# propagation delays, ns (maximums at 5 V; F parts' are their typical 25 C figures plus a margin)
DELAY = {"gate": 8.0, "74": 7.0, "163": 8.0, "573": 9.5, "574": 10.0, "377": 10.0, "299": 9.0, "164": 10.5,
         "245": 8.5, "245en": 10.0, "245dis": 9.0, "244": 15.0, "244en": 20.0, "138": 25.0, "ram_aa": 55.0, "ram_oe": 30.0,
         "ram_oh": 10.0, "ram_hz": 15.0, "rom_acc": 70.0, "rom_oh": 5.0, "rom_hz": 25.0}
SETUP = {"74": 3.0, "163": 8.0, "377": 4.5, "574": 4.5, "299": 7.5, "164": 5.0}       # data (and mode) before the clock
HOLD = {"74": 1.0, "163": 1.0, "377": 1.0, "574": 1.5, "299": 1.0, "164": 1.0}
RAM_TWP, RAM_TDW = 45.0, 25.0                          # AS6C1008-55: write pulse, data set-up to its end
OVERLAP = 3.0                                          # two three-state outputs may both be on this long at a handover
FLOAT = 300.0                                          # a 10k pull-up needs about this long to move an undriven bus line


def kind(value):
    """a part's type from its value: 74ACT04 -> 04, HD63484P8 -> chip, ..."""
    if value.startswith("HD63484"): return "chip"
    if value.startswith("AS6C"): return "ram"
    if "27C256" in value: return "rom"
    if value == "7416": return "16"
    if value.startswith("74"):
        d = value[2:].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return d
    return None


def AND(*a): return 0 if 0 in a else (None if None in a else 1)
def OR(*a): return 1 if 1 in a else (None if None in a else 0)
def NOT(a): return None if a is None else 1 - a
def XOR(a, b): return None if a is None or b is None else a ^ b


class Sim:
    def __init__(self, fitted_out=()):
        self.t = 0.0; self.q = []; self.seq = 0; self.pending = {}; self.floating = {}
        self.netof = {}; self.onnet = {}
        for net, pins in N.NETS.items():
            for ref, pin in pins:
                if ref in fitted_out: continue
                self.netof[(ref, pin)] = net; self.onnet.setdefault(net, []).append((ref, pin))
        self.val = {net: None for net in N.NETS}; self.val["VCC"] = 1; self.val["GND"] = 0
        self.last = {net: -1e9 for net in N.NETS}
        self.drv = {net: {} for net in N.NETS}
        self.pull = {}
        for ref, (value, sym, fp, note) in N.PARTS.items():      # a resistor or a network from a net to VCC or GND
            if ref in fitted_out: continue
            nets = [self.netof.get((ref, p)) for p in N.PINS[ref]]
            if ref.startswith("RN") and nets[0] == "VCC":
                for n in nets[1:]: self.pull[n] = 1
            elif ref.startswith("R") and not ref.startswith("RN") and len(nets) == 2:
                for a, b in ((nets[0], nets[1]), (nets[1], nets[0])):
                    if a in ("VCC", "GND") and b not in ("VCC", "GND"): self.pull.setdefault(b, 1 if a == "VCC" else 0)
        for net, v in self.pull.items(): self.val[net] = v
        self.parts = {}; self.faults = []; self.fights = {}; self.fstart = {}; self.holds = []; self.margin = {}
        for ref, (value, sym, fp, note) in N.PARTS.items():
            if ref in fitted_out: continue
            k = kind(value)
            if k in MODELS: self.parts[ref] = MODELS[k](self, ref, k)
        self.byname = {}
        for ref, m in self.parts.items():
            for pin in N.PINS[ref]:
                net = self.netof.get((ref, pin))
                if net: self.byname.setdefault(net, []).append(m)

    # ---- nets
    def v(self, ref, pin): return self.val.get(self.netof.get((ref, str(pin))))
    def net(self, ref, pin): return self.netof.get((ref, str(pin)))

    def drive(self, ref, pin, value, delay):
        """an output pin takes a value after a delay; what was still to come on that pin at or after that time is dropped"""
        net = self.netof.get((ref, str(pin)))
        if net is None: return
        self.post(net, (ref, str(pin)), value, delay)

    def force(self, net, value, delay=0.0): self.post(net, ("TB", net), value, delay)

    def post(self, net, who, value, delay):
        t = self.t + delay
        mine = self.pending.setdefault(who, [])
        for ev in mine:
            if ev[0] >= t - 1e-9: ev[2] = False
        mine[:] = [ev for ev in mine if ev[2] and ev[0] > self.t - 1e-9]
        self.seq += 1
        ev = [t, value, True]
        mine.append(ev)
        heapq.heappush(self.q, (t, self.seq, net, who, ev))

    def resolve(self, net):
        """the net's value; and the bookkeeping of two outputs being on at once (how long, the longest time)"""
        on = sorted(k[0] for k, x in self.drv[net].items() if x is not None)
        if len(on) > 1 and net not in self.fstart: self.fstart[net] = (self.t, tuple(on))
        elif len(on) <= 1 and net in self.fstart:
            t0, who = self.fstart.pop(net)
            if self.t - t0 > self.fights.get((net, who), (0, 0))[0]: self.fights[(net, who)] = (self.t - t0, t0)
        vals = [x for x in self.drv[net].values() if x is not None]
        if not vals:                                   # nothing drives: the net keeps its level; a pull resistor takes
            if net in self.pull and self.val[net] != self.pull[net] and not self.floating.get(net):     # FLOAT ns to move it
                self.floating[net] = True; self.post(net, ("PULL", net), None, FLOAT)
            return self.val[net] if self.val[net] is not None else self.pull.get(net)
        return vals[0] if len(set(vals)) == 1 else None

    def run(self, until):
        while self.q and self.q[0][0] <= until:
            t, _, net, who, ev = heapq.heappop(self.q)
            if not ev[2]: continue
            self.t = t; value = ev[1]
            if who[0] == "PULL":
                self.floating[net] = False
                new = self.pull[net] if not [x for x in self.drv[net].values() if x is not None] else self.val[net]
            else:
                if self.drv[net].get(who, "none") == value: continue
                self.drv[net][who] = value
                new = self.resolve(net)
            if new != self.val[net]:
                self.val[net] = new; self.last[net] = t
                for h in self.holds:
                    if h[0] == net and t - h[1] < h[2] - 1e-9: self.faults.append("%.1f ns: %s hold on %s: it moved %.1f ns after the clock (%.1f wanted)" % (t, h[3], net, t - h[1], h[2]))
                self.holds = [h for h in self.holds if t - h[1] < 30]
                for m in self.byname.get(net, ()): m.eval()
        self.t = until

    # ---- timing checks
    def setup(self, ref, pin, tsu, th, what):
        net = self.netof.get((ref, str(pin)))
        if net in (None, "VCC", "GND") or net in self.pull and not self.drv[net]: return
        slack = self.t - self.last[net] - tsu
        key = what
        if key not in self.margin or slack < self.margin[key][0]: self.margin[key] = (slack, "%s.%s (%s) at %.1f ns" % (ref, pin, net, self.t))
        if slack < -1e-9: self.faults.append("%.1f ns: %s set-up on %s.%s (%s): steady only %.1f ns (%.1f wanted)" % (self.t, what, ref, pin, net, self.t - self.last[net], tsu))
        self.holds.append((net, self.t, th, "%s.%s" % (ref, pin)))

    def note(self, key, slack, where):
        if key not in self.margin or slack < self.margin[key][0]: self.margin[key] = (slack, where)


class Part:
    def __init__(self, sim, ref, k): self.s = sim; self.ref = ref; self.k = k; self.init()
    def init(self): pass
    def v(self, pin): return self.s.v(self.ref, pin)
    def out(self, pin, value, delay): self.s.drive(self.ref, pin, value, delay)
    def rose(self, pin, name="ck"):
        now = self.v(pin); was = getattr(self, name, None); setattr(self, name, now)
        return was == 0 and now == 1


class Gate(Part):
    TABLE = {"00": (lambda a, b: NOT(AND(a, b)), ((1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11))),
             "08": (lambda a, b: AND(a, b), ((1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11))),
             "32": (lambda a, b: OR(a, b), ((1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11))),
             "86": (lambda a, b: XOR(a, b), ((1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11))),
             "02": (lambda a, b: NOT(OR(a, b)), ((2, 3, 1), (5, 6, 4), (8, 9, 10), (11, 12, 13))),
             "04": (lambda a: NOT(a), ((1, 2), (3, 4), (5, 6), (9, 8), (11, 10), (13, 12))),
             "16": (lambda a: (0 if a == 1 else None), ((1, 2), (3, 4), (5, 6), (9, 8), (11, 10), (13, 12))),   # open collector
             "10": (lambda a, b, c: NOT(AND(a, b, c)), ((1, 2, 13, 12), (3, 4, 5, 6), (9, 10, 11, 8))),
             "11": (lambda a, b, c: AND(a, b, c), ((1, 2, 13, 12), (3, 4, 5, 6), (9, 10, 11, 8))),
             "21": (lambda a, b, c, d: AND(a, b, c, d), ((1, 2, 4, 5, 6), (9, 10, 12, 13, 8)))}

    def eval(self):
        f, gates = self.TABLE[self.k]
        for g in gates:
            self.out(g[-1], f(*[self.v(p) for p in g[:-1]]), DELAY["gate"])


class FF74(Part):
    def init(self): self.q = {0: 0, 1: 0}
    def eval(self):
        for i, (clr, d, ck, pre, q, qn) in enumerate(((1, 2, 3, 4, 5, 6), (13, 12, 11, 10, 9, 8))):
            edge = self.rose(ck, "ck%d" % i); old = self.q[i]
            if self.v(pre) == 0: self.q[i] = 1
            elif self.v(clr) == 0: self.q[i] = 0
            elif edge:
                self.s.setup(self.ref, d, SETUP["74"], HOLD["74"], "74F74 D")
                self.q[i] = self.v(d)
            if self.q[i] != old or not hasattr(self, "up%d" % i):
                setattr(self, "up%d" % i, 1)
                self.out(q, self.q[i], DELAY["74"]); self.out(qn, NOT(self.q[i]), DELAY["74"])


class Counter163(Part):
    def init(self): self.n = getattr(self.s, "count0", 0); self.first = True
    def eval(self):
        if self.rose(2):
            if self.v(1) == 0: self.n = 0
            elif self.v(9) == 0:
                for p in (3, 4, 5, 6): self.s.setup(self.ref, p, SETUP["163"], HOLD["163"], "74F163 load data")
                bits = [self.v(p) for p in (3, 4, 5, 6)]
                self.n = sum((b or 0) << i for i, b in enumerate(bits))
            elif self.v(7) == 1 and self.v(10) == 1: self.n = (self.n + 1) & 15
            self.s.setup(self.ref, 9, SETUP["163"], HOLD["163"], "74F163 -LOAD")
            self.first = True
        if self.first:
            self.first = False
            for i, p in enumerate((14, 13, 12, 11)): self.out(p, self.n >> i & 1, DELAY["163"])


class Reg377(Part):
    PAIRS = ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))
    def init(self): self.q = [0] * 8; self.up = False
    def eval(self):
        if self.rose(11):
            self.s.setup(self.ref, 1, SETUP["377"], HOLD["377"], "74ACT377 -E")
            if self.v(1) == 0:
                for d, q in self.PAIRS: self.s.setup(self.ref, d, SETUP["377"], HOLD["377"], "74ACT377 D")
                self.q = [self.v(d) for d, q in self.PAIRS]; self.up = False
        if not self.up:
            self.up = True
            for (d, q), x in zip(self.PAIRS, self.q): self.out(q, x, DELAY["377"])


class Reg574(Part):
    def init(self): self.q = [0] * 8; self.oe = None
    def eval(self):
        new = self.rose(11)
        if new:
            for d in range(2, 10): self.s.setup(self.ref, d, SETUP["574"], HOLD["574"], "74ACT574 D")
            self.q = [self.v(d) for d in range(2, 10)]
        oe = self.v(1)
        if new or oe != self.oe:
            delay = DELAY["574"] if oe == self.oe else DELAY["574"] - (0 if oe == 0 else 1.5)     # off a little sooner than on
            self.oe = oe
            for i, x in enumerate(self.q): self.out(19 - i, x if oe == 0 else None, delay)


class Latch573(Part):
    def init(self): self.q = [None] * 8
    def eval(self):
        if self.v(11) == 1: self.q = [self.v(d) for d in range(2, 10)]
        for i, x in enumerate(self.q): self.out(19 - i, x if self.v(1) == 0 else None, DELAY["573"])


class Shift299(Part):
    IO = {0: 7, 1: 13, 2: 6, 3: 14, 4: 5, 5: 15, 6: 4, 7: 16}
    def init(self): self.q = [0] * 8; self.up = False; self.loads = []
    def eval(self):
        if self.v(9) == 0: self.q = [0] * 8; self.up = False
        elif self.rose(12):
            s0, s1 = self.v(1), self.v(19)
            self.s.setup(self.ref, 19, SETUP["299"], HOLD["299"], "74F299 S1")
            if s0 == 1 and s1 == 1:
                for i in range(8): self.s.setup(self.ref, self.IO[i], SETUP["299"], HOLD["299"], "74F299 data")
                self.q = [self.v(self.IO[i]) for i in range(8)]; self.loads.append(self.s.t)
            elif s0 == 1 and s1 == 0: self.q = [self.v(11)] + self.q[:7]
            elif s0 == 0 and s1 == 1: self.q = self.q[1:] + [self.v(18)]
            self.up = False
        if not self.up:
            self.up = True
            self.out(8, self.q[0], DELAY["299"]); self.out(17, self.q[7], DELAY["299"])


class Shift164(Part):
    def init(self): self.q = [0] * 8; self.up = False
    def eval(self):
        if self.v(9) == 0: self.q = [0] * 8; self.up = False
        elif self.rose(8):
            for p in (1, 2): self.s.setup(self.ref, p, SETUP["164"], HOLD["164"], "74ACT164 A, B")
            self.q = [AND(self.v(1), self.v(2))] + self.q[:7]; self.up = False
        if not self.up:
            self.up = True
            for p, x in zip((3, 4, 5, 6, 10, 11, 12, 13), self.q): self.out(p, x, DELAY["164"])


class Buf245(Part):
    def init(self): self.on = None
    def eval(self):
        on, d = self.v(19) == 0, self.v(1)
        delay = DELAY["245"] if on == self.on else (DELAY["245en"] if on else DELAY["245dis"])
        self.on = on
        for i in range(8):
            a, b = 2 + i, 18 - i
            self.out(b, self.v(a) if on and d == 1 else None, delay); self.out(a, self.v(b) if on and d == 0 else None, delay)


class Buf244(Part):
    def eval(self):
        for oe, pairs in ((1, ((2, 18), (4, 16), (6, 14), (8, 12))), (19, ((11, 9), (13, 7), (15, 5), (17, 3)))):
            for a, y in pairs: self.out(y, self.v(a) if self.v(oe) == 0 else None, DELAY["244"])


class Dec138(Part):
    def eval(self):
        en = self.v(6) == 1 and self.v(4) == 0 and self.v(5) == 0
        n = sum((self.v(p) or 0) << i for i, p in enumerate((1, 2, 3)))
        for i, p in enumerate((15, 14, 13, 12, 11, 10, 9, 7)): self.out(p, 0 if en and i == n else 1, DELAY["138"])


class Ram(Part):
    A = {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7, 6: 6, 7: 5, 8: 27, 9: 26, 10: 23, 11: 25, 12: 4, 13: 28, 14: 3, 15: 31, 16: 2}
    D = (13, 14, 15, 17, 18, 19, 20, 21)
    def init(self): self.mem = {}; self.we = 1; self.wrote = []; self.outv = "?"
    def addr(self):
        bits = [self.v(self.A[i]) for i in range(17)]
        return None if None in bits else sum(b << i for i, b in enumerate(bits))
    def default(self, a): return (a * 7 + (3 if self.ref == "IC10" else 0x51)) & 255
    def eval(self):
        sel = self.v(22) == 0 and self.v(30) == 1
        we = self.v(29)
        if self.we != 0 and we == 0: self.tfall = self.s.t
        if self.we == 0 and we == 1 and sel:                       # the end of a write
            a = self.addr(); data = [self.v(p) for p in self.D]
            width = self.s.t - self.tfall
            self.s.note("RAM write pulse", width - RAM_TWP, "%s at %.1f ns: %.1f ns wide" % (self.ref, self.s.t, width))
            if width < RAM_TWP: self.s.faults.append("%.1f ns: %s write pulse %.1f ns (%.1f wanted)" % (self.s.t, self.ref, width, RAM_TWP))
            for p in self.D:
                net = self.s.net(self.ref, p); st = self.s.t - self.s.last[net]
                self.s.note("RAM data set-up", st - RAM_TDW, "%s.%d at %.1f ns: steady %.1f ns" % (self.ref, p, self.s.t, st))
                if st < RAM_TDW: self.s.faults.append("%.1f ns: %s data set-up on pin %d: %.1f ns (%.1f wanted)" % (self.s.t, self.ref, p, st, RAM_TDW))
            for i in range(17):
                net = self.s.net(self.ref, self.A[i])
                if self.s.last[net] > self.tfall: self.s.faults.append("%.1f ns: %s address A%d moved during the write pulse" % (self.s.t, self.ref, i))
            if a is None or None in data: self.s.faults.append("%.1f ns: %s written with an unknown address or data" % (self.s.t, self.ref))
            else:
                self.mem[a] = sum(b << i for i, b in enumerate(data)); self.wrote.append((self.s.t, a, self.mem[a]))
        self.we = we
        on = sel and self.v(24) == 0 and we == 1
        a = self.addr()
        key = (on, a)
        if key == self.outv: return
        was_on = self.outv != "?" and self.outv[0]
        self.outv = key
        if not on:
            for p in self.D: self.out(p, None, DELAY["ram_hz"])
            return
        value = None if a is None else self.mem.get(a, self.default(a))
        if was_on:
            for p in self.D: self.out(p, None, DELAY["ram_oh"])         # the old word goes after its hold time
        for i, p in enumerate(self.D): self.out(p, None if value is None else value >> i & 1, DELAY["ram_aa"])


class Rom(Part):
    A = {0: 10, 1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 25, 9: 24, 10: 21, 11: 23, 12: 2, 13: 26, 14: 27}
    D = (11, 12, 13, 15, 16, 17, 18, 19)
    def init(self): self.outv = "?"
    def byte(self, a): return (a * 5 + 0x33) & 255 if self.ref == "IC14" else glyph(a >> 4 & 255, a & 15)
    def eval(self):
        on = self.v(20) == 0 and self.v(22) == 0
        bits = [self.v(self.A[i]) for i in range(15)]
        a = None if None in bits else sum(b << i for i, b in enumerate(bits))
        if (on, a) == self.outv: return
        was_on = self.outv != "?" and self.outv[0]
        self.outv = (on, a)
        if not on:
            for p in self.D: self.out(p, None, DELAY["rom_hz"])
            return
        if was_on:
            for p in self.D: self.out(p, None, DELAY["rom_oh"])
        value = None if a is None else self.byte(a)
        for i, p in enumerate(self.D): self.out(p, None if value is None else value >> i & 1, DELAY["rom_acc"])


def glyph(code, line): return (code * 3 + line * 17 + 1) & 255       # the test character generator's byte


class Chip(Part):
    """the HD63484's memory side (manual figures T-6, T-8, T-9, 2.1): a script of memory cycles, timed from 2CLK's
    falling edge with the delays of self.s.d (ns). A cycle is a dict: kind 'disp' | 'win' | 'read' | 'write' | 'dummy' |
    'atr', addr (20 bits; for a character screen 16 bits and ra = the raster line), data, chr, hs, disp."""
    MAD = {0: 61, 1: 60, 2: 59, 3: 58, 4: 57, 5: 48, 6: 47, 7: 46, 8: 45, 9: 44, 10: 43, 11: 42, 12: 41, 13: 40, 14: 39, 15: 38}
    def init(self):
        self.ck = None; self.mcyc = 1; self.cyc = None; self.script = []; self.log = []; self.reads = []
        self.out(52, 1, 0); self.out(53, 1, 0); self.out(55, 1, 0); self.out(54, 1, 0); self.out(56, 0, 0)
        self.out(12, 1, 0); self.out(13, 1, 0); self.out(63, 1, 0)
        for p in (34, 35, 36, 37, 33): self.out(p, 0, 0)

    def mad(self, value, delay):
        for i in range(16): self.out(self.MAD[i], None if value is None else value >> i & 1, delay)

    def eval(self):
        now = self.v(50); was = self.ck; self.ck = now
        d = self.s.d
        if was == 0 and now == 1:                                   # 2CLK rises: AS ends in the address half
            if self.mcyc == 0 and self.cyc and self.cyc["kind"] not in ("dummy", "atr", "idle"): self.out(53, 1, d["asr"])
            return
        if not (was == 1 and now == 0): return
        t = self.s.t
        if self.mcyc == 0:                                          # the data half begins
            self.mcyc = 1; self.out(52, 1, d["mcyc"])
            c = self.cyc
            if c is None: return
            if c["kind"] == "write":
                self.mad(None, d["maz"]); self.mad(c["data"], d["mwd"])
            elif c["kind"] == "atr":
                self.mad(None, d["maz"]); self.mad(c["data"], d["atr"])
                for i, p in enumerate((37, 36, 35, 34)): self.out(p, c["data"] >> (8 + i) & 1, d["atr"])
            else: self.mad(None, d["maz"])
            return
        # a cycle ends and the next begins
        c = self.cyc
        if c is not None:
            if c["kind"] == "read":
                bits = [self.v(self.MAD[i]) for i in range(16)]
                steady = min(t - self.s.last[self.s.net(self.ref, self.MAD[i])] for i in range(16))
                self.s.note("chip read data set-up", steady - 40.0, "at %.1f ns: steady %.1f ns" % (t, steady))
                if steady < 40.0: self.s.faults.append("%.1f ns: the chip's read data steady only %.1f ns (40 wanted)" % (t, steady))
                for i in range(16): self.s.holds.append((self.s.net(self.ref, self.MAD[i]), t, 10.0, "IC1 read data"))
                self.reads.append((c["addr"], None if None in bits else sum(b << i for i, b in enumerate(bits))))
            if c["kind"] in ("write", "atr"): self.mad(None, d["mwz"])
            self.log.append((t, c))
        self.mcyc = 0; self.out(52, 0, d["mcyc"])
        c = self.cyc = self.script.pop(0) if self.script else {"kind": "dummy"}
        k = c["kind"]; a = c.get("addr", 0); ch = c.get("chr", 0)
        self.out(54, 0 if k in ("read", "write") else 1, d["ctl"])                    # DRAW
        self.out(55, 0 if k in ("write", "win") else 1, d["ctl"])                     # MRD: low marks a write or the Window
        self.out(56, ch, d["ctl"])
        hi = c.get("ra", 0) if ch else a >> 16
        for i, p in enumerate((37, 36, 35, 34)): self.out(p, hi >> i & 1, d["ctl"])
        self.out(33, c.get("ra", 0) >> 4 & 1 if ch else 0, d["ctl"])
        self.out(12, c.get("hs", 1), d["sync"]); self.out(63, c.get("disp", 1), d["sync"])
        if k in ("dummy", "atr", "idle"): self.mad(0 if k == "dummy" else None, d["mad"])
        else:
            self.out(53, 0, d["as"]); self.mad(a & 0xFFFF, d["mad"])


MODELS = {k: Gate for k in Gate.TABLE}
MODELS.update({"74": FF74, "163": Counter163, "377": Reg377, "574": Reg574, "573": Latch573, "299": Shift299, "164": Shift164,
               "245": Buf245, "244": Buf244, "138": Dec138, "ram": Ram, "rom": Rom, "chip": Chip})
PS2 = ["IC24", "IC25", "IC26", "IC27", "IC28", "IC29", "IC30"]            # not simulated (V2.0's section, proved there)
DMAX = {"mcyc": 40.0, "as": 65.0, "asr": 12.0, "mad": 70.0, "maz": 50.0, "mwd": 70.0, "mwz": 40.0, "ctl": 70.0, "sync": 70.0, "atr": 80.0}
DMIN = {"mcyc": 10.0, "as": 15.0, "asr": 4.0, "mad": 15.0, "maz": 12.0, "mwd": 20.0, "mwz": 12.0, "ctl": 12.0, "sync": 12.0, "atr": 20.0}


def build(delays, count0, text):
    Sim.count0 = count0
    s = Sim(fitted_out=PS2 + ([] if text else N.TEXT_A))
    s.count0 = count0; s.d = delays
    s.parts["IC7"].q[0] = 1                                           # the -WE flip-flop starts high (at power-up it may not)
    s.force("-RESET", 1); s.force("-IO-WR", 1); s.force("-IO-RD", 1)
    s.force("RSEL", 1)                                                # JP4 1-2: the 128K RAMs' CE2 high
    for i in range(4): s.force("IO-ADDR%d" % i, 0)
    s.run(0.0)
    for m in s.parts.values(): m.eval()
    s.samples = {}                                                    # CK edge number -> the nets' values just before it
    return s


# samples[k] is what is on the wires in the dot period after the dot clock's edge k (taken just before edge k + 1)
def clock(s, dots, watch=("VDOT", "GDEL", "TDOT", "VR", "VG", "VB", "HSB", "VSB", "OFFR", "OFFG", "OFFB", "POLH", "POLV")):
    """dots periods of the dot clock; before each rising edge the watched nets are sampled (the dot now on the wire)"""
    n0 = getattr(s, "nck", 0)
    for i in range(dots):
        t0 = (n0 + i) * DOT
        s.run(t0 + DOT / 2 - 0.01); s.force("CK", 0); s.run(t0 + DOT - 0.01)
        s.samples[n0 + i] = {w: s.val.get(w) for w in watch}
        s.force("CK", 1)
    s.nck = n0 + dots
    s.run(s.nck * DOT - 0.02)


def edge_of(s, t): return int(round(t / DOT))                         # the dot clock edge nearest a time


def stream(s, net, first, n): return [s.samples[first + i][net] for i in range(n)]


def bits(word, n=16): return [word >> i & 1 for i in range(n)]


def word_at(s, a): return s.parts["IC10"].mem.get(a, s.parts["IC10"].default(a)) | s.parts["IC11"].mem.get(a, s.parts["IC11"].default(a)) << 8


def finish(s, name, checks):
    out = []
    for (net, who), (dur, t0) in sorted(s.fights.items()):
        s.note("outputs overlapping", OVERLAP - dur, "%s (%s) for %.1f ns at %.1f ns" % (net, ", ".join(who), dur, t0))
        if dur > OVERLAP: out.append("two outputs on %s (%s) for %.1f ns from %.1f ns" % (net, ", ".join(who), dur, t0))
    out += s.faults + [c for c in checks if c]
    if VERBOSE or out:
        for k in sorted(s.margin): print("      %-24s %6.1f ns to spare   %s" % (k, s.margin[k][0], s.margin[k][1]))
    return out


def interleaved(delays, count0):
    s = build(delays, count0, text=False)
    chip = s.parts["IC1"]; chk = []
    W1, W2 = 0xA55A, 0x0FF1
    script = [{"kind": "dummy"}] * 6 + [
        {"kind": "disp", "addr": 0x00123}, {"kind": "write", "addr": 0x00200, "data": W1},
        {"kind": "disp", "addr": 0x00124}, {"kind": "read", "addr": 0x00200},
        {"kind": "disp", "addr": 0x00125}, {"kind": "dummy"},
        {"kind": "disp", "addr": 0x00200}, {"kind": "read", "addr": 0x80321},
        {"kind": "disp", "addr": 0x0FFFF}, {"kind": "write", "addr": 0x80010, "data": 0x1234},
        {"kind": "disp", "addr": 0x10000, "disp": 0}, {"kind": "write", "addr": 0x1FFFF, "data": W2},
        {"kind": "disp", "addr": 0x1FFFF, "disp": 0}, {"kind": "read", "addr": 0x1FFFF},
        # HSYNC: the display off, three cycles with HSYNC low, the attribute byte in the last
        {"kind": "dummy", "hs": 0}, {"kind": "write", "addr": 0x00300, "data": 0xFFEA, "hs": 0}, {"kind": "atr", "data": 0x15, "hs": 0},
        {"kind": "dummy"}, {"kind": "dummy"},
        {"kind": "disp", "addr": 0x00200, "disp": 0}, {"kind": "dummy"}, {"kind": "disp", "addr": 0x00123, "disp": 0}, {"kind": "dummy"}, {"kind": "dummy"}]
    chip.script = list(script)
    clock(s, 8 * (len(script) + 4))
    # the counter in step: QC low in the address half
    qc = s.parts["IC6"]
    ends = {id(c): t for t, c in chip.log}
    by = [(t, c) for t, c in chip.log]
    # the writes
    for ram in ("IC10", "IC11"):
        got = [(a, v) for _, a, v in s.parts[ram].wrote]
        sh = 0 if ram == "IC10" else 8
        want = [(0x00200, W1 >> sh & 255), (0x1FFFF, W2 >> sh & 255), (0x00300, 0xFFEA >> sh & 255)]
        if got != want: chk.append("%s was written %r, not %r" % (ram, [(hex(a), hex(v)) for a, v in got], [(hex(a), hex(v)) for a, v in want]))
    # the reads: the word written; the font's byte on both halves; the last word of the RAM
    fb = s.parts["IC14"].byte(0x321)
    want = [(0x00200, W1), (0x80321, fb | fb << 8), (0x1FFFF, W2)]
    if chip.reads != want: chk.append("the chip read %r, not %r" % ([(hex(a), v if v is None else hex(v)) for a, v in chip.reads], [(hex(a), hex(v)) for a, v in want]))
    # the loads: one for each display cycle, at its end, and the 16 dots after it
    disp = [(t, c) for t, c in by if c["kind"] == "disp"]
    loads = s.parts["IC23"].loads
    if len(loads) != len(disp): chk.append("%d loads of the shift registers for %d display cycles" % (len(loads), len(disp)))
    lag = None
    for t, c in disp:
        e = edge_of(s, t - DELAY["163"])                               # the dot clock edge that made the chip's 2CLK edge
        w = word_at(s, c["addr"])
        if stream(s, "VDOT", e, 16) != bits(w): chk.append("the word at %05X left the shift registers as %r" % (c["addr"], stream(s, "VDOT", e, 16)))
        on = c.get("disp", 1) == 0                                     # DISP1 is active low
        want = bits(w) if on else [0] * 16
        if stream(s, "GDEL", e + 8, 16) != want: chk.append("the word at %05X, 8 dots on, display %s: %r" % (c["addr"], "on" if on else "off", stream(s, "GDEL", e + 8, 16)))
        atr = 0x15 if t > [tt for tt, cc in by if cc["kind"] == "atr"][0] + 8 * DOT else 0
        for gun, bit in (("VR", 1), ("VG", 2), ("VB", 4)):
            w2 = [0] * 16 if atr & bit else want
            if stream(s, gun, e + 8, 16) != w2: chk.append("%s for the word at %05X (ATR %02X): %r" % (gun, c["addr"], atr, stream(s, gun, e + 8, 16)))
    # the control register: 00 until the attribute cycle has passed and HSYNC is high again, then 15; HSYNC's pin follows
    ta = [t for t, c in by if c["kind"] == "atr"][0]; ea = edge_of(s, ta)
    reg = lambda n: sum((s.samples[n][k] or 0) << i for i, k in enumerate(("OFFR", "OFFG", "OFFB", "POLH", "POLV")))
    for n in range(8, ea + 1):
        if reg(n) != 0: chk.append("the control register is %02X at dot clock %d, before the attribute byte's cycle ended" % (reg(n), n)); break
    if reg(ea + 12) != 0x15: chk.append("the control register is %02X after the attribute byte 15" % reg(ea + 12))
    th = [t for t, c in by if c.get("hs", 1) == 0][0]; eh = edge_of(s, th)
    if stream(s, "HSB", eh - 4, 2) != [0, 0] or s.samples[ea + 30]["HSB"] != 1: chk.append("HSYNC to the connector: low in the pulse, high after it, wanted")
    if s.samples[ea + 30]["VSB"] != 0: chk.append("VSYNC positive (ATR bit 4): the line should be low outside the pulse")
    return finish(s, "interleaved", chk)


def superimposed(delays, count0):
    s = build(delays, count0, text=True)
    chip = s.parts["IC1"]; chk = []
    CW = 0x4241                                                        # the character word: 'A' on the left, 'B' on the right
    line = 6                                                           # even lines too: RA0 is on the MA16 pin
    script = [{"kind": "dummy"}] * 6 + [
        {"kind": "disp", "addr": 0x00123, "disp": 0}, {"kind": "write", "addr": 0x1234, "data": CW, "chr": 1, "ra": 8, "disp": 0},
        {"kind": "disp", "addr": 0x00124, "disp": 0}, {"kind": "win", "addr": 0x1234, "chr": 1, "ra": line, "disp": 0},
        {"kind": "disp", "addr": 0x00125, "disp": 0}, {"kind": "win", "addr": 0x1235, "chr": 1, "ra": 15, "disp": 0},
        {"kind": "disp", "addr": 0x00126, "disp": 0}, {"kind": "dummy", "disp": 0},
        {"kind": "disp", "addr": 0x00127, "disp": 0}, {"kind": "read", "addr": 0x1234, "chr": 1, "ra": 2, "disp": 0},
        {"kind": "dummy", "hs": 0}, {"kind": "atr", "data": 0x20, "hs": 0}, {"kind": "dummy"}, {"kind": "dummy"},     # TEXTON
        {"kind": "disp", "addr": 0x00123, "disp": 0}, {"kind": "win", "addr": 0x1234, "chr": 1, "ra": line, "disp": 0},
        {"kind": "disp", "addr": 0x00124, "disp": 0}, {"kind": "dummy", "disp": 0},
        {"kind": "dummy", "hs": 0}, {"kind": "atr", "data": 0x60, "hs": 0}, {"kind": "dummy"}, {"kind": "dummy"},     # TEXTON, XOR
        {"kind": "disp", "addr": 0x00123, "disp": 0}, {"kind": "win", "addr": 0x1234, "chr": 1, "ra": line, "disp": 0},
        {"kind": "disp", "addr": 0x00124, "disp": 0}, {"kind": "dummy", "disp": 0}, {"kind": "dummy"}, {"kind": "dummy"}, {"kind": "dummy"}]
    chip.script = list(script)
    clock(s, 8 * (len(script) + 4))
    by = list(chip.log)
    for ram, sh in (("IC10", 0), ("IC11", 8)):
        got = [(a, v) for _, a, v in s.parts[ram].wrote]
        if got != [(0x11234, CW >> sh & 255)]: chk.append("%s was written %r: the character word belongs at 11234" % (ram, [(hex(a), hex(v)) for a, v in got]))
    if chip.reads != [(0x1234, CW)]: chk.append("the chip read %r from the character screen, not %04X" % (chip.reads, CW))
    disp = [(t, c) for t, c in by if c["kind"] == "disp"]
    if len(s.parts["IC23"].loads) != len(disp): chk.append("%d loads of the graphics shift registers for %d Background cycles" % (len(s.parts["IC23"].loads), len(disp)))
    wins = [(t, c) for t, c in by if c["kind"] == "win"]
    atrs = [t for t, c in by if c["kind"] == "atr"]
    shown = [t for t, c in wins if t > atrs[0]]                         # the text shifter is held clear until TEXTON
    if len(s.parts["IC48"].loads) != 2 * len(shown): chk.append("%d loads of the text shifter for %d Window cycles with the text on" % (len(s.parts["IC48"].loads), len(shown)))
    for t, c in wins:
        e = edge_of(s, t - DELAY["163"])
        w = s.parts["IC10"].mem.get(0x10000 | c["addr"], s.parts["IC10"].default(0x10000 | c["addr"])) | \
            s.parts["IC11"].mem.get(0x10000 | c["addr"], s.parts["IC11"].default(0x10000 | c["addr"])) << 8
        atr = 0x60 if len(atrs) > 1 and t > atrs[1] else 0x20 if t > atrs[0] else 0
        text = bits(glyph(w & 255, c["ra"]), 8) + bits(glyph(w >> 8, c["ra"]), 8) if atr & 0x20 else [0] * 16
        if stream(s, "TDOT", e, 16) != text: chk.append("the character word %04X on line %d came out as %r, not %r" % (w, c["ra"], stream(s, "TDOT", e, 16), text))
        # the graphics word of the same display cycle (the Background cycle before this one) is on GDEL in the same 16 dots
        tb, cb = [(tt, cc) for tt, cc in disp if tt < t][-1]
        g = bits(word_at(s, cb["addr"]))
        if stream(s, "GDEL", e, 16) != g: chk.append("the graphics word under the text at %04X: %r, not %r" % (c["addr"], stream(s, "GDEL", e, 16), g))
        want = [a ^ b for a, b in zip(g, text)] if atr & 0x40 else [a | b for a, b in zip(g, text)]
        if stream(s, "VG", e, 16) != want: chk.append("the picture with ATR %02X at %04X: %r, not %r" % (atr, c["addr"], stream(s, "VG", e, 16), want))
    # after the last Window cycle's two characters the text shifter is empty
    t, c = wins[-1]; e = edge_of(s, t - DELAY["163"])
    if any(stream(s, "TDOT", e + 16, 24)): chk.append("text after the last Window cycle's two characters: %r" % stream(s, "TDOT", e + 16, 24))
    return finish(s, "superimposed", chk)


def ports():
    """the six ports' strobes: OUT PA / PB and IN PC / PD select the chip, with the bus buffer's direction; no other"""
    s = build(DMAX, 0, text=False)
    chk = []
    for port in range(16):
        for strobe in ("-IO-WR", "-IO-RD"):
            for i in range(4): s.force("IO-ADDR%d" % i, port >> i & 1)
            s.force("-IO-WR", 1); s.force("-IO-RD", 1); s.run(s.t + 200)
            for i in range(8): s.force("DATA%d" % i, None if strobe == "-IO-RD" else 0x5A >> i & 1)
            for i in range(8): s.force("HD%d" % i, 0xC3 >> i & 1 if strobe == "-IO-RD" else None)      # the chip's answer to a read
            s.force(strobe, 0); s.run(s.t + 400)
            cs = s.val["CS#"]
            want = 0 if (strobe == "-IO-WR" and port in (10, 11)) or (strobe == "-IO-RD" and port in (12, 13)) else 1
            if cs != want: chk.append("port %X, %s: CS is %r" % (port, strobe, cs))
            if cs == 0:
                if s.v("IC1", 5) != (port & 1) or s.v("IC1", 3) != (port >> 2 & 1): chk.append("port %X: RS %r, R/W %r" % (port, s.v("IC1", 5), s.v("IC1", 3)))
                if strobe == "-IO-WR":
                    got = sum((s.val["HD%d" % i] or 0) << i for i in range(8))
                    if got != 0x5A: chk.append("OUT port %X: the chip's data pins see %02X, not 5A" % (port, got))
                else:
                    got = sum((s.drv["DATA%d" % i].get(("IC5", str(18 - i))) or 0) << i for i in range(8))
                    if got != 0xC3: chk.append("IN port %X: the buffer puts %02X on the bus, not C3" % (port, got))
            others = {"WRPE#": ("-IO-WR", 14), "RDPE#": ("-IO-RD", 14), "RDPF#": ("-IO-RD", 15)}
            for net, (st, pt) in others.items():
                if s.val[net] != (0 if (strobe, port) == (st, pt) else 1): chk.append("port %X, %s: %s is %r" % (port, strobe, net, s.val[net]))
            s.force(strobe, 1); s.run(s.t + 200)
    s.fights = {k: v for k, v in s.fights.items() if "TB" not in k[1]}                        # not the test bench's own drivers
    return finish(s, "ports", chk)


def main():
    fails = 0
    runs = [("ports", ports, ())]
    for dn, d in (("max", DMAX), ("min", DMIN)):
        for c0 in (1, 6):
            runs.append(("interleaved, chip delays %s, counter from %d" % (dn, c0), interleaved, (d, c0)))
            runs.append(("superimposed, chip delays %s, counter from %d" % (dn, c0), superimposed, (d, c0)))
    worst = {}
    for name, f, args in runs:
        out = f(*args)
        print("%-52s %s" % (name, "PASS" if not out else "FAIL"))
        for x in out[:12]: print("    " + x)
        fails += bool(out)
    print("v30_netsim: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
