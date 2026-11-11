#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/v30_netsim.py - the video card V3's netlist run as a circuit, and its timing check (2026-11-11).

  v30_netsim.py [-v]      -v prints every run's measurements

hardware/cards/video/kicad/v3.0/v30_netlist.py is simulated gate for gate, with delays in nanoseconds: every 74xx
part, the RAMs and the EPROMs are models written here from the parts' pinouts and function tables (not from the
netlist), wired by the netlist's nets. The HD63484 is a model of its memory side from the manual's figures T-6, T-8,
T-9 and 2.1: it answers the 2CLK the card gives it with MCYC, AS, the address and data on MAD, MRD, DRAW, CHR, the
raster line, HSYNC, DISP1 and the cursors, each after its delay from the timing table, and runs a script of memory
cycles. On the bus side the test bench is the machine: it drives the port number, the data and the strobes as the
microcode's OUT and IN records do, and those records are read from test.hex to see that they do.

The delays (the tables below) are the parts' data-sheet figures, minimum and maximum, a rising and a falling output
apart. Every script runs at these corners, and from both phases the dot counter can start in:
  the chip slow (the manual's maximums) or fast (near its minimums, assumed where the manual gives none: DMIN), with
  the card's parts all at their maximum or all at their minimum: four straight corners;
  the parts' rising outputs at their minimum and their falling ones at their maximum, and the other way round: what a
  gate makes of two signals that change at the same clock edge. A clock, a clear or a latch enable that is a decode
  of counter bits shows its runt pulse here even where the straight corners miss it.

What is checked:
  interleaved access (text method A's sockets empty): the counter falls into step with MCYC; a drawing write puts
    the word into both RAMs and nowhere else; a drawing read gives the chip the word 40 ns before its cycle ends; the
    font EPROM's byte reads on both halves, also with a dummy cycle after it; every display cycle's word leaves the
    shift registers bit 0 first for 16 dots, 8 dots later after the delay line, and on the three guns one dot clock
    after that; a word fetched with the display off, a dummy cycle and a drawing cycle load nothing; the control
    register takes the attribute byte of the last cycle before HSYNC rises, when HSYNC rises, and does not move
    before; the guns follow its off bits, the syncs its polarity bits
  superimposed access (the sockets fitted): the character word of a Window cycle comes out as its two glyphs, the
    left code first, bit 0 first, exactly under the graphics word of the same display cycle, and only while the text
    layer is on (ATR bit 5); a word written to the character screen lands in the RAM's top 64K words whatever the
    raster line says; the layers OR and XOR; the second font (ATR bit 7); the cursors: CUD1 low in a Window cycle
    turns the left character to its cursor form, in the cycle after it the right one, CUD2 likewise
  the ports: OUT PA / PB and IN PC / PD select the chip and nothing else does; RS and R/W steady 50 ns before CS
    and until it has risen, though an IN record drops the port number with its strobe; CS three 2CLK cycles long
    with a step of 500 ns (a 4 MHz CPU clock); an OUT's byte at the chip 40 ns before CS rises and 10 ns after; an
    IN's byte on the bus when the record takes it; the chip and the bus buffer never both on the chip's data pins
  everywhere: every flip-flop's, register's and shift register's set-up and hold; the RAM's write pulse, data set-up
    and address; no pulse shorter than 5 ns on any clock, clear, preset, latch enable or -WE; and, in the four
    straight corners, no two outputs on a net for more than 3 ns at a handover. The memories count as on from their
    low-impedance time (10 ns after a chip enable, 5 ns after an output enable), not from when their data is good.

What the numbers are not: the chip's minimums (the manual gives maximums and a few hold times), and a bench.
"""
import os, sys, heapq, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("v30_netlist", os.path.join(ROOT, "hardware/cards/video/kicad/v3.0/v30_netlist.py"))
N = importlib.util.module_from_spec(spec); spec.loader.exec_module(N)
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
    """a part's family and type from its value: 74ACT04 -> (ACT, 04), 74F163A -> (F, 163), HD63484P8 -> (-, chip)"""
    if value.startswith("HD63484"): return "-", "chip"
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


class Chip(Part):
    """the HD63484's memory side (manual figures T-6, T-8, T-9, 2.1): a script of memory cycles, timed from 2CLK's
    falling edge with the delays of self.s.d (ns). A cycle is a dict: kind 'disp' | 'win' | 'read' | 'write' | 'dummy' |
    'atr', addr (20 bits; for a character screen 16 bits and ra = the raster line), data, chr, hs, disp."""
    MAD = {0: 61, 1: 60, 2: 59, 3: 58, 4: 57, 5: 48, 6: 47, 7: 46, 8: 45, 9: 44, 10: 43, 11: 42, 12: 41, 13: 40, 14: 39, 15: 38}
    def init(self):
        self.ck = None; self.mcyc = 1; self.cyc = None; self.script = []; self.log = []; self.reads = []
        self.out(52, 1, 0); self.out(53, 1, 0); self.out(55, 1, 0); self.out(54, 1, 0); self.out(56, 0, 0)
        self.out(12, 1, 0); self.out(13, 1, 0); self.out(63, 1, 0); self.out(1, 1, 0); self.out(2, 1, 0)
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
                self.s.atr_now = True
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
        if c is not None and c["kind"] != "atr": self.s.atr_now = False
        c = self.cyc = self.script.pop(0) if self.script else {"kind": "dummy"}
        k = c["kind"]; a = c.get("addr", 0); ch = c.get("chr", 0)
        self.out(54, 0 if k in ("read", "write") else 1, d["ctl"])                    # DRAW
        self.out(55, 0 if k in ("write", "win") else 1, d["ctl"])                     # MRD: low marks a write or the Window
        self.out(56, ch, d["ctl"])
        hi = c.get("ra", 0) if ch else a >> 16
        for i, p in enumerate((37, 36, 35, 34)): self.out(p, hi >> i & 1, d["ctl"])
        self.out(33, c.get("ra", 0) >> 4 & 1 if ch else 0, d["ctl"])
        self.out(12, c.get("hs", 1), d["sync"]); self.out(63, c.get("disp", 1), d["sync"])
        self.out(1, c.get("cud1", 1), d["sync"]); self.out(2, c.get("cud2", 1), d["sync"])     # the cursors, active low
        if k in ("dummy", "atr", "idle"): self.mad(0 if k == "dummy" else None, d["mad"])
        else:
            self.out(53, 0, d["as"]); self.mad(a & 0xFFFF, d["mad"])


MODELS = {k: Gate for k in Gate.TABLE}
MODELS.update({"74": FF74, "163": Counter163, "273": Reg273, "574": Reg574, "573": Latch573, "299": Shift299,
               "245": Buf245, "244": Buf244, "138": Dec138, "ram": Ram, "rom": Rom, "chip": Chip})
PS2 = ["IC24", "IC25", "IC26", "IC27", "IC28", "IC29", "IC30"]            # not simulated (V2.0's section, proved there)
def jp4():
    """JP4 1-2, the 128K RAMs: the net of the RAMs' pin 30 is the net on JP4's pin 1"""
    return {"RSEL": [n for n, pins in N.NETS.items() if ("JP4", "1") in pins][0]}
DMAX = {"mcyc": 40.0, "as": 65.0, "asr": 12.0, "mad": 70.0, "maz": 50.0, "mwd": 70.0, "mwz": 40.0, "ctl": 70.0, "sync": 70.0, "atr": 80.0}
DMIN = {"mcyc": 10.0, "as": 15.0, "asr": 4.0, "mad": 15.0, "maz": 12.0, "mwd": 20.0, "mwz": 12.0, "ctl": 12.0, "sync": 12.0, "atr": 20.0}


def build(delays, count0, text, corner="max"):
    """the card with the chip's delays, the parts at the slow or the fast end of their ranges, the counter's first count"""
    Sim.count0 = count0; Sim.corner = corner
    s = Sim(fitted_out=PS2 + ([] if text else N.TEXT_A), joined=jp4())
    s.count0 = count0; s.d = delays
    s.qb = TPD[("F", "163")][2 if corner in ("min", "fall") else 3]   # the chip's 2CLK edge (QB falling) comes this long after the dot clock's
    s.force("RESB#", 1)                                               # (IC30, with the PS/2 section, is not simulated)
    s.parts["IC7"].q[0] = 1                                           # the -WE flip-flop starts high (at power-up it may not)
    s.force("-RESET", 1); s.force("-IO-WR", 1); s.force("-IO-RD", 1)
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


def interleaved(delays, count0, corner="max"):
    s = build(delays, count0, False, corner)
    chip = s.parts["IC1"]; chk = []
    W1, W2 = 0xA55A, 0x0FF1
    script = [{"kind": "dummy"}] * 6 + [
        {"kind": "disp", "addr": 0x00123}, {"kind": "write", "addr": 0x00200, "data": W1},            # (the display off)
        {"kind": "disp", "addr": 0x00124, "disp": 0}, {"kind": "read", "addr": 0x00200},
        {"kind": "disp", "addr": 0x00125, "disp": 0}, {"kind": "dummy"},
        {"kind": "disp", "addr": 0x00200, "disp": 0}, {"kind": "read", "addr": 0x80321},
        {"kind": "disp", "addr": 0x0FFFF}, {"kind": "write", "addr": 0x80010, "data": 0x1234},
        {"kind": "disp", "addr": 0x10000, "disp": 0}, {"kind": "write", "addr": 0x1FFFF, "data": W2},
        {"kind": "disp", "addr": 0x1FFFF, "disp": 0}, {"kind": "read", "addr": 0x1FFFF},
        # HSYNC: the display off, three cycles with HSYNC low, the attribute byte in the last
        {"kind": "dummy", "hs": 0}, {"kind": "write", "addr": 0x00300, "data": 0xFFEA, "hs": 0}, {"kind": "atr", "data": 0x15, "hs": 0},
        {"kind": "dummy"}, {"kind": "dummy"},
        {"kind": "disp", "addr": 0x00200, "disp": 0}, {"kind": "dummy"}, {"kind": "disp", "addr": 0x00123, "disp": 0}, {"kind": "dummy"}, {"kind": "dummy"},
        # a font read with a dummy cycle after it: no AS in that one, so only VALID keeps the RAM off the font's heels
        {"kind": "read", "addr": 0x80322}, {"kind": "dummy"}, {"kind": "disp", "addr": 0x00124, "disp": 0}, {"kind": "dummy"}]
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
    fb = s.parts["IC14"].byte(0x321); fb2 = s.parts["IC14"].byte(0x322)
    want = [(0x00200, W1), (0x80321, fb | fb << 8), (0x1FFFF, W2), (0x80322, fb2 | fb2 << 8)]
    if chip.reads != want: chk.append("the chip read %r, not %r" % ([(hex(a), v if v is None else hex(v)) for a, v in chip.reads], [(hex(a), hex(v)) for a, v in want]))
    # the loads: one for each display cycle, at its end, and the 16 dots after it
    disp = [(t, c) for t, c in by if c["kind"] == "disp"]
    loads = s.parts["IC23"].loads
    shown = [c for t, c in disp if c.get("disp", 1) == 0]              # DISP1 is active low
    if len(loads) != len(shown): chk.append("%d loads of the shift registers for %d display cycles with the display on" % (len(loads), len(shown)))
    lag = None
    for t, c in disp:
        e = edge_of(s, t - s.qb)                                       # the dot clock edge that made the chip's 2CLK edge
        w = word_at(s, c["addr"])
        on = c.get("disp", 1) == 0
        want = bits(w) if on else [0] * 16                              # a word fetched with the display off is not loaded
        if stream(s, "VDOT", e, 16) != want: chk.append("the word at %05X, display %s, left the shift registers as %r" % (c["addr"], "on" if on else "off", stream(s, "VDOT", e, 16)))
        if stream(s, "GDEL", e + 8, 16) != want: chk.append("the word at %05X, 8 dots on, display %s: %r" % (c["addr"], "on" if on else "off", stream(s, "GDEL", e + 8, 16)))
        atr = 0x15 if t > [tt for tt, cc in by if cc["kind"] == "atr"][0] + 8 * DOT else 0
        for gun, bit in (("VR", 1), ("VG", 2), ("VB", 4)):
            w2 = [0] * 16 if atr & bit else want
            if stream(s, gun, e + 9, 16) != w2: chk.append("%s for the word at %05X (ATR %02X): %r" % (gun, c["addr"], atr, stream(s, gun, e + 9, 16)))
    # the control register: 00 until the attribute cycle has passed and HSYNC is high again, then 15; HSYNC's pin follows
    ta = [t for t, c in by if c["kind"] == "atr"][0]; ea = edge_of(s, ta)
    reg = lambda n: sum((s.samples[n][k] or 0) << i for i, k in enumerate(("OFFR", "OFFG", "OFFB", "POLH", "POLV")))
    for n in range(8, ea):
        if reg(n) != 0: chk.append("the control register is %02X at dot clock %d, before the attribute byte's cycle ended" % (reg(n), n)); break
    if reg(ea + 3) != 0x15: chk.append("the control register is %02X three dots after the attribute byte 15's cycle" % reg(ea + 3))
    th = [t for t, c in by if c.get("hs", 1) == 0][0]; eh = edge_of(s, th)
    if stream(s, "HSB", eh - 4, 2) != [0, 0] or s.samples[ea + 30]["HSB"] != 1: chk.append("HSYNC to the connector: low in the pulse, high after it, wanted")
    if s.samples[ea + 30]["VSB"] != 0: chk.append("VSYNC positive (ATR bit 4): the line should be low outside the pulse")
    return finish(s, "interleaved", chk)


def superimposed(delays, count0, corner="max"):
    s = build(delays, count0, True, corner)
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
        {"kind": "disp", "addr": 0x00124, "disp": 0}, {"kind": "dummy", "disp": 0},
        {"kind": "dummy", "hs": 0}, {"kind": "atr", "data": 0xA0, "hs": 0}, {"kind": "dummy"}, {"kind": "dummy"},     # TEXTON, the second font
        # the cursors: CUD1 low in the Window cycle (the left character), in the cycle after it (the right one); CUD2
        {"kind": "disp", "addr": 0x00123, "disp": 0}, {"kind": "win", "addr": 0x1234, "chr": 1, "ra": line, "disp": 0, "cud1": 0},
        {"kind": "disp", "addr": 0x00124, "disp": 0}, {"kind": "win", "addr": 0x1234, "chr": 1, "ra": 15, "disp": 0},
        {"kind": "disp", "addr": 0x00125, "disp": 0, "cud1": 0}, {"kind": "win", "addr": 0x1235, "chr": 1, "ra": 0, "disp": 0, "cud2": 0},
        {"kind": "disp", "addr": 0x00126, "disp": 0, "cud2": 0}, {"kind": "dummy", "disp": 0}, {"kind": "dummy"}, {"kind": "dummy"}, {"kind": "dummy"}]
    chip.script = list(script)
    clock(s, 8 * (len(script) + 4))
    by = list(chip.log)
    for ram, sh in (("IC10", 0), ("IC11", 8)):
        got = [(a, v) for _, a, v in s.parts[ram].wrote]
        if got != [(0x11234, CW >> sh & 255)]: chk.append("%s was written %r: the character word belongs at 11234" % (ram, [(hex(a), hex(v)) for a, v in got]))
    if chip.reads != [(0x1234, CW)]: chk.append("the chip read %r from the character screen, not %04X" % (chip.reads, CW))
    disp = [(t, c) for t, c in by if c["kind"] == "disp"]
    if len(s.parts["IC23"].loads) != len(disp): chk.append("%d loads of the graphics shift registers for %d Background cycles" % (len(s.parts["IC23"].loads), len(disp)))      # (all with the display on)
    wins = [(t, c) for t, c in by if c["kind"] == "win"]
    atrs = [(t, c["data"]) for t, c in by if c["kind"] == "atr"]
    shown = [t for t, c in wins if t > atrs[0][0]]                      # the text shifter is held clear until TEXTON
    if len(s.parts["IC48"].loads) != 2 * len(shown): chk.append("%d loads of the text shifter for %d Window cycles with the text on" % (len(s.parts["IC48"].loads), len(shown)))
    for t, c in wins:
        e = edge_of(s, t - s.qb)
        w = s.parts["IC10"].mem.get(0x10000 | c["addr"], s.parts["IC10"].default(0x10000 | c["addr"])) | \
            s.parts["IC11"].mem.get(0x10000 | c["addr"], s.parts["IC11"].default(0x10000 | c["addr"])) << 8
        atr = ([0] + [a for ta, a in atrs if ta < t])[-1]
        nxt = by[[id(cc) for tt, cc in by].index(id(c)) + 1][1]         # the cycle after: the right character's look-up
        gen = lambda code, cyc: chargen(cyc.get("cud2", 1) << 14 | (atr >> 7 & 1) << 13 | cyc.get("cud1", 1) << 12 | code << 4 | c["ra"])
        text = bits(gen(w & 255, c), 8) + bits(gen(w >> 8, nxt), 8) if atr & 0x20 else [0] * 16
        if stream(s, "TDOT", e, 16) != text: chk.append("the character word %04X on line %d came out as %r, not %r" % (w, c["ra"], stream(s, "TDOT", e, 16), text))
        # the graphics word of the same display cycle (the Background cycle before this one) is on GDEL in the same 16 dots
        tb, cb = [(tt, cc) for tt, cc in disp if tt < t][-1]
        g = bits(word_at(s, cb["addr"]))
        if stream(s, "GDEL", e, 16) != g: chk.append("the graphics word under the text at %04X: %r, not %r" % (c["addr"], stream(s, "GDEL", e, 16), g))
        want = [a ^ b for a, b in zip(g, text)] if atr & 0x40 else [a | b for a, b in zip(g, text)]
        if stream(s, "VG", e + 1, 16) != want: chk.append("the picture with ATR %02X at %04X: %r, not %r" % (atr, c["addr"], stream(s, "VG", e + 1, 16), want))
    # after the last Window cycle's two characters the text shifter is empty
    t, c = wins[-1]; e = edge_of(s, t - s.qb)
    if any(stream(s, "TDOT", e + 16, 24)): chk.append("text after the last Window cycle's two characters: %r" % stream(s, "TDOT", e + 16, 24))
    return finish(s, "superimposed", chk)


STEP = 500.0                # a microcode step, two CPU clocks: 500 ns at 4 MHz, the fastest the chip's CS allows (477 ns)
T_RSRW, T_WDATA, T_WHOLD, T_CS = 50.0, 40.0, 10.0, 3 * 4 * DOT       # the chip's host side (8 MHz grade), ns; CS three 2CLK cycles
T_RDATA, T_RREL = 80.0, 60.0                                          # its read data after CS, and released after CS


def records():
    """the microcode's I/O records, which ports() imitates: what it relies on is checked here against the tree's
    test.hex. Returns the faults"""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import ucode_wavedrom as W
    sig, recs = W.signal_table(), W.microcode()
    S = {n: (b, bt) for n, b, bt in sig}
    on = lambda w, n: W.active(w, S[n][0], S[n][1], n)
    port = lambda w: sum(on(w, "IOADDR%d" % i) << i for i in range(4))
    src = lambda w: tuple(n for n in ("-AC-RD", "-ALU-FUNC", "-MEM-RD", "-TMP-REG-RD0", "-TMP-REG-RD1", "-REG-FUNC-RD") if on(w, n))
    out = []; nw = nr = 0; drops = 0
    for op in range(256):
        w = recs[op]; st = [w[i * 8:i * 8 + 8] for i in range(64)]
        last = next((i for i in range(64) if on(st[i], "UCODE-COUNT-RESET")), 63)
        for i in range(1, last + 1):
            for strobe in ("-IO-WR", "-IO-RD"):
                if not on(st[i], strobe) or on(st[i - 1], strobe): continue
                j = i
                while j < last and on(st[j + 1], strobe): j += 1
                if i < 3 or port(st[i - 2]) != port(st[i]) or port(st[i - 1]) != port(st[i]):
                    out.append("opcode %02X: the port number is not on the bus two steps before %s" % (op, strobe))
                if any(port(st[k]) != port(st[i]) for k in range(i, j + 1)): out.append("opcode %02X: the port number moves during %s" % (op, strobe))
                if strobe == "-IO-WR":
                    nw += 1
                    if j != i: out.append("opcode %02X: -IO-WR is %d steps" % (op, j - i + 1))
                    if j + 1 > last or port(st[j + 1]) != port(st[i]): out.append("opcode %02X: the port number goes with -IO-WR" % op)
                    if not src(st[i]) or any(src(st[k]) != src(st[i]) for k in (i - 2, i - 1, j + 1) if k <= last) or j + 1 > last:
                        out.append("opcode %02X: the data is not on the bus from two steps before -IO-WR to a step after" % op)
                else:
                    nr += 1
                    takes = [k for k in range(i, min(j + 2, last + 1)) if on(st[k], "-AC-LD")]
                    if not takes or takes[0] < i + 1: out.append("opcode %02X: the byte is taken less than a step into -IO-RD" % op)
                    if j == last or port(st[j + 1]) != port(st[i]): drops += 1
    if not nw or not nr: out.append("no I/O records found in the microcode")
    return out, "%d OUT and %d IN records: the port number and the data two steps before a strobe, a step after -IO-WR; " \
                "%d of the IN records drop the port number with -IO-RD" % (nw, nr, drops)


def ports(corner="max"):
    """the bus side, driven as the microcode's records drive it (records() checks that they do): the port number, and
    for an OUT the data, on the bus two steps before the strobe; -IO-WR one step, the port number and the data staying
    a step more; -IO-RD four steps, the byte taken a step into it, the port number going in the same instant as the
    strobe. The chip is a stand-in: it answers a read 80 ns after CS and lets go 60 ns after it.
    Checked: OUT PA / PB and IN PC / PD select the chip and nothing else does, at any moment; RS and R/W are steady
    50 ns before CS and until it has risen; CS lasts three 2CLK cycles; an OUT's byte is at the chip 40 ns before CS
    rises and 10 ns after; an IN's byte is on the bus a step into the strobe; the chip and the bus buffer never drive
    the chip's data pins together; the PS/2 section's strobes come for their ports only"""
    s = build(DMAX, 0, False, corner)
    chk = []
    hd = ["HD%d" % i for i in range(8)]
    rsrw = (("RS", s.net("IC1", 5)), ("R/W", s.net("IC1", 3)))          # the nets at the chip's own pins
    def chipd(v, delay):
        for i in range(8): s.post(hd[i], ("IC1", str(17 + i)), None if v is None else v >> i & 1, delay)
    def until(net, value, limit=400.0):
        t0 = s.t
        while s.val[net] != value and s.t < t0 + limit: s.run(s.t + 0.5)
        return s.t
    s.run(s.t + STEP)
    for port in range(16):
        for strobe in ("-IO-WR", "-IO-RD"):
            wr = strobe == "-IO-WR"
            chip = port in ((10, 11) if wr else (12, 13))
            name = "%s port %X" % ("OUT" if wr else "IN", port)
            for i in range(4): s.force("IO-ADDR%d" % i, port >> i & 1)
            for i in range(8): s.force("DATA%d" % i, 0x5A >> i & 1 if wr else None)
            s.run(s.t + 2 * STEP)
            cs_before = s.last["CS#"]
            t0 = s.t; s.force(strobe, 0)
            if chip:
                tf = until("CS#", 0)
                if s.val["CS#"] != 0: chk.append("%s: no CS" % name); continue
                for pin, net in rsrw:
                    s.note("RS, R/W before CS", tf - s.last[net] - T_RSRW, "%s: %s steady %.1f ns" % (name, pin, tf - s.last[net]))
                    if tf - s.last[net] < T_RSRW: chk.append("%s: %s moved %.1f ns before CS (%.0f wanted)" % (name, pin, tf - s.last[net], T_RSRW))
                if s.v("IC1", 5) != (port & 1) or s.v("IC1", 3) != (0 if wr else 1): chk.append("%s: RS %r, R/W %r" % (name, s.v("IC1", 5), s.v("IC1", 3)))
                if not wr: chipd(0xC3, T_RDATA)
            s.run(t0 + STEP)                                           # a step into the strobe: an IN's byte is taken here
            if chip and not wr:
                got = [s.val["DATA%d" % i] for i in range(8)]
                if got != [0xC3 >> i & 1 for i in range(8)]: chk.append("%s: the bus has %r a step into -IO-RD, not C3" % (name, got))
                s.note("IN byte before its take", s.t - max(s.last["DATA%d" % i] for i in range(8)), "%s" % name)
            others = {"WRPE#": ("-IO-WR", 14), "RDPE#": ("-IO-RD", 14), "RDPF#": ("-IO-RD", 15)}
            for net, (st, pt) in others.items():
                if s.val[net] != (0 if (strobe, port) == (st, pt) else 1): chk.append("%s: %s is %r" % (name, net, s.val[net]))
            if wr: s.force(strobe, 1)                                   # -IO-WR ends; the port number and the data stay a step
            else:
                s.run(t0 + 4 * STEP); s.force(strobe, 1)                # -IO-RD ends, and the port number in the same instant
                for i in range(4): s.force("IO-ADDR%d" % i, 0)
            if chip:
                tr = until("CS#", 1)
                s.note("CS low", tr - tf - T_CS, "%s: %.1f ns" % (name, tr - tf))
                if tr - tf < T_CS: chk.append("%s: CS low %.1f ns (%.1f wanted)" % (name, tr - tf, T_CS))
                for pin, net in rsrw:
                    if s.last[net] > tf: chk.append("%s: %s moved %.1f ns before CS rose" % (name, pin, tr - s.last[net]))
                if wr:
                    steady = tr - max(s.last[n] for n in hd)
                    got = sum((s.val[n] or 0) << i for i, n in enumerate(hd))
                    s.note("OUT data before CS ends", steady - T_WDATA, "%s: steady %.1f ns" % (name, steady))
                    if got != 0x5A or steady < T_WDATA: chk.append("%s: the chip's data pins have %02X, steady %.1f ns, as CS rises" % (name, got, steady))
                    s.run(tr + T_WHOLD)
                    if max(s.last[n] for n in hd) > tr: chk.append("%s: the chip's data moved within %.0f ns of CS rising" % (name, T_WHOLD))
                else: chipd(None, T_RREL)
            s.run(s.t + STEP)
            if not chip and s.last["CS#"] != cs_before: chk.append("%s: CS moved at %.1f ns" % (name, s.last["CS#"]))
            for i in range(8): s.force("DATA%d" % i, None)
    s.fights = {k: v for k, v in s.fights.items() if "TB" not in k[1]}                        # not the test bench's own drivers
    return finish(s, "ports", chk)


def main():
    fails = 0
    out, what = records()
    print("%-66s %s" % ("the microcode's I/O records", "PASS" if not out else "FAIL"))
    print("    " + what)
    for x in out[:12]: print("    " + x)
    fails += bool(out)
    runs = [("ports, parts slow", ports, ("max",)), ("ports, parts fast", ports, ("min",))]
    for cn, d, corner, phases in (("chip slow, parts slow", DMAX, "max", (1, 6)), ("chip slow, parts fast", DMAX, "min", (1,)),
                                  ("chip fast, parts slow", DMIN, "max", (1,)), ("chip fast, parts fast", DMIN, "min", (1, 6)),
                                  ("chip slow, rises fast, falls slow", DMAX, "rise", (1,)), ("chip slow, rises slow, falls fast", DMAX, "fall", (1,)),
                                  ("chip fast, rises fast, falls slow", DMIN, "rise", (1,)), ("chip fast, rises slow, falls fast", DMIN, "fall", (1,))):
        for c0 in phases:
            runs.append(("interleaved, %s, counter from %d" % (cn, c0), interleaved, (d, c0, corner)))
            runs.append(("superimposed, %s, counter from %d" % (cn, c0), superimposed, (d, c0, corner)))
    for name, f, args in runs:
        out = f(*args)
        print("%-66s %s" % (name, "PASS" if not out else "FAIL"))
        for x in out[:12]: print("    " + x)
        fails += bool(out)
    print("v30_netsim: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
