#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/netsim.py - a video card's netlist run as a circuit, gate for gate, with the parts' data-sheet delays
(2026-11-11, from the V3 card's check; on its own since 2026-11-18, when the V3 design left the tree).

Not run by itself: tests/video/v40_netsim.py sets N to its netlist module (NETS, PARTS, PINS) and builds its runs from
Sim and the part models here. Every 74xx part, the RAMs and the EPROMs are models written from the parts' pinouts and
function tables (not from the netlist), wired by the netlist's nets.

The delays (the tables below) are the parts' data-sheet figures, minimum and maximum, a rising and a falling output
apart. A run picks its corner (Sim.corner): every part at its maximum or its minimum, or the parts' rising outputs at
their minimum and their falling ones at their maximum and the other way round: what a gate makes of two signals that
change at the same clock edge. A clock, a clear or a latch enable that is a decode of counter bits shows its runt
pulse there even where the straight corners miss it.

What every run checks (finish()): every flip-flop's, register's and shift register's set-up and hold; the RAM's write
pulse, data set-up and address; no pulse shorter than 5 ns on any clock, clear, preset, latch enable or -WE; and, in
the four straight corners, no two outputs on a net for more than 3 ns at a handover. The memories count as on from
their low-impedance time (10 ns after a chip enable, 5 ns after an output enable), not from when their data is good.
"""
import os, sys, heapq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
N = None                                               # the netlist module: set by the card's check
VERBOSE = "-v" in sys.argv
DOT = 1000.0 / 25.175                                  # ns

# The parts' delays from their data sheets, 5 V +- 0.5 V, 50 pF, over temperature: (tPLH min, max, tPHL min, max) ns.
# TI: SN74F163A (SDFS088A), SN74F74 (SDFS046A), SN74F299 (SDFS071B), SN74F21, SN74ACT00 / 04 / 08 / 10 / 11 / 32 / 86,
# CD74ACT02, SN74ACT573 / 574 / 245, CD74ACT273 (SCHS249C). The 74HCT parts (the ports' decode and the bus buffer) only
# see the bus's 2 us strobes: one generous figure.
TPD = {("F", "163"): (2.7, 9.5, 2.7, 11.0),             # clock to Q: counting 2.7-8.5 / 2.7-11, loading 3.2-9.5
       ("F", "74"): (3.0, 7.8, 3.6, 9.2), ("F", "299"): (3.2, 10.0, 2.7, 9.5), ("F", "21"): (1.0, 5.3, 1.5, 5.5),
       ("ACT", "00"): (1.0, 9.5, 1.0, 8.0), ("ACT", "04"): (1.0, 9.0, 1.0, 8.5), ("ACT", "08"): (1.0, 10.0, 1.0, 10.0),
       ("ACT", "10"): (1.0, 10.0, 1.0, 9.5), ("ACT", "11"): (1.0, 10.5, 1.0, 10.5), ("ACT", "32"): (1.0, 10.0, 1.0, 10.0),
       ("ACT", "86"): (1.0, 10.0, 1.0, 10.5), ("ACT", "02"): (3.1, 11.1, 3.1, 11.1),
       ("ACT", "573"): (2.0, 12.0, 2.0, 12.0), ("ACT", "574"): (2.0, 12.0, 1.5, 11.0), ("ACT", "273"): (3.5, 12.3, 3.5, 12.3),
       ("ACT", "245"): (1.5, 8.0, 1.0, 9.0), ("HCT", "*"): (5.0, 40.0, 5.0, 40.0)}
PRECLR = {("F", "74"): (2.4, 7.1, 2.7, 10.5), ("F", "299"): (3.7, 10.5, 3.7, 10.5), ("ACT", "273"): (3.5, 12.3, 3.5, 12.3)}
ENABLE = {("ACT", "245"): (1.5, 12.0), ("ACT", "574"): (1.5, 10.0), ("ACT", "573"): (1.5, 11.0), ("HCT", "*"): (5.0, 45.0)}
DISABLE = {("ACT", "245"): (1.0, 11.0), ("ACT", "574"): (1.5, 11.5), ("ACT", "573"): (1.0, 12.5), ("HCT", "*"): (5.0, 40.0)}
# set-up and hold before / after the clock, ns
SETUP = {("F", "74"): (3.0, 1.0), ("F", "163", "data"): (5.0, 2.0), ("F", "163", "load"): (11.5, 2.0),
         ("F", "299", "mode"): (8.5, 0.0), ("F", "299", "data"): (5.5, 2.0), ("ACT", "273"): (2.0, 2.0), ("ACT", "574"): (2.5, 1.0)}
# Alliance AS6C1008-55 (v1.2, 2023): tAA 55, tOE 30, tOH 10, tOLZ 5, tOHZ 20; write tWP 45, tDW 25, tAW 50.
# Atmel AT27C256R-70 (doc 0014): tACC 70, tOE 30, tDF 25, tOH 7. (min, max): where the sheet gives no minimum, a small one
# A memory's outputs are on (and fight whatever else is) from its low-impedance time at any corner: the RAM's tCLZ 10 ns
# after its chip enable and tOLZ 5 ns after its output enable, whichever is later (the EPROM's sheet has neither: 5 ns
# for both). What they carry is unknown (X) until the access time from the address, the chip enable or the output
# enable, whichever is last. Outputs disabled again before the low-impedance time never came on
MEM = {"ram_aa": (12.0, 55.0), "ram_oe": (5.0, 30.0), "ram_oh": (10.0, 10.0), "ram_hz": (2.0, 20.0), "ram_clz": (10.0, 10.0), "ram_olz": (5.0, 5.0),
       "rom_acc": (9.0, 70.0), "rom_oe": (5.0, 30.0), "rom_oh": (7.0, 7.0), "rom_hz": (2.0, 25.0), "rom_clz": (5.0, 5.0), "rom_olz": (5.0, 5.0)}
RAM_TWP, RAM_TDW, RAM_TAW = 45.0, 25.0, 50.0           # write pulse, data set-up to its end, address valid to its end
OVERLAP = 3.0                                          # two three-state outputs may both be on this long at a handover
FLOAT = 300.0                                          # a 10k pull-up needs about this long to move an undriven bus line
# a clock, a clear, a preset, a latch enable or the RAM's -WE must not see a pulse shorter than this: a gate that decodes
# two counter bits changing at once gives one (the bits' rise and fall times differ), and a flip-flop may take it or not
MINPULSE = 5.0
# the pins that act on an edge or a level by themselves (not sampled by a clock), by model
EDGE_PINS = {"74": (3, 11, 1, 4, 10, 13), "163": (2,), "273": (11, 1), "574": (11,), "573": (11,), "299": (12, 9), "ram": (29,)}


def family(value):
    """a part's family and type from its value: 74ACT04 -> (ACT, 04), 74F163A -> (F, 163)"""
    if value.startswith("AS6C"): return "-", "ram"
    if "27C256" in value: return "-", "rom"
    if value == "7416": return "-", "16"
    if value.startswith("74"):
        fam = value[2:].rstrip("0123456789A") if value[-1] == "A" else value[2:].rstrip("0123456789")
        num = value[2 + len(fam):].rstrip("A")
        return fam, num
    return "-", None


def AND(*a): return 0 if 0 in a else (None if None in a else 1)
def OR(*a): return 1 if 1 in a else (None if None in a else 0)
def NOT(a): return None if a is None else 1 - a
def XOR(a, b): return None if a is None or b is None else a ^ b


class Sim:
    # which end of the parts' delay ranges this run uses: "max", "min", or the two that set a part's rising outputs
    # against its falling ones, "rise" (tPLH at its minimum, tPHL at its maximum) and "fall" (the other way round).
    # Enables, disables and the memories' times are at their maximum in those two
    corner = "max"

    def mem(self, key): return MEM[key][0 if self.corner == "min" else 1]

    def __init__(self, fitted_out=(), joined={}):
        """joined: nets a fitted jumper makes one, {net: the net it is joined to}"""
        self.t = 0.0; self.q = []; self.seq = 0; self.pending = {}; self.floating = {}
        self.netof = {}; self.onnet = {}
        for net, pins in N.NETS.items():
            net = joined.get(net, net)
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
            fam, k = family(value)
            if k in MODELS: self.parts[ref] = MODELS[k](self, ref, fam, k)
        self.edgenets = {}                              # net -> the pins on it that a runt pulse would upset
        for ref, m in self.parts.items():
            for pin in EDGE_PINS.get(m.k, ()):
                net = self.netof.get((ref, str(pin)))
                if net and net not in ("VCC", "GND", "CK"): self.edgenets.setdefault(net, []).append("%s.%d" % (ref, pin))
        self.lastedge = {}; self.runts = {}
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
        if "X" in vals: return None                    # an output is on, with nothing known on it yet
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
                if net in self.edgenets and new in (0, 1) and self.val[net] in (0, 1):
                    w = t - self.lastedge.get(net, -1e9); self.lastedge[net] = t
                    if w < MINPULSE - 1e-9 and (net not in self.runts or w < self.runts[net][0]): self.runts[net] = (w, t)
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
    def __init__(self, sim, ref, fam, k): self.s = sim; self.ref = ref; self.fam = fam; self.k = k; self.init()
    def init(self): pass
    def v(self, pin): return self.s.v(self.ref, pin)
    def key(self, table): return (self.fam, self.k) if (self.fam, self.k) in table else (self.fam, "*")
    def tpd(self, value, table=None):
        """the delay to an output's new value: tPLH for 1, tPHL for 0, at this run's end of the data sheet's range"""
        t = (table or TPD)[self.key(table or TPD)]
        cn = self.s.corner
        if value == 1: return t[0 if cn in ("min", "rise") else 1]
        if value == 0: return t[2 if cn in ("min", "fall") else 3]
        return min(t[0], t[2]) if cn == "min" else max(t[1], t[3])
    def out(self, pin, value, delay=None, table=None): self.s.drive(self.ref, pin, value, self.tpd(value, table) if delay is None else delay)
    def onoff(self, on): return (ENABLE if on else DISABLE)[self.key(ENABLE)][0 if self.s.corner == "min" else 1]
    def su(self, pin, what, sub=None):
        tsu, th = SETUP[(self.fam, self.k, sub)] if sub else SETUP[(self.fam, self.k)]
        self.s.setup(self.ref, pin, tsu, th, "74%s%s %s" % (self.fam, self.k, what))
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
            self.out(g[-1], f(*[self.v(p) for p in g[:-1]]))


class FF74(Part):
    def init(self): self.q = {0: 0, 1: 0}
    def eval(self):
        for i, (clr, d, ck, pre, q, qn) in enumerate(((1, 2, 3, 4, 5, 6), (13, 12, 11, 10, 9, 8))):
            edge = self.rose(ck, "ck%d" % i); old = self.q[i]; table = None
            if self.v(pre) == 0: self.q[i] = 1; table = PRECLR
            elif self.v(clr) == 0: self.q[i] = 0; table = PRECLR
            elif edge:
                self.su(d, "D")
                self.q[i] = self.v(d)
            if self.q[i] != old or not hasattr(self, "up%d" % i):
                setattr(self, "up%d" % i, 1)
                self.out(q, self.q[i], table=table); self.out(qn, NOT(self.q[i]), table=table)


class Counter163(Part):
    def init(self): self.n = getattr(self.s, "count0", 0); self.first = True
    def eval(self):
        if self.rose(2):
            if self.v(1) == 0: self.n = 0
            elif self.v(9) == 0:
                for p in (3, 4, 5, 6): self.su(p, "load data", "data")
                bits = [self.v(p) for p in (3, 4, 5, 6)]
                self.n = sum((b or 0) << i for i, b in enumerate(bits))
            elif self.v(7) == 1 and self.v(10) == 1: self.n = (self.n + 1) & 15
            self.su(9, "-LOAD", "load")
            self.first = True
        if self.first:
            self.first = False
            for i, p in enumerate((14, 13, 12, 11)): self.out(p, self.n >> i & 1)


class Reg273(Part):
    PAIRS = ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19))
    def init(self): self.q = [0] * 8; self.up = False
    def eval(self):
        table = None
        if self.v(1) == 0:
            if any(self.q): self.up = False
            self.q = [0] * 8; table = PRECLR
        elif self.rose(11):
            if self.ref != "IC34" or getattr(self.s, "atr_now", False):     # IC34 takes whatever floats on MAD in the
                for d, q in self.PAIRS: self.su(d, "D")                    # other cycles of HSYNC: nothing uses it
            self.q = [self.v(d) for d, q in self.PAIRS]; self.up = False
        if not self.up:
            self.up = True
            for (d, q), x in zip(self.PAIRS, self.q): self.out(q, x, table=table)


class Reg574(Part):
    def init(self): self.q = [0] * 8; self.oe = None
    def eval(self):
        new = self.rose(11)
        if new:
            for d in range(2, 10): self.su(d, "D")
            self.q = [self.v(d) for d in range(2, 10)]
        oe = self.v(1)
        if new or oe != self.oe:
            sw = oe != self.oe
            self.oe = oe
            for i, x in enumerate(self.q):
                val = x if oe == 0 else None
                self.out(19 - i, val, self.onoff(oe == 0) if sw else None)


class Latch573(Part):
    def init(self): self.q = [None] * 8
    def eval(self):
        if self.v(11) == 1: self.q = [self.v(d) for d in range(2, 10)]
        for i, x in enumerate(self.q): self.out(19 - i, x if self.v(1) == 0 else None)


class Shift299(Part):
    IO = {0: 7, 1: 13, 2: 6, 3: 14, 4: 5, 5: 15, 6: 4, 7: 16}
    def init(self): self.q = [0] * 8; self.up = False; self.loads = []
    def eval(self):
        table = None
        if self.v(9) == 0:
            if any(self.q): self.up = False
            self.q = [0] * 8; table = PRECLR
        elif self.rose(12):
            s0, s1 = self.v(1), self.v(19)
            self.su(19, "S1", "mode")
            if s0 == 1 and s1 == 1:
                for i in range(8): self.su(self.IO[i], "data", "data")
                self.q = [self.v(self.IO[i]) for i in range(8)]; self.loads.append(self.s.t)
            elif s0 == 1 and s1 == 0:
                self.su(11, "serial in", "data")
                self.q = [self.v(11)] + self.q[:7]
            elif s0 == 0 and s1 == 1: self.q = self.q[1:] + [self.v(18)]
            self.up = False
        else: self.rose(12)
        if not self.up:
            self.up = True
            self.out(8, self.q[0], table=table); self.out(17, self.q[7], table=table)


class Buf245(Part):
    def init(self): self.on = None
    def eval(self):
        on, d = self.v(19) == 0, self.v(1)
        sw = on != self.on
        self.on = on
        for i in range(8):
            a, b = 2 + i, 18 - i
            vb = self.v(a) if on and d == 1 else None; va = self.v(b) if on and d == 0 else None
            self.out(b, vb, self.onoff(on) if sw else None); self.out(a, va, self.onoff(on) if sw else None)


class Buf244(Part):
    def eval(self):
        for oe, pairs in ((1, ((2, 18), (4, 16), (6, 14), (8, 12))), (19, ((11, 9), (13, 7), (15, 5), (17, 3)))):
            for a, y in pairs: self.out(y, self.v(a) if self.v(oe) == 0 else None)


class Dec138(Part):
    def eval(self):
        en = self.v(6) == 1 and self.v(4) == 0 and self.v(5) == 0
        n = sum((self.v(p) or 0) << i for i, p in enumerate((1, 2, 3)))
        for i, p in enumerate((15, 14, 13, 12, 11, 10, 9, 7)): self.out(p, 0 if en and i == n else 1)


class Ram(Part):
    A = {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7, 6: 6, 7: 5, 8: 27, 9: 26, 10: 23, 11: 25, 12: 4, 13: 28, 14: 3, 15: 31, 16: 2}
    D = (13, 14, 15, 17, 18, 19, 20, 21)
    def init(self): self.mem = {}; self.we = 1; self.wrote = []; self.outv = "?"; self.was = (None, False, False); self.since = [-1e9] * 3
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
                st = self.s.t - self.s.last[net]
                self.s.note("RAM address to write end", st - RAM_TAW, "%s A%d at %.1f ns: steady %.1f ns" % (self.ref, i, self.s.t, st))
            if a is None or None in data: self.s.faults.append("%.1f ns: %s written with an unknown address or data" % (self.s.t, self.ref))
            else:
                self.mem[a] = sum(b << i for i, b in enumerate(data)); self.wrote.append((self.s.t, a, self.mem[a]))
        self.we = we
        oe = self.v(24) == 0 and we == 1
        on = sel and oe
        a = self.addr()
        now = (a, sel, oe)                                         # when each of the three last became what it is
        for i in range(3):
            if now[i] != self.was[i] and (i == 0 or now[i]): self.since[i] = self.s.t
        self.was = now
        key = (on, a)
        if key == self.outv: return
        was_on = self.outv != "?" and self.outv[0]
        self.outv = key
        if not on:
            never = self.s.t < getattr(self, "on_at", -1e9) - 1e-9      # disabled before the outputs came on at all
            if never: self.s.note("memory off before it is on", self.on_at - self.s.t, "%s at %.1f ns" % (self.ref, self.s.t))
            for p in self.D: self.out(p, None, 0.0 if never else self.s.mem("ram_hz"))
            return
        value = None if a is None else self.mem.get(a, self.default(a))
        m = self.s.mem
        # the old word goes after its hold time; or the outputs come on
        first = m("ram_oh") if was_on else max(self.since[1] + m("ram_clz"), self.since[2] + m("ram_olz"), self.s.t) - self.s.t
        if not was_on: self.on_at = self.s.t + first
        ready = max(self.since[0] + m("ram_aa"), self.since[1] + m("ram_aa"), self.since[2] + m("ram_oe")) - self.s.t
        for i, p in enumerate(self.D):
            self.out(p, "X", first); self.out(p, "X" if value is None else value >> i & 1, max(ready, first + 0.1))


class Rom(Part):
    A = {0: 10, 1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 25, 9: 24, 10: 21, 11: 23, 12: 2, 13: 26, 14: 27}
    D = (11, 12, 13, 15, 16, 17, 18, 19)
    def init(self): self.outv = "?"; self.was = (None, False, False); self.since = [-1e9] * 3
    def byte(self, a): return (a * 5 + 0x33) & 255 if self.ref == "IC14" else chargen(a)
    def eval(self):
        ce, oe = self.v(20) == 0, self.v(22) == 0
        on = ce and oe
        bits = [self.v(self.A[i]) for i in range(15)]
        a = None if None in bits else sum(b << i for i, b in enumerate(bits))
        now = (a, ce, oe)
        for i in range(3):
            if now[i] != self.was[i] and (i == 0 or now[i]): self.since[i] = self.s.t
        self.was = now
        if (on, a) == self.outv: return
        was_on = self.outv != "?" and self.outv[0]
        self.outv = (on, a)
        if not on:
            never = self.s.t < getattr(self, "on_at", -1e9) - 1e-9      # disabled before the outputs came on at all
            if never: self.s.note("memory off before it is on", self.on_at - self.s.t, "%s at %.1f ns" % (self.ref, self.s.t))
            for p in self.D: self.out(p, None, 0.0 if never else self.s.mem("rom_hz"))
            return
        m = self.s.mem
        first = m("rom_oh") if was_on else max(self.since[1] + m("rom_clz"), self.since[2] + m("rom_olz"), self.s.t) - self.s.t
        if not was_on: self.on_at = self.s.t + first
        ready = max(self.since[0] + m("rom_acc"), self.since[1] + m("rom_acc"), self.since[2] + m("rom_oe")) - self.s.t
        value = None if a is None else self.byte(a)
        for i, p in enumerate(self.D):
            self.out(p, "X", first); self.out(p, "X" if value is None else value >> i & 1, max(ready, first + 0.1))


def glyph(code, line): return (code * 3 + line * 17 + 1) & 255       # the test character generator's byte


def chargen(a, cud1=None, font2=None, cud2=None):
    """the test character generator: the glyph, turned over where CUD1 (A12) is low, and marked by the second font
    (A13) and by CUD2 (A14) low"""
    g = glyph(a >> 4 & 255, a & 15)
    return g ^ (0 if a >> 12 & 1 else 0xFF) ^ (0x55 if a >> 13 & 1 else 0) ^ (0 if a >> 14 & 1 else 0x0F)


MODELS = {k: Gate for k in Gate.TABLE}
MODELS.update({"74": FF74, "163": Counter163, "273": Reg273, "574": Reg574, "573": Latch573, "299": Shift299,
               "245": Buf245, "244": Buf244, "138": Dec138, "ram": Ram, "rom": Rom})


def edge_of(s, t): return int(round(t / DOT))                         # the dot clock edge nearest a time


def stream(s, net, first, n): return [s.samples[first + i][net] for i in range(n)]


def bits(word, n=16): return [word >> i & 1 for i in range(n)]


def finish(s, name, checks):
    out = []
    # handovers are judged in the four straight corners: the two others set every flip-flop's Q against its own -Q by the
    # whole spread of the data sheet, and are there for what gates make of signals that change together
    for (net, who), (dur, t0) in sorted(s.fights.items()):
        if s.corner in ("rise", "fall"): continue
        s.note("outputs overlapping", OVERLAP - dur, "%s (%s) for %.1f ns at %.1f ns" % (net, ", ".join(who), dur, t0))
        if dur > OVERLAP: out.append("two outputs on %s (%s) for %.1f ns from %.1f ns" % (net, ", ".join(who), dur, t0))
    for net, (w, t) in sorted(s.runts.items()):
        out.append("a pulse of %.1f ns on %s (%s) at %.1f ns: %.1f ns is the least a clock or an enable may be" % (w, net, ", ".join(s.edgenets[net]), t, MINPULSE))
    out += s.faults + [c for c in checks if c]
    if VERBOSE or out:
        for k in sorted(s.margin): print("      %-24s %6.1f ns to spare   %s" % (k, s.margin[k][0], s.margin[k][1]))
    return out
